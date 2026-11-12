"""
예측 요청 Stream을 Consumer Group으로 읽어 처리하고 결과를 요청별 Stream에 발행합니다.

처리 보장: 최소 1회. 결과 발행·ACK·요청 삭제를 한 트랜잭션으로 묶습니다.
Worker가 처리 중 멈추면 메시지는 Pending에 남고, CLAIM_MIN_IDLE_MS가 지나면 다른 Worker(또는 재시작한 Worker)가 회수합니다.
같은 요청이 두 번 처리될 수 있으므로 결과 Stream은 마지막 1건만 보관합니다.

건강 정보 보호
- 처리를 마친 요청은 Stream에서 삭제합니다(XDEL). payload가 Redis에 남는 시간을 줄이기 위함입니다.
- 실패 기록(Dead Letter)과 로그에는 task_id, 오류 코드, 사유만 남깁니다.
"""

import logging
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from tasks.prediction_stream_contract import (
    CLAIM_BATCH_SIZE,
    CLAIM_INTERVAL_SECONDS,
    CLAIM_MIN_IDLE_MS,
    DEAD_LETTER_MAXLEN,
    MAX_DELIVERY_COUNT,
    PREDICTION_CONSUMER_GROUP,
    PREDICTION_DEAD_LETTER_STREAM,
    PREDICTION_REQUEST_STREAM,
    READ_BLOCK_MS,
    READ_COUNT,
    RECONNECT_BACKOFF_INITIAL_SECONDS,
    RECONNECT_BACKOFF_MAX_SECONDS,
    RESULT_TTL_SECONDS,
    PredictionErrorCode,
    PredictionTaskStatus,
    result_stream_key,
)
from tasks.prediction_task import PredictionTask, TaskOutcome

logger = logging.getLogger(__name__)

# 실패 기록으로 남기지 않는 오류: 사용자 입력 오류는 정상적인 실패 응답입니다.
_NOT_DEAD_LETTER_CODES = {PredictionErrorCode.INVALID_INPUT}

# decode_responses=True 클라이언트의 응답 형식입니다. redis-py 타입 정의가 bytes·int까지 합쳐 선언해 명시합니다.
StreamEntry = tuple[str, dict[str, str] | None]
ReadGroupResponse = list[tuple[str, list[StreamEntry]]]
PendingEntry = dict[str, Any]


