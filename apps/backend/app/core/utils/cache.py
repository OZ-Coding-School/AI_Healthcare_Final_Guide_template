"""
Redis 캐시 공통 도구입니다.

Cache Stampede 방지: 같은 시점에 만든 캐시가 한꺼번에 만료되면 요청이 동시에 DB로 몰립니다.
TTL에 무작위 값을 더해(Randomized TTL) 만료 시점을 흩어 놓습니다.
"""

import random


def jittered_ttl(base_seconds: int, jitter_ratio: float) -> int:
    """기본 TTL에 0 ~ base_seconds × jitter_ratio초를 무작위로 더한 TTL을 반환합니다."""
    if base_seconds <= 0:
        raise ValueError("base_seconds must be positive.")
    if jitter_ratio < 0:
        raise ValueError("jitter_ratio must not be negative.")
    return base_seconds + random.randint(0, int(base_seconds * jitter_ratio))
