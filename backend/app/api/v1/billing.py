"""
app/api/v1/billing.py
----------------------
Internal billing endpoints called by:
  - The Next.js Stripe webhook relay (POST /api/v1/billing/tier-update)
  - The frontend auth flow (POST /api/v1/auth/login)

These endpoints are NOT user-facing — they're service-to-service.
In production, add mutual TLS or an internal service token check.
"""

import logging
import os
from typing import Literal

import bcrypt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from app.billing.stripe_webhooks import handle_payment_failed, update_user_tier
from app.core.config import get_settings

logger = logging.getLogger("aureus.api.billing")
router = APIRouter(tags=["billing-internal"])

INTERNAL_SECRET = os.getenv("INTERNAL_API_SECRET", "")


def _verify_internal(x_internal_secret: str = Header(default="")) -> None:
    """Simple shared-secret check for internal service calls."""
    if INTERNAL_SECRET and x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized internal call")


# ── Tier update (from Stripe webhook relay) ───────────────────────────────────

class TierUpdateRequest(BaseModel):
    stripe_customer_id:     str
    new_tier:               Literal["sovereign", "elite", "institutional"]
    subscription_status:    str
    stripe_subscription_id: str = ""


@router.post("/api/v1/billing/tier-update")
def tier_update(req: TierUpdateRequest, x_internal_secret: str = Header(default="")) -> dict:
    _verify_internal(x_internal_secret)
    result = update_user_tier(
        stripe_customer_id=req.stripe_customer_id,
        new_tier=req.new_tier,
        subscription_status=req.subscription_status,
        stripe_subscription_id=req.stripe_subscription_id,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result


class PaymentFailedRequest(BaseModel):
    stripe_customer_id: str


@router.post("/api/v1/billing/payment-failed")
def payment_failed(req: PaymentFailedRequest, x_internal_secret: str = Header(default="")) -> dict:
    _verify_internal(x_internal_secret)
    return handle_payment_failed(req.stripe_customer_id)


# ── Auth login (from NextAuth CredentialsProvider) ───────────────────────────

class LoginRequest(BaseModel):
    email:    str
    password: str


@router.post("/api/v1/auth/login")
def login(req: LoginRequest) -> dict:
    """
    Validate email + password, return user info + tier for NextAuth JWT.
    """
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT
                        u.id, u.email, u.password_hash,
                        p.display_name,
                        st.tier_name,
                        us.stripe_customer_id
                    FROM users u
                    LEFT JOIN profiles p ON p.user_id = u.id
                    LEFT JOIN user_subscriptions us ON us.user_id = u.id
                        AND us.status IN ('active', 'trialing')
                    LEFT JOIN subscription_tiers st ON st.id = us.tier_id
                    WHERE u.email = :email
                      AND u.is_active = true
                      AND u.deleted_at IS NULL
                    LIMIT 1
                """),
                {"email": req.email.lower().strip()},
            ).fetchone()
    finally:
        engine.dispose()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password (bcrypt)
    pw_hash = row.password_hash or ""
    if not pw_hash:
        raise HTTPException(status_code=401, detail="Account uses SSO — use your SSO provider")

    try:
        is_valid = bcrypt.checkpw(req.password.encode(), pw_hash.encode())
    except Exception:
        is_valid = False

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "user_id":            str(row.id),
        "email":              row.email,
        "display_name":       row.display_name or row.email,
        "tier":               row.tier_name or "sovereign",
        "stripe_customer_id": row.stripe_customer_id or "",
    }
