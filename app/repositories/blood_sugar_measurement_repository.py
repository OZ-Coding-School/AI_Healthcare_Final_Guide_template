from typing import Any
from uuid import UUID

from app.models.health_profiles import BloodSugarMeasurement


class BloodSugarMeasurementRepository:
    async def create(self, user_id: UUID, data: dict[str, Any]) -> BloodSugarMeasurement:
        return await BloodSugarMeasurement.create(user_id=user_id, **data)

    async def get_list_by_user_id(self, user_id: UUID) -> list[BloodSugarMeasurement]:
        return await BloodSugarMeasurement.filter(user_id=user_id).all()

    async def get_by_id(self, user_id: UUID, measurement_id: UUID) -> BloodSugarMeasurement | None:
        return await BloodSugarMeasurement.get_or_none(user_id=user_id, id=measurement_id)
