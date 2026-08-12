"""
app/backtesting/strategy_engine.py
------------------------------------
User-facing, rule-based strategy backtesting engine.

Distinct from app/backtesting/engine.py (which replays AUREUS'S OWN
ensemble signal against history to answer "does our model's directional
call beat the market"). This module lets a user DEFINE a trading rule —
an RSI threshold or a moving-average crossover, with position sizing,
commission, slippage, stop-loss and take-profit — and simulates actual
trade-by-trade execution against historical OHLCV data, producing a full
trade log and equity curve. This is the standard "backtest my strategy"
workflow and is deliberately independent of the live-analysis ensemble.

===================================================================
EXECUTION-TIMING DESIGN (how look-ahead bias is avoided here)
===================================================================
1. INDICATORS ARE TRAILING-ONLY: RSI/SMA/EMA are computed with pandas
   rolling/ewm windows, which by construction only look backward from
   each row. No future bar is ever read to produce bar i's indicator
   value.
2. SIGNAL-TO-FILL DELAY: a crossing detected using bar i's CLOSE is not
   filled at bar i's close — that price is only fully "known" at the
   end of bar i, so a real order reacting to it can't also fill at it.
   Entries and signal-driven exits fill at bar i+1's OPEN, the first
   tradeable price after the signal is confirmed.
3. STOP-LOSS / TAKE-PROFIT ARE THE ONE EXCEPTION, BY DESIGN: a resting
   stop or limit order sits in the market continuously, so it can
   legitimately fill intrabar the moment price touches it — checked
   against each bar's HIGH/LOW, not its close. If both would be hit on
   the same bar, the stop-loss is assumed to trigger first (the
   conservative assumption).
4. SLIPPAGE is applied to every fill (entry, exit-by-signal, and
   exit-by-stop/target) as an adverse price adjustment — the trader
   never gets the exact touched price, real fills are always a little
   worse.

===================================================================
MULTI-TICKER / MULTI-ASSET HANDLING
===================================================================
Each ticker in the request runs as an independent sub-portfolio with an
equal split of initial_capital (initial_capital / len(tickers)); the
resulting equity curves are summed and trade logs concatenated. This
avoids modeling cross-ticker capital contention (two simultaneous
signals competing for the same cash pool), which would need a much
more complex portfolio-level allocator — independent equal-split
sub-portfolios is the standard, defensible simplification for this
class of retail-facing multi-asset backtest tool.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

import numpy as np
import pandas as pd

from app.backtesting.metrics import max_drawdown, sharpe_ratio, sortino_ratio
from app.ingestion.market_data import MarketDataService

logger = logging.getLogger("aureus.backtesting.strategy_engine")

_TRADING_DAYS_PER_YEAR = 252


# =====================================================================
# Strategy rule definitions
# =====================================================================

@dataclass
class RSIRule:
    kind: Literal["rsi"] = "rsi"
    period: int = 14
    buy_below: float = 30.0     # enter long when RSI crosses BELOW this (oversold)
    sell_above: float = 70.0    # exit long / enter short when RSI crosses ABOVE this (overbought)


@dataclass
class MACrossoverRule:
    kind: Literal["ma_crossover"] = "ma_crossover"
    fast_period: int = 20
    slow_period: int = 50
    ma_type: Literal["sma", "ema"] = "sma"


StrategyRule = RSIRule | MACrossoverRule


@dataclass
class StrategyConfig:
    rule: StrategyRule
    stop_loss_pct: float | None = 0.07     # e.g. 0.07 = 7% adverse move from entry
    take_profit_pct: float | None = 0.15   # e.g. 0.15 = 15% favorable move from entry
    allow_short: bool = False              # if False, a "sell" signal only exits a long, never opens a short


@dataclass
class BacktestRunConfig:
    tickers: list[str]
    start_date: date
    end_date: date
    frequency: Literal["1d", "1h", "5m"] = "1d"
    initial_capital: float = 10_000.0
    max_position_pct: float = 1.0    # fraction of that sub-portfolio's equity risked per position (1.0 = up to 100%)
    commission_pct: float = 0.001    # 0.1% of trade notional, charged on EACH leg (entry and exit)
    slippage_pct: float = 0.0005     # 0.05% adverse price adjustment, applied to every fill
    strategy: StrategyConfig = field(default_factory=lambda: StrategyConfig(rule=RSIRule()))
    risk_free_rate: float = 0.05


# =====================================================================
# Vectorized indicators (full series — used for signal generation)
# =====================================================================

def _rsi_series(close: pd.Series, period: int) -> pd.Series:
    """Wilder's RSI, full trailing series (no look-ahead: ewm only looks backward)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _ma_series(close: pd.Series, period: int, ma_type: str) -> pd.Series:
    if ma_type == "ema":
        return close.ewm(span=period, adjust=False, min_periods=period).mean()
    return close.rolling(window=period, min_periods=period).mean()


