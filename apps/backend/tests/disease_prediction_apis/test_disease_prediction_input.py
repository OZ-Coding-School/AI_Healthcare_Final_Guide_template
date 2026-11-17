from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.core.enums import (
    DrinkingFrequency,
    FamilyHistoryAnswer,
    Gender,
    HabitStatus,
    UrineGlucoseStatus,
    UrineProteinStatus,
)
from app.models.health_profiles import AnnualHealthScreening, HealthProfile, MonthlyHealthSurvey
from app.services.disease_prediction_input import PredictionInputError, build_prediction_payload

TODAY = date(2026, 11, 13)


def make_profile(**overrides: Any) -> HealthProfile:
    data: dict[str, Any] = {
        "gender": Gender.MALE,
        "birth_date": date(1970, 3, 15),
        "height": Decimal("172.5"),
        "weight": Decimal("78.0"),
        "has_diabetes": False,
        "has_hypertension": True,
    }
    data.update(overrides)
    return HealthProfile(**data)


def make_screening(**overrides: Any) -> AnnualHealthScreening:
    data: dict[str, Any] = {
        "height": Decimal("172.5"),
        "weight": Decimal("78.0"),
        "bmi": Decimal("26.2"),
        "waist_circumference": Decimal("92.0"),
        "sbp": 132,
        "dbp": 84,
        "fbs": 108,
        "hba1c": Decimal("5.9"),
        "triglyceride": 180,
        "ldl": 130,
        "hdl": 45,
        "total_cholesterol": 210,
        "ast": 28,
        "alt": 35,
        "creatinine": Decimal("0.95"),
        "urine_protein": UrineProteinStatus.TRACE,
        "urine_glucose": UrineGlucoseStatus.NEGATIVE,
        "family_history_diabetes": True,
        "family_history_hypertension": False,
        "diabetes_family_history_father": FamilyHistoryAnswer.YES,
        "diabetes_family_history_mother": FamilyHistoryAnswer.NO,
        "diabetes_family_history_siblings": FamilyHistoryAnswer.NO_SIBLINGS,
        "screening_at": date(2026, 5, 20),
        "is_fasting": True,
    }
    data.update(overrides)
    return AnnualHealthScreening(**data)


def make_survey(**overrides: Any) -> MonthlyHealthSurvey:
    data: dict[str, Any] = {
        "smoking_status": HabitStatus.CURRENT,
        "smoking_fr_per_day": 10,
        "drinking_status": HabitStatus.CURRENT,
        "drinking_frequency": DrinkingFrequency.WEEKLY_2_TO_3,
        "drinking_amount_per_session": 5,
        "systolic_bp": 130,
        "diastolic_bp": 85,
    }
    data.update(overrides)
    return MonthlyHealthSurvey(**data)


def error_fields(error: PredictionInputError) -> dict[str, str]:
    return {item.field: item.reason for item in error.errors}


def test_build_payload_maps_records_to_worker_input() -> None:
    payload = build_prediction_payload(make_profile(), make_screening(), make_survey(), TODAY)

    assert payload == {
        "gender": "M",
        "birth_date": "1970-03-15",
        "has_diabetes": False,
        "has_hypertension": True,
        "screening_date": "2026-05-20",
        "height": 172.5,
        "weight": 78.0,
        "waist_circumference": 92.0,
        "sbp": 132,
        "dbp": 84,
        "fbs": 108,
        "hba1c": 5.9,
        "triglyceride": 180,
        "total_cholesterol": 210,
        "hdl": 45,
        "ast": 28,
        "alt": 35,
        "creatinine": 0.95,
        "urine_protein": "±",
        "urine_glucose": "-",
        "diabetes_family_history": {"father": "YES", "mother": "NO", "siblings": "NO_SIBLINGS"},
        # 상세가 없고 병력 여부가 False이면 모두 NO
        "hypertension_family_history": {"father": "NO", "mother": "NO", "siblings": "NO"},
        "smoking_status": "CURRENT",
        "cigarettes_per_day": 10,
        "drinking_status": "CURRENT",
        "drinking_frequency": "WEEKLY_2_TO_3",
        "drinks_per_session": 5,
    }
    # 모델 입력에 없는 건강검진 항목은 보내지 않습니다 (Worker는 추가 필드를 거부).
    assert {"bmi", "ldl", "is_fasting"}.isdisjoint(payload)


