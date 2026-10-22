import logging
from collections.abc import Iterable
from functools import lru_cache
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.cache import EPOCH_FIELD, ResponseCache
from app.core.config import settings

logger = logging.getLogger(__name__)

REDIS_ERRORS = (RedisError, OSError, TimeoutError)
SOCKET_TIMEOUT_SECONDS = 1.0
INVALIDATE_ATTEMPTS = 2


class RedisResponseCache:
    def __init__(self, url: str, prefix: str) -> None:
        self._redis = Redis.from_url(
            url,
            socket_timeout=SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=SOCKET_TIMEOUT_SECONDS,
            health_check_interval=30,
        )
        self._versions_key = f"{prefix}:versions"

    async def lookup(self, key: str) -> tuple[bytes | None, dict[str, str] | None]:
        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.get(key)
                pipe.hgetall(self._versions_key)
                entry, raw_versions = await pipe.execute()
            versions = _decode(raw_versions)
            if EPOCH_FIELD not in versions:
                await self._redis.hsetnx(self._versions_key, EPOCH_FIELD, uuid4().hex)
                return None, _decode(await self._redis.hgetall(self._versions_key))
        except REDIS_ERRORS:
            logger.warning("Response cache lookup failed", exc_info=True)
            return None, None
        return entry, versions

    async def store(self, key: str, value: bytes, ttl: int) -> None:
        try:
            await self._redis.set(key, value, ex=ttl)
        except REDIS_ERRORS:
            logger.warning("Response cache store failed", exc_info=True)

    async def invalidate(self, names: Iterable[str]) -> None:
        names = sorted(set(names))
        if not names:
            return
        for attempt in range(1, INVALIDATE_ATTEMPTS + 1):
            try:
                async with self._redis.pipeline(transaction=False) as pipe:
                    for name in names:
                        pipe.hincrby(self._versions_key, name, 1)
                    await pipe.execute()
                return
            except REDIS_ERRORS:
                if attempt == INVALIDATE_ATTEMPTS:
                    logger.error("Response cache invalidation failed for %s", names, exc_info=True)


def _decode(raw: dict[bytes, bytes]) -> dict[str, str]:
    return {key.decode(): value.decode() for key, value in raw.items()}


@lru_cache
def get_response_cache() -> ResponseCache | None:
    if not settings.redis_url:
        return None
    return RedisResponseCache(settings.redis_url, settings.app_name)
