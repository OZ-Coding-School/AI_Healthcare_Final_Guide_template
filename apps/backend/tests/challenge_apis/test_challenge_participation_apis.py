from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core import settings
from app.core.enums import ChallengeRecommendationStatus, ChallengeStatus, ChallengeType, DiseasePredictionStatus
from app.models.challenge_models import PersonalChallenge, PersonalChallengeHistory
from app.models.disease_prediction_models import DiseasePrediction
from app.models.user_models import User
from main import app

CHALLENGE_API = "/api/v1/challenges"


def now() -> datetime:
    return datetime.now(settings.TIMEZONE)


class TestChallengeParticipationAPI(TestCase):
    signup_data = {
        "email": "participation_test@example.com",
        "password": "Password123!",
        "nickname": "참여테스터",
        "name": "참여테스터",
        "phone_number": "01055554444",
    }

    async def signup(
        self, client: AsyncClient, email: str | None = None, phone: str | None = None
    ) -> tuple[dict[str, str], User]:
        data = dict(self.signup_data)
        if email:
            data.update(email=email, phone_number=phone or "01011110000")
        with patch("app.services.auth.AuthService.ensure_signup_email_verified", AsyncMock()):
            await client.post("/api/v1/auth/signup", json=data)
        response = await client.post("/api/v1/auth/login", json={"email": data["email"], "password": data["password"]})
        user = await User.get(email=data["email"])
        return {"Authorization": f"Bearer {response.json()['access_token']}"}, user

    async def create_challenge(self, user: User, **overrides: Any) -> PersonalChallenge:
        data: dict[str, Any] = {
            "user": user,
            "title": "매일 30분 빠르게 걷기",
            "description": "하루 30분 빠르게 걷습니다.",
            "challenge_type": ChallengeType.DAILY,
            "expected_effect": "체중 관리에 도움이 될 수 있습니다.",
            "total_rounds": 14,
            "target_diseases": ["diabetes_risk"],
            "basis": [{"model_type": "diabetes_risk", "feature": "허리둘레", "display_name": "허리둘레"}],
            "status": ChallengeStatus.PENDING,
            "expired_at": now() + timedelta(days=7),
        }
        data.update(overrides)
        return await PersonalChallenge.create(**data)

    async def start_challenge(self, user: User, days_ago: int, **overrides: Any) -> PersonalChallenge:
        """days_ago일 전에 수락한 진행 중 챌린지를 만듭니다."""
        return await self.create_challenge(
            user, status=ChallengeStatus.IN_PROGRESS, joined_at=now() - timedelta(days=days_ago), **overrides
        )

    async def add_history(
        self, challenge: PersonalChallenge, current_round: int, is_success: bool = True, days_ago: int = 0
    ) -> None:
        history = await PersonalChallengeHistory.create(
            challenge=challenge, current_round=current_round, is_success=is_success
        )
        await PersonalChallengeHistory.filter(id=history.id).update(created_at=now() - timedelta(days=days_ago))

    # ---------- 수락 ----------

    async def test_accept_pending_challenge(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.create_challenge(user)
            response = await client.post(f"{CHALLENGE_API}/{challenge.id}/accept", headers=headers)

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["status"] == "IN_PROGRESS"
        assert body["status_label"] == "진행중"
        assert body["joined_at"] is not None
        assert body["histories"] == []
        assert body["progress"]["total_rounds"] == 14
        assert body["progress"]["required_success"] == 12
        assert body["progress"]["current_round"] == 1
        assert body["progress"]["can_record"] is True
        saved = await PersonalChallenge.get(id=challenge.id)
        assert saved.status is ChallengeStatus.IN_PROGRESS
        assert saved.joined_at is not None

    async def test_accept_twice_returns_conflict(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.create_challenge(user)
            await client.post(f"{CHALLENGE_API}/{challenge.id}/accept", headers=headers)
            response = await client.post(f"{CHALLENGE_API}/{challenge.id}/accept", headers=headers)

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_expired_challenge_cannot_be_accepted(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.create_challenge(user, expired_at=now() - timedelta(minutes=1))
            response = await client.post(f"{CHALLENGE_API}/{challenge.id}/accept", headers=headers)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert (await PersonalChallenge.get(id=challenge.id)).status is ChallengeStatus.PENDING

    async def test_challenge_without_target_rounds_cannot_be_accepted(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.create_challenge(user, total_rounds=None)
            response = await client.post(f"{CHALLENGE_API}/{challenge.id}/accept", headers=headers)

        assert response.status_code == status.HTTP_409_CONFLICT

    # ---------- 회차 기록 ----------

    async def test_record_current_round(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(user, days_ago=2)
            response = await client.post(
                f"{CHALLENGE_API}/{challenge.id}/histories",
                json={"is_success": True, "memo": "  저녁 식후에 걸었어요  "},
                headers=headers,
            )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        body = response.json()
        assert body["status"] == "IN_PROGRESS"
        assert len(body["histories"]) == 1
        assert body["histories"][0]["current_round"] == 3
        assert body["histories"][0]["is_success"] is True
        assert body["histories"][0]["memo"] == "저녁 식후에 걸었어요"
        assert body["progress"]["success_count"] == 1
        assert body["progress"]["can_record"] is False
        assert body["progress"]["current_round"] is None

    async def test_same_round_cannot_be_recorded_twice(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(user, days_ago=0)
            url = f"{CHALLENGE_API}/{challenge.id}/histories"
            first = await client.post(url, json={"is_success": False}, headers=headers)
            second = await client.post(url, json={"is_success": True}, headers=headers)

        assert first.status_code == status.HTTP_201_CREATED
        assert first.json()["histories"][0]["memo"] is None
        assert second.status_code == status.HTTP_409_CONFLICT
        assert await PersonalChallengeHistory.filter(challenge_id=challenge.id).count() == 1

    async def test_pending_challenge_cannot_be_recorded(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.create_challenge(user)
            response = await client.post(
                f"{CHALLENGE_API}/{challenge.id}/histories", json={"is_success": True}, headers=headers
            )

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_memo_length_is_validated(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(user, days_ago=0)
            response = await client.post(
                f"{CHALLENGE_API}/{challenge.id}/histories",
                json={"is_success": True, "memo": "가" * 301},
                headers=headers,
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # ---------- 판정 ----------

    async def test_periodic_challenge_completes_at_success_rate(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            # 5일 챌린지 마지막 날, 1~3회차 성공·4회차 미기록 → 오늘 성공하면 5회 중 4회(80%)
            challenge = await self.start_challenge(user, days_ago=4, total_rounds=5)
            for current_round in (1, 2, 3):
                await self.add_history(challenge, current_round, days_ago=5 - current_round)
            response = await client.post(
                f"{CHALLENGE_API}/{challenge.id}/histories", json={"is_success": True}, headers=headers
            )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        body = response.json()
        assert body["status"] == "COMPLETED"
        assert body["completed_at"] is not None
        assert body["progress"]["success_count"] == 4
        assert body["progress"]["can_record"] is False

    async def test_periodic_challenge_fails_when_period_ended(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(user, days_ago=5, total_rounds=3)
            await self.add_history(challenge, 1, days_ago=5)
            listed = await client.get(CHALLENGE_API, headers=headers)
            in_progress = await client.get(CHALLENGE_API, params={"status": "IN_PROGRESS"}, headers=headers)
            record = await client.post(
                f"{CHALLENGE_API}/{challenge.id}/histories", json={"is_success": True}, headers=headers
            )

        assert listed.json()[0]["status"] == "FAILED"
        assert listed.json()[0]["progress"]["success_count"] == 1
        assert in_progress.json() == []
        assert record.status_code == status.HTTP_409_CONFLICT
        saved = await PersonalChallenge.get(id=challenge.id)
        assert saved.status is ChallengeStatus.FAILED
        assert saved.completed_at is not None

    async def test_periodic_challenge_fails_early_when_rate_unreachable(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(user, days_ago=2, total_rounds=5)
            response = await client.get(f"{CHALLENGE_API}/{challenge.id}", headers=headers)

        assert response.json()["status"] == "FAILED"

    async def test_count_based_challenge_completes_when_target_reached(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(
                user, days_ago=5, challenge_type=ChallengeType.COUNT_BASED, total_rounds=3
            )
            await self.add_history(challenge, 1, days_ago=4)
            await self.add_history(challenge, 2, days_ago=2)
            response = await client.post(
                f"{CHALLENGE_API}/{challenge.id}/histories", json={"is_success": True}, headers=headers
            )

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert response.json()["status"] == "COMPLETED"
        assert response.json()["histories"][-1]["current_round"] == 3

    async def test_count_based_challenge_allows_one_record_per_day(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(
                user, days_ago=1, challenge_type=ChallengeType.COUNT_BASED, total_rounds=10
            )
            url = f"{CHALLENGE_API}/{challenge.id}/histories"
            first = await client.post(url, json={"is_success": True}, headers=headers)
            second = await client.post(url, json={"is_success": True}, headers=headers)

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_409_CONFLICT

    async def test_count_based_challenge_fails_after_deadline(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(
                user,
                days_ago=settings.CHALLENGE_COUNT_BASED_DAYS,
                challenge_type=ChallengeType.COUNT_BASED,
                total_rounds=5,
            )
            await self.add_history(challenge, 1, days_ago=10)
            response = await client.get(f"{CHALLENGE_API}/{challenge.id}", headers=headers)

        assert response.json()["status"] == "FAILED"

    # ---------- 조회·캐시·권한 ----------

    async def test_detail_returns_histories_in_round_order(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.start_challenge(user, days_ago=3)
            await self.add_history(challenge, 2, days_ago=2)
            await self.add_history(challenge, 1, is_success=False, days_ago=3)
            response = await client.get(f"{CHALLENGE_API}/{challenge.id}", headers=headers)

        body = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert [item["current_round"] for item in body["histories"]] == [1, 2]
        assert body["progress"]["recorded_count"] == 2
        assert body["progress"]["success_count"] == 1
        assert body["progress"]["current_round"] == 4

    async def test_pending_challenge_has_no_progress(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            await self.create_challenge(user)
            listed = await client.get(CHALLENGE_API, headers=headers)

        assert listed.json()[0]["progress"] is None

    async def test_list_cache_is_invalidated_by_accept_and_record(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            challenge = await self.create_challenge(user)
            before = await client.get(CHALLENGE_API, headers=headers)
            await client.post(f"{CHALLENGE_API}/{challenge.id}/accept", headers=headers)
            accepted = await client.get(CHALLENGE_API, headers=headers)
            await client.post(f"{CHALLENGE_API}/{challenge.id}/histories", json={"is_success": True}, headers=headers)
            recorded = await client.get(CHALLENGE_API, headers=headers)

        assert before.json()[0]["status"] == "PENDING"
        assert accepted.json()[0]["status"] == "IN_PROGRESS"
        assert accepted.json()[0]["progress"]["can_record"] is True
        assert recorded.json()[0]["progress"]["success_count"] == 1
        assert recorded.json()[0]["progress"]["can_record"] is False

    async def test_accept_invalidates_recommendation_cache(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers, user = await self.signup(client)
            prediction = await DiseasePrediction.create(
                user=user,
                status=DiseasePredictionStatus.COMPLETED,
                feature={},
                challenge_status=ChallengeRecommendationStatus.COMPLETED,
            )
            challenge = await self.create_challenge(user, prediction=prediction)
            url = f"/api/v1/disease-predictions/{prediction.id}/challenges"
            cached = await client.get(url, headers=headers)
            await client.post(f"{CHALLENGE_API}/{challenge.id}/accept", headers=headers)
            refreshed = await client.get(url, headers=headers)

        assert cached.json()["challenges"][0]["status"] == "PENDING"
        assert refreshed.json()["challenges"][0]["status"] == "IN_PROGRESS"

    async def test_other_users_challenge_is_not_found(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            _, owner = await self.signup(client)
            challenge = await self.create_challenge(owner)
            other_headers, _ = await self.signup(client, email="other_participation@example.com", phone="01077776666")
            detail = await client.get(f"{CHALLENGE_API}/{challenge.id}", headers=other_headers)
            accept = await client.post(f"{CHALLENGE_API}/{challenge.id}/accept", headers=other_headers)
            record = await client.post(
                f"{CHALLENGE_API}/{challenge.id}/histories", json={"is_success": True}, headers=other_headers
            )
            missing = await client.get(f"{CHALLENGE_API}/999999", headers=other_headers)

        assert detail.status_code == status.HTTP_404_NOT_FOUND
        assert accept.status_code == status.HTTP_404_NOT_FOUND
        assert record.status_code == status.HTTP_404_NOT_FOUND
        assert missing.status_code == status.HTTP_404_NOT_FOUND
        assert (await PersonalChallenge.get(id=challenge.id)).status is ChallengeStatus.PENDING

    async def test_requires_authentication(self) -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            detail = await client.get(f"{CHALLENGE_API}/1")
            accept = await client.post(f"{CHALLENGE_API}/1/accept")
            record = await client.post(f"{CHALLENGE_API}/1/histories", json={"is_success": True})

        assert detail.status_code == status.HTTP_401_UNAUTHORIZED
        assert accept.status_code == status.HTTP_401_UNAUTHORIZED
        assert record.status_code == status.HTTP_401_UNAUTHORIZED
