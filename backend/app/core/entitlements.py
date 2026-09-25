"""
app/core/entitlements.py
--------------------------
What a user's plan actually permits, and how much of it they have used.

=====================================================================
WHY THIS REPLACES THE OLD tiers.py
=====================================================================
tiers.py answered one question — "is this user at least Elite?" — which
was enough for a single all-or-nothing gate on the Quant Lab. It is not
enough for real plans, because most limits are not binary. "200 analyses
per day" and "5 tickers per backtest" and "a 15-minute news delay" are
quantities, and they have to come from the database rather than from
constants, or the pricing page and the enforcement drift apart the first
time someone edits a plan.

So everything here resolves from subscription_tiers. Change a number in
the database and the app enforces the new number; nothing is duplicated
in Python.

=====================================================================
THE NULL CONVENTION
=====================================================================
NULL in a limit column means UNLIMITED. It does not mean "unset".

This matters because 0 is a real, different value: the free tier has
voice_minutes_per_month = 0, meaning voice is unavailable, while
Institutional has NULL, meaning uncapped. A naive `limit or default`
would collapse those two into the same behaviour and hand free users
unlimited voice — which is exactly the bug this convention exists to
prevent. Always test `is None`, never truthiness.

=====================================================================
FAILURE POSTURE
=====================================================================
Tier resolution fails CLOSED to sovereign: an unknown user, a missing
subscription, or a database error all yield the least-privileged plan.
A fail-open default would turn any transient outage into free access to
paid features.

Usage metering fails OPEN: if the counter cannot be read or written, the
request proceeds. That asymmetry is deliberate. Failing closed on the
gate protects revenue; failing closed on the meter would mean a Redis
hiccup locks out paying customers who are nowhere near their limit. The
worst case here is a handful of uncounted requests.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Literal

from fastapi import HTTPException, Query
from sqlalchemy import create_engine, text

from app.core.config import get_settings

logger = logging.getLogger("aureus.core.entitlements")

TierName = Literal["sovereign", "plus", "elite", "institutional"]

# Least to most privileged.
_TIER_ORDER: list[str] = ["sovereign", "plus", "elite", "institutional"]

# Tier rows change only when someone edits a plan, so a short cache
# removes a database round-trip from every gated request without making
# a pricing change take meaningfully long to appear.
_TIER_CACHE_TTL = 300


@lru_cache(maxsize=1)
def _engine():
    """One pooled engine per process — this runs on every gated request."""
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)


def tier_rank(tier: str) -> int:
    try:
        return _TIER_ORDER.index((tier or "sovereign").lower())
    except ValueError:
        return 0


def next_tier(tier: str) -> str:
    """
    The plan one step up, for "raise this limit" suggestions.

    Quota messages point here rather than straight at Elite: someone who
    has run out of daily analyses on the free plan wants more volume, and
    Plus sells exactly that for a fraction of the price. Feature gates
    (the Quant Lab, voice, the leaderboard) name their own minimum instead.
    """
    return _TIER_ORDER[min(tier_rank(tier) + 1, len(_TIER_ORDER) - 1)]


# ── The resolved plan ─────────────────────────────────────────────────

@dataclass
class Entitlements:
    """
    A user's complete limit set. Every `max_*` field uses the NULL =
    unlimited convention described in the module docstring.
    """
    tier: str = "sovereign"
    display_name: str = "Sovereign"
    price_cents: int = 0

    max_analysis_requests_per_day: int | None = 15
    max_backtests_per_day: int | None = 3
    max_backtest_tickers: int | None = 1
    max_backtest_years: int | None = 2
    max_portfolio_holdings: int | None = 15
    max_portfolios: int | None = 1
    voice_minutes_per_month: int | None = 0
    news_feed_delay_seconds: int = 900

    quant_lab_enabled: bool = False
    quant_history_years: int | None = None
    quant_monte_carlo_paths: int | None = None
    quant_custom_peers: bool = False

    # Hottest Stocks Leaderboard + Strong Buy alerts (migration 013).
    leaderboard_enabled: bool = False

    max_sentiment_catalysts: int | None = 3
    sec_filing_tone_enabled: bool = False

    # ── Cost/quality/speed profile (migrations 009-010) ──────────────
    # monthly_credits is the real spend ceiling; the request counters
    # above are only a coarse abuse guard now.
    monthly_credits: int = 0
    llm_model_default: str | None = None      # None = deterministic only
    llm_model_deep: str | None = None
    market_data_providers: list = field(default_factory=lambda: ["yfinance"])
    sentiment_sources: list = field(default_factory=lambda: ["finnhub_free", "yahoo", "stocktwits"])
    cache_ttl_seconds: int = 3600
    queue_priority: int = 1
    max_concurrent_jobs: int = 1
    api_keys_allowed: int = 0

    features: dict = field(default_factory=dict)

    def unlimited(self, attr: str) -> bool:
        return getattr(self, attr, None) is None

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "display_name": self.display_name,
            "price_cents": self.price_cents,
            "limits": {
                "analysis_requests_per_day": self.max_analysis_requests_per_day,
                "backtests_per_day": self.max_backtests_per_day,
                "backtest_tickers": self.max_backtest_tickers,
                "backtest_years": self.max_backtest_years,
                "portfolio_holdings": self.max_portfolio_holdings,
                "portfolios": self.max_portfolios,
                "voice_minutes_per_month": self.voice_minutes_per_month,
                "news_feed_delay_seconds": self.news_feed_delay_seconds,
                "sentiment_catalysts": self.max_sentiment_catalysts,
                "quant_history_years": self.quant_history_years,
                "quant_monte_carlo_paths": self.quant_monte_carlo_paths,
                "monthly_credits": self.monthly_credits,
                "cache_ttl_seconds": self.cache_ttl_seconds,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "api_keys_allowed": self.api_keys_allowed,
            },
            "quality": {
                "llm_model_default": self.llm_model_default,
                "llm_model_deep": self.llm_model_deep,
                "market_data_providers": self.market_data_providers,
                "sentiment_sources": self.sentiment_sources,
                "queue_priority": self.queue_priority,
            },
            "features": {
                "quant_lab": self.quant_lab_enabled,
                "quant_custom_peers": self.quant_custom_peers,
                "leaderboard": self.leaderboard_enabled,
                "sec_filing_tone": self.sec_filing_tone_enabled,
                **self.features,
            },
        }


# Free tier as a literal, used when the database cannot answer. Kept in
# sync with migration 008's sovereign row; it is the fail-closed floor,
# so if it drifts it drifts toward LESS access, never more.
_SOVEREIGN_FALLBACK = Entitlements()


def _row_to_entitlements(row) -> Entitlements:
    m = row._mapping
    return Entitlements(
        tier=str(m["tier_name"]),
        display_name=m["display_name"],
        price_cents=int(m["price_cents"] or 0),
        max_analysis_requests_per_day=m["max_analysis_requests_per_day"],
        max_backtests_per_day=m["max_backtests_per_day"],
        max_backtest_tickers=m["max_backtest_tickers"],
        max_backtest_years=m["max_backtest_years"],
        max_portfolio_holdings=m["max_portfolio_holdings"],
        max_portfolios=m["max_portfolios"],
        voice_minutes_per_month=m["voice_minutes_per_month"],
        news_feed_delay_seconds=int(m["news_feed_delay_seconds"] or 0),
        quant_lab_enabled=bool(m["quant_lab_enabled"]),
        quant_history_years=m["quant_history_years"],
        quant_monte_carlo_paths=m["quant_monte_carlo_paths"],
        quant_custom_peers=bool(m["quant_custom_peers"]),
        leaderboard_enabled=bool(m["leaderboard_enabled"]),
        max_sentiment_catalysts=m["max_sentiment_catalysts"],
        sec_filing_tone_enabled=bool(m["sec_filing_tone_enabled"]),
        features=dict(m["features"] or {}),
        monthly_credits=int(m["monthly_credits"] or 0),
        llm_model_default=m["llm_model_default"],
        llm_model_deep=m["llm_model_deep"],
        market_data_providers=list(m["market_data_providers"] or ["yfinance"]),
        sentiment_sources=list(m["sentiment_sources"] or []),
        cache_ttl_seconds=int(m["cache_ttl_seconds"] or 3600),
        queue_priority=int(m["queue_priority"] or 1),
        max_concurrent_jobs=int(m["max_concurrent_jobs"] or 1),
        api_keys_allowed=int(m["api_keys_allowed"] or 0),
    )


_TIER_COLUMNS = """
    tier_name, display_name, price_cents,
    max_analysis_requests_per_day, voice_minutes_per_month, news_feed_delay_seconds,
    max_backtests_per_day, max_backtest_tickers, max_backtest_years,
    max_portfolio_holdings, max_portfolios,
    quant_lab_enabled, quant_history_years, quant_monte_carlo_paths, quant_custom_peers,
    leaderboard_enabled,
    max_sentiment_catalysts, sec_filing_tone_enabled, features,
    monthly_credits, llm_model_default, llm_model_deep,
    market_data_providers, sentiment_sources,
    cache_ttl_seconds, queue_priority, max_concurrent_jobs, api_keys_allowed
