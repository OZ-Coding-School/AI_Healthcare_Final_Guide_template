from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, PositiveInt, field_serializer, model_validator

from app.core.enums import HabitStatus
from app.core.utils.date import normalize_datetime
from app.schemas.base import BaseSerializerModel
from app.schemas.mixins import ConditionalFieldValidationMixin


class MonthlyHealthSurveyCreateRequest(BaseModel, ConditionalFieldValidationMixin):
    smoking_status: HabitStatus
    smoking_fr_per_day: PositiveInt | None = None
    drinking_status: HabitStatus
    drinking_fr_per_week: PositiveInt | None = None
    drinking_amount_per_session: PositiveInt | None = None
    systolic_bp: PositiveInt
    diastolic_bp: PositiveInt
    pulse: PositiveInt | None = None

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
    start_year: Annotated[PositiveInt | None, Field(ge=2000)] = None
    end_year: Annotated[PositiveInt | None, Field(ge=2000)] = None

    @model_validator(mode="after")
    def validate_year_range(self) -> Self:
        if self.start_year and self.end_year and self.start_year > self.end_year:
            raise ValueError("start_year must be less than or equal to end_year")
        return self


class MonthlyHealthSurveyListResponse(BaseSerializerModel):
    id: UUID
    title: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_datetime_fields(self, value: datetime) -> str:
        return normalize_datetime(value)


class MonthlyHealthSurveyResponse(MonthlyHealthSurveyListResponse):
    smoking_status: HabitStatus
    smoking_fr_per_day: PositiveInt | None
    drinking_status: HabitStatus
    drinking_fr_per_week: PositiveInt | None
    drinking_amount_per_session: PositiveInt | None
    systolic_bp: PositiveInt
    diastolic_bp: PositiveInt
    pulse: PositiveInt | None

    @field_serializer("smoking_status", "drinking_status")
    def serialize_habit_status(self, value: HabitStatus) -> str:
        return value.label
