"""
위험도 추론에 쓰는 서비스 입력 스키마입니다.

Backend의 건강 프로필·건강검진 기록 형식을 따르며, 혈액·소변 검사 항목은 모두 필수입니다.
혈액 지표가 없는 사용자는 학습 데이터에 없던 패턴이라 근거 있는 위험도를 낼 수 없기 때문입니다.
"""

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.components.knhanes_inference_errors import InferenceInputError, InputFieldError
from src.knhanes_inference_configs import SERVICE_INPUT_RANGES
from src.knhanes_merge_configs import KNHANES_ADULT_MIN_AGE


class ServiceGender(StrEnum):
    MALE = "M"
    FEMALE = "F"


class ServiceHabitStatus(StrEnum):
    NEVER = "NEVER"  # 해 본 적 없음
    FORMER = "FORMER"  # 과거에는 했으나 현재 하지 않음
    CURRENT = "CURRENT"  # 현재 함


class ServiceDrinkingFrequency(StrEnum):
    LESS_THAN_MONTHLY = "LESS_THAN_MONTHLY"
    MONTHLY = "MONTHLY"
    MONTHLY_2_TO_4 = "MONTHLY_2_TO_4"
    WEEKLY_2_TO_3 = "WEEKLY_2_TO_3"
    WEEKLY_4_OR_MORE = "WEEKLY_4_OR_MORE"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # 현재 마시지 않음


class ServiceUrinalysisStatus(StrEnum):
    NEGATIVE = "-"
    TRACE = "±"
    POSITIVE_1 = "1+"
    POSITIVE_2 = "2+"
    POSITIVE_3 = "3+"
    POSITIVE_4 = "4+"


class FamilyHistoryAnswer(StrEnum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"
    NO_SIBLINGS = "NO_SIBLINGS"  # 형제자매 항목에만 허용


def _ranged(name: str, optional: bool = False) -> Any:
    lower, upper = SERVICE_INPUT_RANGES[name]
    if optional:
        return Field(default=None, ge=lower, le=upper)
    return Field(ge=lower, le=upper)


def calculate_age(birth_date: date, on_date: date) -> int:
    """기준일의 만 나이를 계산합니다."""
    before_birthday = (on_date.month, on_date.day) < (birth_date.month, birth_date.day)
    return on_date.year - birth_date.year - int(before_birthday)


class FamilyHistoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    father: FamilyHistoryAnswer
    mother: FamilyHistoryAnswer
    siblings: FamilyHistoryAnswer

    @model_validator(mode="after")
    def _validate_parent_answers(self) -> "FamilyHistoryInput":
        for field_name in ["father", "mother"]:
            if getattr(self, field_name) == FamilyHistoryAnswer.NO_SIBLINGS:
                raise ValueError(f"{field_name} cannot be NO_SIBLINGS")
        return self


class ServiceHealthInput(BaseModel):
    """
    추론 입력 1건입니다. 키·체중·혈압 등은 건강검진 기록을, 나이는 검진일 기준 만 나이를 사용합니다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # 프로필
    gender: ServiceGender
    birth_date: date
    has_diabetes: bool
    has_hypertension: bool

    # 건강검진
    screening_date: date
    height: float = _ranged("height")
    weight: float = _ranged("weight")
    waist_circumference: float = _ranged("waist_circumference")
    sbp: int = _ranged("sbp")
    dbp: int = _ranged("dbp")
    fbs: int = _ranged("fbs")
    hba1c: float = _ranged("hba1c")
    triglyceride: int = _ranged("triglyceride")
    total_cholesterol: int = _ranged("total_cholesterol")
    hdl: int = _ranged("hdl")
    ast: int = _ranged("ast")
    alt: int = _ranged("alt")
    creatinine: float = _ranged("creatinine")
    urine_protein: ServiceUrinalysisStatus
    urine_glucose: ServiceUrinalysisStatus
    diabetes_family_history: FamilyHistoryInput
    hypertension_family_history: FamilyHistoryInput

    # 생활습관 (월간 건강 설문)
    smoking_status: ServiceHabitStatus
    cigarettes_per_day: int | None = _ranged("cigarettes_per_day", optional=True)
    drinking_status: ServiceHabitStatus
    drinking_frequency: ServiceDrinkingFrequency
    drinks_per_session: int | None = _ranged("drinks_per_session", optional=True)

    @property
    def age(self) -> int:
        return calculate_age(self.birth_date, self.screening_date)

    @model_validator(mode="after")
    def _validate_consistency(self) -> "ServiceHealthInput":
        if self.screening_date > date.today():
            raise ValueError("screening_date cannot be in the future")
        if self.birth_date >= self.screening_date:
            raise ValueError("birth_date must be before screening_date")
        if self.age < KNHANES_ADULT_MIN_AGE:
            raise ValueError(f"age at screening must be at least {KNHANES_ADULT_MIN_AGE}")
        if self.dbp >= self.sbp:
            raise ValueError("dbp must be lower than sbp")
        if self.hdl > self.total_cholesterol:
            raise ValueError("hdl cannot exceed total_cholesterol")
        self._validate_smoking()
        self._validate_drinking()
        return self

    def _validate_smoking(self) -> None:
        if self.smoking_status != ServiceHabitStatus.CURRENT and self.cigarettes_per_day:
            raise ValueError("cigarettes_per_day must be empty or 0 unless smoking_status is CURRENT")

    def _validate_drinking(self) -> None:
        not_drinking = self.drinking_status != ServiceHabitStatus.CURRENT
        if not_drinking and self.drinking_frequency != ServiceDrinkingFrequency.NOT_APPLICABLE:
            raise ValueError("drinking_frequency must be NOT_APPLICABLE unless drinking_status is CURRENT")
        if not_drinking and self.drinks_per_session:
            raise ValueError("drinks_per_session must be empty or 0 unless drinking_status is CURRENT")
        if not not_drinking and self.drinking_frequency == ServiceDrinkingFrequency.NOT_APPLICABLE:
            raise ValueError("drinking_frequency is required when drinking_status is CURRENT")
        if not not_drinking and self.drinks_per_session == 0:
            raise ValueError("drinks_per_session must be at least 1 when drinking_status is CURRENT")


def parse_service_input(payload: ServiceHealthInput | Mapping[str, Any]) -> ServiceHealthInput:
    """
    입력을 검증해 ServiceHealthInput으로 반환합니다.
    오류에는 필드명과 사유만 담고 입력값은 담지 않습니다.
    """
    if isinstance(payload, ServiceHealthInput):
        return payload
    if not isinstance(payload, Mapping):
        raise InferenceInputError([InputFieldError(field="__root__", reason="input must be an object")])
    try:
        return ServiceHealthInput.model_validate(dict(payload))
    except ValidationError as error:
        field_errors = [
            InputFieldError(field=".".join(str(part) for part in item["loc"]) or "__root__", reason=item["msg"])
            for item in error.errors(include_input=False, include_url=False)
        ]
        raise InferenceInputError(field_errors) from None
