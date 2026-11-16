import json
import math

import pytest
from pydantic import ValidationError

from tasks.prediction_stream_contract import (
    PREDICTION_RESULT_STREAM_PREFIX,
    PREDICTION_SCHEMA_VERSION,
    FieldErrorDetail,
    PredictionErrorCode,
    PredictionResultMessage,
    PredictionTaskStatus,
    is_valid_task_id,
    processing_stream_fields,
    result_stream_key,
)
from tests.prediction_worker_helpers import FIXED_NOW, TASK_ID

# ---------------------------------------------------------------- 성공 케이스


def test_result_stream_key_uses_task_id():
    assert result_stream_key(TASK_ID) == f"{PREDICTION_RESULT_STREAM_PREFIX}{TASK_ID}"


def test_succeeded_message_has_result_without_error_fields():
    message = PredictionResultMessage(
        task_id=TASK_ID,
        status=PredictionTaskStatus.SUCCEEDED,
        result={"diabetes_risk": {"a": 1}},
        completed_at=FIXED_NOW,
    )

    fields = message.to_stream_fields()

    assert fields["status"] == "succeeded"
    assert json.loads(fields["result"]) == {"diabetes_risk": {"a": 1}}
    assert "error_code" not in fields and "errors" not in fields
    assert fields["completed_at"] == FIXED_NOW.isoformat()
    assert all(isinstance(value, str) for value in fields.values())


def test_processing_fields_have_no_payload_or_result():
    fields = processing_stream_fields(TASK_ID, FIXED_NOW)

    assert fields == {
        "task_id": TASK_ID,
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "status": "processing",
        "started_at": FIXED_NOW.isoformat(),
    }


def test_failed_message_has_error_fields_without_result():
    message = PredictionResultMessage(
        task_id=TASK_ID,
        status=PredictionTaskStatus.FAILED,
        error_code=PredictionErrorCode.INVALID_INPUT,
        errors=[FieldErrorDetail(field="sbp", reason="out of range")],
        completed_at=FIXED_NOW,
    )

    fields = message.to_stream_fields()

    assert fields["status"] == "failed"
    assert fields["error_code"] == "INVALID_INPUT"
    assert json.loads(fields["errors"]) == [{"field": "sbp", "reason": "out of range"}]
    assert "result" not in fields


# ---------------------------------------------------------------- 실패 케이스


@pytest.mark.parametrize("task_id", ["a:b", "a*", "", "x" * 65, "한글", None, 123])
def test_invalid_task_id_is_rejected(task_id):
    assert not is_valid_task_id(task_id)
    if isinstance(task_id, str):
        with pytest.raises(ValueError):
            result_stream_key(task_id)


def test_final_message_cannot_be_processing():
    with pytest.raises(ValidationError):
        PredictionResultMessage(task_id=TASK_ID, status=PredictionTaskStatus.PROCESSING, completed_at=FIXED_NOW)


def test_processing_fields_reject_invalid_task_id():
    with pytest.raises(ValueError):
        processing_stream_fields("a:b", FIXED_NOW)


def test_succeeded_message_requires_result():
    with pytest.raises(ValidationError):
        PredictionResultMessage(task_id=TASK_ID, status=PredictionTaskStatus.SUCCEEDED, completed_at=FIXED_NOW)


def test_failed_message_requires_error_code():
    with pytest.raises(ValidationError):
        PredictionResultMessage(task_id=TASK_ID, status=PredictionTaskStatus.FAILED, completed_at=FIXED_NOW)


def test_failed_message_cannot_carry_result():
    with pytest.raises(ValidationError):
        PredictionResultMessage(
            task_id=TASK_ID,
            status=PredictionTaskStatus.FAILED,
            error_code=PredictionErrorCode.MODEL_ERROR,
            result={"diabetes_risk": {}},
            completed_at=FIXED_NOW,
        )


def test_nan_in_result_is_not_serialized():
    message = PredictionResultMessage(
        task_id=TASK_ID,
        status=PredictionTaskStatus.SUCCEEDED,
        result={"diabetes_risk": {"risk_probability": math.nan}},
        completed_at=FIXED_NOW,
    )

    with pytest.raises(ValueError):
        message.to_stream_fields()
