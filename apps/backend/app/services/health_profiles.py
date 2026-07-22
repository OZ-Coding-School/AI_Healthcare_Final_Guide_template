from uuid import UUID

from fastapi import Depends, HTTPException
from tortoise.exceptions import IntegrityError

from app.models.health_profiles import HealthProfile
from app.repositories.health_profile_repository import HealthProfileRepository
from app.schemas.health_profiles import HealthProfileCreateRequest, HealthProfileUpdateRequest


class HealthProfileService:
    def __init__(self, repo: HealthProfileRepository) -> None:
        self.repo = repo

    async def create_health_profile(self, user_id: UUID, dto: HealthProfileCreateRequest) -> HealthProfile:
        if await self.repo.get_health_profile_by_user_id(user_id):
            raise HTTPException(status_code=400, detail="Health profile already exists.")
        try:
            return await self.repo.create_health_profile(user_id, **dto.model_dump())
        except IntegrityError as e:
            raise HTTPException(status_code=400, detail="Health profile already exists.") from e

    async def get_health_profile_by_user_id(self, user_id: UUID) -> HealthProfile:
        health_profile = await self.repo.get_health_profile_by_user_id(user_id)
        if health_profile is None:
            raise HTTPException(status_code=404, detail="Health profile Not Found.")
        return health_profile

    async def update_health_profile(self, user_id: UUID, dto: HealthProfileUpdateRequest) -> HealthProfile:
        health_profile = await self.get_health_profile_by_user_id(user_id)
        return await self.repo.update_health_profile(health_profile, dto.model_dump(exclude_unset=True))


def get_health_profile_service(
    repo: HealthProfileRepository = Depends(HealthProfileRepository),
) -> HealthProfileService:
    return HealthProfileService(repo)
