from unittest.mock import AsyncMock, patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.enums import UrineGlucoseStatus, UrineProteinStatus
from main import app


class TestAnnualHealthScreeningAPI(TestCase):
    def setUp(self):
        super().setUp()
        self.signup_data = {
            "email": "ahs_test@example.com",
            "password": "Password123!",
            "nickname": "AHS테스터",
            "name": "AHS테스터",
            "phone_number": "01099998888",
        }
        self.login_data = {"email": "ahs_test@example.com", "password": "Password123!"}
        self.api_path = "/api/v1/annual-health-screenings"

    async def get_token(self, client: AsyncClient):
        with patch("app.services.auth.AuthService.ensure_signup_email_verified", AsyncMock()):
            await client.post("/api/v1/auth/signup", json=self.signup_data)
        response = await client.post("/api/v1/auth/login", json=self.login_data)
        return response.json()["access_token"]

    def get_valid_screening_data(self):
        return {
            "height": 170.5,
            "weight": 65.0,
            "bmi": 22.4,
            "waist_circumference": 80.0,
            "sbp": 120,
            "dbp": 80,
            "pulse": 72,
            "fbs": 95,
            "hba1c": 5.5,
            "triglyceride": 140,
            "ldl": 100,
            "hdl": 60,
            "total_cholesterol": 190,
            "ast": 25,
            "alt": 20,
            "gamma_gtp": 30,
            "egfr": 90,
            "creatinine": 0.9,
            "urine_protein": UrineProteinStatus.NEGATIVE,
            "urine_glucose": UrineGlucoseStatus.NEGATIVE,
            "family_history_diabetes": False,
            "family_history_hypertension": False,
            "screening_at": "2024-07-14",
            "is_fasting": True,
        }

    async def test_create_annual_health_screening_success(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            data = self.get_valid_screening_data()

            response = await client.post(self.api_path, json=data, headers=headers)
            assert response.status_code == status.HTTP_201_CREATED

    async def test_create_annual_health_screening_invalid_data(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            # 잘못된 고혈압 수치 (음수)
            data = self.get_valid_screening_data()
            data["sbp"] = -1

            response = await client.post(self.api_path, json=data, headers=headers)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_get_annual_health_screening_list_success(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            # 2개 데이터 생성
            data1 = self.get_valid_screening_data()
            data1["screening_at"] = "2023-01-01"
            await client.post(self.api_path, json=data1, headers=headers)

            data2 = self.get_valid_screening_data()
            data2["screening_at"] = "2024-01-01"
            await client.post(self.api_path, json=data2, headers=headers)

            response = await client.get(self.api_path, headers=headers)
            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            assert len(result) == 2
            # 필드 확인
            assert "id" in result[0]
            assert "title" in result[0]
            assert "screening_at" in result[0]

    async def test_get_annual_health_screening_by_id_success(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            # 데이터 생성
            data = self.get_valid_screening_data()
            await client.post(self.api_path, json=data, headers=headers)

            # 목록에서 ID 가져오기
            list_resp = await client.get(self.api_path, headers=headers)
            screening_id = list_resp.json()[0]["id"]

            # 상세 조회
            response = await client.get(f"{self.api_path}/{screening_id}", headers=headers)
            assert response.status_code == status.HTTP_200_OK
            detail = response.json()
            assert detail["height"] == "170.5"
            assert detail["weight"] == "65.0"
            assert detail["sbp"] == 120

    async def test_get_annual_health_screening_by_id_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            random_id = str(uuid4())
            response = await client.get(f"{self.api_path}/{random_id}", headers=headers)
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["detail"] == "Annual Health Screening Not Found."

    async def test_delete_annual_health_screening_success(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            # 데이터 생성
            data = self.get_valid_screening_data()
            await client.post(self.api_path, json=data, headers=headers)

            # 목록에서 ID 가져오기
            list_resp = await client.get(self.api_path, headers=headers)
            screening_id = list_resp.json()[0]["id"]

            # 삭제
            response = await client.delete(f"{self.api_path}/{screening_id}", headers=headers)
            assert response.status_code == status.HTTP_204_NO_CONTENT

            # 삭제 확인
            check_resp = await client.get(f"{self.api_path}/{screening_id}", headers=headers)
            assert check_resp.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_annual_health_screening_not_found(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await self.get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            random_id = str(uuid4())
            response = await client.delete(f"{self.api_path}/{random_id}", headers=headers)
            assert response.status_code == status.HTTP_404_NOT_FOUND
