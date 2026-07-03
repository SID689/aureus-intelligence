"""
app/ingestion/market_data.py
----------------------------
Three concrete MarketDataProvider implementations in descending quality:
  1. PolygonProvider   — paid, tick-level, sub-second latency
  2. AlphaVantageProvider — freemium, 5 req/min on free tier
  3. YFinanceProvider  — free, best-effort, no SLA

`MarketDataService.fetch_bars()` and `fetch_latest_price()` try them in
order, track which providers failed, and raise FallbackExhaustedError
only when all three are exhausted.
"""

import logging
from datetime import date, datetime, timezone
from typing import Literal

import httpx
import pandas as pd
import yfinance as yf

from app.core.config import get_settings
from app.ingestion.base import MarketDataProvider, MarketDataResult
from app.ingestion.rate_limiter import (
    DataNotFoundError,
    FallbackExhaustedError,
    ProviderUnavailableError,
    RateLimitError,
    raise_for_status,
    with_exponential_backoff,
)

logger = logging.getLogger("aureus.ingestion.market_data")

POLYGON_BASE  = "https://api.polygon.io"
AV_BASE       = "https://www.alphavantage.co/query"


# ── 1. Polygon.io ──────────────────────────────────────────────────────────────

class PolygonProvider(MarketDataProvider):
    """
    Polygon.io Aggregates v2 endpoint.
    Paid tier supports unlimited calls; free tier has 5 req/min.
    We apply back-off regardless because institutional volumes can still
    saturate even paid-tier burst limits.
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

        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params=params)

        raise_for_status(resp.status_code, resp.text, self.name)
        payload = resp.json()

        results = payload.get("results", [])
        if not results:
            raise DataNotFoundError(
                f"Polygon returned no bars for {ticker} ({start} → {end})",
                provider=self.name,
            )

        df = pd.DataFrame(results).rename(
            columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "timestamp"}
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]].astype(float)

        logger.info("Polygon bars fetched", extra={"ticker": ticker, "rows": len(df)})
        return MarketDataResult(ticker=ticker, provider=self.name, frequency=frequency, bars=df)

    @with_exponential_backoff(max_retries=3, base_delay=1.0)
    def fetch_latest_price(self, ticker: str) -> float:
        settings = get_settings()
        url = f"{POLYGON_BASE}/v2/last/trade/{ticker}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params={"apiKey": settings.polygon_api_key})
        raise_for_status(resp.status_code, resp.text, self.name)
        return float(resp.json()["results"]["p"])


# ── 2. Alpha Vantage ───────────────────────────────────────────────────────────

class AlphaVantageProvider(MarketDataProvider):
    """
    Alpha Vantage TIME_SERIES_DAILY_ADJUSTED endpoint.
    Free tier: 25 req/day, 5 req/min.  Premium keys have higher limits.
    Back-off is critical here — the free tier hits 429 very quickly.
    """

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

        # AV intraday endpoint differs from daily — we degrade to daily only
        # since AV intraday coverage is limited on free keys.
        if frequency != "1d":
            logger.warning(
                "AlphaVantage fallback only supports daily frequency — degrading",
                extra={"ticker": ticker, "requested_frequency": frequency},
            )
            frequency = "1d"

        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "full",  # up to 20 years of data
            "apikey": settings.alpha_vantage_api_key,
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.get(AV_BASE, params=params)

        raise_for_status(resp.status_code, resp.text, self.name)
        payload = resp.json()

        if "Note" in payload:   # AV's non-standard rate-limit signal
            raise RateLimitError(payload["Note"][:300], status_code=429, provider=self.name)
        if "Error Message" in payload:
            raise DataNotFoundError(payload["Error Message"], provider=self.name)

        ts_key = "Time Series (Daily)"
        raw = payload.get(ts_key, {})
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
        df = (
            pd.DataFrame(rows)
            .set_index("timestamp")
            .sort_index()
        )

        # Filter to requested date window
        start_ts = pd.Timestamp(start, tz="UTC")
        end_ts   = pd.Timestamp(end,   tz="UTC") + pd.Timedelta(days=1)
        df = df.loc[start_ts:end_ts]

        if df.empty:
            raise DataNotFoundError(
                f"AlphaVantage: no bars for {ticker} in [{start}, {end}]",
                provider=self.name,
            )

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


# ── 3. YFinance (free, no key) ─────────────────────────────────────────────────

class YFinanceProvider(MarketDataProvider):
    """
    Yahoo Finance via the yfinance library.
    No API key required. Best-effort, no SLA. Used only as a final fallback.

    Uses yf.Ticker().history() rather than yf.download() because newer
    yfinance versions (0.2.x) return multi-level column headers from download()
    for single tickers, which breaks simple column name normalization.
    history() always returns a flat single-level DataFrame.
    """

    @property
    def name(self) -> str:
        return "YFinance"

    def is_available(self) -> bool:
        return True  # always available — it's the backstop

    @with_exponential_backoff(max_retries=3, base_delay=5.0, max_delay=60.0)
    def fetch_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        frequency: Literal["1d", "1h", "5m"] = "1d",
    ) -> MarketDataResult:
        interval_map = {"1d": "1d", "1h": "1h", "5m": "5m"}
        interval = interval_map[frequency]

        try:
            t = yf.Ticker(ticker)
            df = t.history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval=interval,
                auto_adjust=True,
            )
        except Exception as exc:
            raise ProviderUnavailableError(
                f"YFinance error for {ticker}: {exc}", provider=self.name
            )

        if df is None or df.empty:
            raise DataNotFoundError(
                f"YFinance: no data for {ticker} ({start} → {end})", provider=self.name
            )

        # history() returns clean single-level columns: Open, High, Low, Close, Volume
        df.columns = [c.lower() for c in df.columns]

        # Ensure index is UTC-aware DatetimeIndex
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        # Select only the columns we need — history() may include Dividends, Stock Splits
        available = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        if "close" not in available:
            raise DataNotFoundError(
                f"YFinance: unexpected column schema for {ticker}: {df.columns.tolist()}",
                provider=self.name,
            )
        df = df[available].astype(float)

        logger.info("YFinance bars fetched", extra={"ticker": ticker, "rows": len(df)})
        return MarketDataResult(ticker=ticker, provider=self.name, frequency=frequency, bars=df)

    def fetch_latest_price(self, ticker: str) -> float:
        try:
            t = yf.Ticker(ticker)
            # fast_info is the lightest call — no full quote download
            fast = t.fast_info
            price = getattr(fast, "last_price", None)
            if price is None or (isinstance(price, float) and price != price):  # NaN check
                # Fallback: pull last close from a tiny history window
                hist = t.history(period="2d", auto_adjust=True)
                if hist.empty:
                    raise DataNotFoundError(
                        f"YFinance: no price data for {ticker}", provider=self.name
                    )
                price = float(hist["Close"].iloc[-1])
            return float(price)
        except DataNotFoundError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(str(exc), provider=self.name)


# ── Fallback orchestrator ──────────────────────────────────────────────────────

class MarketDataService:
    """
    Tries providers in priority order (Polygon → AlphaVantage → YFinance).
    Any provider that lacks a configured API key is skipped silently.
    Any provider that raises a non-retryable error is logged and skipped.
    Raises FallbackExhaustedError only when all providers fail.
    """

    def __init__(self) -> None:
        self._providers: list[MarketDataProvider] = [
            PolygonProvider(),
            AlphaVantageProvider(),
            YFinanceProvider(),
        ]

    def fetch_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        frequency: Literal["1d", "1h", "5m"] = "1d",
    ) -> MarketDataResult:
        attempted: list[str] = []
        for provider in self._providers:
            if not provider.is_available():
                logger.debug(f"Skipping {provider.name} (not configured)")
                continue
            attempted.append(provider.name)
            try:
                return provider.fetch_bars(ticker, start, end, frequency)
            except FallbackExhaustedError:
                raise
            except Exception as exc:
                logger.warning(
                    f"{provider.name} failed — trying next provider",
                    extra={"ticker": ticker, "error": str(exc)},
                )

        raise FallbackExhaustedError(ticker, attempted)

    def fetch_latest_price(self, ticker: str) -> float:
        attempted: list[str] = []
        for provider in self._providers:
            if not provider.is_available():
                continue
            attempted.append(provider.name)
            try:
                return provider.fetch_latest_price(ticker)
            except Exception as exc:
                logger.warning(
                    f"{provider.name} price fetch failed",
                    extra={"ticker": ticker, "error": str(exc)},
                )

        raise FallbackExhaustedError(ticker, attempted)
