"""
챌린지 캐시 저장소와 TTL 도구를 DB 없이 fakeredis로 검증합니다.
"""

from unittest.mock import patch
from uuid import uuid4

import fakeredis
import pytest
from redis.exceptions import RedisError

from app.core import settings
from app.core.enums import ChallengeStatus
from app.core.utils.cache import jittered_ttl
from app.repositories.challenge_cache_repository import ChallengeCacheRepository


@pytest.fixture
def redis_client() -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis(decode_responses=True)


class BrokenRedis:
    """모든 명령이 RedisError를 내는 Redis입니다 (장애 상황)."""

    def __getattr__(self, name: str):
        def fail(*args, **kwargs):
            raise RedisError("connection refused")

        return fail


def test_jittered_ttl_stays_within_range() -> None:
    values = {jittered_ttl(100, 0.2) for _ in range(500)}

    assert min(values) >= 100
    assert max(values) <= 120
    assert len(values) > 1  # 만료 시점이 흩어집니다.


def test_jittered_ttl_without_jitter_and_invalid_values() -> None:
    assert jittered_ttl(60, 0) == 60
    with pytest.raises(ValueError):
        jittered_ttl(0, 0.2)
    with pytest.raises(ValueError):
        jittered_ttl(60, -0.1)


async def test_recommendation_cache_round_trip_with_randomized_ttl(redis_client) -> None:
    cache = ChallengeCacheRepository(redis_client)
    user_id, prediction_id = uuid4(), uuid4()

    assert await cache.get_recommendation(user_id, prediction_id) is None
    await cache.set_recommendation(user_id, prediction_id, '{"status": "COMPLETED"}')

    assert await cache.get_recommendation(user_id, prediction_id) == '{"status": "COMPLETED"}'
    ttl = await redis_client.ttl(f"challenge:recommendation:{user_id}:{prediction_id}")
    base = settings.CHALLENGE_RECOMMENDATION_CACHE_TTL_SECONDS
    assert base - 1 <= ttl <= base * (1 + settings.CACHE_TTL_JITTER_RATIO)

    await cache.delete_recommendation(user_id, prediction_id)
    assert await cache.get_recommendation(user_id, prediction_id) is None


async def test_recommendation_cache_is_separated_by_user(redis_client) -> None:
    cache = ChallengeCacheRepository(redis_client)
    prediction_id = uuid4()
    await cache.set_recommendation(uuid4(), prediction_id, "owner")

    assert await cache.get_recommendation(uuid4(), prediction_id) is None


async def test_list_cache_is_invalidated_by_version(redis_client) -> None:
    cache = ChallengeCacheRepository(redis_client)
    user_id = uuid4()

    version, cached = await cache.get_list(user_id, None)
    assert (version, cached) == (0, None)
    await cache.set_list(user_id, version, None, "[all]")
    await cache.set_list(user_id, version, ChallengeStatus.PENDING, "[pending]")
    assert await cache.get_list(user_id, None) == (0, "[all]")
    assert await cache.get_list(user_id, ChallengeStatus.PENDING) == (0, "[pending]")

    await cache.invalidate_list(user_id)

    # 상태 필터와 상관없이 이전 버전의 목록 캐시를 더 이상 읽지 않습니다.
    assert await cache.get_list(user_id, None) == (1, None)
    assert await cache.get_list(user_id, ChallengeStatus.PENDING) == (1, None)
    assert await redis_client.ttl(f"challenge:list:version:{user_id}") > 0


async def test_list_saved_with_old_version_is_not_read(redis_client) -> None:
    """조회와 저장 사이에 무효화되면, 늦게 저장된 이전 목록은 읽히지 않아야 합니다."""
    cache = ChallengeCacheRepository(redis_client)
    user_id = uuid4()
    version, _ = await cache.get_list(user_id, None)

    await cache.invalidate_list(user_id)
    await cache.set_list(user_id, version, None, "[stale]")

    assert await cache.get_list(user_id, None) == (1, None)


async def test_redis_errors_are_treated_as_cache_miss() -> None:
    cache = ChallengeCacheRepository(BrokenRedis())  # type: ignore[arg-type]
    user_id, prediction_id = uuid4(), uuid4()

    with patch("app.repositories.challenge_cache_repository.logger") as logger:
        assert await cache.get_recommendation(user_id, prediction_id) is None
        await cache.set_recommendation(user_id, prediction_id, "value")
        await cache.delete_recommendation(user_id, prediction_id)
        assert await cache.get_list(user_id, None) == (0, None)
        await cache.set_list(user_id, 0, None, "[]")
        await cache.invalidate_list(user_id)

    assert logger.warning.called
