from uuid import UUID

from fastapi import Depends, HTTPException
from starlette import status

from app.core.utils.common import normalize_phone_number
from app.dtos.users import UserUpdateRequest
from app.models.user_models import User
from app.repositories.user_repository import UserRepository
from app.repositories.user_withdrawal_repository import UserWithdrawalRepository


class UserService:
    def __init__(self, user_repo: UserRepository, withdrawal_repo: UserWithdrawalRepository) -> None:
        self.user_repo = user_repo
        self.withdrawal_repo = withdrawal_repo

    async def get_user_by_id(self, user_id: UUID) -> User:
        user = await self.user_repo.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return user

    async def update_user(self, user: User, data: UserUpdateRequest) -> User:
        if data.phone_number:
            normalized_phone_number = normalize_phone_number(data.phone_number)
            await self.check_phone_number_exists(normalized_phone_number)
            data.phone_number = normalized_phone_number
        return await self.user_repo.update_user(user=user, data=data.model_dump(exclude_unset=True))

    async def check_phone_number_exists(self, phone_number: str) -> None:
        if await self.user_repo.exists_by_phone_number(phone_number):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용중인 휴대폰 번호입니다.")


def get_user_service(
    user_repo: UserRepository = Depends(UserRepository),
    withdrawal_repo: UserWithdrawalRepository = Depends(UserWithdrawalRepository),
) -> UserService:
    return UserService(user_repo, withdrawal_repo)
