"""
예측 요청·결과 Redis Stream 계약입니다.

Backend(13번)는 이 모듈을 import하지 않으므로, Stream 이름·필드·값을 Backend에도 같게 적어야 합니다.
계약을 바꾸면 PREDICTION_SCHEMA_VERSION을 올리고 양쪽을 함께 수정합니다.

요청 (Backend → Worker)
    Stream: ai:prediction:requests, Consumer Group: ai-workers
    필드: task_id, schema_version, payload(ServiceHealthInput JSON), requested_at(ISO 8601)

결과 (Worker → Backend)
    Stream: ai:prediction:result:{task_id} (요청별 1개, 마지막 항목 1건만 보관, TTL 적용)
    처리 시작: task_id, schema_version, status=processing, started_at
    성공: task_id, schema_version, status=succeeded, result(JSON), completed_at
    실패: task_id, schema_version, status=failed, error_code, errors(JSON), completed_at

처리 시작 항목은 Worker가 요청을 가져갈 때 남기며, 최종 결과(성공·실패)가 같은 키에서 이를 대체합니다.
Backend는 이를 보고 Task 상태를 PENDING → PROCESSING으로 바꿉니다.

Redis Stream 필드는 문자열만 담을 수 있어 객체는 JSON 문자열로 넣습니다.
"""

import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 2: 처리 시작(status=processing) 항목 추가
PREDICTION_SCHEMA_VERSION = "2"

# Stream·Consumer Group 이름
PREDICTION_REQUEST_STREAM = "ai:prediction:requests"
PREDICTION_CONSUMER_GROUP = "ai-workers"
PREDICTION_RESULT_STREAM_PREFIX = "ai:prediction:result:"
PREDICTION_DEAD_LETTER_STREAM = "ai:prediction:dead-letter"

# task_id는 결과 Stream 키에 들어가므로 키 구분자(:)나 패턴 문자(*)를 허용하지 않습니다. UUID를 권장합니다.
TASK_ID_PATTERN = r"^[A-Za-z0-9-]{1,64}$"
_TASK_ID_REGEX = re.compile(TASK_ID_PATTERN)

# 건강 입력 1건은 수 KB이므로 이보다 크면 잘못된 메시지로 봅니다.
MAX_PAYLOAD_BYTES = 16_384

# 결과 보관 시간: Backend가 결과를 받아 DB에 저장하기 전까지 필요한 시간
RESULT_TTL_SECONDS = 3_600
# 실패 기록 보관 개수 (입력값은 넣지 않음)
DEAD_LETTER_MAXLEN = 1_000

# 같은 메시지를 이 횟수만큼 전달했는데도 처리하지 못하면 실패로 확정합니다.
MAX_DELIVERY_COUNT = 3
# 이 시간 동안 ACK되지 않은 메시지는 처리하던 Worker가 멈춘 것으로 보고 회수합니다.
CLAIM_MIN_IDLE_MS = 30_000
CLAIM_INTERVAL_SECONDS = 15.0
CLAIM_BATCH_SIZE = 10

# XREADGROUP 대기 시간: 종료 신호를 이 간격 안에 확인합니다.
READ_BLOCK_MS = 5_000
READ_COUNT = 1

# Redis 연결 오류 시 재연결 대기 시간 (지수 증가)
RECONNECT_BACKOFF_INITIAL_SECONDS = 1.0
RECONNECT_BACKOFF_MAX_SECONDS = 30.0


class PredictionTaskStatus(StrEnum):
    PROCESSING = "processing"  # Worker가 요청을 가져가 처리 중 (최종 결과 아님)
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PredictionErrorCode(StrEnum):
    """Backend가 사용자 응답으로 바꿀 때의 대응 관계를 함께 적습니다."""

    INVALID_MESSAGE = "INVALID_MESSAGE"  # 계약 위반 (Backend 버그, 500)
    INVALID_INPUT = "INVALID_INPUT"  # 사용자 입력 오류 (400·422)
    MODEL_ERROR = "MODEL_ERROR"  # 모델 번들 오류·불일치 (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"  # 재시도 한도 초과 (500)


def result_stream_key(task_id: str) -> str:
    if not is_valid_task_id(task_id):
        raise ValueError("task_id has an invalid format")
    return f"{PREDICTION_RESULT_STREAM_PREFIX}{task_id}"


def is_valid_task_id(task_id: Any) -> bool:
    return isinstance(task_id, str) and _TASK_ID_REGEX.fullmatch(task_id) is not None


def processing_stream_fields(task_id: str, started_at: datetime) -> dict[str, str]:
    """처리 시작 항목입니다. 입력값과 결과는 담지 않습니다."""
    if not is_valid_task_id(task_id):
        raise ValueError("task_id has an invalid format")
    return {
        "task_id": task_id,
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "status": str(PredictionTaskStatus.PROCESSING),
        "started_at": started_at.isoformat(),
    }


class PredictionRequestMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(pattern=TASK_ID_PATTERN)
    schema_version: Literal["2"]
    payload: str = Field(min_length=2, max_length=MAX_PAYLOAD_BYTES)
    requested_at: datetime


class FieldErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: str
    reason: str


class PredictionResultMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str = Field(pattern=TASK_ID_PATTERN)
    schema_version: str = PREDICTION_SCHEMA_VERSION
    status: PredictionTaskStatus
    result: dict[str, Any] | None = None
    error_code: PredictionErrorCode | None = None
    errors: list[FieldErrorDetail] = Field(default_factory=list)
    completed_at: datetime

    @model_validator(mode="after")
    def _check_status_fields(self) -> "PredictionResultMessage":
        if self.status is PredictionTaskStatus.PROCESSING:
            raise ValueError("final result cannot be processing; use processing_stream_fields")
        if self.status is PredictionTaskStatus.SUCCEEDED and (self.result is None or self.error_code is not None):
            raise ValueError("succeeded result requires result and no error_code")
        if self.status is PredictionTaskStatus.FAILED and (self.error_code is None or self.result is not None):
            raise ValueError("failed result requires error_code and no result")
        return self

    def to_stream_fields(self) -> dict[str, str]:
        """Redis Stream에 넣을 문자열 필드입니다. NaN·Infinity는 JSON에서 거부합니다."""
        fields = {
            "task_id": self.task_id,
            "schema_version": self.schema_version,
            "status": str(self.status),
            "completed_at": self.completed_at.isoformat(),
        }
        if self.status is PredictionTaskStatus.SUCCEEDED:
            fields["result"] = json.dumps(self.result, ensure_ascii=False, allow_nan=False)
        else:
            fields["error_code"] = str(self.error_code)
            fields["errors"] = json.dumps([error.model_dump() for error in self.errors], ensure_ascii=False)
        return fields
