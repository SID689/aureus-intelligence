"""
app/backtesting/engine.py
----------------------------
Vectorized-where-possible, loop-where-necessary backtester that replays
Aureus's REAL technical and quantitative analysis modules bar-by-bar
against historical data — not a separate reimplementation that could
drift from what's actually running in production.

===================================================================
HOW LOOK-AHEAD BIAS IS MITIGATED (explicit, per the Phase 6 brief)
===================================================================
1. TRUNCATED WINDOWS: at simulated decision point `i`, every analysis
   function receives `bars.iloc[:i+1]` — only price history up to and
   including that day. It is structurally impossible for the signal at
   day `i` to see day `i+1`'s price, because that data simply isn't in
   the DataFrame passed to the function.

2. FUNDAMENTAL ANALYSIS IS EXCLUDED FROM THE BACKTEST. This is the most
   important mitigation and deserves explanation: fundamental analysis
   (DCF, safety ratios, growth trends) relies on filed financial
   statements. There is no free, point-in-time fundamentals database
   available to this project — Finnhub and SEC EDGAR both return the
   ISSUER'S CURRENT financials, not a snapshot of what was known on a
   historical date. Using today's balance sheet to "backtest" a decision
   from a year ago would leak information the model could not have had
   at the time (a classic, severe form of look-ahead bias). Rather than
   fake point-in-time fundamentals, the backtest re-weights the ensemble
   to technical + quantitative only, using the SAME aggregator

   NOTE (pillar refactor): the live three-pillar blend is now
   Fundamental / Technical / SENTIMENT, with quantitative relocated to
   the Quant Lab. This backtest deliberately keeps using the quantitative
   module rather than following that change, because sentiment cannot be
   replayed historically without look-ahead bias — the news and social
   APIs serve only a recent window, so "what was sentiment on this date
   in 2023" is unobtainable, and substituting today's reading would be
   precisely the look-ahead error this module exists to avoid.
   (analysis/aggregation.py) as production so the math is consistent,
   and this exclusion is logged in every report so results are never
   misread as "the full ensemble backtested well" when only 2 of 3 legs
   were actually tested.

   KEEPING THE MATH CONSISTENT IS LOAD-BEARING, not tidiness. When the
   live ensemble moved from averaging its legs to pooling them as
   evidence, this file briefly kept averaging while still importing the
   live BUY/SELL thresholds. The result was not an error anywhere — it
   was a backtest quietly measuring a different strategy from the one
   the product runs. Measured over 48 decision points it produced 15 BUY
   against 1 SELL, because two quantitative scorers (12-1 momentum
   averaging 70/100, alpha vs SPY averaging 72/100) put the composite
   permanently near the BUY line and nowhere near the SELL line. Both
   are now centred on their measured behaviour (analysis/calibration.py)
   and both legs are pooled the way production pools them.

3. NO PARAMETER FITTING: the BUY/SELL thresholds and module weights used
   here are imported directly from the live `ensemble.py` and the
   individual module files — not redefined or tuned against this
   backtest's own results. There is no optimization loop in this file.
   This avoids data-snooping bias (fitting parameters to the test set
   and then reporting inflated performance on that same set).

4. FORWARD RETURNS USE FUTURE DATA ON PURPOSE — this is not a bug. The
   forward return is the thing being predicted, computed AFTER the
   signal is locked in, purely to score the signal's accuracy. It is
   never fed back into the signal generation itself (see mitigation #1).
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.analysis.ensemble import _BUY_THRESHOLD, _SELL_THRESHOLD, _STRONG_BUY_THRESH, _STRONG_SELL_THRESH
from app.analysis.quantitative import run_quantitative_analysis
from app.analysis.aggregation import EvidenceSignal, combine_evidence
from app.analysis.technical import run_technical_analysis
from app.backtesting.metrics import SignalRecord, compile_full_report
from app.ingestion.market_data import MarketDataService

logger = logging.getLogger("aureus.backtesting.engine")

# Backtest-mode weights: technical (0.35) + quantitative (0.30) from the
# live ensemble, renormalized to sum to 1.0 since fundamental (0.35) is
# excluded (see module docstring, mitigation #2).
_BT_W_TECHNICAL, _BT_W_QUANTITATIVE = 0.35, 0.30


def _classify(score: float) -> str:
    if score >= _BUY_THRESHOLD:
        return "BUY"
    if score < _SELL_THRESHOLD:
        return "SELL"
    return "HOLD"


@dataclass
class BacktestConfig:
    ticker: str
    start_date: date
    end_date: date
    forward_window_days: int = 21     # how far ahead we measure "did the signal pay off"
    step_days: int = 5                # generate a new signal every N trading days
    min_lookback_days: int = 260      # need 252+ days of history before momentum/ML signals can compute
    risk_free_rate: float = 0.05


def run_backtest(config: BacktestConfig) -> dict:
    """
    Main entry point. Fetches history, replays the ensemble bar-by-bar,
    and returns a full institutional metrics report.
    """
    ticker = config.ticker.upper().strip()
    logger.info("Backtest started", extra={"ticker": ticker, "start": str(config.start_date), "end": str(config.end_date)})

    # Fetch extra buffer on both ends: lookback buffer before start_date so
    # early signals have enough history, forward buffer after end_date so
    # the last signal has a forward window to be scored against.
    fetch_start = config.start_date - timedelta(days=int(config.min_lookback_days * 1.6))  # trading days -> calendar days buffer
    fetch_end   = config.end_date + timedelta(days=int(config.forward_window_days * 1.6))

    svc = MarketDataService()
    bars     = svc.fetch_bars(ticker, fetch_start, fetch_end, frequency="1d").bars
    spy_bars = svc.fetch_bars("SPY",  fetch_start, fetch_end, frequency="1d").bars

    # Align on shared trading dates only
    aligned = bars.join(spy_bars[["close"]].rename(columns={"close": "spy_close"}), how="inner")
    if len(aligned) < config.min_lookback_days + config.forward_window_days + 10:
        raise ValueError(
            f"Not enough overlapping history for {ticker} and SPY to backtest "
            f"this window ({len(aligned)} aligned bars available, "
            f"{config.min_lookback_days + config.forward_window_days} required)."
        )

    signal_records: list[SignalRecord] = []
    daily_position = pd.Series(0.0, index=aligned.index)  # 1.0 = long, 0.0 = flat

    n = len(aligned)
    decision_indices = range(config.min_lookback_days, n - config.forward_window_days, config.step_days)

    for i in decision_indices:
        # ── Mitigation #1: truncated window, no future data visible ────
        window_bars = aligned.iloc[: i + 1][["open", "high", "low", "close", "volume"]]
        window_spy  = aligned.iloc[: i + 1][["spy_close"]].rename(columns={"spy_close": "close"})

        try:
            technical_result = run_technical_analysis(ticker, window_bars)
            quant_result = run_quantitative_analysis(
                ticker, window_bars, spy_bars=window_spy, rsi_value=technical_result.rsi_14,
            )
        except Exception as exc:
            logger.warning("Signal generation failed at index", extra={"index": i, "error": str(exc)})
            continue

        # ── Mitigation #3: the SAME aggregator the live engine uses ──────
        # Pools the two legs' standardised evidence, exactly as
        # ensemble.py pools its three. If the backtester aggregated
        # differently from production, a backtest would be measuring a
        # strategy nobody is running — and it would do so silently, which
        # is the worst version of that failure.
        top = combine_evidence(
            [
                EvidenceSignal("technical", technical_result.evidence_z, _BT_W_TECHNICAL,
                               technical_result.data_completeness > 0.15),
                EvidenceSignal("quantitative", quant_result.evidence_z, _BT_W_QUANTITATIVE,
                               quant_result.data_completeness > 0.15),
            ],
            group="backtest",
            pre_standardised=True,
        )
        signal = _classify(top.composite_score)

        # ── Forward returns (computed AFTER the fact, purely for scoring) ──
        entry_price = float(aligned["close"].iloc[i])
        exit_price  = float(aligned["close"].iloc[i + config.forward_window_days])
        forward_return = (exit_price - entry_price) / entry_price

        spy_entry = float(aligned["spy_close"].iloc[i])
        spy_exit  = float(aligned["spy_close"].iloc[i + config.forward_window_days])
        forward_benchmark_return = (spy_exit - spy_entry) / spy_entry

        signal_records.append(SignalRecord(
            date=str(aligned.index[i].date()),
            ticker=ticker,
            signal=signal,
            confidence=top.composite_score,
            forward_return=forward_return,
            forward_benchmark_return=forward_benchmark_return,
        ))

        # Update the position held from this decision date until the next one
        next_i = min(i + config.step_days, n - 1)
        daily_position.iloc[i:next_i] = 1.0 if signal == "BUY" else 0.0

    if not signal_records:
        raise ValueError(f"No signals were generated for {ticker} in this window: try a longer date range.")

    # ── Build the strategy's daily return series and equity curve ──────
    asset_daily_returns = aligned["close"].pct_change().fillna(0.0)
    strategy_daily_returns = asset_daily_returns * daily_position.shift(1).fillna(0.0)  # shift(1): act on yesterday's signal, not today's close
    equity_curve = (1 + strategy_daily_returns).cumprod()

    report = compile_full_report(
        returns=strategy_daily_returns[strategy_daily_returns.index >= aligned.index[config.min_lookback_days]],
        equity_curve=equity_curve[equity_curve.index >= aligned.index[config.min_lookback_days]],
        signal_records=signal_records,
        risk_free_rate=config.risk_free_rate,
    )

    report["config"] = {
        "ticker": ticker,
        "start_date": str(config.start_date),
        "end_date": str(config.end_date),
        "forward_window_days": config.forward_window_days,
        "step_days": config.step_days,
        "total_signals_generated": len(signal_records),
    }
    report["methodology_note"] = (
        "This backtest excludes the fundamental analysis module (35% weight in live "
        "production scoring) because no free point-in-time fundamentals dataset is "
        "available, using current financials to score historical decisions would be "
        "look-ahead bias. Technical (35%) and quantitative (30%) weights were "
        "renormalized to sum to 1.0. See app/backtesting/engine.py module docstring "
        "for the full bias-mitigation methodology."
    )

    logger.info("Backtest complete", extra={
        "ticker": ticker, "signals": len(signal_records),
        "sharpe": report.get("sharpe_ratio"), "total_return_pct": report.get("total_return_pct"),
    })
    return report
