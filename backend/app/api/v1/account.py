"""
app/api/v1/account.py
-----------------------
What the caller's plan includes and how much of it they have used.

GET /api/v1/account/entitlements  the caller's own limits + live usage
GET /api/v1/account/plans         the full public plan comparison

Neither route is gated. Gating the endpoint that explains the plans would
make the upgrade path unreachable for exactly the users who need it, and
plan definitions are public information — they are on the pricing page.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.entitlements import (
    _engine, _TIER_COLUMNS, _row_to_entitlements,
    resolve_entitlements, usage_summary,
 next_tier)

logger = logging.getLogger("aureus.api.account")

router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.get("/entitlements")
def get_entitlements(user_id: Annotated[str, Query(min_length=1)]) -> dict:
    """
    The caller's plan, its limits, and current usage against them.

    This is what the settings page and the quota warnings render from, so
    the client never has to hardcode a limit — which is how a UI ends up
    claiming "10 per day" long after the plan moved to 15.
    """
    ent = resolve_entitlements(user_id)
    return {
        "user_id": user_id,
        **ent.to_dict(),
        "usage": usage_summary(user_id, ent),
    }


@router.get("/plans")
def list_plans() -> dict:
    """
    Every active plan, for the comparison table.

    Served from the database rather than a hardcoded frontend constant so
    the pricing page cannot drift away from what is actually enforced —
    the exact failure this whole change is fixing.
    """
    try:
        with _engine().connect() as conn:
            rows = conn.execute(text(f"""
                SELECT {_TIER_COLUMNS}
                  FROM subscription_tiers
                 WHERE is_active = true
                 ORDER BY price_cents
            """)).fetchall()
    except Exception as exc:
        logger.error("Plan listing failed", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail="Plan information temporarily unavailable")

    return {"plans": [_row_to_entitlements(r).to_dict() for r in rows]}


# ── Credits, API keys, treasury ───────────────────────────────────────

class ApiKeyRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str = Field(default="Default key", max_length=80)


@router.get("/credits")
def get_credits(user_id: Annotated[str, Query(min_length=1)]) -> dict:
    """Credit balance plus the recent ledger, so a charge is explainable."""
    from app.billing.credits import get_balance, recent_transactions
    return {
        "user_id": user_id,
        "balance": get_balance(user_id).to_dict(),
        "transactions": recent_transactions(user_id, limit=25),
        "unit": "1 credit = $0.001 of underlying vendor cost",
    }


@router.get("/api-keys")
def get_api_keys(user_id: Annotated[str, Query(min_length=1)]) -> dict:
    from app.billing.credits import list_api_keys
    ent = resolve_entitlements(user_id)
    return {
        "keys": list_api_keys(user_id),
        "allowed": ent.api_keys_allowed,
        "tier": ent.tier,
    }


@router.post("/api-keys")
def create_api_key(req: ApiKeyRequest) -> dict:
    """
    Mint a platform key. The plaintext is returned exactly once.

    This is an Aureus key, not a vendor key — see app/billing/credits.py
    for why upstream credentials are never handed out.
    """
    from app.billing.credits import issue_api_key
    try:
        return issue_api_key(req.user_id, name=req.name)
    except PermissionError as exc:
        ent = resolve_entitlements(req.user_id)
        raise HTTPException(status_code=402, detail={
            "error": "tier_required",
            "message": str(exc),
            "current_tier": ent.tier,
            "suggested_tier": next_tier(ent.tier),
        })
    except Exception as exc:
        logger.error("API key issue failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Could not issue API key")


@router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: str, user_id: Annotated[str, Query(min_length=1)]) -> dict:
    from app.billing.credits import revoke_api_key
    return {"revoked": revoke_api_key(user_id, key_id)}


@router.get("/treasury")
def get_treasury(admin_key: Annotated[str, Query(min_length=1)]) -> dict:
    """
    Platform economics: revenue, vendor cost, margin, break-even.

    Owner-only — this is the business's P&L, not a customer's data. Gated
    on the internal secret rather than a tier, because no subscription
    level should expose it.
    """
    import os
    import secrets as _secrets
    expected = os.getenv("INTERNAL_API_SECRET", "")
    if not expected or not _secrets.compare_digest(admin_key, expected):
        raise HTTPException(status_code=403, detail="Admin access required")
    from app.billing.treasury import treasury_summary
    return treasury_summary()
