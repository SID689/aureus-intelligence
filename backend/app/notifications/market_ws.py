"""
app/notifications/market_ws.py
--------------------------------
Live delivery of Strong Buy alerts to open browser sessions.

Differs from websocket_manager.py (portfolio alerts) in two ways that
matter here:

  * Many sockets per user. The existing manager keeps one and replaces it,
    so a second tab silently disconnects the first — fine for its purpose,
    wrong for an alert someone is paying to see wherever they are looking.
  * One Redis subscription per PROCESS, not per user. A pattern
    subscription fans in every user's channel and dispatches to local
    sockets, so a thousand connected users cost one Redis connection, not
    a thousand.
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.core.config import get_settings
from app.notifications import market_alerts

logger = logging.getLogger("aureus.notifications.market_ws")


class MarketAlertHub:
    def __init__(self) -> None:
        self._sockets: dict[str, set[WebSocket]] = {}
        self._listener: asyncio.Task | None = None

    @property
    def connection_count(self) -> int:
        return sum(len(s) for s in self._sockets.values())

    async def register(self, user_id: str, ws: WebSocket) -> None:
        self._sockets.setdefault(user_id, set()).add(ws)
        await asyncio.to_thread(market_alerts.touch_presence, user_id)
        if self._listener is None or self._listener.done():
            self._listener = asyncio.create_task(self._listen(), name="market-alert-hub")

    async def unregister(self, user_id: str, ws: WebSocket) -> None:
        socks = self._sockets.get(user_id)
        if socks is None:
            return
        socks.discard(ws)
        if not socks:
            self._sockets.pop(user_id, None)
            # Only this process's view. Another process holding a socket for
            # the same user re-asserts presence within one ping interval,
            # and the second delivery pass covers the gap.
            await asyncio.to_thread(market_alerts.clear_presence, user_id)

    async def _listen(self) -> None:
        backoff = 1.0
        while True:
            try:
                async with aioredis.from_url(get_settings().redis_url, decode_responses=True,
                                             socket_connect_timeout=5) as client:
                    pubsub = client.pubsub()
                    await pubsub.psubscribe(f"{market_alerts.CHANNEL_PREFIX}*")
                    backoff = 1.0
                    async for message in pubsub.listen():
                        if message.get("type") != "pmessage":
                            continue
                        user_id = message["channel"][len(market_alerts.CHANNEL_PREFIX):]
                        await self._dispatch(user_id, message["data"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("Market alert listener dropped; reconnecting", extra={"error": str(exc)})
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2)

    async def _dispatch(self, user_id: str, raw: str) -> None:
        socks = list(self._sockets.get(user_id, ()))
        if not socks:
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return
        delivered = False
        for ws in socks:
            try:
                await ws.send_json({"type": "market_alert", **payload})
                delivered = True
            except Exception:  # noqa: BLE001 — a dead socket; its handler will unregister it
                self._sockets.get(user_id, set()).discard(ws)
        if delivered and payload.get("notification_id"):
            try:
                await asyncio.to_thread(market_alerts.mark_ws_delivered, payload["notification_id"], user_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not confirm socket delivery", extra={"error": str(exc)})


hub = MarketAlertHub()
