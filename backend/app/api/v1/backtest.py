"""
app/api/v1/backtest.py
--------------------------
HTTP wrapper around app/backtesting/engine.py so a backtest can be run
via curl/Postman/frontend without exec-ing into the container. Runs
synchronously — a multi-year daily backtest typically completes in a
few seconds since it's pure pandas/numpy, no per-bar network calls.
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backtesting.engine import BacktestConfig, run_backtest

logger = logging.getLogger("aureus.api.backtest")
router = APIRouter(prefix="/api/v1/backtest", tags=["backtesting"])


class BacktestRequest(BaseModel):
    ticker: str = Field(pattern=r"^[A-Za-z.\-]{1,10}$")
    start_date: date
    end_date: date
    forward_window_days: int = Field(default=21, ge=5, le=90)
    step_days: int = Field(default=5, ge=1, le=30)


@router.post("/run")
def run_backtest_endpoint(req: BacktestRequest) -> dict:
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
        logger.error("Backtest endpoint failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}")
