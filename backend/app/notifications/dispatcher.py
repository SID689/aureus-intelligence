"""
app/notifications/dispatcher.py
--------------------------------
Alert dispatcher called by the advisory agent after generating alert payloads.

The dispatcher handles the routing decision:
  - User is connected via WebSocket → immediate push via ConnectionManager
  - User is offline → alert sits in portfolio_impacts with status='pending'
    and will be delivered on next login (polling endpoint in api/v1/ws.py)

Also updates the `notification_status` column in portfolio_impacts after
delivery so the Phase 1 schema's audit trail stays current.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.redis_client import get_redis_client

logger = logging.getLogger("aureus.notifications.dispatcher")


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def publish_alert_to_redis(user_id: str, alert_payload: dict[str, Any]) -> None:
    """
    Publish an alert to the Redis channel for this user.
    The WebSocket listener task picks it up and pushes it to the browser.
    This is the synchronous version called from Celery workers.
    """
    channel = f"alerts:{user_id}"
    payload = json.dumps({
        **alert_payload,
        "dispatched_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    try:
        get_redis_client().publish(channel, payload)
        logger.debug("Alert published to Redis channel", extra={"channel": channel})
    except Exception as exc:
        logger.error(
            "Redis publish failed",
            extra={"user_id": user_id, "error": str(exc)},
        )


def update_delivery_status(
    portfolio_id: str,
    user_id: str,
    status: str = "delivered",
) -> None:
    """
    Update notification_status in portfolio_impacts after delivery.
    Called after a successful Redis publish.
    """
    engine = _get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE portfolio_impacts
                    SET notification_status = :status,
                        notified_at = NOW()
                    WHERE portfolio_id = :portfolio_id
                      AND user_id = :user_id
                      AND notification_status = 'pending'
                """),
                {
                    "status":       status,
                    "portfolio_id": portfolio_id,
                    "user_id":      user_id,
                },
            )
    except Exception as exc:
        logger.error(
            "Failed to update delivery status",
            extra={"user_id": user_id, "portfolio_id": portfolio_id, "error": str(exc)},
        )
    finally:
        engine.dispose()


def get_pending_alerts(user_id: str) -> list[dict]:
    """
    Fetch undelivered alerts for a user.
    Called on WebSocket connect so users receive alerts they missed while offline.
    """
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        pi.id,
                        pi.portfolio_id,
                        na.ticker,
                        na.sentiment_score,
                        na.summary,
                        pi.beta_volatility_impact,
                        pi.impact_confidence,
                        pi.requires_human_review,
                        pi.notification_status,
                        pi.created_at,
                        art.headline,
                        art.source,
                        art.source_url,
                        art.published_at
                    FROM portfolio_impacts pi
                    JOIN news_alerts na   ON pi.news_alert_id = na.id
                    JOIN news_articles art ON na.news_article_id = art.id
                    WHERE pi.user_id = :user_id
                      AND pi.notification_status = 'pending'
                    ORDER BY pi.created_at DESC
                    LIMIT 50
                """),
                {"user_id": user_id},
            ).fetchall()

        return [
            {
                "id":                    str(row.id),
                "portfolio_id":          str(row.portfolio_id),
                "ticker":                row.ticker,
                "sentiment_score":       float(row.sentiment_score),
                "summary":               row.summary,
                "beta_volatility_impact": float(row.beta_volatility_impact),
                "impact_confidence":     float(row.impact_confidence),
                "requires_human_review": row.requires_human_review,
                "headline":              row.headline,
                "source":                row.source,
                "source_url":            row.source_url,
                "published_at":          row.published_at.isoformat() if row.published_at else None,
                "created_at":            row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    except Exception as exc:
        logger.error("Failed to fetch pending alerts", extra={"user_id": user_id, "error": str(exc)})
        return []
    finally:
        engine.dispose()
