import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.enums import PredictionModelType
from app.core.utils.prediction_stream import (
    MAX_PAYLOAD_BYTES,
    PREDICTION_RESULT_STREAM_PREFIX,
    PredictionErrorCode,
    PredictionProcessingMessage,
    PredictionResultParseError,
    PredictionTaskStatus,
    build_request_fields,
    parse_result_fields,
    result_stream_key,
)
from tests.disease_prediction_apis.helpers import (
    disease_result,
    failed_result_fields,
    processing_result_fields,
    succeeded_result_fields,
)


def test_build_request_fields_matches_worker_contract() -> None:
    task_id = str(uuid4())
    requested_at = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)

    fields = build_request_fields(task_id, {"gender": "M", "sbp": 120}, requested_at)

    assert set(fields) == {"task_id", "schema_version", "payload", "requested_at"}
    assert fields["task_id"] == task_id
    assert fields["schema_version"] == "2"
    assert json.loads(fields["payload"]) == {"gender": "M", "sbp": 120}
    assert datetime.fromisoformat(fields["requested_at"]) == requested_at
    assert all(isinstance(value, str) for value in fields.values())


@pytest.mark.parametrize("task_id", ["bad:id", "", "a" * 65, "*"])
def test_build_request_fields_rejects_invalid_task_id(task_id: str) -> None:
    with pytest.raises(ValueError):
        build_request_fields(task_id, {}, datetime.now(UTC))


def test_build_request_fields_rejects_large_payload() -> None:
    with pytest.raises(ValueError):
        build_request_fields(str(uuid4()), {"memo": "x" * MAX_PAYLOAD_BYTES}, datetime.now(UTC))


def test_build_request_fields_rejects_nan() -> None:
    with pytest.raises(ValueError):
        build_request_fields(str(uuid4()), {"weight": float("nan")}, datetime.now(UTC))


def test_result_stream_key() -> None:
    task_id = str(uuid4())
    assert result_stream_key(task_id) == f"{PREDICTION_RESULT_STREAM_PREFIX}{task_id}"
    with pytest.raises(ValueError):
        result_stream_key("bad:id")


def test_parse_succeeded_result() -> None:
    task_id = str(uuid4())

    message = parse_result_fields(succeeded_result_fields(task_id))

    assert message.status is PredictionTaskStatus.SUCCEEDED
    assert message.result is not None
    assert set(message.result) == set(PredictionModelType)
    diabetes = message.result[PredictionModelType.DIABETES_RISK]
    assert diabetes.risk_probability == pytest.approx(0.2345678)
    assert diabetes.risk_factors[0].display_name == "허리둘레"


def test_parse_processing_entry() -> None:
    task_id = str(uuid4())

    message = parse_result_fields(processing_result_fields(task_id))

    assert isinstance(message, PredictionProcessingMessage)
    assert message.task_id == task_id
    assert message.started_at.tzinfo is not None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda fields: fields.pop("started_at"),
        lambda fields: fields.update(schema_version="1"),
        lambda fields: fields.update(task_id="bad:id"),
    ],
)
def test_parse_processing_entry_rejects_contract_violation(mutate) -> None:
    fields = processing_result_fields(uuid4())
    mutate(fields)

    with pytest.raises(PredictionResultParseError):
        parse_result_fields(fields)


def test_parse_failed_result() -> None:
    fields = failed_result_fields(uuid4(), "INVALID_INPUT", [{"field": "sbp", "reason": "too high"}])

    message = parse_result_fields(fields)

    assert message.status is PredictionTaskStatus.FAILED
    assert message.error_code is PredictionErrorCode.INVALID_INPUT
    assert message.errors[0].field == "sbp"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda fields: fields.update(result="{broken"),
        lambda fields: fields.update(schema_version="1"),  # 이전 계약 버전
        lambda fields: fields.update(status="unknown"),
        lambda fields: fields.update(task_id="bad:id"),
        lambda fields: fields.update(
            result=json.dumps({"diabetes_risk": disease_result("diabetes_risk", 0.3)})
        ),  # 질환 1개 누락
        lambda fields: fields.update(
            result=json.dumps(
                {
                    "diabetes_risk": disease_result("hypertension_risk", 0.3),
                    "hypertension_risk": disease_result("hypertension_risk", 0.3),
                }
            )
        ),  # 키와 model_type 불일치
        lambda fields: fields.update(
            result=json.dumps(
                {
                    "diabetes_risk": disease_result("diabetes_risk", 1.5),
                    "hypertension_risk": disease_result("hypertension_risk", 0.3),
                }
            )
        ),  # 확률 범위 초과
        lambda fields: fields.update(
            result=json.dumps(
                {
                    "diabetes_risk": {**disease_result("diabetes_risk", 0.3), "shap_base_value": float("nan")},
                    "hypertension_risk": disease_result("hypertension_risk", 0.3),
                }
            )
        ),  # NaN
        lambda fields: fields.update(error_code="INVALID_INPUT"),  # 성공 결과에 오류 코드
    ],
)
def test_parse_result_rejects_contract_violation(mutate) -> None:
    fields = succeeded_result_fields(uuid4())
    mutate(fields)

    with pytest.raises(PredictionResultParseError):
        parse_result_fields(fields)


def test_parse_failed_result_requires_error_code() -> None:
    fields = failed_result_fields(uuid4(), "INVALID_INPUT")
    del fields["error_code"]

    with pytest.raises(PredictionResultParseError):
        parse_result_fields(fields)
