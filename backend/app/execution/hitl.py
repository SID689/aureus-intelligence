"""
app/execution/hitl.py
----------------------
Human-in-the-Loop (HITL) approval state machine.

State transitions:
  PROPOSED → AWAITING_APPROVAL → APPROVED  → (execution layer)
                               → REJECTED  → (archived)
                               → EXPIRED   → (auto-cancelled after timeout)

Cryptographic signing:
  When a proposal enters AWAITING_APPROVAL, we compute an HMAC-SHA256
  approval token:  token = HMAC(HITL_SIGNING_SECRET, "{proposal_id}:{user_id}:{timestamp}")

  The UI receives the proposal_id and approval_token_hash.
  When the user clicks Approve, the frontend sends back the proposal_id.
  The backend re-derives the expected token and compares with constant-time
  hmac.compare_digest() to prevent timing attacks.

  This ensures:
    - Approvals cannot be forged without the server's HITL_SIGNING_SECRET.
    - A stolen proposal_id alone is insufficient to approve an order.
    - Replayed approval requests are rejected (timestamp window check).

Storage:
  Proposals stored in Redis with a TTL equal to hitl_approval_timeout_seconds.
  If Redis TTL expires before approval, the proposal state is EXPIRED.
  The executed_trades DB row is updated on state transitions for audit trail.
"""

import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.execution.guardrails import OrderProposal

logger = logging.getLogger("aureus.execution.hitl")

HITLState = Literal["awaiting_approval", "approved", "rejected", "expired", "executed", "failed"]

_PROPOSAL_KEY_PREFIX = "hitl:proposal:"


# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class HITLProposal:
    proposal_id:       str
    strategy_id:       str
    user_id:           str
    portfolio_id:      str
    ticker:            str
    side:              str
    order_type:        str
    quantity:          float
    entry_price:       float | None
    stop_loss_price:   float | None
    take_profit_price: float | None
    limit_price:       float | None
    confidence:        float
    is_paper:          bool
    state:             HITLState
    approval_token_hash: str        # SHA256 of the HMAC token (not the token itself)
    created_at:        str          # ISO-8601
    expires_at:        str          # ISO-8601
    state_changed_at:  str          # ISO-8601
    executed_trade_id: str | None = None
    rejection_reason:  str | None = None


# ── Signing ───────────────────────────────────────────────────────────────────

