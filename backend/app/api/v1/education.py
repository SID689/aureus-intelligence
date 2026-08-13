"""
app/api/v1/education.py
-------------------------
The /education course browser API — the self-paced counterpart to the
dashboard's daily-lesson card (app/api/v1/lessons.py). Both read the same
curriculum registry (app/lessons/content.py), so the two surfaces can
never show divergent content.

  GET  /api/v1/education/catalog?user_id=      full curriculum + per-user progress
  GET  /api/v1/education/lesson/{id}?user_id=  one lesson (quiz answers withheld)
  POST /api/v1/education/lesson/{id}/start     mark in_progress
  POST /api/v1/education/lesson/{id}/complete  mark complete, award lesson XP
  POST /api/v1/education/lesson/{id}/quiz      grade a quiz attempt, award bonus XP
  GET  /api/v1/education/progress?user_id=     XP, accuracy, badges
  GET  /api/v1/education/curriculum-health     authoring coverage check (no user)

QUIZ ANSWER HANDLING
Correct answers are never serialized to the client before submission — see
Lesson.to_detail_dict(include_answers=False), which is the default.
Grading happens server-side in POST /quiz, and only then does the response
include which options were correct plus the per-question explanations.
Option ORDER is a deterministic shuffle fixed at import (content.py), so
the indices the client submits always line up with the server's view.

XP IS AWARDED ONCE, NOT PER VISIT
Both /complete and /quiz are idempotent with respect to XP: re-completing
a lesson or retaking a passed quiz does not re-award points. Quiz score is
tracked as a high-water mark so a worse retake never reduces banked
progress.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.lessons.badges import ProgressSnapshot, evaluate_badges
from app.lessons.content import (
    ALL_LESSONS,
    LESSONS_BY_TIER,
    get_lesson,
    lessons_without_quizzes,
    tier_summary,
    total_xp_available,
)
from app.lessons.models import QUIZ_BONUS_XP, TIER_DESCRIPTIONS, TIER_LABELS

logger = logging.getLogger("aureus.api.education")
router = APIRouter(prefix="/api/v1/education", tags=["education"])


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def _fetch_progress_rows(conn, user_id: str) -> dict[str, dict]:
    rows = conn.execute(
        text("""
            SELECT lesson_id, tier, status, quiz_attempts, quiz_best_score,
                   quiz_total, quiz_passed, xp_earned, completed_at
            FROM user_lesson_progress
            WHERE user_id = :uid
        """),
        {"uid": user_id},
    ).fetchall()
    return {
        r.lesson_id: {
            "status": r.status,
            "quiz_attempts": r.quiz_attempts,
            "quiz_best_score": r.quiz_best_score,
            "quiz_total": r.quiz_total,
            "quiz_passed": r.quiz_passed,
            "xp_earned": r.xp_earned,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in rows
    }


def _build_snapshot(progress: dict[str, dict]) -> ProgressSnapshot:
    completed_by_tier: dict[int, int] = {}
    total_completed = total_xp = 0
    quizzes_taken = quizzes_passed = perfect = correct = answered = 0

    for lesson in ALL_LESSONS:
        p = progress.get(lesson.id)
        if not p:
            continue
        total_xp += p["xp_earned"]
        if p["status"] == "completed":
            total_completed += 1
            completed_by_tier[lesson.tier] = completed_by_tier.get(lesson.tier, 0) + 1
        if p["quiz_attempts"] > 0 and p["quiz_total"]:
            quizzes_taken += 1
            correct += p["quiz_best_score"] or 0
            answered += p["quiz_total"]
            if p["quiz_passed"]:
                quizzes_passed += 1
            if p["quiz_best_score"] == p["quiz_total"]:
                perfect += 1

    return ProgressSnapshot(
        completed_by_tier=completed_by_tier,
        total_completed=total_completed,
        total_xp=total_xp,
        quizzes_taken=quizzes_taken,
        quizzes_passed=quizzes_passed,
        perfect_quizzes=perfect,
        correct_answers=correct,
        total_answers=answered,
    )


# ── Catalog ───────────────────────────────────────────────────────────────

@router.get("/catalog")
def get_catalog(user_id: str) -> dict:
    """Full curriculum grouped by difficulty tier, annotated with this user's progress."""
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            progress = _fetch_progress_rows(conn, user_id)
    except Exception as exc:
        logger.error("Catalog query failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Could not load curriculum progress")
    finally:
        engine.dispose()

    modules = []
    for meta in tier_summary():
        tier = meta["tier"]
        lessons = []
        completed = tier_xp = 0
        for lesson in LESSONS_BY_TIER[tier]:
            p = progress.get(lesson.id)
            status = p["status"] if p else "not_started"
            if status == "completed":
                completed += 1
            tier_xp += p["xp_earned"] if p else 0
            lessons.append({
                **lesson.to_summary_dict(),
                "status": status,
                "xp_earned": p["xp_earned"] if p else 0,
                "quiz_best_score": p["quiz_best_score"] if p else None,
                "quiz_total": p["quiz_total"] if p else None,
                "quiz_passed": p["quiz_passed"] if p else False,
                "completed_at": p["completed_at"] if p else None,
            })
        modules.append({
            **meta,
            "lessons": lessons,
            "lessons_completed": completed,
            "xp_earned": tier_xp,
            "percent_complete": round(completed / len(lessons) * 100) if lessons else 0,
        })

    snapshot = _build_snapshot(progress)
    return {
        "modules": modules,
        "totals": {
            "lessons_total": len(ALL_LESSONS),
            "lessons_completed": snapshot.total_completed,
            "xp_earned": snapshot.total_xp,
            "xp_available": total_xp_available(),
            "percent_complete": round(snapshot.total_completed / len(ALL_LESSONS) * 100) if ALL_LESSONS else 0,
        },
    }


