from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from app.core.enums import UrineGlucoseStatus, UrineProteinStatus
from app.core.utils.date import normalize_date, normalize_datetime
from app.schemas.base import BaseSerializerModel
from app.schemas.health_profiles import Height, Weight

BMI = Annotated[Decimal, Field(ge=0, max_digits=3, decimal_places=1)]
WaistCircumference = Annotated[Decimal, Field(ge=0, max_digits=4, decimal_places=1)]
HbA1c = Annotated[Decimal, Field(ge=0, max_digits=3, decimal_places=1)]
Creatinine = Annotated[Decimal, Field(ge=0, max_digits=3, decimal_places=2)]


class AnnualHealthScreeningCreateRequest(BaseModel):
    height: Height
    weight: Weight
    bmi: BMI
    waist_circumference: WaistCircumference
    sbp: int
    dbp: int
    pulse: int
    fbs: int
    hba1c: HbA1c
    triglyceride: int
    ldl: int
    hdl: int
    total_cholesterol: int
    ast: int
    alt: int
    gamma_gtp: int
    egfr: int
    creatinine: Creatinine
    urine_protein: UrineProteinStatus
    urine_glucose: UrineGlucoseStatus
    family_history_diabetes: bool
    family_history_hypertension: bool
    screening_at: date
    is_fasting: bool


class AnnualHealthScreeningListResponse(BaseSerializerModel):
    id: UUID
    title: str
    screening_at: date
    created_at: datetime

    @field_serializer("screening_at", "created_at")
    def serialize_datetime_or_date(self, value: date | datetime) -> str:
        if isinstance(value, datetime):
            return normalize_datetime(value)
        return normalize_date(value)


class AnnualHealthScreeningResponse(AnnualHealthScreeningListResponse):
    height: Height
    weight: Weight
    bmi: BMI
    waist_circumference: WaistCircumference
    sbp: int
    dbp: int
    pulse: int
    fbs: int
    hba1c: HbA1c
    triglyceride: int
    ldl: int
    hdl: int
    total_cholesterol: int
    ast: int
    alt: int
    gamma_gtp: int
    egfr: int
    creatinine: Creatinine
    urine_protein: UrineProteinStatus
    urine_glucose: UrineGlucoseStatus
    family_history_diabetes: bool
    family_history_hypertension: bool

    @field_serializer("urine_protein", "urine_glucose")
    def _serialize_urine_related_fields(self, value: UrineProteinStatus | UrineGlucoseStatus) -> str:
        return value.description
