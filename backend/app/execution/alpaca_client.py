"""
app/execution/alpaca_client.py
-------------------------------
Thin, typed wrapper around alpaca-py's TradingClient.

Design decisions:
  - Never exposes raw alpaca-py objects to callers — always returns plain
    dicts or dataclasses so the rest of the codebase has no Alpaca import dep.
  - Paper and live clients are separate instances initialised from separate
    key pairs so it is impossible to accidentally route a paper proposal to
    the live endpoint through a config typo.
  - All monetary values are returned as float (not Decimal) since they flow
    into numpy/pandas calculations downstream.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
    TrailingStopOrderRequest,
)

from app.core.config import get_settings

logger = logging.getLogger("aureus.execution.alpaca")


# ── Output types ──────────────────────────────────────────────────────────────

@dataclass
class AccountSnapshot:
    account_id: str
    equity: float           # total account value
    cash: float
    buying_power: float
    portfolio_value: float
    currency: str
    is_paper: bool


@dataclass
class OrderResult:
    broker_order_id: str
    ticker: str
    side: str
    order_type: str
    quantity: float
    status: str
    submitted_at: str
    filled_avg_price: float | None


# ── Client factory ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=2)
def _get_client(paper: bool) -> TradingClient:
    settings = get_settings()
    if paper:
        if not settings.alpaca_paper_configured:
            raise RuntimeError(
                "Alpaca paper keys not configured. "
                "Set ALPACA_PAPER_API_KEY and ALPACA_PAPER_SECRET_KEY in .env"
            )
        return TradingClient(
            settings.alpaca_paper_api_key,
            settings.alpaca_paper_secret_key,
            paper=True,
        )
    else:
        if not settings.alpaca_live_configured:
            raise RuntimeError(
                "Alpaca live keys not configured. "
                "Set ALPACA_LIVE_API_KEY and ALPACA_LIVE_SECRET_KEY in .env"
            )
        return TradingClient(
            settings.alpaca_live_api_key,
            settings.alpaca_live_secret_key,
            paper=False,
        )


# ── Public interface ──────────────────────────────────────────────────────────

def get_account(paper: bool = True) -> AccountSnapshot:
    """Fetch current account state from Alpaca."""
    client  = _get_client(paper)
    account = client.get_account()
    return AccountSnapshot(
        account_id=str(account.id),
        equity=float(account.equity),
        cash=float(account.cash),
        buying_power=float(account.buying_power),
        portfolio_value=float(account.portfolio_value),
        currency=str(account.currency),
        is_paper=paper,
    )


def submit_bracket_order(
    ticker: str,
    side: str,           # "buy" | "sell"
    qty: float,
    stop_loss_price: float,
    take_profit_price: float,
    limit_price: float | None = None,  # None = market order
    paper: bool = True,
) -> OrderResult:
    """
    Submit a bracket order (entry + automatic stop-loss + take-profit).
    Bracket orders are the required format for all Aureus strategy orders —
    bare market/limit orders without protective legs are rejected by the guardrails
    before they reach this function.
    """
    client = _get_client(paper)

    tp_req = TakeProfitRequest(limit_price=round(take_profit_price, 2))
    sl_req = StopLossRequest(stop_price=round(stop_loss_price, 2))

    order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

    if limit_price is not None:
        request = LimitOrderRequest(
            symbol=ticker,
            qty=qty,
            side=order_side,
            type=OrderType.LIMIT,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
            order_class="bracket",
            take_profit=tp_req,
            stop_loss=sl_req,
        )
    else:
        request = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
            order_class="bracket",
            take_profit=tp_req,
            stop_loss=sl_req,
        )

    try:
        order = client.submit_order(request)
        logger.info(
            "Bracket order submitted",
            extra={
                "broker_order_id": str(order.id),
                "ticker": ticker,
                "side": side,
                "qty": qty,
                "paper": paper,
            },
        )
        return OrderResult(
            broker_order_id=str(order.id),
            ticker=ticker,
            side=side,
            order_type="bracket",
            quantity=float(qty),
            status=str(order.status),
            submitted_at=str(order.submitted_at),
            filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
        )
    except Exception as exc:
        logger.error(
            "Alpaca order submission failed",
            extra={"ticker": ticker, "side": side, "error": str(exc)},
        )
        raise


def cancel_order(broker_order_id: str, paper: bool = True) -> bool:
    """Cancel an open order by broker order ID. Returns True on success."""
    try:
        _get_client(paper).cancel_order_by_id(broker_order_id)
        logger.info("Order cancelled", extra={"broker_order_id": broker_order_id})
        return True
    except Exception as exc:
        logger.error("Cancel failed", extra={"broker_order_id": broker_order_id, "error": str(exc)})
        return False


def get_position(ticker: str, paper: bool = True) -> dict | None:
    """Return current open position for a ticker, or None if flat."""
    try:
        pos = _get_client(paper).get_open_position(ticker)
        return {
            "ticker":        str(pos.symbol),
            "qty":           float(pos.qty),
            "market_value":  float(pos.market_value),
            "avg_entry":     float(pos.avg_entry_price),
            "unrealized_pl": float(pos.unrealized_pl),
        }
    except Exception:
        return None


def get_portfolio_value(paper: bool = True) -> float:
    """Convenience: return total portfolio_value from account."""
    return get_account(paper).portfolio_value
