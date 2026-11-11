"""
Redis Stream 처리 통합 테스트입니다. fakeredis로 실제 Stream 명령(XREADGROUP, XCLAIM, XACK 등)을 실행합니다.
회수 대기 시간(30초)은 claim_min_idle_ms=0, claim_interval_seconds=0으로 줄여 즉시 회수되게 합니다.
"""

import json
import threading
import time
from unittest.mock import MagicMock

import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.knhanes_inference_configs import SERVING_MANIFEST_NAME, SERVING_MODEL_DIR
from tasks.prediction_stream_consumer import PredictionStreamConsumer
from tasks.prediction_stream_contract import (
    PREDICTION_CONSUMER_GROUP,
    PREDICTION_DEAD_LETTER_STREAM,
    PREDICTION_REQUEST_STREAM,
    PREDICTION_RESULT_STREAM_PREFIX,
    RESULT_TTL_SECONDS,
    result_stream_key,
)
from tasks.prediction_task import PredictionTask
from tests.prediction_worker_helpers import FIXED_NOW, TASK_ID, FakePredictor, make_request
from tests.test_knhanes_input_adapter import valid_payload

IMMEDIATE_CLAIM = {"claim_min_idle_ms": 0, "claim_interval_seconds": 0}


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


def make_consumer(client, predictor, **options) -> PredictionStreamConsumer:
    consumer = PredictionStreamConsumer(
        client, PredictionTask(predictor, clock=lambda: FIXED_NOW), "test-consumer", block_ms=10, **options
    )
    consumer.ensure_group()
    return consumer


def latest_result(client, task_id: str = TASK_ID) -> dict[str, str] | None:
    entries = client.xrange(result_stream_key(task_id))
    return entries[-1][1] if entries else None


def pending_count(client) -> int:
    return client.xpending(PREDICTION_REQUEST_STREAM, PREDICTION_CONSUMER_GROUP)["pending"]


def dead_letters(client) -> list[dict[str, str]]:
    return [fields for _, fields in client.xrange(PREDICTION_DEAD_LETTER_STREAM)]


def run_for(consumer: PredictionStreamConsumer, seconds: float) -> float:
    """run()을 seconds 뒤 stop()으로 끝내고 걸린 시간을 반환합니다."""
    timer = threading.Timer(seconds, consumer.stop)
    timer.start()
    started = time.monotonic()
    try:
        consumer.run()
    finally:
        timer.cancel()
    return time.monotonic() - started


# ---------------------------------------------------------------- 성공 케이스


def test_ensure_group_can_be_called_repeatedly(redis_client):
    consumer = make_consumer(redis_client, FakePredictor())

    consumer.ensure_group()

    groups = redis_client.xinfo_groups(PREDICTION_REQUEST_STREAM)
    assert [group["name"] for group in groups] == [PREDICTION_CONSUMER_GROUP]


def test_valid_request_publishes_result_and_removes_request(redis_client):
    consumer = make_consumer(redis_client, FakePredictor())
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request())

    processed = consumer.run_once()

    result = latest_result(redis_client)
    assert processed == 1
    assert result["status"] == "succeeded"
    assert set(json.loads(result["result"])) == {"diabetes_risk", "hypertension_risk"}
    assert 0 < redis_client.ttl(result_stream_key(TASK_ID)) <= RESULT_TTL_SECONDS
    assert redis_client.xlen(PREDICTION_REQUEST_STREAM) == 0
    assert pending_count(redis_client) == 0
    assert dead_letters(redis_client) == []


def test_duplicate_task_keeps_only_latest_result(redis_client):
    consumer = make_consumer(redis_client, FakePredictor())
    for _ in range(2):
        redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request())
        consumer.run_once()

    assert redis_client.xlen(result_stream_key(TASK_ID)) == 1


def test_invalid_input_publishes_failure_without_dead_letter(redis_client):
    consumer = make_consumer(redis_client, FakePredictor())
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request(payload=json.dumps(valid_payload(sbp=999))))

    consumer.run_once()

    result = latest_result(redis_client)
    assert result["status"] == "failed"
    assert result["error_code"] == "INVALID_INPUT"
    assert dead_letters(redis_client) == []
    assert pending_count(redis_client) == 0


def test_temporary_error_is_retried_and_succeeds(redis_client):
    predictor = FakePredictor(error=RuntimeError("temporary"), fail_times=1)
    consumer = make_consumer(redis_client, predictor, **IMMEDIATE_CLAIM)
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request())

    consumer.run_once()  # 1회차 실패: ACK하지 않고 Pending에 남김
    assert latest_result(redis_client) is None
    assert pending_count(redis_client) == 1

    consumer.run_once()  # 회수 후 성공

    assert predictor.calls == 2
    assert latest_result(redis_client)["status"] == "succeeded"
    assert pending_count(redis_client) == 0
    assert dead_letters(redis_client) == []


# ---------------------------------------------------------------- 실패 케이스


