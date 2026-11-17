"""
건강 프로필·건강검진·월간 설문을 AI Worker 예측 입력(ServiceHealthInput)으로 조합하고 미리 검증합니다.

검증 규칙은 AI 쪽(apps/ai/src/components/knhanes_service_input.py, SERVICE_INPUT_RANGES)과 같아야 합니다.
요청을 발행하기 전에 여기서 걸러야 사용자가 어떤 기록의 어떤 항목을 고칠지 바로 알 수 있습니다.
Worker의 INVALID_INPUT은 이 검증을 통과한 뒤의 안전장치입니다.

오류에는 필드명과 사유만 담고 입력값은 담지 않습니다.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.enums import DrinkingFrequency, FamilyHistoryAnswer, HabitStatus
from app.models.health_profiles import AnnualHealthScreening, HealthProfile, MonthlyHealthSurvey

PROFILE = "health_profile"
SCREENING = "annual_health_screening"
SURVEY = "monthly_health_survey"

# KNHANES 학습 대상과 같은 성인 기준 (검진일 기준 만 나이)
ADULT_MIN_AGE = 19

# 예측 입력 허용 범위: AI의 SERVICE_INPUT_RANGES와 같은 값 (키: 예측 입력 필드명)
PREDICTION_INPUT_RANGES: dict[str, tuple[float, float]] = {
    "height": (100.0, 230.0),  # cm
    "weight": (25.0, 250.0),  # kg
    "waist_circumference": (40.0, 200.0),  # cm
    "sbp": (60, 260),  # mmHg
    "dbp": (30, 160),  # mmHg
    "fbs": (40, 600),  # mg/dL
    "hba1c": (3.0, 20.0),  # %
    "triglyceride": (10, 3000),  # mg/dL
    "total_cholesterol": (50, 600),  # mg/dL
    "hdl": (5, 200),  # mg/dL
    "ast": (1, 2000),  # IU/L
    "alt": (1, 2000),  # IU/L
    "creatinine": (0.1, 20.0),  # mg/dL
    "cigarettes_per_day": (0, 100),  # 개비
    "drinks_per_session": (0, 50),  # 잔
}

# 예측 입력 필드 → 사용자가 고칠 원천 기록의 필드 (오류 위치 표시용)
SOURCE_FIELD_MAP: dict[str, str] = {
    "gender": f"{PROFILE}.gender",
    "birth_date": f"{PROFILE}.birth_date",
    "has_diabetes": f"{PROFILE}.has_diabetes",
    "has_hypertension": f"{PROFILE}.has_hypertension",
    "screening_date": f"{SCREENING}.screening_at",
    **{
        name: f"{SCREENING}.{name}"
        for name in [
            "height",
            "weight",
            "waist_circumference",
            "sbp",
            "dbp",
            "fbs",
            "hba1c",
            "triglyceride",
            "total_cholesterol",
            "hdl",
            "ast",
            "alt",
            "creatinine",
        ]
    },
    "smoking_status": f"{SURVEY}.smoking_status",
    "cigarettes_per_day": f"{SURVEY}.smoking_fr_per_day",
    "drinking_status": f"{SURVEY}.drinking_status",
    "drinking_frequency": f"{SURVEY}.drinking_frequency",
    "drinks_per_session": f"{SURVEY}.drinking_amount_per_session",
}

# 예측 입력의 가족력 필드 → (건강검진 상세 필드 접두사, 병력 여부 필드)
FAMILY_HISTORY_SOURCE_MAP: dict[str, tuple[str, str]] = {
    "diabetes_family_history": ("diabetes_family_history", "family_history_diabetes"),
    "hypertension_family_history": ("hypertension_family_history", "family_history_hypertension"),
}
FAMILY_HISTORY_RELATIONS = ("father", "mother", "siblings")


@dataclass(frozen=True)
class PredictionInputFieldError:
    field: str
    reason: str


class PredictionInputError(Exception):
    def __init__(self, errors: list[PredictionInputFieldError]) -> None:
        super().__init__(f"{len(errors)} invalid prediction input field(s)")
        self.errors = errors


def calculate_age(birth_date: date, on_date: date) -> int:
    """기준일의 만 나이를 계산합니다."""
    before_birthday = (on_date.month, on_date.day) < (birth_date.month, birth_date.day)
    return on_date.year - birth_date.year - int(before_birthday)


def build_prediction_payload(
    profile: HealthProfile,
    screening: AnnualHealthScreening,
    survey: MonthlyHealthSurvey,
    today: date,
) -> dict[str, Any]:
    """
    세 기록을 예측 입력 1건으로 조합합니다.

    :param today: 미래 검진일 판단 기준일 (서비스 시간대 기준 오늘)
    :raises PredictionInputError: 입력이 AI 검증 규칙을 통과하지 못할 때
    """
    errors: list[PredictionInputFieldError] = []

    payload: dict[str, Any] = {
        "gender": profile.gender.value,
        "birth_date": profile.birth_date.isoformat(),
        "has_diabetes": profile.has_diabetes,
        "has_hypertension": profile.has_hypertension,
        "screening_date": screening.screening_at.isoformat(),
        "height": _to_float(screening.height),
        "weight": _to_float(screening.weight),
        "waist_circumference": _to_float(screening.waist_circumference),
        "sbp": screening.sbp,
        "dbp": screening.dbp,
        "fbs": screening.fbs,
        "hba1c": _to_float(screening.hba1c),
        "triglyceride": screening.triglyceride,
        "total_cholesterol": screening.total_cholesterol,
        "hdl": screening.hdl,
        "ast": screening.ast,
        "alt": screening.alt,
        "creatinine": _to_float(screening.creatinine),
        "urine_protein": screening.urine_protein.value,
        "urine_glucose": screening.urine_glucose.value,
        "smoking_status": survey.smoking_status.value,
        "cigarettes_per_day": survey.smoking_fr_per_day,
        "drinking_status": survey.drinking_status.value,
        "drinking_frequency": survey.drinking_frequency.value,
        "drinks_per_session": survey.drinking_amount_per_session,
    }
    for input_field, (detail_prefix, has_history_field) in FAMILY_HISTORY_SOURCE_MAP.items():
        payload[input_field] = _family_history(screening, detail_prefix, has_history_field, errors)

    _validate_ranges(payload, errors)
    _validate_screening(profile, screening, today, errors)
    _validate_habits(survey, errors)

    if errors:
        raise PredictionInputError(errors)
    return payload


def _to_float(value: Decimal | float) -> float:
    return float(value)


def _error(errors: list[PredictionInputFieldError], input_field: str, reason: str) -> None:
    errors.append(PredictionInputFieldError(field=SOURCE_FIELD_MAP.get(input_field, input_field), reason=reason))


def _family_history(
    screening: AnnualHealthScreening,
    detail_prefix: str,
    has_history_field: str,
    errors: list[PredictionInputFieldError],
) -> dict[str, str] | None:
    """
    가족력 상세를 AI 입력 형식({father, mother, siblings})으로 바꿉니다.
    상세가 없고 병력 여부가 False이면 모두 NO로 봅니다. True이면 누가 해당하는지 알 수 없어 상세 입력을 요구합니다.
    """
    answers = {relation: getattr(screening, f"{detail_prefix}_{relation}") for relation in FAMILY_HISTORY_RELATIONS}
    if all(answer is not None for answer in answers.values()):
        return {relation: FamilyHistoryAnswer(answer).value for relation, answer in answers.items()}
    if any(answer is not None for answer in answers.values()):
        errors.append(
            PredictionInputFieldError(
                field=f"{SCREENING}.{detail_prefix}", reason="father, mother and siblings must be provided together"
            )
        )
        return None
    if getattr(screening, has_history_field):
        errors.append(
            PredictionInputFieldError(
                field=f"{SCREENING}.{detail_prefix}",
                reason=f"father, mother and siblings are required when {has_history_field} is true",
            )
        )
        return None
    return {relation: FamilyHistoryAnswer.NO.value for relation in FAMILY_HISTORY_RELATIONS}


def _validate_ranges(payload: dict[str, Any], errors: list[PredictionInputFieldError]) -> None:
    for name, (lower, upper) in PREDICTION_INPUT_RANGES.items():
        value = payload[name]
        if value is None:
            continue
        if not lower <= value <= upper:
            _error(errors, name, f"must be between {lower:g} and {upper:g}")


def _validate_screening(
    profile: HealthProfile,
    screening: AnnualHealthScreening,
    today: date,
    errors: list[PredictionInputFieldError],
) -> None:
    if screening.screening_at > today:
        _error(errors, "screening_date", "cannot be in the future")
    if profile.birth_date >= screening.screening_at:
        _error(errors, "birth_date", "must be before the screening date")
    elif calculate_age(profile.birth_date, screening.screening_at) < ADULT_MIN_AGE:
        _error(errors, "birth_date", f"age at screening must be at least {ADULT_MIN_AGE}")
    if screening.dbp >= screening.sbp:
        _error(errors, "dbp", "must be lower than sbp")
    if screening.hdl > screening.total_cholesterol:
        _error(errors, "hdl", "cannot exceed total_cholesterol")


def _validate_habits(survey: MonthlyHealthSurvey, errors: list[PredictionInputFieldError]) -> None:
    if survey.smoking_status != HabitStatus.CURRENT and survey.smoking_fr_per_day:
        _error(errors, "cigarettes_per_day", "must be empty unless smoking_status is CURRENT")

    drinking = survey.drinking_status == HabitStatus.CURRENT
    not_applicable = survey.drinking_frequency == DrinkingFrequency.NOT_APPLICABLE
    if not drinking and not not_applicable:
        _error(errors, "drinking_frequency", "must be NOT_APPLICABLE unless drinking_status is CURRENT")
    if not drinking and survey.drinking_amount_per_session:
        _error(errors, "drinks_per_session", "must be empty unless drinking_status is CURRENT")
    if drinking and not_applicable:
        _error(errors, "drinking_frequency", "is required when drinking_status is CURRENT")
    if drinking and survey.drinking_amount_per_session == 0:
        _error(errors, "drinks_per_session", "must be at least 1 when drinking_status is CURRENT")
