"""
app/agents/state.py
--------------------
LangGraph state definition for the news → portfolio impact pipeline.

TypedDict fields are grouped by the agent that writes them.
Every field has a default-safe type so the graph can be constructed
with only the input fields set — agents fill in the rest as they run.

Design note: we deliberately keep the state flat (no nested TypedDicts)
because LangGraph serializes state to JSON between nodes, and flat dicts
serialize cleanly without custom encoders.
"""

from typing import TypedDict


class NewsProcessingState(TypedDict):

    # ── INPUT (set before graph.invoke()) ─────────────────────────────────────
    article_id:    str
    headline:      str
    clean_content: str
    source:        str
    source_url:    str
    published_at:  str        # ISO-8601
    candidate_tickers: list   # preliminary tickers from preprocessor

    # ── NEWS ANALYST AGENT output ──────────────────────────────────────────────
    sentiment_score:    float             # -1.0 to +1.0
    sentiment_evidence: str              # exact quote from article
    event_type:         str              # earnings|merger_acquisition|regulatory|
                                         # product_launch|macro|management|legal|other
    event_severity:     str              # low|medium|high|critical
    affected_tickers:   list             # refined/confirmed ticker list
    named_entities:     list             # [{name, ticker, role}]
    analyst_summary:    str              # 2-3 sentence factual summary
    analyst_completed:  bool
    analyst_used_fallback: bool          # True if the LLM call failed/parsed-failed and
                                         # sentiment_score is a 0.0 placeholder, not a
                                         # genuine LLM-confirmed-neutral verdict — the
                                         # router must not treat these the same way

    # ── PORTFOLIO RISK-DELTA AGENT output ──────────────────────────────────────
    affected_users:           list       # [{user_id, portfolio_id, ticker, weight, beta}]
    portfolio_impacts:        list       # [{user_id, portfolio_id, impact_estimate,
                                         #   beta_weighted_exposure, confidence,
                                         #   requires_human_review}]
    any_users_affected:       bool       # False → skip advisory agent
    risk_delta_completed:     bool

    # ── ADVISORY NOTIFICATION AGENT output ────────────────────────────────────
    alerts_generated: list               # [{user_id, portfolio_id, message,
                                         #   severity, requires_human_review}]
    advisory_completed: bool

    # ── ERROR TRACKING ─────────────────────────────────────────────────────────
    errors:           list               # list of error strings from any agent
    processing_stage: str               # last completed stage for observability


def make_initial_state(
    article_id:        str,
    headline:          str,
    clean_content:     str,
    source:            str,
    source_url:        str,
    published_at:      str,
    candidate_tickers: list | None = None,
) -> NewsProcessingState:
    """
    Build a fully-initialized state dict with safe defaults for all agent fields.
    Prevents KeyError inside agent nodes when they read fields written by prior agents.
    """
    return NewsProcessingState(
        # Input
        article_id=article_id,
        headline=headline,
        clean_content=clean_content,
        source=source,
        source_url=source_url,
        published_at=published_at,
        candidate_tickers=candidate_tickers or [],

        # News Analyst defaults
        sentiment_score=0.0,
        sentiment_evidence="",
        event_type="other",
        event_severity="low",
        affected_tickers=[],
        named_entities=[],
        analyst_summary="",
        analyst_completed=False,
        analyst_used_fallback=False,

        # Risk Delta defaults
        affected_users=[],
        portfolio_impacts=[],
        any_users_affected=False,
        risk_delta_completed=False,

        # Advisory defaults
        alerts_generated=[],
        advisory_completed=False,

        # Error tracking
        errors=[],
        processing_stage="initialized",
    )
