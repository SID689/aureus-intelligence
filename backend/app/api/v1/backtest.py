"""
app/api/v1/backtest.py
--------------------------
Two independent backtesting tools live under this prefix:

POST /api/v1/backtest/strategy
  THE main user-facing feature: define a rule-based trading strategy
  (RSI threshold or moving-average crossover, with stop-loss/take-profit,
  position sizing, commission, and slippage) and simulate actual
  trade-by-trade execution against historical OHLCV data. Wraps
  app/backtesting/strategy_engine.py.

POST /api/v1/backtest/signal-accuracy/run
  A different, narrower analytical tool: replays AUREUS'S OWN ensemble
  signal against history to measure whether the model's BUY/SELL calls
  actually beat the market (see app/backtesting/engine.py's module
  docstring for the full methodology). Kept at its own sub-path so it's
  never confused with the strategy backtester above — this was the
  original /run endpoint, moved here unchanged when the strategy
  backtester was added.

Both run synchronously — a multi-year daily backtest typically completes
in a few seconds since it's pure pandas/numpy, no per-bar network calls.
"""

import logging
import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.entitlements import check_quota, record_usage, resolve_entitlements, next_tier
from app.backtesting.engine import BacktestConfig, run_backtest
from app.backtesting.strategy_engine import (
    BacktestRunConfig,
    MACrossoverRule,
    RSIRule,
    StrategyConfig,
    run_strategy_backtest,
)

logger = logging.getLogger("aureus.api.backtest")
router = APIRouter(prefix="/api/v1/backtest", tags=["backtesting"])

_TICKER_RE = re.compile(r"^[A-Z.\-]{1,10}$")


# =====================================================================
# POST /strategy — the main user-facing strategy backtester
# =====================================================================

class RSIRuleRequest(BaseModel):
    type: Literal["rsi"] = "rsi"
    period: int = Field(default=14, ge=2, le=100)
    buy_below: float = Field(default=30.0, ge=0, le=100)
    sell_above: float = Field(default=70.0, ge=0, le=100)

    @model_validator(mode="after")
    def _check_thresholds(self) -> "RSIRuleRequest":
        if self.buy_below >= self.sell_above:
            raise ValueError("buy_below must be less than sell_above")
        return self


class MACrossoverRuleRequest(BaseModel):
    type: Literal["ma_crossover"] = "ma_crossover"
    fast_period: int = Field(default=20, ge=2, le=200)
    slow_period: int = Field(default=50, ge=3, le=400)
    ma_type: Literal["sma", "ema"] = "sma"

    @model_validator(mode="after")
    def _check_periods(self) -> "MACrossoverRuleRequest":
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be less than slow_period")
        return self


class StrategyBacktestRequest(BaseModel):
    # Upper bound is the highest any plan allows (Institutional = 25);
    # the caller's actual cap is enforced against their plan below, so
    # this only rejects the absurd.
    tickers: list[str] = Field(min_length=1, max_length=25)
    user_id: str = Field(..., min_length=1)
    start_date: date
    end_date: date
    frequency: Literal["1d", "1h", "5m"] = "1d"

    initial_capital: float = Field(default=10_000.0, gt=0, le=100_000_000)
    max_position_pct: float = Field(default=1.0, gt=0, le=1.0, description="Fraction of sub-portfolio equity risked per position")
    commission_pct: float = Field(default=0.001, ge=0, le=0.05)
    slippage_pct: float = Field(default=0.0005, ge=0, le=0.05)

    rule: RSIRuleRequest | MACrossoverRuleRequest = Field(discriminator="type")
    stop_loss_pct: float | None = Field(default=0.07, gt=0, le=1.0)
    take_profit_pct: float | None = Field(default=0.15, gt=0, le=5.0)
    allow_short: bool = False

    @field_validator("tickers")
    @classmethod
    def _validate_tickers(cls, v: list[str]) -> list[str]:
        cleaned = [t.upper().strip() for t in v]
        for t in cleaned:
            if not _TICKER_RE.match(t):
                raise ValueError(f"Invalid ticker symbol: {t!r}")
        return cleaned

    @model_validator(mode="after")
    def _validate_date_range(self) -> "StrategyBacktestRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


