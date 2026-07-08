import redis.asyncio as redis

from app.core import settings

redis_pool: redis.ConnectionPool | None = None


def initialize_redis_pool() -> None:
    global redis_pool
    redis_pool = redis.ConnectionPool.from_url(
        url=settings.REDIS_URL,
        max_connections=settings.REDIS_MAX_CONNECTION,
        decode_responses=True,
    )


async def close_redis_pool() -> None:
    global redis_pool
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None


def get_redis() -> redis.Redis:
    if redis_pool is None:
        raise RuntimeError("Redis pool has not been initialized.")

    return redis.Redis(connection_pool=redis_pool)
