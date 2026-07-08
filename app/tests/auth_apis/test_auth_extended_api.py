from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.core.enums import WithdrawalReason
from app.main import app


class TestAuthExtendedAPI(TestCase):
    def setUp(self):
        super().setUp()
        self.email = "auth_ext@example.com"
        self.password = "Password123!"

    async def test_send_signup_verification_mail(self):
        from app.services.mail_service import get_mail_service

        mock_mail_service = AsyncMock()
        app.dependency_overrides[get_mail_service] = lambda: mock_mail_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/signup/send-verification-mail", json={"email": self.email})

        assert response.status_code == status.HTTP_201_CREATED
        assert mock_mail_service.send_with_template.called

        app.dependency_overrides.pop(get_mail_service)

    async def test_verify_signup_email_success(self):
        from app.services.mail_service import get_mail_service

        mock_mail_service = AsyncMock()
        app.dependency_overrides[get_mail_service] = lambda: mock_mail_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. 메일 발송 (이때 redis에 코드 저장됨)
            await client.post("/api/v1/auth/signup/send-verification-mail", json={"email": self.email})
            call_args = mock_mail_service.send_with_template.call_args
            verification_code = call_args.kwargs["context"]["verification_code"]

            # 2. 코드 검증
            response = await client.post(
                "/api/v1/auth/signup/verify-email", json={"email": self.email, "code": verification_code}
            )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        app.dependency_overrides.pop(get_mail_service)

    @patch("app.services.auth.get_redis")
    async def test_verify_signup_email_fail(self, mock_get_redis):
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = "123456"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/signup/verify-email", json={"email": self.email, "code": "wrong"}
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_withdraw_success(self):
        # 1. 가입
        signup_data = {
            "email": "withdraw@example.com",
            "password": "Password123!",
            "nickname": "탈퇴테스터",
            "name": "탈퇴테스터",
            "phone_number": "01055556666",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 회원가입 전 이메일 인증 통과를 위해 redis mocking 필요하나
            # 여기서는 API 레벨이므로 직접 DB에 유저를 생성하거나 가입 API를 호출할 때 redis mock 필요
            with patch("app.services.auth.AuthService.ensure_signup_email_verified", AsyncMock()):
                await client.post("/api/v1/auth/signup", json=signup_data)

            # 2. 로그인
            login_resp = await client.post(
                "/api/v1/auth/login", json={"email": "withdraw@example.com", "password": "Password123!"}
            )
            token = login_resp.json()["access_token"]

            # 3. 탈퇴
            withdraw_data = {
                "reason": WithdrawalReason.NOT_USE,
                "reason_details": "너무 바빠요",
                "feedback": "좋은 앱이네요",
            }
            response = await client.post(
                "/api/v1/auth/withdraw", json=withdraw_data, headers={"Authorization": f"Bearer {token}"}
            )
            assert (
                response.status_code == status.HTTP_204_NO_CONTENT or response.status_code == status.HTTP_204_NO_CONTENT
            )

            # 4. 탈퇴 후 로그인 실패 확인
            login_resp_after = await client.post(
                "/api/v1/auth/login", json={"email": "withdraw@example.com", "password": "Password123!"}
            )
            assert login_resp_after.status_code == status.HTTP_423_LOCKED

    async def test_account_recovery_flow(self):
        from app.services.mail_service import get_mail_service

        mock_mail_service = AsyncMock()
        app.dependency_overrides[get_mail_service] = lambda: mock_mail_service

        email = "recover@example.com"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. 가입 및 탈퇴 처리
            with patch("app.services.auth.AuthService.ensure_signup_email_verified", AsyncMock()):
                await client.post(
                    "/api/v1/auth/signup",
                    json={
                        "email": email,
                        "password": "Password123!",
                        "nickname": "R",
                        "name": "R",
                        "phone_number": "01077778888",
                    },
                )

            login_resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
            token = login_resp.json()["access_token"]
            await client.post(
                "/api/v1/auth/withdraw",
                json={"reason": WithdrawalReason.OTHER},
                headers={"Authorization": f"Bearer {token}"},
            )

            # 2. 복구 메일 발송
            response = await client.post("/api/v1/auth/auth/recovery/send-mail", json={"email": email})
            assert response.status_code == status.HTTP_200_OK
            assert mock_mail_service.send_with_template.called

            # 3. 메일 인증 및 복구
            call_args = mock_mail_service.send_with_template.call_args
            verification_code = call_args.kwargs["context"]["verification_code"]

            response = await client.post(
                "/api/v1/auth/auth/recovery/verify-mail", json={"email": email, "code": verification_code}
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

            # 4. 복구 후 로그인 확인
            login_resp_final = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
            )
            assert login_resp_final.status_code == status.HTTP_200_OK

        app.dependency_overrides.pop(get_mail_service)
