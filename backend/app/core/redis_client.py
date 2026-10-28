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
from urllib.parse import urlsplit, urlunsplit

import redis

from app.core.config import get_settings

logger = logging.getLogger("aureus.redis")


def safe_url(url: str) -> str:
    """
    A connection URL with the password removed, for logging.

    Managed Redis hands you credentials inside the URL, so logging the
    URL logs the password into whatever collects the service's output.
    The host and port are the parts worth seeing when a connection fails;
    the secret never is.
    """
    try:
        parts = urlsplit(url)
        if parts.password:
            user = parts.username or ""
            netloc = f"{user}:***@{parts.hostname}" if user else f"***@{parts.hostname}"
            if parts.port:
                netloc += f":{parts.port}"
            return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:  # noqa: BLE001
        # Never let a logging helper be the thing that breaks startup.
        return "<unparseable redis url>"


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
    target = safe_url(settings.redis_url)
    try:
        client.ping()
        logger.info("Redis connection established", extra={"redis": target})
    except redis.ConnectionError as exc:
        # Name the host that was actually tried. "Redis unreachable" on its
        # own sends you looking at the Redis provider when the usual cause
        # is REDIS_URL being unset, which leaves the compose service name
        # `redis` as the target and that resolves nowhere else.
        #
        # The second hint is for managed Redis, which is TLS-only. A
        # plaintext connection to a TLS endpoint is not refused, it is
        # ACCEPTED and then dropped, so the error reads "Connection closed
        # by server" and says nothing about encryption. One missing letter
        # in the scheme, and nothing in the stack trace points at it.
        hint = ""
        if settings.redis_url.startswith("redis://") and "closed by server" in str(exc).lower():
            hint = (" The server accepted the connection and then closed it, which is what a "
                    "TLS-only endpoint does when reached in plaintext. Try rediss:// instead.")
        logger.error("Redis connection failed, rate limiting and caching unavailable%s" % hint,
                     extra={"redis": target, "error": str(exc)})
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
