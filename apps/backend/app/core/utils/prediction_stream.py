"""
AI Worker와 주고받는 질병 위험도 예측 Redis Stream 계약입니다.

AI 쪽 정의(apps/ai/tasks/prediction_stream_contract.py)와 Stream 이름·필드·값이 같아야 합니다.
두 앱은 패키지를 공유하지 않으므로, 계약을 바꾸면 PREDICTION_SCHEMA_VERSION을 올리고 양쪽을 함께 수정합니다.

요청 (Backend → Worker)
    Stream: ai:prediction:requests
    필드: task_id, schema_version, payload(JSON), requested_at(ISO 8601)

결과 (Worker → Backend)
    Stream: ai:prediction:result:{task_id} (요청별 1개, 마지막 항목 1건, TTL 1시간)
    처리 시작: task_id, schema_version, status=processing, started_at
    성공: task_id, schema_version, status=succeeded, result(JSON), completed_at
    실패: task_id, schema_version, status=failed, error_code, errors(JSON), completed_at
처리 시작 항목은 Worker가 요청을 가져갈 때 남기며, 최종 결과(성공·실패)가 같은 키에서 이를 대체합니다.
"""

import json
import re
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.enums import DiseaseRiskLevel, PredictionModelType

# 2: 처리 시작(status=processing) 항목 추가
PREDICTION_SCHEMA_VERSION = "2"

PREDICTION_REQUEST_STREAM = "ai:prediction:requests"
PREDICTION_RESULT_STREAM_PREFIX = "ai:prediction:result:"

# task_id는 결과 Stream 키에 들어가므로 키 구분자(:)나 패턴 문자(*)를 허용하지 않습니다.
TASK_ID_PATTERN = r"^[A-Za-z0-9-]{1,64}$"
_TASK_ID_REGEX = re.compile(TASK_ID_PATTERN)

# Worker가 이보다 긴 payload는 잘못된 메시지로 거부합니다.
MAX_PAYLOAD_BYTES = 16_384

# Worker가 결과를 보관하는 시간. 이 시간이 지나도 PENDING이면 결과를 받을 수 없습니다.
RESULT_TTL_SECONDS = 3_600

# 요청 Stream 보관 길이 (근사값). Worker가 처리한 요청도 남아 있으므로 무한히 쌓이지 않게 합니다.
REQUEST_STREAM_MAXLEN = 10_000


class PredictionTaskStatus(StrEnum):
    PROCESSING = "processing"  # Worker가 처리 중 (최종 결과 아님)
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PredictionErrorCode(StrEnum):
    # AI Worker가 보내는 코드
    INVALID_MESSAGE = "INVALID_MESSAGE"  # 계약 위반 (Backend 버그)
    INVALID_INPUT = "INVALID_INPUT"  # 사용자 입력 오류
    MODEL_ERROR = "MODEL_ERROR"  # 모델 번들 오류·불일치
    INTERNAL_ERROR = "INTERNAL_ERROR"  # 재시도 한도 초과
    # Backend에서만 쓰는 코드
    PUBLISH_FAILED = "PUBLISH_FAILED"  # 요청 발행 실패 (Redis 장애)
    RESULT_EXPIRED = "RESULT_EXPIRED"  # 결과 보관 시간 초과
    INVALID_RESULT = "INVALID_RESULT"  # Worker 결과가 계약과 다름


class PredictionResultParseError(ValueError):
    """Worker 결과가 계약과 다를 때 발생합니다. 메시지에 입력값은 담지 않습니다."""


def is_valid_task_id(task_id: Any) -> bool:
    return isinstance(task_id, str) and _TASK_ID_REGEX.fullmatch(task_id) is not None


def result_stream_key(task_id: str) -> str:
    if not is_valid_task_id(task_id):
        raise ValueError("task_id has an invalid format")
    return f"{PREDICTION_RESULT_STREAM_PREFIX}{task_id}"


def build_request_fields(task_id: str, payload: Mapping[str, Any], requested_at: datetime) -> dict[str, str]:
    """요청 Stream에 넣을 문자열 필드를 만듭니다. Redis Stream 필드는 문자열만 담을 수 있습니다."""
    if not is_valid_task_id(task_id):
        raise ValueError("task_id has an invalid format")
    payload_json = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(payload_json) > MAX_PAYLOAD_BYTES:
        raise ValueError("payload is too large")
    return {
        "task_id": task_id,
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "payload": payload_json,
        "requested_at": requested_at.isoformat(),
    }


