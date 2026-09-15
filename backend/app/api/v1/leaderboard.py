"""
app/api/v1/leaderboard.py
---------------------------
The Hottest Stocks Leaderboard, Strong Buy notifications and push
subscriptions. Elite and Institutional only.

AUTH
Every route takes a signed realtime token (core/realtime_auth.py), never a
`user_id` parameter. Entitlement is then resolved from the database on
each call, so a downgrade takes effect on the next request rather than
when a token or session happens to expire.

GET    /api/v1/leaderboard                  board + candidates for a horizon
GET    /api/v1/leaderboard/access           does the caller's plan include it (not gated)
GET    /api/v1/leaderboard/events           recent entries and exits
GET    /api/v1/scanner/status               recent runs, coverage, budget, rules
GET    /api/v1/notifications                alert history
POST   /api/v1/notifications/read           mark some or all read
GET    /api/v1/push/vapid-public-key        the application server key (not gated)
POST   /api/v1/push/subscriptions           register this browser
DELETE /api/v1/push/subscriptions           unregister it
POST   /api/v1/push/test                    send a test notification to my devices
WS     /api/v1/ws/market?token=...          live alerts
"""

import asyncio
import logging
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.entitlements import feature_error, resolve_entitlements
from app.core.realtime_auth import RealtimeAuthError, realtime_user, verify_token
from app.ingestion.rate_limiter import RedisTokenBucket
from app.notifications import market_alerts, push
from app.notifications.market_ws import hub
from app.scanner import leaderboard

logger = logging.getLogger("aureus.api.leaderboard")

router = APIRouter(prefix="/api/v1", tags=["leaderboard"])

Horizon = Literal["short_term", "medium_term", "long_term"]

_PING_SECONDS = 25
_ENTITLEMENT_RECHECK_SECONDS = 300


def premium_user(user_id: str = Depends(realtime_user)) -> str:
    ent = resolve_entitlements(user_id)
    if not ent.leaderboard_enabled:
        raise feature_error("The Hottest Stocks Leaderboard", "elite", ent)
    return user_id


# ── Board ─────────────────────────────────────────────────────────────────

@router.get("/leaderboard/access")
def leaderboard_access(user_id: str = Depends(realtime_user)) -> dict:
    ent = resolve_entitlements(user_id)
    return {"enabled": ent.leaderboard_enabled, "tier": ent.tier, "plan": ent.display_name}


@router.get("/leaderboard")
def get_leaderboard(horizon: Horizon = Query(default="medium_term"), _: str = Depends(premium_user)) -> dict:
    return leaderboard.cached_board(horizon)


@router.get("/leaderboard/events")
def leaderboard_events(
    horizon: Horizon | None = Query(default=None),
    limit: int = Query(default=40, ge=1, le=200),
    _: str = Depends(premium_user),
) -> dict:
    return {"events": leaderboard.recent_events(horizon, limit)}


@router.get("/scanner/status")
def get_scanner_status(_: str = Depends(premium_user)) -> dict:
    return leaderboard.scanner_status()


# ── Notification history ──────────────────────────────────────────────────

class MarkRead(BaseModel):
    ids: list[str] | None = Field(default=None, max_length=200)
    all: bool = False


@router.get("/notifications")
def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    before: str | None = Query(default=None, max_length=40),
    user_id: str = Depends(premium_user),
) -> dict:
    return market_alerts.feed(user_id, limit, before)


@router.post("/notifications/read")
def read_notifications(body: MarkRead, user_id: str = Depends(premium_user)) -> dict:
    try:
        updated = market_alerts.mark_read(user_id, body.ids, body.all)
    except Exception as exc:  # noqa: BLE001 — a malformed id is a client error, not a 500
        raise HTTPException(status_code=422, detail="Invalid notification id") from exc
    return {"updated": updated, "unread": market_alerts.unread_count(user_id)}


# ── Web Push ──────────────────────────────────────────────────────────────

