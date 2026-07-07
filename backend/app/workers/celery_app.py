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
            "stream-health-check-every-5min": {
                "task":     "app.workers.news_tasks.check_stream_health",
                "schedule": 300,
                "options":  {"queue": "news-ingestion"},
            },
        },
    )

    return app


celery_app = create_celery_app()