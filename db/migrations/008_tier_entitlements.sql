-- =====================================================================
-- 008_tier_entitlements.sql
-- ---------------------------------------------------------------------
-- Makes the subscription tiers mean something.
--
-- STARTING STATE
-- ---------------------------------------------------------------------
-- subscription_tiers already carried max_analysis_requests_per_day,
-- voice_minutes_per_month and news_feed_delay_seconds, and NOT ONE of
-- them was read by any code. Every tier had identical real-world access:
-- a free account could run unlimited analyses, unlimited backtests, and
-- see real-time news. The only genuine gate in the application was the
-- Quant Lab check added with the sentiment refactor.
--
-- The `features` JSONB was worse than unused — it was wrong. It
-- advertised live_execution, direct_alpaca and paper_trading_only, all of
-- which were deleted when agentic execution was removed, as was
-- supports_human_in_loop_alerts. The billing UI was selling four
-- capabilities with zero implementing files.
--
-- WHAT THIS MIGRATION DOES
-- ---------------------------------------------------------------------
-- 1. Adds the limit columns the app actually needs to meter.
-- 2. Extends usage_counter_type so backtests can be counted.
-- 3. Rewrites all three tier rows with limits that match what exists.
--
-- CONVENTION: NULL means UNLIMITED, not "unset". Every limit column is
-- nullable for exactly this reason, and app/core/entitlements.py treats
-- NULL as no cap. A 0 means genuinely zero (e.g. voice on the free tier),
-- which is a different statement and must stay distinguishable.
--
-- Idempotent: safe to re-run.
-- =====================================================================

BEGIN;

-- ── 1. New limit columns ─────────────────────────────────────────────
ALTER TABLE subscription_tiers
  ADD COLUMN IF NOT EXISTS max_backtests_per_day        INTEGER,
  ADD COLUMN IF NOT EXISTS max_backtest_tickers         INTEGER,
  ADD COLUMN IF NOT EXISTS max_backtest_years           INTEGER,
  ADD COLUMN IF NOT EXISTS max_portfolio_holdings       INTEGER,
  ADD COLUMN IF NOT EXISTS max_portfolios               INTEGER,
  -- Quant Lab: gated by flag, then scaled by these once inside.
  ADD COLUMN IF NOT EXISTS quant_lab_enabled            BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS quant_history_years          INTEGER,
  ADD COLUMN IF NOT EXISTS quant_monte_carlo_paths      INTEGER,
  ADD COLUMN IF NOT EXISTS quant_custom_peers           BOOLEAN NOT NULL DEFAULT false,
  -- Sentiment pillar depth. The pillar SCORE is available to everyone —
  -- withholding it would make the headline number unexplainable — but the
  -- research depth behind it is a paid feature.
  ADD COLUMN IF NOT EXISTS max_sentiment_catalysts      INTEGER,
  ADD COLUMN IF NOT EXISTS sec_filing_tone_enabled      BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN subscription_tiers.max_analysis_requests_per_day IS
  'NULL = unlimited. Metered in usage_counters as analysis_request.';
COMMENT ON COLUMN subscription_tiers.max_backtests_per_day IS
  'NULL = unlimited. Metered in usage_counters as backtest_run.';
COMMENT ON COLUMN subscription_tiers.news_feed_delay_seconds IS
  'Articles newer than this are withheld from the feed. 0 = real time.';

-- ── 2. Count backtests ───────────────────────────────────────────────
-- Backtests are the second-most expensive user action after voice: each
-- run pulls multi-year bars per ticker and replays them, so it needs its
-- own meter rather than being folded into analysis_request.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_enum e
    JOIN pg_type t ON t.oid = e.enumtypid
    WHERE t.typname = 'usage_counter_type' AND e.enumlabel = 'backtest_run'
  ) THEN
    ALTER TYPE usage_counter_type ADD VALUE 'backtest_run';
  END IF;
END$$;

COMMIT;

-- ALTER TYPE ... ADD VALUE cannot be used in the same transaction that
-- created it on older servers, so the data rewrite gets its own block.
BEGIN;

