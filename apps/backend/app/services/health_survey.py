from uuid import UUID

from fastapi import Depends, HTTPException

from app.models.health_profiles import MonthlyHealthSurvey
from app.repositories.monthly_health_survey_repository import MonthlyHealthSurveyRepository
from app.schemas.health_surveys import MonthlyHealthSurveyCreateRequest, MonthlyHealthSurveyListFilter


class HealthSurveyService:
    def __init__(
        self,
        monthly_health_survey_repo: MonthlyHealthSurveyRepository,
    ) -> None:
        self.monthly_health_survey_repo = monthly_health_survey_repo

    async def create_monthly_health_survey(
        self, user_id: UUID, data: MonthlyHealthSurveyCreateRequest
    ) -> MonthlyHealthSurvey:
        if await self._has_submitted_this_month(user_id):
            raise HTTPException(status_code=409, detail="Monthly Health Survey already submitted this month.")
        return await self.monthly_health_survey_repo.create(user_id, **data.model_dump())

    async def get_monthly_health_survey_by_id(self, user_id: UUID, survey_id: UUID) -> MonthlyHealthSurvey | None:
        survey = await self.monthly_health_survey_repo.get_by_id(user_id, survey_id)
        if survey is None:
            raise HTTPException(status_code=404, detail="Monthly Health Survey Not Found.")
        return survey

    async def get_monthly_health_survey_list(
        self, user_id: UUID, filters: MonthlyHealthSurveyListFilter
    ) -> list[MonthlyHealthSurvey]:
        return await self.monthly_health_survey_repo.get_list(user_id, **filters.model_dump())

    async def _has_submitted_this_month(self, user_id: UUID) -> bool:
        return await self.monthly_health_survey_repo.exists_this_month(user_id)


def get_health_survey_service(
    repo: MonthlyHealthSurveyRepository = Depends(MonthlyHealthSurveyRepository),
) -> HealthSurveyService:
    return HealthSurveyService(repo)