# =====================================================================
# Trade record
# =====================================================================

@dataclass
class TradeRecord:
    ticker: str
    direction: Literal["long", "short"]
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    quantity: float
    duration_days: float
    pnl_dollars: float
    pnl_pct: float
    exit_reason: Literal["signal", "stop_loss", "take_profit", "end_of_backtest"]


# =====================================================================
# Per-ticker event-driven simulation
# =====================================================================

def _simulate_single_ticker(
    ticker: str,
    bars: pd.DataFrame,
    capital: float,
    cfg: BacktestRunConfig,
) -> tuple[list[TradeRecord], pd.Series]:
    """
    Runs the configured rule bar-by-bar against one ticker's OHLCV history.
    Returns (trades, equity_curve) — equity_curve is indexed identically
    to `bars` and mark-to-marks the position every bar, not just at trades.
    """
    close, open_, high, low = bars["close"], bars["open"], bars["high"], bars["low"]
    rule = cfg.strategy.rule

    if rule.kind == "rsi":
        indicator = _rsi_series(close, rule.period)
        indicator2 = None
    else:
        indicator = _ma_series(close, rule.fast_period, rule.ma_type)
        indicator2 = _ma_series(close, rule.slow_period, rule.ma_type)

    n = len(bars)
    trades: list[TradeRecord] = []
    equity = pd.Series(index=bars.index, dtype=float)

    # realized_equity == true current equity whenever direction == 0 (flat).
    # While a position is open it's held at the value it had at entry —
    # mark-to-market unrealized P&L is added on top separately (Step 4) so
    # a position's notional is never double-counted into equity.
    realized_equity = capital
    direction: int = 0          # 0 flat, 1 long, -1 short
    entry_price = 0.0
    entry_qty = 0.0
    entry_date = None
    stop_price = None
    target_price = None
    pending_action: str | None = None   # "enter_long" | "enter_short" | "exit", executes at THIS bar's open

    def _fill_price(raw_price: float, buying: bool) -> float:
        # Slippage always works against the trader: buying fills higher, selling fills lower.
        return raw_price * (1 + cfg.slippage_pct) if buying else raw_price * (1 - cfg.slippage_pct)

    for i in range(n):
        o, h, l, c = float(open_.iloc[i]), float(high.iloc[i]), float(low.iloc[i]), float(close.iloc[i])

        # ── Step 1: execute any pending entry/exit queued from the PREVIOUS bar, at THIS bar's open ──
        if pending_action == "enter_long" and direction == 0:
            fill = _fill_price(o, buying=True)
            notional = realized_equity * cfg.max_position_pct
            entry_qty = notional / fill
            direction, entry_price, entry_date = 1, fill, bars.index[i]
            stop_price = fill * (1 - cfg.strategy.stop_loss_pct) if cfg.strategy.stop_loss_pct else None
            target_price = fill * (1 + cfg.strategy.take_profit_pct) if cfg.strategy.take_profit_pct else None
        elif pending_action == "enter_short" and direction == 0:
            fill = _fill_price(o, buying=False)
            notional = realized_equity * cfg.max_position_pct
            entry_qty = notional / fill
            direction, entry_price, entry_date = -1, fill, bars.index[i]
            stop_price = fill * (1 + cfg.strategy.stop_loss_pct) if cfg.strategy.stop_loss_pct else None
            target_price = fill * (1 - cfg.strategy.take_profit_pct) if cfg.strategy.take_profit_pct else None
        elif pending_action == "exit" and direction != 0:
            fill = _fill_price(o, buying=(direction == -1))
            realized_equity += _close_position(direction, entry_qty, entry_price, fill, cfg.commission_pct)
            trades.append(_make_trade(ticker, direction, entry_date, entry_price, bars.index[i], fill, entry_qty, cfg.commission_pct, "signal"))
            direction, entry_price, entry_qty, stop_price, target_price = 0, 0.0, 0.0, None, None
        pending_action = None

        # ── Step 2: intrabar stop-loss / take-profit check (resting orders — legitimately same-bar) ──
        if direction == 1:
            if stop_price is not None and l <= stop_price:
                fill = _fill_price(stop_price, buying=False)
                realized_equity += _close_position(1, entry_qty, entry_price, fill, cfg.commission_pct)
                trades.append(_make_trade(ticker, 1, entry_date, entry_price, bars.index[i], fill, entry_qty, cfg.commission_pct, "stop_loss"))
                direction, entry_qty, stop_price, target_price = 0, 0.0, None, None
            elif target_price is not None and h >= target_price:
                fill = _fill_price(target_price, buying=False)
                realized_equity += _close_position(1, entry_qty, entry_price, fill, cfg.commission_pct)
                trades.append(_make_trade(ticker, 1, entry_date, entry_price, bars.index[i], fill, entry_qty, cfg.commission_pct, "take_profit"))
                direction, entry_qty, stop_price, target_price = 0, 0.0, None, None
        elif direction == -1:
            if stop_price is not None and h >= stop_price:
                fill = _fill_price(stop_price, buying=True)
                realized_equity += _close_position(-1, entry_qty, entry_price, fill, cfg.commission_pct)
                trades.append(_make_trade(ticker, -1, entry_date, entry_price, bars.index[i], fill, entry_qty, cfg.commission_pct, "stop_loss"))
                direction, entry_qty, stop_price, target_price = 0, 0.0, None, None
            elif target_price is not None and l <= target_price:
                fill = _fill_price(target_price, buying=True)
                realized_equity += _close_position(-1, entry_qty, entry_price, fill, cfg.commission_pct)
                trades.append(_make_trade(ticker, -1, entry_date, entry_price, bars.index[i], fill, entry_qty, cfg.commission_pct, "take_profit"))
                direction, entry_qty, stop_price, target_price = 0, 0.0, None, None

        # ── Step 3: evaluate the rule using data through THIS bar's close, queue action for NEXT bar's open ──
        if i > 0:
            if rule.kind == "rsi":
                prev_val, val = indicator.iloc[i - 1], indicator.iloc[i]
                if pd.notna(prev_val) and pd.notna(val):
                    crossed_below_buy = prev_val >= rule.buy_below and val < rule.buy_below
                    crossed_above_sell = prev_val <= rule.sell_above and val > rule.sell_above
                    if direction == 0:
                        if crossed_below_buy:
                            pending_action = "enter_long"
                        elif crossed_above_sell and cfg.strategy.allow_short:
                            pending_action = "enter_short"
                    elif direction == 1 and crossed_above_sell:
                        pending_action = "exit"
                    elif direction == -1 and crossed_below_buy:
                        pending_action = "exit"
            else:  # ma_crossover
                pf, sf = indicator.iloc[i - 1], indicator2.iloc[i - 1]
                cf, cs = indicator.iloc[i], indicator2.iloc[i]
                if pd.notna(pf) and pd.notna(sf) and pd.notna(cf) and pd.notna(cs):
                    golden_cross = pf <= sf and cf > cs
                    death_cross  = pf >= sf and cf < cs
                    if direction == 0:
                        if golden_cross:
                            pending_action = "enter_long"
                        elif death_cross and cfg.strategy.allow_short:
                            pending_action = "enter_short"
                    elif direction == 1 and death_cross:
                        pending_action = "exit"
                    elif direction == -1 and golden_cross:
                        pending_action = "exit"

        # ── Step 4: mark-to-market equity for this bar ──
        # realized_equity is frozen at its value from before this position opened;
        # add unrealized P&L on top so the position's notional is never double-counted.
        if direction == 1:
            equity.iloc[i] = realized_equity + entry_qty * (c - entry_price)
        elif direction == -1:
            equity.iloc[i] = realized_equity + entry_qty * (entry_price - c)
        else:
            equity.iloc[i] = realized_equity

    # Force-close any still-open position at the last bar's close (can't leave it dangling)
    if direction != 0:
        fill = _fill_price(float(close.iloc[-1]), buying=(direction == -1))
        realized_equity += _close_position(direction, entry_qty, entry_price, fill, cfg.commission_pct)
        trades.append(_make_trade(ticker, direction, entry_date, entry_price, bars.index[-1], fill, entry_qty, cfg.commission_pct, "end_of_backtest"))
        equity.iloc[-1] = realized_equity

    return trades, equity


