"""
app/agents/guardrails.py
--------------------------
Two things live here:

1. CORE_ORCHESTRATOR_SYSTEM_PROMPT — the definitive system prompt for any
   general-purpose financial LLM call in Aureus (currently wired into the
   analysis-reasoning polish step in analysis/reasoning.py; the same
   constant should be reused by any future "ask Aureus a question" endpoint
   so the guardrails are enforced from one place, not re-implemented per call site).

2. validate_llm_output() — regex-based middleware that scans ANY LLM output
   string before it reaches a client. It looks for absolute predictive
   language ("will rise"), guarantee language ("guaranteed return"), and
   risk-free claims, all of which are compliance violations regardless of
   how confident the underlying model was. Matches are flagged; callers
   decide whether to strip, reject-and-regenerate, or fall back to a
   deterministic (non-LLM) response.

This is intentionally regex/pattern based rather than a second LLM call —
a second LLM call to "check" the first is slower, costs money, and can
itself hallucinate a pass/fail verdict. A fixed pattern list is fast,
free, deterministic, and auditable (you can read every rule that exists).
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("aureus.agents.guardrails")


# =====================================================================
# 1. CORE SYSTEM PROMPT
# =====================================================================

CORE_ORCHESTRATOR_SYSTEM_PROMPT = """You are the Aureus Intelligence financial analysis orchestrator. You operate under strict, non-negotiable rules that exist for legal and ethical reasons, not stylistic preference. Follow every rule below exactly.

## SCOPE: FINANCIAL TOPICS ONLY
You answer questions about: equities, ETFs, bonds, macroeconomics, company fundamentals, technical analysis, market structure, portfolio construction, and the Aureus Intelligence platform itself.

If a user asks about ANYTHING outside this scope (relationships, medical advice, coding help unrelated to finance, politics unrelated to markets, general trivia, creative writing, etc.), respond with EXACTLY this and nothing else:
"I'm focused specifically on financial analysis and markets. That question is outside what I can help with here: is there anything about your portfolio, a stock, or market conditions I can look into instead?"
Do not soften this into partial engagement with the off-topic request. Do not answer "just this once." This is an absolute rule, not a judgment call.

## CITATIONS: EVERY FACTUAL CLAIM NEEDS A SOURCE
When you state a specific fact (a financial metric, a news event, a filing detail, a historical price), it must be traceable to data provided to you in this conversation's context (search results, database query results, or explicitly provided figures). Never state a specific number, date, or event from memory alone if source data was supposed to back it: say "I don't have current data on that" instead of guessing.
When citing, name the source plainly ("per the Q3 10-Q filing...", "based on today's market data...") rather than inventing citation formatting.

## NUMERICAL DISCIPLINE, NEVER FABRICATE A NUMBER
Every number you state (price, ratio, percentage, date) must come from the underlying data you were given, not be estimated or "rounded from memory." If you don't have a specific figure, say so explicitly rather than producing a plausible-sounding placeholder. A wrong number stated with confidence is worse than an honest "I don't have that figure."

## ABSOLUTE PROHIBITIONS
Never use predictive-certainty language: "will rise," "will fall," "guaranteed to," "certain to," "definitely will."
Never claim any investment is "risk-free," "can't lose," or offers a "guaranteed return."
Never give a specific personalized buy/sell instruction ("you should buy X now"). You may discuss what an indicator or model output suggests, framed as informational.
Never diagnose someone's financial situation as "you can afford" or "you should risk", that depends on facts about them you don't have and legal categories you're not qualified to assess.

## REQUIRED FRAMING
Frame outputs as informational analysis, not advice: "the model's technical score suggests..." rather than "you should..."
When discussing any historical performance or backtest result, note that past performance does not indicate future results.
When giving any probabilistic or confidence-scored output, note that it is a heuristic estimate, not a calibrated probability guarantee.

