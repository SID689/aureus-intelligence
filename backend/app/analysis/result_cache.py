"""
app/analysis/result_cache.py
----------------------------
A warm cache for completed analyses, keyed by ticker and horizon.

=====================================================================
WHY THIS EXISTS
=====================================================================
`GET /api/v1/analysis/quick/{ticker}` runs the whole ensemble inline:
prices, fundamentals, filings, news, sentiment, then two LLM syntheses.
That is five to fifteen seconds and a dozen provider calls, and until
now every caller paid all of it. Two people asking for AAPL within the
same minute ran the pipeline twice and got the same answer, because
nothing in the inputs had changed.

That is merely wasteful with a handful of users. In front of a room of
people who all open the same ticker at once it is fatal: thirty phones
means thirty pipeline runs, Finnhub's sixty-a-minute is gone in the
first ten seconds, and the rest of the room watches a spinner resolve
into an error.

So a completed run is cached under the ticker, and subsequent callers
are served from it. One pipeline run, one set of provider calls, the
whole room answered in milliseconds.

=====================================================================
WHY THE TTL IS SHORT OUTSIDE A DEMO
=====================================================================
Analysis output is a claim about right now. Three minutes is long enough
to absorb a double-tap, a remount, or a room full of phones, and short
enough that nobody is shown a verdict formed before a move they can see
on the chart beside it. A demo deployment raises it to hours, because
there the cost of a cold run is a visible stall in front of an audience
and the cost of a slightly old snapshot is nothing.

=====================================================================
DEGRADATION ORDER
=====================================================================
    fresh cache  ->  live pipeline  ->  stale cache  ->  bundled snapshot

A stale entry beats an error page: an analysis from twenty minutes ago
is still informative, a 503 is not. The bundled snapshot is last, is
only consulted in demo mode, and is always labelled.

Every read and write is wrapped: a Redis outage must slow this app down,
never break it.
"""

import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("aureus.analysis.cache")

# Entries older than the fresh TTL are kept for this much longer, as the
# fallback for a failed live run. Deliberately generous: the alternative
# to a forty-minute-old analysis is no analysis.
_STALE_GRACE_SECONDS = 3600


def _key(ticker: str, horizon: str) -> str:
    return f"analysis_warm:{ticker.upper()}:{horizon}"


def _redis():
    from app.core.redis_client import get_redis_client
    return get_redis_client()


def store(ticker: str, horizon: str, payload: dict[str, Any]) -> None:
    """Cache a completed analysis. Never raises."""
    settings = get_settings()
    try:
        _redis().setex(
            _key(ticker, horizon),
            settings.analysis_cache_ttl + _STALE_GRACE_SECONDS,
            json.dumps({"fresh_for": settings.analysis_cache_ttl, "payload": payload}, default=str),
        )
    except Exception as exc:
        logger.warning("Analysis cache write failed", extra={"ticker": ticker, "error": str(exc)})


def _read(ticker: str, horizon: str) -> tuple[dict[str, Any], int] | None:
    """The cached payload and its remaining lifetime in seconds."""
    try:
        redis = _redis()
        key = _key(ticker, horizon)
        raw = redis.get(key)
        if raw is None:
            return None
        ttl = int(redis.ttl(key) or 0)
        entry = json.loads(raw)
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            return None
        return payload, max(0, ttl - _STALE_GRACE_SECONDS) if ttl > _STALE_GRACE_SECONDS else 0
    except Exception as exc:
        logger.warning("Analysis cache read failed", extra={"ticker": ticker, "error": str(exc)})
        return None


def fresh(ticker: str, horizon: str) -> dict[str, Any] | None:
    """A cached analysis still inside its TTL, or None."""
    hit = _read(ticker, horizon)
    if hit is None:
        return None
    payload, remaining = hit
    if remaining <= 0:
        return None
    return payload


def fallback(ticker: str, horizon: str) -> tuple[dict[str, Any], str] | None:
    """
    Something to serve when the live run failed.

    Returns the payload and the source label, or None when there is
    genuinely nothing to show.
    """
    hit = _read(ticker, horizon)
    if hit is not None:
        return hit[0], "stale_cache"

    if get_settings().demo_mode:
        from app.demo.fixtures import load_analysis
        snapshot = load_analysis(ticker, horizon)
        if snapshot is not None:
            return snapshot, "showcase_snapshot"
    return None


def prime(ticker: str, horizon: str) -> dict[str, Any] | None:
    """
    The bundled snapshot, for warming a cold deployment before anyone
    arrives. Only meaningful in demo mode; returns None otherwise.
    """
    if not get_settings().demo_mode:
        return None
    from app.demo.fixtures import load_analysis
    payload = load_analysis(ticker, horizon)
    if payload is not None:
        store(ticker, horizon, payload)
    return payload
