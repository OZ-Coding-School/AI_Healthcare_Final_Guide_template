from datetime import date, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, PositiveInt, field_serializer, model_validator

from app.core.enums import BloodSugarMeasurementType, ExerciseType
from app.schemas.base import BaseSerializerModel
from app.schemas.mixins import ConditionalFieldValidationMixin


class BloodSugarMeasurementCreateRequest(BaseModel, ConditionalFieldValidationMixin):
    measure_type: BloodSugarMeasurementType
    blood_glucose: PositiveInt
    minutes_since_meal: PositiveInt | None = None
    has_exercised: bool
    exercise_type: ExerciseType | None = None
    exercise_minutes: PositiveInt | None = None
    minutes_since_exercise: PositiveInt | None = None
    has_medicated: bool
    medicine_name: str | None = None
    minutes_since_medication: PositiveInt | None = None
    memo: str | None = Field(
        None, min_length=0, max_length=1000, description="혈당 측정 시 참고메모(식사, 운동, 복약 관련)"
    )
    measured_at: datetime

    @model_validator(mode="after")
    def validate_conditional_fields(self) -> Self:
        # 측정 유형에 따른 유효성 검증 후 노말라이즈
        self._normalize_conditional_fields(
            field_names=("minutes_since_meal",),
            condition_field="measure_type",
            expected_value=BloodSugarMeasurementType.FASTING,
            invert_condition=True,
        )

        # 운동 여부에 따른 필드 유효성 검증 후 노말라이즈
        self._normalize_conditional_fields(
            field_names=("exercise_type", "exercise_minutes", "minutes_since_exercise"),
            condition_field="has_exercised",
            expected_value=True,
        )

        # 복약 여부에 따른 필드 유효성 검증 후 노말라이즈
        self._normalize_conditional_fields(
            field_names=("medicine_name", "minutes_since_medication"),
            condition_field="has_medicated",
            expected_value=True,
        )

        return self


class BloodSugarMeasurementListResponse(BaseSerializerModel):
    id: UUID
    measure_type: BloodSugarMeasurementType
    measured_at: datetime
    created_at: datetime

    @field_serializer("measure_type")
    def serialize_measure_type(self, value: BloodSugarMeasurementType) -> str:
        return value.label


class BloodSugarMeasurementResponse(BloodSugarMeasurementListResponse):
    blood_glucose: PositiveInt
    minutes_since_meal: PositiveInt | None = None
    has_exercised: bool
    exercise_type: ExerciseType | None = None
    exercise_minutes: PositiveInt | None = None
    minutes_since_exercise: PositiveInt | None = None
    has_medicated: bool
    medicine_name: str | None = None
    minutes_since_medication: PositiveInt | None = None
    memo: str | None = Field(
        None, min_length=0, max_length=500, description="혈당 측정 시 참고메모(식사, 운동, 복약 관련)"
    )

    @field_serializer("exercise_type")
    def serialize_exercise_type(self, value: ExerciseType | None) -> str | None:
        if value is None:
            return None
        return value.label


class BloodSugarMeasurementListFilter(BaseModel):
    start_date: Annotated[date | None, Field(ge=date(2000, 1, 1))] = None
    end_date: Annotated[date | None, Field(ge=date(2000, 1, 1))] = None

    @model_validator(mode="after")
    def validate_year_range(self) -> Self:
        if self.start_date and self.end_date is None:
            raise ValueError("end_date must be provided if start_date is provided")

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        return self
