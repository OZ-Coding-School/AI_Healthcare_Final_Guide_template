from datetime import date, datetime
from typing import Any
from uuid import UUID

from tortoise.expressions import Q

from app.models.health_profiles import BloodSugarMeasurement


class BloodSugarMeasurementRepository:
    async def create(self, user_id: UUID, data: dict[str, Any]) -> BloodSugarMeasurement:
        return await BloodSugarMeasurement.create(user_id=user_id, **data)

    async def get_filtered_list(
        self,
        user_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[BloodSugarMeasurement]:
        query = BloodSugarMeasurement.filter(
            user_id=user_id,
        )
        if start_date is not None:
            start_datetime = datetime(year=start_date.year, month=start_date.month, day=start_date.day)
            query = query.filter(Q(measured_at__gte=start_datetime))
        if end_date is not None:
            end_datetime = datetime(year=end_date.year, month=end_date.month, day=end_date.day)
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            query = query.filter(Q(measured_at__lte=end_datetime))

        return await query.only("id", "measure_type", "measured_at", "created_at").order_by("measured_at").all()

    async def get_by_id(self, user_id: UUID, measurement_id: UUID) -> BloodSugarMeasurement | None:
        return await BloodSugarMeasurement.get_or_none(user_id=user_id, id=measurement_id)