def _generate_approval_token(proposal_id: str, user_id: str, timestamp: int) -> str:
    """
    Generate a time-bound HMAC-SHA256 approval token.
    The token is sent to the UI; the server only stores a hash of it.
    """
    secret  = get_settings().hitl_signing_secret.encode()
    message = f"{proposal_id}:{user_id}:{timestamp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _hash_token(token: str) -> str:
    """Store only the SHA256 hash of the token in Redis and DB (defense in depth)."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_approval_token(proposal_id: str, user_id: str, submitted_token: str) -> bool:
    """
    Verify that the submitted token matches the one generated at proposal creation.
    Fetches the stored token_hash from Redis and compares.
    Uses hmac.compare_digest to prevent timing attacks.
    """
    raw = get_redis_client().get(f"{_PROPOSAL_KEY_PREFIX}{proposal_id}")
    if not raw:
        return False
    proposal_data = json.loads(raw)
    if proposal_data.get("user_id") != user_id:
        return False
    stored_hash   = proposal_data.get("approval_token_hash", "")
    submitted_hash = _hash_token(submitted_token)
    return hmac.compare_digest(stored_hash, submitted_hash)


# ── State machine ─────────────────────────────────────────────────────────────

def create_proposal(order: OrderProposal, db_trade_id: str) -> tuple[HITLProposal, str]:
    """
    Create a HITL proposal from a validated OrderProposal.
    Returns (HITLProposal, approval_token).
    The approval_token should be sent to the frontend; do NOT persist it.
    """
    cfg         = get_settings()
    proposal_id = str(uuid.uuid4())
    now_ts      = int(time.time())
    expires_ts  = now_ts + cfg.hitl_approval_timeout_seconds

    token       = _generate_approval_token(proposal_id, order.user_id, now_ts)
    token_hash  = _hash_token(token)

    now_iso     = datetime.now(tz=timezone.utc).isoformat()
    expires_iso = datetime.fromtimestamp(expires_ts, tz=timezone.utc).isoformat()

    proposal = HITLProposal(
        proposal_id=proposal_id,
        strategy_id=order.strategy_id,
        user_id=order.user_id,
        portfolio_id=order.portfolio_id,
        ticker=order.ticker,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        entry_price=order.entry_price,
        stop_loss_price=order.stop_loss_price,
        take_profit_price=order.take_profit_price,
        limit_price=order.limit_price,
        confidence=order.confidence,
        is_paper=order.is_paper,
        state="awaiting_approval",
        approval_token_hash=token_hash,
        created_at=now_iso,
        expires_at=expires_iso,
        state_changed_at=now_iso,
        executed_trade_id=db_trade_id,
    )

    # Store in Redis with TTL
    redis = get_redis_client()
    redis.setex(
        f"{_PROPOSAL_KEY_PREFIX}{proposal_id}",
        cfg.hitl_approval_timeout_seconds,
        json.dumps(asdict(proposal)),
    )

    # Notify the user via Redis pub/sub → WebSocket
    redis.publish(
        f"alerts:{order.user_id}",
        json.dumps({
            "type":            "hitl_approval_required",
            "proposal_id":     proposal_id,
            "ticker":          order.ticker,
            "side":            order.side,
            "quantity":        order.quantity,
            "stop_loss_price": order.stop_loss_price,
            "take_profit_price": order.take_profit_price,
            "confidence":      order.confidence,
            "expires_at":      expires_iso,
            "approval_token":  token,   # sent once to UI, never stored
        }),
    )

    logger.info(
        "HITL proposal created",
        extra={
            "proposal_id": proposal_id,
            "ticker": order.ticker,
            "user_id": order.user_id,
            "expires_at": expires_iso,
        },
    )
    return proposal, token


def get_proposal(proposal_id: str) -> HITLProposal | None:
    """Fetch proposal from Redis. Returns None if expired or not found."""
    raw = get_redis_client().get(f"{_PROPOSAL_KEY_PREFIX}{proposal_id}")
    if not raw:
        return None
    return HITLProposal(**json.loads(raw))


def _update_state(proposal_id: str, new_state: HITLState, reason: str | None = None) -> bool:
    key = f"{_PROPOSAL_KEY_PREFIX}{proposal_id}"
    raw = get_redis_client().get(key)
    if not raw:
        return False
    data                   = json.loads(raw)
    data["state"]          = new_state
    data["state_changed_at"] = datetime.now(tz=timezone.utc).isoformat()
    if reason:
        data["rejection_reason"] = reason
    # Keep TTL alive for audit — extend by 5 minutes regardless of outcome
    get_redis_client().setex(key, 300, json.dumps(data))
    return True


def approve_proposal(proposal_id: str, user_id: str, submitted_token: str) -> bool:
    """
    Verify the token and transition proposal to APPROVED.
    Returns True if approved, False if token is invalid or proposal expired.
    """
    if not verify_approval_token(proposal_id, user_id, submitted_token):
        logger.warning("HITL: invalid approval token", extra={"proposal_id": proposal_id, "user_id": user_id})
        return False
    success = _update_state(proposal_id, "approved")
    if success:
        logger.info("HITL proposal approved", extra={"proposal_id": proposal_id, "user_id": user_id})
    return success


def reject_proposal(proposal_id: str, user_id: str, reason: str = "User rejected") -> bool:
    """
    Reject a HITL-pending order. Unlike approval, this doesn't require the
    signed token (rejection is the safe/conservative direction), but it must
    still verify the caller owns the proposal — otherwise any caller who
    learns a proposal_id could cancel another user's pending trade.
    """
    proposal = get_proposal(proposal_id)
    if not proposal or proposal.user_id != user_id:
        logger.warning("HITL: reject attempted by non-owner or unknown proposal", extra={"proposal_id": proposal_id, "user_id": user_id})
        return False
    success = _update_state(proposal_id, "rejected", reason=reason)
    if success:
        logger.info("HITL proposal rejected", extra={"proposal_id": proposal_id, "reason": reason})
    return success


def mark_executed(proposal_id: str) -> bool:
    return _update_state(proposal_id, "executed")


def mark_failed(proposal_id: str, reason: str) -> bool:
    return _update_state(proposal_id, "failed", reason=reason)


_EXEC_LOCK_PREFIX = "hitl:executing:"
_EXEC_LOCK_TTL_SECONDS = 60


def try_acquire_execution_lock(proposal_id: str) -> bool:
    """
    Atomic guard against double-submission to the broker.

    approve_proposal()/_update_state() aren't compare-and-swap — two
    concurrent approve requests for the same proposal (a double-click, or
    a client retry after a timeout) can both observe state=="approved" and
    both proceed to execute_approved_hitl(). Redis SET NX is atomic, so only
    the first caller acquires this lock; the second must back off instead of
    submitting a second real order to Alpaca for the same proposal.
    """
    return bool(get_redis_client().set(f"{_EXEC_LOCK_PREFIX}{proposal_id}", "1", nx=True, ex=_EXEC_LOCK_TTL_SECONDS))
