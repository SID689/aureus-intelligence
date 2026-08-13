"""
app/analysis/fundamental.py  (rewrite — structured strengths/weaknesses + honest DCF diagnostics)
------------------------------------------------------------------------------------------------
Two direct fixes here:

1. Every computed sub-signal now also appends a structured dict to
   `signal_breakdown` — {label, score, detail} — instead of only a prose
   note. reasoning.py uses this to name SPECIFIC things helping or hurting
   the score ("gross margin of 43% is a moat component") rather than only
   reporting the composite number.

2. DCF skip diagnosis is now genuinely specific. Previously it just said
   "DCF skipped — missing X" with no explanation of WHY that data was
   missing. Now it distinguishes:
     - FCF is None (the data provider never returned this figure at all —
       states which provider was queried, since Finnhub vs EDGAR fail for
       different reasons)
     - FCF is not None but <= 0 (the company's trailing free cash flow is
       genuinely negative — a real, informative fact about the business,
       not a data gap, and it's reported as such)
     - shares_outstanding missing (same treatment)
"""

import logging
import math

from app.ingestion.base import FundamentalDataResult
from app.analysis.models import DCFResult, FundamentalScore
from app.analysis.reweighting import WeightedSignal, reweight

logger = logging.getLogger("aureus.analysis.fundamental")

_W_DCF, _W_SAFETY, _W_GROWTH, _W_MOAT = 0.30, 0.20, 0.20, 0.12
# Sector-relative valuation. Carries real weight because an absolute multiple
# is close to meaningless on its own — 35x is expensive for a utility and
# ordinary for software. Dropped by the dynamic reweighting when the sector
# medians aren't available (unknown/uncovered sector, or still computing).
_W_RELATIVE = 0.18


def _two_stage_dcf(fcf, near_growth, terminal_growth, discount_rate, projection_years, shares) -> float:
    if discount_rate <= terminal_growth:
        discount_rate, terminal_growth = 0.15, 0.03
    pv_sum, current_fcf = 0.0, fcf
    for year in range(1, projection_years + 1):
        current_fcf *= (1 + near_growth)
        pv_sum += current_fcf / ((1 + discount_rate) ** year)
    terminal_fcf   = current_fcf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
    pv_terminal    = terminal_value / ((1 + discount_rate) ** projection_years)
    return max((pv_sum + pv_terminal) / shares, 0.0)


def _dcf_to_score(intrinsic: float, current_price: float) -> float:
    if intrinsic <= 0 or current_price <= 0:
        return 50.0
    margin = (intrinsic - current_price) / intrinsic
    return max(0.0, min(100.0, 50.0 + (margin / 0.30) * 50.0))


def _diagnose_dcf_skip(data: FundamentalDataResult) -> str:
    """
    The specific, honest answer to 'why was DCF skipped / why is FCF missing'.
    """
    provider = data.provider or "unavailable"

    if data.free_cash_flow_ttm is None:
        if provider == "unavailable":
            return (
                "No fundamental data provider returned results for this ticker at all — "
                "both Finnhub and SEC EDGAR lookups failed (check that FINNHUB_API_KEY is "
                "configured, and that this ticker is SEC-registered if you expected an EDGAR match)."
            )
        return (
            f"{provider} did not report a free cash flow figure for this ticker. "
            + ("Finnhub sometimes omits FCF for smaller-cap or thinly-covered names."
               if provider == "Finnhub" else
               "SEC EDGAR's operating-cash-flow and capex figures use standardized GAAP tags — "
               "if this company's 10-K used a non-standard tag for either figure, the lookup "
               "returns nothing even though the data exists in the filing.")
        )

    if data.free_cash_flow_ttm <= 0:
        return (
            f"{data.free_cash_flow_ttm/1e6:+.1f}M — this company's trailing free cash flow is "
            "genuinely negative, per " + provider + ". A DCF model can't meaningfully discount "
            "cash flows that aren't being generated yet. This is common for companies in a heavy "
            "growth or capex phase; it isn't a data problem, it's a fact about the business worth watching."
        )

    if not data.shares_outstanding:
        return f"{provider} returned free cash flow but not shares outstanding, so per-share intrinsic value can't be computed."

    return "Required inputs unavailable."


