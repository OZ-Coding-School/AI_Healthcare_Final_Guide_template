"""
예측 요청 메시지 1건을 처리해 결과 메시지를 만듭니다. Redis는 다루지 않습니다.

- 계약 위반·입력 오류·모델 오류는 다시 시도해도 결과가 같으므로 바로 실패 결과로 확정합니다.
- 그 밖의 예외는 호출자(PredictionStreamConsumer)로 올려 재시도 대상이 되게 합니다.
- 결과와 로그에 입력값을 남기지 않습니다. 오류에는 필드명과 사유만 담습니다.
"""

import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from src.components.knhanes_inference_errors import InferenceInputError, ModelArtifactError
from src.pipelines.inference_pipeline import DiseaseRiskPrediction
from tasks.prediction_stream_contract import (
    FieldErrorDetail,
    PredictionErrorCode,
    PredictionRequestMessage,
    PredictionResultMessage,
    PredictionTaskStatus,
    is_valid_task_id,
)

logger = logging.getLogger(__name__)


class RiskPredictor(Protocol):
    """KnhanesRiskPredictor의 Worker 사용 범위입니다. 테스트에서 가짜 Predictor로 바꿀 수 있습니다."""

    def predict_all(self, payload: Any) -> Mapping[Any, DiseaseRiskPrediction]: ...


@dataclass(frozen=True)
class TaskOutcome:
    """
    task_id가 None이면 결과를 보낼 키를 만들 수 없는 메시지입니다.
    호출자는 결과 발행 없이 실패 기록만 남기고 ACK합니다.
    """

    task_id: str | None
    result: PredictionResultMessage | None


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PredictionTask:
    def __init__(self, predictor: RiskPredictor, clock: Callable[[], datetime] = _utc_now) -> None:
        self._predictor = predictor
        self._clock = clock

    def handle(self, fields: Mapping[str, str]) -> TaskOutcome:
        task_id = fields.get("task_id")
        if not is_valid_task_id(task_id):
            return TaskOutcome(task_id=None, result=None)
        assert isinstance(task_id, str)

        try:
            message = PredictionRequestMessage.model_validate(dict(fields))
        except ValidationError as error:
            return self._failed(task_id, PredictionErrorCode.INVALID_MESSAGE, _validation_errors(error))

        try:
            payload = json.loads(message.payload)
        except json.JSONDecodeError:
            return self._failed(
                task_id,
                PredictionErrorCode.INVALID_MESSAGE,
                [FieldErrorDetail(field="payload", reason="payload must be a JSON object")],
            )

        try:
            predictions = self._predictor.predict_all(payload)
        except InferenceInputError as error:
            errors = [FieldErrorDetail(field=item.field, reason=item.reason) for item in error.errors]
            return self._failed(task_id, PredictionErrorCode.INVALID_INPUT, errors)
        except ModelArtifactError as error:
            # 메시지에는 모델 종류와 사유만 있고 입력값은 없습니다. 사용자 응답에는 내보내지 않습니다.
            logger.error("Task %s model error: %s", task_id, error)
            return self._failed(task_id, PredictionErrorCode.MODEL_ERROR, [])

        result = {str(model_type): prediction.to_dict() for model_type, prediction in predictions.items()}
        try:
            json.dumps(result, allow_nan=False)
        except (TypeError, ValueError):
            logger.error("Task %s produced a result that cannot be serialized to JSON", task_id)
            return self._failed(task_id, PredictionErrorCode.MODEL_ERROR, [])

        return TaskOutcome(
            task_id=task_id,
            result=PredictionResultMessage(
                task_id=task_id,
                status=PredictionTaskStatus.SUCCEEDED,
                result=result,
                completed_at=self._clock(),
            ),
        )

    def failed_after_retries(self, task_id: str | None) -> TaskOutcome:
        """재시도 한도를 넘긴 메시지를 실패로 확정합니다."""
        if not is_valid_task_id(task_id):
            return TaskOutcome(task_id=None, result=None)
        assert isinstance(task_id, str)
        return self._failed(task_id, PredictionErrorCode.INTERNAL_ERROR, [])

    def _failed(self, task_id: str, error_code: PredictionErrorCode, errors: list[FieldErrorDetail]) -> TaskOutcome:
        return TaskOutcome(
            task_id=task_id,
            result=PredictionResultMessage(
                task_id=task_id,
                status=PredictionTaskStatus.FAILED,
                error_code=error_code,
                errors=errors,
                completed_at=self._clock(),
            ),
        )


def _validation_errors(error: ValidationError) -> list[FieldErrorDetail]:
    return [
        FieldErrorDetail(field=".".join(str(part) for part in item["loc"]) or "__root__", reason=item["msg"])
        for item in error.errors(include_input=False, include_url=False)
    ]
