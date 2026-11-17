"""
질병 위험도 예측 테스트 공통 도구입니다.

Worker 결과는 AI 쪽 PredictionResultMessage.to_stream_fields()와 같은 형식으로 만듭니다.
계약을 바꾸면 이 예시도 AI 쪽 테스트와 함께 수정합니다.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.enums import DrinkingFrequency, HabitStatus
from app.models.health_profiles import MonthlyHealthSurvey


def disease_result(model_type: str, probability: float, risk_level: str = "MODERATE") -> dict[str, Any]:
    """AI DiseaseRiskPrediction.to_dict()와 같은 형식입니다."""
    return {
        "model_type": model_type,
        "model_version": f"{model_type}:train_a_tg:LightGBM:0123456789ab",
        "risk_probability": probability,
        "risk_level": risk_level,
        "risk_thresholds": {"moderate": 0.1234567, "high": 0.4567891},
        "shap_output_space": "probability",
        "shap_base_value": 0.1523456789,
        "risk_factors": [
            {
                "feature": "허리둘레",
                "display_name": "허리둘레",
                "value": 92.0,
                "shap_value": 0.0812,
                "direction": "increase",
                "actionable": True,
                "reverse_causation_suspected": False,
            },
            {
                "feature": "나이",
                "display_name": "나이",
                "value": 54,
                "shap_value": 0.0512,
                "direction": "increase",
                "actionable": False,
                "reverse_causation_suspected": False,
            },
        ],
        "out_of_training_range": [],
    }


def processing_result_fields(task_id: str | UUID) -> dict[str, str]:
    """AI processing_stream_fields()와 같은 형식의 처리 시작 항목입니다."""
    return {
        "task_id": str(task_id),
        "schema_version": "2",
        "status": "processing",
        "started_at": datetime.now(UTC).isoformat(),
    }


def succeeded_result_fields(task_id: str | UUID) -> dict[str, str]:
    result = {
        "diabetes_risk": disease_result("diabetes_risk", 0.2345678),
        "hypertension_risk": disease_result("hypertension_risk", 0.6789012, risk_level="HIGH"),
    }
    return {
        "task_id": str(task_id),
        "schema_version": "2",
        "status": "succeeded",
        "completed_at": datetime.now(UTC).isoformat(),
        "result": json.dumps(result, ensure_ascii=False),
    }


def failed_result_fields(
    task_id: str | UUID, error_code: str, errors: list[dict[str, str]] | None = None
) -> dict[str, str]:
    return {
        "task_id": str(task_id),
        "schema_version": "2",
        "status": "failed",
        "completed_at": datetime.now(UTC).isoformat(),
        "error_code": error_code,
        "errors": json.dumps(errors or [], ensure_ascii=False),
    }


def profile_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "gender": "M",
        "birth_date": "1970-03-15",
        "height": 172.5,
        "weight": 78.0,
        "has_diabetes": False,
        "has_hypertension": False,
    }
    data.update(overrides)
    return data


def screening_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "height": 172.5,
        "weight": 78.0,
        "bmi": 26.2,
        "waist_circumference": 92.0,
        "sbp": 132,
        "dbp": 84,
        "fbs": 108,
        "hba1c": 5.9,
        "triglyceride": 180,
        "ldl": 130,
        "hdl": 45,
        "total_cholesterol": 210,
        "ast": 28,
        "alt": 35,
        "creatinine": 0.95,
        "urine_protein": "-",
        "urine_glucose": "-",
        "family_history_diabetes": True,
        "family_history_hypertension": False,
        "diabetes_family_history_father": "YES",
        "diabetes_family_history_mother": "NO",
        "diabetes_family_history_siblings": "NO_SIBLINGS",
        "screening_at": "2026-05-20",
        "is_fasting": True,
    }
    data.update(overrides)
    return data


async def create_survey(user_id: UUID, **overrides: Any) -> MonthlyHealthSurvey:
    """월간 설문은 같은 달에 1건만 API로 만들 수 있어 ORM으로 직접 만듭니다."""
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
    return await MonthlyHealthSurvey.create(user_id=user_id, title="테스트 설문", **data)
