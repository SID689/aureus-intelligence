"""
app/api/v1/cron.py
------------------
POST /api/v1/cron/tick    run whatever scheduled work is now due (X-Internal-Secret)
GET  /api/v1/cron/status  when each job last ran            (X-Internal-Secret)

WHY THIS EXISTS

Celery beat does not run in production. Render's free tier has web
services and nothing else: no background worker to consume a queue, no
cron to fill one. So every scheduled job in this codebase -- price
refreshes, news ingestion, the agent pipeline, the daily catalyst sweep
-- simply never happened once deployed, and the market data went stale
from the moment it was seeded.

This gives that schedule an external heartbeat. Something outside the
platform (a GitHub Actions workflow, in .github/workflows/cron.yml)
calls tick every few minutes, and tick runs whatever is due in this
process.

WHAT IT DOES NOT DO

It does not restate the schedule. The definitions live in
celery_app.conf.beat_schedule and are read from there, because a second
copy would drift from the first and the drift would be silent -- a job
running at the wrong cadence, or not at all, with both files looking
correct in isolation. Adding a job to beat_schedule is all that is
needed for this to pick it up.

It is also not a replacement for beat. Cadences below the caller's
interval collapse into it: the news preprocessing cycle wants 15 seconds
and will get one run per call. That is the honest cost of having no
worker, and it is a long way better than never running.
"""

import logging
import os
import secrets as _secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from app.core.redis_client import get_redis_client

logger = logging.getLogger("aureus.cron")

router = APIRouter(prefix="/api/v1/cron", tags=["cron"])

INTERNAL_SECRET = os.getenv("INTERNAL_API_SECRET", "")

# Redis keys
_LAST = "cron:last:{}"           # ISO timestamp of the last attempt, per job
_LOCK = "cron:tick:lock"

# A tick answers over HTTP, so it cannot run for as long as it likes. New
# jobs stop being started past this; whatever is left is reported as
# deferred and picked up by the next call, since nothing has been marked
# as run.
_BUDGET = float(os.getenv("CRON_TICK_BUDGET_SECONDS", "45"))

# Long enough that a slow tick is never lapped by the next one, short
# enough that a killed instance does not wedge the schedule for an hour.
_LOCK_TTL = 600


def _verify(x_internal_secret: str) -> None:
    """
    Shared-secret check, failing closed, as in billing.py.

    An unset secret refuses every call rather than skipping the check.
    This endpoint runs market-data jobs that spend metered provider
    quota, so an open version of it is a way for a stranger to burn money.
    """
    if not INTERNAL_SECRET:
        logger.error("INTERNAL_API_SECRET is not configured: refusing cron call")
        raise HTTPException(status_code=503, detail="Internal auth not configured")
    if not _secrets.compare_digest(x_internal_secret or "", INTERNAL_SECRET):
        raise HTTPException(status_code=403, detail="Unauthorized internal call")


def _schedule() -> dict:
    """
    The beat schedule, with every task in the app's `include` list
    actually imported, so it can be resolved by name.

    finalize() is not what does that -- it builds the task registry from
    what has already been imported, which in the API process is almost
    nothing, so every lookup missed and every job was skipped with "task
    not registered". Importing the default modules is the step a worker
    performs at startup and this process otherwise never does.
    """
    from app.workers.celery_app import celery_app
    try:
        celery_app.loader.import_default_modules()
    except Exception:
        logger.exception("Could not import scheduled task modules")
    celery_app.finalize()
    return dict(celery_app.conf.beat_schedule or {})


def _read_last(redis, name: str) -> datetime | None:
    try:
        raw = redis.get(_LAST.format(name))
    except Exception:
        return None
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _mark(redis, name: str, when: datetime) -> None:
    try:
        redis.set(_LAST.format(name), when.isoformat())
    except Exception as exc:
        logger.warning("Could not record cron run", extra={"job": name, "error": str(exc)})


