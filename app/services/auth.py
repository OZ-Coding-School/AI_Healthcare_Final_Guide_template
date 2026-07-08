import secrets
from enum import StrEnum
from uuid import UUID

from fastapi import Depends
from fastapi.exceptions import HTTPException
from pydantic import EmailStr
from redis.asyncio import Redis
from starlette import status
from tortoise.transactions import in_transaction

from app.core import settings
from app.core.utils.common import normalize_phone_number
from app.core.utils.jwt.provider import JWTProvider
from app.core.utils.jwt.tokens import AccessToken, RefreshToken
from app.core.utils.redis import get_redis
from app.core.utils.security import hash_password, verify_password
from app.dtos.auth import LoginRequest, SignUpRequest
from app.dtos.users import UserWithdrawRequest
from app.models.user_models import User
from app.repositories.user_repository import UserRepository
from app.repositories.user_withdrawal_repository import UserWithdrawalRepository
from app.services.mail_service import MailService, get_mail_service


class VerificationPurpose(StrEnum):
    SIGNUP = "회원가입"
    ACCOUNT_RECOVERY = "계정복구"


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        withdrawal_repo: UserWithdrawalRepository,
        jwt_provider: JWTProvider,
        mail_service: MailService,
        redis_client: Redis,
    ) -> None:
        self.user_repo = user_repo
        self.withdrawal_repo = withdrawal_repo
        self.jwt_provider = jwt_provider
        self.mail_service = mail_service
        self.redis_client = redis_client

    async def signup(self, data: SignUpRequest) -> User:
        # 이메일 인증여부 확인
        await self.ensure_signup_email_verified(data.email)

        # 이메일 중복가입 여부 확인
        await self._check_email_exists(data.email)

        # 입력받은 휴대폰 번호를 노말라이즈
        normalized_phone_number = normalize_phone_number(data.phone_number)

        # 휴대폰 번호 중복 체크
        await self._check_phone_number_exists(normalized_phone_number)

        # 유저 생성
        async with in_transaction():
            user = await self.user_repo.create_user(
                email=data.email,
                hashed_password=hash_password(data.password),  # 해시화된 비밀번호를 사용
                nickname=data.nickname,
                name=data.name,
                phone_number=normalized_phone_number,
            )

        # 유저 회원가입 인증 여부 키 삭제
        await self.redis_client.delete(f"signup_verification:{data.email}")

        return user

    async def authenticate(self, data: LoginRequest) -> User:
        # 이메일로 사용자 조회
        email = str(data.email)
        user = await self.user_repo.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 또는 비밀번호가 올바르지 않습니다."
            )

        # 비밀번호 검증
        if not verify_password(user.hashed_password, data.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="이메일 또는 비밀번호가 올바르지 않습니다."
            )

        # 활성 사용자 체크
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="비활성화된 계정입니다.")

        return user

    async def login(self, user: User) -> dict[str, AccessToken | RefreshToken]:
        if not user.is_active and user.withdrawal is not None:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="탈퇴한 계정입니다.")

        await self.user_repo.update_last_login(user)
        return self.jwt_provider.issue_jwt_pair(user)

    async def account_withdraw(self, user_id: UUID, dto: UserWithdrawRequest) -> None:
        async with in_transaction():
            await self.withdrawal_repo.create_withdrawal(user_id, **dto.model_dump())
            await self.user_repo.deactivate_user_by_id(user_id)

    async def account_recover(self, email: EmailStr, code: str) -> None:
        await self._verify_email_for_account_recovery(email, code)
        user = await self._ensure_withdrawn_user(email)

        async with in_transaction():
            await self.withdrawal_repo.delete_withdrawal_by_user_id(user.id)
            await self.user_repo.activate_user_by_id(user.id)

    async def send_verification_email_for_signup(self, email: EmailStr) -> None:
        await self._send_verification_email(email, VerificationPurpose.SIGNUP)

    async def verify_email_for_signup(self, email: EmailStr, code: str) -> None:
        cached_code = await self._get_cached_verification_code(email, VerificationPurpose.SIGNUP)
        if cached_code != code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
        await self._del_cached_verification_code(email, VerificationPurpose.SIGNUP)
        await self.redis_client.set(
            self._build_signup_verification_cache_key(email), "verified", ex=settings.EMAIL_VERIFICATION_TTL
        )

    async def ensure_signup_email_verified(self, email: EmailStr) -> None:
        verified = await self.redis_client.get(self._build_signup_verification_cache_key(email))
        if not verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Email verification has not been completed."
            )

    async def send_verification_email_for_account_recovery(self, email: EmailStr) -> None:
        await self._ensure_withdrawn_user(email)
        await self._send_verification_email(email, VerificationPurpose.ACCOUNT_RECOVERY)

    async def _ensure_withdrawn_user(self, email: str) -> User:
        user = await self.user_repo.get_user_by_email(email)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        if user.is_active and user.withdrawal is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already user activated.")
        return user

    async def _verify_email_for_account_recovery(self, email: EmailStr, code: str) -> None:
        cached_code = await self._get_cached_verification_code(email, VerificationPurpose.ACCOUNT_RECOVERY)
        if not cached_code == code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
        await self._del_cached_verification_code(email, VerificationPurpose.ACCOUNT_RECOVERY)

    async def _send_verification_email(self, email: EmailStr, purpose: VerificationPurpose) -> None:
        verification_code = self._create_verification_code()
        context = {"email": email, "purpose": purpose.value, "verification_code": verification_code}

        await self.mail_service.send_with_template(
            to=email,
            subject=f"[AI HealthCare APP] {purpose.value}를 위한 인증 메일입니다.",
            template_name="email_verification.html",
            context=context,
        )
        await self._cache_verification_code(email, purpose, verification_code)

    @staticmethod
    def _build_signup_verification_cache_key(email: EmailStr) -> str:
        return f"signup_verification:{email}"

    @staticmethod
    def _build_verification_code_cache_key(email: EmailStr, purpose: VerificationPurpose) -> str:
        return f"verification:{email}:{purpose.name}"

    async def _cache_verification_code(self, email: EmailStr, purpose: VerificationPurpose, code: str) -> None:
        await self.redis_client.set(
            name=self._build_verification_code_cache_key(email, purpose), value=code, ex=settings.EMAIL_VERIFICATION_TTL
        )

    async def _get_cached_verification_code(self, email: EmailStr, purpose: VerificationPurpose) -> str | None:
        return await self.redis_client.get(self._build_verification_code_cache_key(email, purpose))

    async def _del_cached_verification_code(self, email: EmailStr, purpose: VerificationPurpose) -> None:
        await self.redis_client.delete(self._build_verification_code_cache_key(email, purpose))

    @staticmethod
    def _create_verification_code(length: int = 6) -> str:
        upper = 10**length
        return f"{secrets.randbelow(upper):0{length}d}"

    async def _check_email_exists(self, email: str | EmailStr) -> None:
        if await self.user_repo.exists_by_email(email):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 이메일입니다.")

    async def _check_phone_number_exists(self, phone_number: str) -> None:
        if await self.user_repo.exists_by_phone_number(phone_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 휴대폰 번호입니다.")

    def token_refresh(self, refresh_token: str) -> AccessToken:
        return self.jwt_provider.refresh_jwt(refresh_token)


def get_auth_service(
    user_repo: UserRepository = Depends(UserRepository),
    withdrawal_repo: UserWithdrawalRepository = Depends(UserWithdrawalRepository),
    jwt_provider: JWTProvider = Depends(JWTProvider),
    mail_service: MailService = Depends(get_mail_service),
    redis_client: Redis = Depends(get_redis),
) -> AuthService:
    return AuthService(user_repo, withdrawal_repo, jwt_provider, mail_service, redis_client)