def _compute_safety_score(data: FundamentalDataResult, notes: list[str], signals: list[dict]) -> tuple[float, bool]:
    components: list[float] = []

    if data.debt_to_equity is not None:
        de = data.debt_to_equity
        s = 30.0 if de < 0 else (100.0 if de == 0 else max(0.0, 100.0 - (de / 3.0) * 100.0))
        components.append(s)
        notes.append(f"Debt/Equity {de:.2f} → safety component {s:.0f}/100")
        signals.append({"label": "Debt-to-Equity", "score": s, "detail": f"D/E ratio of {de:.2f}" + (" (no debt)" if de == 0 else " signals elevated leverage" if s < 40 else " is conservative")})

    if data.current_ratio is not None:
        cr = data.current_ratio
        s = max(0.0, min(100.0, (cr - 1.0) * 50.0))
        components.append(s)
        notes.append(f"Current ratio {cr:.2f} → liquidity component {s:.0f}/100")
        signals.append({"label": "Current Ratio", "score": s, "detail": f"Current ratio of {cr:.2f}" + (" shows tight near-term liquidity" if s < 40 else " indicates solid short-term liquidity")})

    if data.operating_margin is not None:
        om = data.operating_margin
        s = max(0.0, min(100.0, (om / 0.20) * 80.0 + 20.0 if om > 0 else om * 200.0 + 20.0))
        components.append(s)
        notes.append(f"Operating margin {om*100:.1f}% → efficiency component {s:.0f}/100")
        signals.append({"label": "Operating Margin", "score": s, "detail": f"Operating margin of {om*100:.1f}%" + (" is thin" if s < 40 else " reflects efficient core operations")})

    if not components:
        return 50.0, False
    return sum(components) / len(components), True


def _compute_growth_score(data: FundamentalDataResult, notes: list[str], signals: list[dict]) -> tuple[float, bool]:
    components: list[float] = []

    if data.revenue_growth_yoy is not None:
        g = data.revenue_growth_yoy
        s = max(0.0, min(100.0, 50.0 + (g / 0.20) * 50.0))
        components.append(s)
        notes.append(f"Revenue growth YoY {g*100:.1f}% → growth component {s:.0f}/100")
        signals.append({"label": "Revenue Growth (YoY)", "score": s, "detail": f"Revenue grew {g*100:+.1f}% year-over-year" + (" — a genuine headwind" if s < 40 else " — outpacing the 20% benchmark" if s > 80 else "")})

    if len(data.revenue_history) >= 3:
        valid = [v for v in data.revenue_history if v > 0]
        if len(valid) >= 2:
            years = len(valid) - 1
            cagr = (valid[-1] / valid[0]) ** (1.0 / years) - 1.0
            s = max(0.0, min(100.0, 50.0 + (cagr / 0.15) * 50.0))
            components.append(s)
            notes.append(f"{years}-yr revenue CAGR {cagr*100:.1f}% → trend component {s:.0f}/100")
            signals.append({"label": f"{years}-Year Revenue CAGR", "score": s, "detail": f"Revenue compounded at {cagr*100:+.1f}% annually over {years} years"})

    if len(data.net_income_history) >= 2:
        ni = data.net_income_history
        consistency = sum(1 for v in ni if v > 0) / len(ni)
        s = consistency * 100.0
        components.append(s)
        if consistency < 1.0:
            signals.append({"label": "Earnings Consistency", "score": s, "detail": f"Profitable in only {int(consistency*len(ni))} of the last {len(ni)} reported years"})

    if not components:
        return 50.0, False
    return sum(components) / len(components), True


