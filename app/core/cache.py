import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def cache_get(key: str) -> Any | None:
    r = await get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    r = await get_redis()
    await r.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_invalidate_prefix(prefix: str) -> int:
    r = await get_redis()
    count = 0
    async for key in r.scan_iter(match=f"{prefix}*", count=500):
        await r.delete(key)
        count += 1
    return count


def make_key(prefix: str, params: dict[str, Any]) -> str:
    canonical = json.dumps(params, sort_keys=True, default=str)
    h = hashlib.sha1(canonical.encode()).hexdigest()[:16]
    return f"{prefix}{h}"


async def invalidate_cars_cache() -> None:
    await cache_invalidate_prefix("cars:")
