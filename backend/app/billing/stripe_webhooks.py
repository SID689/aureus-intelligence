"""
app/billing/stripe_webhooks.py
-------------------------------
Backend logic triggered by Stripe events (relayed from the Next.js webhook route).
Handles tier updates in the database.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from app.billing.credits import grant_allowance, revoke_all_keys, revoke_allowance
from app.core.entitlements import invalidate_entitlements
from app.core.config import get_settings

logger = logging.getLogger("aureus.billing")


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def update_user_tier(
    stripe_customer_id: str,
    new_tier: str,
    subscription_status: str,
    stripe_subscription_id: str,
) -> dict:
    """Update a user's subscription tier in the database."""
    engine = _get_engine()

    try:
        with engine.begin() as conn:
            # Find the user by Stripe customer ID
            user_row = conn.execute(
                text("""
                    SELECT us.user_id, us.id as sub_id, st.tier_name as current_tier
                    FROM user_subscriptions us
                    JOIN subscription_tiers st ON us.tier_id = st.id
                    WHERE us.stripe_customer_id = :customer_id
                    LIMIT 1
                """),
                {"customer_id": stripe_customer_id},
            ).fetchone()

            if not user_row:
                logger.warning(
                    "No user found for Stripe customer",
                    extra={"stripe_customer_id": stripe_customer_id},
                )
                return {"status": "not_found"}

            user_id      = str(user_row.user_id)
            current_tier = str(user_row.current_tier)

            # Get the new tier's ID
            tier_row = conn.execute(
                text("SELECT id FROM subscription_tiers WHERE tier_name = :tier"),
                {"tier": new_tier},
            ).fetchone()

            if not tier_row:
                logger.error("Unknown tier name", extra={"tier": new_tier})
                return {"status": "unknown_tier"}

            new_tier_id = str(tier_row.id)

            # Update the subscription record
            conn.execute(
                text("""
                    UPDATE user_subscriptions
                    SET tier_id = :tier_id,
                        status  = :status,
                        stripe_subscription_id = :sub_id,
                        updated_at = NOW()
                    WHERE stripe_customer_id = :customer_id
                """),
                {
                    "tier_id":     new_tier_id,
                    "status":      subscription_status,
                    "sub_id":      stripe_subscription_id,
                    "customer_id": stripe_customer_id,
                },
            )

        logger.info(
            "Tier updated",
            extra={
                "stripe_customer_id": stripe_customer_id,
                "user_id":            user_id,
                "old_tier":           current_tier,
                "new_tier":           new_tier,
                "subscription_status": subscription_status,
            },
        )

        # Must run BEFORE the return, and after the transaction commits.
        # Otherwise a customer who just paid keeps hitting their old limits
        # until the cache TTL expires, which reads as "I upgraded and
        # nothing happened".
        invalidate_entitlements(user_id)
        _provision_for_tier(user_id, new_tier, subscription_status)

        return {
            "status":   "updated",
            "user_id":  user_id,
            "old_tier": current_tier,
            "new_tier": new_tier,
        }
    except Exception as exc:
        logger.error("Tier update failed", extra={"error": str(exc)}, exc_info=True)
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()


def handle_payment_failed(stripe_customer_id: str) -> dict:
    """
    Mark subscription as past_due. Agents keep running (grace period).
    A second failure (handled by Stripe retry config) triggers full downgrade.
    """
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE user_subscriptions
                    SET status = 'past_due', updated_at = NOW()
                    WHERE stripe_customer_id = :customer_id
                """),
                {"customer_id": stripe_customer_id},
            )
        logger.warning("Payment failed — marked past_due", extra={"customer_id": stripe_customer_id})
        return {"status": "marked_past_due"}
    except Exception as exc:
        logger.error("Payment-failed handler error", extra={"error": str(exc)})
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()


def _provision_for_tier(user_id: str, new_tier: str, status: str) -> None:
    """
    Bring a user's credits and API keys in line with the tier they now
    hold. This is the moment "they bought it" becomes "they can use it".

    Ordering matters: entitlements are invalidated first (above) so any
    request racing this sees the new plan, then the spendable balance is
    set. Granting credits before the tier is visible would let someone
    spend an Institutional allowance under Elite limits.

    Never raises. A provisioning failure must not make the webhook fail,
    because Stripe would then retry the whole event and re-run the tier
    update; the reconciliation job is what repairs a missed grant.
    """
    from sqlalchemy import text as _text

    try:
        engine = _get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                _text("SELECT monthly_credits, api_keys_allowed FROM subscription_tiers WHERE tier_name = :t"),
                {"t": new_tier},
            ).fetchone()
        credits = int(row[0]) if row else 0
        keys_allowed = int(row[1]) if row else 0
    except Exception as exc:
        logger.error("Could not read tier for provisioning",
                     extra={"user_id": user_id, "tier": new_tier, "error": str(exc)})
        return

    active = status in ("active", "trialing")

    try:
        if active and credits > 0:
            grant_allowance(user_id, credits, reason=f"subscription_{new_tier}")
        else:
            # Cancelled, past_due or a zero-credit plan: withdraw the
            # allowance and kill live keys. A lapsed subscription must not
            # keep programmatic access — that is the one path that bills
            # the platform owner for a customer who has stopped paying.
            revoke_allowance(user_id, reason=f"subscription_{status}")
            if keys_allowed == 0:
                n = revoke_all_keys(user_id, reason=f"subscription_{status}")
                if n:
                    logger.info("API keys revoked on downgrade",
                                extra={"user_id": user_id, "count": n})
        logger.info("Provisioned for tier", extra={
            "user_id": user_id, "tier": new_tier, "credits": credits, "active": active,
        })
    except Exception as exc:
        logger.error("Provisioning failed",
                     extra={"user_id": user_id, "error": str(exc)}, exc_info=True)
