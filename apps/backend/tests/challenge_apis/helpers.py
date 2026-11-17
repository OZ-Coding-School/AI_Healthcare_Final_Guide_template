"""
챌린지 추천 테스트 공통 도구입니다. 실제 Claude API를 호출하지 않도록 가짜 LLM 클라이언트를 씁니다.
"""

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from app.core.enums import DiseaseRiskLevel, DrinkingFrequency, HabitStatus, PredictionModelType
from app.core.llm import LLMResponse, LLMUnavailableError
from app.models.disease_prediction_models import DiseasePredictionResult
from app.models.health_profiles import MonthlyHealthSurvey


def factor(
    feature: str,
    shap_value: float,
    *,
    display_name: str | None = None,
    value: Any = 1.0,
    actionable: bool = True,
    reverse: bool = False,
) -> dict[str, Any]:
    return {
        "feature": feature,
        "display_name": display_name or feature,
        "value": value,
        "shap_value": shap_value,
        "direction": "increase" if shap_value >= 0 else "decrease",
        "actionable": actionable,
        "reverse_causation_suspected": reverse,
    }


def result(
    model_type: PredictionModelType,
    factors: list[dict[str, Any]],
    *,
    risk_level: DiseaseRiskLevel = DiseaseRiskLevel.MODERATE,
    risk_score: str = "23.46",
    out_of_training_range: list[str] | None = None,
) -> DiseasePredictionResult:
    """DB에 저장하지 않은 DiseasePredictionResult입니다 (프롬프트 단위 테스트용)."""
    return DiseasePredictionResult(
        model_type=model_type,
        risk_level=risk_level,
        risk_score=Decimal(risk_score),
        shap_results=factors,
        out_of_training_range=out_of_training_range or [],
    )


def survey(**overrides: Any) -> MonthlyHealthSurvey:
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
    return MonthlyHealthSurvey(title="테스트 설문", **data)


def challenge_item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "title": "매일 30분 빠르게 걷기",
        "description": "저녁 식사 후 30분 동안 빠르게 걷습니다. 숨이 약간 찰 정도의 속도를 유지합니다.",
        "challenge_type": "DAILY",
        "total_rounds": 21,
        "expected_effect": "꾸준한 유산소 활동은 허리둘레 관리와 혈당 조절에 도움이 됩니다.",
        "target_diseases": ["diabetes_risk"],
        "basis_features": ["허리둘레"],
    }
    item.update(overrides)
    return item


def challenges_json(items: Sequence[dict[str, Any]]) -> str:
    return json.dumps({"challenges": list(items)}, ensure_ascii=False)


def valid_response_text() -> str:
    """tests.disease_prediction_apis.helpers의 Worker 결과(허리둘레 actionable)에 맞는 정상 응답입니다."""
    return challenges_json(
        [
            challenge_item(),
            challenge_item(
                title="주 3회 저녁 식사량 줄이기",
                challenge_type="WEEKLY",
                total_rounds=4,
                target_diseases=["diabetes_risk", "hypertension_risk"],
            ),
            challenge_item(
                title="만보 걷기 20회 채우기",
                challenge_type="COUNT_BASED",
                total_rounds=20,
                target_diseases=["hypertension_risk"],
            ),
        ]
    )


class FakeLLMClient:
    """
    정해 둔 응답을 순서대로 돌려줍니다. 항목이 예외 인스턴스면 그 예외를 냅니다.
    마지막 응답은 이후 호출에도 계속 돌려줍니다.
    """

    def __init__(self, *responses: str | Exception, model_name: str = "claude-haiku-5-5") -> None:
        self.responses = list(responses) or [valid_response_text()]
        self.model_name = model_name
        self.calls: list[dict[str, Any]] = []

    async def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> LLMResponse:
        self.calls.append({"system": system, "user": user, "schema": schema})
        index = min(len(self.calls), len(self.responses)) - 1
        response = self.responses[index]
        if isinstance(response, Exception):
            raise response
        return LLMResponse(text=response, model=self.model_name, stop_reason="end_turn")


def unavailable() -> LLMUnavailableError:
    return LLMUnavailableError("LLM service error: status=529")
