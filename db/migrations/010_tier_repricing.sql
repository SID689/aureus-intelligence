-- =====================================================================
-- 010_tier_repricing.sql
-- ---------------------------------------------------------------------
-- Reprices the paid tiers around measured vendor cost, and gives each
-- tier a real technical profile (model, data provider, cache, priority)
-- rather than just a bigger number next to the same features.
--
-- =====================================================================
-- THE ARITHMETIC THIS IS FIXING
-- =====================================================================
-- Elite was $50/mo with 200 analyses/day = 6,000/month. Routed through
-- Claude Sonnet at this codebase's actual prompt sizes (~2,500 input /
-- 800 output tokens per thesis), that is ~$0.02 per analysis, or ~$120 a
-- month in LLM cost alone — before voice, before market data. A negative
-- 140% gross margin that gets WORSE the more the customer uses it.
--
-- Two things fix it, and both are needed:
--   1. Caps denominated in cost (credits), not request counts. A Haiku
--      run and an Opus run differ ~19x in price; one counter cannot
--      express both.
--   2. Model tiering. Haiku carries routine synthesis at roughly a
--      quarter of Sonnet's cost; Opus is reserved for deep analysis where
--      the quality difference is visible and the volume is low.
--
-- =====================================================================
-- WHAT EACH CREDIT ALLOWANCE ACTUALLY BUYS
-- =====================================================================
-- 1 credit = $0.001 of BILLED value (vendor cost x markup). At the 3.0x
-- LLM markup seeded in migration 009:
--
--   Haiku thesis   ~15.6 credits   -> Elite's 25,000 ≈ 1,600 runs/month
--   Sonnet thesis  ~58.5 credits   -> Elite's 25,000 ≈   427 runs/month
--   Opus thesis    ~292  credits   -> Instl's 150,000 ≈  510 runs/month
--
-- Real vendor cost behind the allowances: Elite ~$8.33, Institutional
-- ~$50. Against $99 and $499 that is ~92% and ~90% gross margin on
-- variable cost, which is what has to carry the $628/month of fixed
-- vendor subscriptions (see vendor_subscriptions).
--
-- BREAK-EVEN on that fixed floor: ~7 Elite subscribers, or ~2
-- Institutional. Below that the owner is funding the platform, and no
-- amount of payment plumbing changes it — see the treasury module.
--
-- =====================================================================
-- FREE TIER: DELIBERATELY UNCHANGED, WITH ONE HONEST CONSEQUENCE
-- =====================================================================
-- Limits, sources and caps stay exactly as migration 008 set them. But
-- Ollama is being removed from the product, and Ollama was what gave the
-- free tier its optional LLM polish. Free output is therefore now
-- deterministic-only.
--
-- That is not a downgrade worth apologising for: the deterministic
-- thesis engine builds every bullet from a metric that actually
-- computed, with the real number interpolated, and never asserts
-- anything it cannot show. It is the honest version. What free users
-- lose is prose fluency, not substance — and the alternative was paying
-- Anthropic for users who generate no revenue.
-- =====================================================================

BEGIN;

-- ── SOVEREIGN — unchanged limits, no LLM spend ───────────────────────
UPDATE subscription_tiers SET
  monthly_credits        = 0,
  llm_model_default      = NULL,          -- deterministic output only
  llm_model_deep         = NULL,
  market_data_providers  = ARRAY['yfinance'],
  sentiment_sources      = ARRAY['finnhub_free','yahoo','stocktwits'],
  cache_ttl_seconds      = 3600,          -- longest cache: cheapest to serve
  queue_priority         = 1,             -- served last under load
  max_concurrent_jobs    = 1,
  api_keys_allowed       = 0,             -- no programmatic access
  features = features || jsonb_build_object(
    'llm_synthesis', false,
    'deterministic_analysis', true,
    'programmatic_api', false
  )
WHERE tier_name = 'sovereign';

-- ── ELITE — $99/mo ───────────────────────────────────────────────────
-- Analyses/day drops 200 -> 150 and stops being the binding constraint;
-- credits are. The count remains only as an abuse guard.
UPDATE subscription_tiers SET
  price_cents                   = 9900,
  display_name                  = 'Elite',
  monthly_credits               = 25000,      -- $25 billed ≈ $8.33 real
  llm_model_default             = 'claude-haiku',
  llm_model_deep                = 'claude-sonnet',
  market_data_providers         = ARRAY['polygon','finnhub','yfinance'],
  sentiment_sources             = ARRAY['finnhub','yahoo','stocktwits','reddit'],
  cache_ttl_seconds             = 300,        -- 5 min: markedly fresher
  queue_priority                = 5,
  max_concurrent_jobs           = 3,
  api_keys_allowed              = 2,
  max_analysis_requests_per_day = 150,
  voice_minutes_per_month       = 300,        -- credit-metered on top
  features = features || jsonb_build_object(
    'llm_synthesis', true,
    'llm_model', 'Claude Haiku + Sonnet for deep analysis',
    'realtime_market_data', true,
    'programmatic_api', true,
    'priority_queue', true
  )
WHERE tier_name = 'elite';

-- ── INSTITUTIONAL — $499/mo ──────────────────────────────────────────
-- Every premium data source, the strongest model, and the shortest cache.
-- Priced so ~2 subscribers cover the entire $628/month fixed floor.
UPDATE subscription_tiers SET
  price_cents                   = 49900,
  display_name                  = 'Institutional',
  monthly_credits               = 150000,     -- $150 billed ≈ $50 real
  llm_model_default             = 'claude-sonnet',
  llm_model_deep                = 'claude-opus',
  market_data_providers         = ARRAY['polygon_advanced','polygon','finnhub','alphavantage','yfinance'],
  sentiment_sources             = ARRAY['finnhub','yahoo','stocktwits','reddit','x_api','stocktwits_enterprise'],
  cache_ttl_seconds             = 60,         -- near-live
  queue_priority                = 9,          -- served first, always
  max_concurrent_jobs           = 10,
  api_keys_allowed              = 10,
  max_analysis_requests_per_day = NULL,       -- credit-bound only
  voice_minutes_per_month       = NULL,
  features = features || jsonb_build_object(
    'llm_synthesis', true,
    'llm_model', 'Claude Sonnet + Opus for deep analysis',
    'realtime_market_data', true,
    'all_premium_data_sources', true,
    'programmatic_api', true,
    'priority_queue', true,
    'dedicated_concurrency', true
  )
WHERE tier_name = 'institutional';

COMMIT;

-- ── Backfill credit accounts for existing subscribers ────────────────
BEGIN;

INSERT INTO credit_accounts (user_id, allowance_credits, period_start, period_end)
SELECT us.user_id,
       st.monthly_credits,
       date_trunc('month', now()),
       date_trunc('month', now()) + interval '1 month'
  FROM user_subscriptions us
  JOIN subscription_tiers st ON st.id = us.tier_id
 WHERE us.status IN ('active', 'trialing')
ON CONFLICT (user_id) DO UPDATE
  SET allowance_credits = EXCLUDED.allowance_credits;

INSERT INTO credit_transactions (user_id, kind, credits, operation, balance_after, metadata)
SELECT ca.user_id, 'grant', ca.allowance_credits, 'initial_provisioning',
       ca.allowance_credits,
       jsonb_build_object('source', 'migration_010')
  FROM credit_accounts ca
 WHERE ca.allowance_credits > 0;

COMMIT;
