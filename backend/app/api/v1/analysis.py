"""
app/api/v1/analysis.py
----------------------
FastAPI router for the analysis API.

POST /api/v1/analysis/run
  Enqueues an ensemble analysis job and returns a job_id immediately.
  The client polls the result endpoint — no long-polling or SSE here yet.

GET  /api/v1/analysis/result/{job_id}
  Returns the current status and result payload from Redis.

GET  /api/v1/analysis/quick/{ticker}
  Synchronous endpoint — runs analysis inline and returns the result directly.
  Only available for Elite/Institutional tiers (enforced by the tier-check dep).
  Sovereign tier must use the async POST → poll flow.

All endpoints share a common disclaimer injection so it's impossible
to return analysis results without the required regulatory language.
"""

import json
import logging
import uuid
from typing import Any, Literal

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.entitlements import (
    Entitlements, check_quota, current_entitlements, record_usage, resolve_entitlements,
)
from app.core.redis_client import get_redis_client
from app.workers.analysis_tasks import run_analysis_task

logger = logging.getLogger("aureus.api.analysis")

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

DISCLAIMER = (
    "Aureus Intelligence provides software-generated informational analysis only. "
    "Nothing presented constitutes investment, legal, or tax advice, nor a recommendation "
    "to buy, hold, or sell any security. Past performance is not indicative of future results. "
    "All probabilistic outputs carry inherent uncertainty and should not be interpreted "
    "as guarantees of any outcome."
)


# ── Request / Response schemas ─────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, pattern=r"^[A-Za-z0-9.\-]+$")
    time_horizon: Literal["short_term", "medium_term", "long_term"] = "medium_term"
    # Required so the run can be metered against the caller's plan. The
    # client states WHO it is; the server decides what that permits.
    user_id: str = Field(..., min_length=1)


class JobEnqueuedResponse(BaseModel):
    job_id: str
    ticker: str
    time_horizon: str
    status: str = "queued"
    poll_url: str
    disclaimer: str = DISCLAIMER


class AnalysisResultResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "complete", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None
    disclaimer: str = DISCLAIMER


def _apply_sentiment_entitlements(result: dict, ent) -> dict:
    """
    Trim the sentiment pillar's research depth to what the plan includes.

    The pillar SCORE is never withheld. Hiding it would leave the headline
    confidence index unexplainable — a user would see a number moved by a
    factor they cannot see at all, which is worse than showing a free-tier
    user less detail. What is gated is the DEPTH behind it: the full
    catalyst list and the SEC filing-tone breakdown.

    Anything removed is replaced with an explicit `*_locked` marker rather
    than silently dropped, so the UI can render "3 of 12 catalysts —
    upgrade to see the rest" instead of appearing to have less data.
    """
    sent = result.get("sentiment")
    if not isinstance(sent, dict):
        return result

    cap = ent.max_sentiment_catalysts
    catalysts = sent.get("catalysts") or []
    if cap is not None and len(catalysts) > cap:
        sent["catalysts_total"] = len(catalysts)
        sent["catalysts"] = catalysts[:cap]
        sent["catalysts_locked"] = len(catalysts) - cap
    else:
        sent["catalysts_total"] = len(catalysts)
        sent["catalysts_locked"] = 0

    if not ent.sec_filing_tone_enabled:
        # Zero out the reading but keep the shape, so the card renders a
        # locked state rather than an error or a phantom neutral 50.
        sent["sec_tone_detail"] = {}
        sent["sec_tone_computed"] = False
        sent["sec_tone_label"] = "Locked"
        sent["sec_tone_locked"] = True
    else:
        sent["sec_tone_locked"] = False

    result["sentiment"] = sent
    return result


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/run", response_model=JobEnqueuedResponse, status_code=202)
def enqueue_analysis(request: AnalysisRequest) -> JobEnqueuedResponse:
    """
    Enqueue an ensemble analysis job.
    Returns a job_id immediately; the heavy work runs in a Celery worker.

    Metered against the caller's plan before the job is dispatched, so a
    user over quota never occupies a worker slot.
    """
    ticker    = request.ticker.upper().strip()
    job_id    = str(uuid.uuid4())

    ent = resolve_entitlements(request.user_id)
    check_quota(request.user_id, ent, "analysis_request", "Analysis", "runs")
    # Counted at dispatch rather than on completion. Counting on success
    # would let a user retry a failing ticker without limit, and the cost
    # being metered — provider calls and worker time — is already spent by
    # the time the job runs.
    record_usage(request.user_id, "analysis_request", 1.0)

    # Pre-write a "queued" status so the poll endpoint returns immediately
    try:
        redis = get_redis_client()
        redis.setex(
            f"analysis_result:{job_id}",
            3600,
            json.dumps({"status": "queued", "ticker": ticker, "time_horizon": request.time_horizon}),
        )
    except Exception as exc:
        logger.warning("Could not pre-write job status to Redis", extra={"error": str(exc)})

    # Dispatch to Celery
    run_analysis_task.apply_async(
        kwargs={
            "job_id": job_id,
            "ticker": ticker,
            "time_horizon": request.time_horizon,
        },
        task_id=job_id,
    )

    logger.info("Analysis job enqueued", extra={"job_id": job_id, "ticker": ticker})

    return JobEnqueuedResponse(
        job_id=job_id,
        ticker=ticker,
        time_horizon=request.time_horizon,
        poll_url=f"/api/v1/analysis/result/{job_id}",
    )


