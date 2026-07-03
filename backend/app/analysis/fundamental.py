"""
app/analysis/fundamental.py
---------------------------
Fundamental Module: evaluates intrinsic value, financial safety,
growth trajectory, and competitive moat proxies.

All scores are on a [0, 100] scale where 100 = maximally bullish.
None-handling is explicit: when a required data point is missing we either
skip the sub-score contribution or assign a neutral 50 (with a logged note)
rather than crashing. This ensures the ensemble always gets a valid float.

Sub-score weights:
  DCF signal    35%  — is the stock trading below intrinsic value?
  Safety        25%  — can the company survive adversity?
  Growth        25%  — is revenue/earnings trajectory improving?
  Moat          15%  — ROE, gross margin, multi-year consistency
"""

import logging
import math
from dataclasses import dataclass

from app.ingestion.base import FundamentalDataResult
from app.analysis.models import DCFResult, FundamentalScore

logger = logging.getLogger("aureus.analysis.fundamental")

# Sub-score weights (must sum to 1.0)
_W_DCF    = 0.35
_W_SAFETY = 0.25
_W_GROWTH = 0.25
_W_MOAT   = 0.15


# ── DCF engine ─────────────────────────────────────────────────────────────────

def _two_stage_dcf(
    fcf: float,
    near_growth: float,
    terminal_growth: float,
    discount_rate: float,
    projection_years: int,
    shares: float,
) -> float:
    """
    Two-stage Discounted Cash Flow model.

    Stage 1: FCF grows at `near_growth` for `projection_years`.
    Stage 2 (terminal): FCF grows at `terminal_growth` in perpetuity,
                         discounted back as a Gordon Growth Model terminal value.

    Returns intrinsic value per share.
    All rates are in decimal form (e.g., 0.10 = 10%).
    """
    if discount_rate <= terminal_growth:
        # Gordon model breaks down — fall back to 15% discount, 3% terminal
        discount_rate, terminal_growth = 0.15, 0.03

    pv_sum = 0.0
    current_fcf = fcf
    for year in range(1, projection_years + 1):
        current_fcf *= (1 + near_growth)
        pv_sum += current_fcf / ((1 + discount_rate) ** year)

    # Terminal value at end of Stage 1
    terminal_fcf = current_fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / ((1 + discount_rate) ** projection_years)

    total_equity_value = pv_sum + pv_terminal
    return max(total_equity_value / shares, 0.0)


def _dcf_to_score(intrinsic: float, current_price: float) -> float:
    """
    Convert the DCF margin-of-safety into a 0–100 score.
    margin = (intrinsic - price) / intrinsic
      +30% or more upside  → 100
      0%  (fair value)     →  50
      -30% or more downside →  0
    Linear interpolation between those anchors.
    """
    if intrinsic <= 0 or current_price <= 0:
        return 50.0  # neutral when DCF is unreliable
    margin = (intrinsic - current_price) / intrinsic
    score = 50.0 + (margin / 0.30) * 50.0
    return max(0.0, min(100.0, score))


# ── Safety score ───────────────────────────────────────────────────────────────

def _compute_safety_score(data: FundamentalDataResult, notes: list[str]) -> float:
    components: list[float] = []

    # Debt-to-Equity (lower = safer; D/E > 3 is dangerous)
    if data.debt_to_equity is not None:
        de = data.debt_to_equity
        if de < 0:
            s = 30.0   # negative equity is a red flag
        elif de == 0:
            s = 100.0  # zero debt
        else:
            # Linear from 100 at D/E=0 to 0 at D/E=3
            s = max(0.0, 100.0 - (de / 3.0) * 100.0)
        components.append(s)
        notes.append(f"D/E ratio: {de:.2f} → safety sub-score {s:.1f}")
    else:
        notes.append("D/E ratio unavailable — safety partially estimated")

    # Current ratio (liquidity; >2 = excellent, <1 = danger)
    if data.current_ratio is not None:
        cr = data.current_ratio
        s = max(0.0, min(100.0, (cr - 1.0) * 50.0))
        components.append(s)

    # Interest coverage proxy: if we have operating income and debt
    # (simplified: operating margin proxy)
    if data.operating_margin is not None:
        om = data.operating_margin
        # Margin > 20% = very safe, < 0 = distress
        s = max(0.0, min(100.0, (om / 0.20) * 80.0 + 20.0 if om > 0 else om * 200.0 + 20.0))
        components.append(s)

    return sum(components) / len(components) if components else 50.0


# ── Growth score ───────────────────────────────────────────────────────────────

def _compute_growth_score(data: FundamentalDataResult, notes: list[str]) -> float:
    components: list[float] = []

    # YoY revenue growth
    if data.revenue_growth_yoy is not None:
        g = data.revenue_growth_yoy
        # +20% growth → 100; 0% → 50; -20% → 0
        s = max(0.0, min(100.0, 50.0 + (g / 0.20) * 50.0))
        components.append(s)
        notes.append(f"Revenue growth YoY: {g*100:.1f}% → growth sub-score {s:.1f}")

    # Revenue trend consistency (5-year CAGR from history)
    if len(data.revenue_history) >= 3:
        history = data.revenue_history
        # Filter out zeros to avoid division by zero in CAGR
        valid = [v for v in history if v > 0]
        if len(valid) >= 2:
            years = len(valid) - 1
            cagr = (valid[-1] / valid[0]) ** (1.0 / years) - 1.0
            s = max(0.0, min(100.0, 50.0 + (cagr / 0.15) * 50.0))
            components.append(s)

    # Earnings momentum
    if len(data.net_income_history) >= 2:
        ni = data.net_income_history
        positive_years = sum(1 for v in ni if v > 0)
        consistency = positive_years / len(ni)
        components.append(consistency * 100.0)

    return sum(components) / len(components) if components else 50.0