def _compute_moat_score(data: FundamentalDataResult, notes: list[str], signals: list[dict]) -> tuple[float, bool]:
    components: list[float] = []

    if data.gross_margin is not None:
        gm = data.gross_margin
        s = max(0.0, min(100.0, (gm / 0.40) * 80.0 + 20.0))
        components.append(s)
        notes.append(f"Gross margin {gm*100:.1f}% → moat component {s:.0f}/100")
        signals.append({"label": "Gross Margin", "score": s, "detail": f"Gross margin of {gm*100:.1f}%" + (" suggests limited pricing power or commodity exposure" if s < 40 else " points to real pricing power" if s > 75 else "")})

    if data.return_on_equity is not None:
        roe = data.return_on_equity
        s = 10.0 if roe < 0 else max(0.0, min(100.0, (roe / 0.20) * 100.0))
        components.append(s)
        notes.append(f"ROE {roe*100:.1f}% → durability component {s:.0f}/100")
        signals.append({"label": "Return on Equity", "score": s, "detail": f"ROE of {roe*100:.1f}%" + (" is a red flag on capital efficiency" if s < 30 else " reflects strong capital efficiency" if s > 75 else "")})

    if len(data.revenue_history) >= 3:
        vals = [v for v in data.revenue_history if v > 0]
        if len(vals) >= 3:
            mean_rev = sum(vals) / len(vals)
            std_rev  = math.sqrt(sum((v - mean_rev) ** 2 for v in vals) / len(vals))
            cv       = std_rev / mean_rev if mean_rev > 0 else 1.0
            s = max(20.0, min(90.0, 90.0 - (cv / 0.5) * 70.0))
            components.append(s)

    if not components:
        return 50.0, False
    return sum(components) / len(components), True


