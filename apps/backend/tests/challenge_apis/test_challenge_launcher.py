"""
추천 실행기(ChallengeRecommendationLauncher)의 백그라운드 실행을 DB 없이 검증합니다.
API 테스트는 DB 연결을 공유하므로 바로 실행 모드를 쓰고, 여기서는 가짜 저장소로 실제 백그라운드 동작을 봅니다.
"""

import asyncio
from datetime import datetime
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID, uuid4

from pydantic import SecretStr

from app.core import settings
from app.core.enums import ChallengeRecommendationStatus, PredictionModelType
from app.core.llm import LLMResponse
from app.repositories.challenge_repository import ChallengeRepository
from app.services.challenge_recommendations import ChallengeRecommendationLauncher
from tests.challenge_apis.helpers import factor, result, valid_response_text


class FakePrediction:
    def __init__(self) -> None:
        self.id = uuid4()
        self.user_id = uuid4()
        self.results = [
            result(PredictionModelType.DIABETES_RISK, [factor("허리둘레", 0.08)]),
            result(PredictionModelType.HYPERTENSION_RISK, [factor("허리둘레", 0.05)]),
        ]
        self.monthly_health_survey = None


class FakeRepository:
    def __init__(self, prediction: FakePrediction) -> None:
        self.prediction = prediction
        self.status: ChallengeRecommendationStatus | None = None
        self.claimed_at: datetime | None = None
        self.saved: list[dict[str, Any]] = []
        self.error_code: str | None = None

    async def claim_recommendation(
        self, prediction_id: UUID, started_at: datetime, stale_before: datetime, retry: bool = False
    ) -> bool:
        if self.status is not None:
            return False
        self.status, self.claimed_at = ChallengeRecommendationStatus.PROCESSING, started_at
        return True

    async def get_prediction_for_recommendation(self, prediction_id: UUID) -> FakePrediction:
        return self.prediction

    async def save_recommendations(
        self,
        prediction_id: UUID,
        claimed_at: datetime,
        challenges: list[dict[str, Any]],
        model_name: str,
        now: datetime,
    ) -> bool:
        assert claimed_at == self.claimed_at
        self.status, self.saved = ChallengeRecommendationStatus.COMPLETED, challenges
        return True

    async def mark_recommendation_failed(
        self, prediction_id: UUID, claimed_at: datetime, error_code: str, now: datetime
    ) -> bool:
        self.status, self.error_code = ChallengeRecommendationStatus.FAILED, error_code
        return True


class SlowLLMClient:
    """release 이벤트가 설정될 때까지 응답을 미룹니다."""

    model_name = "claude-haiku-5-5"

    def __init__(self) -> None:
        self.release = asyncio.Event()

    async def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> LLMResponse:
        await self.release.wait()
        return LLMResponse(text=valid_response_text(), model=self.model_name, stop_reason="end_turn")


async def test_start_returns_before_llm_responds_and_saves_in_background() -> None:
    prediction = FakePrediction()
    repo = FakeRepository(prediction)
    llm = SlowLLMClient()
    launcher = ChallengeRecommendationLauncher(
        repository_factory=lambda: cast(ChallengeRepository, repo), llm_client_factory=lambda: llm
    )

    with patch.object(settings, "ANTHROPIC_API_KEY", SecretStr("test-key")):
        started = await launcher.start(prediction.id)
        assert started is True
        assert repo.status is ChallengeRecommendationStatus.PROCESSING

        llm.release.set()
        await launcher.wait_all()

    assert repo.status is ChallengeRecommendationStatus.COMPLETED
    assert len(repo.saved) == 3
    # 허리둘레는 두 질환 모두의 요인이지만, 근거는 챌린지가 겨냥한 질환 것만 저장합니다.
    assert repo.saved[0]["target_diseases"] == ["diabetes_risk"]
    assert repo.saved[0]["basis"] == [
        {"model_type": "diabetes_risk", "feature": "허리둘레", "display_name": "허리둘레"}
    ]
    assert {item["model_type"] for item in repo.saved[1]["basis"]} == {"diabetes_risk", "hypertension_risk"}


async def test_start_claims_only_once() -> None:
    prediction = FakePrediction()
    repo = FakeRepository(prediction)
    llm = SlowLLMClient()
    launcher = ChallengeRecommendationLauncher(
        repository_factory=lambda: cast(ChallengeRepository, repo), llm_client_factory=lambda: llm
    )

    with patch.object(settings, "ANTHROPIC_API_KEY", SecretStr("test-key")):
        first = await launcher.start(prediction.id)
        second = await launcher.start(prediction.id)
        llm.release.set()
        await launcher.wait_all()

    assert (first, second) == (True, False)


async def test_start_without_api_key_fails_immediately() -> None:
    prediction = FakePrediction()
    repo = FakeRepository(prediction)
    launcher = ChallengeRecommendationLauncher(
        repository_factory=lambda: cast(ChallengeRepository, repo), llm_client_factory=SlowLLMClient
    )

    with patch.object(settings, "ANTHROPIC_API_KEY", SecretStr("")):
        assert await launcher.start(prediction.id) is True

    assert repo.status is ChallengeRecommendationStatus.FAILED
    assert repo.error_code == "LLM_NOT_CONFIGURED"
    assert not launcher._tasks