"""


def _cache_key(user_id: str) -> str:
    return f"entitlements:{user_id}"


def resolve_entitlements(user_id: str, use_cache: bool = True) -> Entitlements:
    """
    The user's plan. Falls back to sovereign on any failure (see the
    module docstring on failure posture).
    """
    if use_cache:
        try:
            import json
            from app.core.redis_client import get_redis_client
            raw = get_redis_client().get(_cache_key(user_id))
            if raw:
                d = json.loads(raw)
                return Entitlements(**d)
        except Exception:
            pass

    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text(f"""
                    SELECT {_TIER_COLUMNS}
                      FROM active_user_subscriptions us
                      JOIN subscription_tiers st ON st.id = us.tier_id
                     WHERE us.user_id = :uid
                     ORDER BY us.created_at DESC
                     LIMIT 1
                """),
                {"uid": user_id},
            ).fetchone()
            if row is None:
                # No subscription row at all — treat as the free plan, and
                # read its real limits rather than the literal fallback so
                # a pricing edit still applies to signed-up-but-unbilled
                # users, who are the majority of a freemium base.
                row = conn.execute(
                    text(f"SELECT {_TIER_COLUMNS} FROM subscription_tiers WHERE tier_name = 'sovereign'")
                ).fetchone()
    except Exception as exc:
        logger.warning("Entitlement resolution failed, defaulting to sovereign",
                       extra={"user_id": user_id, "error": str(exc)})
        return _SOVEREIGN_FALLBACK

    if row is None:
        return _SOVEREIGN_FALLBACK

    ent = _row_to_entitlements(row)
    try:
        import json
        from dataclasses import asdict
        from app.core.redis_client import get_redis_client
        get_redis_client().setex(_cache_key(user_id), _TIER_CACHE_TTL, json.dumps(asdict(ent)))
    except Exception:
        pass
    return ent


def invalidate_entitlements(user_id: str) -> None:
    """
    Drop a user's cached plan.

    Must be called whenever a subscription changes, or an upgrade takes
    up to _TIER_CACHE_TTL to take effect — which reads to the customer as
    "I paid and nothing happened".
    """
    try:
        from app.core.redis_client import get_redis_client
        get_redis_client().delete(_cache_key(user_id))
    except Exception:
        pass


# ── Usage metering ────────────────────────────────────────────────────

CounterType = Literal["analysis_request", "voice_minute", "backtest_run"]


def _period_key(counter_type: str) -> str:
    """
    Daily buckets for request counters, monthly for voice.

    UTC, deliberately: a local-timezone bucket lets someone reset their
    daily quota by changing their clock, and makes the reset time
    ambiguous for anyone travelling.
    """
    now = datetime.now(tz=timezone.utc)
    if counter_type == "voice_minute":
        return now.strftime("%Y-%m")
    return now.strftime("%Y-%m-%d")


def get_usage(user_id: str, counter_type: CounterType) -> float:
    """Current period's usage. Returns 0.0 on any failure (fails open)."""
    try:
        with _engine().connect() as conn:
            row = conn.execute(
                text("""
                    SELECT count_value FROM usage_counters
                     WHERE user_id = :uid AND counter_type = :ct AND period_key = :pk
                """),
                {"uid": user_id, "ct": counter_type, "pk": _period_key(counter_type)},
            ).fetchone()
        return float(row[0]) if row else 0.0
    except Exception as exc:
        logger.warning("Usage read failed, treating as zero",
                       extra={"user_id": user_id, "counter": counter_type, "error": str(exc)})
        return 0.0


