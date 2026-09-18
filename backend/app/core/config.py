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

    # ── Web Push (VAPID) ──────────────────────────────────────────────
    # Generated per environment. The public key is served to browsers;
    # the private key signs push requests and must never leave the server.
    vapid_public_key: str = Field(default="")
    vapid_private_key: str = Field(default="")
    vapid_claim_sub: str = Field(default="mailto:push-admin@example.invalid")

    # ── Price cache ───────────────────────────────────────────────────
    # See app/ingestion/price_cache.py. Collapses repeated quotes for the
    # same ticker into one provider call.
    price_cache_seconds: int = Field(default=60)
    demo_price_cache_seconds: int = Field(default=900)

    # ── CORS ──────────────────────────────────────────────────────────
    # Comma-separated. Production used to hardcode one hostname, which
    # meant any other deployment — a demo on a tunnel, a staging host, a
    # preview URL — silently refused every browser call it did not proxy
    # server-side. The default keeps the previous behaviour.
    cors_allowed_origins: str = Field(default="")

    # ── Institutional Demo Mode ──────────────────────────────────────
    # A presentation environment. When on, POST /api/v1/demo/session
    # provisions a throwaway account on the top plan, and the analysis
    # endpoints will serve a bundled showcase payload rather than fail
    # when a provider is unreachable.
    #
    # Off by default, and deliberately not derived from app_env: a demo
    # deployment IS production as far as every other setting is
    # concerned, and a real production deployment must not hand out free
    # Institutional accounts because someone set APP_ENV wrong.
    demo_mode: bool = Field(default=False)

    # The plan a demo session is provisioned on.
    demo_tier: str = Field(default="institutional", pattern="^(sovereign|plus|elite|institutional)$")

    # Credit allowance granted to each demo session. Enough for a couple
    # of LLM-polished theses per visitor, not enough for one phone to
    # spend the whole event's budget.
    demo_credit_allowance: int = Field(default=2_000)

    # How long a completed analysis stays servable to other visitors.
    # The whole audience asking for AAPL should cost one pipeline run,
    # not one per phone: without this every device pays full provider
    # latency and the rate limits go first.
    demo_analysis_cache_seconds: int = Field(default=6 * 3600)

    # Non-demo deployments get the same warm cache, just briefly, so a
    # double-click or a remount does not re-run the pipeline.
    analysis_cache_seconds: int = Field(default=180)

    # ── Market scanner ───────────────────────────────────────────────
    # A single switch so an environment on a shared or tightly-limited API
    # key can run the rest of the platform without the background sweep.
    scanner_enabled: bool = Field(default=True)

    # ── Local LLM ────────────────────────────────────────────
    # Ollama was removed when the paid tiers launched. It was correct for
    # a single-user local app and wrong for a product: several GB of
    # resident RAM per concurrent request on a server the owner pays for,
    # output quality below what a $99/month plan implies, and no way to
    # measure what a call cost — which a billed tier has to know.
    # See app/analysis/llm_provider.py.

    # ── Sentiment pillar ──────────────────────────────────────
    # "lexicon" (default) uses the finance-domain lexicon in
    # app/sentiment/lexicon.py — zero dependencies, no download, and
    # genuinely strong on headline-length text. "finbert" switches to
    # ProsusAI/finbert, which needs transformers+torch installed and
    # pulls ~440MB on first use; it falls back to the lexicon by itself
    # if those aren't present, so setting it is never fatal.
    sentiment_model: str = Field(default="lexicon", pattern="^(lexicon|finbert)$")
    # How far back news is gathered for the news sub-score. 7 days keeps
    # the pillar responsive to catalysts; older articles are already
    # reflected in price and mostly add drift.
    sentiment_news_lookback_days: int = 7
    # Social sources are noisier than news by a wide margin and are the
    # main vector for coordinated manipulation, so they are capped at a
    # minority of the blend no matter how loud they get.
    sentiment_max_social_weight: float = 0.30
    # Minimum scored documents before the news sub-score is trusted at
    # all. Below this, one article would set the whole pillar.
    sentiment_min_documents: int = 3

    # ── Quant Lab ─────────────────────────────────────────────
    quant_monte_carlo_paths: int = 10_000
    quant_var_confidence: float = 0.95

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
    def cors_origins(self) -> list[str]:
        explicit = [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
        if explicit:
            return explicit
        if self.is_production:
            return ["https://app.aureusintelligence.com"]
        return ["http://localhost:3000"]

    @property
    def price_cache_ttl(self) -> int:
        return self.demo_price_cache_seconds if self.demo_mode else self.price_cache_seconds

    @property
    def analysis_cache_ttl(self) -> int:
        """Warm-cache lifetime for a completed analysis, by environment."""
        return self.demo_analysis_cache_seconds if self.demo_mode else self.analysis_cache_seconds

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
