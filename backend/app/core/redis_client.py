"""
app/core/redis_client.py
------------------------
Provides a single shared Redis connection pool for the entire process.
Used for:
  - Caching resolved tier limits (subscription_tiers lookup)
  - Storing rate-limit counters (usage_counters hot path)
  - Celery broker/result backend (configured in celery_app.py, not here)
  - Pub/sub channel for SSE alerts (future Phase)
"""

import logging
from functools import lru_cache

import redis

from app.core.config import get_settings

logger = logging.getLogger("aureus.redis")


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """
    Returns a thread-safe Redis client backed by a connection pool.
    The pool is created once per process and reused across all calls.
    decode_responses=True means all keys/values come back as str, not bytes.
    """
    settings = get_settings()
    client = redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    try:
        client.ping()
        logger.info("Redis connection established", extra={"url": settings.redis_url})
    except redis.ConnectionError as exc:
        logger.error("Redis connection failed, rate limiting and caching unavailable", extra={"error": str(exc)})
        raise
    return client


def cache_set(key: str, value: str, ttl_seconds: int = 300) -> None:
    """
    Write a string value to Redis with a TTL.
    Fails silently — callers should not crash if the cache is unavailable.
    """
    try:
        get_redis_client().setex(key, ttl_seconds, value)
    except Exception as exc:
        logger.warning("Cache write failed", extra={"key": key, "error": str(exc)})


def cache_get(key: str) -> str | None:
    """
    Read a string value from Redis.
    Returns None on cache miss or connection failure.
    """
    try:
        return get_redis_client().get(key)
    except Exception as exc:
        logger.warning("Cache read failed", extra={"key": key, "error": str(exc)})
        return None


def increment_counter(key: str, ttl_seconds: int = 86400) -> int:
    """
    Atomically increment an integer counter in Redis and return the new value.
    Sets a TTL on first creation (SETEX semantics for counters via INCR + EXPIRE).
    Used for usage_counters hot-path rate-limit checks without a Postgres roundtrip.
    """
    try:
        client = get_redis_client()
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl_seconds)
        results = pipe.execute()
        return int(results[0])
    except Exception as exc:
        logger.warning("Counter increment failed", extra={"key": key, "error": str(exc)})
        return 0
