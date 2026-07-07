"""
app/main.py  (Phase 3 update — registers WebSocket router)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.redis_client import get_redis_client
from app.api.v1.analysis import router as analysis_router
from app.api.v1.ws import router as ws_router

settings = get_settings()
setup_logging(level=settings.log_level, use_json=settings.is_production)
logger = logging.getLogger("aureus.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Aureus Intelligence API starting up", extra={"env": settings.app_env})
    try:
        get_redis_client().ping()
        logger.info("Redis connectivity: OK")
    except Exception as exc:
        logger.critical("Redis unreachable at startup", extra={"error": str(exc)})
        raise RuntimeError("Redis is required but not reachable") from exc

    logger.info(
        "Provider configuration",
        extra={
            "polygon":       settings.polygon_configured,
            "alpha_vantage": settings.alpha_vantage_configured,
            "finnhub":       settings.finnhub_configured,
            "anthropic":     settings.anthropic_configured,
        },
    )
    yield
    logger.info("Aureus Intelligence API shutting down")


app = FastAPI(
    title="Aureus Intelligence API",
    description=(
        "Quantitative analysis, streaming news pipeline, and multi-agent "
        "portfolio impact system. All outputs are informational only."
    ),
    version="0.3.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else ["https://app.aureusintelligence.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(analysis_router)
app.include_router(ws_router)       # Phase 3: WebSocket + pending alerts


@app.get("/health", tags=["ops"])
def health_check() -> dict:
    return {"status": "ok", "version": "0.3.0"}
