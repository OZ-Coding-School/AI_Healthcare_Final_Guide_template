"""
AI Worker 진입점입니다. apps/ai에서 `uv run python main.py`로 실행합니다.

1. 서빙 번들을 1회 로드합니다. 실패하면 메시지를 받지 않고 종료 코드 1로 종료합니다.
2. Redis 예측 요청 Stream을 Consumer Group으로 읽어 처리합니다.
3. SIGTERM·SIGINT를 받으면 처리 중인 메시지를 마치고 종료합니다.
"""

import logging
import os
import signal
import socket
import sys
from types import FrameType

import redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from core.config import Config, settings
from core.logger import configure_logger
from src.components.knhanes_inference_errors import ModelArtifactError
from src.pipelines.inference_pipeline import KnhanesRiskPredictor
from tasks.prediction_stream_consumer import PredictionStreamConsumer
from tasks.prediction_stream_contract import READ_BLOCK_MS
from tasks.prediction_task import PredictionTask

# XREADGROUP 대기보다 길어야 대기 중에 소켓 타임아웃이 나지 않습니다.
REDIS_SOCKET_TIMEOUT_SECONDS = READ_BLOCK_MS / 1000 + 5
REDIS_CONNECT_TIMEOUT_SECONDS = 3
REDIS_HEALTH_CHECK_INTERVAL_SECONDS = 30
# redis-py 8의 기본 재시도는 10회라 장애 감지가 늦습니다. 긴 대기는 Consumer의 재연결 루프가 맡습니다.
REDIS_COMMAND_RETRIES = 2


def create_redis_client(config: Config) -> redis.Redis:
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        username=config.REDIS_USER or None,
        password=config.REDIS_PASSWORD or None,
        decode_responses=True,
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
        health_check_interval=REDIS_HEALTH_CHECK_INTERVAL_SECONDS,
        retry=Retry(ExponentialBackoff(cap=1.0, base=0.1), REDIS_COMMAND_RETRIES),
    )


def consumer_name() -> str:
    """컨테이너를 여러 개 띄워도 겹치지 않도록 호스트명과 PID를 씁니다."""
    return f"{socket.gethostname()}-{os.getpid()}"


def main() -> int:
    logger = configure_logger()
    # src·tasks 모듈의 로그도 같은 형식으로 출력합니다.
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")

    try:
        predictor = KnhanesRiskPredictor()
    except (ModelArtifactError, FileNotFoundError) as error:
        logger.error("Failed to load serving bundles: %s", error)
        logger.error("Run `uv run python -m src.pipelines.knhanes_serving_bundle_pipeline` in apps/ai first.")
        return 1

    consumer = PredictionStreamConsumer(create_redis_client(settings), PredictionTask(predictor), consumer_name())

    def _handle_signal(signum: int, _frame: FrameType | None) -> None:
        logger.info("Received %s; stopping after the current message", signal.Signals(signum).name)
        consumer.stop()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    consumer.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
