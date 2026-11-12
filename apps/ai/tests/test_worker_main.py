import os
import socket

import pytest

import main
from core.config import Config
from src.components.knhanes_inference_errors import ModelArtifactError

# ---------------------------------------------------------------- 성공 케이스


def test_create_redis_client_uses_config_values():
    config = Config(REDIS_HOST="redis-host", REDIS_PORT=6380, REDIS_DB=2, REDIS_USER="worker", REDIS_PASSWORD="secret")

    kwargs = main.create_redis_client(config).connection_pool.connection_kwargs

    assert (kwargs["host"], kwargs["port"], kwargs["db"]) == ("redis-host", 6380, 2)
    assert (kwargs["username"], kwargs["password"]) == ("worker", "secret")
    assert kwargs["decode_responses"] is True
    assert kwargs["socket_timeout"] > main.READ_BLOCK_MS / 1000


def test_create_redis_client_sends_no_password_when_empty():
    kwargs = main.create_redis_client(Config(REDIS_PASSWORD="")).connection_pool.connection_kwargs

    assert kwargs["password"] is None


def test_consumer_name_is_host_and_pid():
    assert main.consumer_name() == f"{socket.gethostname()}-{os.getpid()}"


# ---------------------------------------------------------------- 실패 케이스


@pytest.mark.parametrize("error", [ModelArtifactError("missing"), FileNotFoundError("missing")])
def test_main_returns_1_when_bundle_cannot_be_loaded(monkeypatch, error):
    def _fail() -> None:
        raise error

    def _unexpected_redis(_config: Config) -> None:
        raise AssertionError("Redis must not be used when the bundle fails to load")

    monkeypatch.setattr(main, "KnhanesRiskPredictor", _fail)
    monkeypatch.setattr(main, "create_redis_client", _unexpected_redis)

    assert main.main() == 1
