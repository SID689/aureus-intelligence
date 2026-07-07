"""
app/agents/graph.py
--------------------
Assembles the LangGraph state machine connecting the three agent nodes.

Graph topology:
  START
    │
    ▼
  news_analyst           ← extracts sentiment, tickers, event type
    │
    ▼
  risk_delta             ← queries DB, calculates portfolio impacts
    │
    ├── any_users_affected=False ──► END   (no one holds the ticker)
    │
    ▼
  advisory               ← generates alerts, writes DB, dispatches Redis
    │
    ▼
  END

The conditional edge after risk_delta is the key cost-saving optimization:
the majority of news articles affect tickers no user holds, so the advisory
LLM call (the most expensive in the pipeline) is skipped for most articles.

Usage:
    from app.agents.graph import news_pipeline
    from app.agents.state import make_initial_state

    state = make_initial_state(
        article_id="abc123",
        headline="Apple Reports Record Q4 Earnings",
        clean_content="Apple Inc. today reported...",
        source="Reuters",
        source_url="https://...",
        published_at="2024-11-01T21:00:00Z",
        candidate_tickers=["AAPL"],
    )
    result = news_pipeline.invoke(state)
    # result is the final NewsProcessingState with all fields populated
"""

import logging

from langgraph.graph import END, StateGraph

from app.agents.advisory import advisory_node
from app.agents.news_analyst import news_analyst_node
from app.agents.risk_delta import risk_delta_node
from app.agents.state import NewsProcessingState

logger = logging.getLogger("aureus.agents.graph")


# ── Conditional routing ────────────────────────────────────────────────────────

def _route_after_risk_delta(state: NewsProcessingState) -> str:
    """
    After risk_delta runs, decide whether to generate alerts.
    Skip advisory entirely if no users hold the affected tickers —
    this is the common case for most news articles.
    """
    if state.get("any_users_affected", False):
        return "advisory"
    logger.debug(
        "No users affected — skipping advisory",
        extra={"article_id": state.get("article_id")},
    )
    return END


def _route_after_analyst(state: NewsProcessingState) -> str:
    """
    After analyst runs, skip risk_delta if sentiment is essentially neutral
    (|score| < 0.05 means VADER let it through but LLM confirmed it's neutral).
    """
    score = abs(state.get("sentiment_score", 0.0))
    if score < 0.05:
        logger.debug(
            "LLM confirmed neutral sentiment — short-circuiting",
            extra={"article_id": state.get("article_id"), "score": score},
        )
        return END
    return "risk_delta"


# ── Graph construction ─────────────────────────────────────────────────────────

def build_news_pipeline() -> StateGraph:
    """
    Build and compile the LangGraph state machine.
    Called once at module import time — the compiled graph is reused
    across all Celery task invocations (thread-safe, stateless).
    """
    builder = StateGraph(NewsProcessingState)

    # Register nodes
    builder.add_node("news_analyst", news_analyst_node)
    builder.add_node("risk_delta",   risk_delta_node)
    builder.add_node("advisory",     advisory_node)

    # Entry point
    builder.set_entry_point("news_analyst")

    # news_analyst → risk_delta OR END (if LLM confirmed neutral)
    builder.add_conditional_edges(
        "news_analyst",
        _route_after_analyst,
        {
            "risk_delta": "risk_delta",
            END:          END,
        },
    )

    # risk_delta → advisory OR END (if no users hold the ticker)
    builder.add_conditional_edges(
        "risk_delta",
        _route_after_risk_delta,
        {
            "advisory": "advisory",
            END:        END,
        },
    )

    # advisory always terminates
    builder.add_edge("advisory", END)

    return builder.compile()


# Module-level compiled graph — import this in Celery tasks
news_pipeline = build_news_pipeline()
logger.info("LangGraph news pipeline compiled successfully")
