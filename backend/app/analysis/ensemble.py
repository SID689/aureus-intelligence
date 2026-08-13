"""
app/analysis/ensemble.py  (Phase 6 rewrite)
---------------------------------------------
Top-level ensemble aggregation now uses the SAME dynamic-reweighting
logic as each individual module (see reweighting.py). If, say, the
fundamental module had near-zero data completeness for a given ticker
(common for smaller/foreign tickers where EDGAR/Finnhub don't return
much), its 35% baseline weight is proportionally redistributed to
technical and quantitative — both of which only need price history,
which is far more reliably available. This is what actually fixes the
"everything is HOLD with similar scores" bug: previously, a broken
fundamental leg would silently pull every score toward 50 at full
weight; now a broken leg gets discounted, and the signal that remains
is driven by data that's genuinely known about that specific stock.

Also generates `reasoning` — a grounded explanation of the score,
optionally polished by an LLM and validated through the guardrails
(see analysis/reasoning.py).
"""

import logging
from datetime import date, timedelta
from typing import Literal

import pandas as pd

from app.analysis.fundamental import run_fundamental_analysis
from app.analysis.models import EnsembleSignal, FundamentalScore, QuantitativeScore, TechnicalScore
from app.analysis.quantitative import run_quantitative_analysis
from app.analysis.reasoning import generate_reasoning
from app.analysis.reweighting import WeightedSignal, reweight
from app.analysis.sector_peers import compare_to_sector
from app.analysis.thesis import build_theses
from app.analysis.technical import run_technical_analysis
from app.ingestion.fundamentals import FundamentalDataService
from app.ingestion.market_data import MarketDataService

logger = logging.getLogger("aureus.analysis.ensemble")

# Pillar weights are a function of the SELECTED HORIZON, not fixed.
#
# The three pillars answer questions that matter on different clocks. Over a
# few days price action and flow dominate and a DCF is close to irrelevant —
# a cheap stock can stay cheap for years. Over a multi-year hold the reverse
# is true: today's RSI carries no information about where the business is in
# 2030, while margins, returns on capital and balance-sheet strength do.
# Applying one fixed blend to every horizon systematically mis-weights the
# evidence, which is why this is horizon-dependent.
#
# Read as (fundamental, technical, quantitative); each row sums to 1.0.
_HORIZON_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "short_term":  (0.10, 0.60, 0.30),
    "medium_term": (0.30, 0.35, 0.35),
    "long_term":   (0.60, 0.15, 0.25),
}

# Retained for callers that need a horizon-agnostic default — notably
# app/backtesting/engine.py, which replays the ensemble without a horizon.
_W_FUNDAMENTAL, _W_TECHNICAL, _W_QUANTITATIVE = _HORIZON_WEIGHTS["medium_term"]

_BUY_THRESHOLD, _SELL_THRESHOLD = 65.0, 35.0
_STRONG_BUY_THRESH, _STRONG_SELL_THRESH = 80.0, 20.0

# Minimum data completeness for a module to count as "computed" at all
# for reweighting purposes at the ensemble level. Below this, the module
# is so thin it shouldn't influence which way the signal leans.
_MODULE_COMPLETENESS_FLOOR = 0.15

_HORIZON_CONFIG: dict[str, dict] = {
    "short_term":  {"lookback_days": 90,       "frequency": "1d", "label": "Short Term (1-4 weeks)"},
    "medium_term": {"lookback_days": 365,      "frequency": "1d", "label": "Medium Term (1-6 months)"},
    "long_term":   {"lookback_days": 365 * 3,  "frequency": "1d", "label": "Long Term (6 months - 2 years)"},
}


def _classify_signal(score: float) -> tuple[Literal["BUY", "HOLD", "SELL"], Literal["STRONG", "MODERATE", "WEAK"]]:
    if score >= _BUY_THRESHOLD:
        return "BUY", "STRONG" if score >= _STRONG_BUY_THRESH else "MODERATE"
    if score < _SELL_THRESHOLD:
        return "SELL", "STRONG" if score < _STRONG_SELL_THRESH else "MODERATE"
    return "HOLD", "WEAK"


