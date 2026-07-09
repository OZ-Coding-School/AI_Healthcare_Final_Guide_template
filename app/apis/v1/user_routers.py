from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies.security import get_request_user
from app.models.user_models import User
from app.schemas.users import UserInfoResponse, UserUpdateRequest
from app.services.users import UserService, get_user_service

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/me", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def get_user(
    user: Annotated[User, Depends(get_request_user)],
) -> UserInfoResponse:
    return UserInfoResponse.model_validate(user)


@user_router.patch("/me", response_model=UserInfoResponse, status_code=status.HTTP_200_OK)
async def update_user(
    update_data: UserUpdateRequest,
    user: Annotated[User, Depends(get_request_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserInfoResponse:
    updated_user = await user_service.update_user(user=user, data=update_data)
    return UserInfoResponse.model_validate(updated_user)
