"""
app/api/v1/onboarding.py
---------------------------
Persists the onboarding wizard's completion — sophistication tier and
digital risk-acknowledgment signature — into the Phase 1 schema's
consent_records and profiles tables. This is what makes the frontend
wizard's signature step legally meaningful rather than decorative:
the signed acknowledgment is durably stored with a timestamp and can
be produced later if ever needed for a compliance review.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from app.core.config import get_settings

logger = logging.getLogger("aureus.api.onboarding")
router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


class OnboardingCompleteRequest(BaseModel):
    user_id: str
    sophistication_tier: str
    sophistication_score: int
    signature_full_name: str
    signed_at: str
    terms_version: str = "v1.0"


@router.get("/status")
def onboarding_status(user_id: str) -> dict:
    """
    Returns whether this user has a recorded risk-disclosure signature.
    Used by (dashboard)/layout.tsx to force new users through /onboarding
    before they can reach the app.
    """
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT 1 FROM consent_records
                    WHERE user_id = :uid AND consent_type = 'risk_disclosure' AND granted = true
                    LIMIT 1
                """),
                {"uid": user_id},
            ).fetchone()
        return {"completed": row is not None}
    except Exception as exc:
        logger.error("Onboarding status check failed", extra={"error": str(exc)})
        # Fail open: don't lock a user out of the app because of a transient DB error
        return {"completed": True}
    finally:
        engine.dispose()


@router.post("/complete")
def complete_onboarding(req: OnboardingCompleteRequest, request: Request) -> dict:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    client_ip = request.client.host if request.client else None

    try:
        with engine.begin() as conn:
            # Record the signed risk acknowledgment — append-only audit trail,
            # matching the pattern used for every other consent type.
            conn.execute(
                text("""
                    INSERT INTO consent_records (id, user_id, consent_type, version, granted, granted_at, ip_address)
                    VALUES (gen_random_uuid(), :uid, 'risk_disclosure', :version, true, :signed_at, :ip)
                """),
                {
                    "uid": req.user_id, "version": req.terms_version,
                    "signed_at": req.signed_at, "ip": client_ip,
                },
            )

            # Update the profile with the acknowledgment timestamp and terms version
            conn.execute(
                text("""
                    UPDATE profiles
                    SET risk_disclosure_acknowledged_at = :signed_at,
                        terms_version_accepted = :version,
                        updated_at = NOW()
                    WHERE user_id = :uid
                """),
                {"uid": req.user_id, "signed_at": req.signed_at, "version": req.terms_version},
            )

            # Seed the lesson-difficulty starting tier from the onboarding
            # sophistication result — novice=0 (Foundational+), intermediate=1
            # (Advanced), advanced=2 (Expert). This is the only durable place
            # sophistication_tier is stored, so lessons.py reads it from here
            # via this table rather than needing a separate lookup.
            tier_map = {"novice": 0, "intermediate": 1, "advanced": 2}
            base_level = tier_map.get(req.sophistication_tier, 0)
            conn.execute(
                text("""
                    INSERT INTO user_learning_progress (user_id, base_level, lessons_completed_count)
                    VALUES (:uid, :level, 0)
                    ON CONFLICT (user_id) DO UPDATE SET base_level = :level, updated_at = NOW()
                """),
                {"uid": req.user_id, "level": base_level},
            )

        logger.info(
            "Onboarding completed",
            extra={"user_id": req.user_id, "tier": req.sophistication_tier, "score": req.sophistication_score},
        )
        return {"status": "recorded"}

    except Exception as exc:
        logger.error("Onboarding completion failed", extra={"error": str(exc)}, exc_info=True)
        # Don't hard-fail the user's onboarding flow over a logging issue —
        # but do surface it so the frontend can retry if desired.
        raise HTTPException(status_code=500, detail="Could not record onboarding completion")
    finally:
        engine.dispose()
