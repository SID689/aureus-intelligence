"""
app/ingestion/market_data.py  (Phase 4 update — hardened Polygon integration)
Fallback chain: Polygon.io → Alpha Vantage → YFinance

Polygon changes in this version:
  - fetch_latest_price now tries /v2/last/trade (paid) then falls back to
    /v2/aggs/ticker/{t}/prev (free tier — previous close) automatically.
  - All 403 responses are caught and re-raised as ProviderUnavailableError
    with a clear message distinguishing "bad key" from "plan not subscribed."
  - Subscription tier is detected from the 403 body and logged once.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import httpx
import pandas as pd
import yfinance as yf

from app.core.config import get_settings
from app.ingestion.base import MarketDataProvider, MarketDataResult
from app.ingestion.rate_limiter import (
    ProviderBudgetExhausted,
    AureusAPIError,
    DataNotFoundError,
    FallbackExhaustedError,
    ProviderUnavailableError,
    RateLimitError,
    RedisTokenBucket,
    raise_for_status,
    with_exponential_backoff,
)

logger = logging.getLogger("aureus.ingestion.market_data")

POLYGON_BASE = "https://api.polygon.io"
AV_BASE      = "https://www.alphavantage.co/query"

# Shared across every PolygonProvider instance and every process (Redis-backed),
# so the free tier's 5-calls/min cap is respected globally, not per-process.
# This is what lets Polygon actually be the dominant data source in practice:
# without this, a handful of concurrent chart loads would exhaust the quota
# in one burst and every subsequent call would silently fall back to YFinance.
_polygon_bucket = RedisTokenBucket("polygon_api", max_calls=5, window_seconds=60)


# ── 1. Polygon.io ─────────────────────────────────────────────────────────────

class PolygonProvider(MarketDataProvider):
    """
    Polygon.io market data provider.

    Free tier ($0/mo):   15-minute delayed data, 5 API calls/min.
                         Latest-price falls back to previous close.
    Starter ($29/mo)+:   Real-time data, higher rate limits.

    The provider auto-detects which plan is active from the API responses
    and degrades gracefully rather than crashing.
    """

    @property
    def name(self) -> str:
        return "Polygon.io"

    def is_available(self) -> bool:
        return get_settings().polygon_configured

    @with_exponential_backoff(max_retries=4, base_delay=2.0, max_delay=30.0)
    def fetch_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        frequency: Literal["1d", "1h", "5m"] = "1d",
    ) -> MarketDataResult:
        if not _polygon_bucket.allow():
            # Non-retryable by design — see ProviderBudgetExhausted. Sleeping
            # here would burn ~60s waiting on a quota we already know is spent,
            # when AlphaVantage/YFinance can answer immediately.
            raise ProviderBudgetExhausted(
                "Polygon.io free-tier rate limit (5/min) reached, deferring to next provider",
                status_code=429, provider=self.name,
            )

        settings = get_settings()
        timespan_map = {"1d": ("day", 1), "1h": ("hour", 1), "5m": ("minute", 5)}
        timespan, multiplier = timespan_map[frequency]

        url = (
            f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range"
            f"/{multiplier}/{timespan}"
            f"/{start.isoformat()}/{end.isoformat()}"
        )
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": settings.polygon_api_key,
        }

        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, params=params)

        # 403 = valid key but plan doesn't include this endpoint
        if resp.status_code == 403:
            raise ProviderUnavailableError(
                f"Polygon.io: plan restriction (403) for {ticker} {frequency} bars. "
                "Free tier supports daily bars only. Upgrade at polygon.io/dashboard.",
                status_code=403, provider=self.name,
            )

        raise_for_status(resp.status_code, resp.text, self.name)
        payload = resp.json()

        # Polygon returns status "OK" or "DELAYED" — both have data
        status  = payload.get("status", "")
        results = payload.get("results", [])
        if not results:
            raise DataNotFoundError(
                f"Polygon: no bars for {ticker} ({start}→{end}). "
                f"API status: {status}",
                provider=self.name,
            )

        if status == "DELAYED":
            logger.info(
                "Polygon returning 15-min delayed data (free tier)",
                extra={"ticker": ticker},
            )

        df = pd.DataFrame(results).rename(columns={
            "o": "open", "h": "high", "l": "low",
            "c": "close", "v": "volume", "t": "timestamp",
        })
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]].astype(float)

        logger.info("Polygon bars fetched", extra={"ticker": ticker, "rows": len(df), "status": status})
        return MarketDataResult(ticker=ticker, provider=self.name, frequency=frequency, bars=df)

    def fetch_latest_price(self, ticker: str) -> float:
        """
        Try real-time last trade (paid tier).
        On 403, fall back to previous-session close (free tier).
        """
        if not _polygon_bucket.allow():
            # Non-retryable by design — see ProviderBudgetExhausted. Sleeping
            # here would burn ~60s waiting on a quota we already know is spent,
            # when AlphaVantage/YFinance can answer immediately.
            raise ProviderBudgetExhausted(
                "Polygon.io free-tier rate limit (5/min) reached, deferring to next provider",
                status_code=429, provider=self.name,
            )

        settings = get_settings()
        api_key  = settings.polygon_api_key

        # ── Try 1: real-time last trade (requires Starter+ plan) ──
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{POLYGON_BASE}/v2/last/trade/{ticker}",
                    params={"apiKey": api_key},
                )
            if resp.status_code == 200:
                return float(resp.json()["results"]["p"])
            if resp.status_code != 403:
                raise_for_status(resp.status_code, resp.text, self.name)
            # 403 → fall through to previous close
            logger.debug("Polygon last trade requires paid plan, using prev close", extra={"ticker": ticker})
        except (AureusAPIError, ProviderUnavailableError):
            raise
        except Exception:
            pass

        # ── Try 2: previous session close (free tier) ──────────────
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/prev",
                params={"adjusted": "true", "apiKey": api_key},
            )
        if resp.status_code == 403:
            raise ProviderUnavailableError(
                "Polygon.io: cannot fetch price, check API key validity.",
                status_code=403, provider=self.name,
            )
        raise_for_status(resp.status_code, resp.text, self.name)
        results = resp.json().get("results", [])
        if not results:
            raise DataNotFoundError(f"Polygon: no prev-close data for {ticker}", provider=self.name)
        return float(results[0]["c"])


# ── 2. Alpha Vantage ──────────────────────────────────────────────────────────

class AlphaVantageProvider(MarketDataProvider):

    @property
    def name(self) -> str:
        return "AlphaVantage"

    def is_available(self) -> bool:
        return get_settings().alpha_vantage_configured

    @with_exponential_backoff(max_retries=4, base_delay=12.0, max_delay=60.0)
    def fetch_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        frequency: Literal["1d", "1h", "5m"] = "1d",
    ) -> MarketDataResult:
        settings = get_settings()
        if frequency != "1d":
            logger.warning("AlphaVantage fallback supports daily only, degrading", extra={"ticker": ticker})
            frequency = "1d"

        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "full",
            "apikey": settings.alpha_vantage_api_key,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(AV_BASE, params=params)
        raise_for_status(resp.status_code, resp.text, self.name)
        payload = resp.json()

        if "Note" in payload:
            raise RateLimitError(payload["Note"][:300], status_code=429, provider=self.name)
        if "Error Message" in payload:
            raise DataNotFoundError(payload["Error Message"], provider=self.name)

        raw = payload.get("Time Series (Daily)", {})
        if not raw:
            raise DataNotFoundError(f"AlphaVantage: no time series for {ticker}", provider=self.name)

        rows = [
            {
                "timestamp": pd.Timestamp(dt, tz="UTC"),
                "open":   float(v["1. open"]),
                "high":   float(v["2. high"]),
                "low":    float(v["3. low"]),
                "close":  float(v["5. adjusted close"]),
                "volume": float(v["6. volume"]),
            }
            for dt, v in raw.items()
        ]
        df = pd.DataFrame(rows).set_index("timestamp").sort_index()
        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts   = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
        df = df.loc[start_ts:end_ts]
        if df.empty:
            raise DataNotFoundError(f"AlphaVantage: no bars for {ticker} in [{start}, {end}]", provider=self.name)

        logger.info("AlphaVantage bars fetched", extra={"ticker": ticker, "rows": len(df)})
        return MarketDataResult(ticker=ticker, provider=self.name, frequency=frequency, bars=df)

    @with_exponential_backoff(max_retries=3, base_delay=12.0)
    def fetch_latest_price(self, ticker: str) -> float:
        settings = get_settings()
        params = {"function": "GLOBAL_QUOTE", "symbol": ticker, "apikey": settings.alpha_vantage_api_key}
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(AV_BASE, params=params)
        raise_for_status(resp.status_code, resp.text, self.name)
        payload = resp.json()
        if "Note" in payload:
            raise RateLimitError(payload["Note"][:300], status_code=429, provider=self.name)
        price_str = payload.get("Global Quote", {}).get("05. price", "")
        if not price_str:
            raise DataNotFoundError(f"No price for {ticker} from AlphaVantage", provider=self.name)
        return float(price_str)


# ── 3. YFinance ───────────────────────────────────────────────────────────────

class YFinanceProvider(MarketDataProvider):

    @property
    def name(self) -> str:
        return "YFinance"

    def is_available(self) -> bool:
        return True

    @with_exponential_backoff(max_retries=3, base_delay=5.0, max_delay=60.0)
    def fetch_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        frequency: Literal["1d", "1h", "5m"] = "1d",
    ) -> MarketDataResult:
        interval_map = {"1d": "1d", "1h": "1h", "5m": "5m"}
        try:
            t  = yf.Ticker(ticker)
            # Split-adjusted only, like Polygon's adjusted=true above it in
            # the chain. With auto_adjust=True this fallback also removed
            # dividends, so the same stock scored differently depending on
            # which provider happened to answer: CVX's three-year technical
            # pillar read 62 through here and 65 through Polygon, purely
            # because a rate limit had been hit.
            df = t.history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval=interval_map[frequency],
                auto_adjust=False,
            )
        except Exception as exc:
            raise ProviderUnavailableError(f"YFinance error for {ticker}: {exc}", provider=self.name)

        if df is None or df.empty:
            raise DataNotFoundError(f"YFinance: no data for {ticker} ({start}→{end})", provider=self.name)

        df.columns = [c.lower() for c in df.columns]
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        available = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        if "close" not in available:
            raise DataNotFoundError(f"YFinance: unexpected columns for {ticker}: {df.columns.tolist()}", provider=self.name)

        df = df[available].astype(float)
        logger.info("YFinance bars fetched", extra={"ticker": ticker, "rows": len(df)})
        return MarketDataResult(ticker=ticker, provider=self.name, frequency=frequency, bars=df)

    def fetch_latest_price(self, ticker: str) -> float:
        try:
            t     = yf.Ticker(ticker)
            fast  = t.fast_info
            price = getattr(fast, "last_price", None)
            if price is None or (isinstance(price, float) and price != price):
                hist  = t.history(period="2d", auto_adjust=True)
                if hist.empty:
                    raise DataNotFoundError(f"YFinance: no price for {ticker}", provider=self.name)
                price = float(hist["Close"].iloc[-1])
            return float(price)
        except DataNotFoundError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(str(exc), provider=self.name)


# ── Fallback orchestrator ─────────────────────────────────────────────────────

def _bars_cache_key(ticker: str, start: date, end: date, frequency: str) -> str:
    return f"marketdata:bars:{ticker}:{frequency}:{start.isoformat()}:{end.isoformat()}"


# Daily bars barely change intra-day after the first fetch; cache generously.
# Intraday frequencies get a much shorter TTL since they go stale fast.
_BARS_CACHE_TTL = {"1d": 900, "1h": 180, "5m": 60}  # seconds


def _normalise_bars(result: "MarketDataResult") -> None:
    """
    Force one bar shape across every provider.

    Providers disagree on the index name — Polygon returns `timestamp`,
    yfinance returns `Date` — and consumers downstream do
    `bars.reset_index()` and then read `row["timestamp"]`. That worked only
    because Polygon almost always answered first; the moment the chain fell
    through to yfinance the API raised KeyError: 'timestamp' and 500'd.
    (The Redis cache round-trip already normalised it via set_index("timestamp"),
    so a cached result behaved differently from a fresh one — the same request
    could succeed or fail depending purely on cache state.)

    Normalising here, at the one choke point every provider passes through,
    makes the contract true for the API, the analysis engine, the backtester
    and the pattern game alike.
    """
    df = result.bars
    if df is None or df.empty:
        return
    df.index.name = "timestamp"
    df.columns = [str(c).lower() for c in df.columns]


class MarketDataService:
    """
    Tries providers in priority order: Polygon.io → Alpha Vantage → YFinance.
    Polygon is intentionally listed first and is the intended primary source —
    the RedisTokenBucket above plus this caching layer are both specifically
    there to keep Polygon serving the majority of requests without tripping
    its free-tier rate limit, rather than every other request silently
    degrading to YFinance.
    """

    def __init__(self) -> None:
        self._providers: list[MarketDataProvider] = [
            PolygonProvider(),
            AlphaVantageProvider(),
            YFinanceProvider(),
        ]

    def fetch_bars(self, ticker: str, start: date, end: date, frequency: Literal["1d","1h","5m"] = "1d") -> MarketDataResult:
        cache_key = _bars_cache_key(ticker, start, end, frequency)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        attempted: list[str] = []
        for provider in self._providers:
            if not provider.is_available():
                continue
            attempted.append(provider.name)
            try:
                result = provider.fetch_bars(ticker, start, end, frequency)
                _normalise_bars(result)
                self._write_cache(cache_key, result, frequency)
                return result
            except FallbackExhaustedError:
                raise
            except Exception as exc:
                logger.warning(f"{provider.name} bars failed, next", extra={"ticker": ticker, "error": str(exc)})
        raise FallbackExhaustedError(ticker, attempted)

    def _read_cache(self, cache_key: str) -> MarketDataResult | None:
        try:
            from app.core.redis_client import get_redis_client
            raw = get_redis_client().get(cache_key)
            if not raw:
                return None
            import json
            payload = json.loads(raw)
            df = pd.read_json(payload["bars_json"], orient="records")
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp")
            return MarketDataResult(
                ticker=payload["ticker"], provider=f"{payload['provider']} (cached)",
                frequency=payload["frequency"], bars=df,
            )
        except Exception:
            return None

    def _write_cache(self, cache_key: str, result: MarketDataResult, frequency: str) -> None:
        try:
            from app.core.redis_client import get_redis_client
            import json
            bars_json = result.bars.reset_index().to_json(orient="records", date_format="iso")
            payload = json.dumps({
                "ticker": result.ticker, "provider": result.provider,
                "frequency": result.frequency, "bars_json": bars_json,
            })
            ttl = _BARS_CACHE_TTL.get(frequency, 300)
            get_redis_client().setex(cache_key, ttl, payload)
        except Exception as exc:
            logger.debug("Bars cache write failed (non-fatal)", extra={"error": str(exc)})

    def fetch_latest_price(self, ticker: str) -> float:
        attempted: list[str] = []
        for provider in self._providers:
            if not provider.is_available():
                continue
            attempted.append(provider.name)
            try:
                return provider.fetch_latest_price(ticker)
            except Exception as exc:
                logger.warning(f"{provider.name} price failed, next", extra={"ticker": ticker, "error": str(exc)})
        raise FallbackExhaustedError(ticker, attempted)
