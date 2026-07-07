"""
app/agents/news_analyst.py
---------------------------
LangGraph node: News Analyst Agent.

Calls Claude to extract named entities, compute sentiment polarity,
classify the event type/severity, and produce a factual summary.
All output is structured JSON, parsed and validated before being
written back to state.

Error handling strategy:
  - LLM call failure → log error, write to state["errors"], return
    neutral defaults so the graph can continue to risk_delta (which
    will find no affected users and short-circuit gracefully).
  - JSON parse failure → same strategy; a broken LLM response should
    never kill the entire pipeline.
"""

import json
import logging
import time

import anthropic

from app.agents.prompts import NEWS_ANALYST_SYSTEM, NEWS_ANALYST_USER_TEMPLATE
from app.agents.state import NewsProcessingState
from app.core.config import get_settings

logger = logging.getLogger("aureus.agents.news_analyst")

_VALID_EVENT_TYPES = {
    "earnings", "merger_acquisition", "regulatory", "product_launch",
    "macro", "management", "legal", "analyst_rating", "other",
}
_VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def _get_client() -> anthropic.Anthropic:
    settings = get_settings()
    if not settings.anthropic_configured:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. "
            "Set it in .env to enable the agent pipeline."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _call_llm(user_message: str) -> str:
    """
    Call Claude with exponential backoff on rate-limit errors.
    Returns the raw text response.
    """
    client    = _get_client()
    max_tries = 3
    base_delay = 5.0

    for attempt in range(max_tries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=NEWS_ANALYST_SYSTEM,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text
        except anthropic.RateLimitError as exc:
            if attempt == max_tries - 1:
                raise
            sleep_time = base_delay * (2 ** attempt)
            logger.warning(
                "Anthropic rate limit — backing off",
                extra={"attempt": attempt + 1, "sleep_seconds": sleep_time},
            )
            time.sleep(sleep_time)
        except anthropic.APIError as exc:
            logger.error("Anthropic API error", extra={"error": str(exc)})
            raise


def _parse_and_validate(raw_json: str, article_id: str) -> dict:
    """
    Parse the LLM JSON response and apply validation/clamping.
    Returns a dict with safe defaults for any missing or invalid fields.
    """
    # Strip markdown fences if the model included them despite instructions
    cleaned = raw_json.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(
            "JSON parse failed on analyst response",
            extra={"article_id": article_id, "error": str(exc), "raw": raw_json[:300]},
        )
        return {}

    # Clamp sentiment score
    score = data.get("sentiment_score", 0.0)
    try:
        score = max(-1.0, min(1.0, float(score)))
    except (TypeError, ValueError):
        score = 0.0

    event_type = data.get("event_type", "other")
    if event_type not in _VALID_EVENT_TYPES:
        event_type = "other"

    severity = data.get("event_severity", "low")
    if severity not in _VALID_SEVERITIES:
        severity = "low"

    tickers = data.get("affected_tickers", [])
    if not isinstance(tickers, list):
        tickers = []
    # Sanitize: uppercase, strip $, max 10 tickers
    tickers = [str(t).upper().lstrip("$") for t in tickers if t][:10]

    entities = data.get("named_entities", [])
    if not isinstance(entities, list):
        entities = []

    return {
        "sentiment_score":    score,
        "sentiment_evidence": str(data.get("sentiment_evidence", ""))[:500],
        "event_type":         event_type,
        "event_severity":     severity,
        "affected_tickers":   tickers,
        "named_entities":     entities,
        "analyst_summary":    str(data.get("analyst_summary", ""))[:1000],
    }


# ── LangGraph node ─────────────────────────────────────────────────────────────

def news_analyst_node(state: NewsProcessingState) -> dict:
    """
    LangGraph node function.
    Reads input fields from state, calls Claude, writes analyst output back.
    Always returns a dict — LangGraph merges it into the state.
    """
    article_id = state["article_id"]
    start_time = time.monotonic()

    logger.info(
        "News Analyst Agent started",
        extra={"article_id": article_id, "headline": state["headline"][:60]},
    )

    user_message = NEWS_ANALYST_USER_TEMPLATE.format(
        source=state["source"],
        source_url=state["source_url"],
        published_at=state["published_at"],
        headline=state["headline"],
        clean_content=state["clean_content"][:3000],  # fit within context window
        candidate_tickers=", ".join(state["candidate_tickers"]) or "none detected",
    )

    try:
        raw_response = _call_llm(user_message)
        parsed       = _parse_and_validate(raw_response, article_id)
        elapsed      = time.monotonic() - start_time

        if not parsed:
            # JSON parse failed — neutral defaults, mark completed with warning
            errors = state["errors"] + [f"analyst: JSON parse failed for {article_id}"]
            logger.warning("Analyst returning neutral defaults due to parse failure")
            return {
                "sentiment_score":   0.0,
                "sentiment_evidence": "",
                "event_type":        "other",
                "event_severity":    "low",
                "affected_tickers":  state["candidate_tickers"],  # fall back to preprocessor
                "named_entities":    [],
                "analyst_summary":   state["headline"],
                "analyst_completed": True,
                "errors":            errors,
                "processing_stage":  "news_analyst",
            }

        logger.info(
            "News Analyst Agent complete",
            extra={
                "article_id":     article_id,
                "sentiment":      parsed["sentiment_score"],
                "event_type":     parsed["event_type"],
                "severity":       parsed["event_severity"],
                "tickers":        parsed["affected_tickers"],
                "elapsed_seconds": round(elapsed, 2),
            },
        )

        return {
            **parsed,
            "analyst_completed": True,
            "processing_stage":  "news_analyst",
        }

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        error_msg = f"analyst: LLM call failed for {article_id}: {exc}"
        logger.error(error_msg, extra={"elapsed_seconds": round(elapsed, 2)}, exc_info=True)

        return {
            "sentiment_score":   0.0,
            "sentiment_evidence": "",
            "event_type":        "other",
            "event_severity":    "low",
            "affected_tickers":  state["candidate_tickers"],
            "named_entities":    [],
            "analyst_summary":   state["headline"],
            "analyst_completed": True,
            "errors":            state["errors"] + [error_msg],
            "processing_stage":  "news_analyst",
        }