# ── Single lesson ─────────────────────────────────────────────────────────

@router.get("/lesson/{lesson_id}")
def get_lesson_detail(lesson_id: str, user_id: str) -> dict:
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson {lesson_id!r} not found")

    engine = _get_engine()
    try:
        with engine.connect() as conn:
            progress = _fetch_progress_rows(conn, user_id)
    finally:
        engine.dispose()

    p = progress.get(lesson_id)
    # include_answers stays False — the client must not receive the key.
    return {
        "lesson": lesson.to_detail_dict(include_answers=False),
        "progress": {
            "status": p["status"] if p else "not_started",
            "xp_earned": p["xp_earned"] if p else 0,
            "quiz_attempts": p["quiz_attempts"] if p else 0,
            "quiz_best_score": p["quiz_best_score"] if p else None,
            "quiz_total": p["quiz_total"] if p else None,
            "quiz_passed": p["quiz_passed"] if p else False,
        },
        "quiz_pass_mark": lesson.quiz_pass_mark(),
        "quiz_bonus_xp": QUIZ_BONUS_XP if lesson.quiz else 0,
    }


# ── Mutations ─────────────────────────────────────────────────────────────

class UserBody(BaseModel):
    user_id: str


def _upsert_started(conn, user_id: str, lesson) -> None:
    conn.execute(
        text("""
            INSERT INTO user_lesson_progress (user_id, lesson_id, tier, status, first_viewed_at)
            VALUES (:uid, :lid, :tier, 'in_progress', NOW())
            ON CONFLICT (user_id, lesson_id) DO UPDATE
              -- The ::lesson_completion_status cast is required: a bare CASE
              -- yields `text`, which Postgres will not implicitly coerce into
              -- an enum column.
              SET status = (CASE
                    WHEN user_lesson_progress.status = 'completed' THEN 'completed'
                    ELSE 'in_progress'
                  END)::lesson_completion_status,
                  first_viewed_at = COALESCE(user_lesson_progress.first_viewed_at, NOW()),
                  updated_at = NOW()
        """),
        {"uid": user_id, "lid": lesson.id, "tier": lesson.tier},
    )


@router.post("/lesson/{lesson_id}/start")
def start_lesson(lesson_id: str, body: UserBody) -> dict:
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson {lesson_id!r} not found")
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            _upsert_started(conn, body.user_id, lesson)
    except Exception as exc:
        logger.error("Start lesson failed", extra={"error": str(exc), "lesson_id": lesson_id})
        raise HTTPException(status_code=500, detail="Could not record lesson start")
    finally:
        engine.dispose()
    return {"lesson_id": lesson_id, "status": "in_progress"}


@router.post("/lesson/{lesson_id}/complete")
def complete_lesson(lesson_id: str, body: UserBody) -> dict:
    """
    Mark a lesson complete and award its base XP. Idempotent: the XP add is
    guarded on the row not already being 'completed', so repeat calls (a
    double-click, a page refresh) don't inflate the score.
    """
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson {lesson_id!r} not found")

    engine = _get_engine()
    try:
        with engine.begin() as conn:
            _upsert_started(conn, body.user_id, lesson)
            row = conn.execute(
                text("""
                    UPDATE user_lesson_progress
                    SET status       = 'completed',
                        completed_at = COALESCE(completed_at, NOW()),
                        xp_earned    = xp_earned + CASE WHEN status <> 'completed' THEN :xp ELSE 0 END,
                        updated_at   = NOW()
                    WHERE user_id = :uid AND lesson_id = :lid
                    RETURNING xp_earned, (completed_at IS NOT NULL) AS was_completed
                """),
                {"uid": body.user_id, "lid": lesson.id, "xp": lesson.xp_points},
            ).fetchone()
    except Exception as exc:
        logger.error("Complete lesson failed", extra={"error": str(exc), "lesson_id": lesson_id})
        raise HTTPException(status_code=500, detail="Could not record lesson completion")
    finally:
        engine.dispose()

    return {
        "lesson_id": lesson_id,
        "status": "completed",
        "xp_earned_total_for_lesson": row.xp_earned if row else 0,
    }


class QuizSubmission(BaseModel):
    user_id: str
    # answers[i] is the selected option index for question i; -1 = skipped
    answers: list[int] = Field(min_length=1)


