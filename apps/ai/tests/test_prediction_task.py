import json
import math

import pytest

from src.components.knhanes_inference_errors import ModelArtifactError
from tasks.prediction_stream_contract import MAX_PAYLOAD_BYTES, PredictionErrorCode, PredictionTaskStatus
from tasks.prediction_task import PredictionTask
from tests.prediction_worker_helpers import FIXED_NOW, TASK_ID, FakePredictor, make_request
from tests.test_knhanes_input_adapter import valid_payload


def _task(predictor: FakePredictor | None = None) -> PredictionTask:
    return PredictionTask(predictor or FakePredictor(), clock=lambda: FIXED_NOW)


# ---------------------------------------------------------------- 성공 케이스


def test_valid_message_returns_succeeded():
    outcome = _task().handle(make_request())

    assert outcome.task_id == TASK_ID
    assert outcome.result.status is PredictionTaskStatus.SUCCEEDED
    assert outcome.result.error_code is None
    assert outcome.result.completed_at == FIXED_NOW


def test_result_is_keyed_by_model_type_string():
    outcome = _task().handle(make_request())

    assert set(outcome.result.result) == {"diabetes_risk", "hypertension_risk"}
    assert outcome.result.result["diabetes_risk"]["risk_probability"] == pytest.approx(0.2)
    json.dumps(outcome.result.result, allow_nan=False)


def test_failed_after_retries_returns_internal_error():
    outcome = _task().failed_after_retries(TASK_ID)

    assert outcome.task_id == TASK_ID
    assert outcome.result.error_code is PredictionErrorCode.INTERNAL_ERROR


# ---------------------------------------------------------------- 실패 케이스: 결과를 보낼 수 없는 메시지


@pytest.mark.parametrize("task_id", ["bad:id", ""])
def test_invalid_task_id_returns_no_result(task_id):
    predictor = FakePredictor()

    outcome = _task(predictor).handle(make_request(task_id=task_id))

    assert outcome.task_id is None
    assert outcome.result is None
    assert predictor.calls == 0


def test_missing_task_id_returns_no_result():
    fields = make_request()
    del fields["task_id"]

    outcome = _task().handle(fields)

    assert outcome.result is None


def test_failed_after_retries_with_invalid_task_id_returns_no_result():
    assert _task().failed_after_retries(None).result is None


# ---------------------------------------------------------------- 실패 케이스: 계약 위반


@pytest.mark.parametrize(
    ("overrides", "error_field"),
    [
        ({"schema_version": "2"}, "schema_version"),
        ({"requested_at": "yesterday"}, "requested_at"),
        ({"unexpected": "x"}, "unexpected"),
        ({"payload": "x" * (MAX_PAYLOAD_BYTES + 1)}, "payload"),
    ],
)
def test_contract_violation_returns_invalid_message(overrides, error_field):
    predictor = FakePredictor()

    outcome = _task(predictor).handle(make_request(**overrides))

    assert outcome.result.status is PredictionTaskStatus.FAILED
    assert outcome.result.error_code is PredictionErrorCode.INVALID_MESSAGE
    assert [error.field for error in outcome.result.errors] == [error_field]
    assert predictor.calls == 0


def test_missing_field_returns_invalid_message():
    fields = make_request()
    del fields["requested_at"]

    outcome = _task().handle(fields)

    assert outcome.result.error_code is PredictionErrorCode.INVALID_MESSAGE
    assert [error.field for error in outcome.result.errors] == ["requested_at"]


def test_broken_json_payload_returns_invalid_message():
    outcome = _task().handle(make_request(payload="{not json"))

    assert outcome.result.error_code is PredictionErrorCode.INVALID_MESSAGE
    assert [error.field for error in outcome.result.errors] == ["payload"]


# ---------------------------------------------------------------- 실패 케이스: 입력 오류


def test_non_object_payload_returns_invalid_input():
    outcome = _task().handle(make_request(payload="[1, 2]"))

    assert outcome.result.error_code is PredictionErrorCode.INVALID_INPUT
    assert [error.field for error in outcome.result.errors] == ["__root__"]


def test_out_of_range_input_returns_invalid_input_with_field_name():
    outcome = _task().handle(make_request(payload=json.dumps(valid_payload(sbp=999))))

    assert outcome.result.error_code is PredictionErrorCode.INVALID_INPUT
    assert [error.field for error in outcome.result.errors] == ["sbp"]


def test_input_error_does_not_expose_input_value():
    outcome = _task().handle(make_request(payload=json.dumps(valid_payload(sbp=999))))

    assert "999" not in json.dumps(outcome.result.to_stream_fields())


# ---------------------------------------------------------------- 실패 케이스: 모델 오류


def test_model_artifact_error_returns_model_error_without_details():
    predictor = FakePredictor(error=ModelArtifactError("diabetes_risk: categories unseen in training"))

    outcome = _task(predictor).handle(make_request())

    assert outcome.result.error_code is PredictionErrorCode.MODEL_ERROR
    assert outcome.result.errors == []


def test_non_finite_prediction_returns_model_error():
    outcome = _task(FakePredictor(probability=math.nan)).handle(make_request())

    assert outcome.result.error_code is PredictionErrorCode.MODEL_ERROR


# ---------------------------------------------------------------- 실패 케이스: 재시도 대상


def test_unexpected_error_is_raised_for_retry():
    with pytest.raises(RuntimeError):
        _task(FakePredictor(error=RuntimeError("temporary"))).handle(make_request())
