from typing import Any
from uuid import UUID

from app.models.health_profiles import AnnualHealthScreening


class AnnualHealthScreeningRepository:
    async def create(self, user_id: UUID, **kwargs: Any) -> AnnualHealthScreening:
        return await AnnualHealthScreening.create(user_id=user_id, **kwargs)

    async def get_list_by_user_id(self, user_id: UUID) -> list[AnnualHealthScreening]:
        return await AnnualHealthScreening.filter(user_id=user_id)

    async def get_by_id(self, user_id: UUID, screening_id: UUID) -> AnnualHealthScreening | None:
        return await AnnualHealthScreening.get_or_none(user_id=user_id, id=screening_id)

    async def delete_by_id(self, user_id: UUID, screening_id: UUID) -> int:
        return await AnnualHealthScreening.filter(user_id=user_id, id=screening_id).delete()
