-- =====================================================================
-- 009_credits_keys_treasury.sql
-- ---------------------------------------------------------------------
-- Three related systems: cost-denominated credits, platform-issued API
-- keys, and a treasury ledger that reconciles revenue against real
-- vendor spend.
--
-- =====================================================================
-- WHY CREDITS RATHER THAN REQUEST COUNTS
-- =====================================================================
-- Migration 008 metered requests: "200 analyses per day". That is the
-- right shape when every request costs the same, and the wrong shape the
-- moment a paid LLM is involved, because two analyses can differ by 50x
-- in vendor cost. A deterministic run on cached bars costs nothing; the
-- same ticker with an Opus-authored thesis and a fresh Polygon pull costs
-- real money.
--
-- Measured on this codebase's own prompts: a thesis synthesis is roughly
-- 2,500 input + 800 output tokens. On Claude Sonnet that is about $0.02.
-- At the Elite cap of 200/day = 6,000/month, that single feature costs
-- ~$120/month against a $50 plan. Counting requests cannot express that,
-- so the cap has to be denominated in the thing that actually varies.
--
-- UNIT: 1 credit = $0.001 (one tenth of a US cent) of underlying vendor
-- cost. 1,000 credits = $1.00. Chosen so the smallest meaningful vendor
-- charge (a Haiku call, ~$0.0005) is at least half a credit rather than
-- rounding to zero, and so an allowance reads as a plain number rather
-- than a fraction.
--
-- Balances are NUMERIC, never floating point. Money-like quantities that
-- accumulate over thousands of small debits drift under binary floats,
-- and a drifting balance is a billing dispute.
--
-- =====================================================================
-- WHY USERS NEVER RECEIVE UPSTREAM VENDOR KEYS
-- =====================================================================
-- "How do they run the software on their own" has a tempting wrong
-- answer: hand each subscriber an Anthropic/Polygon key. Three reasons
-- that is not done here:
--   1. It violates those vendors' terms — keys are not redistributable.
--   2. A leaked key bills the platform owner without limit and cannot be
--      attributed to the user who leaked it.
--   3. It destroys metering entirely: usage would bypass this database.
-- Instead the platform issues its OWN keys (aur_live_...), scoped to one
-- user, revocable, and debited against that user's credit balance on
-- every call. The user gets programmatic access to Aureus; Aureus keeps
-- a single relationship with each vendor.
--
-- Idempotent: safe to re-run.
-- =====================================================================

BEGIN;

