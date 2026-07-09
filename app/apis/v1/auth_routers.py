from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import JSONResponse as Response

from app.core import settings
from app.core.config import Env
from app.dependencies.security import get_request_user
from app.models.user_models import User
from app.schemas.auth import LoginRequest, LoginResponse, SignUpRequest, TokenRefreshResponse
from app.schemas.users import SendVerificationMailRequest, UserWithdrawRequest, VerifyMailRequest
from app.services.auth import AuthService, get_auth_service

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    request_data: SignUpRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth_service.signup(request_data)


@auth_router.post("/signup/send-verification-mail", status_code=status.HTTP_201_CREATED)
async def send_signup_verification_mail(
    request_data: SendVerificationMailRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth_service.send_verification_email_for_signup(request_data.email)


@auth_router.post("/signup/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_signup_email(
    request_data: VerifyMailRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth_service.verify_email_for_signup(request_data.email, request_data.code)


@auth_router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    user = await auth_service.authenticate(request)
    tokens = await auth_service.login(user)
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(), status_code=status.HTTP_200_OK
    )
    resp.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if settings.ENV == Env.PROD else False,
        domain=settings.COOKIE_DOMAIN or None,
        expires=tokens["access_token"].payload["exp"],
    )
    return resp


@auth_router.post("/withdraw", status_code=status.HTTP_204_NO_CONTENT)
async def user_withdraw(
    request_data: UserWithdrawRequest,
    user: Annotated[User, Depends(get_request_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth_service.account_withdraw(user.id, request_data)


@auth_router.post("/auth/recovery/send-mail", status_code=status.HTTP_200_OK)
async def account_recovery_send_mail(
    request_data: SendVerificationMailRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth_service.send_verification_email_for_account_recovery(request_data.email)


@auth_router.post("/auth/recovery/verify-mail", status_code=status.HTTP_204_NO_CONTENT)
async def account_recovery_verify_email(
    request_data: VerifyMailRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth_service.account_recover(request_data.email, request_data.code)


@auth_router.get("/token/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
async def token_refresh(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenRefreshResponse:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing.")
    access_token = auth_service.token_refresh(refresh_token)
    return TokenRefreshResponse(access_token=str(access_token))
