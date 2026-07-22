from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.enums import Gender
from app.models.health_profiles import HealthProfile


class HealthProfileRepository:
    async def create_health_profile(
        self,
        user_id: UUID,
        *,
        gender: Gender,
        birth_date: date,
        height: Decimal,
        weight: Decimal,
        has_diabetes: bool,
        has_hypertension: bool,
    ) -> HealthProfile:
        return await HealthProfile.create(
            user_id=user_id,
            gender=gender,
            birth_date=birth_date,
            height=height,
            weight=weight,
            has_diabetes=has_diabetes,
            has_hypertension=has_hypertension,
        )

    async def get_health_profile_by_user_id(self, user_id: UUID) -> HealthProfile | None:
        return await HealthProfile.get_or_none(user_id=user_id)

    async def update_health_profile(self, health_profile: HealthProfile, data: dict[str, Any]) -> HealthProfile:
        for key, value in data.items():
            setattr(health_profile, key, value)
        await health_profile.save(update_fields=[k for k in data.keys()])
        return health_profile
