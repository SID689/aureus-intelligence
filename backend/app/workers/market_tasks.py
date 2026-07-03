"""
app/workers/market_tasks.py
---------------------------
Celery tasks for background market data ingestion.

All tasks are synchronous (no asyncio) since Celery workers use threading,
not an event loop. The MarketDataService fallback chain is fully sync.

Each task follows the same structure:
  1. Fetch data via MarketDataService (with fallback + backoff).
  2. Write results to Postgres via SQLAlchemy.
  3. Publish a Redis pub/sub event so connected SSE clients update.
  4. Log timing and row counts as performance metrics.
"""

import logging
import time
from datetime import date, timedelta

from celery import shared_task
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.ingestion.market_data import MarketDataService
from app.ingestion.rate_limiter import FallbackExhaustedError

logger = logging.getLogger("aureus.workers.market")


def _get_engine():
    """SQLAlchemy engine — created per-task to avoid shared connection state."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def _get_all_tracked_tickers(engine) -> list[str]:
    """
    Pull the distinct set of tickers currently held across all portfolios.
    This drives which symbols need periodic price refreshes.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT ticker FROM portfolio_holdings")
        ).fetchall()
    return [row[0] for row in rows]


def _upsert_latest_price(engine, ticker: str, price: float) -> None:
    """
    Update current_price and last_priced_at on portfolio_holdings rows
    for all holdings of this ticker.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE portfolio_holdings
                SET current_price = :price,
                    last_priced_at = NOW()
                WHERE ticker = :ticker
            """),
            {"price": price, "ticker": ticker},
        )


def _publish_price_update(ticker: str, price: float) -> None:
    """
    Publish to Redis pub/sub so FastAPI's SSE endpoint can forward
    the price update to connected browser clients in real time.
    Channel format: 'price:{TICKER}'
    """
    try:
        redis_client = get_redis_client()
        redis_client.publish(f"price:{ticker}", f"{price:.4f}")
    except Exception as exc:
        logger.warning(
            "Redis pub/sub publish failed — SSE clients won't get live update",
            extra={"ticker": ticker, "error": str(exc)},
        )


# ── Tasks ──────────────────────────────────────────────────────────────────────

@shared_task(
    name="app.workers.market_tasks.refresh_latest_prices",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="market-data",
)
def refresh_latest_prices(self) -> dict:
    """
    Periodic task: fetch the latest trade price for every tracked ticker
    and write it to portfolio_holdings + publish to Redis.
    Called every 5 minutes by Celery Beat.
    """
    start_time = time.monotonic()
    engine = _get_engine()
    svc    = MarketDataService()

    tickers = _get_all_tracked_tickers(engine)
    if not tickers:
        logger.info("No tracked tickers — skipping price refresh")
        return {"tickers_refreshed": 0}

    success_count = 0
    failed: list[str] = []

    for ticker in tickers:
        try:
            price = svc.fetch_latest_price(ticker)
            _upsert_latest_price(engine, ticker, price)
            _publish_price_update(ticker, price)
            success_count += 1
        except FallbackExhaustedError as exc:
            logger.error(
                "All providers failed for ticker",
                extra={"ticker": ticker, "providers": exc.attempted_providers},
            )
            failed.append(ticker)
        except Exception as exc:
            logger.error(
                "Unexpected error refreshing price",
                extra={"ticker": ticker, "error": str(exc)},
            )
            failed.append(ticker)

    elapsed = time.monotonic() - start_time
    logger.info(
        "Price refresh complete",
        extra={
            "tickers_success": success_count,
            "tickers_failed": len(failed),
            "elapsed_seconds": round(elapsed, 3),
        },
    )
    return {
        "tickers_refreshed": success_count,
        "tickers_failed": failed,
        "elapsed_seconds": round(elapsed, 3),
    }


@shared_task(
    name="app.workers.market_tasks.refresh_daily_bars",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    queue="market-data",
)
def refresh_daily_bars(self) -> dict:
    """
    Periodic task: fetch yesterday's completed daily bar for all tracked tickers.
    Runs once daily after market close (configured in celery_app.py beat schedule).
    Stores bars in Redis as JSON for fast retrieval by the analysis tasks.
    """
    start_time = time.monotonic()
    engine  = _get_engine()
    svc     = MarketDataService()
    redis   = get_redis_client()

    tickers = _get_all_tracked_tickers(engine)
    if not tickers:
        return {"bars_cached": 0}

    end_date   = date.today()
    start_date = end_date - timedelta(days=365)

    cached_count = 0
    failed: list[str] = []

    for ticker in tickers:
        try:
            result = svc.fetch_bars(ticker, start_date, end_date, frequency="1d")
            # Store as JSON in Redis — key format: bars:1d:{TICKER}
            bars_json = result.bars.reset_index().to_json(orient="records", date_format="iso")
            redis.setex(f"bars:1d:{ticker}", 86400 * 2, bars_json)  # 48h TTL
            cached_count += 1
            logger.debug("Daily bars cached", extra={"ticker": ticker, "rows": len(result.bars)})
        except FallbackExhaustedError as exc:
            logger.error("All providers failed for daily bars", extra={"ticker": ticker})
            failed.append(ticker)
        except Exception as exc:
            logger.error(
                "Daily bar refresh error",
                extra={"ticker": ticker, "error": str(exc)},
            )
            failed.append(ticker)

    elapsed = time.monotonic() - start_time
    logger.info(
        "Daily bar refresh complete",
        extra={"cached": cached_count, "failed": len(failed), "elapsed_seconds": round(elapsed, 3)},
    )
    return {"bars_cached": cached_count, "tickers_failed": failed}


@shared_task(
    name="app.workers.market_tasks.refresh_ticker_bars",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="market-data",
)
def refresh_ticker_bars(self, ticker: str, lookback_days: int = 365) -> dict:
    """
    On-demand task: fetch and cache bars for a single ticker.
    Triggered when a user runs an analysis on a ticker not already cached.
    """
    start_time = time.monotonic()
    svc   = MarketDataService()
    redis = get_redis_client()

    end_date   = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    try:
        result    = svc.fetch_bars(ticker.upper(), start_date, end_date, frequency="1d")
        bars_json = result.bars.reset_index().to_json(orient="records", date_format="iso")
        redis.setex(f"bars:1d:{ticker.upper()}", 86400 * 2, bars_json)
        elapsed   = time.monotonic() - start_time
        return {
            "ticker": ticker,
            "provider": result.provider,
            "rows": len(result.bars),
            "elapsed_seconds": round(elapsed, 3),
        }
    except FallbackExhaustedError as exc:
        logger.error(
            "All providers exhausted for on-demand bar fetch",
            extra={"ticker": ticker, "providers": exc.attempted_providers},
        )
        raise self.retry(exc=exc)
