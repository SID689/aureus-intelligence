"""
app/lessons/models.py
-----------------------
Shared types for the educational curriculum.

CONTENT LIVES IN CODE, PROGRESS LIVES IN THE DATABASE.
That split is deliberate. Lesson text, quizzes, and XP values are static
editorial content with no admin UI — keeping them as Python literals means
they're version-controlled, reviewable in a diff, and can never drift out
of sync with a separate seed script. What IS per-user and mutable
(completion status, quiz scores, XP earned) lives in Postgres in
`user_lesson_progress`. See db/migrations/004_education_modules.sql.

===================================================================
TIER NUMBERING — READ BEFORE CHANGING
===================================================================
Tiers are stored as integers in `user_learning_progress.base_level`, so
the NUMBERS are load-bearing, not just the labels. The scheme was
originally 3 tiers (0=Foundational+, 1=Advanced, 2=Expert). Adding a
BEGINNER tier BELOW Foundational+ shifted every existing number up:

    old 0 (Foundational+) -> new 1
    old 1 (Advanced)      -> new 3
    old 2 (Expert)        -> new 4

Migration 004 remaps existing users' stored base_level accordingly so
nobody silently gets demoted to beginner content. If you insert another
tier in the middle, you must do the same thing again.
"""

from dataclasses import dataclass, field
from typing import Literal

# ── Tier constants ────────────────────────────────────────────────────────
TIER_BEGINNER     = 0
TIER_FOUNDATIONAL = 1
TIER_INTERMEDIATE = 2
TIER_ADVANCED     = 3
TIER_EXPERT       = 4

MIN_TIER = TIER_BEGINNER
MAX_TIER = TIER_EXPERT

# Machine-readable difficulty_level codes, per the curriculum spec.
DIFFICULTY_CODES: dict[int, str] = {
    TIER_BEGINNER:     "BEGINNER",
    TIER_FOUNDATIONAL: "FOUNDATIONAL+",
    TIER_INTERMEDIATE: "INTERMEDIATE",
    TIER_ADVANCED:     "ADVANCED",
    TIER_EXPERT:       "EXPERT",
}

# Human-facing labels used in the UI.
TIER_LABELS: dict[int, str] = {
    TIER_BEGINNER:     "New to Investing",
    TIER_FOUNDATIONAL: "Foundational+",
    TIER_INTERMEDIATE: "Intermediate",
    TIER_ADVANCED:     "Advanced",
    TIER_EXPERT:       "Expert",
}

TIER_DESCRIPTIONS: dict[int, str] = {
    TIER_BEGINNER:
        "Start here if you've never bought a stock. What an exchange is, what you actually "
        "own, how orders get filled, and how to read a quote without guessing.",
    TIER_FOUNDATIONAL:
        "Assumes you've placed trades and know the common terms — goes one layer deeper on "
        "the mechanism behind them and where the standard explanations break down.",
    TIER_INTERMEDIATE:
        "The bridge to professional analysis: valuation under uncertainty, position sizing "
        "math, factor basics, and how to read a filing rather than a headline.",
    TIER_ADVANCED:
        "Factor mechanics, options greeks interactions, correlation regimes, fixed-income "
        "convexity, and market microstructure detail.",
    TIER_EXPERT:
        "Institutional-grade: risk model internals, crowding and unwind dynamics, execution "
        "theory, tail-risk economics, and where standard models structurally fail.",
}

# XP awarded per lesson, scaled by tier — later tiers are denser and take
# longer, so they're worth proportionally more. Quizzes award a bonus on
# top of this (see QUIZ_BONUS_XP), which is what makes the quiz worth
# taking rather than skipping straight to "mark complete".
BASE_XP_BY_TIER: dict[int, int] = {
    TIER_BEGINNER:     50,
    TIER_FOUNDATIONAL: 75,
    TIER_INTERMEDIATE: 100,
    TIER_ADVANCED:     150,
    TIER_EXPERT:       200,
}

