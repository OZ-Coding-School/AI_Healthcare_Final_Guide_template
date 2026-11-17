from datetime import datetime, timedelta
from uuid import UUID

from tortoise.expressions import Q

from app.core.enums import DrinkingFrequency, HabitStatus
from app.models.health_profiles import MonthlyHealthSurvey


class MonthlyHealthSurveyRepository:
    async def create(
        self,
        user_id: UUID,
        smoking_status: HabitStatus,
        smoking_fr_per_day: int | None,
        drinking_status: HabitStatus,
        drinking_frequency: DrinkingFrequency,
        drinking_amount_per_session: int | None,
        systolic_bp: int,
        diastolic_bp: int,
    ) -> MonthlyHealthSurvey:
        return await MonthlyHealthSurvey.create(
            user_id=user_id,
            smoking_status=smoking_status,
            smoking_fr_per_day=smoking_fr_per_day,
            drinking_status=drinking_status,
            drinking_frequency=drinking_frequency,
            drinking_amount_per_session=drinking_amount_per_session,
            systolic_bp=systolic_bp,
            diastolic_bp=diastolic_bp,
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

    async def get_latest_by_user_id(self, user_id: UUID) -> MonthlyHealthSurvey | None:
        return await MonthlyHealthSurvey.filter(user_id=user_id).order_by("-created_at").first()

    async def exists_this_month(self, user_id: UUID) -> bool:
        start_at, next_month_start = month_bounds(datetime.now())
        return await MonthlyHealthSurvey.filter(
            user_id=user_id, created_at__gte=start_at, created_at__lt=next_month_start
        ).exists()


def month_bounds(moment: datetime) -> tuple[datetime, datetime]:
    """
    moment가 속한 달의 시작 시각과 다음 달 시작 시각을 반환합니다.
    끝을 "다음 달 1일 0시 미만"으로 두어 달 길이(28~31일)와 연도 경계에 상관없이 동작합니다.
    """
    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 1일에서 32일을 더하면 항상 다음 달 안에 들어가므로, 다시 1일로 맞추면 다음 달 시작입니다.
    next_start = (start + timedelta(days=32)).replace(day=1)
    return start, next_start
