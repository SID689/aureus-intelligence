"""
app/streaming/redis_streams.py
-------------------------------
Redis Streams wrapper — the internal message bus for the Phase 3 pipeline.

Redis Streams (XADD/XREAD/XACK) give us Kafka-like semantics without the
Kafka operational overhead:
  - Persistent, ordered, append-only log per stream
  - Consumer groups with at-least-once delivery guarantees
  - Message acknowledgement (XACK) so a crashed worker doesn't lose articles
  - O(1) producer write, O(N) consumer read where N = messages since last ID

Stream topology:
  news:raw          ← raw articles from Finnhub/RSS (before preprocessing)
  news:processed    ← cleaned, deduplicated, pre-filtered articles
  news:agent_input  ← articles that passed VADER threshold, ready for LLM
  alerts:dispatch   ← generated alerts waiting for WebSocket delivery

Consumer group naming convention: {stream}:workers
This allows multiple Celery worker processes to cooperate on the same stream
without processing the same message twice.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import redis

from app.core.redis_client import get_redis_client

logger = logging.getLogger("aureus.streaming.redis_streams")

# ── Stream name constants ──────────────────────────────────────────────────────
STREAM_RAW       = "news:raw"
STREAM_PROCESSED = "news:processed"
STREAM_AGENT     = "news:agent_input"
STREAM_ALERTS    = "alerts:dispatch"

# Consumer group names
GROUP_PREPROCESSOR = "preprocessor:workers"
GROUP_AGENT        = "agent:workers"
GROUP_DISPATCHER   = "dispatcher:workers"

# How long to block on XREADGROUP waiting for new messages (ms)
BLOCK_MS = 2000

# Max messages to read per XREADGROUP call
READ_BATCH = 10

# Pending message reclaim: if a message sits in PEL for > this many ms, reclaim it
RECLAIM_IDLE_MS = 30_000


# ── Message dataclass ──────────────────────────────────────────────────────────

@dataclass
class RawNewsMessage:
    article_id: str
    headline: str
    raw_content: str
    source: str
    source_url: str
    published_at: str         # ISO-8601
    ingested_at: str          # ISO-8601


@dataclass
class ProcessedNewsMessage:
    article_id: str
    headline: str
    clean_content: str
    source: str
    source_url: str
    published_at: str
    ingested_at: str
    affected_tickers: str     # JSON-encoded list, e.g. '["AAPL","MSFT"]'
    vader_compound: float     # VADER pre-filter score


@dataclass
class AlertMessage:
    user_id: str
    portfolio_id: str
    article_id: str
    ticker: str
    headline: str
    alert_text: str
    sentiment_score: float
    portfolio_impact_estimate: float
    severity: str             # low|medium|high|critical
    requires_human_review: bool
    generated_at: str         # ISO-8601


# ── Producer ───────────────────────────────────────────────────────────────────

class StreamProducer:
    """
    Thin wrapper around XADD.
    All values are coerced to strings because Redis Streams only store bytes.
    Use `from_dataclass` to serialize a dataclass to the flat dict Redis expects.
    """

    def __init__(self, client: redis.Redis | None = None):
        self._client = client or get_redis_client()

    def publish(self, stream: str, data: dict[str, Any]) -> str:
        """
        Write a message to a stream.
        Returns the Redis message ID (e.g. "1704067200000-0").
        All dict values are coerced to str for Redis compatibility.
        """
        str_data = {k: str(v) for k, v in data.items()}
        msg_id = self._client.xadd(stream, str_data)
        logger.debug("Published to stream", extra={"stream": stream, "msg_id": msg_id})
        return msg_id

    def publish_raw(self, msg: RawNewsMessage) -> str:
        return self.publish(STREAM_RAW, asdict(msg))

    def publish_processed(self, msg: ProcessedNewsMessage) -> str:
        return self.publish(STREAM_PROCESSED, asdict(msg))

    def publish_alert(self, msg: AlertMessage) -> str:
        return self.publish(STREAM_ALERTS, asdict(msg))


# ── Consumer ───────────────────────────────────────────────────────────────────

class StreamConsumer:
    """
    Consumer group reader with automatic group creation and message acknowledgement.

    Usage:
        consumer = StreamConsumer(STREAM_PROCESSED, GROUP_AGENT, "worker-1")
        for msg_id, data in consumer.read():
            process(data)
            consumer.ack(msg_id)
    """

    def __init__(self, stream: str, group: str, consumer_name: str):
        self.stream        = stream
        self.group         = group
        self.consumer_name = consumer_name
        self._client       = get_redis_client()
        self._ensure_group()

    def _ensure_group(self) -> None:
        """Create the consumer group if it doesn't already exist."""
        try:
            # MKSTREAM=True creates the stream if it doesn't exist yet
            self._client.xgroup_create(
                self.stream, self.group, id="0", mkstream=True
            )
            logger.info(
                "Consumer group created",
                extra={"stream": self.stream, "group": self.group},
            )
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                pass  # Group already exists — normal on restart
            else:
                raise

    def read(self, count: int = READ_BATCH, block_ms: int = BLOCK_MS):
        """
        Yield (msg_id, data_dict) tuples.
        Uses ">" as the ID so we only get undelivered messages.
        Blocks for block_ms if the stream is empty.
        """
        results = self._client.xreadgroup(
            groupname=self.group,
            consumername=self.consumer_name,
            streams={self.stream: ">"},
            count=count,
            block=block_ms,
        )
        if not results:
            return
        for _stream, messages in results:
            for msg_id, fields in messages:
                yield msg_id, fields

    def ack(self, msg_id: str) -> None:
        """Acknowledge a message — removes it from the PEL."""
        self._client.xack(self.stream, self.group, msg_id)

    def reclaim_idle(self, idle_ms: int = RECLAIM_IDLE_MS, count: int = 10):
        """
        Reclaim messages that have been pending (unacknowledged) for > idle_ms.
        Called at startup and periodically to recover from crashed workers.
        """
        try:
            result = self._client.xautoclaim(
                self.stream, self.group, self.consumer_name,
                min_idle_time=idle_ms, start_id="0-0", count=count,
            )
            # xautoclaim returns (next_id, messages, deleted_ids) in Redis 7+
            messages = result[1] if isinstance(result, (list, tuple)) and len(result) > 1 else []
            if messages:
                logger.info(
                    "Reclaimed idle messages",
                    extra={"stream": self.stream, "count": len(messages)},
                )
                for msg_id, fields in messages:
                    yield msg_id, fields
        except Exception as exc:
            logger.warning("xautoclaim failed", extra={"error": str(exc)})


# ── Stream length monitoring ───────────────────────────────────────────────────

def stream_lengths() -> dict[str, int]:
    """Return current length of all pipeline streams — used for health checks."""
    client = get_redis_client()
    streams = [STREAM_RAW, STREAM_PROCESSED, STREAM_AGENT, STREAM_ALERTS]
    result = {}
    for s in streams:
        try:
            result[s] = client.xlen(s)
        except Exception:
            result[s] = -1
    return result