# Awarded once, on the first quiz attempt that scores at/above the pass mark.
QUIZ_BONUS_XP = 25
QUIZ_PASS_RATIO = 0.7   # 70% correct to pass and bank the bonus


@dataclass(frozen=True)
class QuizQuestion:
    """
    One multiple-choice question. `correct_index` is the 0-based index into
    `options`. `explanation` is shown after answering regardless of whether
    the user got it right — the explanation IS the teaching moment, so it
    should say why the right answer is right, not just restate it.
    """
    question: str
    options: list[str]
    correct_index: int
    explanation: str

    def __post_init__(self) -> None:
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError(f"correct_index {self.correct_index} out of range for {self.question!r}")
        if len(self.options) < 2:
            raise ValueError(f"Quiz question needs at least 2 options: {self.question!r}")


@dataclass(frozen=True)
class GlossaryTerm:
    """
    An inline term definition. The lesson viewer scans the body for `term`
    and renders it as a hoverable/tappable definition, so a beginner never
    has to leave the page to look up a word they don't know.
    """
    term: str
    definition: str


@dataclass(frozen=True)
class Callout:
    """
    A highlighted aside inside a lesson.
      key_idea    — the single thing to remember
      why_it_matters — practical consequence
      common_mistake — the error this lesson is trying to prevent
      example     — a worked numeric example
    """
    kind: Literal["key_idea", "why_it_matters", "common_mistake", "example"]
    title: str
    body: str


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    category: str
    tier: int
    body: str
    key_takeaway: str
    estimated_read_time_minutes: int = 4
    glossary: list[GlossaryTerm] = field(default_factory=list)
    callouts: list[Callout] = field(default_factory=list)
    quiz: list[QuizQuestion] = field(default_factory=list)

    @property
    def difficulty_level(self) -> str:
        """Machine-readable difficulty code (BEGINNER / FOUNDATIONAL+ / ...)."""
        return DIFFICULTY_CODES[self.tier]

    @property
    def tier_label(self) -> str:
        return TIER_LABELS[self.tier]

    @property
    def xp_points(self) -> int:
        """XP for completing the lesson itself, before any quiz bonus."""
        return BASE_XP_BY_TIER[self.tier]

    @property
    def max_xp(self) -> int:
        """Lesson XP plus the quiz bonus, if this lesson has a quiz."""
        return self.xp_points + (QUIZ_BONUS_XP if self.quiz else 0)

    def quiz_pass_mark(self) -> int:
        """Number of correct answers required to pass this lesson's quiz."""
        if not self.quiz:
            return 0
        import math
        return max(1, math.ceil(len(self.quiz) * QUIZ_PASS_RATIO))

    def to_summary_dict(self) -> dict:
        """Catalog view — no body/quiz answers, safe to list in bulk."""
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "tier": self.tier,
            "difficulty_level": self.difficulty_level,
            "tier_label": self.tier_label,
            "estimated_read_time_minutes": self.estimated_read_time_minutes,
            "xp_points": self.xp_points,
            "max_xp": self.max_xp,
            "quiz_question_count": len(self.quiz),
            "key_takeaway": self.key_takeaway,
        }

    def to_detail_dict(self, include_answers: bool = False) -> dict:
        """
        Full lesson view. `include_answers` MUST stay False for anything the
        client can see before submitting — otherwise the correct answers ship
        to the browser with the quiz and the quiz is meaningless.
        """
        return {
            **self.to_summary_dict(),
            "body": self.body,
            "glossary": [{"term": g.term, "definition": g.definition} for g in self.glossary],
            "callouts": [{"kind": c.kind, "title": c.title, "body": c.body} for c in self.callouts],
            "quiz": [
                {
                    "index": i,
                    "question": q.question,
                    "options": q.options,
                    **({"correct_index": q.correct_index, "explanation": q.explanation} if include_answers else {}),
                }
                for i, q in enumerate(self.quiz)
            ],
        }
