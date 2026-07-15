from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from main import app


class TestSignupAPI(TestCase):
    def setUp(self):
        super().setUp()
        self.signup_data = {
            "email": "test@example.com",
            "password": "Password123!",
            "nickname": "테스터",
            "name": "테스터",
            "phone_number": "01012345678",
        }

    async def test_signup_success(self):
        from app.services.mail_service import get_mail_service

        mock_mail_service = AsyncMock()
        app.dependency_overrides[get_mail_service] = lambda: mock_mail_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. 회원가입 이메일 인증 메일 발송 api 호출
            send_mail_resp = await client.post(
                "/api/v1/auth/signup/send-verification-mail", json={"email": self.signup_data["email"]}
            )
            assert send_mail_resp.status_code == status.HTTP_201_CREATED

            # AuthService._send_verification_email에서 mail_service.send_with_template를 호출함
            call_args = mock_mail_service.send_with_template.call_args
            verification_code = call_args.kwargs["context"]["verification_code"]

            # 2. 회원가입 이메일 인증 검증 api 호출
            verify_resp = await client.post(
                "/api/v1/auth/signup/verify-email", json={"email": self.signup_data["email"], "code": verification_code}
            )
            assert verify_resp.status_code == status.HTTP_204_NO_CONTENT

            # 3. 회원가입 api 호출
            response = await client.post("/api/v1/auth/signup", json=self.signup_data)
            assert response.status_code == status.HTTP_201_CREATED

        app.dependency_overrides.pop(get_mail_service)

    async def test_signup_without_verification_fail(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=self.signup_data)
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_signup_invalid_email(self):
        signup_data = self.signup_data.copy()
        signup_data["email"] = "invalid-email"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=signup_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_signup_invalid_phone_format(self):
        signup_data = self.signup_data.copy()
        signup_data["phone_number"] = "010&3333&4444"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup", json=signup_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
