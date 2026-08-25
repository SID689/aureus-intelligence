"""
app/workers/analysis_tasks.py
------------------------------
Celery tasks that execute the full ensemble analysis pipeline in the background.
The FastAPI endpoint enqueues a task and returns a job_id immediately.
The client polls GET /api/v1/analysis/result/{job_id} until status = "complete".
"""

import json
import logging
import time
from typing import Literal

from celery import shared_task

from app.core.redis_client import get_redis_client
from app.analysis.ensemble import run_ensemble_analysis
from app.analysis.models import EnsembleSignal
from app.ingestion.rate_limiter import FallbackExhaustedError

logger = logging.getLogger("aureus.workers.analysis")

# Result TTL in Redis (1 hour — enough for polling, not permanent storage)
_RESULT_TTL = 3600


def _signal_to_dict(signal: EnsembleSignal) -> dict:
    """Serialize EnsembleSignal to a JSON-safe dict for Redis storage."""
    from dataclasses import asdict
    raw = asdict(signal)
    # Convert datetime to ISO string
    raw["generated_at"] = signal.generated_at.isoformat()
    return raw


def _store_result(job_id: str, status: str, payload: dict) -> None:
    try:
        redis = get_redis_client()
        redis.setex(
            f"analysis_result:{job_id}",
            _RESULT_TTL,
            json.dumps({"status": status, **payload}),
        )
    except Exception as exc:
        logger.error("Failed to store analysis result in Redis", extra={"job_id": job_id, "error": str(exc)})


@shared_task(
    name="app.workers.analysis_tasks.run_analysis_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    queue="market-data",
    track_started=True,
)
def run_analysis_task(
    self,
    job_id: str,
    ticker: str,
    time_horizon: Literal["short_term", "medium_term", "long_term"],
) -> dict:
    """
    Execute full ensemble analysis for a ticker and cache the result.

    Args:
        job_id:       UUID issued by the API layer — used as the Redis key.
        ticker:       Asset symbol.
        time_horizon: Analysis time horizon.
    """
    start_time = time.monotonic()
    logger.info("Analysis task started", extra={"job_id": job_id, "ticker": ticker})

    # Mark as in-progress so poll endpoint returns status immediately
    _store_result(job_id, "running", {"ticker": ticker, "time_horizon": time_horizon})

    try:
        signal = run_ensemble_analysis(ticker=ticker, time_horizon=time_horizon)
        elapsed = time.monotonic() - start_time

        result_dict = _signal_to_dict(signal)
        result_dict["elapsed_seconds"] = round(elapsed, 3)

        _store_result(job_id, "complete", result_dict)

        logger.info(
            "Analysis task complete",
            extra={
                "job_id": job_id,
                "ticker": ticker,
                "signal": signal.signal,
                "confidence": signal.confidence_index,
                "elapsed_seconds": round(elapsed, 3),
            },
        )
        return {"job_id": job_id, "status": "complete"}

    except FallbackExhaustedError as exc:
        logger.error(
            "Analysis failed — all data providers exhausted",
            extra={"job_id": job_id, "ticker": ticker, "providers": exc.attempted_providers},
        )
        _store_result(
            job_id, "failed",
            {"error": f"No market data available for {ticker}. Providers tried: {', '.join(exc.attempted_providers)}"},
        )
        # Don't retry on data-not-found — it won't succeed
        return {"job_id": job_id, "status": "failed"}

    except Exception as exc:
        logger.error(
            "Analysis task error",
            extra={"job_id": job_id, "ticker": ticker, "error": str(exc)},
            exc_info=True,
        )
        _store_result(job_id, "failed", {"error": "Internal analysis error. Please try again."})
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"job_id": job_id, "status": "failed"}


# ── Signal calibration refresh ──────────────────────────────────────────

@shared_task(
    name="app.workers.analysis_tasks.recalibrate_signals",
    # One attempt. This job makes roughly 160 provider calls; retrying a
    # partial failure would double that against rate-limited APIs to
    # refresh numbers that are, at worst, a month stale. The scheduled
    # run next month is the retry.
    max_retries=0,
    # Generous: 40 tickers x four analysis modules, several of which hit
    # the network with backoff.
    time_limit=3600,
    soft_time_limit=3300,
)
def recalibrate_signals(universe: list[str] | None = None) -> dict:
    """
    Re-measure sub-signal centres and dispersions into signal_calibration.

    Never raises. A failed refresh must not retry-storm the providers or
    mark the beat schedule unhealthy — analysis/calibration.py falls back
    to the last good measurement, and the staleness warning it logs is
    the signal that this needs attention.
    """
    from app.analysis.calibration_job import run as run_calibration

    started = time.time()
    try:
        result = run_calibration(universe)
        payload = {
            "ok": result.rows_written > 0,
            "rows_written": result.rows_written,
            "signals_measured": result.signals_measured,
            "universe_size": result.universe_size,
            "partial_failures": len(result.failures),
            "elapsed_seconds": round(time.time() - started, 1),
        }
        logger.info("Signal calibration task complete", extra=payload)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.error("Signal calibration task failed", extra={
            "error": str(exc), "elapsed_seconds": round(time.time() - started, 1),
        })
        return {"ok": False, "error": str(exc)}
