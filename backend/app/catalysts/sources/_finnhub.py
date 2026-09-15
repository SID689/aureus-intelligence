"""
Shared Finnhub access for catalyst sources.

Catalysts draw from their OWN token bucket rather than the one analysis
requests use. The market-wide refresh is a batch job; if it shared a budget
with interactive traffic, the nightly earnings sweep could starve a user's
analysis request of Finnhub calls at exactly the moment they are waiting.
Twenty calls a minute leaves two-thirds of the free tier's 60 for people.
"""

import time

import httpx

from app.core.config import get_settings
from app.ingestion.rate_limiter import RedisTokenBucket

FINNHUB_BASE = "https://finnhub.io/api/v1"

_bucket = RedisTokenBucket("finnhub_catalysts", max_calls=20, window_seconds=60)


class SourceUnavailable(Exception):
    """The source could not be reached or refused us. Callers degrade, never crash."""


def finnhub_get(path: str, params: dict | None = None, *, wait_seconds: float = 0.0) -> object:
    """
    GET a Finnhub endpoint within the catalyst budget.

    `wait_seconds` is how long to wait for budget. The request path passes
    0 and serves whatever is cached; batch jobs pass ~65 and simply pace
    themselves across the minute boundary.
    """
    key = get_settings().finnhub_api_key
    if not key:
        raise SourceUnavailable("FINNHUB_API_KEY is not configured")

    deadline = time.monotonic() + wait_seconds
    while not _bucket.allow():
        if time.monotonic() >= deadline:
            raise SourceUnavailable("catalyst call budget exhausted for this minute")
        time.sleep(2.0)

    try:
        # Header, not the ?token= query parameter, so the key never lands in
        # an access log or an exception message that echoes the URL.
        r = httpx.get(f"{FINNHUB_BASE}{path}", params=params or {},
                      headers={"X-Finnhub-Token": key}, timeout=20.0)
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"Finnhub unreachable: {type(exc).__name__}") from exc
    if r.status_code == 429:
        raise SourceUnavailable("Finnhub rate limit")
    if r.status_code == 403:
        raise SourceUnavailable(f"Finnhub denied {path} on this plan")
    if r.status_code >= 400:
        raise SourceUnavailable(f"Finnhub HTTP {r.status_code} on {path}")
    try:
        return r.json()
    except ValueError as exc:
        raise SourceUnavailable("Finnhub returned non-JSON") from exc