def _to_engine_rule(rule: RSIRuleRequest | MACrossoverRuleRequest) -> RSIRule | MACrossoverRule:
    if isinstance(rule, RSIRuleRequest):
        return RSIRule(period=rule.period, buy_below=rule.buy_below, sell_above=rule.sell_above)
    return MACrossoverRule(fast_period=rule.fast_period, slow_period=rule.slow_period, ma_type=rule.ma_type)


@router.post("/strategy")
def run_strategy_backtest_endpoint(req: StrategyBacktestRequest) -> dict:
    ent = resolve_entitlements(req.user_id)

    # Three separate limits, because a backtest can be expensive along
    # three independent axes: how often you run one, how many symbols it
    # replays, and how far back it reaches. Capping only the count would
    # let a free account run a 25-ticker, 20-year replay three times a day
    # and cost more than an Elite user doing fifty single-ticker runs.
    check_quota(req.user_id, ent, "backtest_run", "Backtests", "runs")

    if ent.max_backtest_tickers is not None and len(req.tickers) > ent.max_backtest_tickers:
        raise HTTPException(status_code=402, detail={
            "error": "limit_exceeded",
            "resource": "backtest_tickers",
            "message": (
                f"The {ent.display_name} plan allows {ent.max_backtest_tickers} "
                f"ticker{'s' if ent.max_backtest_tickers != 1 else ''} per backtest; "
                f"you requested {len(req.tickers)}."
            ),
            "limit": ent.max_backtest_tickers,
            "requested": len(req.tickers),
            "current_tier": ent.tier,
            "suggested_tier": next_tier(ent.tier),
        })

    span_years = (req.end_date - req.start_date).days / 365.25
    if ent.max_backtest_years is not None and span_years > ent.max_backtest_years + 0.01:
        raise HTTPException(status_code=402, detail={
            "error": "limit_exceeded",
            "resource": "backtest_years",
            "message": (
                f"The {ent.display_name} plan allows {ent.max_backtest_years} years of "
                f"backtest history; you requested {span_years:.1f}."
            ),
            "limit": ent.max_backtest_years,
            "requested": round(span_years, 1),
            "current_tier": ent.tier,
            "suggested_tier": next_tier(ent.tier),
        })

    record_usage(req.user_id, "backtest_run", 1.0)

    cfg = BacktestRunConfig(
        tickers=req.tickers,
        start_date=req.start_date,
        end_date=req.end_date,
        frequency=req.frequency,
        initial_capital=req.initial_capital,
        max_position_pct=req.max_position_pct,
        commission_pct=req.commission_pct,
        slippage_pct=req.slippage_pct,
        strategy=StrategyConfig(
            rule=_to_engine_rule(req.rule),
            stop_loss_pct=req.stop_loss_pct,
            take_profit_pct=req.take_profit_pct,
            allow_short=req.allow_short,
        ),
    )
    try:
        return run_strategy_backtest(cfg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Strategy backtest endpoint failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")


# =====================================================================
# POST /signal-accuracy/run — the original ensemble-signal backtester
# =====================================================================

class SignalAccuracyBacktestRequest(BaseModel):
    ticker: str = Field(pattern=r"^[A-Za-z.\-]{1,10}$")
    start_date: date
    end_date: date
    forward_window_days: int = Field(default=21, ge=5, le=90)
    step_days: int = Field(default=5, ge=1, le=30)


@router.post("/signal-accuracy/run")
def run_signal_accuracy_backtest_endpoint(req: SignalAccuracyBacktestRequest) -> dict:
    config = BacktestConfig(
        ticker=req.ticker.upper(),
        start_date=req.start_date,
        end_date=req.end_date,
        forward_window_days=req.forward_window_days,
        step_days=req.step_days,
    )
    try:
        return run_backtest(config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Signal-accuracy backtest endpoint failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")
