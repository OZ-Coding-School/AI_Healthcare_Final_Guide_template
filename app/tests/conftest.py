import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import Mock, patch

import fakeredis
import pytest
import pytest_asyncio
from _pytest.fixtures import FixtureRequest
from tortoise import generate_config
from tortoise.contrib.test import finalizer, initializer

from app.core import settings
from app.core.db.databases import TORTOISE_APP_MODELS
from app.core.utils.redis import get_redis
from app.main import app

TEST_BASE_URL = "http://test"
TEST_DB_LABEL = "models"
TEST_DB_TZ = "Asia/Seoul"


def get_test_db_config() -> dict[str, Any]:
    tortoise_config = generate_config(
        db_url=f"asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/test",
        app_modules={TEST_DB_LABEL: TORTOISE_APP_MODELS},
        connection_label=TEST_DB_LABEL,
        testing=True,
    )
    tortoise_config["timezone"] = TEST_DB_TZ

    return tortoise_config


@pytest.fixture(scope="session", autouse=True)
def initialize(request: FixtureRequest) -> Generator[None, None]:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with patch("tortoise.contrib.test.getDBConfig", Mock(return_value=get_test_db_config())):
        initializer(modules=TORTOISE_APP_MODELS)
    yield
    finalizer()
    loop.close()


@pytest_asyncio.fixture(autouse=True, scope="session")  # type: ignore[type-var]
def event_loop() -> None:
    pass


@pytest.fixture(autouse=True)
async def fake_redis() -> AsyncGenerator[fakeredis.FakeAsyncRedis, None]:
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    # 팩토리 함수를 사용하여 항상 같은 FakeAsyncRedis 인스턴스를 반환하도록 오버라이드
    app.dependency_overrides[get_redis] = lambda: redis

    # 전역 get_redis도 모킹하여 서비스 내에서 직접 호출할 때도 가짜 객체를 반환하게 함
    with patch("app.core.utils.redis.get_redis", return_value=redis):
        yield redis

    await redis.aclose()
    app.dependency_overrides.clear()
