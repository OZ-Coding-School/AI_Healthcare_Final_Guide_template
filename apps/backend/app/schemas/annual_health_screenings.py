from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, Field, PositiveInt, field_serializer, model_validator

from app.core.enums import FamilyHistoryAnswer, UrineGlucoseStatus, UrineProteinStatus
from app.schemas.base import BaseSerializerModel
from app.schemas.health_profiles import Height, Weight

BMI = Annotated[Decimal, Field(ge=0, max_digits=3, decimal_places=1)]
WaistCircumference = Annotated[Decimal, Field(ge=0, max_digits=4, decimal_places=1)]
HbA1c = Annotated[Decimal, Field(ge=0, max_digits=3, decimal_places=1)]
Creatinine = Annotated[Decimal, Field(ge=0, max_digits=3, decimal_places=2)]


FAMILY_HISTORY_RELATIONS = ("father", "mother", "siblings")
FAMILY_HISTORY_DISEASES = {
    # 상세 필드 접두사: 기존 병력 여부(bool) 필드
    "diabetes_family_history": "family_history_diabetes",
    "hypertension_family_history": "family_history_hypertension",
}


class FamilyHistoryDetailMixin(BaseModel):
    """
    가족력 상세(아버지·어머니·형제자매)입니다. 위험도 예측 입력에 필요합니다.
    기존 병력 여부(bool) 필드와 호환되도록 선택 입력이며, 입력할 때는 질환별로 세 항목을 모두 입력합니다.
    """

    diabetes_family_history_father: FamilyHistoryAnswer | None = None
    diabetes_family_history_mother: FamilyHistoryAnswer | None = None
    diabetes_family_history_siblings: FamilyHistoryAnswer | None = None
    hypertension_family_history_father: FamilyHistoryAnswer | None = None
    hypertension_family_history_mother: FamilyHistoryAnswer | None = None
    hypertension_family_history_siblings: FamilyHistoryAnswer | None = None


class AnnualHealthScreeningCreateRequest(FamilyHistoryDetailMixin):
    height: Height
    weight: Weight
    bmi: BMI
    waist_circumference: WaistCircumference
    sbp: PositiveInt
    dbp: PositiveInt
    fbs: PositiveInt
    hba1c: HbA1c
    triglyceride: PositiveInt
    ldl: PositiveInt
    hdl: PositiveInt
    total_cholesterol: PositiveInt
    ast: PositiveInt
    alt: PositiveInt
    creatinine: Creatinine
    urine_protein: UrineProteinStatus
    urine_glucose: UrineGlucoseStatus
    family_history_diabetes: bool
    family_history_hypertension: bool
    screening_at: date
    is_fasting: bool

    @model_validator(mode="after")
    def validate_family_history_detail(self) -> Self:
        for prefix, has_history_field in FAMILY_HISTORY_DISEASES.items():
            answers = {relation: getattr(self, f"{prefix}_{relation}") for relation in FAMILY_HISTORY_RELATIONS}
            provided = [answer for answer in answers.values() if answer is not None]
            if not provided:
                continue
            if len(provided) != len(FAMILY_HISTORY_RELATIONS):
                raise ValueError(f"{prefix}_father, _mother, _siblings must be provided together")
            for relation in ("father", "mother"):
                if answers[relation] == FamilyHistoryAnswer.NO_SIBLINGS:
                    raise ValueError(f"{prefix}_{relation} cannot be NO_SIBLINGS")
            has_yes = FamilyHistoryAnswer.YES in provided
            if getattr(self, has_history_field) != has_yes:
                raise ValueError(f"{has_history_field} must match {prefix} detail (true only when any answer is YES)")
        return self


class AnnualHealthScreeningListResponse(BaseSerializerModel):
    id: UUID
    title: str
    screening_at: date
    created_at: datetime


class AnnualHealthScreeningResponse(AnnualHealthScreeningListResponse, FamilyHistoryDetailMixin):
    height: Height
    weight: Weight
    bmi: BMI
    waist_circumference: WaistCircumference
    sbp: PositiveInt
    dbp: PositiveInt
    fbs: PositiveInt
    hba1c: HbA1c
    triglyceride: PositiveInt
    ldl: PositiveInt
    hdl: PositiveInt
    total_cholesterol: PositiveInt
    ast: PositiveInt
    alt: PositiveInt
    creatinine: Creatinine
    urine_protein: UrineProteinStatus
    urine_glucose: UrineGlucoseStatus
    family_history_diabetes: bool
    family_history_hypertension: bool

    @field_serializer("urine_protein", "urine_glucose")
    def _serialize_urine_related_fields(self, value: UrineProteinStatus | UrineGlucoseStatus) -> str:
        return value.label
