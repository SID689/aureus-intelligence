"""
app/ingestion/fundamentals.py
-----------------------------
Two concrete FundamentalDataProvider implementations:
  1. FinnhubProvider  — paid/freemium, fast JSON API, broad coverage
  2. SECEdgarProvider — free, authoritative, US public companies only

The FundamentalDataService MERGES both rather than taking whichever answers
first — they return different, complementary fields (Finnhub: precomputed
ratios and market data; EDGAR: raw filing line items including cash flow and
debt). See FundamentalDataService's docstring for why first-wins was a bug.

Note on EDGAR: all EDGAR requests include a descriptive User-Agent per the
SEC's published requirements (https://www.sec.gov/os/accessing-edgar-data).
Missing or generic User-Agents result in 403s from their CDN.
"""

import json
import logging
from dataclasses import fields as dataclass_fields, replace
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


def _pct_to_fraction(value: Any) -> float | None:
    """
    Convert a provider's PERCENTAGE into the fraction the rest of the system
    expects (FundamentalDataResult documents `0.40 = 40%`).

    Finnhub reports margins, ROE/ROA and growth as percentages — grossMarginTTM
    comes back as 48.65, not 0.4865. The analysis layer divides by fractional
    benchmarks (`gross_margin / 0.40`), so feeding it a percentage inflated
    every ratio by 100x and clamped the resulting sub-score to a perfect 100.
    That pinned the moat, growth and efficiency components at 100 for any
    profitable company, and made the DCF's growth input hit its 40% cap on
    every ticker with positive growth — which is what produced absurd
    intrinsic values. Normalising here, at the provider boundary, keeps the
    documented contract true for every consumer.
    """
    f = _safe_float(value)
    return None if f is None else f / 100.0


def _plausible_ratio(value: float | None, lo: float, hi: float) -> float | None:
    """
    Drop a derived ratio that falls outside a physically sensible range.

    EDGAR's XBRL facts are per-filing, and a concept can be missing or cover a
    different period than its denominator — Apple reports revenue under
    RevenueFromContractWithCustomerExcludingAssessedTax while GrossProfit is
    filed in full, so a naive divide yields a 310% "gross margin". Returning
    None rather than a wrong number is the correct move here: the analysis
    layer's dynamic reweighting already handles a missing signal by
    redistributing its weight, whereas a bogus one silently corrupts the score.
    """
    if value is None:
        return None
    return value if lo <= value <= hi else None


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

        # Revenue/net-income history intentionally not taken from Finnhub —
        # it exposes CAGRs, not the absolute annual series the growth-trajectory
        # scoring needs. EDGAR supplies those through the merge.

        result = FundamentalDataResult(
            ticker=ticker,
            provider=self.name,
            revenue_ttm=_safe_float(m.get("revenuePerShareTTM")) and
                        (_safe_float(m.get("revenuePerShareTTM")) or 0) *
                        (_safe_float(profile.get("shareOutstanding")) or 0) * 1_000_000,
            revenue_growth_yoy=_pct_to_fraction(m.get("revenueGrowthTTMYoy")),
            net_income_ttm=_safe_float(m.get("netIncomePerShareTTM")) and
                           (_safe_float(m.get("netIncomePerShareTTM")) or 0) *
                           (_safe_float(profile.get("shareOutstanding")) or 0) * 1_000_000,
            eps_ttm=_safe_float(m.get("epsTTM")),
            gross_margin=_pct_to_fraction(m.get("grossMarginTTM")),
            operating_margin=_pct_to_fraction(m.get("operatingMarginTTM")),
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
            return_on_equity=_pct_to_fraction(m.get("roeTTM")),
            return_on_assets=_pct_to_fraction(m.get("roaTTM")),
            sector=(profile.get("finnhubIndustry") or None),
            company_name=(profile.get("name") or None),
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
        # Added so EV/EBITDA, ROIC and interest coverage can be computed
        # without a paid data vendor — all present in standard XBRL filings.
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "CashAndCashEquivalentsAtCarryingValue",
        "InterestExpense",
        "IncomeTaxExpenseBenefit",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
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

        dna_series      = (
            self._extract_annual_values(facts, "DepreciationDepletionAndAmortization")
            or self._extract_annual_values(facts, "DepreciationAmortizationAndAccretionNet")
        )
        cash_series     = self._extract_annual_values(facts, "CashAndCashEquivalentsAtCarryingValue")
        interest_series = self._extract_annual_values(facts, "InterestExpense")
        tax_series      = self._extract_annual_values(facts, "IncomeTaxExpenseBenefit")
        pretax_series   = self._extract_annual_values(
            facts,
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        )
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
        # Bounded because a mismatched-period divide yields nonsense (see _plausible_ratio).
        gross_margin    = _plausible_ratio(_safe_div(gross_profit, revenue_ttm), -1.0, 1.0)

        op_series       = self._extract_annual_values(facts, "OperatingIncomeLoss")
        op_income       = op_series[-1][1] if op_series else None
        op_margin       = _plausible_ratio(_safe_div(op_income, revenue_ttm), -1.0, 1.0)

        book_value_ps   = _safe_div(total_equity, shares)
        roe             = _plausible_ratio(_safe_div(net_income_ttm, total_equity), -5.0, 5.0)
        roa             = _plausible_ratio(_safe_div(net_income_ttm, total_assets), -2.0, 2.0)
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
            ebitda_ttm=(
                (op_income + dna_series[-1][1]) if (op_income is not None and dna_series) else None
            ),
            cash_and_equivalents=(cash_series[-1][1] if cash_series else None),
            interest_expense_ttm=(interest_series[-1][1] if interest_series else None),
            income_tax_expense_ttm=(tax_series[-1][1] if tax_series else None),
            pretax_income_ttm=(pretax_series[-1][1] if pretax_series else None),
            revenue_history=rev_history,
            net_income_history=ni_history,
        )

        logger.info("EDGAR fundamentals fetched", extra={"ticker": ticker, "cik": cik})
        return result


