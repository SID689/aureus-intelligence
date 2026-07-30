"""
app/api/v1/lessons.py
------------------------
Daily educational lesson endpoints.

GET  /api/v1/lessons/today?user_id=X
  Returns today's lesson at the user's EFFECTIVE difficulty tier
  (base_level + progression from lessons completed, capped at 2), plus
  whether they've already dismissed it today (so the frontend can skip
  rendering it on repeat visits within the same day).

POST /api/v1/lessons/dismiss
  Marks today's lesson dismissed (Redis, self-expiring) AND durably
  increments lessons_completed_count in Postgres — this is what drives
  the progressive difficulty increase over time.

GET  /api/v1/lessons/level?user_id=X
PUT  /api/v1/lessons/level
  View/set the user's manual base_level. Defaults to their onboarding
  sophistication_tier (novice=0, intermediate=1, advanced=2) the first
  time this is queried, if no row exists yet.
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.lessons.content import LESSONS_BY_TIER, TIER_LABELS, get_lesson_for_date

logger = logging.getLogger("aureus.api.lessons")
router = APIRouter(prefix="/api/v1/lessons", tags=["lessons"])

LESSONS_PER_TIER_BUMP = 15   # every 15 lessons completed, effective tier goes up by 1
_DISMISS_TTL_SECONDS = 60 * 60 * 30  # 30h — comfortably spans a calendar day with margin


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def _get_or_create_progress(conn, user_id: str) -> dict:
    row = conn.execute(
        text("SELECT base_level, lessons_completed_count FROM user_learning_progress WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchone()
    if row:
        return {"base_level": row.base_level, "lessons_completed_count": row.lessons_completed_count}

    # No row yet — normally onboarding.py's /complete endpoint creates this
    # with the right base_level from the sophistication quiz. If a user
    # reaches here without one (e.g. a pre-existing test account created
    # before onboarding existed), default to Foundational+ (0).
    conn.execute(
        text("""
            INSERT INTO user_learning_progress (user_id, base_level, lessons_completed_count)
            VALUES (:uid, 0, 0)
            ON CONFLICT (user_id) DO NOTHING
        """),
        {"uid": user_id},
    )
    return {"base_level": 0, "lessons_completed_count": 0}


def _effective_tier(base_level: int, lessons_completed: int) -> int:
    bump = lessons_completed // LESSONS_PER_TIER_BUMP
    return max(0, min(2, base_level + bump))


@router.get("/today")
def get_todays_lesson(user_id: str) -> dict:
    today = date.today()
    day_of_year = today.timetuple().tm_yday

    engine = _get_engine()
    try:
        with engine.begin() as conn:
            progress = _get_or_create_progress(conn, user_id)
    finally:
        engine.dispose()

    tier = _effective_tier(progress["base_level"], progress["lessons_completed_count"])
    lesson = get_lesson_for_date(tier, day_of_year)

    dismiss_key = f"lesson_dismissed:{user_id}:{today.isoformat()}"
    try:
        already_dismissed = bool(get_redis_client().get(dismiss_key))
    except Exception:
        already_dismissed = False

    lessons_into_tier = progress["lessons_completed_count"] % LESSONS_PER_TIER_BUMP
    lessons_to_next_tier = None if tier == 2 else (LESSONS_PER_TIER_BUMP - lessons_into_tier)

    return {
        "lesson": {
            "id": lesson.id, "title": lesson.title, "category": lesson.category,
            "body": lesson.body, "key_takeaway": lesson.key_takeaway,
        },
        "tier": tier,
        "tier_label": TIER_LABELS[tier],
        "already_dismissed_today": already_dismissed,
        "lessons_completed_count": progress["lessons_completed_count"],
        "lessons_to_next_tier": lessons_to_next_tier,
    }


class DismissRequest(BaseModel):
    user_id: str
    lesson_id: str


@router.post("/dismiss")
def dismiss_todays_lesson(req: DismissRequest) -> dict:
    today = date.today()
    dismiss_key = f"lesson_dismissed:{req.user_id}:{today.isoformat()}"

    try:
        get_redis_client().setex(dismiss_key, _DISMISS_TTL_SECONDS, req.lesson_id)
    except Exception as exc:
        logger.warning("Could not set dismissal flag in Redis", extra={"error": str(exc)})

    engine = _get_engine()
    try:
        with engine.begin() as conn:
            _get_or_create_progress(conn, req.user_id)  # ensure row exists
            conn.execute(
                text("""
                    UPDATE user_learning_progress
                    SET lessons_completed_count = lessons_completed_count + 1,
                        last_lesson_id_shown = :lesson_id,
                        last_shown_date = :today,
                        updated_at = NOW()
                    WHERE user_id = :uid
                """),
                {"uid": req.user_id, "lesson_id": req.lesson_id, "today": today},
            )
            row = conn.execute(
                text("SELECT base_level, lessons_completed_count FROM user_learning_progress WHERE user_id = :uid"),
                {"uid": req.user_id},
            ).fetchone()
    finally:
        engine.dispose()

    new_tier = _effective_tier(row.base_level, row.lessons_completed_count) if row else 0
    return {"dismissed": True, "lessons_completed_count": row.lessons_completed_count if row else 0, "current_tier": new_tier}


@router.get("/level")
def get_level(user_id: str) -> dict:
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            progress = _get_or_create_progress(conn, user_id)
    finally:
        engine.dispose()
    tier = _effective_tier(progress["base_level"], progress["lessons_completed_count"])
    return {
        "base_level": progress["base_level"],
        "base_level_label": TIER_LABELS[progress["base_level"]],
        "effective_tier": tier,
        "effective_tier_label": TIER_LABELS[tier],
        "lessons_completed_count": progress["lessons_completed_count"],
    }


class SetLevelRequest(BaseModel):
    user_id: str
    base_level: int = Field(ge=0, le=2)


@router.put("/level")
def set_level(req: SetLevelRequest) -> dict:
    """
    Lets a user manually set their starting difficulty in Settings —
    e.g. an experienced trader can jump straight to Expert instead of
    grinding through 30 lessons to get there via progression alone.
    """
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            _get_or_create_progress(conn, req.user_id)
            conn.execute(
                text("UPDATE user_learning_progress SET base_level = :lvl, updated_at = NOW() WHERE user_id = :uid"),
                {"lvl": req.base_level, "uid": req.user_id},
            )
    except Exception as exc:
        logger.error("Set level failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Could not update learning level")
    finally:
        engine.dispose()

    return {"base_level": req.base_level, "base_level_label": TIER_LABELS[req.base_level]}
