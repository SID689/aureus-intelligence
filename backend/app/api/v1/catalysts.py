"""
app/api/v1/catalysts.py
-------------------------
Catalyst timeline. Available on every plan: knowing that a company reports
in six days is basic risk information, not a premium insight.

GET  /api/v1/catalysts/{ticker}          timeline for one ticker
GET  /api/v1/catalysts/macro/upcoming    FOMC and other market-wide dates
POST /api/v1/catalysts/internal/refresh  enqueue the market-wide sweep (X-Internal-Secret)
"""

import hmac
import os
import re
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query

from app.catalysts import service
from app.ingestion.rate_limiter import RedisTokenBucket

router = APIRouter(prefix="/api/v1/catalysts", tags=["catalysts"])

_TICKER_RE = re.compile(r"^[A-Z]{1,5}([.\-][A-Z]{1,2})?$")

# A refresh spends provider calls, and an unknown ticker string is a fresh
# cache key every time. Per-caller and global ceilings keep a script
# walking random symbols from converting this endpoint into quota burn;
# over either limit the endpoint still answers, from stored data.
_GLOBAL_REFRESH = RedisTokenBucket("catalyst_refresh_global", max_calls=600, window_seconds=3600)


@router.get("/macro/upcoming")
def macro_upcoming(days: int = Query(default=90, ge=1, le=400)) -> dict:
    return {"items": service.macro_upcoming(days), "unavailable": service.UNAVAILABLE_SOURCES}


@router.get("/{ticker}")
def catalyst_timeline(
    ticker: str,
    user_id: str = Query(..., min_length=1),
    horizon: Literal["short_term", "medium_term", "long_term"] = Query(default="medium_term"),
    refresh: bool = Query(default=True),
) -> dict:
    t = ticker.upper().strip()
    if not _TICKER_RE.match(t):
        raise HTTPException(status_code=422, detail=f"'{ticker}' is not a valid ticker symbol")
    throttled = False
    if refresh and service.needs_refresh(t):
        caller = RedisTokenBucket(f"catalyst_refresh:{user_id[:64]}", max_calls=60, window_seconds=3600)
        if not (caller.allow() and _GLOBAL_REFRESH.allow()):
            refresh, throttled = False, True
    timeline = service.get_timeline(t, horizon, refresh=refresh)
    timeline["refresh_throttled"] = throttled
    return timeline


@router.post("/internal/refresh", status_code=202)
def internal_refresh(x_internal_secret: str = Header(default="")) -> dict:
    secret = os.getenv("INTERNAL_API_SECRET", "")
    if not secret or not hmac.compare_digest(secret, x_internal_secret):
        raise HTTPException(status_code=403, detail="Forbidden")
    from app.workers.scanner_tasks import refresh_catalysts_market_wide
    return {"enqueued": refresh_catalysts_market_wide.delay().id}
