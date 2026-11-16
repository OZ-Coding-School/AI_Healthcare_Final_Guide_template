"""
질병 위험도 예측 결과를 바탕으로 LLM(Claude)이 생활습관 챌린지를 추천합니다.

흐름
    1. 예측이 COMPLETED로 확정되면 DiseasePredictionService가 launcher.start()를 호출합니다.
    2. start()는 추천 상태를 PROCESSING으로 선점하고, LLM 호출은 백그라운드 작업으로 넘깁니다.
       (SSE 결과 전송이 LLM 응답을 기다리지 않도록 합니다.)
    3. 백그라운드 작업: 프롬프트 생성 → LLM 호출 → 응답 검증 → PersonalChallenge(PENDING) 저장 → COMPLETED
       실패하면 FAILED와 오류 코드를 남깁니다. 기본 챌린지로 대체하지 않습니다.
    4. Frontend는 GET /disease-predictions/{id}/challenges로 상태와 추천을 조회하고, 실패하면 retry API를 호출합니다.

서버 재시작 등으로 PROCESSING에 멈춘 추천, 완료 직후 시작하지 못한 추천은 조회할 때 다시 시작합니다.
건강 정보 보호를 위해 프롬프트·응답 본문은 로그에 남기지 않습니다.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException
from starlette import status

from app.core import logger, settings
from app.core.enums import ChallengeRecommendationStatus, ChallengeStatus, DiseasePredictionStatus
from app.core.llm import LLMClient, LLMNotConfiguredError, LLMRequestError, LLMUnavailableError, get_llm_client
from app.models.challenge_models import PersonalChallenge
from app.models.disease_prediction_models import DiseasePrediction
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.disease_prediction_repository import DiseasePredictionRepository
from app.services.challenge_parser import ChallengeParseError, ParsedChallenge, parse_challenges
from app.services.challenge_prompt import ChallengePrompt, build_challenge_prompt, build_retry_message

# LLM이 응답을 끝까지 쓰지 못했거나 거절한 경우의 stop_reason입니다.
INCOMPLETE_STOP_REASONS = {"max_tokens", "refusal"}


class ChallengeRecommendationErrorCode(StrEnum):
    LLM_NOT_CONFIGURED = "LLM_NOT_CONFIGURED"  # API 키 미설정
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"  # 네트워크·요청 한도·서버 오류 (재시도 가능)
    LLM_REQUEST_FAILED = "LLM_REQUEST_FAILED"  # 잘못된 키·모델 등 설정 오류
    LLM_INVALID_RESPONSE = "LLM_INVALID_RESPONSE"  # 응답이 형식·규칙 검증을 통과하지 못함
    NO_PREDICTION_RESULT = "NO_PREDICTION_RESULT"  # 질환별 결과가 없음
    INTERNAL_ERROR = "INTERNAL_ERROR"


def _now() -> datetime:
    return datetime.now(settings.TIMEZONE)


class ChallengeRecommendationGenerator:
    """선점한 추천 1건을 끝까지 처리합니다. 예외를 밖으로 내보내지 않고 상태로 남깁니다."""

    def __init__(
        self,
        repository: ChallengeRepository,
        llm_client: LLMClient,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self.repo = repository
        self.llm = llm_client
        self.clock = clock

    async def run(self, prediction_id: UUID, claimed_at: datetime) -> None:
        try:
            await self._run(prediction_id, claimed_at)
        except LLMNotConfiguredError:
            await self._fail(prediction_id, claimed_at, ChallengeRecommendationErrorCode.LLM_NOT_CONFIGURED)
        except LLMRequestError as error:
            logger.error("Challenge recommendation %s rejected by LLM: %s", prediction_id, error.status_code)
            await self._fail(prediction_id, claimed_at, ChallengeRecommendationErrorCode.LLM_REQUEST_FAILED)
        except LLMUnavailableError:
            await self._fail(prediction_id, claimed_at, ChallengeRecommendationErrorCode.LLM_UNAVAILABLE)
        except ChallengeParseError:
            await self._fail(prediction_id, claimed_at, ChallengeRecommendationErrorCode.LLM_INVALID_RESPONSE)
        except Exception:
            logger.exception("Unexpected error in challenge recommendation %s", prediction_id)
            await self._fail(prediction_id, claimed_at, ChallengeRecommendationErrorCode.INTERNAL_ERROR)

    async def _run(self, prediction_id: UUID, claimed_at: datetime) -> None:
        prediction = await self.repo.get_prediction_for_recommendation(prediction_id)
        if prediction is None or not prediction.results:
            await self._fail(prediction_id, claimed_at, ChallengeRecommendationErrorCode.NO_PREDICTION_RESULT)
            return

        prompt = build_challenge_prompt(
            list(prediction.results), prediction.monthly_health_survey, settings.CHALLENGE_RECOMMENDATION_COUNT
        )
        challenges, model_name = await self._request(prediction_id, prompt)
        now = self.clock()
        expired_at = now + timedelta(days=settings.CHALLENGE_ACCEPT_EXPIRE_DAYS)
        records = [_challenge_record(prediction, prompt, challenge, expired_at) for challenge in challenges]
        if await self.repo.save_recommendations(prediction_id, claimed_at, records, model_name, now):
            logger.info("Challenge recommendation %s saved %d challenges", prediction_id, len(records))
        else:
            logger.warning("Challenge recommendation %s was taken over by another run", prediction_id)

    async def _request(self, prediction_id: UUID, prompt: ChallengePrompt) -> tuple[list[ParsedChallenge], str]:
        """LLM을 호출하고 검증합니다. 일시적 장애나 형식 오류는 LLM_MAX_ATTEMPTS까지 다시 시도합니다."""
        user_message = prompt.user
        attempts = max(1, settings.LLM_MAX_ATTEMPTS)
        for attempt in range(1, attempts + 1):
            last_attempt = attempt == attempts
            try:
                response = await self.llm.generate_json(prompt.system, user_message, prompt.schema)
            except LLMUnavailableError:
                logger.warning("Challenge recommendation %s: LLM unavailable (attempt %d)", prediction_id, attempt)
                if last_attempt:
                    raise
                continue
            try:
                if response.stop_reason in INCOMPLETE_STOP_REASONS:
                    raise ChallengeParseError([f"응답이 완성되지 않았습니다(stop_reason={response.stop_reason})"])
                challenges = parse_challenges(
                    response.text,
                    allowed_features=prompt.allowed_features,
                    allowed_diseases={str(disease) for disease in prompt.target_diseases},
                    max_count=prompt.count,
                )
            except ChallengeParseError as error:
                logger.warning(
                    "Challenge recommendation %s: invalid LLM response (attempt %d, %d issues)",
                    prediction_id,
                    attempt,
                    len(error.reasons),
                )
                if last_attempt:
                    raise
                user_message = build_retry_message(prompt, error.reasons)
                continue
            return challenges, response.model
        raise AssertionError("unreachable")

    async def _fail(self, prediction_id: UUID, claimed_at: datetime, code: ChallengeRecommendationErrorCode) -> None:
        if await self.repo.mark_recommendation_failed(prediction_id, claimed_at, code, self.clock()):
            logger.warning("Challenge recommendation %s failed: %s", prediction_id, code)


class ChallengeRecommendationLauncher:
    """
    추천을 선점하고 백그라운드 작업으로 실행합니다. 앱 전체에서 하나(challenge_recommendation_launcher)를 씁니다.
    실행 중인 작업은 참조를 보관해 가비지 컬렉션으로 사라지지 않게 합니다.
    """

    def __init__(
        self,
        repository_factory: Callable[[], ChallengeRepository] = ChallengeRepository,
        llm_client_factory: Callable[[], LLMClient] = get_llm_client,
        clock: Callable[[], datetime] = _now,
        run_in_background: bool = True,
    ) -> None:
        self.repository_factory = repository_factory
        self.llm_client_factory = llm_client_factory
        self.clock = clock
        # False이면 start()가 생성을 끝까지 기다립니다. DB 연결 1개를 공유하는 API 테스트에서만 씁니다.
        self.run_in_background = run_in_background
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self, prediction_id: UUID, retry: bool = False) -> bool:
        """추천을 선점했으면 백그라운드 작업을 시작하고 True를 반환합니다."""
        repo = self.repository_factory()
        now = self.clock()
        stale_before = now - timedelta(seconds=settings.CHALLENGE_RECOMMENDATION_STALE_SECONDS)
        if not await repo.claim_recommendation(prediction_id, now, stale_before, retry=retry):
            return False

        if not settings.ANTHROPIC_API_KEY.get_secret_value():
            # 키가 없으면 호출할 수 없으므로 작업을 만들지 않고 바로 실패로 남깁니다.
            await repo.mark_recommendation_failed(
                prediction_id, now, ChallengeRecommendationErrorCode.LLM_NOT_CONFIGURED, now
            )
            logger.warning("Challenge recommendation %s skipped: ANTHROPIC_API_KEY is not set", prediction_id)
            return True

        generator = ChallengeRecommendationGenerator(repo, self.llm_client_factory(), self.clock)
        if not self.run_in_background:
            await generator.run(prediction_id, now)
            return True
        task = asyncio.create_task(generator.run(prediction_id, now), name=f"challenge-recommendation-{prediction_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        logger.info("Challenge recommendation %s started", prediction_id)
        return True

    async def wait_all(self) -> None:
        """실행 중인 작업이 모두 끝날 때까지 기다립니다 (테스트·종료 처리용)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


