"""
app/backtesting/metrics.py
-----------------------------
Institutional-standard performance metrics, computed from a return series
and/or a log of (signal, forward_return, forward_benchmark_return) tuples.

All functions are pure (no I/O, no side effects) so they're independently
unit-testable and reusable outside the backtest engine (e.g., for live
portfolio performance reporting later).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

_TRADING_DAYS_PER_YEAR = 252


# =====================================================================
# Standard risk-adjusted return metrics
# =====================================================================

def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float | None:
    """
    Annualized Sharpe ratio: (mean excess return / stdev of excess return) * sqrt(252).
    Uses daily returns; risk_free_rate is an annual rate, converted to daily internally.
    """
    if len(returns) < 20:
        return None
    daily_rf = (1 + risk_free_rate) ** (1 / _TRADING_DAYS_PER_YEAR) - 1
    excess = returns - daily_rf
    std = excess.std()
    if std == 0 or pd.isna(std):
        return None
    return float((excess.mean() / std) * np.sqrt(_TRADING_DAYS_PER_YEAR))


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float | None:
    """
    Annualized Sortino ratio: like Sharpe, but only penalizes downside
    volatility (returns below the risk-free rate), not upside variance.
    This is the more appropriate metric for asymmetric strategies since
    Sharpe treats a big upside month as "risk" identically to a big
    downside month.
    """
    if len(returns) < 20:
        return None
    daily_rf = (1 + risk_free_rate) ** (1 / _TRADING_DAYS_PER_YEAR) - 1
    excess = returns - daily_rf
    downside = excess[excess < 0]
    if len(downside) == 0:
        return None
    downside_std = downside.std()
    if downside_std == 0 or pd.isna(downside_std):
        return None
    return float((excess.mean() / downside_std) * np.sqrt(_TRADING_DAYS_PER_YEAR))


def max_drawdown(equity_curve: pd.Series) -> dict:
    """
    Maximum peak-to-trough decline in an equity curve.
    Returns the drawdown magnitude plus the dates of the peak and trough
    so it's actually interpretable, not just a bare number.
    """
    if len(equity_curve) < 2:
        return {"max_drawdown_pct": 0.0, "peak_date": None, "trough_date": None}

    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max

    trough_idx = drawdown.idxmin()
    trough_val = drawdown.min()
    peak_idx = equity_curve.loc[:trough_idx].idxmax()

    return {
        "max_drawdown_pct": float(trough_val * 100),
        "peak_date": str(peak_idx),
        "trough_date": str(trough_idx),
    }


def win_loss_ratio(returns: pd.Series) -> dict:
    """
    Fraction of positive vs negative periods, plus average magnitude of
    each, and the classic win-rate-weighted payoff ratio.
    """
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    total = len(wins) + len(losses)
    if total == 0:
        return {"win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0, "payoff_ratio": 0.0}

    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0

    return {
        "win_rate": round(len(wins) / total * 100, 2),
        "avg_win_pct": round(avg_win * 100, 3),
        "avg_loss_pct": round(avg_loss * 100, 3),
        "payoff_ratio": round(abs(avg_win / avg_loss), 3) if avg_loss != 0 else None,
    }


# =====================================================================
# Custom metric: Signal Accuracy vs. Realized Forward Alpha
# =====================================================================

@dataclass
class SignalRecord:
    """One historical point where the ensemble generated a signal."""
    date: str
    ticker: str
    signal: str           # "BUY" | "HOLD" | "SELL"
    confidence: float
    forward_return: float           # realized return of the STOCK over the forward window
    forward_benchmark_return: float # realized return of SPY over the same window


def signal_accuracy_vs_forward_alpha(records: list[SignalRecord]) -> dict:
    """
    THE custom institutional metric requested in the Phase 6 brief.

    Definition:
      forward_alpha = forward_return - forward_benchmark_return
      A BUY signal is "correct" if forward_alpha > 0 (stock beat the market
        after the model said BUY).
      A SELL signal is "correct" if forward_alpha < 0 (stock underperformed
        the market after the model said SELL — validating the caution).
      HOLD signals are excluded from the accuracy score (there's no
        directional claim to validate) but their average forward alpha is
        still reported for reference.

    This measures whether the ensemble's signals actually contain
    information about FUTURE relative performance, not just whether the
    stock went up in absolute terms (which mostly reflects broad market
    drift, not model skill).
    """
    buy_records  = [r for r in records if r.signal == "BUY"]
    sell_records = [r for r in records if r.signal == "SELL"]
    hold_records = [r for r in records if r.signal == "HOLD"]

    def _alpha(r: SignalRecord) -> float:
        return r.forward_return - r.forward_benchmark_return

    def _accuracy(recs: list[SignalRecord], correct_if_positive: bool) -> dict:
        if not recs:
            return {"n": 0, "accuracy_pct": None, "avg_forward_alpha_pct": None}
        alphas = [_alpha(r) for r in recs]
        correct = sum(1 for a in alphas if (a > 0) == correct_if_positive)
        return {
            "n": len(recs),
            "accuracy_pct": round(correct / len(recs) * 100, 2),
            "avg_forward_alpha_pct": round(float(np.mean(alphas)) * 100, 3),
            "median_forward_alpha_pct": round(float(np.median(alphas)) * 100, 3),
        }

    buy_stats  = _accuracy(buy_records, correct_if_positive=True)
    sell_stats = _accuracy(sell_records, correct_if_positive=False)

    hold_alphas = [_alpha(r) for r in hold_records]
    hold_stats = {
        "n": len(hold_records),
        "avg_forward_alpha_pct": round(float(np.mean(hold_alphas)) * 100, 3) if hold_alphas else None,
    }

    # Blended accuracy across directional (BUY+SELL) calls only
    directional = buy_records + sell_records
    if directional:
        correct_count = sum(
            1 for r in directional
            if (_alpha(r) > 0) == (r.signal == "BUY")
        )
        overall_accuracy = round(correct_count / len(directional) * 100, 2)
    else:
        overall_accuracy = None

    return {
        "buy_signals": buy_stats,
        "sell_signals": sell_stats,
        "hold_signals": hold_stats,
        "overall_directional_accuracy_pct": overall_accuracy,
        "interpretation": (
            "accuracy_pct measures how often the signal's implied direction matched "
            "realized forward alpha (stock return minus S&P 500 return over the same "
            "forward window). 50% is what random guessing would produce; meaningfully "
            "above 50% suggests the signal carries real information, not just market beta."
        ),
    }


def compile_full_report(
    returns: pd.Series,
    equity_curve: pd.Series,
    signal_records: list[SignalRecord],
    risk_free_rate: float = 0.05,
) -> dict:
    """Bundle every metric into one report dict — the main entry point for run_backtest.py."""
    return {
        "sharpe_ratio": sharpe_ratio(returns, risk_free_rate),
        "sortino_ratio": sortino_ratio(returns, risk_free_rate),
        "max_drawdown": max_drawdown(equity_curve),
        "win_loss": win_loss_ratio(returns),
        "signal_accuracy_vs_forward_alpha": signal_accuracy_vs_forward_alpha(signal_records),
        "total_return_pct": round(float((equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100), 2) if len(equity_curve) > 1 else None,
        "annualized_return_pct": (
            round(float(((equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (_TRADING_DAYS_PER_YEAR / len(equity_curve)) - 1) * 100), 2)
            if len(equity_curve) > 1 else None
        ),
    }