class PushKeys(BaseModel):
    p256dh: str = Field(min_length=40, max_length=200)
    auth: str = Field(min_length=12, max_length=64)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=1000)
    keys: PushKeys
    user_agent: str | None = Field(default=None, max_length=300)


class PushSubscriptionOut(BaseModel):
    endpoint: str = Field(min_length=20, max_length=1000)


@router.get("/push/vapid-public-key")
def vapid_public_key() -> dict:
    s = get_settings()
    return {"key": s.vapid_public_key or None, "configured": push.configured()}


@router.post("/push/subscriptions", status_code=201)
def create_push_subscription(body: PushSubscriptionIn, user_id: str = Depends(premium_user)) -> dict:
    if not push.endpoint_allowed(body.endpoint):
        raise HTTPException(status_code=422, detail="Push endpoint is not a recognised browser push service")
    push.subscribe(user_id, body.endpoint, body.keys.p256dh, body.keys.auth, body.user_agent)
    return {"subscribed": True, "devices": push.subscription_count(user_id)}


@router.delete("/push/subscriptions")
def delete_push_subscription(body: PushSubscriptionOut, user_id: str = Depends(realtime_user)) -> dict:
    # Deliberately NOT premium-gated: a user who downgraded must still be
    # able to switch notifications off.
    return {"removed": push.unsubscribe(user_id, body.endpoint), "devices": push.subscription_count(user_id)}


@router.post("/push/test")
def test_push(user_id: str = Depends(premium_user)) -> dict:
    if not RedisTokenBucket(f"push_test:{user_id}", max_calls=5, window_seconds=3600).allow():
        raise HTTPException(status_code=429, detail="Test notifications are limited to five an hour")
    return push.send_test(user_id)


# ── Live socket ───────────────────────────────────────────────────────────

async def _drain(ws: WebSocket) -> None:
    """Read until the client goes away. Client messages carry nothing we act on."""
    while True:
        await ws.receive_text()


@router.websocket("/ws/market")
async def market_socket(websocket: WebSocket, token: str = Query(default="", max_length=2000)) -> None:
    """
    The token travels in the query string because browsers cannot set
    headers on a WebSocket handshake. It lives five minutes and only opens
    the socket, which limits what a copy of it in an access log is worth.

    Failures accept and then close with an application code (4401, 4403),
    because a rejected handshake reaches browser code as an anonymous 1006
    and the client could not tell "sign in again" from "network down".
    """
    try:
        user_id = verify_token(token)
    except RealtimeAuthError:
        await websocket.accept()
        await websocket.close(code=4401, reason="invalid or expired token")
        return

    ent = await asyncio.to_thread(resolve_entitlements, user_id)
    if not ent.leaderboard_enabled:
        await websocket.accept()
        await websocket.close(code=4403, reason="plan does not include market alerts")
        return

    await websocket.accept()
    await hub.register(user_id, websocket)
    receiver: asyncio.Task | None = None
    try:
        unread = await asyncio.to_thread(market_alerts.unread_count, user_id)
        await websocket.send_json({"type": "connected", "unread": unread})
        receiver = asyncio.create_task(_drain(websocket))
        last_check = time.monotonic()
        while True:
            done, _ = await asyncio.wait({receiver}, timeout=_PING_SECONDS)
            if receiver in done:
                break
            await websocket.send_json({"type": "ping"})
            await asyncio.to_thread(market_alerts.touch_presence, user_id)
            if time.monotonic() - last_check >= _ENTITLEMENT_RECHECK_SECONDS:
                last_check = time.monotonic()
                ent = await asyncio.to_thread(resolve_entitlements, user_id)
                if not ent.leaderboard_enabled:
                    await websocket.close(code=4403, reason="plan no longer includes market alerts")
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.info("Market socket closed with error", extra={"error": str(exc)})
    finally:
        if receiver is not None:
            receiver.cancel()
        await hub.unregister(user_id, websocket)
