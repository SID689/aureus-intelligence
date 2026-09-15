"""
app/scanner/inputs.py
-----------------------
Where the scanner's data comes from.

The scoring functions are the analysis page's own (see engine.py). What
differs is only how the INPUTS are gathered, because gathering them the
page's way — one ticker at a time, every provider, every time — is exactly
what would exhaust the quotas.
"""

import json
import logging
import time
from dataclasses import asdict, fields
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from app.core.redis_client import get_redis_client
from app.ingestion.base import FundamentalDataResult, MarketDataResult
from app.scanner import HORIZONS

logger = logging.getLogger("aureus.scanner.inputs")

BATCH_SIZE = 100
_FUND_KEY = "scanner:fundamentals:v1:{}"
_FUND_TTL = 8 * 86400
_FUND_FIELDS = {f.name for f in fields(FundamentalDataResult)}


def provider_symbol(ticker: str) -> str:
    """BRK.B on the index and at Finnhub is BRK-B at Yahoo."""
    return ticker.replace(".", "-")


# ── Prices ────────────────────────────────────────────────────────────────

def _normalise(frame: pd.DataFrame) -> pd.DataFrame | None:
    """The same bar shape market_data._normalise_bars and the YFinance provider produce."""
    if frame is None or frame.empty:
        return None
    df = frame.copy()
    df.columns = [str(c).lower() for c in df.columns]
    cols = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    if "close" not in cols:
        return None
    df = df[cols].dropna(subset=["close"]).astype(float)
    if df.empty:
        return None
    idx = pd.DatetimeIndex(df.index)
    df.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    df.index.name = "timestamp"
    return df


def fetch_universe_bars(tickers: list[str], start: date, end: date) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """
    Daily bars for every ticker, 100 per request.

    Split-adjusted but NOT dividend-adjusted (auto_adjust=False), matching
    Polygon's adjusted=true bars, which are what the analysis page scores.
    Measured before this was set: with Yahoo's full dividend adjustment a
    three-year CVX window began 12% lower than Polygon's, every moving
    average shifted with it, and the scanner put CVX's technical pillar at
    82 where the page computed 65. Stocks without dividends matched to the
    decimal either way, which is how the difference hid.
    `end` is inclusive here: today's bar is the one that moves during a
    session, and a scanner that ignored it would be a day behind the page.
    """
    import yfinance as yf

    out: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for i in range(0, len(tickers), BATCH_SIZE):
        chunk = tickers[i:i + BATCH_SIZE]
        symbols = [provider_symbol(t) for t in chunk]
        frame = None
        for attempt in range(2):
            try:
                frame = yf.download(symbols, start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                                    interval="1d", group_by="ticker", auto_adjust=False,
                                    threads=True, progress=False)
                if frame is not None and not frame.empty:
                    break
            except Exception as exc:  # noqa: BLE001
                logger.warning("Batch price download failed", extra={"batch": i // BATCH_SIZE, "attempt": attempt,
                                                                      "error": str(exc)})
            time.sleep(5)
        if frame is None or frame.empty:
            failed.extend(chunk)
            continue
        multi = isinstance(frame.columns, pd.MultiIndex)
        for t, sym in zip(chunk, symbols):
            try:
                sub = frame[sym] if multi else frame
            except KeyError:
                failed.append(t)
                continue
            df = _normalise(sub)
            if df is None:
                failed.append(t)
            else:
                out[t] = df
    return out, failed


def slice_lookback(df: pd.DataFrame, lookback_days: int, today: date) -> pd.DataFrame:
    """The window run_ensemble_analysis requests for a horizon."""
    return df[df.index >= pd.Timestamp(today - timedelta(days=lookback_days), tz="UTC")]


def prime_analysis_cache(tickers: list[str], bars: dict[str, pd.DataFrame], today: date) -> int:
    """
    Seed the analysis page's bar cache for the names people are about to click.

    The page then scores those tickers on the very bars the scanner ranked
    them on, for the cache's 15-minute life, instead of a second provider's
    slightly different prints. Limited to board members and candidates:
    doing it for the whole index would put tens of megabytes into Redis
    every run for pages nobody opens.
    """
    from app.analysis.ensemble import _HORIZON_CONFIG
    from app.ingestion.market_data import MarketDataService, _bars_cache_key

    svc = MarketDataService()
    primed = 0
    for t in tickers:
        df = bars.get(t)
        if df is None:
            continue
        for cfg in _HORIZON_CONFIG.values():
            start = today - timedelta(days=cfg["lookback_days"])
            result = MarketDataResult(ticker=t, provider="yfinance (scanner batch)", frequency="1d",
                                      bars=slice_lookback(df, cfg["lookback_days"], today))
            svc._write_cache(_bars_cache_key(t, start, today, "1d"), result, "1d")
        primed += 1
    return primed


# ── Fundamentals ──────────────────────────────────────────────────────────

def fetched_at_utc(data: FundamentalDataResult) -> datetime:
    ts = data.fetched_at
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _encode(data: FundamentalDataResult) -> str:
    d = asdict(data)
    d["fetched_at"] = fetched_at_utc(data).isoformat()
    return json.dumps(d)


def _decode(raw: str) -> FundamentalDataResult:
    d = json.loads(raw)
    d["fetched_at"] = datetime.fromisoformat(d["fetched_at"])
    return FundamentalDataResult(**{k: v for k, v in d.items() if k in _FUND_FIELDS})


def load_cached_fundamentals(tickers: list[str]) -> dict[str, FundamentalDataResult]:
    out: dict[str, FundamentalDataResult] = {}
    redis = get_redis_client()
    for i in range(0, len(tickers), 200):
        chunk = tickers[i:i + 200]
        for t, raw in zip(chunk, redis.mget([_FUND_KEY.format(t) for t in chunk])):
            if not raw:
                continue
            try:
                out[t] = _decode(raw)
            except Exception:  # noqa: BLE001 — a corrupt entry is just a cache miss
                continue
    return out


def refresh_fundamentals(ticker: str) -> FundamentalDataResult:
    """Fetch through the page's own provider chain (Finnhub, then SEC EDGAR) and cache the RAW result."""
    from app.ingestion.fundamentals import FundamentalDataService

    data = FundamentalDataService().fetch_fundamentals(ticker)
    get_redis_client().setex(_FUND_KEY.format(ticker), _FUND_TTL, _encode(data))
    return data


# ── Sentiment ─────────────────────────────────────────────────────────────

def refresh_sentiment(ticker: str, company_name: str | None) -> dict:
    """
    One fetch of the ticker's coverage, scored for all three horizons.

    Raises if the engine does — unlike the analysis page, the scanner would
    rather keep a ticker's previous reading than overwrite it with the
    neutral placeholder a failed run produces.
    """
    from app.analysis.sentiment import score_sentiment
    from app.catalysts.service import record_news_catalysts
    from app.sentiment.engine import analyse_sentiment

    breakdown = analyse_sentiment(ticker, company_name)
    record_news_catalysts(ticker, breakdown.catalysts)
    return {h: score_sentiment(ticker, breakdown, h) for h in HORIZONS}
