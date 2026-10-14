from __future__ import annotations

import json
import threading
import time
from functools import lru_cache
from typing import Any

from app.config import CACHE_KEY_PREFIX, LAB7_CACHE_BACKEND, REDIS_URL
from app.shared.logging_config import get_logger

logger = get_logger("cache")


class JsonCache:
    def get(self, key: str) -> dict[str, Any] | list[Any] | None:
        raise NotImplementedError

    def set(self, key: str, value: dict[str, Any] | list[Any], ttl_seconds: int) -> None:
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> int:
        raise NotImplementedError


class NullJsonCache(JsonCache):
    def get(self, key):
        return None

    def set(self, key, value, ttl_seconds):
        return None

    def delete_prefix(self, prefix):
        return 0


class InMemoryJsonCache(JsonCache):
    def __init__(self):
        self._values: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key):
        now = time.time()
        with self._lock:
            item = self._values.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            return json.loads(json.dumps(value))

    def set(self, key, value, ttl_seconds):
        with self._lock:
            self._values[key] = (time.time() + ttl_seconds, json.loads(json.dumps(value)))

    def delete_prefix(self, prefix):
        with self._lock:
            keys = [k for k in self._values if k.startswith(prefix)]
            for key in keys:
                self._values.pop(key, None)
            return len(keys)


class RedisJsonCache(JsonCache):
    def __init__(self, url: str = REDIS_URL, key_prefix: str = CACHE_KEY_PREFIX):
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("redis package is required for Redis cache") from exc
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.key_prefix = key_prefix.rstrip(":")

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def get(self, key):
        raw = self.client.get(self._key(key))
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key, value, ttl_seconds):
        self.client.setex(self._key(key), ttl_seconds, json.dumps(value, ensure_ascii=False))

    def delete_prefix(self, prefix):
        pattern = self._key(prefix) + "*"
        deleted = 0
        for key in self.client.scan_iter(match=pattern, count=100):
            deleted += int(self.client.delete(key))
        return deleted


@lru_cache(maxsize=1)
def get_cache() -> JsonCache:
    backend = LAB7_CACHE_BACKEND.lower()
    if backend == "memory":
        return InMemoryJsonCache()
    if backend == "none":
        return NullJsonCache()
    return RedisJsonCache()


def cache_get(key: str):
    try:
        value = get_cache().get(key)
        logger.info("cache hit" if value is not None else "cache miss", extra={"operation": key})
        return value
    except Exception as exc:
        logger.warning("cache read failed; continuing without cache", extra={"operation": key, "error_type": type(exc).__name__})
        return None


def cache_set(key: str, value, ttl_seconds: int):
    try:
        get_cache().set(key, value, ttl_seconds)
        logger.info("cache set", extra={"operation": key})
    except Exception as exc:
        logger.warning("cache write failed; continuing without cache", extra={"operation": key, "error_type": type(exc).__name__})


def cache_delete_prefix(prefix: str) -> int:
    try:
        deleted = get_cache().delete_prefix(prefix)
        logger.info("cache invalidated", extra={"operation": prefix})
        return deleted
    except Exception as exc:
        logger.warning("cache invalidation failed", extra={"operation": prefix, "error_type": type(exc).__name__})
        return 0
