"""
app/billing/stripe_webhooks.py
-------------------------------
Backend logic triggered by Stripe events (relayed from the Next.js webhook route).
Handles tier updates in the database.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

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