def _is_due(entry_schedule, last: datetime | None, now: datetime) -> tuple[bool, str]:
    """
    Due or not, and why.

    Two kinds of schedule appear in beat_schedule: a number of seconds,
    and a crontab.

    A number with no recorded run is treated as due. These are the
    frequent, cheap jobs, and running one a few minutes early costs
    nothing.

    A crontab with no recorded run is NOT. Otherwise the first tick after
    a deploy fires every daily, weekly and monthly job at once --
    including the monthly recalibration, which makes around 160 provider
    calls. The first sighting records a baseline instead, and the job
    fires at its next real occurrence.
    """
    if isinstance(entry_schedule, (int, float)):
        if last is None:
            return True, "never run"
        elapsed = (now - last).total_seconds()
        return (elapsed >= float(entry_schedule),
                f"{elapsed:.0f}s since last, every {entry_schedule:.0f}s")

    is_due_fn = getattr(entry_schedule, "is_due", None)
    if is_due_fn is None:
        return False, "unrecognised schedule"

    if last is None:
        return False, "first sighting: a baseline is taken, then it fires at its next occurrence"
    try:
        state = is_due_fn(last)
        return bool(state[0]), "crontab due" if state[0] else "crontab not due"
    except Exception as exc:          # a malformed entry must not stop the tick
        logger.warning("Could not evaluate schedule", extra={"error": str(exc)})
        return False, "schedule could not be evaluated"


@router.post("/tick")
def tick(x_internal_secret: str = Header(default="")) -> dict:
    """Run every job whose schedule says it is due, in this process."""
    _verify(x_internal_secret)

    redis = get_redis_client()

    # One tick at a time. Two overlapping callers would run the same jobs
    # twice against rate-limited providers.
    try:
        if not redis.set(_LOCK, "1", nx=True, ex=_LOCK_TTL):
            return {"status": "busy", "detail": "another tick is already running"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}") from exc

    started = time.monotonic()
    ran: list[dict] = []
    skipped: list[dict] = []
    deferred: list[str] = []

    try:
        from app.workers.celery_app import celery_app
        schedule = _schedule()

        for name, entry in sorted(schedule.items()):
            task_name = entry.get("task", "")
            now = datetime.now(timezone.utc)
            last = _read_last(redis, name)
            due, why = _is_due(entry.get("schedule"), last, now)

            if not due:
                # A crontab seen for the first time gets its baseline here,
                # so it becomes eligible from now rather than from epoch.
                if last is None and not isinstance(entry.get("schedule"), (int, float)):
                    _mark(redis, name, now)
                skipped.append({"job": name, "reason": why})
                continue

            if time.monotonic() - started > _BUDGET:
                # Deliberately not marked: the next tick finds it still due.
                deferred.append(name)
                continue

            task = celery_app.tasks.get(task_name)
            if task is None:
                skipped.append({"job": name, "reason": f"task not registered: {task_name}"})
                continue

            job_started = time.monotonic()
            # Marked before running, not after. A job that dies hard, or
            # an instance killed mid-run, must not leave the job eligible
            # on every subsequent tick -- that turns one failure into a
            # loop against metered providers.
            _mark(redis, name, now)
            try:
                result = task.apply()          # eager, in this process
                ok = result.successful()
                entry_out = {
                    "job": name,
                    "task": task_name,
                    "ok": ok,
                    "seconds": round(time.monotonic() - job_started, 2),
                }
                if not ok:
                    entry_out["error"] = str(result.result)[:300]
                    logger.error("Scheduled job failed", extra={"job": name, "error": entry_out["error"]})
                else:
                    logger.info("Scheduled job ran", extra={"job": name, "seconds": entry_out["seconds"]})
                ran.append(entry_out)
            except Exception as exc:
                logger.exception("Scheduled job raised", extra={"job": name})
                ran.append({
                    "job": name, "task": task_name, "ok": False,
                    "seconds": round(time.monotonic() - job_started, 2),
                    "error": str(exc)[:300],
                })
    finally:
        try:
            redis.delete(_LOCK)
        except Exception:
            pass

    failed = [r["job"] for r in ran if not r["ok"]]
    return {
        "status": "ok" if not failed else "partial",
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "ran": ran,
        "failed": failed,
        "deferred": deferred,
        "skipped": skipped,
    }


@router.get("/status")
def status(x_internal_secret: str = Header(default="")) -> dict:
    """When each job last ran, and whether it is due now. Read-only."""
    _verify(x_internal_secret)
    redis = get_redis_client()
    now = datetime.now(timezone.utc)

    out = []
    for name, entry in sorted(_schedule().items()):
        last = _read_last(redis, name)
        due, why = _is_due(entry.get("schedule"), last, now)
        out.append({
            "job": name,
            "task": entry.get("task", ""),
            "last_run": last.isoformat() if last else None,
            "due_now": due,
            "detail": why,
        })
    return {"now": now.isoformat(), "jobs": out}