def test_build_payload_keeps_empty_habit_amounts_for_non_current() -> None:
    survey = make_survey(
        smoking_status=HabitStatus.NEVER,
        smoking_fr_per_day=None,
        drinking_status=HabitStatus.FORMER,
        drinking_frequency=DrinkingFrequency.NOT_APPLICABLE,
        drinking_amount_per_session=None,
    )

    payload = build_prediction_payload(make_profile(), make_screening(), survey, TODAY)

    assert payload["cigarettes_per_day"] is None
    assert payload["drinks_per_session"] is None


def test_family_history_detail_is_required_when_history_is_true() -> None:
    screening = make_screening(
        diabetes_family_history_father=None,
        diabetes_family_history_mother=None,
        diabetes_family_history_siblings=None,
    )

    with pytest.raises(PredictionInputError) as caught:
        build_prediction_payload(make_profile(), screening, make_survey(), TODAY)

    assert "annual_health_screening.diabetes_family_history" in error_fields(caught.value)


def test_family_history_detail_must_be_complete() -> None:
    screening = make_screening(diabetes_family_history_siblings=None)

    with pytest.raises(PredictionInputError) as caught:
        build_prediction_payload(make_profile(), screening, make_survey(), TODAY)

    assert "annual_health_screening.diabetes_family_history" in error_fields(caught.value)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"sbp": 300}, "annual_health_screening.sbp"),
        ({"fbs": 30}, "annual_health_screening.fbs"),
        ({"creatinine": Decimal("25.00")}, "annual_health_screening.creatinine"),
        ({"dbp": 140, "sbp": 130}, "annual_health_screening.dbp"),
        ({"hdl": 220, "total_cholesterol": 210}, "annual_health_screening.hdl"),
        ({"screening_at": date(2026, 11, 14)}, "annual_health_screening.screening_at"),
    ],
)
def test_screening_rules_match_worker(overrides: dict[str, Any], field: str) -> None:
    with pytest.raises(PredictionInputError) as caught:
        build_prediction_payload(make_profile(), make_screening(**overrides), make_survey(), TODAY)

    assert field in error_fields(caught.value)


def test_minor_at_screening_is_rejected() -> None:
    profile = make_profile(birth_date=date(2008, 1, 1))

    with pytest.raises(PredictionInputError) as caught:
        build_prediction_payload(profile, make_screening(), make_survey(), TODAY)

    assert "health_profile.birth_date" in error_fields(caught.value)


def test_screening_today_is_allowed() -> None:
    payload = build_prediction_payload(make_profile(), make_screening(screening_at=TODAY), make_survey(), TODAY)

    assert payload["screening_date"] == TODAY.isoformat()


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        (
            {"drinking_status": HabitStatus.FORMER, "drinking_amount_per_session": None},
            "monthly_health_survey.drinking_frequency",
        ),
        (
            {"drinking_frequency": DrinkingFrequency.NOT_APPLICABLE},
            "monthly_health_survey.drinking_frequency",
        ),
        ({"smoking_fr_per_day": 150}, "monthly_health_survey.smoking_fr_per_day"),
        ({"drinking_amount_per_session": 60}, "monthly_health_survey.drinking_amount_per_session"),
    ],
)
def test_survey_rules_match_worker(overrides: dict[str, Any], field: str) -> None:
    with pytest.raises(PredictionInputError) as caught:
        build_prediction_payload(make_profile(), make_screening(), make_survey(**overrides), TODAY)

    assert field in error_fields(caught.value)


def test_errors_do_not_contain_input_values() -> None:
    with pytest.raises(PredictionInputError) as caught:
        build_prediction_payload(make_profile(), make_screening(sbp=299), make_survey(), TODAY)

    assert all("299" not in item.reason for item in caught.value.errors)
