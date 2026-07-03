"""
app/analysis/ensemble.py
------------------------
Ensemble Aggregation Engine: combines fundamental, technical, and quantitative
scores into a single weighted Confidence Index and Buy/Hold/Sell signal.

Weighting rationale:
  Fundamental 35% — intrinsic value and balance sheet health are the
                     strongest long-run predictors of return.
  Technical   35% — price action and momentum are most relevant for entry
                     timing, which is critical at all horizons.
  Quantitative 30% — statistical/ML signals act as a cross-check and
                      catch factor exposures the other two modules miss.

Signal thresholds (tuned against typical score distributions):
  ≥ 65 → BUY   (≥ 80: STRONG, 65-79: MODERATE)
  35-64 → HOLD  (NEUTRAL)
  < 35  → SELL  (< 20: STRONG, 20-34: MODERATE)

The entry point for all external callers is `run_ensemble_analysis()`.
It handles all data fetching internally so callers only need a ticker and
time horizon — not pre-fetched DataFrames or FundamentalDataResult objects.
"""

import logging
from datetime import date, timedelta
from typing import Literal

import pandas as pd

from app.analysis.fundamental import run_fundamental_analysis
from app.analysis.models import EnsembleSignal, FundamentalScore, QuantitativeScore, TechnicalScore
from app.analysis.quantitative import run_quantitative_analysis
from app.analysis.technical import run_technical_analysis
from app.ingestion.fundamentals import FundamentalDataService
from app.ingestion.market_data import MarketDataService

logger = logging.getLogger("aureus.analysis.ensemble")

# Module weights — must sum to 1.0
_W_FUNDAMENTAL  = 0.35
_W_TECHNICAL    = 0.35
_W_QUANTITATIVE = 0.30

# Signal thresholds
_BUY_THRESHOLD      = 65.0
_SELL_THRESHOLD     = 35.0
_STRONG_BUY_THRESH  = 80.0
_STRONG_SELL_THRESH = 20.0


# ── Horizon → lookback mapping ─────────────────────────────────────────────────

_HORIZON_CONFIG: dict[str, dict] = {
    "short_term": {
        "lookback_days": 90,
        "frequency": "1d",
        "label": "Short Term (1–4 weeks)",
    },
    "medium_term": {
        "lookback_days": 365,
        "frequency": "1d",
        "label": "Medium Term (1–6 months)",
    },
    "long_term": {
        "lookback_days": 365 * 3,
        "frequency": "1d",
        "label": "Long Term (6 months – 2 years)",
    },
}


# ── Signal classification ──────────────────────────────────────────────────────

def _classify_signal(
    score: float,
) -> tuple[Literal["BUY", "HOLD", "SELL"], Literal["STRONG", "MODERATE", "WEAK"]]:
    if score >= _BUY_THRESHOLD:
        strength = "STRONG" if score >= _STRONG_BUY_THRESH else "MODERATE"
        return "BUY", strength
    if score < _SELL_THRESHOLD:
        strength = "STRONG" if score < _STRONG_SELL_THRESH else "MODERATE"
        return "SELL", strength
    return "HOLD", "WEAK"


# ── Weighted composite ─────────────────────────────────────────────────────────

def _compute_confidence_index(
    fundamental_score: float,
    technical_score: float,
    quantitative_score: float,
) -> float:
    """
    Weighted mean of the three module scores.
    All inputs are expected on [0, 100]. Output is clamped to [0, 100].
    """
    raw = (
        _W_FUNDAMENTAL  * fundamental_score  +
        _W_TECHNICAL    * technical_score    +
        _W_QUANTITATIVE * quantitative_score
    )
    return round(max(0.0, min(100.0, raw)), 2)


# ── Main orchestrator ──────────────────────────────────────────────────────────