def _close_position(direction: int, qty: float, entry_price: float, exit_price: float, commission_pct: float) -> float:
    """
    Returns the cash delta from closing a position — the realized P&L net
    of both legs' commission. Cash bookkeeping is kept in P&L terms
    (rather than modeling margin/short-proceeds literally) since that's
    all the equity curve and trade log actually need.
    """
    entry_notional = qty * entry_price
    exit_notional  = qty * exit_price
    gross_pnl = (exit_price - entry_price) * qty if direction == 1 else (entry_price - exit_price) * qty
    commission = entry_notional * commission_pct + exit_notional * commission_pct
    return gross_pnl - commission


def _make_trade(
    ticker: str, direction: int, entry_date, entry_price: float, exit_date, exit_price: float,
    qty: float, commission_pct: float, reason: str,
) -> TradeRecord:
    pnl = _close_position(direction, qty, entry_price, exit_price, commission_pct)
    entry_notional = qty * entry_price
    duration_days = (pd.Timestamp(exit_date) - pd.Timestamp(entry_date)).total_seconds() / 86400.0
    return TradeRecord(
        ticker=ticker,
        direction="long" if direction == 1 else "short",
        entry_date=str(pd.Timestamp(entry_date).date()),
        entry_price=round(entry_price, 4),
        exit_date=str(pd.Timestamp(exit_date).date()),
        exit_price=round(exit_price, 4),
        quantity=round(qty, 6),
        duration_days=round(duration_days, 2),
        pnl_dollars=round(pnl, 2),
        pnl_pct=round((pnl / entry_notional) * 100, 3) if entry_notional else 0.0,
        exit_reason=reason,
    )