# ── Fallback orchestrator ──────────────────────────────────────────────────────

class FundamentalDataService:
    """
    MERGES Finnhub and SEC EDGAR rather than taking whichever answers first.

    =================================================================
    WHY MERGE INSTEAD OF FALLING BACK
    =================================================================
    This used to be a first-wins chain, and that quietly crippled the
    fundamental pillar. The two providers are COMPLEMENTARY, not redundant:

      Finnhub  — precomputed ratios and market data: P/E, P/B, margins,
                 ROE, ROA, current ratio, market cap, shares outstanding.
                 Does NOT return free cash flow, total debt, or equity.
      EDGAR    — raw XBRL line items straight from the filings: operating
                 cash flow, capex (therefore FREE CASH FLOW), long-term
                 debt, stockholders' equity, current assets/liabilities.

    Because Finnhub is listed first and virtually always succeeds, EDGAR
    never ran. Free cash flow was therefore permanently None, which meant
    the DCF valuation could never compute and silently dropped out of the
    fundamental score on every single ticker — the "why is FCF missing"
    confusion noted in the project docs. Same for debt-to-equity.

    Merging is field-level and PRIMARY-WINS: a field already populated by
    Finnhub is never overwritten by EDGAR, so precomputed ratios keep
    Finnhub's (more current, market-aware) values while EDGAR fills only
    the genuine gaps. Derived values are then computed from whatever the
    merge produced.

    A provider failing is not fatal — the merge simply proceeds with what
    it has, and the analysis layer's dynamic reweighting drops whichever
    sub-signals still lack inputs.
    """

    def __init__(self) -> None:
        self._providers: list[FundamentalDataProvider] = [
            FinnhubProvider(),
            SECEdgarProvider(),
        ]

    def fetch_fundamentals(self, ticker: str) -> FundamentalDataResult:
        attempted: list[str] = []
        results: list[FundamentalDataResult] = []

        for provider in self._providers:
            if not provider.is_available():
                continue
            attempted.append(provider.name)
            try:
                results.append(provider.fetch_fundamentals(ticker))
            except Exception as exc:
                logger.warning(
                    f"{provider.name} fundamental fetch failed: continuing with other sources",
                    extra={"ticker": ticker, "error": str(exc)},
                )

        if not results:
            raise FallbackExhaustedError(ticker, attempted)

        merged = self._merge(results)
        self._derive(merged)
        logger.info(
            "Fundamentals merged",
            extra={"ticker": ticker, "provider": merged.provider,
                   "has_fcf": merged.free_cash_flow_ttm is not None,
                   "has_dte": merged.debt_to_equity is not None},
        )
        return merged

    @staticmethod
    def _merge(results: list[FundamentalDataResult]) -> FundamentalDataResult:
        """Field-level merge, primary-wins. Lists merge if the winner's is empty."""
        primary = results[0]
        merged = replace(primary)
        sources = [primary.provider]

        for other in results[1:]:
            filled_any = False
            for f in dataclass_fields(FundamentalDataResult):
                if f.name in ("ticker", "provider", "fetched_at"):
                    continue
                cur, new = getattr(merged, f.name), getattr(other, f.name)
                if isinstance(cur, list):
                    if not cur and new:
                        setattr(merged, f.name, new)
                        filled_any = True
                elif cur is None and new is not None:
                    setattr(merged, f.name, new)
                    filled_any = True
            if filled_any:
                sources.append(other.provider)

        merged.provider = " + ".join(dict.fromkeys(sources))
        return merged

    @staticmethod
    def _derive(d: FundamentalDataResult) -> None:
        """
        Fill values that are computable from the merged inputs.

        Only ever fills a field that is still None — a provider's own figure
        always beats one reconstructed here.
        """
        if d.free_cash_flow_ttm is None and d.operating_cash_flow_ttm is not None:
            capex = abs(d.capex_ttm) if d.capex_ttm is not None else 0.0
            d.free_cash_flow_ttm = d.operating_cash_flow_ttm - capex

        if d.debt_to_equity is None:
            dte = _safe_div(d.total_debt, d.total_equity)
            if dte is not None:
                d.debt_to_equity = dte

        if d.market_cap is None and d.current_price and d.shares_outstanding:
            d.market_cap = d.current_price * d.shares_outstanding

        if d.eps_ttm is None and d.net_income_ttm and d.shares_outstanding:
            eps = _safe_div(d.net_income_ttm, d.shares_outstanding)
            if eps is not None:
                d.eps_ttm = eps

        # ── Institutional valuation & quality ratios ──────────────────
        # All of these are computed from SEC XBRL line items, so they cost
        # nothing and need no vendor key. Each is left None when an input is
        # missing rather than approximated — the analysis layer's dynamic
        # reweighting handles an absent signal correctly, whereas a guessed
        # one silently corrupts the score.

        # Enterprise value = equity value + debt - cash. This is the figure a
        # buyer of the whole business would pay, which is why EV multiples are
        # comparable across companies with different capital structures in a
        # way P/E is not.
        if d.enterprise_value is None and d.market_cap is not None:
            debt = d.total_debt or 0.0
            cash = d.cash_and_equivalents or 0.0
            d.enterprise_value = d.market_cap + debt - cash

        if d.ev_to_ebitda is None and d.enterprise_value is not None and d.ebitda_ttm:
            if d.ebitda_ttm > 0:
                d.ev_to_ebitda = d.enterprise_value / d.ebitda_ttm

        if d.price_to_sales is None:
            ps = _safe_div(d.market_cap, d.revenue_ttm)
            if ps is not None and ps > 0:
                d.price_to_sales = ps

        if d.fcf_yield is None and d.free_cash_flow_ttm is not None and d.market_cap:
            d.fcf_yield = d.free_cash_flow_ttm / d.market_cap

        # Interest coverage = EBIT / interest expense. Below ~2x the business
        # is servicing debt out of most of its operating profit.
        if d.interest_coverage is None and d.interest_expense_ttm:
            ebit = d.ebitda_ttm
            if ebit is None and d.operating_margin is not None and d.revenue_ttm:
                ebit = d.operating_margin * d.revenue_ttm
            if ebit is not None and d.interest_expense_ttm > 0:
                d.interest_coverage = ebit / d.interest_expense_ttm

        # ROIC = NOPAT / invested capital. Uses the company's OWN effective tax
        # rate from the filing rather than a statutory assumption, so it stays
        # honest for businesses with unusual tax profiles.
        if d.roic is None:
            invested = None
            if d.total_debt is not None and d.total_equity is not None:
                invested = d.total_debt + d.total_equity
            ebit = None
            if d.operating_margin is not None and d.revenue_ttm:
                ebit = d.operating_margin * d.revenue_ttm
            tax_rate = _safe_div(d.income_tax_expense_ttm, d.pretax_income_ttm)
            if tax_rate is None or not (0.0 <= tax_rate <= 0.6):
                tax_rate = 0.21   # US statutory fallback when the filing's own rate is unusable
            if ebit is not None and invested and invested > 0:
                d.roic = _plausible_ratio((ebit * (1 - tax_rate)) / invested, -2.0, 3.0)
