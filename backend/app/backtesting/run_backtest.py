"""
app/backtesting/run_backtest.py
-----------------------------------
CLI entry point for running a backtest and printing an institutional-style
report to stdout (also returns the raw dict for programmatic use).

Usage (from inside the backend container):
    python -m app.backtesting.run_backtest AAPL 2023-01-01 2025-12-31
    python -m app.backtesting.run_backtest MSFT 2022-06-01 2025-06-01 --forward-days 10 --step-days 3
"""

import argparse
import json
import sys
from datetime import date, datetime

from app.backtesting.engine import BacktestConfig, run_backtest


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _print_report(report: dict) -> None:
    cfg = report["config"]
    print("=" * 72)
    print(f"  AUREUS INTELLIGENCE — BACKTEST REPORT: {cfg['ticker']}")
    print(f"  {cfg['start_date']} → {cfg['end_date']}  "
          f"({cfg['total_signals_generated']} signals, {cfg['forward_window_days']}d forward window)")
    print("=" * 72)

    print("\n── Risk-Adjusted Returns ──")
    print(f"  Sharpe Ratio (annualized):   {report['sharpe_ratio']}")
    print(f"  Sortino Ratio (annualized):  {report['sortino_ratio']}")
    print(f"  Total Return:                {report['total_return_pct']}%")
    print(f"  Annualized Return:           {report['annualized_return_pct']}%")

    dd = report["max_drawdown"]
    print("\n── Drawdown ──")
    print(f"  Max Drawdown:                {dd['max_drawdown_pct']:.2f}%")
    print(f"  Peak → Trough:               {dd['peak_date']} → {dd['trough_date']}")

    wl = report["win_loss"]
    print("\n── Win / Loss ──")
    print(f"  Win Rate:                    {wl['win_rate']}%")
    print(f"  Avg Win / Avg Loss:          {wl['avg_win_pct']}% / {wl['avg_loss_pct']}%")
    print(f"  Payoff Ratio:                {wl['payoff_ratio']}")

    sa = report["signal_accuracy_vs_forward_alpha"]
    print("\n── Signal Accuracy vs. Realized Forward Alpha (custom metric) ──")
    print(f"  BUY signals:   n={sa['buy_signals']['n']:<4} accuracy={sa['buy_signals']['accuracy_pct']}%   "
          f"avg forward alpha={sa['buy_signals']['avg_forward_alpha_pct']}%")
    print(f"  SELL signals:  n={sa['sell_signals']['n']:<4} accuracy={sa['sell_signals']['accuracy_pct']}%   "
          f"avg forward alpha={sa['sell_signals']['avg_forward_alpha_pct']}%")
    print(f"  HOLD signals:  n={sa['hold_signals']['n']:<4} (no directional accuracy scored)   "
          f"avg forward alpha={sa['hold_signals']['avg_forward_alpha_pct']}%")
    print(f"  Overall directional accuracy: {sa['overall_directional_accuracy_pct']}%")
    print(f"\n  {sa['interpretation']}")

    print(f"\n── Methodology ──\n  {report['methodology_note']}")
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the Aureus analytical ensemble against historical data.")
    parser.add_argument("ticker")
    parser.add_argument("start_date", help="YYYY-MM-DD")
    parser.add_argument("end_date", help="YYYY-MM-DD")
    parser.add_argument("--forward-days", type=int, default=21, help="Forward window to measure signal accuracy (default 21 trading days ≈ 1 month)")
    parser.add_argument("--step-days", type=int, default=5, help="Generate a new signal every N trading days (default 5)")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of formatted report")
    args = parser.parse_args()

    config = BacktestConfig(
        ticker=args.ticker,
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        forward_window_days=args.forward_days,
        step_days=args.step_days,
    )

    try:
        report = run_backtest(config)
    except Exception as exc:
        print(f"Backtest failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report)


if __name__ == "__main__":
    main()