# =====================================================================
# Trade-log distribution metrics (dollar/trade-level — complements
# metrics.py's return-series-level sharpe/sortino/drawdown)
# =====================================================================

def _trade_distribution_stats(trades: list[TradeRecord]) -> dict:
    if not trades:
        return {
            "total_trades": 0, "winning_trades": 0, "losing_trades": 0, "win_rate_pct": None,
            "profit_factor": None, "expectancy_dollars": None,
            "avg_win_dollars": None, "avg_loss_dollars": None,
            "longest_win_streak": 0, "longest_loss_streak": 0,
            "avg_trade_duration_days": None,
        }

    pnls = [t.pnl_dollars for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    # Streaks
    longest_win_streak = longest_loss_streak = cur_win = cur_loss = 0
    for p in pnls:
        if p > 0:
            cur_win += 1; cur_loss = 0
        elif p < 0:
            cur_loss += 1; cur_win = 0
        else:
            cur_win = cur_loss = 0
        longest_win_streak = max(longest_win_streak, cur_win)
        longest_loss_streak = max(longest_loss_streak, cur_loss)

    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else None,
        "expectancy_dollars": round(sum(pnls) / len(trades), 2),
        "avg_win_dollars": round(gross_profit / len(wins), 2) if wins else None,
        "avg_loss_dollars": round(-gross_loss / len(losses), 2) if losses else None,
        "longest_win_streak": longest_win_streak,
        "longest_loss_streak": longest_loss_streak,
        "avg_trade_duration_days": round(float(np.mean([t.duration_days for t in trades])), 2),
    }


# =====================================================================
# Main entry point
# =====================================================================

