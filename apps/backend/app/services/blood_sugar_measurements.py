from uuid import UUID

from fastapi import Depends, HTTPException

from app.models.health_profiles import BloodSugarMeasurement
from app.repositories.blood_sugar_measurement_repository import BloodSugarMeasurementRepository
from app.schemas.blood_sugar_measurements import BloodSugarMeasurementCreateRequest, BloodSugarMeasurementListFilter


class BloodSugarMeasurementService:
    def __init__(self, blood_sugar_measurement_repo: BloodSugarMeasurementRepository) -> None:
        self.repo = blood_sugar_measurement_repo

    async def get_blood_sugar_measurements(
        self, user_id: UUID, query_params: BloodSugarMeasurementListFilter
    ) -> list[BloodSugarMeasurement]:
        return await self.repo.get_filtered_list(user_id=user_id, **query_params.model_dump(exclude_unset=True))

    async def get_blood_sugar_measurement_by_id(self, user_id: UUID, measurement_id: UUID) -> BloodSugarMeasurement:
        measurement = await self.repo.get_by_id(user_id, measurement_id)
        if measurement is None:
            raise HTTPException(status_code=404, detail="Blood Sugar Measurement Not Found.")
        return measurement

    async def create_blood_sugar_measurement(
        self, user_id: UUID, data: BloodSugarMeasurementCreateRequest
    ) -> BloodSugarMeasurement:
        return await self.repo.create(user_id, data.model_dump(exclude_unset=True))

    async def delete_blood_sugar_measurement_by_id(self, user_id: UUID, measurement_id: UUID) -> None:
        deleted_count = await self.repo.delete_by_id(user_id, measurement_id)
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="Blood Sugar Measurement Not Found.")


def get_blood_sugar_measurement_service(
    repo: BloodSugarMeasurementRepository = Depends(BloodSugarMeasurementRepository),
) -> BloodSugarMeasurementService:
    return BloodSugarMeasurementService(blood_sugar_measurement_repo=repo)