def run_fundamental_analysis(
    ticker: str,
    data: FundamentalDataResult,
    time_horizon: str = "medium_term",
    sector_comparison=None,   # SectorComparison | None, from analysis/sector_peers.py
) -> FundamentalScore:
    notes: list[str] = []
    signals: list[dict] = []
    horizon_years = {"short_term": 3, "medium_term": 5, "long_term": 10}.get(time_horizon, 5)

    dcf_detail: DCFResult | None = None
    dcf_signal = 50.0
    dcf_computed = False
    dcf_skip_reason: str | None = None

    if (
        data.free_cash_flow_ttm is not None and data.free_cash_flow_ttm > 0
        and data.shares_outstanding is not None and data.shares_outstanding > 0
        and data.current_price is not None and data.current_price > 0
    ):
        near_growth     = min(data.revenue_growth_yoy or 0.08, 0.40)
        terminal_growth = 0.025
        discount_rate   = 0.10
        try:
            intrinsic = _two_stage_dcf(
                data.free_cash_flow_ttm, near_growth, terminal_growth,
                discount_rate, horizon_years, data.shares_outstanding,
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
            dcf_signal   = _dcf_to_score(intrinsic, data.current_price)
            dcf_computed = True
            notes.append(
                f"DCF intrinsic value ${intrinsic:.2f} vs current ${data.current_price:.2f} "
                f"({margin*100:+.1f}% margin of safety) → DCF component {dcf_signal:.0f}/100"
            )
            signals.append({
                "label": "DCF Margin of Safety", "score": dcf_signal,
                "detail": f"Trading {abs(margin)*100:.1f}% {'below' if margin > 0 else 'above'} estimated intrinsic value of ${intrinsic:.2f}",
            })
        except Exception as exc:
            dcf_skip_reason = f"DCF calculation raised an error ({exc}) despite having the required inputs — excluded from composite."
            notes.append(dcf_skip_reason)
            logger.warning("DCF failed", extra={"ticker": ticker, "error": str(exc)})
    else:
        dcf_skip_reason = _diagnose_dcf_skip(data)
        notes.append(f"DCF skipped: {dcf_skip_reason}")

    safety_score, safety_computed = _compute_safety_score(data, notes, signals)
    growth_score, growth_computed = _compute_growth_score(data, notes, signals)
    moat_score,   moat_computed   = _compute_moat_score(data, notes, signals)

    # ── Sector-relative valuation ─────────────────────────────────────
    relative_score, relative_computed = 50.0, False
    if sector_comparison is not None and sector_comparison.relative_score is not None:
        relative_score, relative_computed = sector_comparison.relative_score, True
        cheap = [k for k, c in sector_comparison.comparisons.items()
                 if c["favourable"] and k in ("pe_ratio", "price_to_sales", "pb_ratio", "ev_to_fcf")]
        rich = [k for k, c in sector_comparison.comparisons.items()
                if not c["favourable"] and k in ("pe_ratio", "price_to_sales", "pb_ratio", "ev_to_fcf")]
        pretty = {"pe_ratio": "P/E", "price_to_sales": "P/S", "pb_ratio": "P/B", "ev_to_fcf": "EV/FCF"}
        bits = []
        if cheap:
            bits.append("below the sector median on " + ", ".join(pretty[k] for k in cheap))
        if rich:
            bits.append("above it on " + ", ".join(pretty[k] for k in rich))
        notes.append(
            f"Valuation vs {sector_comparison.sector} peers "
            f"(n={sector_comparison.peer_count}) → relative component {relative_score:.0f}/100"
        )
        signals.append({
            "label": "Valuation vs Sector", "score": relative_score,
            "detail": (f"Against the {sector_comparison.sector} median, trades "
                       + ("; ".join(bits) if bits else "broadly in line")
                       + ". An absolute multiple says little without this comparison."),
        })
    elif sector_comparison is not None and sector_comparison.stale:
        notes.append(f"Sector medians for {sector_comparison.sector} are still computing — "
                     f"relative valuation excluded from this run")

    result = reweight([
        WeightedSignal("dcf_signal",    dcf_signal,    _W_DCF,    dcf_computed),
        WeightedSignal("safety_score",  safety_score,  _W_SAFETY, safety_computed),
        WeightedSignal("growth_score",  growth_score,  _W_GROWTH, growth_computed),
        WeightedSignal("moat_score",    moat_score,    _W_MOAT,   moat_computed),
        WeightedSignal("relative_valuation", relative_score, _W_RELATIVE, relative_computed),
    ])

    if result.dropped_signals:
        notes.append(
            f"Excluded from scoring (no real data): {', '.join(result.dropped_signals)}. "
            f"Their weight was redistributed to the components that had data."
        )

    logger.info(
        "Fundamental analysis complete",
        extra={
            "ticker": ticker, "score": result.composite_score,
            "data_completeness": result.data_completeness,
            "dropped": result.dropped_signals, "dcf_computed": dcf_computed,
        },
    )

    return FundamentalScore(
        ticker=ticker,
        score=result.composite_score,
        dcf_signal=round(dcf_signal, 2),
        safety_score=round(safety_score, 2),
        growth_score=round(growth_score, 2),
        moat_score=round(moat_score, 2),
        dcf_detail=dcf_detail,
        dcf_skip_reason=dcf_skip_reason,
        fundamental_data_provider=data.provider or "unavailable",
        pe_ratio=data.pe_ratio,
        debt_to_equity=data.debt_to_equity,
        gross_margin=data.gross_margin,
        roe=data.return_on_equity,
        pb_ratio=data.pb_ratio,
        operating_margin=data.operating_margin,
        revenue_growth_yoy=data.revenue_growth_yoy,
        current_ratio=data.current_ratio,
        market_cap=data.market_cap,
        ev_to_ebitda=data.ev_to_ebitda,
        price_to_sales=data.price_to_sales,
        fcf_yield=data.fcf_yield,
        roic=data.roic,
        interest_coverage=data.interest_coverage,
        free_cash_flow=data.free_cash_flow_ttm,
        data_completeness=result.data_completeness,
        effective_weights=result.effective_weights,
        signal_breakdown=signals,
        analysis_notes=notes,
    )
