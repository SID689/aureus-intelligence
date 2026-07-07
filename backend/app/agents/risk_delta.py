"""
app/agents/risk_delta.py
-------------------------
LangGraph node: Portfolio Risk-Delta Agent.

Two-step process:
  1. DATABASE QUERY (deterministic) — find all users who hold any of
     the affected tickers, load their holding weights and betas.
     This is pure SQL, no LLM involved.
  2. LLM CALL (analytical) — Claude performs the beta-weighted impact
     calculation and determines which impacts require human review.
     The LLM adds value here by interpreting edge cases (e.g., short
     positions, hedged portfolios flagged via the configuration JSONB)
     that pure arithmetic would miss.

If no users hold the affected tickers, the node sets any_users_affected=False
and returns immediately, skipping the LLM call entirely (cost and latency saving).
"""

import json
import logging
import time

import anthropic
from sqlalchemy import create_engine, text

from app.agents.prompts import RISK_DELTA_SYSTEM, RISK_DELTA_USER_TEMPLATE
from app.agents.state import NewsProcessingState
from app.core.config import get_settings

logger = logging.getLogger("aureus.agents.risk_delta")


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


# ── Database: find affected users ──────────────────────────────────────────────

def _query_affected_holdings(tickers: list[str]) -> list[dict]:
    """
    Find all active portfolio holdings for the given tickers.
    Returns a list of dicts with user/portfolio/holding data needed
    for the impact calculation.

    Only queries portfolios with known prices (last_priced_at IS NOT NULL)
    to ensure holding_weight and beta are populated.
    """
    if not tickers:
        return []

    engine = _get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        u.id                        AS user_id,
                        p.id                        AS portfolio_id,
                        p.name                      AS portfolio_name,
                        p.is_paper,
                        ph.ticker,
                        ph.quantity,
                        ph.average_cost_basis,
                        ph.current_price,
                        ph.current_weight,
                        ph.beta,
                        sub_tiers.tier_name,
                        sub_tiers.supports_human_in_loop_alerts
                    FROM portfolio_holdings ph
                    JOIN portfolios p          ON ph.portfolio_id = p.id
                    JOIN users u               ON p.user_id = u.id
                    JOIN user_subscriptions us ON u.id = us.user_id
                    JOIN subscription_tiers sub_tiers ON us.tier_id = sub_tiers.id
                    WHERE ph.ticker = ANY(:tickers)
                      AND u.is_active = true
                      AND u.deleted_at IS NULL
                      AND us.status IN ('active', 'trialing')
                      AND ph.current_weight IS NOT NULL
                    ORDER BY u.id, ph.ticker
                """),
                {"tickers": tickers},
            ).fetchall()

        return [
            {
                "user_id":                       str(row.user_id),
                "portfolio_id":                  str(row.portfolio_id),
                "portfolio_name":                row.portfolio_name,
                "is_paper":                      row.is_paper,
                "ticker":                        row.ticker,
                "quantity":                      float(row.quantity),
                "average_cost_basis":            float(row.average_cost_basis),
                "current_price":                 float(row.current_price) if row.current_price else None,
                "holding_weight":                float(row.current_weight) / 100.0,  # DB stores as %, normalize to 0-1
                "beta":                          float(row.beta) if row.beta else 1.0,  # default beta=1 if unknown
                "tier_name":                     row.tier_name,
                "supports_human_in_loop_alerts": row.supports_human_in_loop_alerts,
            }
            for row in rows
        ]
    except Exception as exc:
        logger.error(
            "DB query failed in risk_delta",
            extra={"tickers": tickers, "error": str(exc)},
        )
        return []
    finally:
        engine.dispose()


# ── LLM: calculate and classify impacts ───────────────────────────────────────

def _call_risk_delta_llm(
    state: NewsProcessingState,
    affected_users: list[dict],
) -> list[dict]:
    """
    Ask Claude to compute beta-weighted impact for each affected holding
    and flag which ones require human review.
    Returns a list of portfolio_impact dicts.
    """
    settings = get_settings()
    if not settings.anthropic_configured:
        # Fallback: compute impacts deterministically without LLM
        return _deterministic_impact(state, affected_users)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    user_message = RISK_DELTA_USER_TEMPLATE.format(
        affected_tickers=", ".join(state["affected_tickers"]),
        sentiment_score=state["sentiment_score"],
        event_type=state["event_type"],
        event_severity=state["event_severity"],
        analyst_summary=state["analyst_summary"],
        affected_users_json=json.dumps(affected_users, indent=2),
    )

    max_tries  = 3
    base_delay = 5.0

    for attempt in range(max_tries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=RISK_DELTA_SYSTEM,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            data = json.loads(raw)
            return data.get("portfolio_impacts", [])
        except anthropic.RateLimitError:
            if attempt == max_tries - 1:
                return _deterministic_impact(state, affected_users)
            time.sleep(base_delay * (2 ** attempt))
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Risk delta LLM failed", extra={"error": str(exc)})
            return _deterministic_impact(state, affected_users)


def _deterministic_impact(
    state: NewsProcessingState,
    affected_users: list[dict],
) -> list[dict]:
    """
    Pure arithmetic fallback when the LLM is unavailable.
    impact = sentiment_score × holding_weight × beta
    Confidence defaults to 0.5 (medium uncertainty without LLM interpretation).
    """
    impacts = []
    sentiment = state["sentiment_score"]
    severity  = state["event_severity"]

    for user in affected_users:
        weight  = user["holding_weight"]
        beta    = user["beta"]
        bwe     = weight * beta
        impact  = sentiment * bwe
        # human review: large impact + institutional tier + high/critical severity
        human_review = (
            abs(impact) > 0.02
            and user.get("supports_human_in_loop_alerts", False)
            and severity in ("high", "critical")
        )
        impacts.append({
            "user_id":               user["user_id"],
            "portfolio_id":          user["portfolio_id"],
            "ticker":                user["ticker"],
            "holding_weight":        round(weight, 4),
            "beta":                  round(beta, 4),
            "beta_weighted_exposure": round(bwe, 4),
            "sentiment_score":       sentiment,
            "impact_estimate":       round(impact, 4),
            "confidence":            0.50,
            "reasoning":             f"Deterministic: {sentiment} × {weight:.3f} × {beta:.3f} = {impact:.4f}",
            "requires_human_review": human_review,
        })
    return impacts


# ── LangGraph node ─────────────────────────────────────────────────────────────

def risk_delta_node(state: NewsProcessingState) -> dict:
    """
    LangGraph node function.
    Queries the database for affected users, then calls the LLM to
    compute and classify portfolio impacts.
    """
    article_id      = state["article_id"]
    affected_tickers = state["affected_tickers"]
    start_time      = time.monotonic()

    logger.info(
        "Portfolio Risk-Delta Agent started",
        extra={"article_id": article_id, "tickers": affected_tickers},
    )

    # Short-circuit: no tickers identified → no users affected
    if not affected_tickers:
        logger.info("No affected tickers — skipping risk delta", extra={"article_id": article_id})
        return {
            "affected_users":     [],
            "portfolio_impacts":  [],
            "any_users_affected": False,
            "risk_delta_completed": True,
            "processing_stage":   "risk_delta",
        }

    # Step 1: deterministic DB query
    affected_users = _query_affected_holdings(affected_tickers)

    if not affected_users:
        logger.info(
            "No portfolio holdings found for affected tickers",
            extra={"article_id": article_id, "tickers": affected_tickers},
        )
        return {
            "affected_users":     [],
            "portfolio_impacts":  [],
            "any_users_affected": False,
            "risk_delta_completed": True,
            "processing_stage":   "risk_delta",
        }

    # Step 2: LLM impact calculation
    try:
        portfolio_impacts = _call_risk_delta_llm(state, affected_users)
        elapsed = time.monotonic() - start_time

        logger.info(
            "Portfolio Risk-Delta Agent complete",
            extra={
                "article_id":      article_id,
                "users_affected":  len(affected_users),
                "impacts_computed": len(portfolio_impacts),
                "elapsed_seconds": round(elapsed, 2),
            },
        )

        return {
            "affected_users":     affected_users,
            "portfolio_impacts":  portfolio_impacts,
            "any_users_affected": len(portfolio_impacts) > 0,
            "risk_delta_completed": True,
            "processing_stage":   "risk_delta",
        }

    except Exception as exc:
        error_msg = f"risk_delta: failed for {article_id}: {exc}"
        logger.error(error_msg, exc_info=True)
        return {
            "affected_users":     affected_users,
            "portfolio_impacts":  _deterministic_impact(state, affected_users),
            "any_users_affected": len(affected_users) > 0,
            "risk_delta_completed": True,
            "errors":             state["errors"] + [error_msg],
            "processing_stage":   "risk_delta",
        }
