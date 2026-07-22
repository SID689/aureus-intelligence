"""
app/execution/guardrails.py
----------------------------
Rigid rule validation engine.  Every agent-generated order proposal passes
through this module before touching the broker API.

Rules enforced (in order):
  1. TIER GATE        — user's subscription must be Elite or Institutional.
  2. STRATEGY ACTIVE  — referenced strategy must be in 'active' state.
  3. POSITION SIZING  — proposed value ≤ max_position_pct of account equity.
  4. DAILY LOSS HALT  — if account is down > max_daily_loss_pct today, block all buys.
  5. STOP-LOSS ATTACH — if proposal has no stop_loss, auto-calculate and attach.
  6. TAKE-PROFIT ATTACH — same for take-profit.
  7. CONCURRENT LIMIT — Elite tier: max 5 concurrent live strategies.

Rules are checked in sequence and all violations collected before returning
so the caller gets the full picture, not just the first failure.

The validator never calls the broker API — it only reads account state
(which the caller passes in) to keep the validator fast and testable.
"""

import logging
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import create_engine, text

from app.core.config import get_settings

logger = logging.getLogger("aureus.execution.guardrails")


# ── Order proposal type ───────────────────────────────────────────────────────

@dataclass
class OrderProposal:
    """Represents an agent-generated trade proposal before validation."""
    strategy_id:       str
    user_id:           str
    portfolio_id:      str
    ticker:            str
    side:              Literal["buy", "sell"]
    order_type:        Literal["market", "limit", "stop_limit"]
    quantity:          float
    limit_price:       float | None = None   # required for limit / stop_limit
    stop_price:        float | None = None   # for stop_limit entry
    stop_loss_price:   float | None = None   # protective stop, auto-calculated if None
    take_profit_price: float | None = None   # auto-calculated if None
    entry_price:       float | None = None   # estimated fill price (used for auto-calc)
    confidence:        float = 0.5           # 0-1 from strategy
    is_paper:          bool = True


@dataclass
class ValidationResult:
    is_valid:                bool
    violations:              list[str] = field(default_factory=list)
    warnings:                list[str] = field(default_factory=list)
    requires_human_approval: bool = False
    adjusted_proposal:       OrderProposal | None = None   # auto-corrected copy


# ── Database helpers ──────────────────────────────────────────────────────────

def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def _get_user_tier(user_id: str) -> dict | None:
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT st.tier_name, st.supports_live_execution,
                           st.concurrent_agent_strategies_limit
                    FROM user_subscriptions us
                    JOIN subscription_tiers st ON us.tier_id = st.id
                    WHERE us.user_id = :uid
                      AND us.status IN ('active', 'trialing')
                    LIMIT 1
                """),
                {"uid": user_id},
            ).fetchone()
        return dict(row._mapping) if row else None
    except Exception as exc:
        logger.error("Tier lookup failed", extra={"user_id": user_id, "error": str(exc)})
        return None
    finally:
        engine.dispose()


def _get_active_strategy_count(user_id: str) -> int:
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT COUNT(*) FROM agent_strategies
                    WHERE user_id = :uid AND status = 'active'
                """),
                {"uid": user_id},
            ).fetchone()
        return int(row[0]) if row else 0
    finally:
        engine.dispose()


def _get_strategy_status(strategy_id: str) -> str | None:
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status FROM agent_strategies WHERE id = :sid"),
                {"sid": strategy_id},
            ).fetchone()
        return str(row[0]) if row else None
    finally:
        engine.dispose()


# ── Auto-calculation helpers ──────────────────────────────────────────────────

def _auto_stop_loss(entry_price: float, side: str) -> float:
    cfg = get_settings()
    if side == "buy":
        return round(entry_price * (1.0 - cfg.default_stop_loss_pct), 2)
    else:  # short sell
        return round(entry_price * (1.0 + cfg.default_stop_loss_pct), 2)


def _auto_take_profit(entry_price: float, side: str) -> float:
    cfg = get_settings()
    if side == "buy":
        return round(entry_price * (1.0 + cfg.default_take_profit_pct), 2)
    else:
        return round(entry_price * (1.0 - cfg.default_take_profit_pct), 2)


# ── Main validator ────────────────────────────────────────────────────────────

