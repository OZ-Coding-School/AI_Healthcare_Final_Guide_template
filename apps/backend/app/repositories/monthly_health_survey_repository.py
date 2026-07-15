from datetime import datetime
from uuid import UUID

from tortoise.expressions import Q

from app.core.enums import HabitStatus
from app.models.health_profiles import MonthlyHealthSurvey


class MonthlyHealthSurveyRepository:
    async def create(
        self,
        user_id: UUID,
        smoking_status: HabitStatus,
        smoking_fr_per_day: int | None,
        drinking_status: HabitStatus,
        drinking_fr_per_week: int | None,
        drinking_amount_per_session: int | None,
        systolic_bp: int,
        diastolic_bp: int,
        pulse: int | None = None,
    ) -> MonthlyHealthSurvey:
        return await MonthlyHealthSurvey.create(
            user_id=user_id,
            smoking_status=smoking_status,
            smoking_fr_per_day=smoking_fr_per_day,
            drinking_status=drinking_status,
            drinking_fr_per_week=drinking_fr_per_week,
            drinking_amount_per_session=drinking_amount_per_session,
            systolic_bp=systolic_bp,
            diastolic_bp=diastolic_bp,
            pulse=pulse,
        )

    async def get_list(
        self,
        user_id: UUID,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[MonthlyHealthSurvey]:
        queryset = MonthlyHealthSurvey.filter(user_id=user_id)

        if start_year:
            queryset = queryset.filter(Q(created_at__gte=datetime(start_year, 1, 1)))
        if end_year:
            queryset = queryset.filter(Q(created_at__lte=datetime(end_year, 12, 31)))

        return await queryset.all()

    async def get_by_id(self, user_id: UUID, survey_id: UUID) -> MonthlyHealthSurvey | None:
        return await MonthlyHealthSurvey.get_or_none(user_id=user_id, id=survey_id)

    async def exists_this_month(self, user_id: UUID) -> bool:
        now = datetime.now()
        start_at = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_at = start_at.replace(day=31, hour=23, minute=59, second=59, microsecond=999999)
        return await MonthlyHealthSurvey.filter(
            user_id=user_id, created_at__gte=start_at, created_at__lte=end_at
        ).exists()