def run_ensemble_analysis(
    ticker: str,
    time_horizon: Literal["short_term", "medium_term", "long_term"] = "medium_term",
) -> EnsembleSignal:
    """
    Full pipeline entry point.

    1. Fetch market bars (with provider fallback chain).
    2. Fetch SPY bars for beta/alpha calculation.
    3. Fetch fundamental data (with provider fallback chain).
    4. Run fundamental, technical, and quantitative modules.
    5. Compute weighted Confidence Index and classify signal.
    6. Return a fully populated EnsembleSignal with all sub-breakdowns.

    Args:
        ticker:        Asset symbol (e.g., "AAPL", "MSFT").
        time_horizon:  "short_term" | "medium_term" | "long_term"

    Raises:
        FallbackExhaustedError: if all market data providers fail for `ticker`.
        Any other exception propagates to the caller (Celery task or API handler).
    """
    ticker       = ticker.upper().strip()
    cfg          = _HORIZON_CONFIG.get(time_horizon, _HORIZON_CONFIG["medium_term"])
    lookback     = cfg["lookback_days"]
    frequency    = cfg["frequency"]
    horizon_label = cfg["label"]

    end_date   = date.today()
    start_date = end_date - timedelta(days=lookback)

    logger.info(
        "Ensemble analysis started",
        extra={"ticker": ticker, "horizon": time_horizon, "lookback_days": lookback},
    )

    market_svc      = MarketDataService()
    fundamental_svc = FundamentalDataService()

    # ── 1. Fetch asset bars ───────────────────────────────────────
    market_result = market_svc.fetch_bars(ticker, start_date, end_date, frequency=frequency)
    bars = market_result.bars

    # ── 2. Fetch SPY bars (best-effort; don't fail the whole request) ──
    spy_bars: pd.DataFrame | None = None
    try:
        spy_result = market_svc.fetch_bars("SPY", start_date, end_date, frequency=frequency)
        spy_bars = spy_result.bars
    except Exception as exc:
        logger.warning("SPY fetch failed — alpha/beta will be skipped", extra={"error": str(exc)})

    # ── 3. Fetch fundamental data ─────────────────────────────────
    # Attach current price from market data to FundamentalDataResult
    # so DCF can use it even if Finnhub/EDGAR don't provide it.
    current_price = float(bars["close"].iloc[-1])
    try:
        fund_data = fundamental_svc.fetch_fundamentals(ticker)
        if fund_data.current_price is None:
            fund_data.current_price = current_price
        fundamental_provider = fund_data.provider
    except Exception as exc:
        logger.error(
            "Fundamental data fetch failed — fundamental score will be neutral",
            extra={"ticker": ticker, "error": str(exc)},
        )
        # Create a minimal result so the analysis can still proceed
        from app.ingestion.base import FundamentalDataResult
        fund_data = FundamentalDataResult(
            ticker=ticker,
            provider="unavailable",
            current_price=current_price,
        )
        fundamental_provider = "unavailable"

    # ── 4. Run analysis modules ───────────────────────────────────
    fundamental_result: FundamentalScore = run_fundamental_analysis(
        ticker=ticker,
        data=fund_data,
        time_horizon=time_horizon,
    )

    technical_result: TechnicalScore = run_technical_analysis(
        ticker=ticker,
        bars=bars,
    )

    quantitative_result: QuantitativeScore = run_quantitative_analysis(
        ticker=ticker,
        bars=bars,
        spy_bars=spy_bars,
        rsi_value=technical_result.rsi_14,  # reuse pre-computed RSI
    )

    # ── 5. Ensemble aggregation ───────────────────────────────────
    confidence_index = _compute_confidence_index(
        fundamental_score=fundamental_result.score,
        technical_score=technical_result.score,
        quantitative_score=quantitative_result.score,
    )
    signal, strength = _classify_signal(confidence_index)

    logger.info(
        "Ensemble analysis complete",
        extra={
            "ticker":             ticker,
            "signal":             signal,
            "strength":           strength,
            "confidence_index":   confidence_index,
            "fundamental_score":  fundamental_result.score,
            "technical_score":    technical_result.score,
            "quantitative_score": quantitative_result.score,
            "market_provider":    market_result.provider,
            "fundamental_provider": fundamental_provider,
        },
    )

    return EnsembleSignal(
        ticker=ticker,
        time_horizon=horizon_label,
        signal=signal,
        signal_strength=strength,
        confidence_index=confidence_index,
        fundamental_score=fundamental_result.score,
        technical_score=technical_result.score,
        quantitative_score=quantitative_result.score,
        fundamental=fundamental_result,
        technical=technical_result,
        quantitative=quantitative_result,
        market_data_provider=market_result.provider,
        fundamental_data_provider=fundamental_provider,
    )
