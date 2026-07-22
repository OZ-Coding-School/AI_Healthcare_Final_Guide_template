from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from app.dependencies.security import get_request_user
from app.models.user_models import User
from app.schemas.health_surveys import (
    MonthlyHealthSurveyCreateRequest,
    MonthlyHealthSurveyListFilter,
    MonthlyHealthSurveyListResponse,
    MonthlyHealthSurveyResponse,
)
from app.services.health_survey import HealthSurveyService, get_health_survey_service

health_survey_router = APIRouter(prefix="/health-surveys", tags=["health-survey"])


@health_survey_router.post("", status_code=201)
async def create_monthly_health_survey(
    request_data: MonthlyHealthSurveyCreateRequest,
    request_user: User = Depends(get_request_user),
    health_survey_service: HealthSurveyService = Depends(get_health_survey_service),
) -> None:
    await health_survey_service.create_monthly_health_survey(request_user.id, request_data)


@health_survey_router.get("", response_model=list[MonthlyHealthSurveyListResponse], status_code=200)
async def get_monthly_health_survey_list(
    query_params: Annotated[MonthlyHealthSurveyListFilter, Query()],
    request_user: User = Depends(get_request_user),
    health_survey_service: HealthSurveyService = Depends(get_health_survey_service),
) -> list[MonthlyHealthSurveyListResponse]:
    surveys = await health_survey_service.get_monthly_health_survey_list(request_user.id, query_params)
    return [MonthlyHealthSurveyListResponse.model_validate(survey) for survey in surveys]


@health_survey_router.get("/{survey_id}", response_model=MonthlyHealthSurveyResponse, status_code=200)
async def get_monthly_health_survey_by_id(
    survey_id: Annotated[UUID, Path(title="Monthly Health Survey ID of the item to get")],
    request_user: User = Depends(get_request_user),
    health_survey_service: HealthSurveyService = Depends(get_health_survey_service),
) -> MonthlyHealthSurveyResponse:
    survey = await health_survey_service.get_monthly_health_survey_by_id(request_user.id, survey_id)
    return MonthlyHealthSurveyResponse.model_validate(survey)