def run_strategy_backtest(cfg: BacktestRunConfig) -> dict:
    tickers = [t.upper().strip() for t in cfg.tickers]
    logger.info("Strategy backtest started", extra={"tickers": tickers, "rule": cfg.strategy.rule.kind})

    svc = MarketDataService()
    # Fetch a lookback buffer before start_date so the slower indicator has
    # a warmed-up window by the requested start, rather than a cold start
    # that quietly skips the first N days of the window.
    lookback_days = max(
        getattr(cfg.strategy.rule, "period", 0),
        getattr(cfg.strategy.rule, "slow_period", 0),
    ) * 3 + 30
    fetch_start = cfg.start_date - timedelta(days=lookback_days)

    per_ticker_capital = cfg.initial_capital / len(tickers)

    all_trades: list[TradeRecord] = []
    equity_curves: list[pd.Series] = []
    spy_curve: pd.Series | None = None

    for ticker in tickers:
        bars = svc.fetch_bars(ticker, fetch_start, cfg.end_date, frequency=cfg.frequency).bars
        if bars.empty or len(bars) < 30:
            raise ValueError(f"Not enough historical data for {ticker} in this window to backtest.")

        trades, equity = _simulate_single_ticker(ticker, bars, per_ticker_capital, cfg)
        # Trim the warm-up buffer off the front of the equity curve/report window
        equity = equity[equity.index.date >= cfg.start_date]
        if equity.empty:
            raise ValueError(f"No trading days for {ticker} within {cfg.start_date}..{cfg.end_date} after indicator warm-up.")
        all_trades.extend([t for t in trades if t.exit_date >= str(cfg.start_date)])
        equity_curves.append(equity)

    # Combine sub-portfolio equity curves (inner-join on shared trading dates)
    combined = pd.concat(equity_curves, axis=1).ffill().bfill()
    combined_equity = combined.sum(axis=1)

    # SPY benchmark, scaled to start at the same initial capital for a fair visual comparison
    spy_bars = svc.fetch_bars("SPY", fetch_start, cfg.end_date, frequency=cfg.frequency).bars
    spy_close = spy_bars["close"]
    spy_close = spy_close[spy_close.index.date >= cfg.start_date]
    spy_aligned = spy_close.reindex(combined_equity.index, method="ffill")
    spy_curve = spy_aligned / spy_aligned.iloc[0] * cfg.initial_capital

    daily_returns = combined_equity.pct_change().fillna(0.0)

    trade_stats = _trade_distribution_stats(all_trades)
    dd = max_drawdown(combined_equity)

    # Baseline against the TRUE starting capital, not combined_equity.iloc[0] —
    # a rule can enter a position during the indicator warm-up buffer (before
    # start_date) that's still open or just-closed right at start_date, which
    # would otherwise make the first displayed equity point already differ
    # from initial_capital and silently skew the % return figures.
    total_return_pct = round(float((combined_equity.iloc[-1] / cfg.initial_capital - 1) * 100), 2)
    n_days = (combined_equity.index[-1] - combined_equity.index[0]).days or 1
    cagr_pct = round(float(((combined_equity.iloc[-1] / cfg.initial_capital) ** (365.0 / n_days) - 1) * 100), 2)

    equity_curve_series = [
        {
            "date": str(d.date()),
            "strategy_equity": round(float(v), 2),
            "benchmark_equity": round(float(spy_curve.loc[d]), 2) if d in spy_curve.index else None,
        }
        for d, v in combined_equity.items()
    ]

    trade_log = [
        {
            "ticker": t.ticker, "direction": t.direction,
            "entry_date": t.entry_date, "entry_price": t.entry_price,
            "exit_date": t.exit_date, "exit_price": t.exit_price,
            "quantity": t.quantity, "duration_days": t.duration_days,
            "pnl_dollars": t.pnl_dollars, "pnl_pct": t.pnl_pct,
            "exit_reason": t.exit_reason,
        }
        for t in sorted(all_trades, key=lambda t: t.entry_date)
    ]

    report = {
        "config": {
            "tickers": tickers,
            "start_date": str(cfg.start_date),
            "end_date": str(cfg.end_date),
            "frequency": cfg.frequency,
            "initial_capital": cfg.initial_capital,
            "max_position_pct": cfg.max_position_pct,
            "commission_pct": cfg.commission_pct,
            "slippage_pct": cfg.slippage_pct,
            "strategy_rule": cfg.strategy.rule.kind,
            "rule_params": _rule_params(cfg.strategy.rule),
            "stop_loss_pct": cfg.strategy.stop_loss_pct,
            "take_profit_pct": cfg.strategy.take_profit_pct,
            "allow_short": cfg.strategy.allow_short,
        },
        "summary": {
            **trade_stats,
            "total_return_pct": total_return_pct,
            "cagr_pct": cagr_pct,
            "max_drawdown_pct": dd["max_drawdown_pct"],
            "max_drawdown_peak_date": dd["peak_date"],
            "max_drawdown_trough_date": dd["trough_date"],
            "sharpe_ratio": sharpe_ratio(daily_returns, cfg.risk_free_rate),
            "sortino_ratio": sortino_ratio(daily_returns, cfg.risk_free_rate),
            "final_equity": round(float(combined_equity.iloc[-1]), 2),
        },
        "equity_curve": equity_curve_series,
        "trades": trade_log,
    }

    logger.info("Strategy backtest complete", extra={
        "tickers": tickers, "trades": len(all_trades),
        "total_return_pct": total_return_pct, "sharpe": report["summary"]["sharpe_ratio"],
    })
    return report


def _rule_params(rule: StrategyRule) -> dict:
    if isinstance(rule, RSIRule):
        return {"period": rule.period, "buy_below": rule.buy_below, "sell_above": rule.sell_above}
    return {"fast_period": rule.fast_period, "slow_period": rule.slow_period, "ma_type": rule.ma_type}
