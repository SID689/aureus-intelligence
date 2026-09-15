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
        "Assumes you've placed trades and know the common terms: goes one layer deeper on "
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

# Numeric drills are worth more than the multiple-choice bonus because
# they cannot be guessed. Four options give you 25% for free; a numeric
# field gives you nothing.
PRACTICE_BONUS_XP = 40


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
class NumericQuestion:
    """
    A question answered with a NUMBER rather than a choice.

    Multiple choice teaches recognition; arithmetic teaches the mechanism.
    A reader who can pick "the spread cost $10" from four options has not
    necessarily worked out why — one who types 10 has.

    `tolerance` is absolute, in the same unit as `answer`, and exists
    because these are real calculations: asking for the compounded value
    of $10,000 at 7% over 30 years should accept 76,123 from someone who
    rounded, and reject 50,000 from someone who multiplied instead.
    """
    question: str
    answer: float
    tolerance: float
    explanation: str
    unit: str = ""            # "$", "%", "shares" — rendered beside the input
    hint: str = ""            # revealed on request, costs nothing

    def __post_init__(self) -> None:
        if self.tolerance < 0:
            raise ValueError(f"tolerance must be >= 0: {self.question!r}")

    def is_correct(self, submitted: float) -> bool:
        return abs(submitted - self.answer) <= self.tolerance


@dataclass(frozen=True)
class OrderingQuestion:
    """
    Arrange items into the correct sequence.

    Some ideas are fundamentally about ORDER — the sequence of a trade's
    lifecycle, the seniority of claims in a bankruptcy, the order of
    operations in a DCF — and a multiple-choice question about them
    always leaks the answer in the options.
    """
    question: str
    items: list[str]          # presented shuffled; this is the CORRECT order
    explanation: str

    def __post_init__(self) -> None:
        if len(self.items) < 3:
            raise ValueError(f"Ordering question needs at least 3 items: {self.question!r}")


@dataclass(frozen=True)
class Exercise:
    """
    An interactive calculator embedded in a lesson.

    `kind` names a widget the frontend knows how to render
    (components/education/exercises). `params` seeds its starting values,
    so the same widget can illustrate different points in different
    lessons — the compounding widget opens at 30 years in a retirement
    lesson and at 3 years in a fee-drag one.

    These exist because some lessons are about a RELATIONSHIP, not a
    fact. "Fees compound too" is a sentence you nod at; watching a 1%
    fee eat a quarter of a 40-year balance as you drag a slider is a
    thing you remember.
    """
    kind: Literal[
        "compounding",        # principal/rate/years -> future value
        "spread_cost",        # bid/ask/shares -> round-trip cost
        "position_size",      # account/risk%/entry/stop -> share count
        "drawdown_recovery",  # % lost -> % gain required to break even
        "fee_drag",           # fee % over horizon -> balance forgone
        "expected_value",     # win prob/size, loss size -> EV per trade
        "dollar_cost_average",# volatile path -> DCA vs lump sum
        "risk_of_ruin",       # edge/bet size -> probability of ruin
    ]
    title: str
    prompt: str               # what to try, so it isn't just a toy
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Checkpoint:
    """
    A single question placed MID-lesson rather than at the end.

    Anchored to a paragraph index: the reader answers it having just read
    the relevant passage, while the idea is still loaded. An end-of-lesson
    quiz tests recall of the whole; a checkpoint tests comprehension of
    the part, which is where misunderstanding actually starts.
    """
    after_paragraph: int
    question: str
    options: list[str]
    correct_index: int
    explanation: str

    def __post_init__(self) -> None:
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError(f"correct_index out of range: {self.question!r}")


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

    # ── Interactive additions ────────────────────────────────────────
    # Three kinds, deliberately separate rather than one polymorphic
    # list, because they differ in the only way that matters here:
    # whether the answer can safely reach the browser.
    #
    #   exercises   — calculators. Nothing to grade, nothing to leak.
    #   checkpoints — formative, mid-read. Worth NO XP, so shipping the
    #                 answer costs nothing; the reader gains only by
    #                 being honest with themselves. Graded client-side.
    #   practice    — numeric drills worth XP, so they are graded on the
    #                 server exactly like the quiz and the answers never
    #                 leave it (see api/v1/education.py).
    exercises: list[Exercise] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    practice: list[NumericQuestion] = field(default_factory=list)

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
        """Lesson XP, plus the quiz bonus, plus the practice bonus."""
        return (
            self.xp_points
            + (QUIZ_BONUS_XP if self.quiz else 0)
            + (PRACTICE_BONUS_XP if self.practice else 0)
        )

    def practice_pass_mark(self) -> int:
        """Correct numeric answers required to bank the practice bonus."""
        if not self.practice:
            return 0
        import math
        return max(1, math.ceil(len(self.practice) * QUIZ_PASS_RATIO))

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
            "practice_count": len(self.practice),
            "exercise_count": len(self.exercises),
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
            "exercises": [
                {"kind": e.kind, "title": e.title, "prompt": e.prompt, "params": e.params}
                for e in self.exercises
            ],
            # Checkpoints ship WITH their answers on purpose. They carry no
            # XP, so there is nothing to game — and grading them inline is
            # what makes them instant, which is the entire point of asking
            # mid-read rather than at the end.
            "checkpoints": [
                {
                    "after_paragraph": c.after_paragraph,
                    "question": c.question,
                    "options": c.options,
                    "correct_index": c.correct_index,
                    "explanation": c.explanation,
                }
                for c in self.checkpoints
            ],
            # Practice DOES carry XP, so answers and tolerances stay server
            # side under the same rule as the quiz.
            "practice": [
                {
                    "index": i,
                    "question": q.question,
                    "unit": q.unit,
                    "hint": q.hint,
                    **({"answer": q.answer, "tolerance": q.tolerance, "explanation": q.explanation}
                       if include_answers else {}),
                }
                for i, q in enumerate(self.practice)
            ],
        }