def run_ensemble_analysis(
    ticker: str,
    time_horizon: Literal["short_term", "medium_term", "long_term"] = "medium_term",
    use_llm_reasoning: bool = True,
) -> EnsembleSignal:
    ticker = ticker.upper().strip()
    cfg = _HORIZON_CONFIG.get(time_horizon, _HORIZON_CONFIG["medium_term"])
    lookback, frequency, horizon_label = cfg["lookback_days"], cfg["frequency"], cfg["label"]

    end_date, start_date = date.today(), date.today() - timedelta(days=lookback)

    logger.info("Ensemble analysis started", extra={"ticker": ticker, "horizon": time_horizon})

    market_svc, fundamental_svc = MarketDataService(), FundamentalDataService()

    market_result = market_svc.fetch_bars(ticker, start_date, end_date, frequency=frequency)
    bars = market_result.bars

    spy_bars: pd.DataFrame | None = None
    try:
        spy_bars = market_svc.fetch_bars("SPY", start_date, end_date, frequency=frequency).bars
    except Exception as exc:
        logger.warning("SPY fetch failed — alpha/beta skipped", extra={"error": str(exc)})

    current_price = float(bars["close"].iloc[-1])
    try:
        fund_data = fundamental_svc.fetch_fundamentals(ticker)
        if fund_data.current_price is None:
            fund_data.current_price = current_price
        fundamental_provider = fund_data.provider
    except Exception as exc:
        logger.error("Fundamental data fetch failed", extra={"ticker": ticker, "error": str(exc)})
        from app.ingestion.base import FundamentalDataResult
        fund_data = FundamentalDataResult(ticker=ticker, provider="unavailable", current_price=current_price)
        fundamental_provider = "unavailable"

    sector_cmp = compare_to_sector(
        ticker, fund_data.sector,
        {
            "pe_ratio": fund_data.pe_ratio,
            "price_to_sales": fund_data.price_to_sales,
            "pb_ratio": fund_data.pb_ratio,
            # Sector medians come from Finnhub, which reports margins/returns as
            # PERCENTAGES. Our own values are fractions (see _pct_to_fraction),
            # so scale back up before comparing or every company looks 99%
            # below its sector on every quality metric.
            "gross_margin": (fund_data.gross_margin * 100) if fund_data.gross_margin is not None else None,
            "operating_margin": (fund_data.operating_margin * 100) if fund_data.operating_margin is not None else None,
            "return_on_equity": (fund_data.return_on_equity * 100) if fund_data.return_on_equity is not None else None,
            "roic": (fund_data.roic * 100) if fund_data.roic is not None else None,
            "debt_to_equity": fund_data.debt_to_equity,
        },
    )

    fundamental_result: FundamentalScore = run_fundamental_analysis(
        ticker, fund_data, time_horizon, sector_comparison=sector_cmp
    )
    technical_result: TechnicalScore = run_technical_analysis(ticker, bars)
    quantitative_result: QuantitativeScore = run_quantitative_analysis(
        ticker, bars, spy_bars=spy_bars, rsi_value=technical_result.rsi_14,
    )

    # ── Top-level dynamic reweighting (THE core bug fix) ────────────────
    fund_computed  = fundamental_result.data_completeness  >= _MODULE_COMPLETENESS_FLOOR
    tech_computed  = technical_result.data_completeness    >= _MODULE_COMPLETENESS_FLOOR
    quant_computed = quantitative_result.data_completeness >= _MODULE_COMPLETENESS_FLOOR

    w_fund, w_tech, w_quant = _HORIZON_WEIGHTS.get(time_horizon, _HORIZON_WEIGHTS["medium_term"])

    top_result = reweight([
        WeightedSignal("fundamental",  fundamental_result.score,  w_fund,  fund_computed),
        WeightedSignal("technical",    technical_result.score,    w_tech,  tech_computed),
        WeightedSignal("quantitative", quantitative_result.score, w_quant, quant_computed),
    ])

    confidence_index = top_result.composite_score
    signal, strength = _classify_signal(confidence_index)
    overall_completeness = round(
        (fundamental_result.data_completeness + technical_result.data_completeness + quantitative_result.data_completeness) / 3,
        3,
    )
    module_weights_used = {
        "fundamental":  top_result.effective_weights.get("fundamental", 0.0),
        "technical":    top_result.effective_weights.get("technical", 0.0),
        "quantitative": top_result.effective_weights.get("quantitative", 0.0),
    }

    reasoning_text, reasoning_source = generate_reasoning(
        ticker=ticker, time_horizon_label=horizon_label, signal=signal, strength=strength,
        confidence_index=confidence_index, fundamental=fundamental_result, technical=technical_result,
        quantitative=quantitative_result, module_weights=module_weights_used, use_llm_polish=use_llm_reasoning,
    )

    bull, bear = build_theses(
        ticker, time_horizon, fundamental_result, technical_result,
        quantitative_result, fund_data,
    )

    logger.info("Ensemble analysis complete", extra={
        "ticker": ticker, "signal": signal, "confidence_index": confidence_index,
        "overall_completeness": overall_completeness, "module_weights": module_weights_used,
    })

    return EnsembleSignal(
        ticker=ticker, time_horizon=horizon_label, signal=signal, signal_strength=strength,
        confidence_index=confidence_index,
        fundamental_score=fundamental_result.score, technical_score=technical_result.score,
        quantitative_score=quantitative_result.score,
        fundamental=fundamental_result, technical=technical_result, quantitative=quantitative_result,
        market_data_provider=market_result.provider, fundamental_data_provider=fundamental_provider,
        reasoning=reasoning_text, reasoning_source=reasoning_source,
        sector=fund_data.sector,
        sector_comparison=sector_cmp.to_dict() if sector_cmp else {},
        bull_case=bull.to_dict(), bear_case=bear.to_dict(),
        overall_data_completeness=overall_completeness, module_weights_used=module_weights_used,
    )
