"""
app/agents/advisory.py
-----------------------
LangGraph node: Advisory Notification Agent.

Responsibilities:
  1. Call Claude to write clear, non-alarmist alert text for each
     affected user (using ADVISORY_SYSTEM prompt with banned-word rules).
  2. Write NewsAlert + PortfolioImpact rows to Postgres for audit trail
     (satisfies SEC Rule 204-2 recordkeeping for "recommendations made").
  3. Publish alert to Redis pub/sub channel `alerts:{user_id}` so the
     FastAPI WebSocket endpoint can forward it to connected browsers instantly.
"""

import json
import logging
import time
from datetime import datetime, timezone

import anthropic
from sqlalchemy import create_engine, text

from app.agents.prompts import (
    ADVISORY_SYSTEM,
    ADVISORY_USER_TEMPLATE,
    MANDATORY_DISCLAIMER,
)
from app.agents.state import NewsProcessingState
from app.core.config import get_settings
from app.core.redis_client import get_redis_client

logger = logging.getLogger("aureus.agents.advisory")


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


# ── LLM: generate alert text ───────────────────────────────────────────────────

def _generate_alerts_llm(state: NewsProcessingState) -> list[dict]:
    """
    Call Claude to write alert messages for each portfolio impact.
    Returns list of alert dicts ready for dispatch.
    """
    settings = get_settings()

    if not settings.anthropic_configured:
        return _generate_alerts_deterministic(state)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_message = ADVISORY_USER_TEMPLATE.format(
        headline=state["headline"],
        source=state["source"],
        published_at=state["published_at"],
        analyst_summary=state["analyst_summary"],
        sentiment_score=state["sentiment_score"],
        event_type=state["event_type"],
        event_severity=state["event_severity"],
        portfolio_impacts_json=json.dumps(state["portfolio_impacts"], indent=2),
        disclaimer=MANDATORY_DISCLAIMER,
    )

    max_tries  = 3
    base_delay = 5.0

    for attempt in range(max_tries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=ADVISORY_SYSTEM,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            data = json.loads(raw)
            alerts = data.get("alerts", [])
            # Guarantee disclaimer is present in every alert
            for alert in alerts:
                if MANDATORY_DISCLAIMER not in alert.get("message", ""):
                    alert["message"] = alert.get("message", "") + f"\n\n{MANDATORY_DISCLAIMER}"
                alert.setdefault("disclaimer", MANDATORY_DISCLAIMER)
            return alerts
        except anthropic.RateLimitError:
            if attempt == max_tries - 1:
                return _generate_alerts_deterministic(state)
            time.sleep(base_delay * (2 ** attempt))
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Advisory LLM failed", extra={"error": str(exc)})
            return _generate_alerts_deterministic(state)


def _generate_alerts_deterministic(state: NewsProcessingState) -> list[dict]:
    """
    Template-based fallback when LLM is unavailable.
    Generates a factual, compliant alert without LLM involvement.
    """
    alerts = []
    direction = "positively" if state["sentiment_score"] > 0 else "negatively"
    tickers   = ", ".join(state["affected_tickers"])

    for impact in state["portfolio_impacts"]:
        est     = impact.get("impact_estimate", 0.0)
        conf    = impact.get("confidence", 0.5)
        ticker  = impact.get("ticker", tickers)
        weight  = impact.get("holding_weight", 0.0)
        abs_est = abs(est)

        if abs_est < 0.005:
            severity = "low"
        elif abs_est < 0.02:
            severity = "medium"
        elif abs_est < 0.05:
            severity = "high"
        else:
            severity = "critical"

        message = (
            f"News regarding {ticker} may affect your portfolio {direction}. "
            f"Event: {state['event_type'].replace('_', ' ').title()}. "
            f"Summary: {state['analyst_summary'][:200]} "
            f"Estimated portfolio impact: {est*100:+.2f}% "
            f"(based on {weight*100:.1f}% portfolio weight, "
            f"confidence: {conf*100:.0f}%). "
            f"\n\n{MANDATORY_DISCLAIMER}"
        )
        alerts.append({
            "user_id":             impact["user_id"],
            "portfolio_id":        impact["portfolio_id"],
            "headline":            f"Portfolio Alert: {ticker} — {state['event_type'].replace('_', ' ').title()}",
            "message":             message,
            "severity":            severity,
            "requires_human_review": impact.get("requires_human_review", False),
            "disclaimer":          MANDATORY_DISCLAIMER,
        })
    return alerts


# ── Database writes ────────────────────────────────────────────────────────────

def _write_to_database(state: NewsProcessingState, alerts: list[dict]) -> None:
    """
    Write PortfolioImpact rows only.

    news_articles and news_alerts are now written unconditionally by
    news_analyst.py's _write_general_news_record(), regardless of whether
    any portfolio matched — that's the fix for general market news not
    showing up when no user held the affected ticker. This function only
    handles the genuinely user-specific portfolio_impacts table, looking
    up the already-written news_alert row rather than re-inserting it.
    """
    if not alerts:
        return

    engine = _get_engine()

    try:
        with engine.begin() as conn:
            # Look up the article + alert that news_analyst.py already wrote
            row = conn.execute(
                text("SELECT id FROM news_articles WHERE source_url = :url"),
                {"url": state["source_url"]},
            ).fetchone()
            if row is None:
                logger.warning("No news_articles row found — skipping portfolio_impacts", extra={"article_id": state["article_id"]})
                return
            news_article_id = str(row[0])

            alert_row = conn.execute(
                text("SELECT id FROM news_alerts WHERE news_article_id = :aid LIMIT 1"),
                {"aid": news_article_id},
            ).fetchone()
            news_alert_id = str(alert_row[0]) if alert_row else None

            # ── portfolio_impacts ──────────────────────────────────
            for impact in state["portfolio_impacts"]:
                # Find matching alert for severity
                matching_alert = next(
                    (a for a in alerts if a["user_id"] == impact["user_id"]),
                    None,
                )
                conn.execute(
                    text("""
                        INSERT INTO portfolio_impacts
                          (id, news_alert_id, portfolio_id, user_id,
                           beta_volatility_impact, impact_confidence,
                           requires_human_review, notification_status, created_at)
                        VALUES
                          (gen_random_uuid(), :alert_id, :portfolio_id, :user_id,
                           :beta_impact, :confidence,
                           :human_review, 'pending', NOW())
                    """),
                    {
                        "alert_id":    news_alert_id,
                        "portfolio_id": impact["portfolio_id"],
                        "user_id":     impact["user_id"],
                        "beta_impact": impact.get("beta_weighted_exposure", 0.0),
                        "confidence":  impact.get("confidence", 0.5),
                        "human_review": impact.get("requires_human_review", False),
                    },
                )

    except Exception as exc:
        logger.error("Database write failed in advisory agent", extra={"error": str(exc)})
    finally:
        engine.dispose()


# ── Redis pub/sub dispatch ─────────────────────────────────────────────────────

def _dispatch_to_redis(alerts: list[dict]) -> None:
    """
    Publish each alert to the user's Redis pub/sub channel.
    FastAPI WebSocket handler subscribes to `alerts:{user_id}` and
    forwards the JSON payload to the connected browser instantly.
    """
    redis_client = get_redis_client()
    for alert in alerts:
        user_id  = alert.get("user_id")
        if not user_id:
            continue
        channel  = f"alerts:{user_id}"
        payload  = json.dumps({
            **alert,
            "dispatched_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        try:
            redis_client.publish(channel, payload)
            logger.debug("Alert dispatched to Redis", extra={"user_id": user_id, "channel": channel})
        except Exception as exc:
            logger.error(
                "Redis dispatch failed",
                extra={"user_id": user_id, "error": str(exc)},
            )


# ── LangGraph node ─────────────────────────────────────────────────────────────

def advisory_node(state: NewsProcessingState) -> dict:
    """
    LangGraph node function.
    Generates alerts, writes to DB, dispatches via Redis pub/sub.
    """
    article_id = state["article_id"]
    start_time = time.monotonic()

    logger.info(
        "Advisory Notification Agent started",
        extra={
            "article_id":  article_id,
            "impacts":     len(state["portfolio_impacts"]),
        },
    )

    if not state["portfolio_impacts"]:
        return {
            "alerts_generated":  [],
            "advisory_completed": True,
            "processing_stage":  "advisory",
        }

    try:
        alerts  = _generate_alerts_llm(state)
        elapsed = time.monotonic() - start_time

        # Write to database for audit trail
        _write_to_database(state, alerts)

        # Dispatch to Redis for live WebSocket delivery
        _dispatch_to_redis(alerts)

        logger.info(
            "Advisory Notification Agent complete",
            extra={
                "article_id":      article_id,
                "alerts_generated": len(alerts),
                "elapsed_seconds": round(elapsed, 2),
            },
        )

        return {
            "alerts_generated":  alerts,
            "advisory_completed": True,
            "processing_stage":  "advisory",
        }

    except Exception as exc:
        error_msg = f"advisory: failed for {article_id}: {exc}"
        logger.error(error_msg, exc_info=True)
        return {
            "alerts_generated":  [],
            "advisory_completed": True,
            "errors":            state["errors"] + [error_msg],
            "processing_stage":  "advisory",
        }
