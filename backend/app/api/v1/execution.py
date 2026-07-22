"""
app/api/v1/execution.py
------------------------
REST endpoints for the execution layer.

POST /api/v1/execution/submit
  Submit an order proposal through guardrails → HITL or auto-execute.

POST /api/v1/execution/approve/{proposal_id}
  Approve a HITL-pending order with a cryptographically signed token.

POST /api/v1/execution/reject/{proposal_id}
  Reject a HITL-pending order.

GET  /api/v1/execution/account
  Return current Alpaca account state (equity, buying power, etc).

GET  /api/v1/execution/proposal/{proposal_id}
  Return current state of a HITL proposal.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.execution.guardrails import OrderProposal
from app.execution.hitl import approve_proposal, get_proposal, reject_proposal
from app.execution.order_router import execute_approved_hitl, route_order

logger = logging.getLogger("aureus.api.execution")

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class OrderSubmitRequest(BaseModel):
    strategy_id:    str
    user_id:        str
    portfolio_id:   str
    ticker:         str = Field(pattern=r"^[A-Z]{1,5}$")
    side:           str = Field(pattern=r"^(buy|sell)$")
    order_type:     str = Field(pattern=r"^(market|limit|stop_limit)$")
    quantity:       float = Field(gt=0)
    limit_price:    float | None = None
    entry_price:    float | None = None
    confidence:     float = Field(ge=0.0, le=1.0, default=0.5)
    is_paper:       bool = True


class HITLApproveRequest(BaseModel):
    user_id:        str
    approval_token: str


class HITLRejectRequest(BaseModel):
    user_id: str
    reason:  str = "User rejected"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/submit")
def submit_order(request: OrderSubmitRequest) -> dict:
    """
    Submit an order proposal through the full guardrail → HITL pipeline.
    Returns immediately — execution may be synchronous (auto) or
    deferred (HITL pending user approval).
    """
    proposal = OrderProposal(
        strategy_id=request.strategy_id,
        user_id=request.user_id,
        portfolio_id=request.portfolio_id,
        ticker=request.ticker.upper(),
        side=request.side,
        order_type=request.order_type,
        quantity=request.quantity,
        limit_price=request.limit_price,
        entry_price=request.entry_price,
        confidence=request.confidence,
        is_paper=request.is_paper,
    )
    try:
        return route_order(proposal)
    except Exception as exc:
        logger.error("Order routing error", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Order routing failed: {exc}")


@router.post("/approve/{proposal_id}")
def approve_hitl_order(proposal_id: str, request: HITLApproveRequest) -> dict:
    """
    Approve a HITL-pending order.
    The approval_token was sent to the client when the order entered HITL state.
    """
    if not approve_proposal(proposal_id, request.user_id, request.approval_token):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired approval token. The proposal may have timed out.",
        )
    # Execute the now-approved order
    result = execute_approved_hitl(proposal_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Broker error"))
    return result


@router.post("/reject/{proposal_id}")
def reject_hitl_order(proposal_id: str, request: HITLRejectRequest) -> dict:
    """Reject a HITL-pending order."""
    if not reject_proposal(proposal_id, request.user_id, request.reason):
        raise HTTPException(status_code=404, detail="Proposal not found or already actioned.")
    return {"status": "rejected", "proposal_id": proposal_id}


@router.get("/proposal/{proposal_id}")
def get_proposal_status(proposal_id: str) -> dict:
    """Return current state of a HITL proposal."""
    proposal = get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found or expired.")
    return {
        "proposal_id":     proposal.proposal_id,
        "state":           proposal.state,
        "ticker":          proposal.ticker,
        "side":            proposal.side,
        "quantity":        proposal.quantity,
        "stop_loss_price": proposal.stop_loss_price,
        "take_profit_price": proposal.take_profit_price,
        "confidence":      proposal.confidence,
        "created_at":      proposal.created_at,
        "expires_at":      proposal.expires_at,
    }


@router.get("/account")
def get_account_status(paper: bool = True) -> dict:
    """Return current Alpaca account snapshot."""
    try:
        from app.execution.alpaca_client import get_account
        account = get_account(paper=paper)
        return {
            "equity":          account.equity,
            "cash":            account.cash,
            "buying_power":    account.buying_power,
            "portfolio_value": account.portfolio_value,
            "is_paper":        account.is_paper,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Broker connection error: {exc}")