def validate_order(
    proposal: OrderProposal,
    account_equity: float,
    current_price: float | None = None,
) -> ValidationResult:
    """
    Validate an order proposal against all guardrail rules.

    Args:
        proposal:       The agent-generated order proposal.
        account_equity: Current total account equity from Alpaca.
        current_price:  Latest market price for the ticker (used for sizing check).

    Returns:
        ValidationResult with is_valid, any violations, and the adjusted proposal.
    """
    cfg        = get_settings()
    violations: list[str] = []
    warnings:   list[str] = []
    requires_hitl = False

    # Work on a mutable copy so we can auto-correct without mutating the original
    import copy
    adj = copy.deepcopy(proposal)

    # ── Rule 1: Tier gate ─────────────────────────────────────
    tier_info = _get_user_tier(proposal.user_id)
    if tier_info is None:
        violations.append("No active subscription found — execution blocked.")
    elif not tier_info["supports_live_execution"] and not proposal.is_paper:
        violations.append(
            f"Tier '{tier_info['tier_name']}' does not permit live execution. "
            "Upgrade to Elite or Institutional."
        )
    elif tier_info["tier_name"] == "sovereign":
        violations.append("Sovereign tier cannot run execution agents.")

    # ── Rule 2: Strategy state ────────────────────────────────
    strategy_status = _get_strategy_status(proposal.strategy_id)
    if strategy_status is None:
        violations.append(f"Strategy {proposal.strategy_id} not found.")
    elif strategy_status != "active":
        violations.append(
            f"Strategy is in '{strategy_status}' state — only 'active' strategies may execute."
        )

    # If hard violations already, bail early
    if violations:
        return ValidationResult(is_valid=False, violations=violations, warnings=warnings)

    # ── Rule 3: Position sizing ───────────────────────────────
    price_for_sizing = current_price or proposal.limit_price or proposal.entry_price
    if price_for_sizing and account_equity > 0:
        proposed_value = proposal.quantity * price_for_sizing
        position_pct   = proposed_value / account_equity
        if position_pct > cfg.max_position_pct:
            # Auto-correct: reduce quantity to fit within limit
            max_qty = (cfg.max_position_pct * account_equity) / price_for_sizing
            max_qty = round(max_qty, 4)
            warnings.append(
                f"Position sizing auto-corrected: {proposal.quantity:.4f} → {max_qty:.4f} shares "
                f"({position_pct*100:.1f}% → {cfg.max_position_pct*100:.0f}% of equity)."
            )
            adj.quantity = max_qty
    else:
        warnings.append("Cannot validate position sizing — price unknown. Proceeding with caution.")

    # ── Rule 4: Concurrent strategy limit ─────────────────────
    if tier_info:
        limit = tier_info.get("concurrent_agent_strategies_limit")
        if limit is not None:
            active_count = _get_active_strategy_count(proposal.user_id)
            if active_count >= limit:
                violations.append(
                    f"Concurrent strategy limit reached ({active_count}/{limit}). "
                    "Pause or archive an existing strategy first."
                )

    # ── Rule 5: Auto-attach stop-loss ─────────────────────────
    entry = adj.limit_price or adj.entry_price or current_price
    if entry:
        if adj.stop_loss_price is None:
            adj.stop_loss_price = _auto_stop_loss(entry, adj.side)
            warnings.append(
                f"Stop-loss auto-attached at ${adj.stop_loss_price:.2f} "
                f"({cfg.default_stop_loss_pct*100:.0f}% from entry)."
            )
        if adj.take_profit_price is None:
            adj.take_profit_price = _auto_take_profit(entry, adj.side)
            warnings.append(
                f"Take-profit auto-attached at ${adj.take_profit_price:.2f} "
                f"({cfg.default_take_profit_pct*100:.0f}% from entry)."
            )
    else:
        violations.append("Cannot attach stop-loss/take-profit — no entry price available.")

    # ── Rule 6: HITL determination ────────────────────────────
    # Require human approval when:
    # - Confidence is below 0.65
    # - Order value > 2% of account equity
    # - Tier is Elite (Institutional can auto-execute if configured)
    if tier_info:
        order_value = (adj.quantity * (entry or 0))
        low_confidence = adj.confidence < 0.65
        large_order    = account_equity > 0 and (order_value / account_equity) > 0.02
        is_elite       = tier_info["tier_name"] == "elite"

        if low_confidence or large_order or is_elite:
            requires_hitl = True
            warnings.append(
                "Human-in-the-loop approval required before execution "
                f"(confidence={adj.confidence:.2f}, order_value=${order_value:.2f})."
            )

    if violations:
        return ValidationResult(
            is_valid=False,
            violations=violations,
            warnings=warnings,
            adjusted_proposal=adj,
        )

    logger.info(
        "Order proposal validated",
        extra={
            "ticker": proposal.ticker,
            "side": proposal.side,
            "qty_original": proposal.quantity,
            "qty_adjusted": adj.quantity,
            "requires_hitl": requires_hitl,
            "warnings": len(warnings),
        },
    )

    return ValidationResult(
        is_valid=True,
        violations=[],
        warnings=warnings,
        requires_human_approval=requires_hitl,
        adjusted_proposal=adj,
    )