class PredictionStreamConsumer:
    def __init__(
        self,
        client: redis.Redis,
        task: PredictionTask,
        consumer_name: str,
        *,
        stream: str = PREDICTION_REQUEST_STREAM,
        group: str = PREDICTION_CONSUMER_GROUP,
        dead_letter_stream: str = PREDICTION_DEAD_LETTER_STREAM,
        block_ms: int = READ_BLOCK_MS,
        claim_min_idle_ms: int = CLAIM_MIN_IDLE_MS,
        claim_interval_seconds: float = CLAIM_INTERVAL_SECONDS,
        max_delivery_count: int = MAX_DELIVERY_COUNT,
    ) -> None:
        if not consumer_name:
            raise ValueError("consumer_name must not be empty")
        if max_delivery_count < 1:
            raise ValueError("max_delivery_count must be at least 1")
        self._client = client
        self._task = task
        self._consumer_name = consumer_name
        self._stream = stream
        self._group = group
        self._dead_letter_stream = dead_letter_stream
        self._block_ms = block_ms
        self._claim_min_idle_ms = claim_min_idle_ms
        self._claim_interval_seconds = claim_interval_seconds
        self._max_delivery_count = max_delivery_count
        self._stop_event = threading.Event()
        self._group_ready = False
        self._last_claim_at: float | None = None

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    def ensure_group(self) -> None:
        """Consumer Group이 없으면 만듭니다. Redis가 데이터 없이 재시작된 경우에도 다시 만듭니다."""
        try:
            self._client.xgroup_create(self._stream, self._group, id="0", mkstream=True)
            logger.info("Created consumer group %s on %s", self._group, self._stream)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise
        self._group_ready = True

    def run(self) -> None:
        """stop()이 호출될 때까지 메시지를 처리합니다. Redis 연결 오류는 재연결을 기다립니다."""
        logger.info("Consumer %s started on %s", self._consumer_name, self._stream)
        backoff = RECONNECT_BACKOFF_INITIAL_SECONDS
        while not self.stopped:
            try:
                self.run_once()
                backoff = RECONNECT_BACKOFF_INITIAL_SECONDS
            except (RedisConnectionError, RedisTimeoutError) as error:
                logger.warning("Redis unavailable (%s); retrying in %.0fs", type(error).__name__, backoff)
                self._group_ready = False
                self._stop_event.wait(backoff)
                backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX_SECONDS)
            except ResponseError as error:
                if "NOGROUP" not in str(error):
                    raise
                logger.warning("Consumer group is missing; recreating it")
                self._group_ready = False
        logger.info("Consumer %s stopped", self._consumer_name)

    def run_once(self) -> int:
        """회수 대상과 새 메시지를 한 번 처리하고 처리한 메시지 수를 반환합니다."""
        if not self._group_ready:
            self.ensure_group()

        processed = 0
        now = time.monotonic()
        if self._last_claim_at is None or now - self._last_claim_at >= self._claim_interval_seconds:
            processed += self.reclaim_stale()
            self._last_claim_at = now

        response = cast(
            ReadGroupResponse | None,
            self._client.xreadgroup(
                self._group, self._consumer_name, {self._stream: ">"}, count=READ_COUNT, block=self._block_ms
            ),
        )
        for _stream, messages in response or []:
            for message_id, fields in messages:
                self._process(message_id, fields or {})
                processed += 1
        return processed

    def reclaim_stale(self) -> int:
        """
        오래 ACK되지 않은 메시지를 회수합니다.
        전달 횟수가 한도에 이른 메시지는 다시 처리하지 않고 실패로 확정합니다.
        """
        pending = cast(
            list[PendingEntry],
            self._client.xpending_range(self._stream, self._group, min="-", max="+", count=CLAIM_BATCH_SIZE),
        )
        stale = [entry for entry in pending if entry["time_since_delivered"] >= self._claim_min_idle_ms]
        if not stale:
            return 0

        # xclaim의 message_ids 타입 선언이 list[str]을 받지 않아 Any로 둡니다. 값은 메시지 ID 문자열입니다.
        retry_ids: list[Any] = []
        for entry in stale:
            message_id = str(entry["message_id"])
            if entry["times_delivered"] < self._max_delivery_count:
                retry_ids.append(message_id)
                continue
            fields = self._read_message(message_id)
            task_id = fields.get("task_id") if fields else None
            logger.error("Message %s exceeded %d deliveries", message_id, self._max_delivery_count)
            self._finish(message_id, self._task.failed_after_retries(task_id), reason="max deliveries exceeded")

        processed = len(stale) - len(retry_ids)
        if retry_ids:
            claimed = cast(
                list[StreamEntry],
                self._client.xclaim(
                    self._stream,
                    self._group,
                    self._consumer_name,
                    min_idle_time=self._claim_min_idle_ms,
                    message_ids=retry_ids,
                ),
            )
            for message_id, fields in claimed:
                if fields:
                    self._process(message_id, fields)
                else:
                    # Stream에서 이미 삭제된 메시지: 처리할 내용이 없으므로 Pending에서만 정리합니다.
                    self._client.xack(self._stream, self._group, message_id)
                processed += 1
        return processed

    def _process(self, message_id: str, fields: Mapping[str, str]) -> None:
        started = time.monotonic()
        try:
            outcome = self._task.handle(fields)
        except Exception as error:
            # 일시적일 수 있는 오류: ACK하지 않아 Pending에 남기고, 회수 주기에 다시 처리합니다.
            # 예외 메시지에 입력값이 들어 있을 수 있어 예외 종류만 기록합니다.
            logger.warning("Message %s failed with %s; it will be retried", message_id, type(error).__name__)
            return
        self._finish(message_id, outcome)
        elapsed_ms = (time.monotonic() - started) * 1000
        status = outcome.result.status if outcome.result else "rejected"
        error_code = outcome.result.error_code if outcome.result else None
        logger.info(
            "Task %s %s%s in %.0f ms", outcome.task_id, status, f" ({error_code})" if error_code else "", elapsed_ms
        )

    def _finish(self, message_id: str, outcome: TaskOutcome, reason: str | None = None) -> None:
        """결과 발행, 실패 기록, ACK, 요청 삭제를 한 트랜잭션으로 처리합니다."""
        pipe = self._client.pipeline(transaction=True)
        result = outcome.result
        if result is not None and outcome.task_id is not None:
            key = result_stream_key(outcome.task_id)
            pipe.xadd(key, result.to_stream_fields(), maxlen=1, approximate=False)  # type: ignore[arg-type]
            pipe.expire(key, RESULT_TTL_SECONDS)

        if result is None or (
            result.status is PredictionTaskStatus.FAILED and result.error_code not in _NOT_DEAD_LETTER_CODES
        ):
            pipe.xadd(
                self._dead_letter_stream,
                self._dead_letter_fields(message_id, outcome, reason),  # type: ignore[arg-type]
                maxlen=DEAD_LETTER_MAXLEN,
                approximate=True,
            )

        pipe.xack(self._stream, self._group, message_id)
        pipe.xdel(self._stream, message_id)
        pipe.execute()

    @staticmethod
    def _dead_letter_fields(message_id: str, outcome: TaskOutcome, reason: str | None) -> dict[str, str]:
        result = outcome.result
        error_code = result.error_code if result and result.error_code else PredictionErrorCode.INVALID_MESSAGE
        default_reason = "invalid task_id" if result is None else str(error_code)
        return {
            "message_id": message_id,
            "task_id": outcome.task_id or "",
            "error_code": str(error_code),
            "reason": reason or default_reason,
            "failed_at": datetime.now(UTC).isoformat(),
        }

    def _read_message(self, message_id: str) -> dict[str, str] | None:
        entries = cast(list[StreamEntry], self._client.xrange(self._stream, min=message_id, max=message_id, count=1))
        if not entries:
            return None
        return entries[0][1]
