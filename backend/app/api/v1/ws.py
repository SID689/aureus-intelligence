"""
app/api/v1/ws.py
-----------------
WebSocket endpoint for real-time portfolio impact alerts.

GET  /api/v1/alerts/pending/{user_id}
  REST endpoint to fetch undelivered alerts for users who were offline.
  Called immediately on page load before the WebSocket connects.

WS   /api/v1/ws/alerts/{user_id}
  WebSocket endpoint. On connect:
    1. Sends any pending (undelivered) alerts accumulated while offline.
    2. Subscribes to Redis pub/sub for live alerts from the agent pipeline.
    3. Keeps connection alive with a periodic ping.

Note: In production, user_id should be extracted from a verified JWT,
not passed as a path parameter. Path-param style is used here for
Phase 3 development simplicity — auth middleware is Phase 4 scope.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.notifications.dispatcher import get_pending_alerts, update_delivery_status
from app.notifications.websocket_manager import manager

logger = logging.getLogger("aureus.api.ws")

router = APIRouter(prefix="/api/v1", tags=["realtime"])

# How often to send a WebSocket ping to keep the connection alive (seconds)
_PING_INTERVAL = 25


# ── REST: pending alerts ───────────────────────────────────────────────────────

class PendingAlertsResponse(BaseModel):
    user_id: str
    count: int
    alerts: list[dict[str, Any]]


@router.get("/alerts/pending/{user_id}", response_model=PendingAlertsResponse)
def get_pending_alerts_endpoint(user_id: str) -> PendingAlertsResponse:
    """
    Return all undelivered portfolio impact alerts for a user.
    Call this on page load, before the WebSocket connects, to catch
    alerts generated while the user was offline.
    """
    alerts = get_pending_alerts(user_id)

    # Mark as delivered now that we're serving them via REST
    for alert in alerts:
        update_delivery_status(
            portfolio_id=alert["portfolio_id"],
            user_id=user_id,
            status="delivered",
        )

    return PendingAlertsResponse(
        user_id=user_id,
        count=len(alerts),
        alerts=alerts,
    )


# ── WebSocket: live alerts ─────────────────────────────────────────────────────

@router.websocket("/ws/alerts/{user_id}")
async def alerts_websocket(websocket: WebSocket, user_id: str) -> None:
    """
    WebSocket endpoint for real-time alert delivery.

    Message types sent to client:
      {"type": "connected", ...}           — on successful connection
      {"type": "alert", ...}               — live alert from agent pipeline
      {"type": "pending_alerts", ...}      — backlog of offline alerts
      {"type": "ping"}                     — keepalive
      {"type": "error", "message": "..."}  — error notification
    """
    await manager.connect(websocket, user_id)

    try:
        # Immediately flush any alerts accumulated while offline
        pending = get_pending_alerts(user_id)
        if pending:
            await websocket.send_json({
                "type":   "pending_alerts",
                "count":  len(pending),
                "alerts": pending,
            })
            # Mark them delivered
            for alert in pending:
                update_delivery_status(
                    portfolio_id=alert["portfolio_id"],
                    user_id=user_id,
                    status="delivered",
                )
            logger.info(
                "Flushed pending alerts on connect",
                extra={"user_id": user_id, "count": len(pending)},
            )

        # Keep connection alive with periodic pings.
        # The Redis listener runs as a background task (started in manager.connect).
        # We just need to stay here to keep the WebSocket open.
        while True:
            await asyncio.sleep(_PING_INTERVAL)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break  # client disconnected

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", extra={"user_id": user_id})
    except Exception as exc:
        logger.error(
            "WebSocket handler error",
            extra={"user_id": user_id, "error": str(exc)},
            exc_info=True,
        )
    finally:
        manager.disconnect(user_id)


# ── WebSocket health ───────────────────────────────────────────────────────────

@router.get("/ws/status")
def websocket_status() -> dict:
    """Return number of active WebSocket connections (ops/monitoring endpoint)."""
    return {
        "active_connections": manager.connection_count,
        "connected_users":    manager.connected_user_ids,
    }
