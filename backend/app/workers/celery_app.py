"""
app/workers/celery_app.py
-------------------------
Celery application instance and configuration.

Three queues, each with its own dedicated worker pool (see docker-compose.yml):
  market-data         — tick/bar ingestion, price updates, beta recalculation
  news-ingestion      — news parsing, sentiment scoring, portfolio impact writes
  agent-orchestration — LangGraph/CrewAI agent state machine execution (Phase 3)

Beat schedule: periodic tasks that run on a cron-like schedule.
Workers pick up beat tasks from the 'market-data' queue by default.
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
        # ── Broker & result backend ────────────────────────────────
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        result_expires=3600,            # keep task results for 1 hour

        # ── Serialization ─────────────────────────────────────────
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,

        # ── Queue routing ─────────────────────────────────────────
        task_queues=(
            Queue(
                "market-data",
                Exchange("market-data"),
                routing_key="market-data",
            ),
            Queue(
                "news-ingestion",
                Exchange("news-ingestion"),
                routing_key="news-ingestion",
            ),
            Queue(
                "agent-orchestration",
                Exchange("agent-orchestration"),
                routing_key="agent-orchestration",
            ),
        ),
        task_default_queue="market-data",
        task_default_exchange="market-data",
        task_default_routing_key="market-data",

        # ── Reliability ────────────────────────────────────────────
        task_acks_late=True,            # ack only after task succeeds
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,   # one task at a time per worker thread

        # ── Rate limits ────────────────────────────────────────────
        # Protect the free-tier API fallbacks from overload
        task_annotations={
            "app.workers.market_tasks.refresh_ticker_bars": {"rate_limit": "30/m"},
            "app.workers.market_tasks.refresh_latest_prices": {"rate_limit": "10/m"},
            "app.workers.analysis_tasks.run_analysis_task": {"rate_limit": "20/m"},
        },

        # ── Beat periodic schedule ─────────────────────────────────
        beat_schedule={
            # Refresh prices for every portfolio holding every 5 minutes
            # during US market hours (Mon-Fri 9:30-16:00 ET handled in the task).
            "refresh-portfolio-prices-every-5min": {
                "task": "app.workers.market_tasks.refresh_latest_prices",
                "schedule": 300,  # every 300 seconds
                "options": {"queue": "market-data"},
            },
            # Full bar refresh once daily (after market close)
            "refresh-daily-bars-after-close": {
                "task": "app.workers.market_tasks.refresh_daily_bars",
                "schedule": crontab(hour=17, minute=0, day_of_week="1-5"),  # Mon-Fri 5 PM UTC
                "options": {"queue": "market-data"},
            },
        },
    )

    # Auto-discover tasks in workers package
    app.autodiscover_tasks(["app.workers"])

    return app


celery_app = create_celery_app()
