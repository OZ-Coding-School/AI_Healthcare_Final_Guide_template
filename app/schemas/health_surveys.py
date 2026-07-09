from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.enums import HabitStatus
from app.schemas.base import BaseSerializerModel
from app.schemas.mixins import ConditionalFieldValidationMixin


class MonthlyHealthSurveyCreateRequest(BaseModel, ConditionalFieldValidationMixin):
    smoking_status: HabitStatus
    smoking_fr_per_day: int | None = None
    drinking_status: HabitStatus
    drinking_fr_per_week: int | None = None
    drinking_amount_per_session: int | None = None
    systolic_bp: int
    diastolic_bp: int
    pulse: int | None = None

    @model_validator(mode="after")
    def validate_conditional_fields(self) -> Self:
        self._normalize_conditional_fields(
            field_names=("smoking_fr_per_day",), condition_field="smoking_status", expected_value=HabitStatus.CURRENT
        )
        self._normalize_conditional_fields(
            field_names=("drinking_fr_per_week", "drinking_amount_per_session"),
            condition_field="drinking_status",
            expected_value=HabitStatus.CURRENT,
        )
        return self


class MonthlyHealthSurveyListFilter(BaseModel):
    start_year: Annotated[int | None, Field(ge=2000)] = None
    end_year: Annotated[int | None, Field(ge=2000)] = None

    @model_validator(mode="after")
    def validate_year_range(self) -> Self:
        if self.start_year and self.end_year and self.start_year > self.end_year:
            raise ValueError("start_year must be less than or equal to end_year")
        return self


class MonthlyHealthSurveyListResponse(BaseSerializerModel):
    id: UUID
    title: str
    created_at: datetime


class MonthlyHealthSurveyResponse(BaseSerializerModel):
    id: UUID
    title: str
    smoking_status: HabitStatus
    smoking_fr_per_day: int | None
    drinking_status: HabitStatus
    drinking_fr_per_week: int | None
    drinking_amount_per_session: int | None
    systolic_bp: int
    diastolic_bp: int
    pulse: int | None
