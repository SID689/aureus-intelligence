"""
app/ingestion/fundamentals.py
-----------------------------
Two concrete FundamentalDataProvider implementations:
  1. FinnhubProvider  — paid/freemium, fast JSON API, broad coverage
  2. SECEdgarProvider — free, authoritative, US public companies only

The FundamentalDataService tries Finnhub first. If Finnhub is unconfigured
or fails, it falls back to SEC EDGAR.  EDGAR data is slower (requires CIK
resolution) but is the gold-standard primary source for US equities.

Note on EDGAR: all EDGAR requests include a descriptive User-Agent per the
SEC's published requirements (https://www.sec.gov/os/accessing-edgar-data).
Missing or generic User-Agents result in 403s from their CDN.
"""

import json
import logging
from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.ingestion.base import FundamentalDataProvider, FundamentalDataResult
from app.ingestion.rate_limiter import (
    DataNotFoundError,
    FallbackExhaustedError,
    ProviderUnavailableError,
    RateLimitError,
    raise_for_status,
    with_exponential_backoff,
)

logger = logging.getLogger("aureus.ingestion.fundamentals")

FINNHUB_BASE = "https://finnhub.io/api/v1"
EDGAR_BASE   = "https://data.sec.gov"


# ── Helper ─────────────────────────────────────────────────────────────────────

def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _safe_float(value: Any) -> float | None:
    try:
        f = float(value)
        return f if f == f else None  # reject NaN
    except (TypeError, ValueError):
        return None


# ── 1. Finnhub ─────────────────────────────────────────────────────────────────

class FinnhubProvider(FundamentalDataProvider):
    """
    Finnhub /stock/metric?metric=all endpoint.
    Free tier: 60 API calls/min.
    Returns a flat dict of ~150 financial metrics; we extract the subset
    Aureus's analysis engines need and normalise them to FundamentalDataResult.
    """

    @property
    def name(self) -> str:
        return "Finnhub"

    def is_available(self) -> bool:
        return get_settings().finnhub_configured

    @with_exponential_backoff(max_retries=4, base_delay=2.0, max_delay=30.0)
    def fetch_fundamentals(self, ticker: str) -> FundamentalDataResult:
        settings = get_settings()
        headers = {"X-Finnhub-Token": settings.finnhub_api_key}

        with httpx.Client(timeout=15.0) as client:
            metric_resp = client.get(
                f"{FINNHUB_BASE}/stock/metric",
                params={"symbol": ticker, "metric": "all"},
                headers=headers,
            )
            profile_resp = client.get(
                f"{FINNHUB_BASE}/stock/profile2",
                params={"symbol": ticker},
                headers=headers,
            )

        raise_for_status(metric_resp.status_code, metric_resp.text, self.name)
        raise_for_status(profile_resp.status_code, profile_resp.text, self.name)

        metrics = metric_resp.json().get("metric", {})
        profile = profile_resp.json()

        if not metrics:
            raise DataNotFoundError(f"Finnhub: no metrics for {ticker}", provider=self.name)

        m = metrics  # shorthand

        # Derive D/E from individual fields Finnhub provides
        total_debt    = _safe_float(m.get("totalDebt"))
        total_equity  = _safe_float(m.get("totalEquity"))
        debt_to_equity = _safe_div(total_debt, total_equity)

        # Revenue history: Finnhub provides revenuePerShare * shares for annual
        rev_history = []
        for key in ["10YRevenuegrowthRate", "5YRevenuegrowthRate"]:
            pass  # Finnhub's CAGR isn't the absolute values we want — EDGAR is better here

        result = FundamentalDataResult(
            ticker=ticker,
            provider=self.name,
            revenue_ttm=_safe_float(m.get("revenuePerShareTTM")) and
                        (_safe_float(m.get("revenuePerShareTTM")) or 0) *
                        (_safe_float(profile.get("shareOutstanding")) or 0) * 1_000_000,
            revenue_growth_yoy=_safe_float(m.get("revenueGrowthTTMYoy")),
            net_income_ttm=_safe_float(m.get("netIncomePerShareTTM")) and
                           (_safe_float(m.get("netIncomePerShareTTM")) or 0) *
                           (_safe_float(profile.get("shareOutstanding")) or 0) * 1_000_000,
            eps_ttm=_safe_float(m.get("epsTTM")),
            gross_margin=_safe_float(m.get("grossMarginTTM")),
            operating_margin=_safe_float(m.get("operatingMarginTTM")),
            total_debt=total_debt,
            total_equity=total_equity,
            debt_to_equity=debt_to_equity,
            current_ratio=_safe_float(m.get("currentRatioAnnual")),
            book_value_per_share=_safe_float(m.get("bookValuePerShareAnnual")),
            free_cash_flow_ttm=_safe_float(m.get("freeCashFlowTTM")),
            pe_ratio=_safe_float(m.get("peExclExtraTTM")),
            pb_ratio=_safe_float(m.get("pbAnnual")),
            market_cap=_safe_float(profile.get("marketCapitalization")) and
                       (_safe_float(profile.get("marketCapitalization")) or 0) * 1_000_000,
            shares_outstanding=_safe_float(profile.get("shareOutstanding")) and
                               (_safe_float(profile.get("shareOutstanding")) or 0) * 1_000_000,
            return_on_equity=_safe_float(m.get("roeTTM")),
            return_on_assets=_safe_float(m.get("roaTTM")),
        )

        logger.info("Finnhub fundamentals fetched", extra={"ticker": ticker})
        return result