@router.get("/result/{job_id}", response_model=AnalysisResultResponse)
def get_analysis_result(job_id: str) -> AnalysisResultResponse:
    """
    Poll for the result of an enqueued analysis job.
    Returns status = 'queued' | 'running' | 'complete' | 'failed'.
    When complete, the full EnsembleSignal payload is in `result`.
    """
    try:
        redis = get_redis_client()
        raw   = redis.get(f"analysis_result:{job_id}")
    except Exception as exc:
        logger.error("Redis read error on result poll", extra={"job_id": job_id, "error": str(exc)})
        raise HTTPException(status_code=503, detail="Result store temporarily unavailable")

    if raw is None:
        raise HTTPException(status_code=404, detail="Job not found or result expired")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Malformed result data")

    status = data.pop("status", "unknown")
    error  = data.pop("error", None)
    result = data if status == "complete" and data else None

    return AnalysisResultResponse(
        job_id=job_id,
        status=status,  # type: ignore[arg-type]
        result=result,
        error=error,
    )


@router.get("/quick/{ticker}", response_model=AnalysisResultResponse)
def quick_analysis(
    ticker: str,
    ent: Annotated[Entitlements, Depends(current_entitlements)],
    user_id: Annotated[str, Query(min_length=1)],
    time_horizon: Literal["short_term", "medium_term", "long_term"] = Query(default="medium_term"),
) -> AnalysisResultResponse:
    """
    Synchronous analysis — runs inline and blocks until complete.

    WARNING: this endpoint can take 5-15 seconds depending on provider latency.
    Do not call this from a UI thread without a loading state.
    """
    from app.analysis.ensemble import run_ensemble_analysis
    from app.ingestion.rate_limiter import FallbackExhaustedError

    ticker_clean = ticker.upper().strip()
    job_id       = str(uuid.uuid4())

    check_quota(user_id, ent, "analysis_request", "Analysis", "runs")
    record_usage(user_id, "analysis_request", 1.0)

    try:
        signal = run_ensemble_analysis(ticker=ticker_clean, time_horizon=time_horizon,
                                       user_id=user_id)
        from dataclasses import asdict
        result_dict = asdict(signal)
        result_dict["generated_at"] = signal.generated_at.isoformat()
        result_dict = _apply_sentiment_entitlements(result_dict, ent)

        return AnalysisResultResponse(
            job_id=job_id,
            status="complete",
            result=result_dict,
        )

    except FallbackExhaustedError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Market data unavailable for {ticker_clean}. Providers tried: {', '.join(exc.attempted_providers)}",
        )
    except Exception as exc:
        logger.error(
            "Quick analysis failed",
            extra={"ticker": ticker_clean, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Analysis engine error")
