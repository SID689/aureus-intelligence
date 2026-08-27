"""
app/lessons/content.py
------------------------
The curriculum registry. Assembles every tier into the lookups the API
layer uses, and attaches banked quizzes to the lessons that need them.

CURRICULUM SHAPE
    Tier 0  New to Investing   Module 0 — assumes zero prior knowledge
    Tier 1  Foundational+      one layer past the basics
    Tier 2  Intermediate       doing the work: sizing, valuation, filings
    Tier 3  Advanced           factors, greeks, correlation regimes
    Tier 4  Expert             institutional risk, crowding, execution

QUIZ ATTACHMENT
Module 0 lessons carry their quizzes inline (prose and assessment were
authored together). Tiers 1–4 draw from quizzes.py's bank, which is
attached here. `dataclasses.replace` is used rather than mutation because
Lesson is frozen — that immutability is deliberate, so a request handler
can never accidentally modify shared curriculum state.

BACKWARDS COMPATIBILITY
`LESSONS_BY_TIER`, `TIER_LABELS`, and `get_lesson_for_date()` keep their
original names and signatures because app/api/v1/lessons.py (the daily
dashboard lesson) imports them. The daily-lesson feature and the new
/education course browser read from this same registry, so content can
never diverge between the two surfaces.
"""

import random
from dataclasses import replace

from app.lessons.models import (  # re-exported for callers
    BASE_XP_BY_TIER,
    DIFFICULTY_CODES,
    MAX_TIER,
    MIN_TIER,
    QUIZ_BONUS_XP,
    QUIZ_PASS_RATIO,
    TIER_ADVANCED,
    TIER_BEGINNER,
    TIER_DESCRIPTIONS,
    TIER_EXPERT,
    TIER_FOUNDATIONAL,
    TIER_INTERMEDIATE,
    TIER_LABELS,
    Callout,
    GlossaryTerm,
    Lesson,
    QuizQuestion,
)
from app.lessons.enrichment import enrich
from app.lessons.quizzes import quiz_for
from app.lessons.tier0_beginner import TIER_0_BEGINNER
from app.lessons.tier0_beginner_b import TIER_0_BEGINNER_B
from app.lessons.tier1_foundational import TIER_1_FOUNDATIONAL
from app.lessons.tier2_intermediate import TIER_2_INTERMEDIATE
from app.lessons.tier2_intermediate_b import TIER_2_INTERMEDIATE_B
from app.lessons.tier3_advanced import TIER_3_ADVANCED
from app.lessons.tier4_expert import TIER_4_EXPERT


def _shuffle_options(lesson_id: str, index: int, q: QuizQuestion) -> QuizQuestion:
    """
    Deterministically permute a question's options so the correct answer
    isn't always in the same slot.

    WHY THIS EXISTS: questions are authored with the correct answer written
    first or second, which left ~90% of the bank's answers at index 1 — a
    user could score highly by always picking option B without reading. This
    redistributes them without needing to hand-shuffle 90+ literals.

    WHY IT MUST BE DETERMINISTIC: the client receives options in this order
    from GET /lesson/{id} and posts back the index it displayed. If the order
    changed between processes (or between the GET and the POST), grading
    would silently mark correct answers wrong. Seeding on (lesson_id, index)
    guarantees the identical permutation on every worker and every restart.
    """
    order = list(range(len(q.options)))
    random.Random(f"{lesson_id}:{index}").shuffle(order)
    return QuizQuestion(
        question=q.question,
        options=[q.options[i] for i in order],
        correct_index=order.index(q.correct_index),
        explanation=q.explanation,
    )


def _prepare(lesson: Lesson) -> Lesson:
    """
    Attach the banked quiz (if the lesson has none inline), shuffle its
    options, then append any registered interactive content.

    Enrichment runs last so a lesson authored with its own exercises keeps
    them — see enrichment.py, which appends rather than replaces.
    """
    quiz = lesson.quiz or quiz_for(lesson.id)
    if quiz:
        lesson = replace(lesson, quiz=[_shuffle_options(lesson.id, i, q) for i, q in enumerate(quiz)])
    return enrich(lesson)


LESSONS_BY_TIER: dict[int, list[Lesson]] = {
    TIER_BEGINNER:     [_prepare(l) for l in TIER_0_BEGINNER + TIER_0_BEGINNER_B],
    TIER_FOUNDATIONAL: [_prepare(l) for l in TIER_1_FOUNDATIONAL],
    TIER_INTERMEDIATE: [_prepare(l) for l in TIER_2_INTERMEDIATE + TIER_2_INTERMEDIATE_B],
    TIER_ADVANCED:     [_prepare(l) for l in TIER_3_ADVANCED],
    TIER_EXPERT:       [_prepare(l) for l in TIER_4_EXPERT],
}

ALL_LESSONS: list[Lesson] = [l for tier in sorted(LESSONS_BY_TIER) for l in LESSONS_BY_TIER[tier]]

LESSONS_BY_ID: dict[str, Lesson] = {l.id: l for l in ALL_LESSONS}

# Fail loudly at import time rather than serving two lessons with the same id.
if len(LESSONS_BY_ID) != len(ALL_LESSONS):
    seen: set[str] = set()
    dupes = {l.id for l in ALL_LESSONS if l.id in seen or seen.add(l.id)}  # type: ignore[func-returns-value]
    raise RuntimeError(f"Duplicate lesson ids in curriculum: {sorted(dupes)}")


def get_lesson(lesson_id: str) -> Lesson | None:
    return LESSONS_BY_ID.get(lesson_id)


def get_lesson_for_date(tier: int, day_of_year: int) -> Lesson:
    """
    Deterministic daily rotation within a tier — every user at the same tier
    sees the same lesson on the same calendar day. Used by the dashboard's
    daily-lesson card.
    """
    tier = max(MIN_TIER, min(MAX_TIER, tier))
    bank = LESSONS_BY_TIER[tier]
    return bank[day_of_year % len(bank)]


def tier_summary() -> list[dict]:
    """Per-tier metadata for the course browser (no per-user state)."""
    return [
        {
            "tier": tier,
            "difficulty_level": DIFFICULTY_CODES[tier],
            "label": TIER_LABELS[tier],
            "description": TIER_DESCRIPTIONS[tier],
            "lesson_count": len(LESSONS_BY_TIER[tier]),
            "total_xp_available": sum(l.max_xp for l in LESSONS_BY_TIER[tier]),
            "estimated_minutes": sum(l.estimated_read_time_minutes for l in LESSONS_BY_TIER[tier]),
        }
        for tier in sorted(LESSONS_BY_TIER)
    ]


def total_xp_available() -> int:
    return sum(l.max_xp for l in ALL_LESSONS)


def lessons_without_quizzes() -> list[str]:
    """
    Coverage check — surfaced by GET /api/v1/education/curriculum-health so
    missing quizzes are visible rather than silently shipping a lesson whose
    quiz step is skipped.
    """
    return [l.id for l in ALL_LESSONS if not l.quiz]
