-- 014_plus_tier.sql
--
-- A fourth plan, Plus, between the free Sovereign tier and Elite.
--
-- WHY IT SITS WHERE IT DOES
-- The gap between free and $99 was the widest step in the price ladder
-- and the one most people fall into: someone who has outgrown fifteen
-- analyses a day is rarely ready for the Quant Lab and voice. Plus buys
-- volume and written synthesis, and nothing that costs this platform real
-- money per user (real-time quotes, voice minutes, the market scanner).
--
-- EVERY ADVERTISED DIFFERENCE IS A COLUMN
-- The pricing page renders its matrix from what this row enforces. Do not
-- describe Plus anywhere with a benefit that has no column or flag here.
--
-- Run WITHOUT a wrapping transaction: Postgres does not allow a newly
-- added enum value to be used in the transaction that added it. psql -f
-- commits each statement on its own, which is what this file relies on.

ALTER TYPE subscription_tier_name ADD VALUE IF NOT EXISTS 'plus' BEFORE 'elite';

INSERT INTO subscription_tiers (
    tier_name, display_name, price_cents, billing_interval,
    max_analysis_requests_per_day, voice_minutes_per_month, news_feed_delay_seconds,
    model_tier, supports_human_in_loop_alerts, features, is_active,
    max_backtests_per_day, max_backtest_tickers, max_backtest_years,
    max_portfolio_holdings, max_portfolios,
    quant_lab_enabled, quant_history_years, quant_monte_carlo_paths, quant_custom_peers,
    max_sentiment_catalysts, sec_filing_tone_enabled,
    monthly_credits, llm_model_default, llm_model_deep,
    market_data_providers, sentiment_sources,
    cache_ttl_seconds, queue_priority, max_concurrent_jobs, api_keys_allowed,
    leaderboard_enabled
) VALUES (
    'plus', 'Plus', 1200, 'monthly',
    50, 0, 60,
    'basic', FALSE,
    '{"three_pillar_analysis": true, "deterministic_analysis": true, "llm_synthesis": true,
      "llm_model": "Claude Haiku", "sec_filing_tone": true, "strategy_backtesting": true,
      "education_full_access": true, "games_full_access": true,
      "real_time_data": false, "quant_lab": false, "voice_interface": false,
      "leaderboard_alerts": false, "programmatic_api": false}'::jsonb,
    TRUE,
    10, 2, 5,
    50, 2,
    FALSE, NULL, NULL, FALSE,
    10, TRUE,
    3000, 'claude-haiku', NULL,
    ARRAY['finnhub', 'yfinance'], ARRAY['finnhub', 'yahoo', 'stocktwits'],
    900, 3, 1, 0,
    FALSE
)
ON CONFLICT (tier_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    price_cents = EXCLUDED.price_cents,
    billing_interval = EXCLUDED.billing_interval,
    max_analysis_requests_per_day = EXCLUDED.max_analysis_requests_per_day,
    voice_minutes_per_month = EXCLUDED.voice_minutes_per_month,
    news_feed_delay_seconds = EXCLUDED.news_feed_delay_seconds,
    model_tier = EXCLUDED.model_tier,
    features = EXCLUDED.features,
    max_backtests_per_day = EXCLUDED.max_backtests_per_day,
    max_backtest_tickers = EXCLUDED.max_backtest_tickers,
    max_backtest_years = EXCLUDED.max_backtest_years,
    max_portfolio_holdings = EXCLUDED.max_portfolio_holdings,
    max_portfolios = EXCLUDED.max_portfolios,
    quant_lab_enabled = EXCLUDED.quant_lab_enabled,
    max_sentiment_catalysts = EXCLUDED.max_sentiment_catalysts,
    sec_filing_tone_enabled = EXCLUDED.sec_filing_tone_enabled,
    monthly_credits = EXCLUDED.monthly_credits,
    llm_model_default = EXCLUDED.llm_model_default,
    llm_model_deep = EXCLUDED.llm_model_deep,
    market_data_providers = EXCLUDED.market_data_providers,
    sentiment_sources = EXCLUDED.sentiment_sources,
    cache_ttl_seconds = EXCLUDED.cache_ttl_seconds,
    queue_priority = EXCLUDED.queue_priority,
    max_concurrent_jobs = EXCLUDED.max_concurrent_jobs,
    api_keys_allowed = EXCLUDED.api_keys_allowed,
    leaderboard_enabled = EXCLUDED.leaderboard_enabled;
