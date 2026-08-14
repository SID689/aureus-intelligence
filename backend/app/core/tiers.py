"""
app/core/tiers.py
-------------------
Subscription-tier enforcement for tier-gated API endpoints.

=====================================================================
WHY THIS EXISTS NOW
=====================================================================
Until the Quant Lab there was no server-side tier check anywhere in the
API — gating was purely cosmetic, done in the sidebar by hiding a link
(see frontend Sidebar.tsx). That is not enforcement: anyone can type the
URL or curl the endpoint.

The Quant Lab is Elite/Institutional-only, so it needs a real check. This
module provides it as a FastAPI dependency, resolving the caller's tier
from the database rather than trusting anything the client sends.

=====================================================================
THE TRUST BOUNDARY
=====================================================================
`user_id` arrives from the client, which means the caller identifies WHO
they claim to be, and the server decides WHAT that user may do by looking
the tier up in Postgres. A client cannot promote itself by editing a
request, because the tier is never read from the request.

This matches how the rest of this codebase already passes identity
(portfolio, lessons, education and games endpoints all take user_id).
Replacing that convention with signed session tokens is the right next
step for this app generally, but doing it here alone would leave one
endpoint on a different auth model than the other twenty — so this
follows the existing convention and the upgrade stays a single, separate
change across all of them.
"""

import logging
from functools import lru_cache
from typing import Literal

from fastapi import HTTPException, Query
from sqlalchemy import create_engine, text

from app.core.config import get_settings

logger = logging.getLogger("aureus.core.tiers")


@lru_cache(maxsize=1)
def _engine():
    """
    One pooled engine for the process.

    The routers in this codebase each call create_engine() per request and
    dispose it afterwards. That is fine at their call volume but wrong for
    a dependency that runs on EVERY gated request — building and tearing
    down a connection pool per call would add a TCP handshake to each one.
    """
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)

TierName = Literal["sovereign", "elite", "institutional"]

# Ordered least to most privileged; a check is "index >= required index".
_TIER_ORDER: list[str] = ["sovereign", "elite", "institutional"]


def tier_rank(tier: str) -> int:
    try:
        return _TIER_ORDER.index((tier or "sovereign").lower())
    except ValueError:
        return 0


def resolve_user_tier(user_id: str) -> str:
    """
    The user's current tier from the database.

    Defaults to 'sovereign' — the LEAST privileged tier — whenever the
    lookup is ambiguous: unknown user, no subscription row, or a database
    error. Failing closed matters here: a failing-open default would turn
    any transient database problem into free access to a paid feature.
    """
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text("""
                    SELECT st.tier_name
                      FROM user_subscriptions us
                      JOIN subscription_tiers st ON st.id = us.tier_id
                     WHERE us.user_id = :uid
                       AND us.status IN ('active', 'trialing')
                     ORDER BY us.created_at DESC
                     LIMIT 1
                """),
                {"uid": user_id},
            ).fetchone()
    except Exception as exc:
        logger.warning("Tier lookup failed — defaulting to sovereign",
                       extra={"user_id": user_id, "error": str(exc)})
        return "sovereign"

    return (row[0] if row and row[0] else "sovereign").lower()


def require_tier(minimum: TierName):
    """
    FastAPI dependency factory enforcing a minimum subscription tier.

        @router.get("/thing", dependencies=[Depends(require_tier("elite"))])

    Returns 402 Payment Required rather than 403 Forbidden, because the
    caller is correctly authenticated and simply on a lower plan — 402 is
    the status that tells a client to show an upgrade prompt instead of a
    "you are not allowed" error.
    """
    def _dependency(user_id: str = Query(..., min_length=1)) -> str:
        tier = resolve_user_tier(user_id)
        if tier_rank(tier) < tier_rank(minimum):
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "tier_required",
                    "message": (
                        f"This feature requires the {minimum.title()} plan or above. "
                        f"Your current plan is {tier.title()}."
                    ),
                    "current_tier": tier,
                    "required_tier": minimum,
                },
            )
        return tier
    return _dependency