def record_usage(user_id: str, counter_type: CounterType, amount: float = 1.0) -> None:
    """
    Increment a counter atomically.

    UPSERT with `count_value = usage_counters.count_value + :amt` rather
    than a read-modify-write, so two concurrent requests cannot both read
    N and both write N+1. The unique constraint on
    (user_id, counter_type, period_key) is what makes the conflict target
    valid.
    """
    try:
        with _engine().begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO usage_counters (user_id, counter_type, period_key, count_value)
                    VALUES (:uid, :ct, :pk, :amt)
                    ON CONFLICT (user_id, counter_type, period_key)
                    DO UPDATE SET count_value = usage_counters.count_value + :amt,
                                  updated_at  = now()
                """),
                {"uid": user_id, "ct": counter_type, "pk": _period_key(counter_type), "amt": amount},
            )
    except Exception as exc:
        logger.warning("Usage write failed: request still served",
                       extra={"user_id": user_id, "counter": counter_type, "error": str(exc)})


def usage_summary(user_id: str, ent: Entitlements) -> dict:
    """Usage against limits, for the account/usage panel."""
    def block(counter: CounterType, limit: int | None, unit: str) -> dict:
        used = get_usage(user_id, counter)
        return {
            "used": used,
            "limit": limit,
            "unlimited": limit is None,
            "remaining": None if limit is None else max(0.0, limit - used),
            "exceeded": limit is not None and used >= limit,
            "unit": unit,
            "resets": "daily (UTC)" if counter != "voice_minute" else "monthly (UTC)",
        }

    return {
        "analysis": block("analysis_request", ent.max_analysis_requests_per_day, "runs"),
        "backtest": block("backtest_run", ent.max_backtests_per_day, "runs"),
        "voice": block("voice_minute", ent.voice_minutes_per_month, "minutes"),
    }


# ── Enforcement ───────────────────────────────────────────────────────

def _quota_error(kind: str, used: float, limit: int, ent: Entitlements, unit: str, period: str):
    """
    402 with everything the client needs to render a useful prompt.

    402 Payment Required, not 403 Forbidden: the caller is properly
    authenticated and simply out of quota on their plan, and 402 is what
    tells a client to offer an upgrade rather than show an access error.
    """
    upgrade = next_tier(ent.tier)
    return HTTPException(
        status_code=402,
        detail={
            "error": "quota_exceeded",
            "resource": kind,
            "message": (
                f"You've used {used:.0f} of {limit} {unit} on the {ent.display_name} plan "
                f"({period}). Upgrade to {upgrade.title()} for a higher limit."
            ),
            "used": used,
            "limit": limit,
            "unit": unit,
            "resets": period,
            "current_tier": ent.tier,
            "suggested_tier": upgrade,
        },
    )


def feature_error(feature: str, required: str, ent: Entitlements):
    return HTTPException(
        status_code=402,
        detail={
            "error": "tier_required",
            "feature": feature,
            "message": (
                f"{feature} requires the {required.title()} plan or above. "
                f"Your current plan is {ent.display_name}."
            ),
            "current_tier": ent.tier,
            "required_tier": required,
            "suggested_tier": required,
        },
    )


def check_quota(user_id: str, ent: Entitlements, counter: CounterType,
                kind: str, unit: str) -> None:
    """Raise 402 if the user is at or over their limit for this counter."""
    limit = {
        "analysis_request": ent.max_analysis_requests_per_day,
        "backtest_run": ent.max_backtests_per_day,
        "voice_minute": ent.voice_minutes_per_month,
    }[counter]
    if limit is None:          # unlimited — see the NULL convention
        return
    used = get_usage(user_id, counter)
    if used >= limit:
        period = "resets monthly" if counter == "voice_minute" else "resets daily at 00:00 UTC"
        raise _quota_error(kind, used, limit, ent, unit, period)


# ── FastAPI dependencies ──────────────────────────────────────────────

def current_entitlements(user_id: str = Query(..., min_length=1)) -> Entitlements:
    """Resolve the caller's plan from a `user_id` query parameter.

    Identity comes from the client; ENTITLEMENTS come from the database.
    A client cannot promote itself by editing a request, because no limit
    is ever read from one.
    """
    return resolve_entitlements(user_id)


def require_feature(attr: str, label: str, required_tier: str = "elite"):
    """
    Dependency factory gating a boolean feature flag on the plan.

        dependencies=[Depends(require_feature("quant_lab_enabled", "The Quant Lab"))]
    """
    def _dep(user_id: str = Query(..., min_length=1)) -> Entitlements:
        ent = resolve_entitlements(user_id)
        if not getattr(ent, attr, False):
            raise feature_error(label, required_tier, ent)
        return ent
    return _dep


def require_tier(minimum: TierName):
    """Kept for callers that need a plain rank comparison."""
    def _dep(user_id: str = Query(..., min_length=1)) -> str:
        ent = resolve_entitlements(user_id)
        if tier_rank(ent.tier) < tier_rank(minimum):
            raise feature_error("This feature", minimum, ent)
        return ent.tier
    return _dep


def resolve_user_tier(user_id: str) -> str:
    """Backwards-compatible helper — the tier name alone."""
    return resolve_entitlements(user_id).tier
