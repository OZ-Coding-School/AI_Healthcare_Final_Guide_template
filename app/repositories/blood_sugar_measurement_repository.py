from datetime import datetime
from typing import TypedDict
from uuid import UUID

from app.core.enums import BloodSugarMeasurementType
from app.models.health_profiles import BloodSugarMeasurement


class BloodSugarMeasurementCreateSchema(TypedDict):
    user_id: UUID
    measure_type: BloodSugarMeasurementType
    blood_glucose: int
    minutes_since_meal: int | None
    has_exercised: bool
    exercise_type: str | None
    exercise_minutes: int | None
    minutes_since_exercise: int | None
    has_medicated: bool
    medicine_name: str | None
    minutes_since_medication: int | None
    memo: str | None
    measured_at: datetime


class BloodSugarMeasurementRepository:
    async def create(self, user_id: UUID, **data: BloodSugarMeasurementCreateSchema) -> BloodSugarMeasurement:
        return await BloodSugarMeasurement.create(user_id=user_id, **data)

    async def get_list_by_user_id(self, user_id: UUID) -> list[BloodSugarMeasurement]:
        return await BloodSugarMeasurement.filter(user_id=user_id).all()

    async def get_by_id(self, user_id: UUID, measurement_id: UUID) -> BloodSugarMeasurement | None:
        return await BloodSugarMeasurement.get_or_none(user_id=user_id, id=measurement_id)
