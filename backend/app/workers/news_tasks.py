"""
app/workers/news_tasks.py  (Phase 3 replacement)
-------------------------------------------------
Celery tasks for the full Phase 3 news pipeline:
  1. ingest_news_cycle        — polls Finnhub + RSS, writes to news:raw
  2. run_preprocessing_cycle  — consumes news:raw, cleans/dedupes, writes to news:processed
  3. run_agent_pipeline_cycle — consumes news:processed, runs LangGraph, dispatches alerts

All three run as long-lived periodic tasks scheduled by Celery Beat.
They are intentionally separate tasks on separate queues so each can
be scaled, monitored, and rate-limited independently.
"""

import json
import logging
import time
from datetime import datetime, timezone

from celery import shared_task

from app.agents.graph import news_pipeline
from app.agents.state import make_initial_state
from app.streaming.news_ingestion import run_combined_ingestion, FinnhubNewsPoller, RSSNewsPoller
from app.streaming.preprocessor import PreprocessingWorker
from app.streaming.redis_streams import (
    GROUP_AGENT,
    STREAM_PROCESSED,
    StreamConsumer,
    StreamProducer,
    stream_lengths,
)

logger = logging.getLogger("aureus.workers.news")


# ── Task 1: News ingestion ─────────────────────────────────────────────────────

@shared_task(
    name="app.workers.news_tasks.ingest_news_cycle",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="news-ingestion",
)
def ingest_news_cycle(self) -> dict:
    """
    Poll Finnhub + RSS feeds and write raw articles to news:raw stream.
    Runs every 60 seconds via Celery Beat.
    """
    start = time.monotonic()
    producer = StreamProducer()

    try:
        finnhub = FinnhubNewsPoller(producer)
        rss     = RSSNewsPoller(producer)

        n_finnhub = finnhub.poll_once()
        n_rss     = rss.poll_once()
        elapsed   = time.monotonic() - start

        logger.info(
            "Ingestion cycle complete",
            extra={
                "finnhub_articles": n_finnhub,
                "rss_articles":     n_rss,
                "total":            n_finnhub + n_rss,
                "elapsed_seconds":  round(elapsed, 3),
            },
        )
        return {"finnhub": n_finnhub, "rss": n_rss, "elapsed_seconds": round(elapsed, 3)}

    except Exception as exc:
        logger.error("Ingestion cycle error", extra={"error": str(exc)})
        raise self.retry(exc=exc)


# ── Task 2: Preprocessing ─────────────────────────────────────────────────────

@shared_task(
    name="app.workers.news_tasks.run_preprocessing_cycle",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue="news-ingestion",
)
def run_preprocessing_cycle(self) -> dict:
    """
    Consume a batch from news:raw, preprocess, and write to news:processed.
    Runs every 15 seconds via Celery Beat for near-real-time processing.
    """
    start  = time.monotonic()
    worker = PreprocessingWorker(consumer_name=f"preprocessor-celery-{self.request.id or 'default'}")

    forwarded = 0
    dropped   = 0

    try:
        for msg_id, fields in worker._consumer.read(count=20, block_ms=1000):
            try:
                result = worker.process_one(msg_id, fields)
                if result:
                    forwarded += 1
                else:
                    dropped += 1
            except Exception as exc:
                logger.error(
                    "Preprocessing error on message",
                    extra={"msg_id": msg_id, "error": str(exc)},
                )
                dropped += 1
            finally:
                worker._consumer.ack(msg_id)

        elapsed = time.monotonic() - start
        logger.info(
            "Preprocessing cycle complete",
            extra={
                "forwarded":        forwarded,
                "dropped":          dropped,
                "elapsed_seconds":  round(elapsed, 3),
            },
        )
        return {"forwarded": forwarded, "dropped": dropped}

    except Exception as exc:
        logger.error("Preprocessing cycle error", extra={"error": str(exc)})
        raise self.retry(exc=exc)


# ── Task 3: Agent pipeline ────────────────────────────────────────────────────

@shared_task(
    name="app.workers.news_tasks.run_agent_pipeline_cycle",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
    queue="agent-orchestration",
)
def run_agent_pipeline_cycle(self) -> dict:
    """
    Consume a batch from news:processed, run each article through the
    LangGraph multi-agent pipeline (Analyst → Risk Delta → Advisory),
    and dispatch alerts via Redis pub/sub.

    Rate-limited to prevent LLM cost overruns:
    processes at most 5 articles per cycle (configurable).
    """
    start     = time.monotonic()
    consumer  = StreamConsumer(STREAM_PROCESSED, GROUP_AGENT, f"agent-celery-{self.request.id or 'default'}")

    processed   = 0
    alerts_sent = 0
    errors      = 0
    max_per_cycle = 5  # LLM cost guard — max articles per task invocation

    try:
        for msg_id, fields in consumer.read(count=max_per_cycle, block_ms=1000):
            article_id = fields.get("article_id", "unknown")
            try:
                # Deserialize candidate_tickers from JSON string
                candidate_tickers = []
                raw_tickers = fields.get("affected_tickers", "[]")
                try:
                    candidate_tickers = json.loads(raw_tickers)
                except (json.JSONDecodeError, TypeError):
                    pass

                # Build initial LangGraph state
                initial_state = make_initial_state(
                    article_id=article_id,
                    headline=fields.get("headline", ""),
                    clean_content=fields.get("clean_content", ""),
                    source=fields.get("source", ""),
                    source_url=fields.get("source_url", ""),
                    published_at=fields.get("published_at", ""),
                    candidate_tickers=candidate_tickers,
                )

                # Run the full LangGraph pipeline
                final_state = news_pipeline.invoke(initial_state)

                alerts_count = len(final_state.get("alerts_generated", []))
                alerts_sent += alerts_count
                processed   += 1

                logger.info(
                    "Agent pipeline complete for article",
                    extra={
                        "article_id":    article_id,
                        "signal":        final_state.get("event_type"),
                        "sentiment":     final_state.get("sentiment_score"),
                        "alerts_sent":   alerts_count,
                        "pipeline_errors": final_state.get("errors", []),
                    },
                )

            except Exception as exc:
                errors += 1
                logger.error(
                    "Agent pipeline error for article",
                    extra={"article_id": article_id, "error": str(exc)},
                    exc_info=True,
                )
            finally:
                # Always ack — a failed article should not block the stream
                consumer.ack(msg_id)

        elapsed = time.monotonic() - start
        logger.info(
            "Agent pipeline cycle complete",
            extra={
                "articles_processed": processed,
                "alerts_sent":        alerts_sent,
                "errors":             errors,
                "elapsed_seconds":    round(elapsed, 3),
            },
        )
        return {
            "articles_processed": processed,
            "alerts_sent":        alerts_sent,
            "errors":             errors,
            "elapsed_seconds":    round(elapsed, 3),
        }

    except Exception as exc:
        logger.error("Agent pipeline cycle error", extra={"error": str(exc)})
        raise self.retry(exc=exc)


# ── Task 4: Stream health check ───────────────────────────────────────────────

@shared_task(
    name="app.workers.news_tasks.check_stream_health",
    queue="news-ingestion",
)
def check_stream_health() -> dict:
    """Periodic health check — logs stream depths for monitoring."""
    lengths = stream_lengths()
    logger.info("Stream health check", extra={"stream_lengths": lengths})
    return lengths
