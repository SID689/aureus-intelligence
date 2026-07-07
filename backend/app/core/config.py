"""
app/core/config.py  (Phase 3 update — adds Anthropic key)
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
    secret_key: str = Field(default="dev_secret_key_change_in_production_min_32_chars")

    # ── PostgreSQL ────────────────────────────────────────────────
    database_url: str = Field(default="postgresql://aureus:localdevpassword@db:5432/aureus_dev")

    # ── Redis ─────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://redis:6379/0")

    # ── Market data providers ─────────────────────────────────────
    polygon_api_key: str = Field(default="")
    alpha_vantage_api_key: str = Field(default="")

    # ── Fundamental data providers ────────────────────────────────
    finnhub_api_key: str = Field(default="")
    sec_edgar_user_agent: str = Field(
        default="AureusIntelligence contact@yourdomain.com"
    )

    # ── Phase 3: LLM ─────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")

    # ── Stripe ────────────────────────────────────────────────────
    stripe_secret_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")

    # ── Rate limiting defaults ────────────────────────────────────
    sovereign_daily_analysis_limit: int = 10
    elite_concurrent_strategies: int = 5
    elite_voice_minutes_per_month: int = 500

    # ── Phase 3: streaming ────────────────────────────────────────
    # How often (seconds) to poll Finnhub and RSS feeds for new articles
    news_poll_interval_seconds: int = 60
    # VADER pre-filter: only articles with |compound| > threshold go to LLM
    sentiment_prefilter_threshold: float = 0.05
    # Max LLM agent calls per minute across all workers
    agent_llm_calls_per_minute: int = 20

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

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
