"""
app/api/v1/market.py
----------------------
Real market data endpoints. THIS IS THE FIX for charts showing wrong/
outdated prices — the Phase 5 frontend chart was generating random-walk
mock data instead of calling a real endpoint. That gap is closed here:
the frontend now calls GET /api/v1/market/bars/{ticker} and gets back
genuine OHLCV data from the Polygon-first fallback chain, cached in Redis.
"""

import logging
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.ingestion.market_data import MarketDataService
from app.ingestion.rate_limiter import FallbackExhaustedError

logger = logging.getLogger("aureus.api.market")
router = APIRouter(prefix="/api/v1/market", tags=["market-data"])


@router.get("/bars/{ticker}")
def get_bars(
    ticker: str,
    days: int = Query(default=90, ge=5, le=1095),
    frequency: Literal["1d", "1h", "5m"] = Query(default="1d"),
) -> dict:
    """
    Return real OHLCV bars for a ticker, most recent `days` of history.
    Response shape matches what the frontend PriceChart component expects:
    an array of {timestamp, date, open, high, low, close, volume}.
    """
    ticker = ticker.upper().strip()
    end_date   = date.today()
    start_date = end_date - timedelta(days=days)

    try:
        svc    = MarketDataService()
        result = svc.fetch_bars(ticker, start_date, end_date, frequency=frequency)
    except FallbackExhaustedError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No market data available for {ticker}. Providers tried: {', '.join(exc.attempted_providers)}",
        )
    except Exception as exc:
        logger.error("Bars fetch failed", extra={"ticker": ticker, "error": str(exc)})
        raise HTTPException(status_code=500, detail="Market data fetch failed")

    df = result.bars.reset_index()
    bars = [
        {
            "timestamp": row["timestamp"].strftime("%b %d") if frequency == "1d" else row["timestamp"].strftime("%H:%M"),
            "date":      row["timestamp"].isoformat(),
            "open":      round(float(row["open"]), 4),
            "high":      round(float(row["high"]), 4),
            "low":       round(float(row["low"]), 4),
            "close":     round(float(row["close"]), 4),
            "volume":    int(row["volume"]),
        }
        for _, row in df.iterrows()
    ]

    return {
        "ticker":   ticker,
        "provider": result.provider,
        "frequency": frequency,
        "bars":     bars,
    }


@router.get("/price/{ticker}")
def get_latest_price(ticker: str) -> dict:
    """Return the latest known price for a ticker."""
    ticker = ticker.upper().strip()
    try:
        svc   = MarketDataService()
        price = svc.fetch_latest_price(ticker)
        return {"ticker": ticker, "price": round(price, 4)}
    except FallbackExhaustedError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No price available for {ticker}. Providers tried: {', '.join(exc.attempted_providers)}",
        )
