"""
app/main.py  (Phase 6 — adds market, portfolio, news routers)
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.redis_client import get_redis_client
from app.api.v1.analysis  import router as analysis_router
from app.api.v1.ws        import router as ws_router
from app.api.v1.voice     import router as voice_router
from app.api.v1.billing   import router as billing_router
from app.api.v1.metrics   import router as metrics_router
from app.api.v1.market    import router as market_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.news      import router as news_router
from app.api.v1.backtest  import router as backtest_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.lessons import router as lessons_router

settings = get_settings()
setup_logging(level=settings.log_level, use_json=settings.is_production)
logger = logging.getLogger("aureus.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Aureus Intelligence API starting", extra={"env": settings.app_env, "version": "0.6.0"})
    try:
        get_redis_client().ping()
        logger.info("Redis: OK")
    except Exception as exc:
        raise RuntimeError("Redis unreachable") from exc
    logger.info("Providers", extra={
        "polygon":      settings.polygon_configured,
        "anthropic":    settings.anthropic_configured,
        "openai":       settings.openai_configured,
    })
    yield
    logger.info("Aureus Intelligence API shutting down")


app = FastAPI(
    title="Aureus Intelligence API",
    version="0.6.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"] if not settings.is_production
                  else ["https://app.aureusintelligence.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Internal-Secret"],
)

app.include_router(analysis_router)
app.include_router(ws_router)
app.include_router(voice_router)
app.include_router(billing_router)
app.include_router(metrics_router)
app.include_router(market_router)
app.include_router(portfolio_router)
app.include_router(news_router)
app.include_router(backtest_router)
app.include_router(onboarding_router)
app.include_router(lessons_router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok", "version": "0.6.0"}
