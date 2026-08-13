"""
app/ingestion/rate_limiter.py
-----------------------------
Exponential back-off with full jitter for all external API calls.

Math:
  base_delay: the initial wait after the first failure (seconds)
  attempt:    0-indexed retry count (0 = first retry after initial fail)
  jitter:     random value in [0, base_delay] — prevents thundering herd
              when many workers hit the same rate limit simultaneously

  sleep_time = min(base_delay * 2^attempt, max_delay) + uniform(0, base_delay)

This is the "Full Jitter" strategy from the AWS Architecture Blog, which
produces the lowest average wait while still preventing coordinated retry storms.

Usage:
    @with_exponential_backoff(max_retries=5, retryable=(RateLimitError,))
    def fetch_polygon_bars(ticker: str) -> pd.DataFrame:
        ...
"""

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger("aureus.rate_limiter")

T = TypeVar("T")


# ── Custom exception hierarchy ─────────────────────────────────────────────────

class AureusAPIError(Exception):
    """Base class for all external-API errors raised inside Aureus."""
    def __init__(self, message: str, status_code: int | None = None, provider: str = "unknown"):
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider


class RateLimitError(AureusAPIError):
    """HTTP 429 Too Many Requests from any external provider."""
    pass


class ProviderUnavailableError(AureusAPIError):
    """HTTP 5xx or connection failure — provider is down, not us."""
    pass


class ProviderBudgetExhausted(AureusAPIError):
    """
    Our OWN pre-flight budget check refused the call — no request was made.

    Deliberately NOT in the default `retryable` tuple, and that distinction is
    the whole point of the class. RateLimitError means the REMOTE service
    pushed back, so waiting and retrying is sensible. This means our local
    token bucket knows the minute's quota is already spent, so retrying can
    only sleep through a budget that is not coming back within the retry
    window — while the caller has a perfectly good fallback provider sitting
    right there.

    Raising a retryable error here defeated the token bucket entirely: the
    bucket was added so an exhausted quota falls through to the next provider
    INSTANTLY, but the backoff decorator caught it and slept ~60s across four
    retries first. That was the dominant cost in cold analysis latency.
    """
    pass


class DataNotFoundError(AureusAPIError):
    """Provider responded successfully but returned no data for the request."""
    pass


class FallbackExhaustedError(Exception):
    """
    Raised when every provider in the fallback chain has failed.
    The caller should surface this to the API layer as a 503 with a clear message.
    """
    def __init__(self, ticker: str, attempted_providers: list[str]):
        self.ticker = ticker
        self.attempted_providers = attempted_providers
        super().__init__(
            f"All data providers exhausted for {ticker}: "
            + ", ".join(attempted_providers)
        )


# ── Decorator ──────────────────────────────────────────────────────────────────

def with_exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable: tuple[type[Exception], ...] = (RateLimitError, ProviderUnavailableError),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator factory that wraps any synchronous function with retry logic.

    Args:
        max_retries:  Maximum number of retry attempts (not counting the initial try).
        base_delay:   Base wait time in seconds before first retry.
        max_delay:    Hard ceiling on any single sleep, regardless of attempt number.
        retryable:    Tuple of exception types that should trigger a retry.
                      All other exceptions propagate immediately.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: Exception | None = None

            for attempt in range(max_retries + 1):  # attempt 0 = initial try
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(
                            "Succeeded after retry",
                            extra={"func": func.__name__, "attempt": attempt},
                        )
                    return result

                except retryable as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        logger.error(
                            "Max retries exhausted",
                            extra={
                                "func": func.__name__,
                                "max_retries": max_retries,
                                "error": str(exc),
                            },
                        )
                        raise

                    # Full-jitter sleep
                    exponential_cap = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0, base_delay)
                    sleep_time = exponential_cap + jitter

                    logger.warning(
                        "Retryable error — backing off",
                        extra={
                            "func": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "sleep_seconds": round(sleep_time, 3),
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                    time.sleep(sleep_time)

                except Exception:
                    # Non-retryable: propagate immediately without sleeping
                    raise

            # Unreachable, but satisfies mypy
            assert last_exc is not None
            raise last_exc

        return wrapper
    return decorator


# ── Helper: classify HTTP status codes into exception types ────────────────────

class RedisTokenBucket:
    """
    Distributed rate limiter shared across all Celery workers and API
    processes, backed by Redis. Used to keep Polygon's free-tier 5-calls/min
    limit from being silently exhausted — instead of making a doomed call
    and waiting for a 429, callers check `allow()` first and skip straight
    to the fallback provider if the bucket is empty. This is what makes
    "mostly use Polygon" actually sustainable instead of burning the free
    quota on the first few chart loads and falling back to YFinance for
    the rest of the session.

    Implementation: fixed-window counter (INCR + EXPIRE) — simple, and
    good enough at this call volume.
    """

    def __init__(self, key: str, max_calls: int, window_seconds: int):
        self.key = f"ratelimit:{key}"
        self.max_calls = max_calls
        self.window_seconds = window_seconds

    def allow(self) -> bool:
        """Returns True if a call is permitted right now, and consumes one slot if so."""
        try:
            from app.core.redis_client import get_redis_client
            client = get_redis_client()
            current = client.incr(self.key)
            if current == 1:
                client.expire(self.key, self.window_seconds)
            return current <= self.max_calls
        except Exception:
            return True  # fail open if Redis itself is unavailable

    def remaining(self) -> int:
        try:
            from app.core.redis_client import get_redis_client
            current = int(get_redis_client().get(self.key) or 0)
            return max(0, self.max_calls - current)
        except Exception:
            return self.max_calls


def raise_for_status(status_code: int, body: str, provider: str) -> None:
    """
    Map an HTTP error response to the correct Aureus exception type.
    Call this after every HTTP request in the ingestion layer.
    """
    if status_code == 429:
        raise RateLimitError(
            f"{provider} rate limit hit (429): {body[:200]}",
            status_code=429,
            provider=provider,
        )
    if status_code in (500, 502, 503, 504):
        raise ProviderUnavailableError(
            f"{provider} server error ({status_code}): {body[:200]}",
            status_code=status_code,
            provider=provider,
        )
    if status_code >= 400:
        raise AureusAPIError(
            f"{provider} client error ({status_code}): {body[:200]}",
            status_code=status_code,
            provider=provider,
        )
