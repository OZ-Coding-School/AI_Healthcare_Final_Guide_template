"""AI Worker 테스트 공통 도구입니다. 파일명이 test_로 시작하지 않아 pytest가 수집하지 않습니다."""

import json
from datetime import UTC, datetime
from typing import Any

from src.components.knhanes_service_input import parse_service_input
from src.enums import ModelType
from src.pipelines.inference_pipeline import DiseaseRiskPrediction
from tests.test_knhanes_input_adapter import valid_payload

TASK_ID = "0195f3a2-7c1d-7e4b-9a10-1234567890ab"
FIXED_NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def make_prediction(model_type: ModelType, probability: float = 0.2) -> DiseaseRiskPrediction:
    return DiseaseRiskPrediction(
        model_type=str(model_type),
        model_version="test",
        risk_probability=probability,
        risk_level="MODERATE",
        risk_thresholds={"moderate": 0.1, "high": 0.3},
        shap_output_space="log_odds",
        shap_base_value=-1.5,
    )


class FakePredictor:
    """
    KnhanesRiskPredictor 대신 쓰는 가짜 Predictor입니다.

    - 실제와 같이 parse_service_input으로 입력을 검증하므로 잘못된 입력은 InferenceInputError가 납니다.
    - error를 주면 예외를 던집니다. fail_times를 주면 그 횟수만 실패하고 이후 성공합니다.
    """

    def __init__(self, error: Exception | None = None, fail_times: int = 0, probability: float = 0.2) -> None:
        self.error = error
        self.fail_times = fail_times
        self.probability = probability
        self.calls = 0

    def predict_all(self, payload: Any) -> dict[ModelType, DiseaseRiskPrediction]:
        self.calls += 1
        if self.error is not None and (self.fail_times == 0 or self.calls <= self.fail_times):
            raise self.error
        parse_service_input(payload)
        return {model_type: make_prediction(model_type, self.probability) for model_type in ModelType}


def make_request(**overrides: Any) -> dict[str, str]:
    """정상 요청 메시지를 만들고, 바꿀 필드만 덮어씁니다."""
    fields = {
        "task_id": TASK_ID,
        "schema_version": "1",
        "payload": json.dumps(valid_payload()),
        "requested_at": FIXED_NOW.isoformat(),
    }
    fields.update(overrides)
    return fields