-- ── 3. Tier definitions that match the product ───────────────────────
--
-- SOVEREIGN (free). Enough to genuinely evaluate the analysis engine —
-- 15 full three-pillar runs a day is real use, not a teaser — while the
-- expensive research surfaces stay closed. News runs on the standard
-- 15-minute delay that free market-data tiers universally carry.
UPDATE subscription_tiers SET
  display_name                  = 'Sovereign',
  max_analysis_requests_per_day = 15,
  voice_minutes_per_month       = 0,
  news_feed_delay_seconds       = 900,
  max_backtests_per_day         = 3,
  max_backtest_tickers          = 1,
  max_backtest_years            = 2,
  max_portfolio_holdings        = 15,
  max_portfolios                = 1,
  quant_lab_enabled             = false,
  quant_history_years           = NULL,
  quant_monte_carlo_paths       = NULL,
  quant_custom_peers            = false,
  max_sentiment_catalysts       = 3,
  sec_filing_tone_enabled       = false,
  supports_human_in_loop_alerts = false,
  features = jsonb_build_object(
    'real_time_data', false,
    'education_full_access', true,
    'games_full_access', true,
    'three_pillar_analysis', true
  )
WHERE tier_name = 'sovereign';

-- ELITE. The working tier: unlimited-in-practice analysis, real-time
-- news, the Quant Lab, and metered voice. Voice stays capped because it
-- is the only feature with a hard per-minute vendor cost.
UPDATE subscription_tiers SET
  display_name                  = 'Elite',
  max_analysis_requests_per_day = 200,
  voice_minutes_per_month       = 500,
  news_feed_delay_seconds       = 0,
  max_backtests_per_day         = 50,
  max_backtest_tickers          = 5,
  max_backtest_years            = 10,
  max_portfolio_holdings        = 150,
  max_portfolios                = 5,
  quant_lab_enabled             = true,
  quant_history_years           = 3,
  quant_monte_carlo_paths       = 10000,
  quant_custom_peers            = false,
  max_sentiment_catalysts       = NULL,
  sec_filing_tone_enabled       = true,
  supports_human_in_loop_alerts = false,
  features = jsonb_build_object(
    'real_time_data', true,
    'education_full_access', true,
    'games_full_access', true,
    'three_pillar_analysis', true,
    'quant_lab', true,
    'sec_filing_tone', true,
    'strategy_backtesting', true,
    'voice_interface', true
  )
WHERE tier_name = 'elite';

-- INSTITUTIONAL. Everything uncapped, plus the research depth that only
-- matters at size: a decade of factor history, 5x the simulation paths,
-- and custom peer sets for relative-value work.
UPDATE subscription_tiers SET
  display_name                  = 'Institutional',
  max_analysis_requests_per_day = NULL,
  voice_minutes_per_month       = NULL,
  news_feed_delay_seconds       = 0,
  max_backtests_per_day         = NULL,
  max_backtest_tickers          = 25,
  max_backtest_years            = NULL,
  max_portfolio_holdings        = NULL,
  max_portfolios                = NULL,
  quant_lab_enabled             = true,
  quant_history_years           = 10,
  quant_monte_carlo_paths       = 50000,
  quant_custom_peers            = true,
  max_sentiment_catalysts       = NULL,
  sec_filing_tone_enabled       = true,
  supports_human_in_loop_alerts = false,   -- HITL was removed from the product
  features = jsonb_build_object(
    'real_time_data', true,
    'education_full_access', true,
    'games_full_access', true,
    'three_pillar_analysis', true,
    'quant_lab', true,
    'quant_custom_peers', true,
    'sec_filing_tone', true,
    'strategy_backtesting', true,
    'voice_interface', true,
    'unlimited_analysis', true,
    'extended_factor_history', true
  )
WHERE tier_name = 'institutional';

-- Usage lookups are always "this user, this counter, this period".
CREATE INDEX IF NOT EXISTS idx_usage_counters_lookup
  ON usage_counters(user_id, counter_type, period_key);

COMMIT;
