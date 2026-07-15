from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import EmailStr

from app.core import settings
from app.models.user_models import User


class UserRepository:
    async def get_user_by_id(self, user_id: UUID) -> User | None:
        return await User.get_or_none(id=user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        return await User.get_or_none(email=email)

    async def exists_by_email(self, email: str) -> bool:
        return await User.filter(email=email).exists()

    async def exists_by_phone_number(self, phone_number: str) -> bool:
        return await User.filter(phone_number=phone_number).exists()

    async def create_user(
        self,
        email: str | EmailStr,
        hashed_password: str,
        name: str,
        nickname: str,
        phone_number: str,
        *,
        is_active: bool = True,
        is_admin: bool = False,
    ) -> User:
        return await User.create(
            email=email,
            hashed_password=hashed_password,
            name=name,
            nickname=nickname,
            phone_number=phone_number,
            is_active=is_active,
            is_admin=is_admin,
        )

    async def update_last_login(self, user: User) -> User:
        user.last_login = datetime.now(settings.TIMEZONE)
        await user.save(update_fields=["last_login"])
        return user

    async def update_user(self, user: User, data: dict[str, Any]) -> User:
        for key, value in data.items():
            setattr(user, key, value)
        await user.save(update_fields=[k for k in data.keys()])

        return user

    async def deactivate_user_by_id(self, user_id: UUID) -> None:
        await User.filter(id=user_id).update(is_active=False)

    async def activate_user_by_id(self, user_id: UUID) -> None:
        await User.filter(id=user_id).update(is_active=True)
