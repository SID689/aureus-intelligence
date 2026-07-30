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
import uuid
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


# ── Signup (email + password) ─────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email:        str
    password:     str
    display_name: str = ""
    country_code: str = "US"


def _create_stripe_customer(email: str, name: str) -> str:
    """Create a Stripe customer for the new user. Returns '' if Stripe isn't configured."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        return ""
    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        customer = stripe.Customer.create(email=email, name=name or email)
        return customer.id
    except Exception as exc:
        logger.warning("Stripe customer creation failed at signup — continuing without it", extra={"error": str(exc)})
        return ""


def _provision_new_user(
    conn, email: str, display_name: str, country_code: str,
    password_hash: str | None, auth_provider: str,
) -> dict:
    """
    Shared provisioning logic for both password signup and first-time
    OAuth login: create the user row, profile row, a Stripe customer,
    and a 'sovereign' (free) subscription record so every user has a
    resolvable tier from the moment they exist.
    """
    user_id = str(uuid.uuid4())
    conn.execute(
        text("""
            INSERT INTO users (id, email, password_hash, auth_provider, role, is_active)
            VALUES (:id, :email, :pw, :provider, 'owner', true)
        """),
        {"id": user_id, "email": email.lower().strip(), "pw": password_hash, "provider": auth_provider},
    )
    conn.execute(
        text("INSERT INTO profiles (user_id, display_name, country_code) VALUES (:uid, :name, :cc)"),
        {"uid": user_id, "name": display_name or email, "cc": country_code},
    )

    stripe_customer_id = _create_stripe_customer(email, display_name)

    sovereign_tier = conn.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'sovereign'"),
    ).fetchone()
    if sovereign_tier:
        conn.execute(
            text("""
                INSERT INTO user_subscriptions (id, user_id, tier_id, stripe_customer_id, status)
                VALUES (gen_random_uuid(), :uid, :tier_id, :cust_id, 'active')
            """),
            {"uid": user_id, "tier_id": str(sovereign_tier.id), "cust_id": stripe_customer_id or f"pending_{user_id}"},
        )

    return {
        "user_id": user_id, "email": email, "display_name": display_name or email,
        "tier": "sovereign", "stripe_customer_id": stripe_customer_id,
    }


@router.post("/api/v1/auth/signup")
def signup(req: SignupRequest) -> dict:
    """Create a new user with email/password and provision their free-tier subscription."""
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": req.email.lower().strip()},
            ).fetchone()
            if existing:
                raise HTTPException(status_code=409, detail="An account with this email already exists")

            pw_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
            result = _provision_new_user(
                conn, req.email, req.display_name, req.country_code,
                password_hash=pw_hash, auth_provider="password",
            )
        logger.info("New user signed up", extra={"user_id": result["user_id"], "email": req.email})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Signup failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Signup failed — please try again")
    finally:
        engine.dispose()


# ── OAuth upsert (Google, etc. — called from NextAuth signIn callback) ────────

class OAuthUpsertRequest(BaseModel):
    email:         str
    display_name:  str = ""
    provider:      str = "google"
    external_id:   str = ""


@router.post("/api/v1/auth/oauth-upsert")
def oauth_upsert(req: OAuthUpsertRequest, x_internal_secret: str = Header(default="")) -> dict:
    """
    Called by NextAuth's signIn callback every time a user completes
    Google OAuth. If the email doesn't exist yet, provisions a full new
    account (same as signup, minus a password). If it exists, just
    returns the current tier so the JWT can be populated.
    """
    _verify_internal(x_internal_secret)
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("""
                    SELECT u.id, u.email, p.display_name, st.tier_name, us.stripe_customer_id
                    FROM users u
                    LEFT JOIN profiles p ON p.user_id = u.id
                    LEFT JOIN user_subscriptions us ON us.user_id = u.id AND us.status IN ('active','trialing')
                    LEFT JOIN subscription_tiers st ON st.id = us.tier_id
                    WHERE u.email = :email
                """),
                {"email": req.email.lower().strip()},
            ).fetchone()

            if existing:
                return {
                    "user_id": str(existing.id), "email": existing.email,
                    "display_name": existing.display_name or existing.email,
                    "tier": existing.tier_name or "sovereign",
                    "stripe_customer_id": existing.stripe_customer_id or "",
                }

            result = _provision_new_user(
                conn, req.email, req.display_name, "US",
                password_hash=None, auth_provider=req.provider,
            )
            conn.execute(
                text("UPDATE users SET external_auth_id = :ext WHERE id = :uid"),
                {"ext": req.external_id, "uid": result["user_id"]},
            )
        logger.info("New OAuth user provisioned", extra={"email": req.email, "provider": req.provider})
        return result
    except Exception as exc:
        logger.error("OAuth upsert failed", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Account provisioning failed")
    finally:
        engine.dispose()