## TONE
Direct, precise, and free of hype. No exclamation points. No "to the moon" style language. Speak like a serious analyst, not a promoter."""


# =====================================================================
# 2. OUTPUT VALIDATION MIDDLEWARE
# =====================================================================

# Each pattern is (regex, human-readable violation category).
# Patterns are case-insensitive; \b word boundaries prevent false positives
# like matching "willingness" for "will".
_FORBIDDEN_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Absolute future-price predictions
    (re.compile(r"\bwill\s+(rise|fall|increase|decrease|climb|drop|surge|soar|crash|rally|jump|plunge)\b", re.I), "absolute_price_prediction"),
    (re.compile(r"\b(is|are)\s+going\s+to\s+(rise|fall|increase|decrease|surge|soar|crash|rally)\b", re.I), "absolute_price_prediction"),
    (re.compile(r"\bwill\s+(hit|reach|touch)\s+\$?\d", re.I), "absolute_price_target"),
    (re.compile(r"\bguaranteed?\s+to\s+(rise|fall|increase|outperform|beat)\b", re.I), "absolute_price_prediction"),

    # Guarantee / risk-free language
    (re.compile(r"\bguaranteed?\s+(return|profit|gain|income|yield)\b", re.I), "guaranteed_return_claim"),
    (re.compile(r"\brisk[\s-]?free\b", re.I), "risk_free_claim"),
    (re.compile(r"\b(can'?t|cannot)\s+lose\b", re.I), "cannot_lose_claim"),
    (re.compile(r"\bsure\s+(thing|bet|win)\b", re.I), "sure_thing_claim"),
    (re.compile(r"\b100%\s*(certain|guaranteed|safe|sure)\b", re.I), "absolute_certainty_claim"),
    (re.compile(r"\bno\s+risk\s+(at\s+all|involved|whatsoever)\b", re.I), "no_risk_claim"),

    # Direct personalized trade instructions (the model shouldn't issue these)
    (re.compile(r"\byou\s+should\s+(buy|sell|short|invest\s+in)\b", re.I), "direct_trade_instruction"),
    (re.compile(r"\bI\s+recommend\s+(buying|selling|shorting)\b", re.I), "direct_trade_instruction"),

    # Certainty adverbs stacked with market direction
    (re.compile(r"\b(definitely|certainly|undoubtedly)\s+will\b", re.I), "absolute_certainty_claim"),
]


@dataclass
class ValidationResult:
    is_clean:    bool
    violations:  list[dict] = field(default_factory=list)   # [{category, matched_text, position}]
    cleaned_text: str = ""


def validate_llm_output(text: str) -> ValidationResult:
    """
    Scan LLM-generated text for forbidden absolute/guarantee language.
    Does NOT modify the text — just reports violations. Callers choose
    the remediation strategy (strip the sentence, regenerate, or fall
    back to a deterministic response).
    """
    violations = []
    for pattern, category in _FORBIDDEN_PATTERNS:
        for match in pattern.finditer(text):
            violations.append({
                "category":     category,
                "matched_text": match.group(0),
                "position":     match.start(),
            })

    if violations:
        logger.warning(
            "LLM output failed guardrail validation",
            extra={"violation_count": len(violations), "categories": [v["category"] for v in violations]},
        )

    return ValidationResult(is_clean=len(violations) == 0, violations=violations, cleaned_text=text)


def strip_violating_sentences(text: str, validation: ValidationResult) -> str:
    """
    Remove only the sentences containing violations, keeping the rest of
    the text intact. Used as a lighter-touch remediation than discarding
    the whole response.
    """
    if validation.is_clean:
        return text

    sentences = re.split(r'(?<=[.!?])\s+', text)
    violating_positions = {v["position"] for v in validation.violations}

    cursor = 0
    clean_sentences = []
    for sentence in sentences:
        start, end = cursor, cursor + len(sentence)
        has_violation = any(start <= pos < end for pos in violating_positions)
        if not has_violation:
            clean_sentences.append(sentence)
        cursor = end + 1  # +1 for the split whitespace

    return " ".join(clean_sentences).strip()
