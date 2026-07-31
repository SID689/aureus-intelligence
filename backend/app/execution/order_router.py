"""
app/execution/order_router.py
------------------------------
Orchestrates the full order lifecycle:
  1. Validate via guardrails
  2. Write to executed_trades DB as 'pending'
  3. If HITL required → create proposal, return immediately
  4. If auto-execute → submit to Alpaca, update DB

This is the ONLY module that writes to executed_trades and calls Alpaca.
Agent nodes write to agent_strategies only; the router is the hard boundary.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.execution import alpaca_client as alpaca
from app.execution.guardrails import OrderProposal, validate_order
from app.execution.hitl import create_proposal, mark_executed, mark_failed, try_acquire_execution_lock

logger = logging.getLogger("aureus.execution.order_router")


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def _write_trade_record(proposal: OrderProposal, status: str = "pending") -> str:
    """Insert an executed_trades row and return its UUID."""
    trade_id = str(uuid.uuid4())
    engine   = _get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO executed_trades
                      (id, strategy_id, portfolio_id, user_id,
                       brokerage_connection_id,
                       ticker, side, order_type,
                       limit_price, stop_price, quantity, status,
                       execution_log, created_at)
                    SELECT
                      :id, :strategy_id, :portfolio_id, :user_id,
                      bc.id,
                      :ticker, :side, :order_type,
                      :limit_price, :stop_price, :quantity, :status,
                      :execution_log::jsonb, NOW()
                    FROM brokerage_connections bc
                    WHERE bc.user_id = :user_id
                      AND bc.is_live = :is_live
                      AND bc.status = 'active'
                    LIMIT 1
                """),
                {
                    "id":            trade_id,
                    "strategy_id":   proposal.strategy_id,
                    "portfolio_id":  proposal.portfolio_id,
                    "user_id":       proposal.user_id,
                    "ticker":        proposal.ticker,
                    "side":          proposal.side,
                    "order_type":    proposal.order_type,
                    "limit_price":   proposal.limit_price,
                    "stop_price":    proposal.stop_loss_price,
                    "quantity":      proposal.quantity,
                    "status":        status,
                    "is_live":       not proposal.is_paper,
                    "execution_log": f'[{{"status":"{status}","timestamp":"{datetime.now(tz=timezone.utc).isoformat()}"}}]',
                },
            )
    except Exception as exc:
        logger.error("Failed to write trade record", extra={"error": str(exc)})
        raise
    finally:
        engine.dispose()
    return trade_id