def test_invalid_task_id_goes_to_dead_letter_without_result(redis_client):
    consumer = make_consumer(redis_client, FakePredictor())
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request(task_id="bad:id"))

    consumer.run_once()

    assert redis_client.keys(f"{PREDICTION_RESULT_STREAM_PREFIX}*") == []
    assert [(item["task_id"], item["reason"]) for item in dead_letters(redis_client)] == [("", "invalid task_id")]
    assert redis_client.xlen(PREDICTION_REQUEST_STREAM) == 0
    assert pending_count(redis_client) == 0


def test_contract_violation_publishes_failure_and_dead_letter(redis_client):
    consumer = make_consumer(redis_client, FakePredictor())
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request(schema_version="2"))

    consumer.run_once()

    assert latest_result(redis_client)["error_code"] == "INVALID_MESSAGE"
    letters = dead_letters(redis_client)
    assert [(item["task_id"], item["error_code"]) for item in letters] == [(TASK_ID, "INVALID_MESSAGE")]


def test_dead_letter_does_not_store_payload(redis_client):
    consumer = make_consumer(redis_client, FakePredictor())
    payload = json.dumps(valid_payload(height=171.3))
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request(schema_version="2", payload=payload))

    consumer.run_once()

    letter = dead_letters(redis_client)[0]
    assert set(letter) == {"message_id", "task_id", "error_code", "reason", "failed_at"}
    assert "171.3" not in json.dumps(letter)


def test_message_is_not_reclaimed_before_idle_threshold(redis_client):
    predictor = FakePredictor(error=RuntimeError("temporary"), fail_times=1)
    consumer = make_consumer(redis_client, predictor, claim_interval_seconds=0)  # 기본 대기 30초 유지
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request())

    consumer.run_once()
    consumer.run_once()

    assert predictor.calls == 1
    assert pending_count(redis_client) == 1


def test_message_fails_after_max_deliveries(redis_client):
    predictor = FakePredictor(error=RuntimeError("always"))
    consumer = make_consumer(redis_client, predictor, **IMMEDIATE_CLAIM)
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request())

    for _ in range(5):
        consumer.run_once()

    result = latest_result(redis_client)
    assert predictor.calls == 3
    assert result["status"] == "failed"
    assert result["error_code"] == "INTERNAL_ERROR"
    assert [item["reason"] for item in dead_letters(redis_client)] == ["max deliveries exceeded"]
    assert pending_count(redis_client) == 0
    assert redis_client.xlen(PREDICTION_REQUEST_STREAM) == 0


def test_deleted_pending_message_is_cleared_without_processing(redis_client):
    predictor = FakePredictor(error=RuntimeError("temporary"), fail_times=1)
    consumer = make_consumer(redis_client, predictor, **IMMEDIATE_CLAIM)
    message_id = redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request())
    consumer.run_once()
    redis_client.xdel(PREDICTION_REQUEST_STREAM, message_id)

    consumer.run_once()

    assert predictor.calls == 1
    assert latest_result(redis_client) is None
    assert pending_count(redis_client) == 0


def test_missing_group_is_recreated(redis_client):
    consumer = make_consumer(redis_client, FakePredictor())
    redis_client.xgroup_destroy(PREDICTION_REQUEST_STREAM, PREDICTION_CONSUMER_GROUP)
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request())

    run_for(consumer, 0.5)

    assert latest_result(redis_client)["status"] == "succeeded"


def test_connection_error_waits_and_stops_on_request():
    client = MagicMock()
    client.xpending_range.side_effect = RedisConnectionError("down")
    consumer = make_consumer(client, FakePredictor())

    elapsed = run_for(consumer, 0.2)

    assert consumer.stopped
    assert client.xpending_range.call_count >= 1
    assert elapsed < 2


@pytest.mark.parametrize(
    ("consumer_name", "options"),
    [("", {}), ("worker", {"max_delivery_count": 0})],
)
def test_invalid_constructor_arguments_are_rejected(redis_client, consumer_name, options):
    with pytest.raises(ValueError):
        PredictionStreamConsumer(redis_client, PredictionTask(FakePredictor()), consumer_name, **options)


# ---------------------------------------------------------------- 실제 서빙 번들 왕복

real_bundle = pytest.mark.skipif(
    not (SERVING_MODEL_DIR / SERVING_MANIFEST_NAME).exists(), reason="Serving bundle is not available"
)


@real_bundle
def test_real_bundle_round_trip(redis_client):
    from src.pipelines.inference_pipeline import KnhanesRiskPredictor

    consumer = make_consumer(redis_client, KnhanesRiskPredictor())
    redis_client.xadd(PREDICTION_REQUEST_STREAM, make_request(task_id="real-ok"))
    redis_client.xadd(
        PREDICTION_REQUEST_STREAM, make_request(task_id="real-bad", payload=json.dumps(valid_payload(sbp=999)))
    )

    consumer.run_once()
    consumer.run_once()

    succeeded = latest_result(redis_client, "real-ok")
    body = json.loads(succeeded["result"])
    assert succeeded["status"] == "succeeded"
    for prediction in body.values():
        assert 0 <= prediction["risk_probability"] <= 1
        assert prediction["risk_level"] in {"LOW", "MODERATE", "HIGH"}
    assert latest_result(redis_client, "real-bad")["error_code"] == "INVALID_INPUT"
    assert redis_client.xlen(PREDICTION_REQUEST_STREAM) == 0
