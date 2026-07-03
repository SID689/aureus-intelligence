"""
app/main.py
-----------
FastAPI application entry point.

Startup sequence:
  1. Configure structured logging.
  2. Verify Redis connectivity (fail fast — the app is useless without it).
  3. Register all API routers.
  4. Mount CORS middleware (tightened in production).

Run locally:
  uvicorn app.main:app --reload --port 8000

Or via Docker:
  docker compose up backend
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.redis_client import get_redis_client
from app.api.v1.analysis import router as analysis_router

settings = get_settings()
setup_logging(level=settings.log_level, use_json=settings.is_production)
logger = logging.getLogger("aureus.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context: runs startup checks before accepting requests,
    and any teardown after the server shuts down.
    """
    logger.info("Aureus Intelligence API starting up", extra={"env": settings.app_env})

    # Fail fast if Redis is unreachable — rate limiting and job queuing won't work
    try:
        get_redis_client().ping()
        logger.info("Redis connectivity: OK")
    except Exception as exc:
        logger.critical("Redis unreachable at startup — aborting", extra={"error": str(exc)})
        raise RuntimeError("Redis is required but not reachable") from exc

    logger.info(
        "Provider configuration",
        extra={
            "polygon":       settings.polygon_configured,
            "alpha_vantage": settings.alpha_vantage_configured,
            "finnhub":       settings.finnhub_configured,
        },
    )

    yield  # ← application runs here

    logger.info("Aureus Intelligence API shutting down")


app = FastAPI(
    title="Aureus Intelligence API",
    description=(
        "Quantitative analysis and data ingestion backend for Aureus Intelligence. "
        "All analysis outputs are for informational purposes only and do not constitute "
        "investment advice."
    ),
    version="0.2.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In production, replace "*" with your exact Next.js domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else ["https://app.aureusintelligence.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(analysis_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["ops"])
def health_check() -> dict:
    """
    Lightweight health check for load balancers and container orchestrators.
    Returns 200 if the process is alive; does not check downstream dependencies
    (Redis/Postgres have separate health checks in docker-compose.yml).
    """
    return {"status": "ok", "version": "0.2.0"}