class _ResultBaseModel(BaseModel):
    # 추가 필드는 무시해 Worker 쪽 응답 확장에 대비하고, NaN·Infinity는 거부합니다.
    model_config = ConfigDict(extra="ignore", frozen=True, allow_inf_nan=False)


class RiskFactorMessage(_ResultBaseModel):
    feature: str
    display_name: str
    value: Any = None
    shap_value: float
    direction: str
    actionable: bool
    reverse_causation_suspected: bool


class RiskThresholdsMessage(_ResultBaseModel):
    moderate: float = Field(ge=0, le=1)
    high: float = Field(ge=0, le=1)


class DiseaseRiskMessage(_ResultBaseModel):
    model_type: PredictionModelType
    model_version: str = Field(min_length=1, max_length=100)
    risk_probability: float = Field(ge=0, le=1)
    risk_level: DiseaseRiskLevel
    risk_thresholds: RiskThresholdsMessage
    shap_output_space: str = Field(max_length=20)
    shap_base_value: float
    risk_factors: list[RiskFactorMessage] = Field(default_factory=list)
    out_of_training_range: list[str] = Field(default_factory=list)


class FieldErrorMessage(_ResultBaseModel):
    field: str
    reason: str


class PredictionProcessingMessage(_ResultBaseModel):
    """처리 시작 항목입니다. 최종 결과가 아니므로 Task 상태만 바꿉니다."""

    task_id: str = Field(pattern=TASK_ID_PATTERN)
    schema_version: Literal["2"]
    status: Literal[PredictionTaskStatus.PROCESSING]
    started_at: datetime


class PredictionResultMessage(_ResultBaseModel):
    task_id: str = Field(pattern=TASK_ID_PATTERN)
    schema_version: Literal["2"]
    status: Literal[PredictionTaskStatus.SUCCEEDED, PredictionTaskStatus.FAILED]
    result: dict[PredictionModelType, DiseaseRiskMessage] | None = None
    error_code: PredictionErrorCode | None = None
    errors: list[FieldErrorMessage] = Field(default_factory=list)
    completed_at: datetime

    @model_validator(mode="after")
    def _check_status_fields(self) -> Self:
        if self.status is PredictionTaskStatus.SUCCEEDED:
            if self.result is None or self.error_code is not None:
                raise ValueError("succeeded result requires result and no error_code")
            if set(self.result) != set(PredictionModelType):
                raise ValueError("succeeded result must contain every disease")
            if any(key != value.model_type for key, value in self.result.items()):
                raise ValueError("result key must match model_type")
        if self.status is PredictionTaskStatus.FAILED and (self.error_code is None or self.result is not None):
            raise ValueError("failed result requires error_code and no result")
        return self


def parse_result_fields(fields: Mapping[str, str]) -> PredictionProcessingMessage | PredictionResultMessage:
    """
    결과 Stream 항목을 검증합니다. 계약과 다르면 PredictionResultParseError를 발생시킵니다.
    status=processing이면 처리 시작 항목, 그 밖에는 최종 결과로 검증합니다.
    """
    if fields.get("status") == PredictionTaskStatus.PROCESSING:
        try:
            return PredictionProcessingMessage.model_validate(dict(fields))
        except ValidationError as error:
            raise PredictionResultParseError(_contract_error_message(error)) from None

    data: dict[str, Any] = dict(fields)
    for key in ("result", "errors"):
        if key in data:
            try:
                data[key] = json.loads(data[key])
            except (TypeError, json.JSONDecodeError):
                raise PredictionResultParseError(f"{key} is not valid JSON") from None
    try:
        return PredictionResultMessage.model_validate(data)
    except ValidationError as error:
        raise PredictionResultParseError(_contract_error_message(error)) from None


def _contract_error_message(error: ValidationError) -> str:
    locations = sorted({".".join(str(part) for part in item["loc"]) or "__root__" for item in error.errors()})
    return f"result does not match the contract: {', '.join(locations)}"
