"""
app/core/config.py
"""
from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )

    # ── Application ───────────────────────────────────────────
    app_env: str = Field(default="development", pattern="^(development|staging|production)$")
    log_level: str = Field(default="INFO")
    secret_key: str = Field(default="dev_secret_key_change_in_production_min_32_chars")

    # ── PostgreSQL ────────────────────────────────────────────
    database_url: str = Field(default="postgresql://aureus:localdevpassword@db:5432/aureus_dev")

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = Field(default="redis://redis:6379/0")

    # ── Market data ───────────────────────────────────────────
    polygon_api_key: str = Field(default="")
    alpha_vantage_api_key: str = Field(default="")

    # ── Fundamental data ──────────────────────────────────────
    finnhub_api_key: str = Field(default="")
    sec_edgar_user_agent: str = Field(default="AureusIntelligence contact@yourdomain.com")

    # ── LLM ──────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")

    # ── Phase 4: OpenAI (Whisper STT + TTS) ──────────────────
    openai_api_key: str = Field(default="")

    # ── Local LLM (free) ─────────────────────────────────────
    # Ollama runs open-weight models on the host at zero marginal cost and
    # needs no API key. Must be host.docker.internal, not localhost — the
    # backend is containerised and Ollama runs on the host.
    ollama_base_url: str = Field(default="")
    ollama_model: str = Field(default="llama3.1:8b")

    # ── Stripe ────────────────────────────────────────────────
    stripe_secret_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")

    # ── Rate limiting defaults ────────────────────────────────
    sovereign_daily_analysis_limit: int = 10
    elite_voice_minutes_per_month: int = 500

    # ── Phase 3: streaming ────────────────────────────────────
    news_poll_interval_seconds: int = 60
    sentiment_prefilter_threshold: float = 0.05
    agent_llm_calls_per_minute: int = 20

    # ── Backtesting defaults ──────────────────────────────────
    backtest_default_initial_capital: float = 10_000.0
    backtest_default_commission_pct: float = 0.001   # 0.1% per trade, each side
    backtest_default_slippage_pct: float = 0.0005    # 0.05% adverse fill assumption

    # ── Phase 4: voice ────────────────────────────────────────
    voice_session_ttl_seconds: int = 7200  # 2-hour session
    voice_max_context_turns: int = 20       # rolling window of turns kept in memory

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

    @staticmethod
    def _is_real_key(value: str, min_length: int = 24) -> bool:
        """
        Reject placeholder keys as well as empty ones.

        backend/.env ships with illustrative values like `sk-...` and
        `sk-ant-api03-...`. A plain truthiness check treats those as
        configured, so the app makes a doomed API call on every request and
        only discovers the key is fake from the 401. Requiring a plausible
        length and no ellipsis catches every placeholder in the file while
        never rejecting a genuine key, which is far longer.
        """
        v = (value or "").strip()
        return len(v) >= min_length and "..." not in v

    @property
    def anthropic_configured(self) -> bool:
        return self._is_real_key(self.anthropic_api_key, 40)

    @property
    def openai_configured(self) -> bool:
        return self._is_real_key(self.openai_api_key, 40)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
