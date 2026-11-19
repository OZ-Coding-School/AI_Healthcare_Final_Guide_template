"""
챌린지 조회 결과의 Redis Key-Value 캐시입니다. 값은 Response 스키마를 직렬화한 JSON 문자열입니다.

키
    challenge:recommendation:{user_id}:{prediction_id}        완료(COMPLETED)된 추천 조회 결과
    challenge:list:version:{user_id}                           사용자별 목록 캐시 버전 (변경 시 1 증가)
    challenge:list:{user_id}:v{version}:{status|all}           내 챌린지 목록

- 키에 사용자 ID를 넣어 다른 사용자의 캐시를 읽을 수 없게 합니다.
- 목록은 상태 필터마다 키가 달라, 지울 키를 찾는 대신 버전을 올려 이전 키를 더 이상 읽지 않게 합니다
  (SCAN·KEYS 없이 무효화, 이전 키는 TTL로 사라짐).
- Redis 장애는 캐시가 없는 것으로 처리합니다. 캐시 때문에 API가 실패하지 않습니다.
"""

from uuid import UUID

import redis.asyncio as redis
from fastapi import Depends
from redis.exceptions import RedisError

from app.core import logger, settings
from app.core.enums import ChallengeStatus
from app.core.utils.cache import jittered_ttl
from app.core.utils.redis import get_redis

RECOMMENDATION_KEY = "challenge:recommendation:{user_id}:{prediction_id}"
LIST_VERSION_KEY = "challenge:list:version:{user_id}"
LIST_KEY = "challenge:list:{user_id}:v{version}:{status}"
# 버전 키는 목록 캐시보다 오래 남아야 합니다. 사용하지 않는 사용자의 키는 이 기간 뒤 사라집니다.
LIST_VERSION_TTL_SECONDS = 7 * 24 * 60 * 60


class ChallengeCacheRepository:
    def __init__(self, redis_client: redis.Redis = Depends(get_redis)) -> None:
        self.redis = redis_client

    # ---------- 추천 조회 ----------

    async def get_recommendation(self, user_id: UUID, prediction_id: UUID) -> str | None:
        return await self._get(RECOMMENDATION_KEY.format(user_id=user_id, prediction_id=prediction_id))

    async def set_recommendation(self, user_id: UUID, prediction_id: UUID, payload: str) -> None:
        ttl = jittered_ttl(settings.CHALLENGE_RECOMMENDATION_CACHE_TTL_SECONDS, settings.CACHE_TTL_JITTER_RATIO)
        await self._set(RECOMMENDATION_KEY.format(user_id=user_id, prediction_id=prediction_id), payload, ttl)

    async def delete_recommendation(self, user_id: UUID, prediction_id: UUID) -> None:
        key = RECOMMENDATION_KEY.format(user_id=user_id, prediction_id=prediction_id)
        try:
            await self.redis.delete(key)
        except RedisError:
            logger.warning("Failed to delete challenge cache: %s", key)

    # ---------- 목록 ----------

    async def get_list(self, user_id: UUID, status: ChallengeStatus | None) -> tuple[int, str | None]:
        """현재 목록 버전과 캐시된 값을 반환합니다. set_list에는 여기서 받은 버전을 그대로 넘깁니다."""
        version = await self._get_list_version(user_id)
        return version, await self._get(_list_key(user_id, version, status))

    async def set_list(self, user_id: UUID, version: int, status: ChallengeStatus | None, payload: str) -> None:
        # 조회와 저장 사이에 버전이 올라갔다면 이전 버전 키에 저장되어 읽히지 않으므로 오래된 목록이 보이지 않습니다.
        ttl = jittered_ttl(settings.CHALLENGE_LIST_CACHE_TTL_SECONDS, settings.CACHE_TTL_JITTER_RATIO)
        await self._set(_list_key(user_id, version, status), payload, ttl)

    async def invalidate_list(self, user_id: UUID) -> None:
        """사용자의 챌린지가 추가·변경되면 호출합니다. 상태 필터별 목록 캐시가 모두 무효화됩니다."""
        key = LIST_VERSION_KEY.format(user_id=user_id)
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, LIST_VERSION_TTL_SECONDS)
                await pipe.execute()
        except RedisError:
            logger.warning("Failed to invalidate challenge list cache for user %s", user_id)

    # ---------- 내부 ----------

    async def _get_list_version(self, user_id: UUID) -> int:
        value = await self._get(LIST_VERSION_KEY.format(user_id=user_id))
        try:
            return int(value) if value is not None else 0
        except ValueError:
            return 0

    async def _get(self, key: str) -> str | None:
        try:
            value = await self.redis.get(key)
        except RedisError:
            logger.warning("Failed to read challenge cache: %s", key)
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    async def _set(self, key: str, payload: str, ttl: int) -> None:
        try:
            await self.redis.set(key, payload, ex=ttl)
        except RedisError:
            logger.warning("Failed to write challenge cache: %s", key)


def _list_key(user_id: UUID, version: int, status: ChallengeStatus | None) -> str:
    return LIST_KEY.format(user_id=user_id, version=version, status=status or "all")
