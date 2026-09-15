"""
app/workers/scanner_tasks.py
------------------------------
Celery tasks for the market scanner, catalysts and Strong Buy alerts.

None of these retry on failure except alert delivery. The scan and the
catalyst sweep are scheduled; retrying a failed pass against rate-limited
providers would spend quota to arrive at the same answer the next
scheduled pass reaches anyway. Delivery is different: an alert that fails
to go out is lost, and fan-out is idempotent, so it retries.
"""

import logging

from celery import shared_task

# Imported for its side effect: it configures the Celery app these
# shared_tasks bind to. Without it, a process that imports this module
# before anything else has loaded celery_app (the catalysts API's internal
# refresh route, a management shell) enqueues against Celery's default
# broker, amqp://localhost, and fails with "connection refused".
from app.workers.celery_app import celery_app  # noqa: F401

logger = logging.getLogger("aureus.workers.scanner")


@shared_task(name="app.workers.scanner_tasks.run_market_scan", max_retries=0,
             soft_time_limit=14 * 60, time_limit=15 * 60)
def run_market_scan(force: bool = False) -> dict:
    """Beat fires this every 15 minutes; the engine decides whether a pass is due."""
    from app.scanner.engine import run_scan
    return run_scan(force=force)


@shared_task(name="app.workers.scanner_tasks.refresh_scanner_universe", max_retries=0, time_limit=300)
def refresh_scanner_universe() -> dict:
    from app.scanner.universe import refresh_universe
    return refresh_universe()


@shared_task(name="app.workers.scanner_tasks.refresh_catalysts_market_wide", max_retries=0,
             soft_time_limit=25 * 60, time_limit=30 * 60)
def refresh_catalysts_market_wide() -> dict:
    """
    Daily, before the US open: the earnings calendar for the whole
    universe, FOMC and FDA calendars, and the per-ticker sources (8-K
    filings, dividends) for names on the board — the ones whose catalyst
    column is on screen.
    """
    from app.catalysts import service
    from app.scanner import leaderboard
    from app.scanner.universe import active_universe

    tickers = {u["ticker"] for u in active_universe()}
    board = sorted({t for _, t in leaderboard.active_pairs()})
    result = service.refresh_market_wide(tickers | set(board))
    result["news_reclassified"] = service.reclassify_news_catalysts()
    result["board_refreshed"] = {t: service.refresh_ticker(t, timeout=30) for t in board}
    logger.info("Market-wide catalyst refresh complete",
                extra={"earnings": result.get("earnings"), "board": len(board)})
    return result


@shared_task(name="app.workers.scanner_tasks.deliver_market_alert", bind=True, max_retries=3,
             default_retry_delay=30, time_limit=300)
def deliver_market_alert(self, alert_id: str) -> dict:
    from app.notifications import market_alerts
    try:
        result = market_alerts.fan_out(alert_id)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)
    ensure_alert_delivery.apply_async((alert_id,), countdown=market_alerts.WS_GRACE_SECONDS)
    return result


@shared_task(name="app.workers.scanner_tasks.ensure_alert_delivery", max_retries=0, time_limit=300)
def ensure_alert_delivery(alert_id: str) -> dict:
    from app.notifications import market_alerts
    return market_alerts.push_undelivered(alert_id)