def _update_trade_status(trade_id: str, status: str, broker_order_id: str | None = None) -> None:
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE executed_trades
                    SET status = :status,
                        broker_order_id = COALESCE(:broker_id, broker_order_id),
                        submitted_at = CASE WHEN :status = 'submitted' THEN NOW() ELSE submitted_at END,
                        execution_log = execution_log || :log_entry::jsonb
                    WHERE id = :trade_id
                """),
                {
                    "trade_id":  trade_id,
                    "status":    status,
                    "broker_id": broker_order_id,
                    "log_entry": f'[{{"status":"{status}","timestamp":"{datetime.now(tz=timezone.utc).isoformat()}"}}]',
                },
            )
    except Exception as exc:
        logger.error("Failed to update trade status", extra={"trade_id": trade_id, "error": str(exc)})
    finally:
        engine.dispose()


# ── Public entry point ────────────────────────────────────────────────────────

def route_order(proposal: OrderProposal) -> dict:
    """
    Full order routing pipeline. Call this from Celery tasks or API endpoints.

    Returns a dict with:
      status:      "hitl_pending" | "submitted" | "rejected" | "error"
      proposal_id: (if HITL pending)
      trade_id:    DB row UUID
      broker_order_id: (if submitted)
      violations:  list of rule violations (if rejected)
      warnings:    list of auto-corrections applied
    """
    logger.info(
        "Order routing started",
        extra={"ticker": proposal.ticker, "side": proposal.side, "user_id": proposal.user_id},
    )

    # ── Step 1: fetch account state ───────────────────────────
    try:
        account       = alpaca.get_account(paper=proposal.is_paper)
        account_equity = account.equity
    except Exception as exc:
        logger.error("Cannot fetch account state", extra={"error": str(exc)})
        return {"status": "error", "error": f"Broker connection failed: {exc}"}

    # ── Step 2: fetch current price for sizing ────────────────
    current_price: float | None = None
    try:
        from app.ingestion.market_data import MarketDataService
        current_price = MarketDataService().fetch_latest_price(proposal.ticker)
    except Exception:
        pass  # guardrails handle None price gracefully

    # ── Step 3: validate ──────────────────────────────────────
    result = validate_order(proposal, account_equity, current_price)
    if not result.is_valid:
        logger.warning(
            "Order rejected by guardrails",
            extra={"ticker": proposal.ticker, "violations": result.violations},
        )
        return {
            "status":     "rejected",
            "violations": result.violations,
            "warnings":   result.warnings,
        }

    adj = result.adjusted_proposal or proposal

    # ── Step 4: write pending trade record to DB ──────────────
    trade_id = _write_trade_record(adj, status="pending")

    # ── Step 5: HITL or auto-execute ─────────────────────────
    if result.requires_human_approval:
        hitl_proposal, approval_token = create_proposal(adj, trade_id)
        logger.info(
            "Order awaiting HITL approval",
            extra={"trade_id": trade_id, "proposal_id": hitl_proposal.proposal_id},
        )
        return {
            "status":         "hitl_pending",
            "trade_id":       trade_id,
            "proposal_id":    hitl_proposal.proposal_id,
            "approval_token": approval_token,
            "warnings":       result.warnings,
            "order_summary": {
                "ticker":            adj.ticker,
                "side":              adj.side,
                "quantity":          adj.quantity,
                "stop_loss_price":   adj.stop_loss_price,
                "take_profit_price": adj.take_profit_price,
            },
        }

    # Auto-execute path (Institutional tier with high confidence)
    return _execute_immediately(adj, trade_id, result.warnings)


def _execute_immediately(proposal: OrderProposal, trade_id: str, warnings: list[str]) -> dict:
    """Submit validated order directly to Alpaca without waiting for HITL."""
    try:
        order_result = alpaca.submit_bracket_order(
            ticker=proposal.ticker,
            side=proposal.side,
            qty=proposal.quantity,
            stop_loss_price=proposal.stop_loss_price,
            take_profit_price=proposal.take_profit_price,
            limit_price=proposal.limit_price,
            paper=proposal.is_paper,
        )
        _update_trade_status(trade_id, "submitted", order_result.broker_order_id)
        logger.info(
            "Order auto-executed",
            extra={
                "trade_id":       trade_id,
                "broker_order_id": order_result.broker_order_id,
                "ticker":         proposal.ticker,
            },
        )
        return {
            "status":          "submitted",
            "trade_id":        trade_id,
            "broker_order_id": order_result.broker_order_id,
            "warnings":        warnings,
        }
    except Exception as exc:
        _update_trade_status(trade_id, "rejected")
        logger.error("Broker submission failed", extra={"trade_id": trade_id, "error": str(exc)})
        return {"status": "error", "trade_id": trade_id, "error": str(exc)}


def execute_approved_hitl(proposal_id: str) -> dict:
    """
    Called after HITL approval is confirmed.
    Fetches the proposal from Redis and submits to Alpaca.
    """
    from app.execution.hitl import get_proposal
    proposal_data = get_proposal(proposal_id)
    if not proposal_data:
        return {"status": "error", "error": "Proposal not found or expired"}
    if proposal_data.state != "approved":
        return {"status": "error", "error": f"Proposal is in '{proposal_data.state}' state, not approved"}

    if not try_acquire_execution_lock(proposal_id):
        logger.warning("HITL: duplicate execution attempt blocked", extra={"proposal_id": proposal_id})
        return {"status": "error", "error": "Order is already being executed for this proposal"}

    order = OrderProposal(
        strategy_id=proposal_data.strategy_id,
        user_id=proposal_data.user_id,
        portfolio_id=proposal_data.portfolio_id,
        ticker=proposal_data.ticker,
        side=proposal_data.side,
        order_type=proposal_data.order_type,
        quantity=proposal_data.quantity,
        limit_price=proposal_data.limit_price,
        stop_loss_price=proposal_data.stop_loss_price,
        take_profit_price=proposal_data.take_profit_price,
        entry_price=proposal_data.entry_price,
        confidence=proposal_data.confidence,
        is_paper=proposal_data.is_paper,
    )
    trade_id = proposal_data.executed_trade_id or str(uuid.uuid4())
    result   = _execute_immediately(order, trade_id, [])

    if result["status"] == "submitted":
        mark_executed(proposal_id)
    else:
        mark_failed(proposal_id, result.get("error", "unknown"))

    return result
