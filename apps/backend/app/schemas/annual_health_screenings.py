from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, PositiveInt, field_serializer

from app.core.enums import UrineGlucoseStatus, UrineProteinStatus
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
    sbp: PositiveInt
    dbp: PositiveInt
    pulse: PositiveInt
    fbs: PositiveInt
    hba1c: HbA1c
    triglyceride: PositiveInt
    ldl: PositiveInt
    hdl: PositiveInt
    total_cholesterol: PositiveInt
    ast: PositiveInt
    alt: PositiveInt
    gamma_gtp: PositiveInt
    egfr: PositiveInt
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


class AnnualHealthScreeningResponse(AnnualHealthScreeningListResponse):
    height: Height
    weight: Weight
    bmi: BMI
    waist_circumference: WaistCircumference
    sbp: PositiveInt
    dbp: PositiveInt
    pulse: PositiveInt
    fbs: PositiveInt
    hba1c: HbA1c
    triglyceride: PositiveInt
    ldl: PositiveInt
    hdl: PositiveInt
    total_cholesterol: PositiveInt
    ast: PositiveInt
    alt: PositiveInt
    gamma_gtp: PositiveInt
    egfr: PositiveInt
    creatinine: Creatinine
    urine_protein: UrineProteinStatus
    urine_glucose: UrineGlucoseStatus
    family_history_diabetes: bool
    family_history_hypertension: bool

    @field_serializer("urine_protein", "urine_glucose")
    def _serialize_urine_related_fields(self, value: UrineProteinStatus | UrineGlucoseStatus) -> str:
        return value.label
