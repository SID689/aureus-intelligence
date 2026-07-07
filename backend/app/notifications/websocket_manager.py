"""
app/notifications/websocket_manager.py
---------------------------------------
Manages active WebSocket connections and bridges Redis pub/sub → browser.

Architecture:
  - Each connected user has one WebSocket connection tracked in `_connections`.
  - A background asyncio task subscribes to `alerts:{user_id}` in Redis
    and forwards any published message to the user's WebSocket.
  - When the user disconnects, the task is cancelled and the connection removed.

Thread safety: FastAPI WebSocket handlers run in asyncio event loop.
The Celery advisory agent publishes to Redis synchronously — this is fine
because Redis pub/sub is async at the client level, not the publisher level.
"""

import asyncio
import json
import logging
from typing import Any

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.core.config import get_settings

logger = logging.getLogger("aureus.notifications.ws_manager")


class ConnectionManager:
    """
    Tracks active WebSocket connections per user_id.
    One user_id can have at most one active connection (last-one-wins policy).
    """

    def __init__(self) -> None:
        # user_id → WebSocket
        self._connections: dict[str, WebSocket] = {}
        # user_id → asyncio.Task (Redis listener)
        self._listener_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Accept a WebSocket connection and start the Redis listener task.
        If the user already has an active connection, it is replaced.
        """
        await websocket.accept()

        # Cancel any existing connection for this user
        if user_id in self._listener_tasks:
            self._listener_tasks[user_id].cancel()
            logger.debug("Replaced existing connection", extra={"user_id": user_id})

        self._connections[user_id] = websocket

        # Start a background task that reads from Redis pub/sub and
        # forwards messages to this WebSocket
        task = asyncio.create_task(
            self._redis_listener(user_id, websocket),
            name=f"ws-listener-{user_id}",
        )
        self._listener_tasks[user_id] = task

        logger.info(
            "WebSocket connected",
            extra={"user_id": user_id, "active_connections": len(self._connections)},
        )

        # Send a connection-established message
        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "message": "Connected to Aureus Intelligence real-time alerts.",
        })

    def disconnect(self, user_id: str) -> None:
        """Remove a connection and cancel its listener task."""
        self._connections.pop(user_id, None)
        task = self._listener_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()
        logger.info(
            "WebSocket disconnected",
            extra={"user_id": user_id, "active_connections": len(self._connections)},
        )

    async def send_to_user(self, user_id: str, payload: dict[str, Any]) -> bool:
        """
        Send a JSON payload directly to a connected user.
        Returns True on success, False if user is not connected.
        """
        ws = self._connections.get(user_id)
        if ws is None:
            return False
        try:
            await ws.send_json(payload)
            return True
        except Exception as exc:
            logger.warning(
                "WebSocket send failed",
                extra={"user_id": user_id, "error": str(exc)},
            )
            self.disconnect(user_id)
            return False

    async def _redis_listener(self, user_id: str, websocket: WebSocket) -> None:
        """
        Long-running task: subscribe to Redis `alerts:{user_id}` and
        forward any published alert to the WebSocket.
        Runs until the WebSocket disconnects or the task is cancelled.
        """
        settings  = get_settings()
        channel   = f"alerts:{user_id}"

        try:
            async with aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            ) as client:
                pubsub = client.pubsub()
                await pubsub.subscribe(channel)
                logger.debug("Redis subscription active", extra={"channel": channel})

                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    try:
                        data = json.loads(message["data"])
                        await websocket.send_json({"type": "alert", **data})
                        logger.info(
                            "Alert forwarded to WebSocket",
                            extra={"user_id": user_id, "severity": data.get("severity")},
                        )
                    except json.JSONDecodeError as exc:
                        logger.warning("Malformed Redis alert payload", extra={"error": str(exc)})
                    except Exception as exc:
                        logger.warning(
                            "WebSocket forward failed",
                            extra={"user_id": user_id, "error": str(exc)},
                        )
                        break  # WebSocket likely closed

        except asyncio.CancelledError:
            logger.debug("Redis listener cancelled", extra={"user_id": user_id})
        except Exception as exc:
            logger.error(
                "Redis listener error",
                extra={"user_id": user_id, "channel": channel, "error": str(exc)},
            )
        finally:
            self.disconnect(user_id)

    @property
    def connected_user_ids(self) -> list[str]:
        return list(self._connections.keys())

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Module-level singleton — shared across all FastAPI routes
manager = ConnectionManager()
