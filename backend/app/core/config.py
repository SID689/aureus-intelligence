"""
app/core/config.py
------------------
Single source of truth for all application configuration.
Reads from environment variables (or .env file via python-dotenv).
Validation is handled by pydantic-settings; the app will refuse to start
if required values are missing rather than failing silently at runtime.
"""

from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    app_env: str = Field(default="development", pattern="^(development|staging|production)$")
    log_level: str = Field(default="INFO")
    secret_key: str = Field(min_length=32)

    # ── PostgreSQL ────────────────────────────────────────────────
    database_url: str = Field(...)

    # ── Redis ─────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://redis:6379/0")

    # ── Market data providers ─────────────────────────────────────
    # Polygon is the highest-fidelity paid source.
    polygon_api_key: str = Field(default="")
    # Alpha Vantage is the mid-tier freemium fallback.
    alpha_vantage_api_key: str = Field(default="")
    # YFinance is the free final fallback — no key required.

    # ── Fundamental data providers ────────────────────────────────
    finnhub_api_key: str = Field(default="")
    sec_edgar_user_agent: str = Field(
        default="AureusIntelligence contact@yourdomain.com"
    )

    # ── Stripe ────────────────────────────────────────────────────
    stripe_secret_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")

    # ── Rate limiting defaults ────────────────────────────────────
    # These mirror the subscription_tiers seed data from Phase 1.
    sovereign_daily_analysis_limit: int = 10
    elite_concurrent_strategies: int = 5
    elite_voice_minutes_per_month: int = 500

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def polygon_configured(self) -> bool:
        return bool(self.polygon_api_key)

    @property
    def alpha_vantage_configured(self) -> bool:
        return bool(self.alpha_vantage_api_key)

    @property
    def finnhub_configured(self) -> bool:
        return bool(self.finnhub_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a cached Settings singleton.
    Importing this function and calling it is always safe — the cache
    ensures the .env file is only parsed once per process.
    """
    return Settings()
