"""
Singleton Redis client for use across the application.

Supports:
- Graceful fallback when Redis is not configured
- Shared connection pool for API and Engine processes
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("shared.redis")

_redis_client: Optional[object] = None
_redis_available: bool = False


class MockRedis:
    """In-memory Redis mock for development without a Redis server."""

    def __init__(self):
        self._data: dict = {}
        self._lists: dict = {}
        self._sets: dict = {}
        logger.warning("⚠️  Redis not configured — using in-memory MockRedis (not production-safe)")

    async def ping(self) -> bool:
        return True

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value, ex: int = None):
        self._data[key] = value
        return True

    async def setex(self, key: str, ttl: int, value):
        self._data[key] = value
        return True

    async def delete(self, *keys):
        for k in keys:
            self._data.pop(k, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    async def expire(self, key: str, seconds: int) -> bool:
        return key in self._data

    async def lpush(self, key: str, *values):
        if key not in self._lists:
            self._lists[key] = []
        for v in values:
            self._lists[key].insert(0, v)
        return len(self._lists[key])

    async def rpush(self, key: str, *values):
        if key not in self._lists:
            self._lists[key] = []
        for v in values:
            self._lists[key].append(v)
        return len(self._lists[key])

    async def brpop(self, key: str, timeout: int = 0):
        import asyncio
        lst = self._lists.get(key, [])
        if lst:
            return (key, lst.pop())
        if timeout:
            await asyncio.sleep(min(timeout, 0.5))
        return None

    async def llen(self, key: str) -> int:
        return len(self._lists.get(key, []))

    async def hset(self, name: str, key: str, value):
        if name not in self._data:
            self._data[name] = {}
        self._data[name][key] = value

    async def hget(self, name: str, key: str):
        return self._data.get(name, {}).get(key)

    async def hgetall(self, name: str) -> dict:
        return dict(self._data.get(name, {}))

    async def scard(self, key: str) -> int:
        return len(self._sets.get(key, set()))

    async def sadd(self, key: str, *members):
        if key not in self._sets:
            self._sets[key] = set()
        self._sets[key].update(members)

    async def srem(self, key: str, *members):
        if key in self._sets:
            self._sets[key].difference_update(members)

    async def smembers(self, key: str) -> set:
        return set(self._sets.get(key, set()))


async def get_redis():
    """
    Returns the Redis client singleton.
    Falls back to MockRedis if REDIS_URL is not set or Redis is unreachable.
    """
    global _redis_client, _redis_available

    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        # In production, Redis is mandatory
        app_mode = os.getenv("APP_MODE", "dev")
        if app_mode in ("production", "prod"):
            raise RuntimeError(
                "REDIS_URL is required in production mode. "
                "Set REDIS_URL or change APP_MODE to 'dev'."
            )
        _redis_client = MockRedis()
        _redis_available = False
        return _redis_client

    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            # socket_timeout omitido: brpop usa timeout>3 e conflitaria
        )
        await client.ping()
        _redis_client = client
        _redis_available = True
        logger.info(f"✅ Redis conectado: {redis_url}")
    except Exception as e:
        logger.warning(f"⚠️  Falha ao conectar Redis ({e}) — usando MockRedis")
        _redis_client = MockRedis()
        _redis_available = False

    return _redis_client


def is_redis_available() -> bool:
    return _redis_available


async def close_redis():
    """Close the Redis connection on shutdown."""
    global _redis_client, _redis_available
    if _redis_available and _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
    _redis_client = None
    _redis_available = False