# ── Moat score ─────────────────────────────────────────────────────────────────

def _compute_moat_score(data: FundamentalDataResult, notes: list[str]) -> float:
    """
    Moat proxies: high/stable gross margin, high ROE, revenue consistency.
    We can't measure pricing power or switching costs directly from financials,
    but these quantitative signals are strong correlates.
    """
    components: list[float] = []

    # Gross margin (>40% signals pricing power / low commodity risk)
    if data.gross_margin is not None:
        gm = data.gross_margin
        s = max(0.0, min(100.0, (gm / 0.40) * 80.0 + 20.0))
        components.append(s)

    # Return on Equity (>15% sustained is a classic moat signal)
    if data.return_on_equity is not None:
        roe = data.return_on_equity
        if roe < 0:
            s = 10.0
        else:
            s = max(0.0, min(100.0, (roe / 0.20) * 100.0))
        components.append(s)
        notes.append(f"ROE: {roe*100:.1f}% → moat sub-score {s:.1f}")

    # Revenue consistency (coefficient of variation — lower = more consistent)
    if len(data.revenue_history) >= 3:
        vals = [v for v in data.revenue_history if v > 0]
        if len(vals) >= 3:
            mean_rev = sum(vals) / len(vals)
            std_rev = math.sqrt(sum((v - mean_rev) ** 2 for v in vals) / len(vals))
            cv = std_rev / mean_rev if mean_rev > 0 else 1.0
            # CV < 0.1 (low variability) → 90; CV > 0.5 (high variability) → 20
            s = max(20.0, min(90.0, 90.0 - (cv / 0.5) * 70.0))
            components.append(s)

    return sum(components) / len(components) if components else 50.0


# ── Public API ─────────────────────────────────────────────────────────────────

def run_fundamental_analysis(
    ticker: str,
    data: FundamentalDataResult,
    time_horizon: str = "medium_term",
) -> FundamentalScore:
    """
    Run all fundamental sub-analyses and return a FundamentalScore.

    Args:
        ticker:        Asset symbol.
        data:          Normalised fundamentals from any FundamentalDataProvider.
        time_horizon:  'short_term' | 'medium_term' | 'long_term'
                       Affects DCF projection years and near-term growth rate.
    """
    notes: list[str] = []
    horizon_years = {"short_term": 3, "medium_term": 5, "long_term": 10}.get(time_horizon, 5)

    # ── DCF ──────────────────────────────────────────────────────
    dcf_detail: DCFResult | None = None
    dcf_signal = 50.0  # neutral default

    if (
        data.free_cash_flow_ttm is not None
        and data.free_cash_flow_ttm > 0
        and data.shares_outstanding is not None
        and data.shares_outstanding > 0
        and data.current_price is not None
        and data.current_price > 0
    ):
        # Estimate near-term growth from revenue trend or EDGAR revenue growth
        near_growth = min(
            data.revenue_growth_yoy or 0.08,
            0.40,  # cap at 40% — DCF breaks at extreme growth assumptions
        )
        terminal_growth = 0.025  # long-run GDP proxy
        discount_rate   = 0.10   # conservative WACC approximation

        try:
            intrinsic = _two_stage_dcf(
                fcf=data.free_cash_flow_ttm,
                near_growth=near_growth,
                terminal_growth=terminal_growth,
                discount_rate=discount_rate,
                projection_years=horizon_years,
                shares=data.shares_outstanding,
            )
            margin = (intrinsic - data.current_price) / intrinsic if intrinsic > 0 else 0.0
            dcf_detail = DCFResult(
                intrinsic_value_per_share=round(intrinsic, 2),
                current_price=data.current_price,
                margin_of_safety=round(margin, 4),
                discount_rate=discount_rate,
                terminal_growth_rate=terminal_growth,
                near_term_growth_rate=near_growth,
                projection_years=horizon_years,
            )
            dcf_signal = _dcf_to_score(intrinsic, data.current_price)
            notes.append(
                f"DCF intrinsic: ${intrinsic:.2f} vs price ${data.current_price:.2f} "
                f"(margin of safety: {margin*100:.1f}%)"
            )
        except Exception as exc:
            notes.append(f"DCF calculation failed: {exc} — using neutral 50")
            logger.warning("DCF failed", extra={"ticker": ticker, "error": str(exc)})
    else:
        notes.append("DCF skipped: FCF or shares unavailable / negative FCF → neutral score")

    # ── Sub-scores ────────────────────────────────────────────────
    safety_score = _compute_safety_score(data, notes)
    growth_score = _compute_growth_score(data, notes)
    moat_score   = _compute_moat_score(data, notes)

    # ── Weighted composite ────────────────────────────────────────
    composite = (
        _W_DCF    * dcf_signal   +
        _W_SAFETY * safety_score +
        _W_GROWTH * growth_score +
        _W_MOAT   * moat_score
    )

    logger.info(
        "Fundamental analysis complete",
        extra={
            "ticker": ticker,
            "score": round(composite, 2),
            "dcf": round(dcf_signal, 2),
            "safety": round(safety_score, 2),
            "growth": round(growth_score, 2),
            "moat": round(moat_score, 2),
        },
    )

    return FundamentalScore(
        ticker=ticker,
        score=round(composite, 2),
        dcf_signal=round(dcf_signal, 2),
        safety_score=round(safety_score, 2),
        growth_score=round(growth_score, 2),
        moat_score=round(moat_score, 2),
        dcf_detail=dcf_detail,
        pe_ratio=data.pe_ratio,
        debt_to_equity=data.debt_to_equity,
        gross_margin=data.gross_margin,
        roe=data.return_on_equity,
        free_cash_flow=data.free_cash_flow_ttm,
        analysis_notes=notes,
    )
