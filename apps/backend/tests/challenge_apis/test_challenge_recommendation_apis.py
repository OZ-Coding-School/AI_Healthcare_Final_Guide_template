from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from redis.exceptions import RedisError
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import settings
from app.core.enums import ChallengeRecommendationStatus, ChallengeStatus
from app.core.llm import LLMRequestError
from app.core.utils.prediction_stream import result_stream_key
from app.core.utils.redis import get_redis
from app.models.challenge_models import PersonalChallenge
from app.models.disease_prediction_models import DiseasePrediction
from app.models.user_models import User
from app.services.challenge_recommendations import challenge_recommendation_launcher
from main import app
from tests.challenge_apis.helpers import FakeLLMClient, challenge_item, challenges_json, unavailable
from tests.disease_prediction_apis.helpers import (
    create_survey,
    failed_result_fields,
    profile_data,
    screening_data,
    succeeded_result_fields,
)

PREDICTION_API = "/api/v1/disease-predictions"


class TestChallengeRecommendationAPI(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.signup_data = {
            "email": "challenge_test@example.com",
            "password": "Password123!",
            "nickname": "챌린지테스터",
            "name": "챌린지테스터",
            "phone_number": "01033332222",
        }
        self.llm = FakeLLMClient()
        # 실제 Claude API를 호출하지 않도록 키와 클라이언트를 테스트용으로 바꿉니다.
        self.patches: list[Any] = [
            patch.object(settings, "ANTHROPIC_API_KEY", SecretStr("test-key")),
            patch.object(settings, "LLM_MAX_ATTEMPTS", 2),
            patch.object(challenge_recommendation_launcher, "llm_client_factory", lambda: self.llm),
            # 테스트 DB는 연결 1개를 트랜잭션으로 공유하므로, 요청 처리와 생성 작업이 동시에 쿼리하지 않게 바로 실행합니다.
            # 백그라운드 실행 자체는 test_challenge_launcher.py에서 검증합니다.
            patch.object(challenge_recommendation_launcher, "run_in_background", False),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        super().tearDown()

    @property
    def redis(self) -> fakeredis.FakeAsyncRedis:
        return app.dependency_overrides[get_redis]()

    async def signup(self, client: AsyncClient, email: str | None = None, phone: str | None = None) -> dict[str, str]:
        data = dict(self.signup_data)
        if email:
            data.update(email=email, phone_number=phone or "01011110000")
        with patch("app.services.auth.AuthService.ensure_signup_email_verified", AsyncMock()):
            await client.post("/api/v1/auth/signup", json=data)
        response = await client.post("/api/v1/auth/login", json={"email": data["email"], "password": data["password"]})
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def create_prediction(self, client: AsyncClient, headers: dict[str, str], email: str | None = None) -> str:
        user = await User.get(email=email or self.signup_data["email"])
        await client.post("/api/v1/health-profiles", json=profile_data(), headers=headers)
        await client.post("/api/v1/annual-health-screenings", json=screening_data(), headers=headers)
        await create_survey(user.id)
        response = await client.post(PREDICTION_API, json={}, headers=headers)
        assert response.status_code == status.HTTP_202_ACCEPTED, response.text
        return response.json()["id"]

    async def complete_prediction(self, client: AsyncClient, headers: dict[str, str], prediction_id: str) -> None:
        """Worker 성공 결과를 남기고 상세 조회로 COMPLETED를 반영합니다. 이때 추천이 자동으로 시작됩니다."""
        await self.redis.xadd(result_stream_key(prediction_id), succeeded_result_fields(prediction_id))  # type: ignore[arg-type]
        response = await client.get(f"{PREDICTION_API}/{prediction_id}", headers=headers)
        assert response.json()["status"] == "COMPLETED", response.text

    async def get_recommendation(
        self, client: AsyncClient, headers: dict[str, str], prediction_id: str
    ) -> tuple[int, dict[str, Any]]:
        await challenge_recommendation_launcher.wait_all()
        response = await client.get(f"{PREDICTION_API}/{prediction_id}/challenges", headers=headers)
        return response.status_code, response.json()

    async def completed_prediction(self, client: AsyncClient) -> tuple[dict[str, str], str]:
        headers = await self.signup(client)
        prediction_id = await self.create_prediction(client, headers)
        await self.complete_prediction(client, headers, prediction_id)
        await challenge_recommendation_launcher.wait_all()
        return headers, prediction_id

    # ---------- 자동 생성 ----------

    async def test_recommendation_starts_automatically_when_prediction_completes(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            code, body = await self.get_recommendation(client, headers, prediction_id)

        assert code == status.HTTP_200_OK
        assert body["status"] == "COMPLETED"
        assert body["status_label"] == "추천 완료"
        assert body["error_code"] is None
        assert body["model_name"] == "claude-haiku-5-5"
        assert len(body["challenges"]) == 3
        first = body["challenges"][0]
        assert first["title"] == "매일 30분 빠르게 걷기"
        assert first["challenge_type"] == "DAILY"
        assert first["challenge_type_label"] == "일일 챌린지"
        assert first["total_rounds"] == 21
        assert first["status"] == "PENDING"
        assert first["prediction_id"] == prediction_id
        assert first["target_diseases"] == [{"model_type": "diabetes_risk", "disease_name": "당뇨병"}]
        assert first["basis"] == [{"model_type": "diabetes_risk", "feature": "허리둘레", "display_name": "허리둘레"}]
        assert len(self.llm.calls) == 1

    async def test_prompt_uses_only_actionable_factors(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await self.completed_prediction(client)

        call = self.llm.calls[0]
        factor_section = call["user"].split("[근거로 쓸 수 있는 요인]")[1].split("[현재 생활습관]")[0]
        assert "허리둘레" in factor_section
        assert "나이" not in factor_section
        assert "challenge_test@example.com" not in call["user"]
        assert "챌린지테스터" not in call["user"]

    async def test_challenge_expiry_follows_setting(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            _, prediction_id = await self.completed_prediction(client)

        challenge = await PersonalChallenge.filter(prediction_id=prediction_id).first()
        assert challenge is not None
        expected = timedelta(days=settings.CHALLENGE_ACCEPT_EXPIRE_DAYS)
        assert abs((challenge.expired_at - challenge.created_at) - expected) < timedelta(minutes=1)

    async def test_recommendation_runs_once_for_repeated_reads(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            await client.get(f"{PREDICTION_API}/{prediction_id}", headers=headers)
            await self.get_recommendation(client, headers, prediction_id)
            await self.get_recommendation(client, headers, prediction_id)

        assert len(self.llm.calls) == 1
        assert await PersonalChallenge.filter(prediction_id=prediction_id).count() == 3

    async def test_failed_prediction_does_not_start_recommendation(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            await self.redis.xadd(result_stream_key(prediction_id), failed_result_fields(prediction_id, "MODEL_ERROR"))  # type: ignore[arg-type]
            await client.get(f"{PREDICTION_API}/{prediction_id}", headers=headers)
            code, body = await self.get_recommendation(client, headers, prediction_id)

        assert code == status.HTTP_409_CONFLICT
        assert body["detail"] == "Disease prediction is not completed."
        assert self.llm.calls == []

    async def test_pending_prediction_returns_conflict(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            code, _ = await self.get_recommendation(client, headers, prediction_id)

        assert code == status.HTTP_409_CONFLICT

    # ---------- 실패 처리 ----------

    async def test_missing_api_key_fails_without_calling_llm(self) -> None:
        with patch.object(settings, "ANTHROPIC_API_KEY", SecretStr("")):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                headers, prediction_id = await self.completed_prediction(client)
                code, body = await self.get_recommendation(client, headers, prediction_id)

        assert code == status.HTTP_200_OK
        assert body["status"] == "FAILED"
        assert body["error_code"] == "LLM_NOT_CONFIGURED"
        assert body["challenges"] == []
        assert self.llm.calls == []

    async def test_registering_api_key_recovers_not_configured_recommendation(self) -> None:
        """키 없이 실패한 추천은 키를 등록한 뒤 조회하면 retry 없이 다시 생성됩니다."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch.object(settings, "ANTHROPIC_API_KEY", SecretStr("")):
                headers, prediction_id = await self.completed_prediction(client)
                _, before = await self.get_recommendation(client, headers, prediction_id)
            _, after = await self.get_recommendation(client, headers, prediction_id)

        assert before["status"] == "FAILED"
        assert before["error_code"] == "LLM_NOT_CONFIGURED"
        assert after["status"] == "COMPLETED"
        assert len(after["challenges"]) == 3
        assert len(self.llm.calls) == 1

    async def test_repeated_reads_without_api_key_do_not_restart(self) -> None:
        with patch.object(settings, "ANTHROPIC_API_KEY", SecretStr("")):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                headers, prediction_id = await self.completed_prediction(client)
                first = (await DiseasePrediction.get(id=prediction_id)).challenge_completed_at
                await self.get_recommendation(client, headers, prediction_id)
                _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["error_code"] == "LLM_NOT_CONFIGURED"
        assert (await DiseasePrediction.get(id=prediction_id)).challenge_completed_at == first

    async def test_other_failures_are_not_restarted_by_read(self) -> None:
        self.llm.responses = ["JSON이 아닌 응답"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            self.llm.responses = [challenges_json([challenge_item()])]
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "FAILED"
        assert body["error_code"] == "LLM_INVALID_RESPONSE"
        assert len(self.llm.calls) == settings.LLM_MAX_ATTEMPTS

    async def test_invalid_response_is_retried_with_reasons(self) -> None:
        self.llm.responses = [challenges_json([challenge_item(total_rounds=100)]), challenges_json([challenge_item()])]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "COMPLETED"
        assert len(body["challenges"]) == 1
        assert len(self.llm.calls) == 2
        assert "DAILY의 total_rounds는 7~30이어야 합니다" in self.llm.calls[1]["user"]

    async def test_invalid_response_after_all_attempts_fails(self) -> None:
        self.llm.responses = ["JSON이 아닌 응답"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "FAILED"
        assert body["error_code"] == "LLM_INVALID_RESPONSE"
        assert len(self.llm.calls) == settings.LLM_MAX_ATTEMPTS
        assert await PersonalChallenge.filter(prediction_id=prediction_id).count() == 0

    async def test_unavailable_llm_is_retried(self) -> None:
        self.llm.responses = [unavailable(), challenges_json([challenge_item()])]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "COMPLETED"
        assert len(self.llm.calls) == 2

    async def test_unavailable_llm_after_all_attempts_fails(self) -> None:
        self.llm.responses = [unavailable()]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "FAILED"
        assert body["error_code"] == "LLM_UNAVAILABLE"

    async def test_rejected_request_is_not_retried(self) -> None:
        self.llm.responses = [LLMRequestError(401, "authentication_error")]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["error_code"] == "LLM_REQUEST_FAILED"
        assert len(self.llm.calls) == 1

    # ---------- 재시도 ----------

    async def test_retry_failed_recommendation(self) -> None:
        self.llm.responses = ["JSON이 아닌 응답"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            self.llm.responses = [challenges_json([challenge_item()])]
            self.llm.calls.clear()
            response = await client.post(f"{PREDICTION_API}/{prediction_id}/challenges/retry", headers=headers)
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["error_code"] is None
        assert body["status"] == "COMPLETED"
        assert len(body["challenges"]) == 1
        assert len(self.llm.calls) == 1

    async def test_retry_completed_recommendation_returns_conflict(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            response = await client.post(f"{PREDICTION_API}/{prediction_id}/challenges/retry", headers=headers)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Only failed challenge recommendations can be retried."

    # ---------- 중단된 추천 복구 ----------

    async def test_unstarted_recommendation_starts_on_read(self) -> None:
        """완료 직후 시작하지 못한 경우(서버 재시작 등)에도 조회하면 시작합니다."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            with patch.object(challenge_recommendation_launcher, "start", AsyncMock(return_value=False)):
                await self.redis.xadd(result_stream_key(prediction_id), succeeded_result_fields(prediction_id))  # type: ignore[arg-type]
                await client.get(f"{PREDICTION_API}/{prediction_id}", headers=headers)
            assert (await DiseasePrediction.get(id=prediction_id)).challenge_status is None
            await client.get(f"{PREDICTION_API}/{prediction_id}/challenges", headers=headers)
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "COMPLETED"

    async def test_stale_processing_recommendation_restarts(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            await PersonalChallenge.filter(prediction_id=prediction_id).delete()
            stale = (await DiseasePrediction.get(id=prediction_id)).challenge_started_at
            assert stale is not None
            await DiseasePrediction.filter(id=prediction_id).update(
                challenge_status=ChallengeRecommendationStatus.PROCESSING,
                challenge_started_at=stale - timedelta(seconds=settings.CHALLENGE_RECOMMENDATION_STALE_SECONDS + 1),
            )
            await client.get(f"{PREDICTION_API}/{prediction_id}/challenges", headers=headers)
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "COMPLETED"
        assert len(body["challenges"]) == 3
        assert len(self.llm.calls) == 2

    async def test_recent_processing_recommendation_is_not_restarted(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            await DiseasePrediction.filter(id=prediction_id).update(
                challenge_status=ChallengeRecommendationStatus.PROCESSING
            )
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "PROCESSING"
        assert len(self.llm.calls) == 1

    # ---------- Redis 캐시 ----------

    async def test_completed_recommendation_is_served_from_cache(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            user_id = (await User.get(email=self.signup_data["email"])).id
            _, first = await self.get_recommendation(client, headers, prediction_id)
            key = f"challenge:recommendation:{user_id}:{prediction_id}"
            ttl = await self.redis.ttl(key)
            # 캐시가 쓰이는지 확인하려고 DB만 바꿉니다. 캐시된 응답은 그대로여야 합니다.
            await PersonalChallenge.filter(prediction_id=prediction_id).update(title="DB에서 바뀐 제목")
            _, second = await self.get_recommendation(client, headers, prediction_id)

        base = settings.CHALLENGE_RECOMMENDATION_CACHE_TTL_SECONDS
        assert base - 5 <= ttl <= base * (1 + settings.CACHE_TTL_JITTER_RATIO)
        assert second == first
        assert second["challenges"][0]["title"] == "매일 30분 빠르게 걷기"

    async def test_failed_recommendation_is_not_cached(self) -> None:
        self.llm.responses = ["JSON이 아닌 응답"]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            user_id = (await User.get(email=self.signup_data["email"])).id
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "FAILED"
        assert await self.redis.exists(f"challenge:recommendation:{user_id}:{prediction_id}") == 0

    async def test_processing_recommendation_is_not_cached(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            user_id = (await User.get(email=self.signup_data["email"])).id
            await DiseasePrediction.filter(id=prediction_id).update(
                challenge_status=ChallengeRecommendationStatus.PROCESSING
            )
            _, body = await self.get_recommendation(client, headers, prediction_id)

        assert body["status"] == "PROCESSING"
        assert await self.redis.exists(f"challenge:recommendation:{user_id}:{prediction_id}") == 0

    async def test_challenge_list_cache_is_invalidated_by_new_recommendation(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, _ = await self.completed_prediction(client)
            first = await client.get("/api/v1/challenges", headers=headers)
            cached = await client.get("/api/v1/challenges", headers=headers)

            response = await client.post(PREDICTION_API, json={}, headers=headers)
            second_prediction = response.json()["id"]
            await self.complete_prediction(client, headers, second_prediction)
            refreshed = await client.get("/api/v1/challenges", headers=headers)

        assert len(first.json()) == 3
        assert cached.json() == first.json()
        assert len(refreshed.json()) == 6
        assert {item["prediction_id"] for item in refreshed.json()} >= {second_prediction}

    async def test_redis_failure_falls_back_to_database(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            with (
                patch.object(self.redis, "get", AsyncMock(side_effect=RedisError("down"))),
                patch.object(self.redis, "set", AsyncMock(side_effect=RedisError("down"))),
            ):
                code, body = await self.get_recommendation(client, headers, prediction_id)
                listed = await client.get("/api/v1/challenges", headers=headers)

        assert code == status.HTTP_200_OK
        assert body["status"] == "COMPLETED"
        assert listed.status_code == status.HTTP_200_OK
        assert len(listed.json()) == 3

    # ---------- 권한·목록 ----------

    async def test_other_users_prediction_is_not_found(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            _, prediction_id = await self.completed_prediction(client)
            other_headers = await self.signup(client, email="other_challenge@example.com", phone="01099990000")
            response = await client.get(f"{PREDICTION_API}/{prediction_id}/challenges", headers=other_headers)
            missing = await client.get(f"{PREDICTION_API}/{uuid4()}/challenges", headers=other_headers)
            listed = await client.get("/api/v1/challenges", headers=other_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert missing.status_code == status.HTTP_404_NOT_FOUND
        assert listed.json() == []

    async def test_challenge_list_filters_by_status(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, prediction_id = await self.completed_prediction(client)
            first = await PersonalChallenge.filter(prediction_id=prediction_id).order_by("id").first()
            assert first is not None
            await PersonalChallenge.filter(id=first.id).update(status=ChallengeStatus.IN_PROGRESS)
            all_items = await client.get("/api/v1/challenges", headers=headers)
            pending = await client.get("/api/v1/challenges", params={"status": "PENDING"}, headers=headers)
            invalid = await client.get("/api/v1/challenges", params={"status": "UNKNOWN"}, headers=headers)

        assert all_items.status_code == status.HTTP_200_OK
        assert len(all_items.json()) == 3
        assert len(pending.json()) == 2
        assert all(item["status"] == "PENDING" for item in pending.json())
        assert invalid.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_requires_authentication(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"{PREDICTION_API}/{uuid4()}/challenges")
            listed = await client.get("/api/v1/challenges")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert listed.status_code == status.HTTP_401_UNAUTHORIZED