-- ── 1. Credit balances ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS credit_accounts (
  user_id               UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  -- Credits granted by the current subscription period, reset on renewal.
  allowance_credits     NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (allowance_credits >= 0),
  consumed_credits      NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (consumed_credits >= 0),
  -- Purchased top-ups. Deliberately separate from the allowance: these
  -- are paid for outside the subscription and must NOT be wiped by the
  -- monthly reset, or a customer loses credits they bought.
  purchased_credits     NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (purchased_credits >= 0),
  period_start          TIMESTAMPTZ NOT NULL DEFAULT now(),
  period_end            TIMESTAMPTZ,
  -- Hard stop. When false, a user at zero credits is refused rather than
  -- allowed to overspend the plan they paid for.
  allow_overage         BOOLEAN NOT NULL DEFAULT false,
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE credit_accounts IS
  '1 credit = $0.001 of underlying vendor cost. allowance resets each billing '
  'period; purchased_credits survive the reset.';

-- ── 2. Immutable ledger ──────────────────────────────────────────────
-- Append-only. The balance above is a materialised convenience; this is
-- the record of truth, and it is what makes a disputed bill answerable.
DO $$ BEGIN
  CREATE TYPE credit_txn_kind AS ENUM ('grant', 'debit', 'refund', 'purchase', 'expiry', 'adjustment');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS credit_transactions (
  id                    BIGSERIAL PRIMARY KEY,
  user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind                  credit_txn_kind NOT NULL,
  -- Positive adds, negative removes. Signed so the ledger sums to the
  -- balance without needing to know each kind's direction.
  credits               NUMERIC(14,3) NOT NULL,
  -- What produced the charge: 'anthropic', 'openai_tts', 'polygon', ...
  vendor                TEXT,
  operation             TEXT,
  -- The real money this represents, kept alongside the credit figure so
  -- a rate change later cannot retroactively rewrite what was spent.
  usd_cost              NUMERIC(12,6),
  -- Vendor-reported units (tokens, minutes, calls) for auditability.
  quantity              NUMERIC(14,3),
  unit                  TEXT,
  balance_after         NUMERIC(14,3),
  request_id            TEXT,
  metadata              JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_credit_txn_user_time
  ON credit_transactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_txn_vendor_time
  ON credit_transactions(vendor, created_at DESC);

-- Idempotency for retried charges: a request_id may be billed once.
CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_txn_request
  ON credit_transactions(user_id, request_id) WHERE request_id IS NOT NULL;

-- ── 3. Vendor cost rates ─────────────────────────────────────────────
-- What each vendor unit costs, in one place. Rates live in the database
-- rather than in Python constants so a vendor price change is a row
-- update, not a redeploy — and so historical ledger rows keep the rate
-- that was actually in force via credit_transactions.usd_cost.
CREATE TABLE IF NOT EXISTS vendor_cost_rates (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor                TEXT NOT NULL,
  operation             TEXT NOT NULL,
  unit                  TEXT NOT NULL,          -- 'input_token','output_token','minute','call'
  usd_per_unit          NUMERIC(16,10) NOT NULL CHECK (usd_per_unit >= 0),
  -- Multiplier applied on top of raw cost before debiting the user.
  -- Covers the margin and the fixed subscriptions that per-call pricing
  -- does not capture. 1.0 bills at cost.
  markup_multiplier     NUMERIC(6,3) NOT NULL DEFAULT 1.0 CHECK (markup_multiplier > 0),
  effective_from        TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active             BOOLEAN NOT NULL DEFAULT true,
  notes                 TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_vendor_rate_active
  ON vendor_cost_rates(vendor, operation, unit) WHERE is_active;

-- ── 4. Platform-issued API keys ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS api_keys (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  -- SHA-256 of the secret. The plaintext key is shown exactly once, at
  -- creation, and never stored — the same reason a password is not.
  key_hash              TEXT NOT NULL UNIQUE,
  -- First and last few characters, for display: "aur_live_4f2a…9c1d".
  key_prefix            TEXT NOT NULL,
  name                  TEXT NOT NULL DEFAULT 'Default key',
  environment           TEXT NOT NULL DEFAULT 'live' CHECK (environment IN ('live', 'test')),
  scopes                TEXT[] NOT NULL DEFAULT ARRAY['analysis:read'],
  last_used_at          TIMESTAMPTZ,
  request_count         BIGINT NOT NULL DEFAULT 0,
  revoked_at            TIMESTAMPTZ,
  revoked_reason        TEXT,
  expires_at            TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
-- Lookup on every authenticated API call, so it must be a single index hit.
CREATE INDEX IF NOT EXISTS idx_api_keys_active_hash
  ON api_keys(key_hash) WHERE revoked_at IS NULL;

-- ── 5. Stripe event log (idempotency) ────────────────────────────────
-- Stripe guarantees at-least-once delivery, so the same event can and
-- does arrive twice. Without this, a duplicate checkout.session.completed
-- grants a second month of credits for one payment.
CREATE TABLE IF NOT EXISTS stripe_events (
  event_id              TEXT PRIMARY KEY,
  event_type            TEXT NOT NULL,
  processed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  status                TEXT NOT NULL DEFAULT 'processed',
  error                 TEXT,
  payload_summary       JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_stripe_events_time ON stripe_events(processed_at DESC);

-- ── 6. Treasury: what the platform actually spends ───────────────────
-- Two shapes of vendor cost, and conflating them is the mistake that
-- makes "zero out-of-pocket" look automatable when it is not:
--
--   FIXED    a monthly subscription (Polygon, Finnhub, X API). Costs the
--            same with 0 subscribers as with 1,000. This is the floor
--            that must be covered before any margin exists.
--   VARIABLE per-token / per-minute usage (Anthropic, OpenAI). Scales
--            with subscribers and is genuinely covered by their payments.
--
-- Only variable cost is self-funding. Fixed cost requires a minimum
-- subscriber count, which is a business milestone, not a code path.
CREATE TABLE IF NOT EXISTS vendor_subscriptions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor                TEXT NOT NULL UNIQUE,
  plan_name             TEXT NOT NULL,
  cost_type             TEXT NOT NULL CHECK (cost_type IN ('fixed', 'variable', 'hybrid')),
  monthly_usd           NUMERIC(12,2) NOT NULL DEFAULT 0,
  -- Which tier this vendor's data is exposed to. Lets the app answer
  -- "we have 3 Institutional subscribers, does that cover X API yet".
  required_for_tier     TEXT,
  is_subscribed         BOOLEAN NOT NULL DEFAULT false,
  billing_day           INTEGER CHECK (billing_day BETWEEN 1 AND 28),
  renews_at             TIMESTAMPTZ,
  notes                 TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Actual money in and out, for reconciliation against Stripe.
CREATE TABLE IF NOT EXISTS treasury_ledger (
  id                    BIGSERIAL PRIMARY KEY,
  direction             TEXT NOT NULL CHECK (direction IN ('inflow', 'outflow')),
  category              TEXT NOT NULL,   -- 'subscription_revenue','vendor_fixed','vendor_variable','stripe_fee'
  vendor                TEXT,
  usd_amount            NUMERIC(14,2) NOT NULL,
  occurred_on           DATE NOT NULL DEFAULT CURRENT_DATE,
  stripe_reference      TEXT,
  notes                 TEXT,
  metadata              JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_treasury_month
  ON treasury_ledger(occurred_on DESC, direction);

COMMIT;


-- =====================================================================
-- Seed data
-- =====================================================================
BEGIN;

-- Vendor rates. usd_per_unit is list price at the time of writing and
-- MUST be verified against each vendor's current pricing page — these
-- change, and a stale rate silently under-bills.
--
-- markup_multiplier carries the gross margin AND amortises the fixed
-- subscriptions that per-token pricing cannot express. 3.0 on LLM calls
-- means a $0.02 synthesis debits $0.06 of the customer's allowance.
INSERT INTO vendor_cost_rates (vendor, operation, unit, usd_per_unit, markup_multiplier, notes) VALUES
  ('anthropic', 'claude-haiku',   'input_token',  0.00000080, 3.0, 'Haiku 4.5 list ~$0.80/M in — verify'),
  ('anthropic', 'claude-haiku',   'output_token', 0.00000400, 3.0, 'Haiku 4.5 list ~$4/M out — verify'),
  ('anthropic', 'claude-sonnet',  'input_token',  0.00000300, 3.0, 'Sonnet list ~$3/M in — verify'),
  ('anthropic', 'claude-sonnet',  'output_token', 0.00001500, 3.0, 'Sonnet list ~$15/M out — verify'),
  ('anthropic', 'claude-opus',    'input_token',  0.00001500, 3.0, 'Opus list ~$15/M in — verify'),
  ('anthropic', 'claude-opus',    'output_token', 0.00007500, 3.0, 'Opus list ~$75/M out — verify'),
  ('openai',    'whisper-stt',    'minute',       0.00600000, 3.0, 'Whisper $0.006/min — verify'),
  ('openai',    'tts',            'character',    0.00001500, 3.0, 'TTS ~$15/M chars — verify'),
  ('polygon',   'aggregates',     'call',         0.00050000, 2.0, 'Amortised from flat plan; not per-call billed'),
  ('finnhub',   'company-news',   'call',         0.00050000, 2.0, 'Amortised from flat plan'),
  ('x_api',     'recent-search',  'call',         0.01000000, 2.0, 'Amortised from $100/mo Basic'),
  ('reddit',    'search',         'call',         0.00024000, 2.0, 'Commercial ~$0.24/1k calls — verify')
ON CONFLICT (vendor, operation, unit) WHERE is_active DO NOTHING;

-- Vendor subscriptions. is_subscribed = false everywhere on purpose:
-- nothing is paid for yet, and the treasury view uses this to report what
-- adding each one would cost and how many subscribers would cover it.
INSERT INTO vendor_subscriptions (vendor, plan_name, cost_type, monthly_usd, required_for_tier, is_subscribed, notes) VALUES
  ('anthropic', 'Pay-as-you-go API',        'variable', 0,   'elite',         false, 'No monthly fee; usage-billed. Prepaid credits.'),
  ('openai',    'Pay-as-you-go API',        'variable', 0,   'elite',         false, 'Whisper + TTS for voice. Usage-billed.'),
  ('polygon',   'Stocks Starter',           'fixed',    29,  'elite',         false, 'Real-time equities. Verify current price.'),
  ('polygon',   'Stocks Advanced',          'fixed',    199, 'institutional', false, 'Full tick + unlimited API. Verify.'),
  ('finnhub',   'All-In-One',               'fixed',    150, 'institutional', false, 'Fundamentals + premium news. Verify.'),
  ('x_api',     'Basic',                    'fixed',    100, 'institutional', false, 'Read access. $100/mo floor.'),
  ('reddit',    'Commercial API',           'hybrid',   100, 'institutional', false, 'Negotiated; ~$0.24/1k calls.'),
  ('alphavantage','Premium 600/min',        'fixed',    50,  'institutional', false, 'Verify current price.'),
  ('stocktwits','Enterprise/Partner',       'fixed',    0,   'institutional', false, 'Not self-serve — requires a partnership agreement.')
ON CONFLICT (vendor) DO NOTHING;

COMMIT;


-- =====================================================================
-- Credit allowances per tier
-- =====================================================================
BEGIN;

ALTER TABLE subscription_tiers
  ADD COLUMN IF NOT EXISTS monthly_credits        INTEGER NOT NULL DEFAULT 0,
  -- Which Anthropic model this tier's synthesis runs on. NULL = no LLM,
  -- deterministic output only (which is the free tier's honest state).
  ADD COLUMN IF NOT EXISTS llm_model_default      TEXT,
  ADD COLUMN IF NOT EXISTS llm_model_deep         TEXT,
  -- Market data provider preference, highest quality first.
  ADD COLUMN IF NOT EXISTS market_data_providers  TEXT[] NOT NULL DEFAULT ARRAY['yfinance'],
  ADD COLUMN IF NOT EXISTS sentiment_sources      TEXT[] NOT NULL DEFAULT ARRAY['finnhub','yahoo','stocktwits'],
  -- Speed levers, all real: shorter cache = fresher data; higher queue
  -- priority = served first under load; more concurrency = more parallel
  -- work per user.
  ADD COLUMN IF NOT EXISTS cache_ttl_seconds      INTEGER NOT NULL DEFAULT 900,
  ADD COLUMN IF NOT EXISTS queue_priority         INTEGER NOT NULL DEFAULT 5,
  ADD COLUMN IF NOT EXISTS max_concurrent_jobs    INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS api_keys_allowed       INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN subscription_tiers.monthly_credits IS
  '1 credit = $0.001 of vendor cost. This is the real spend ceiling.';
COMMENT ON COLUMN subscription_tiers.queue_priority IS
  'Higher is served first. Celery consumes the priority queues in order.';

COMMIT;


-- =====================================================================
-- Correction: a vendor can have more than one plan
-- ---------------------------------------------------------------------
-- The original UNIQUE(vendor) above silently discarded Polygon's second
-- plan on insert: the platform genuinely needs Stocks Starter for Elite
-- and Stocks Advanced for Institutional, from the same vendor. The key
-- is (vendor, plan_name).
-- =====================================================================
BEGIN;

ALTER TABLE vendor_subscriptions DROP CONSTRAINT IF EXISTS vendor_subscriptions_vendor_key;
CREATE UNIQUE INDEX IF NOT EXISTS uq_vendor_plan
  ON vendor_subscriptions(vendor, plan_name);

INSERT INTO vendor_subscriptions (vendor, plan_name, cost_type, monthly_usd, required_for_tier, is_subscribed, notes)
VALUES ('polygon', 'Stocks Advanced', 'fixed', 199, 'institutional', false,
        'Full tick + unlimited API calls. Verify current price.')
ON CONFLICT (vendor, plan_name) DO NOTHING;

COMMIT;
