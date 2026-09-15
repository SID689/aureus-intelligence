"""
app/workers/celery_app.py  (Phase 3 — explicit task includes)
"""
import logging
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

from app.core.config import get_settings
from app.core.logging_config import setup_logging

logger = logging.getLogger("aureus.celery")


def create_celery_app() -> Celery:
    settings = get_settings()
    setup_logging(level=settings.log_level, use_json=settings.is_production)

    app = Celery("aureus")

    app.conf.update(
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        result_expires=3600,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        broker_connection_retry_on_startup=True,

        # Explicit includes — autodiscover_tasks only finds files named tasks.py
        include=[
            "app.workers.market_tasks",
            "app.workers.news_tasks",
            "app.workers.analysis_tasks",
            "app.workers.scanner_tasks",
        ],

        task_queues=(
            Queue("market-data",         Exchange("market-data"),         routing_key="market-data"),
            Queue("news-ingestion",      Exchange("news-ingestion"),      routing_key="news-ingestion"),
            Queue("agent-orchestration", Exchange("agent-orchestration"), routing_key="agent-orchestration"),
        ),
        task_default_queue="market-data",
        task_default_exchange="market-data",
        task_default_routing_key="market-data",

        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,

        task_annotations={
            "app.workers.market_tasks.refresh_ticker_bars":    {"rate_limit": "30/m"},
            "app.workers.market_tasks.refresh_latest_prices":  {"rate_limit": "10/m"},
            "app.workers.analysis_tasks.run_analysis_task":    {"rate_limit": "20/m"},
            "app.workers.news_tasks.run_agent_pipeline_cycle": {"rate_limit": "4/m"},
        },

        beat_schedule={
            "refresh-portfolio-prices-every-5min": {
                "task":     "app.workers.market_tasks.refresh_latest_prices",
                "schedule": 300,
                "options":  {"queue": "market-data"},
            },
            "refresh-daily-bars-after-close": {
                "task":     "app.workers.market_tasks.refresh_daily_bars",
                "schedule": crontab(hour=17, minute=0, day_of_week="1-5"),
                "options":  {"queue": "market-data"},
            },
            "ingest-news-every-60s": {
                "task":     "app.workers.news_tasks.ingest_news_cycle",
                "schedule": 60,
                "options":  {"queue": "news-ingestion"},
            },
            "preprocess-news-every-15s": {
                "task":     "app.workers.news_tasks.run_preprocessing_cycle",
                "schedule": 15,
                "options":  {"queue": "news-ingestion"},
            },
            "run-agent-pipeline-every-30s": {
                "task":     "app.workers.news_tasks.run_agent_pipeline_cycle",
                "schedule": 30,
                "options":  {"queue": "agent-orchestration"},
            },
            # Monthly, and deliberately not more often. The job makes
            # ~160 provider calls, and what it measures — where each
            # signal sits across the market — moves on the timescale of a
            # regime, not a week. 06:00 UTC on the 1st is outside US
            # market hours, so it competes with nothing.
            "recalibrate-signals-monthly": {
                "task":     "app.workers.analysis_tasks.recalibrate_signals",
                "schedule": crontab(hour=6, minute=0, day_of_month="1"),
                # market-data, not a queue of its own: there is no
                # "analysis" queue declared in task_queues and no worker
                # subscribed to one, so routing there would park this job
                # in the broker forever with nothing to report it. It is
                # a market-data refresh in substance anyway — it fetches
                # bars and fundamentals — and run_analysis_task already
                # lands on this queue via task_default_queue.
                "options":  {"queue": "market-data"},
            },
            # Fires every 15 minutes; the scanner decides whether a pass is
            # actually due (15 min while the US market is open, hourly
            # otherwise) and holds a Redis lock, so an overrun never
            # overlaps the next beat. Quota ceilings: app/scanner/budget.py.
            # `expires` drops a beat that sat queued behind a busy worker
            # instead of letting several stale ones run back to back.
            "scan-market-every-15min": {
                "task":     "app.workers.scanner_tasks.run_market_scan",
                "schedule": 900,
                "options":  {"queue": "market-data", "expires": 840},
            },
            "refresh-scanner-universe-weekly": {
                "task":     "app.workers.scanner_tasks.refresh_scanner_universe",
                "schedule": crontab(hour=5, minute=0, day_of_week="sun"),
                "options":  {"queue": "market-data"},
            },
            # 10:30 UTC is 06:30 in New York during daylight time and 05:30
            # in winter: before the open either way.
            "refresh-catalysts-daily": {
                "task":     "app.workers.scanner_tasks.refresh_catalysts_market_wide",
                "schedule": crontab(hour=10, minute=30),
                "options":  {"queue": "market-data"},
            },
            "stream-health-check-every-5min": {
                "task":     "app.workers.news_tasks.check_stream_health",
                "schedule": 300,
                "options":  {"queue": "news-ingestion"},
            },
        },
    )

    return app


celery_app = create_celery_app()