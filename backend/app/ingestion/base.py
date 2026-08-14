"""
app/ingestion/base.py
---------------------
Abstract DataProvider contract.
Every concrete provider (Polygon, AlphaVantage, YFinance, Finnhub, EDGAR)
must implement this interface so the fallback chain in market_data.py and
fundamentals.py can swap them without knowing which one is active.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

import pandas as pd


# ── Canonical output types ─────────────────────────────────────────────────────

@dataclass
class OHLCVBar:
    """One OHLCV bar at any frequency."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketDataResult:
    """
    Normalized output from any market data provider.
    `bars` is always a DataFrame with DatetimeIndex and columns
    [open, high, low, close, volume] in float64 — regardless of source.
    """
    ticker: str
    provider: str
    frequency: Literal["1d", "1h", "5m"]
    bars: pd.DataFrame          # shape (N, 5), index is DatetimeIndex UTC
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FundamentalDataResult:
    """
    Normalized fundamental data from any provider.
    All monetary values in USD. None = not available from this provider.
    """
    ticker: str
    provider: str

    # Registered company name, e.g. "NVIDIA Corporation". Used by the
    # sentiment pillar to recognise the company in article text — a
    # headline says "Nvidia", not "NVDA", so without this the aspect
    # targeting in app/sentiment/nlp.py can only match cashtags.
    company_name: str | None = None

    # Income statement
    revenue_ttm: float | None = None
    revenue_growth_yoy: float | None = None   # e.g., 0.12 = 12%
    net_income_ttm: float | None = None
    eps_ttm: float | None = None
    gross_margin: float | None = None         # e.g., 0.40 = 40%
    operating_margin: float | None = None

    # Balance sheet
    total_debt: float | None = None
    total_equity: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    book_value_per_share: float | None = None

    # Cash flow
    free_cash_flow_ttm: float | None = None
    operating_cash_flow_ttm: float | None = None
    capex_ttm: float | None = None

    # Valuation
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    market_cap: float | None = None
    shares_outstanding: float | None = None
    current_price: float | None = None

    # Profitability
    # ── Institutional valuation/quality metrics (SEC EDGAR-derived, free) ──
    ebitda_ttm: float | None = None
    cash_and_equivalents: float | None = None
    interest_expense_ttm: float | None = None
    income_tax_expense_ttm: float | None = None
    pretax_income_ttm: float | None = None
    enterprise_value: float | None = None
    ev_to_ebitda: float | None = None
    price_to_sales: float | None = None
    fcf_yield: float | None = None
    roic: float | None = None                 # NOPAT / invested capital
    interest_coverage: float | None = None    # EBIT / interest expense
    sector: str | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None

    # 5-year historical revenue for growth trend (list of annual values, oldest first)
    revenue_history: list[float] = field(default_factory=list)
    net_income_history: list[float] = field(default_factory=list)

    fetched_at: datetime = field(default_factory=datetime.utcnow)


# ── Abstract base classes ──────────────────────────────────────────────────────

class MarketDataProvider(ABC):
    """
    All market data providers (Polygon, AlphaVantage, YFinance) implement this.
    Methods are synchronous — they are called from Celery workers or
    wrapped with asyncio.to_thread() in FastAPI endpoints.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name for logging and fallback tracking."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Returns True if the provider is configured and reachable.
        Used to skip providers that lack API keys before even attempting a call.
        """
        ...

    @abstractmethod
    def fetch_bars(
        self,
        ticker: str,
        start: date,
        end: date,
        frequency: Literal["1d", "1h", "5m"] = "1d",
    ) -> MarketDataResult:
        """
        Fetch OHLCV bars for `ticker` from `start` to `end` (inclusive).
        Must raise appropriate AureusAPIError subclasses on failure.
        Must NOT return an empty DataFrame — raise DataNotFoundError instead.
        """
        ...

    @abstractmethod
    def fetch_latest_price(self, ticker: str) -> float:
        """Return the most recent trade price for `ticker`."""
        ...


class FundamentalDataProvider(ABC):
    """
    All fundamental data providers (Finnhub, EDGAR) implement this.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def fetch_fundamentals(self, ticker: str) -> FundamentalDataResult:
        """
        Fetch all available fundamental metrics for `ticker`.
        Return a FundamentalDataResult with None for fields the provider
        doesn't supply — the analysis layer handles gaps gracefully.
        """
        ...