@router.post("/lesson/{lesson_id}/quiz")
def submit_quiz(lesson_id: str, body: QuizSubmission) -> dict:
    """
    Grade a quiz attempt server-side. The response is the first and only
    place correct answers and explanations are revealed.
    """
    lesson = get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson {lesson_id!r} not found")
    if not lesson.quiz:
        raise HTTPException(status_code=400, detail="This lesson has no quiz")
    if len(body.answers) != len(lesson.quiz):
        raise HTTPException(
            status_code=400,
            detail=f"Expected {len(lesson.quiz)} answers, received {len(body.answers)}",
        )

    results = []
    score = 0
    for i, (q, given) in enumerate(zip(lesson.quiz, body.answers)):
        correct = given == q.correct_index
        if correct:
            score += 1
        results.append({
            "index": i,
            "your_answer": given,
            "correct_index": q.correct_index,
            "correct": correct,
            "explanation": q.explanation,
        })

    total = len(lesson.quiz)
    pass_mark = lesson.quiz_pass_mark()
    passed = score >= pass_mark

    engine = _get_engine()
    try:
        with engine.begin() as conn:
            _upsert_started(conn, body.user_id, lesson)
            row = conn.execute(
                text("""
                    UPDATE user_lesson_progress
                    SET quiz_attempts   = quiz_attempts + 1,
                        -- high-water mark: a worse retake never lowers the record
                        quiz_best_score = GREATEST(COALESCE(quiz_best_score, 0), :score),
                        quiz_total      = :total,
                        -- bonus XP is awarded once, on the first passing attempt
                        xp_earned       = xp_earned + CASE
                                            WHEN :passed AND NOT quiz_passed THEN :bonus ELSE 0
                                          END,
                        quiz_passed     = quiz_passed OR :passed,
                        updated_at      = NOW()
                    WHERE user_id = :uid AND lesson_id = :lid
                    RETURNING quiz_attempts, quiz_best_score, quiz_passed, xp_earned
                """),
                {
                    "uid": body.user_id, "lid": lesson.id, "score": score, "total": total,
                    "passed": passed, "bonus": QUIZ_BONUS_XP,
                },
            ).fetchone()
    except Exception as exc:
        logger.error("Quiz submission failed", extra={"error": str(exc), "lesson_id": lesson_id})
        raise HTTPException(status_code=500, detail="Could not record quiz result")
    finally:
        engine.dispose()

    return {
        "lesson_id": lesson_id,
        "score": score,
        "total": total,
        "pass_mark": pass_mark,
        "passed": passed,
        "attempts": row.quiz_attempts if row else 1,
        "best_score": row.quiz_best_score if row else score,
        "xp_earned_total_for_lesson": row.xp_earned if row else 0,
        "results": results,
    }


# ── Progress & achievements ───────────────────────────────────────────────

@router.get("/progress")
def get_progress(user_id: str) -> dict:
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            progress = _fetch_progress_rows(conn, user_id)
            legacy = conn.execute(
                text("SELECT lessons_completed_count, base_level FROM user_learning_progress WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchone()
    except Exception as exc:
        logger.error("Progress query failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Could not load progress")
    finally:
        engine.dispose()

    s = _build_snapshot(progress)
    accuracy = round(s.correct_answers / s.total_answers * 100, 1) if s.total_answers else None

    by_tier = [
        {
            "tier": tier,
            "label": TIER_LABELS[tier],
            "description": TIER_DESCRIPTIONS[tier],
            "completed": s.completed_by_tier.get(tier, 0),
            "total": len(LESSONS_BY_TIER[tier]),
        }
        for tier in sorted(LESSONS_BY_TIER)
    ]

    return {
        "xp_earned": s.total_xp,
        "xp_available": total_xp_available(),
        "lessons_completed": s.total_completed,
        "lessons_total": len(ALL_LESSONS),
        "quizzes_taken": s.quizzes_taken,
        "quizzes_passed": s.quizzes_passed,
        "perfect_quizzes": s.perfect_quizzes,
        "quiz_accuracy_pct": accuracy,
        "correct_answers": s.correct_answers,
        "total_answers": s.total_answers,
        "by_tier": by_tier,
        "badges": evaluate_badges(s),
        # The dashboard's daily-lesson card kept its own counter before
        # per-lesson tracking existed. It's reported separately rather than
        # merged, because there's no record of WHICH lessons it counted.
        "legacy_daily_lessons_completed": legacy.lessons_completed_count if legacy else 0,
    }


@router.get("/curriculum-health")
def curriculum_health() -> dict:
    """Authoring coverage check — no user context, safe to call from a smoke test."""
    missing = lessons_without_quizzes()
    return {
        "lessons_total": len(ALL_LESSONS),
        "quiz_questions_total": sum(len(l.quiz) for l in ALL_LESSONS),
        "lessons_without_quizzes": missing,
        "quiz_coverage_pct": round((len(ALL_LESSONS) - len(missing)) / len(ALL_LESSONS) * 100, 1) if ALL_LESSONS else 0,
        "xp_available": total_xp_available(),
        "tiers": tier_summary(),
    }
