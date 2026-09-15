"""
app/lessons/badges.py
-----------------------
Skill badges, derived from progress rather than stored.

WHY DERIVED AND NOT A TABLE: a badge is a pure function of lesson
completions and quiz results, both of which are already persisted. Storing
awarded badges separately would create a second source of truth that can
drift (a badge row surviving after the completion that earned it was
deleted, or a newly-added badge never being awarded retroactively).
Computing them on read means adding a new badge definition here
immediately and correctly applies to every existing user's history.

The cost is recomputation per request, which is trivial at this scale —
the inputs are one indexed query of a few dozen rows per user.
"""

from dataclasses import dataclass
from typing import Callable

from app.lessons.content import LESSONS_BY_TIER
from app.lessons.models import (
    TIER_ADVANCED,
    TIER_BEGINNER,
    TIER_EXPERT,
    TIER_FOUNDATIONAL,
    TIER_INTERMEDIATE,
)


@dataclass(frozen=True)
class BadgeDefinition:
    id: str
    name: str
    description: str
    icon: str                      # emoji, rendered directly by the UI
    # Given a ProgressSnapshot, return (earned, current_value, target_value)
    evaluate: Callable[["ProgressSnapshot"], tuple[bool, int, int]]


@dataclass
class ProgressSnapshot:
    """Everything the badge rules need, assembled once per request."""
    completed_by_tier: dict[int, int]     # tier -> completed lesson count
    total_completed: int
    total_xp: int
    quizzes_taken: int
    quizzes_passed: int
    perfect_quizzes: int                  # scored 100%
    correct_answers: int
    total_answers: int

    def tier_complete(self, tier: int) -> tuple[bool, int, int]:
        target = len(LESSONS_BY_TIER[tier])
        done = self.completed_by_tier.get(tier, 0)
        return done >= target, done, target


def _tier_badge(tier: int) -> Callable[[ProgressSnapshot], tuple[bool, int, int]]:
    return lambda s: s.tier_complete(tier)


def _count_badge(getter: Callable[[ProgressSnapshot], int], target: int):
    return lambda s: (getter(s) >= target, getter(s), target)


BADGE_DEFINITIONS: list[BadgeDefinition] = [
    # ── Milestone badges ──────────────────────────────────────────────
    BadgeDefinition(
        "first_steps", "First Steps", "Complete your first lesson.", "01",
        _count_badge(lambda s: s.total_completed, 1),
    ),
    BadgeDefinition(
        "getting_serious", "Getting Serious", "Complete 10 lessons.", "10",
        _count_badge(lambda s: s.total_completed, 10),
    ),
    BadgeDefinition(
        "dedicated_student", "Dedicated Student", "Complete 25 lessons.", "25",
        _count_badge(lambda s: s.total_completed, 25),
    ),

    # ── Tier completion badges ────────────────────────────────────────
    BadgeDefinition(
        "market_literate", "Market Literate",
        "Complete every lesson in New to Investing.", "N", _tier_badge(TIER_BEGINNER),
    ),
    BadgeDefinition(
        "foundations_built", "Foundations Built",
        "Complete every lesson in Foundational+.", "F", _tier_badge(TIER_FOUNDATIONAL),
    ),
    BadgeDefinition(
        "practitioner", "Practitioner",
        "Complete every lesson in Intermediate.", "I", _tier_badge(TIER_INTERMEDIATE),
    ),
    BadgeDefinition(
        "quant_minded", "Quant-Minded",
        "Complete every lesson in Advanced.", "A", _tier_badge(TIER_ADVANCED),
    ),
    BadgeDefinition(
        "institutional_grade", "Institutional Grade",
        "Complete every lesson in Expert.", "E", _tier_badge(TIER_EXPERT),
    ),

    # ── Quiz mastery badges ───────────────────────────────────────────
    BadgeDefinition(
        "quiz_starter", "Quiz Starter", "Pass your first knowledge check.", "Q",
        _count_badge(lambda s: s.quizzes_passed, 1),
    ),
    BadgeDefinition(
        "sharp_shooter", "Sharp Shooter", "Score 100% on 5 knowledge checks.", "5×",
        _count_badge(lambda s: s.perfect_quizzes, 5),
    ),
    BadgeDefinition(
        "flawless_ten", "Flawless Ten", "Score 100% on 10 knowledge checks.", "10×",
        _count_badge(lambda s: s.perfect_quizzes, 10),
    ),

    # ── XP badges ─────────────────────────────────────────────────────
    BadgeDefinition(
        "xp_1000", "Thousand Club", "Earn 1,000 XP.", "⭐",
        _count_badge(lambda s: s.total_xp, 1000),
    ),
    BadgeDefinition(
        "xp_3000", "Scholar", "Earn 3,000 XP.", "3K",
        _count_badge(lambda s: s.total_xp, 3000),
    ),
]


def evaluate_badges(snapshot: ProgressSnapshot) -> list[dict]:
    """
    Return every badge with its earned state and progress toward it.
    Unearned badges are returned too — showing what's still achievable is
    the point of an achievements screen, not just what's already done.
    """
    out = []
    for b in BADGE_DEFINITIONS:
        earned, current, target = b.evaluate(snapshot)
        out.append({
            "id": b.id,
            "name": b.name,
            "description": b.description,
            "icon": b.icon,
            "earned": earned,
            "progress_current": min(current, target),
            "progress_target": target,
        })
    return out
