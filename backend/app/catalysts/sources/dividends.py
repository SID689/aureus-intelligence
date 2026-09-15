"""
Ex-dividend dates — Polygon's dividends reference endpoint.

Finnhub's dividend endpoint is paid on this key (HTTP 403, measured
2026-09-14); Polygon's is free but shares Polygon's 5-calls/minute limit
with price bars. So dividends are fetched per ticker on demand only, cached
for days, and skipped outright if the Polygon minute is spent — a dividend
date is the lowest-value catalyst here and must never cost a user a chart.
"""

from datetime import date, timedelta

import httpx

from app.catalysts.models import Catalyst
from app.catalysts.sources._finnhub import SourceUnavailable
from app.core.config import get_settings
from app.ingestion.rate_limiter import RedisTokenBucket

# The SAME Redis key market_data.py uses ("ratelimit:polygon_api"), so this
# draws from the one shared Polygon budget rather than a second, parallel
# allowance that would let the two together exceed the provider's limit.
_polygon_bucket = RedisTokenBucket("polygon_api", max_calls=5, window_seconds=60)

_FREQUENCY = {0: "one-time", 1: "annual", 2: "semi-annual", 4: "quarterly",
              12: "monthly", 24: "twice-monthly", 52: "weekly"}


def fetch_dividend_catalysts(ticker: str, *, window_days: int = 150,
                             today: date | None = None) -> list[Catalyst]:
    today = today or date.today()
    key = get_settings().polygon_api_key
    if not key:
        raise SourceUnavailable("POLYGON_API_KEY is not configured")
    if not _polygon_bucket.allow():
        raise SourceUnavailable("Polygon minute budget in use by price data")

    try:
        r = httpx.get(
            "https://api.polygon.io/v3/reference/dividends",
            params={"ticker": ticker.upper(), "limit": 8, "order": "desc", "sort": "ex_dividend_date"},
            headers={"Authorization": f"Bearer {key}"},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"Polygon unreachable: {type(exc).__name__}") from exc
    if r.status_code >= 400:
        raise SourceUnavailable(f"Polygon HTTP {r.status_code}")

    lo, hi = today - timedelta(days=window_days), today + timedelta(days=window_days)
    out: list[Catalyst] = []
    for row in (r.json() or {}).get("results") or []:
        try:
            ex = date.fromisoformat(str(row.get("ex_dividend_date")))
        except ValueError:
            continue
        if not lo <= ex <= hi:
            continue
        amount = row.get("cash_amount")
        special = row.get("dividend_type") == "SC"
        freq = _FREQUENCY.get(row.get("frequency"), "")
        pay = row.get("pay_date")

        bits = []
        if isinstance(amount, (int, float)):
            bits.append(f"${amount:.2f}{(' ' + freq) if freq and not special else ''}")
        if pay:
            bits.append(f"pays {pay}")
        out.append(Catalyst(
            dedupe_key=f"dividend:{ticker.upper()}:{ex.isoformat()}:{row.get('dividend_type') or 'CD'}",
            scope="company", ticker=ticker, catalyst_type="dividend",
            title="Special dividend (ex-date)" if special else "Ex-dividend date",
            description=" · ".join(bits) or None,
            event_date=ex, date_confirmed=True,
            impact="medium" if special else "low", direction="neutral",
            source="polygon_dividends",
            details={"cash_amount": amount, "currency": row.get("currency"), "pay_date": pay,
                     "record_date": row.get("record_date"), "declaration_date": row.get("declaration_date"),
                     "frequency": row.get("frequency"), "dividend_type": row.get("dividend_type")},
        ))
    return out
