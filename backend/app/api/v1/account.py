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
from sqlalchemy import text

from app.core.entitlements import (
    _engine, _TIER_COLUMNS, _row_to_entitlements,
    resolve_entitlements, usage_summary,
)

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
