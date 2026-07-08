from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.enums import Gender
from app.main import app


class TestHealthProfileAPI(TestCase):
    def setUp(self):
        super().setUp()
        self.signup_data = {
            "email": "hp_test@example.com",
            "password": "Password123!",
            "nickname": "HP테스터",
            "name": "HP테스터",
            "phone_number": "01011113333",
        }
        self.login_data = {"email": "hp_test@example.com", "password": "Password123!"}

    async def get_token(self, client: AsyncClient):
        with patch("app.services.auth.AuthService.ensure_signup_email_verified", AsyncMock()):
            await client.post("/api/v1/auth/signup", json=self.signup_data)
        response = await client.post("/api/v1/auth/login", json=self.login_data)
        return response.json()["access_token"]

    async def test_create_health_profile_success(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            hp_data = {
                "gender": Gender.MALE,
                "birth_date": "1990-01-01",
                "height": 175.5,
                "weight": 70.0,
                "has_diabetes": False,
                "has_hypertension": False,
            }

            response = await client.post("/api/v1/health-profile/", json=hp_data, headers=headers)
            assert response.status_code == status.HTTP_201_CREATED

    async def test_get_health_profile_success(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            # 먼저 생성
            hp_data = {
                "gender": Gender.FEMALE,
                "birth_date": "1992-05-20",
                "height": 160.0,
                "weight": 55.0,
                "has_diabetes": True,
                "has_hypertension": False,
            }
            await client.post("/api/v1/health-profile/", json=hp_data, headers=headers)

            # 조회
            response = await client.get("/api/v1/health-profile/", headers=headers)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["gender"] == Gender.FEMALE
            assert data["height"] == "160.0"
            assert data["has_diabetes"] is True

    async def test_update_health_profile_success(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            # 먼저 생성
            hp_data = {
                "gender": Gender.MALE,
                "birth_date": "1985-10-10",
                "height": 180.0,
                "weight": 80.0,
                "has_diabetes": False,
                "has_hypertension": False,
            }
            await client.post("/api/v1/health-profile/", json=hp_data, headers=headers)

            # 수정
            update_data = {"weight": 78.5, "has_hypertension": True}
            response = await client.patch("/api/v1/health-profile/", json=update_data, headers=headers)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["weight"] == "78.5"
            assert data["has_hypertension"] is True
            assert data["height"] == "180.0"  # 기존 값 유지 확인

    async def test_health_profile_unauthorized(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 토큰 없이 요청
            response = await client.get("/api/v1/health-profile/")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_create_health_profile_invalid_data(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            # 잘못된 키 (0 미만)
            hp_data = {
                "gender": Gender.MALE,
                "birth_date": "1990-01-01",
                "height": -1,
                "weight": 70.0,
                "has_diabetes": False,
                "has_hypertension": False,
            }

            response = await client.post("/api/v1/health-profile/", json=hp_data, headers=headers)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
