from uuid import UUID

from fastapi import Depends, HTTPException

from app.models.health_profiles import AnnualHealthScreening
from app.repositories.annual_health_screening_repository import AnnualHealthScreeningRepository
from app.schemas.annual_health_screenings import AnnualHealthScreeningCreateRequest


class AnnualHealthScreeningService:
    def __init__(self, repository: AnnualHealthScreeningRepository) -> None:
        self.repo = repository

    async def create_annual_health_screening(self, user_id: UUID, data: AnnualHealthScreeningCreateRequest) -> None:
        await self.repo.create(user_id, **data.model_dump())

    async def get_list_by_user(self, user_id: UUID) -> list[AnnualHealthScreening]:
        return await self.repo.get_list_by_user_id(user_id)

    async def get_by_id(self, user_id: UUID, screening_id: UUID) -> AnnualHealthScreening | None:
        screening = await self.repo.get_by_id(user_id, screening_id)
        if screening is None:
            raise HTTPException(status_code=404, detail="Annual Health Screening Not Found.")
        return screening

    async def delete_by_id(self, user_id: UUID, screening_id: UUID) -> None:
        deleted_count = await self.repo.delete_by_id(user_id, screening_id)
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="Annual Health Screening Not Found.")


def get_annual_health_screening_service(
    annual_health_screening_repo: AnnualHealthScreeningRepository = Depends(AnnualHealthScreeningRepository),
) -> AnnualHealthScreeningService:
    return AnnualHealthScreeningService(repository=annual_health_screening_repo)