challenge_recommendation_launcher = ChallengeRecommendationLauncher()


async def start_challenge_recommendation(prediction_id: UUID) -> None:
    """예측이 COMPLETED로 확정된 직후 호출합니다. 실패해도 예측 결과 처리에는 영향을 주지 않습니다."""
    try:
        await challenge_recommendation_launcher.start(prediction_id)
    except Exception:
        logger.exception("Failed to start challenge recommendation %s", prediction_id)


class ChallengeRecommendationService:
    def __init__(
        self,
        repository: ChallengeRepository,
        prediction_repo: DiseasePredictionRepository,
        launcher: ChallengeRecommendationLauncher,
    ) -> None:
        self.repo = repository
        self.prediction_repo = prediction_repo
        self.launcher = launcher

    async def get_recommendation(
        self, user_id: UUID, prediction_id: UUID
    ) -> tuple[DiseasePrediction, list[PersonalChallenge]]:
        prediction = await self._get_completed_prediction(user_id, prediction_id)
        # 시작하지 못했거나 중단된 추천이면 다시 시작합니다. 진행 중·완료·실패 상태면 아무것도 하지 않습니다.
        if await self.launcher.start(prediction.id):
            prediction = await self._get_completed_prediction(user_id, prediction_id)
        challenges = await self.repo.get_list_by_prediction(prediction.id)
        return prediction, challenges

    async def retry(self, user_id: UUID, prediction_id: UUID) -> tuple[DiseasePrediction, list[PersonalChallenge]]:
        prediction = await self._get_completed_prediction(user_id, prediction_id)
        if prediction.challenge_status is not ChallengeRecommendationStatus.FAILED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Only failed challenge recommendations can be retried."
            )
        if not await self.launcher.start(prediction.id, retry=True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Challenge recommendation is already in progress."
            )
        prediction = await self._get_completed_prediction(user_id, prediction_id)
        return prediction, await self.repo.get_list_by_prediction(prediction.id)

    async def get_challenge_list(
        self, user_id: UUID, challenge_status: ChallengeStatus | None
    ) -> list[PersonalChallenge]:
        return await self.repo.get_list_by_user(user_id, challenge_status)

    async def _get_completed_prediction(self, user_id: UUID, prediction_id: UUID) -> DiseasePrediction:
        prediction = await self.prediction_repo.get_by_id(user_id, prediction_id)
        if prediction is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disease Prediction Not Found.")
        if prediction.status is not DiseasePredictionStatus.COMPLETED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Disease prediction is not completed.")
        return prediction


def _challenge_record(
    prediction: DiseasePrediction, prompt: ChallengePrompt, challenge: ParsedChallenge, expired_at: datetime
) -> dict[str, Any]:
    return {
        "user_id": prediction.user_id,  # type: ignore[attr-defined]
        "prediction_id": prediction.id,
        "title": challenge.title,
        "description": challenge.description,
        "challenge_type": challenge.challenge_type,
        "expected_effect": challenge.expected_effect,
        "total_rounds": challenge.total_rounds,
        "target_diseases": challenge.target_diseases,
        "basis": prompt.basis_for(challenge.basis_features, challenge.target_diseases),
        "status": ChallengeStatus.PENDING,
        "expired_at": expired_at,
    }


def get_challenge_recommendation_service(
    repository: ChallengeRepository = Depends(ChallengeRepository),
    prediction_repo: DiseasePredictionRepository = Depends(DiseasePredictionRepository),
) -> ChallengeRecommendationService:
    return ChallengeRecommendationService(
        repository=repository, prediction_repo=prediction_repo, launcher=challenge_recommendation_launcher
    )