# ── 2. SEC EDGAR ───────────────────────────────────────────────────────────────

class SECEdgarProvider(FundamentalDataProvider):
    """
    SEC EDGAR XBRL company facts API.
    Public, no key required. US-listed companies only.
    Steps:
      1. Resolve ticker → CIK via EDGAR's company_tickers.json lookup.
      2. Fetch all XBRL facts for the CIK.
      3. Extract the specific GAAP concepts we need from the facts payload.
    This is authoritative but slow (~2-3s per ticker) and US-only.
    """

    GAAP_CONCEPTS = {
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "NetIncomeLoss",
        "EarningsPerShareBasic",
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "StockholdersEquity",
        "NetCashProvidedByUsedInOperatingActivities",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "GrossProfit",
        "OperatingIncomeLoss",
        "CommonStockSharesOutstanding",
        "Assets",
        "Liabilities",
        "AssetsCurrent",
        "LiabilitiesCurrent",
    }

    def __init__(self) -> None:
        self._ticker_to_cik: dict[str, str] | None = None

    @property
    def name(self) -> str:
        return "SEC EDGAR"

    def is_available(self) -> bool:
        return True  # always available for US tickers

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": get_settings().sec_edgar_user_agent, "Accept-Encoding": "gzip"}

    @with_exponential_backoff(max_retries=3, base_delay=3.0, max_delay=30.0)
    def _load_ticker_map(self) -> dict[str, str]:
        """Download the full ticker→CIK map from EDGAR (cached in memory)."""
        if self._ticker_to_cik is not None:
            return self._ticker_to_cik

        url = "https://www.sec.gov/files/company_tickers.json"
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=self._headers())
        raise_for_status(resp.status_code, resp.text, self.name)

        raw: dict[str, dict] = resp.json()
        self._ticker_to_cik = {
            v["ticker"].upper(): str(v["cik_str"]).zfill(10)
            for v in raw.values()
        }
        return self._ticker_to_cik

    def _resolve_cik(self, ticker: str) -> str:
        mapping = self._load_ticker_map()
        cik = mapping.get(ticker.upper())
        if cik is None:
            raise DataNotFoundError(
                f"EDGAR: ticker '{ticker}' not found in company_tickers.json "
                f"(EDGAR only covers SEC-registered US equities)",
                provider=self.name,
            )
        return cik

    @with_exponential_backoff(max_retries=3, base_delay=3.0, max_delay=30.0)
    def _fetch_company_facts(self, cik: str) -> dict:
        url = f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=self._headers())
        raise_for_status(resp.status_code, resp.text, self.name)
        return resp.json()

    def _extract_annual_values(
        self, facts: dict, concept: str, unit: str = "USD"
    ) -> list[tuple[str, float]]:
        """
        Return list of (end_date, value) tuples from 10-K filings only,
        sorted oldest to newest.
        """
        try:
            entries = facts["facts"]["us-gaap"][concept]["units"][unit]
        except KeyError:
            return []

        annual = [
            (e["end"], float(e["val"]))
            for e in entries
            if e.get("form") == "10-K" and e.get("val") is not None
        ]
        # Deduplicate on end date, keep latest filed
        seen: dict[str, float] = {}
        for end, val in annual:
            seen[end] = val
        return sorted(seen.items())

    def fetch_fundamentals(self, ticker: str) -> FundamentalDataResult:
        cik = self._resolve_cik(ticker)
        facts = self._fetch_company_facts(cik)

        # ── Revenue ──────────────────────────────────────────────
        rev_series = (
            self._extract_annual_values(facts, "Revenues")
            or self._extract_annual_values(facts, "RevenueFromContractWithCustomerExcludingAssessedTax")
        )
        rev_history     = [v for _, v in rev_series[-5:]]
        revenue_ttm     = rev_history[-1] if rev_history else None
        revenue_growth  = (
            _safe_div(rev_history[-1] - rev_history[-2], abs(rev_history[-2]))
            if len(rev_history) >= 2 else None
        )

        # ── Net Income ───────────────────────────────────────────
        ni_series       = self._extract_annual_values(facts, "NetIncomeLoss")
        ni_history      = [v for _, v in ni_series[-5:]]
        net_income_ttm  = ni_history[-1] if ni_history else None

        # ── EPS ──────────────────────────────────────────────────
        eps_series      = self._extract_annual_values(facts, "EarningsPerShareBasic")
        eps_ttm         = eps_series[-1][1] if eps_series else None

        # ── Balance sheet ────────────────────────────────────────
        debt_series     = (
            self._extract_annual_values(facts, "LongTermDebt")
            or self._extract_annual_values(facts, "LongTermDebtNoncurrent")
        )
        total_debt      = debt_series[-1][1] if debt_series else None

        equity_series   = self._extract_annual_values(facts, "StockholdersEquity")
        total_equity    = equity_series[-1][1] if equity_series else None

        assets_series   = self._extract_annual_values(facts, "Assets")
        total_assets    = assets_series[-1][1] if assets_series else None

        liab_series     = self._extract_annual_values(facts, "Liabilities")
        total_liab      = liab_series[-1][1] if liab_series else None

        curr_assets_s   = self._extract_annual_values(facts, "AssetsCurrent")
        curr_assets     = curr_assets_s[-1][1] if curr_assets_s else None

        curr_liab_s     = self._extract_annual_values(facts, "LiabilitiesCurrent")
        curr_liab       = curr_liab_s[-1][1] if curr_liab_s else None

        shares_s        = self._extract_annual_values(facts, "CommonStockSharesOutstanding", unit="shares")
        shares          = shares_s[-1][1] if shares_s else None

        # ── Cash Flow ────────────────────────────────────────────
        opcf_series     = self._extract_annual_values(facts, "NetCashProvidedByUsedInOperatingActivities")
        opcf_ttm        = opcf_series[-1][1] if opcf_series else None

        capex_series    = self._extract_annual_values(facts, "PaymentsToAcquirePropertyPlantAndEquipment")
        capex_ttm       = capex_series[-1][1] if capex_series else None
        fcf_ttm         = (
            opcf_ttm - capex_ttm
            if opcf_ttm is not None and capex_ttm is not None
            else None
        )

        # ── Gross profit → margin ────────────────────────────────
        gp_series       = self._extract_annual_values(facts, "GrossProfit")
        gross_profit    = gp_series[-1][1] if gp_series else None
        gross_margin    = _safe_div(gross_profit, revenue_ttm)

        op_series       = self._extract_annual_values(facts, "OperatingIncomeLoss")
        op_income       = op_series[-1][1] if op_series else None
        op_margin       = _safe_div(op_income, revenue_ttm)

        book_value_ps   = _safe_div(total_equity, shares)
        roe             = _safe_div(net_income_ttm, total_equity)
        roa             = _safe_div(net_income_ttm, total_assets)
        debt_to_equity  = _safe_div(total_debt, total_equity)
        current_ratio   = _safe_div(curr_assets, curr_liab)

        result = FundamentalDataResult(
            ticker=ticker,
            provider=self.name,
            revenue_ttm=revenue_ttm,
            revenue_growth_yoy=revenue_growth,
            net_income_ttm=net_income_ttm,
            eps_ttm=eps_ttm,
            gross_margin=gross_margin,
            operating_margin=op_margin,
            total_debt=total_debt,
            total_equity=total_equity,
            debt_to_equity=debt_to_equity,
            current_ratio=current_ratio,
            book_value_per_share=book_value_ps,
            free_cash_flow_ttm=fcf_ttm,
            operating_cash_flow_ttm=opcf_ttm,
            capex_ttm=capex_ttm,
            shares_outstanding=shares,
            return_on_equity=roe,
            return_on_assets=roa,
            revenue_history=rev_history,
            net_income_history=ni_history,
        )

        logger.info("EDGAR fundamentals fetched", extra={"ticker": ticker, "cik": cik})
        return result


# ── Fallback orchestrator ──────────────────────────────────────────────────────

class FundamentalDataService:
    """
    Tries Finnhub first, then EDGAR.
    For non-US tickers EDGAR will always raise DataNotFoundError,
    so Finnhub is the only effective provider in that case.
    """

    def __init__(self) -> None:
        self._providers: list[FundamentalDataProvider] = [
            FinnhubProvider(),
            SECEdgarProvider(),
        ]

    def fetch_fundamentals(self, ticker: str) -> FundamentalDataResult:
        attempted: list[str] = []
        for provider in self._providers:
            if not provider.is_available():
                continue
            attempted.append(provider.name)
            try:
                return provider.fetch_fundamentals(ticker)
            except Exception as exc:
                logger.warning(
                    f"{provider.name} fundamental fetch failed — trying next",
                    extra={"ticker": ticker, "error": str(exc)},
                )

        raise FallbackExhaustedError(ticker, attempted)
