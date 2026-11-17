import asyncio
import json
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import fakeredis
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import settings
from app.core.enums import DiseasePredictionStatus, DiseaseRiskLevel, PredictionModelType
from app.core.utils.prediction_stream import PREDICTION_REQUEST_STREAM, RESULT_TTL_SECONDS, result_stream_key
from app.core.utils.redis import get_redis
from app.models.disease_prediction_models import DiseasePrediction, DiseasePredictionResult
from app.models.user_models import User
from main import app
from tests.disease_prediction_apis.helpers import (
    create_survey,
    failed_result_fields,
    processing_result_fields,
    profile_data,
    screening_data,
    succeeded_result_fields,
)

API_PATH = "/api/v1/disease-predictions"


def parse_sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    """SSE 본문에서 (이벤트 이름, data JSON) 목록을 꺼냅니다. heartbeat 주석은 건너뜁니다."""
    events = []
    for block in text.strip().split("\n\n"):
        lines = [line for line in block.split("\n") if line and not line.startswith(":")]
        if not lines:
            continue
        fields = dict(line.split(": ", 1) for line in lines)
        events.append((fields["event"], json.loads(fields["data"])))
    return events


class TestDiseasePredictionAPI(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.signup_data = {
            "email": "dp_test@example.com",
            "password": "Password123!",
            "nickname": "DP테스터",
            "name": "DP테스터",
            "phone_number": "01077776666",
        }

    @property
    def redis(self) -> fakeredis.FakeAsyncRedis:
        return app.dependency_overrides[get_redis]()

    async def signup(self, client: AsyncClient, email: str | None = None, phone: str | None = None) -> dict[str, str]:
        data = dict(self.signup_data)
        if email:
            data.update(email=email, phone_number=phone or "01055554444")
        with patch("app.services.auth.AuthService.ensure_signup_email_verified", AsyncMock()):
            await client.post("/api/v1/auth/signup", json=data)
        response = await client.post("/api/v1/auth/login", json={"email": data["email"], "password": data["password"]})
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def user_id(self, email: str = "dp_test@example.com") -> UUID:
        return (await User.get(email=email)).id

    async def prepare_records(self, client: AsyncClient, headers: dict[str, str], **screening: Any) -> None:
        await client.post("/api/v1/health-profiles", json=profile_data(), headers=headers)
        await client.post("/api/v1/annual-health-screenings", json=screening_data(**screening), headers=headers)
        await create_survey(await self.user_id())

    async def create_prediction(self, client: AsyncClient, headers: dict[str, str]) -> str:
        await self.prepare_records(client, headers)
        response = await client.post(API_PATH, json={}, headers=headers)
        assert response.status_code == status.HTTP_202_ACCEPTED, response.text
        return response.json()["id"]

    async def publish_result(self, prediction_id: str, fields: dict[str, str]) -> None:
        """AI Worker가 결과 Stream에 항목을 남기는 동작을 흉내 냅니다 (Worker와 같이 마지막 1건만 보관)."""
        await self.redis.xadd(result_stream_key(prediction_id), fields, maxlen=1, approximate=False)  # type: ignore[arg-type]

    async def read_events(self, client: AsyncClient, prediction_id: str, headers: dict[str, str]) -> tuple[Any, str]:
        async with client.stream("GET", f"{API_PATH}/{prediction_id}/events", headers=headers) as response:
            body = "".join([chunk async for chunk in response.aiter_text()])
        return response, body

    # ---------- 요청 발행 ----------

    async def test_create_prediction_publishes_request(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)

        prediction = await DiseasePrediction.get(id=prediction_id)
        assert prediction.status is DiseasePredictionStatus.PENDING
        assert prediction.annual_health_screening_id is not None  # type: ignore[attr-defined]
        assert prediction.monthly_health_survey_id is not None  # type: ignore[attr-defined]

        entries = await self.redis.xrange(PREDICTION_REQUEST_STREAM)
        assert len(entries) == 1
        fields = entries[0][1]
        assert fields["task_id"] == prediction_id
        assert fields["schema_version"] == "2"
        assert json.loads(fields["payload"]) == prediction.feature
        assert prediction.feature["diabetes_family_history"] == {
            "father": "YES",
            "mother": "NO",
            "siblings": "NO_SIBLINGS",
        }

    async def test_create_prediction_response(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            await self.prepare_records(client, headers)
            response = await client.post(API_PATH, json={}, headers=headers)

        body = response.json()
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert body["status"] == "PENDING"
        assert body["events_url"] == f"{API_PATH}/{body['id']}/events"

    async def test_create_prediction_requires_profile(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            response = await client.post(API_PATH, json={}, headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Health Profile Not Found."

    async def test_create_prediction_requires_screening(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            await client.post("/api/v1/health-profiles", json=profile_data(), headers=headers)
            response = await client.post(API_PATH, json={}, headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Annual Health Screening Not Found."

    async def test_create_prediction_requires_survey(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            await client.post("/api/v1/health-profiles", json=profile_data(), headers=headers)
            await client.post("/api/v1/annual-health-screenings", json=screening_data(), headers=headers)
            response = await client.post(API_PATH, json={}, headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Monthly Health Survey Not Found."

    async def test_create_prediction_rejects_other_users_screening(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            other_headers = await self.signup(client, email="other@example.com", phone="01022223333")
            await client.post("/api/v1/annual-health-screenings", json=screening_data(), headers=other_headers)
            other_screening_id = (await client.get("/api/v1/annual-health-screenings", headers=other_headers)).json()[
                0
            ]["id"]

            headers = await self.signup(client)
            await self.prepare_records(client, headers)
            response = await client.post(
                API_PATH, json={"annual_health_screening_id": other_screening_id}, headers=headers
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_create_prediction_validates_input_before_publishing(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            await self.prepare_records(client, headers, sbp=300)
            response = await client.post(API_PATH, json={}, headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        locations = [tuple(error["loc"]) for error in response.json()["detail"]]
        assert ("annual_health_screening", "sbp") in locations
        assert await DiseasePrediction.all().count() == 0
        assert await self.redis.exists(PREDICTION_REQUEST_STREAM) == 0

    async def test_create_prediction_rejects_in_progress_request(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            await self.create_prediction(client, headers)
            response = await client.post(API_PATH, json={}, headers=headers)

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_create_prediction_marks_failed_when_publish_fails(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            await self.prepare_records(client, headers)
            with patch.object(self.redis, "xadd", AsyncMock(side_effect=RedisError("down"))):
                response = await client.post(API_PATH, json={}, headers=headers)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        prediction = await DiseasePrediction.get()
        assert prediction.status is DiseasePredictionStatus.FAILED
        assert prediction.error_code == "PUBLISH_FAILED"

    async def test_create_prediction_unauthorized(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(API_PATH, json={})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ---------- SSE ----------

    async def test_events_send_result_that_arrived_before_connecting(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            await self.publish_result(prediction_id, succeeded_result_fields(prediction_id))
            response, body = await self.read_events(client, prediction_id, headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        events = parse_sse(body)
        # 연결 시 현재 상태(PENDING)를 먼저 보내고, 이미 와 있던 결과를 이어서 보냅니다.
        assert [name for name, _ in events] == ["status", "result"]
        assert events[0][1] == {"id": prediction_id, "status": "PENDING", "status_label": "대기 중"}
        data = events[1][1]
        assert data["status"] == "COMPLETED"
        assert [result["model_type"] for result in data["results"]] == ["diabetes_risk", "hypertension_risk"]
        diabetes = data["results"][0]
        assert diabetes["risk_score"] == 23.46
        assert diabetes["risk_level"] == "MODERATE"
        assert diabetes["risk_thresholds"] == {"moderate": 0.12346, "high": 0.45679}
        assert diabetes["risk_factors"][1]["actionable"] is False

        results = await DiseasePredictionResult.filter(prediction_id=prediction_id).order_by("model_type")
        assert [result.model_type for result in results] == list(PredictionModelType)
        assert results[1].risk_level is DiseaseRiskLevel.HIGH

    async def test_events_send_processing_then_result(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)

            async def worker() -> None:
                await asyncio.sleep(0.3)
                await self.publish_result(prediction_id, processing_result_fields(prediction_id))
                await asyncio.sleep(0.3)
                # 최종 결과가 처리 시작 항목을 대체합니다 (MAXLEN 1).
                await self.publish_result(prediction_id, succeeded_result_fields(prediction_id))

            task = asyncio.create_task(worker())
            _response, body = await self.read_events(client, prediction_id, headers)
            await task

        events = parse_sse(body)
        assert [(name, data.get("status")) for name, data in events] == [
            ("status", "PENDING"),
            ("status", "PROCESSING"),
            ("result", "COMPLETED"),
        ]
        prediction = await DiseasePrediction.get(id=prediction_id)
        assert prediction.started_at is not None
        assert prediction.completed_at is not None

    async def test_events_on_reconnect_while_processing(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            await self.publish_result(prediction_id, processing_result_fields(prediction_id))
            await client.get(f"{API_PATH}/{prediction_id}", headers=headers)  # DB를 PROCESSING으로 반영

            async def worker() -> None:
                await asyncio.sleep(0.3)
                await self.publish_result(prediction_id, succeeded_result_fields(prediction_id))

            task = asyncio.create_task(worker())
            _response, body = await self.read_events(client, prediction_id, headers)
            await task

        # 이미 PROCESSING이므로 같은 상태를 두 번 보내지 않습니다.
        assert [(name, data.get("status")) for name, data in parse_sse(body)] == [
            ("status", "PROCESSING"),
            ("result", "COMPLETED"),
        ]

    async def test_events_send_failed_with_input_errors(self) -> None:
        errors = [{"field": "sbp", "reason": "must be between 60 and 260"}]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            await self.publish_result(prediction_id, failed_result_fields(prediction_id, "INVALID_INPUT", errors))
            _response, body = await self.read_events(client, prediction_id, headers)

        name, data = parse_sse(body)[-1]
        assert name == "failed"
        assert data["status"] == "FAILED"
        assert data["error_code"] == "INVALID_INPUT"
        assert data["errors"] == errors

    async def test_events_hide_internal_error_details(self) -> None:
        errors = [{"field": "diabetes_risk", "reason": "internal detail"}]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            await self.publish_result(prediction_id, failed_result_fields(prediction_id, "MODEL_ERROR", errors))
            _response, body = await self.read_events(client, prediction_id, headers)

        _name, data = parse_sse(body)[-1]
        assert data["error_code"] == "MODEL_ERROR"
        assert data["errors"] == []

    async def test_events_timeout_keeps_prediction_pending(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            with (
                patch.object(settings, "PREDICTION_SSE_TIMEOUT_SECONDS", 2),
                patch.object(settings, "PREDICTION_SSE_HEARTBEAT_SECONDS", 1),
            ):
                _response, body = await self.read_events(client, prediction_id, headers)

        assert ": heartbeat" in body
        events = parse_sse(body)
        pending = {"id": prediction_id, "status": "PENDING", "status_label": "대기 중"}
        assert events == [("status", pending), ("timeout", pending)]
        assert (await DiseasePrediction.get(id=prediction_id)).status is DiseasePredictionStatus.PENDING

    async def test_events_for_completed_prediction_return_immediately(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            await self.publish_result(prediction_id, succeeded_result_fields(prediction_id))
            await self.read_events(client, prediction_id, headers)
            # 결과 Stream이 만료된 뒤에도 DB의 결과를 보냅니다.
            await self.redis.delete(result_stream_key(prediction_id))
            _response, body = await self.read_events(client, prediction_id, headers)

        assert [name for name, _ in parse_sse(body)] == ["result"]
        assert await DiseasePredictionResult.filter(prediction_id=prediction_id).count() == 2

    async def test_events_reject_other_users_prediction(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            other_headers = await self.signup(client, email="other@example.com", phone="01022223333")
            response = await client.get(f"{API_PATH}/{prediction_id}/events", headers=other_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_events_report_invalid_worker_result_as_failed(self) -> None:
        fields = succeeded_result_fields(uuid4())  # 다른 task_id의 결과
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            await self.publish_result(prediction_id, fields)
            _response, body = await self.read_events(client, prediction_id, headers)

        name, data = parse_sse(body)[-1]
        assert name == "failed"
        assert data["error_code"] == "INVALID_RESULT"
        assert await DiseasePredictionResult.filter(prediction_id=prediction_id).count() == 0

    async def test_events_report_redis_error(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            with patch.object(self.redis, "xread", AsyncMock(side_effect=RedisError("down"))):
                _response, body = await self.read_events(client, prediction_id, headers)

        assert parse_sse(body)[-1] == ("error", {"id": prediction_id, "code": "SERVICE_UNAVAILABLE"})

    # ---------- 상세·목록 ----------

    async def test_get_prediction_finalizes_result_without_sse(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)

            pending = await client.get(f"{API_PATH}/{prediction_id}", headers=headers)
            await self.publish_result(prediction_id, succeeded_result_fields(prediction_id))
            first = await client.get(f"{API_PATH}/{prediction_id}", headers=headers)
            second = await client.get(f"{API_PATH}/{prediction_id}", headers=headers)

        assert pending.json()["status"] == "PENDING"
        assert pending.json()["results"] == []
        assert first.json()["status"] == "COMPLETED"
        assert first.json() == second.json()
        # 여러 번 확정을 시도해도 결과는 한 번만 저장됩니다.
        assert await DiseasePredictionResult.filter(prediction_id=prediction_id).count() == 2

    async def test_get_prediction_reflects_processing(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            await self.publish_result(prediction_id, processing_result_fields(prediction_id))

            processing = await client.get(f"{API_PATH}/{prediction_id}", headers=headers)
            retry = await client.post(API_PATH, json={}, headers=headers)

        body = processing.json()
        assert body["status"] == "PROCESSING"
        assert body["status_label"] == "분석 중"
        assert body["started_at"] is not None
        assert body["completed_at"] is None
        assert body["results"] == []
        # 처리 중인 요청도 진행 중이므로 중복 요청을 막습니다.
        assert retry.status_code == status.HTTP_409_CONFLICT

    async def test_get_prediction_expires_old_pending(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            prediction_id = await self.create_prediction(client, headers)
            prediction = await DiseasePrediction.get(id=prediction_id)
            old = prediction.created_at - timedelta(seconds=RESULT_TTL_SECONDS + 60)
            await DiseasePrediction.filter(id=prediction_id).update(created_at=old)

            response = await client.get(f"{API_PATH}/{prediction_id}", headers=headers)
            # 만료된 요청은 진행 중으로 보지 않으므로 새 요청을 받을 수 있습니다.
            retry = await client.post(API_PATH, json={}, headers=headers)

        assert response.json()["status"] == "FAILED"
        assert response.json()["error_code"] == "RESULT_EXPIRED"
        assert retry.status_code == status.HTTP_202_ACCEPTED

    async def test_get_prediction_not_found(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            response = await client.get(f"{API_PATH}/{uuid4()}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Disease Prediction Not Found."

    async def test_get_prediction_list(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await self.signup(client)
            first_id = await self.create_prediction(client, headers)
            await self.publish_result(first_id, succeeded_result_fields(first_id))
            await client.get(f"{API_PATH}/{first_id}", headers=headers)
            second = await client.post(API_PATH, json={}, headers=headers)

            other_headers = await self.signup(client, email="other@example.com", phone="01022223333")
            other_list = await client.get(API_PATH, headers=other_headers)
            response = await client.get(API_PATH, headers=headers)

        body = response.json()
        assert [item["id"] for item in body] == [second.json()["id"], first_id]
        assert body[0]["results"] == []
        assert [result["risk_level"] for result in body[1]["results"]] == ["MODERATE", "HIGH"]
        assert other_list.json() == []
