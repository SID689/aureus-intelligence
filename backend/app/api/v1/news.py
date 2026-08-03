"""
app/api/v1/news.py
---------------------
Fixes "news section doesn't seem to be updating" by giving two things
that didn't exist before:

1. POST /api/v1/news/refresh — runs one full ingestion → preprocess →
   agent cycle SYNCHRONOUSLY and returns exactly what happened at each
   stage. This lets you verify the pipeline works in one request instead
   of waiting on Celery Beat's 60s/15s/30s schedule and reading worker
   logs.

2. GET /api/v1/news/recent — returns recently processed articles and
   their sentiment directly from the database. Previously the only way
   to see news was a live WebSocket push tied to a portfolio match — if
   you had no matching holdings (or the pipeline hadn't run yet), the
   feed looked empty/broken even when ingestion was working. This gives
   general visibility into "is the pipeline actually finding news."
"""

import logging
import time

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.streaming.news_ingestion import FinnhubNewsPoller, RSSNewsPoller
from app.streaming.preprocessor import PreprocessingWorker
from app.streaming.redis_streams import StreamProducer, stream_lengths

logger = logging.getLogger("aureus.api.news")
router = APIRouter(prefix="/api/v1/news", tags=["news"])


def _get_engine():
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@router.post("/refresh")
def manual_refresh() -> dict:
    """
    Synchronously run one ingestion + preprocessing cycle and report
    exactly what happened. Does NOT run the LLM agent step (that stays
    async on the Celery queue since it can take several seconds per
    article) — but this alone proves whether ingestion/preprocessing
    are finding and forwarding articles at all.
    """
    start = time.monotonic()
    producer = StreamProducer()
    result: dict = {"stages": {}}

    try:
        finnhub = FinnhubNewsPoller(producer)
        n_finnhub = finnhub.poll_once()
        result["stages"]["finnhub_ingested"] = n_finnhub
    except Exception as exc:
        result["stages"]["finnhub_error"] = str(exc)
        logger.error("Manual refresh: Finnhub failed", extra={"error": str(exc)})

    try:
        rss = RSSNewsPoller(producer)
        n_rss = rss.poll_once()
        result["stages"]["rss_ingested"] = n_rss
    except Exception as exc:
        result["stages"]["rss_error"] = str(exc)
        logger.error("Manual refresh: RSS failed", extra={"error": str(exc)})

    try:
        worker = PreprocessingWorker(consumer_name="manual-refresh")
        forwarded, dropped = 0, 0
        for msg_id, fields in worker._consumer.read(count=50, block_ms=1000):
            if worker.process_one(msg_id, fields):
                forwarded += 1
            else:
                dropped += 1
            worker._consumer.ack(msg_id)
        result["stages"]["preprocessed_forwarded"] = forwarded
        result["stages"]["preprocessed_dropped_neutral_or_duplicate"] = dropped
    except Exception as exc:
        result["stages"]["preprocessing_error"] = str(exc)
        logger.error("Manual refresh: preprocessing failed", extra={"error": str(exc)})

    result["stream_depths"] = stream_lengths()
    result["elapsed_seconds"] = round(time.monotonic() - start, 2)
    result["note"] = (
        "This ran ingestion + preprocessing synchronously. Articles that passed "
        "the sentiment pre-filter are now queued in news:agent_input — the "
        "Celery agent-orchestration worker will pick them up within ~30s and "
        "generate portfolio alerts for any matching holdings."
    )

    logger.info("Manual news refresh complete", extra=result["stages"])
    return result


@router.get("/recent")
def recent_articles(limit: int = Query(default=25, ge=1, le=100)) -> dict:
    """
    Return the most recently processed news articles with their sentiment,
    regardless of whether they matched any user's portfolio. This is what
    powers a general "market news" view so the feed isn't empty just
    because you don't hold the affected ticker.
    """
    engine = _get_engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        na.id AS alert_id, art.id AS article_id,
                        art.headline, art.source, art.source_url, art.published_at,
                        na.ticker, na.sentiment_score, na.summary, na.created_at
                    FROM news_alerts na
                    JOIN news_articles art ON na.news_article_id = art.id
                    ORDER BY na.created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            ).fetchall()
    except Exception as exc:
        logger.error("Recent articles query failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Could not load recent news")
    finally:
        engine.dispose()

    return {
        "count": len(rows),
        "articles": [
            {
                # id is the news_alerts row's own PK, not the article's — one
                # article can produce multiple alert rows (one per affected
                # ticker) via the join above, so reusing article.id here
                # produced duplicate React keys on the frontend.
                "id": str(r.alert_id), "article_id": str(r.article_id),
                "headline": r.headline, "source": r.source,
                "source_url": r.source_url, "ticker": r.ticker,
                "sentiment_score": float(r.sentiment_score), "summary": r.summary,
                "published_at": r.published_at.isoformat() if r.published_at else None,
                "processed_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/status")
def pipeline_status() -> dict:
    """Quick health check: stream depths + whether ANTHROPIC_API_KEY is set."""
    settings = get_settings()
    return {
        "stream_depths": stream_lengths(),
        "anthropic_configured": settings.anthropic_configured,
        "finnhub_configured": settings.finnhub_configured,
        "note": "agent-orchestration queue processes at most 5 articles per 30s cycle to bound LLM cost.",
    }
