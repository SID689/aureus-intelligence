-- =====================================================================
-- AUREUS INTELLIGENCE — PHASE 1 PRODUCTION DATABASE SCHEMA
-- Target: PostgreSQL 15+
-- =====================================================================
-- DESIGN PRINCIPLES
--  1. Every tenant-scoped table denormalizes (user_id[, organization_id])
--     directly onto the row so Row-Level Security policies are cheap
--     single-column predicates instead of multi-table joins. This is
--     the concrete mechanism behind the GDPR/CCPA "multi-tenant data
--     isolation" requirement, not just a policy statement.
--  2. All monetary, quantity, and cost-basis fields use NUMERIC, never
--     FLOAT/REAL, to avoid floating-point drift in P&L math.
--  3. `users` is soft-deleted (deleted_at) rather than hard-deleted, so
--     GDPR Art. 17 erasure can be satisfied via an anonymization routine
--     while financial records subject to SEC Rule 204-2's 5-year
--     retention requirement (trades, recommendations, disclosures sent)
--     remain intact and referentially valid in audit_logs/executed_trades.
--  4. Brokerage credentials are never stored in plaintext or with a
--     reversible single-key scheme. AES-256-GCM ciphertext, the 12-byte
--     IV/nonce, and the 16-byte auth tag are stored as three discrete
--     columns. The Data Encryption Key (DEK) itself is wrapped by a
--     KMS-managed Key Encryption Key (KEK); only a `kms_key_id`
--     *reference* lives in this database — the unwrapped key material
--     never touches Postgres.
--  5. The LLM agent orchestrator (LangGraph/CrewAI, see architecture doc)
--     never writes directly to executed_trades. It writes strategy
--     configuration/state to agent_strategies; a separate deterministic
--     execution service validates against tier limits and risk rules
--     before any row lands in executed_trades. The schema enforces this
--     boundary by giving agent_strategies no execution-side columns.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------------
-- ENUM TYPES
-- ---------------------------------------------------------------------
CREATE TYPE user_role               AS ENUM ('owner', 'admin', 'member');
CREATE TYPE subscription_tier_name  AS ENUM ('sovereign', 'elite', 'institutional');
CREATE TYPE billing_interval        AS ENUM ('monthly', 'annual', 'free');
CREATE TYPE llm_model_tier          AS ENUM ('basic', 'advanced', 'custom_ensemble');
CREATE TYPE subscription_status    AS ENUM ('trialing', 'active', 'past_due', 'canceled', 'incomplete');
CREATE TYPE broker_provider         AS ENUM ('alpaca_paper', 'alpaca_live');
CREATE TYPE connection_status       AS ENUM ('active', 'revoked', 'error', 'pending_verification');
CREATE TYPE notification_status     AS ENUM ('pending', 'delivered', 'read', 'dismissed', 'failed');
CREATE TYPE agent_type              AS ENUM ('single_agent', 'ensemble');
CREATE TYPE agent_strategy_status   AS ENUM ('draft', 'active', 'paused', 'archived', 'error');
CREATE TYPE trade_side              AS ENUM ('buy', 'sell');
CREATE TYPE order_type              AS ENUM ('market', 'limit', 'stop_loss', 'stop_limit');
CREATE TYPE trade_status            AS ENUM ('pending', 'submitted', 'partially_filled', 'filled', 'canceled', 'rejected', 'expired');
CREATE TYPE audit_event_category    AS ENUM ('recommendation', 'disclosure_shown', 'trade_execution', 'data_access', 'auth', 'consent');
CREATE TYPE consent_type            AS ENUM ('terms_of_service', 'privacy_policy', 'voice_recording', 'marketing', 'risk_disclosure');
CREATE TYPE dsr_type                AS ENUM ('access', 'erasure', 'portability', 'rectification');
CREATE TYPE dsr_status              AS ENUM ('received', 'in_progress', 'completed', 'rejected');
CREATE TYPE usage_counter_type      AS ENUM ('analysis_request', 'voice_minute');

-- ---------------------------------------------------------------------
-- SHARED TRIGGER: auto-maintain `updated_at`
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- 1. ORGANIZATIONS — Institutional multi-seat tenancy root
-- =====================================================================
CREATE TABLE organizations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  billing_email CITEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_organizations_updated_at
  BEFORE UPDATE ON organizations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 2. USERS
-- =====================================================================
CREATE TABLE users (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id  UUID REFERENCES organizations(id) ON DELETE SET NULL,
  email            CITEXT NOT NULL UNIQUE,
  password_hash    TEXT,                       -- nullable: OAuth/SSO-only users have none
  auth_provider    TEXT NOT NULL DEFAULT 'password',
  external_auth_id TEXT,
  role             user_role NOT NULL DEFAULT 'owner',
  mfa_enabled      BOOLEAN NOT NULL DEFAULT false,
  is_active        BOOLEAN NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at       TIMESTAMPTZ                 -- soft delete -> GDPR erasure anonymizes rather than removes the row
);

CREATE INDEX idx_users_organization_id ON users(organization_id);
CREATE TRIGGER trg_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 3. PROFILES — 1:1 with users; jurisdiction + disclosure metadata
-- =====================================================================
CREATE TABLE profiles (
  user_id                           UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  display_name                      TEXT,
  country_code                      CHAR(2) NOT NULL,   -- drives GDPR vs CCPA applicability at the app layer
  timezone                          TEXT NOT NULL DEFAULT 'UTC',
  locale                            TEXT NOT NULL DEFAULT 'en-US',
  accredited_investor_self_attested BOOLEAN NOT NULL DEFAULT false,
  risk_disclosure_acknowledged_at   TIMESTAMPTZ,
  terms_version_accepted            TEXT,
  marketing_opt_in                  BOOLEAN NOT NULL DEFAULT false,
  created_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_profiles_updated_at
  BEFORE UPDATE ON profiles
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 4. SUBSCRIPTION_TIERS — seeded catalog, not user-editable
-- =====================================================================
CREATE TABLE subscription_tiers (
  id                                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tier_name                          subscription_tier_name NOT NULL UNIQUE,
  display_name                      TEXT NOT NULL,
  price_cents                       INTEGER NOT NULL CHECK (price_cents >= 0),
  billing_interval                  billing_interval NOT NULL,
  max_analysis_requests_per_day     INTEGER,             -- NULL = unlimited
  concurrent_agent_strategies_limit INTEGER,             -- NULL = unlimited/contract-defined
  voice_minutes_per_month           INTEGER,             -- NULL = unlimited
  news_feed_delay_seconds           INTEGER NOT NULL DEFAULT 900,
  model_tier                        llm_model_tier NOT NULL,
  supports_live_execution           BOOLEAN NOT NULL DEFAULT false,
  supports_human_in_loop_alerts     BOOLEAN NOT NULL DEFAULT false,
  features                          JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_active                         BOOLEAN NOT NULL DEFAULT true,
  created_at                        TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO subscription_tiers
  (tier_name, display_name, price_cents, billing_interval, max_analysis_requests_per_day,
   concurrent_agent_strategies_limit, voice_minutes_per_month, news_feed_delay_seconds,
   model_tier, supports_live_execution, supports_human_in_loop_alerts, features)
VALUES
  ('sovereign', 'Sovereign (Free / Paper)', 0, 'free', 10,
   0, 0, 900,
   'basic', false, false,
   '{"paper_trading_only": true, "real_time_data": false}'::jsonb),

  ('elite', 'Elite', 5000, 'monthly', NULL,
   5, 500, 0,
   'advanced', true, false,
   '{"real_time_data": true, "live_execution": true, "direct_alpaca": true}'::jsonb),

  ('institutional', 'Institutional', 10000, 'monthly', NULL,
   NULL, NULL, 0,
   'custom_ensemble', true, true,
   '{"real_time_data": true, "sub_second_news": true, "unthrottled_voice": true, "cross_portfolio_alerts": true}'::jsonb);

-- =====================================================================
-- 5. USER_SUBSCRIPTIONS — Stripe-synced billing state
-- =====================================================================
CREATE TABLE user_subscriptions (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tier_id                UUID NOT NULL REFERENCES subscription_tiers(id),
  stripe_customer_id     TEXT NOT NULL,
  stripe_subscription_id TEXT UNIQUE,
  status                 subscription_status NOT NULL DEFAULT 'incomplete',
  current_period_start   TIMESTAMPTZ,
  current_period_end     TIMESTAMPTZ,
  cancel_at_period_end   BOOLEAN NOT NULL DEFAULT false,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Exactly one active/trialing subscription per user — the Stripe gatekeeper
-- middleware reads this row on every gated request to resolve tier limits.
CREATE UNIQUE INDEX uq_one_active_subscription_per_user
  ON user_subscriptions(user_id)
  WHERE status IN ('active', 'trialing');

CREATE INDEX idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE TRIGGER trg_user_subscriptions_updated_at
  BEFORE UPDATE ON user_subscriptions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 6. USAGE_COUNTERS — rate-limit enforcement (analysis/day, voice/month)
-- =====================================================================
CREATE TABLE usage_counters (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  counter_type usage_counter_type NOT NULL,
  period_key   TEXT NOT NULL,        -- 'YYYY-MM-DD' for daily counters, 'YYYY-MM' for monthly
  count_value  NUMERIC(12,2) NOT NULL DEFAULT 0,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, counter_type, period_key)
);

CREATE INDEX idx_usage_counters_user_id ON usage_counters(user_id);
CREATE TRIGGER trg_usage_counters_updated_at
  BEFORE UPDATE ON usage_counters
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 7. BROKERAGE_CONNECTIONS — AES-256-GCM encrypted credentials at rest
-- =====================================================================
CREATE TABLE brokerage_connections (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id      UUID REFERENCES organizations(id) ON DELETE SET NULL,
  broker               broker_provider NOT NULL,
  encrypted_api_key    BYTEA NOT NULL,   -- AES-256-GCM ciphertext
  encrypted_api_secret BYTEA NOT NULL,   -- AES-256-GCM ciphertext
  encryption_iv        BYTEA NOT NULL,   -- 12-byte nonce, unique per encryption operation, never reused
  encryption_auth_tag  BYTEA NOT NULL,   -- 16-byte GCM authentication tag
  kms_key_id           TEXT NOT NULL,    -- reference to the KMS-wrapped DEK; unwrapped key never stored here
  is_live              BOOLEAN NOT NULL DEFAULT false,
  status               connection_status NOT NULL DEFAULT 'pending_verification',
  last_verified_at     TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_brokerage_connections_user_id ON brokerage_connections(user_id);
CREATE TRIGGER trg_brokerage_connections_updated_at
  BEFORE UPDATE ON brokerage_connections
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 8. PORTFOLIOS
-- =====================================================================
CREATE TABLE portfolios (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id         UUID REFERENCES organizations(id) ON DELETE SET NULL,
  brokerage_connection_id UUID REFERENCES brokerage_connections(id) ON DELETE SET NULL,
  name                    TEXT NOT NULL,
  is_paper                BOOLEAN NOT NULL DEFAULT true,
  base_currency           CHAR(3) NOT NULL DEFAULT 'USD',
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_portfolios_user_id ON portfolios(user_id);
CREATE TRIGGER trg_portfolios_updated_at
  BEFORE UPDATE ON portfolios
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 9. PORTFOLIO_HOLDINGS
-- =====================================================================
CREATE TABLE portfolio_holdings (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id       UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- denormalized for cheap RLS
  ticker             TEXT NOT NULL,
  quantity           NUMERIC(20,8) NOT NULL CHECK (quantity >= 0),
  average_cost_basis NUMERIC(20,6) NOT NULL CHECK (average_cost_basis >= 0),
  current_price      NUMERIC(20,6),
  current_weight     NUMERIC(7,4),      -- percentage of portfolio, e.g. 12.3456
  beta               NUMERIC(8,4),
  last_priced_at     TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (portfolio_id, ticker)
);

CREATE INDEX idx_portfolio_holdings_portfolio_id ON portfolio_holdings(portfolio_id);
CREATE INDEX idx_portfolio_holdings_ticker ON portfolio_holdings(ticker);
CREATE TRIGGER trg_portfolio_holdings_updated_at
  BEFORE UPDATE ON portfolio_holdings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 10. NEWS_ARTICLES — raw ingestion record (global, not tenant-scoped)
-- =====================================================================
CREATE TABLE news_articles (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source               TEXT NOT NULL,
  source_url           TEXT NOT NULL UNIQUE,
  headline             TEXT NOT NULL,
  published_at         TIMESTAMPTZ NOT NULL,
  raw_content          TEXT,
  ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  ingestion_latency_ms INTEGER     -- published_at -> ingested_at, tracked for the Institutional sub-second SLA
);

CREATE INDEX idx_news_articles_published_at ON news_articles(published_at DESC);

-- =====================================================================
-- 11. NEWS_ALERTS — per-ticker sentiment extraction
-- =====================================================================
CREATE TABLE news_alerts (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  news_article_id         UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
  ticker                  TEXT NOT NULL,
  sentiment_score         NUMERIC(4,3) NOT NULL CHECK (sentiment_score >= -1.0 AND sentiment_score <= 1.0),
  sentiment_model_version TEXT NOT NULL,
  summary                 TEXT,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_news_alerts_ticker_created_at ON news_alerts(ticker, created_at DESC);

-- =====================================================================
-- 12. PORTFOLIO_IMPACTS — news -> holding impact + notification tracking
-- =====================================================================
CREATE TABLE portfolio_impacts (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  news_alert_id          UUID NOT NULL REFERENCES news_alerts(id) ON DELETE CASCADE,
  portfolio_id           UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  user_id                UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- denormalized for RLS
  holding_id             UUID REFERENCES portfolio_holdings(id) ON DELETE SET NULL,
  beta_volatility_impact NUMERIC(8,4) NOT NULL,   -- estimated beta-adjusted volatility delta to the portfolio
  impact_confidence      NUMERIC(4,3) NOT NULL CHECK (impact_confidence >= 0 AND impact_confidence <= 1),
  requires_human_review  BOOLEAN NOT NULL DEFAULT false,  -- Institutional cross-portfolio human-in-the-loop flag
  notification_status    notification_status NOT NULL DEFAULT 'pending',
  notified_at            TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_portfolio_impacts_portfolio_id ON portfolio_impacts(portfolio_id);
CREATE INDEX idx_portfolio_impacts_pending ON portfolio_impacts(notification_status)
  WHERE notification_status = 'pending';

-- =====================================================================
-- 13. AGENT_STRATEGIES — state-machine-tracked autonomous agent config
-- =====================================================================
CREATE TABLE agent_strategies (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id     UUID REFERENCES organizations(id) ON DELETE SET NULL,
  parent_strategy_id  UUID REFERENCES agent_strategies(id) ON DELETE SET NULL,  -- inherited rule hierarchy
  name                TEXT NOT NULL,
  agent_type          agent_type NOT NULL DEFAULT 'single_agent',
  state_machine_token TEXT NOT NULL DEFAULT 'idle',   -- current FSM node: idle | analyzing | awaiting_approval | executing | halted
  status              agent_strategy_status NOT NULL DEFAULT 'draft',
  confidence_score    NUMERIC(4,3) CHECK (confidence_score >= 0 AND confidence_score <= 1),
  configuration       JSONB NOT NULL DEFAULT '{}'::jsonb,  -- ensemble members, entry/exit rules, risk limits
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_strategies_user_id ON agent_strategies(user_id);
CREATE INDEX idx_agent_strategies_parent_id ON agent_strategies(parent_strategy_id);
CREATE TRIGGER trg_agent_strategies_updated_at
  BEFORE UPDATE ON agent_strategies
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 14. EXECUTED_TRADES
-- =====================================================================
CREATE TABLE executed_trades (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  strategy_id             UUID REFERENCES agent_strategies(id) ON DELETE SET NULL,  -- NULL = manual trade
  portfolio_id            UUID NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
  user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,     -- denormalized for RLS
  brokerage_connection_id UUID NOT NULL REFERENCES brokerage_connections(id),
  ticker                  TEXT NOT NULL,
  side                    trade_side NOT NULL,
  order_type              order_type NOT NULL,
  limit_price             NUMERIC(20,6),
  stop_price              NUMERIC(20,6),
  quantity                NUMERIC(20,8) NOT NULL CHECK (quantity > 0),
  status                  trade_status NOT NULL DEFAULT 'pending',
  broker_order_id         TEXT,
  submitted_at            TIMESTAMPTZ,
  filled_at               TIMESTAMPTZ,
  filled_avg_price        NUMERIC(20,6),
  execution_log           JSONB NOT NULL DEFAULT '[]'::jsonb,  -- ordered [{status, timestamp, detail}, ...]
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT chk_limit_price_required CHECK (
    (order_type IN ('limit', 'stop_limit') AND limit_price IS NOT NULL)
    OR (order_type NOT IN ('limit', 'stop_limit'))
  ),
  CONSTRAINT chk_stop_price_required CHECK (
    (order_type IN ('stop_loss', 'stop_limit') AND stop_price IS NOT NULL)
    OR (order_type NOT IN ('stop_loss', 'stop_limit'))
  )
);

CREATE INDEX idx_executed_trades_portfolio_id ON executed_trades(portfolio_id);
CREATE INDEX idx_executed_trades_strategy_id ON executed_trades(strategy_id);
CREATE INDEX idx_executed_trades_status ON executed_trades(status);

-- =====================================================================
-- 15. AUDIT_LOGS — SEC Rule 204-2 recordkeeping substrate
-- =====================================================================
CREATE TABLE audit_logs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
  organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
  event_category  audit_event_category NOT NULL,
  event_type      TEXT NOT NULL,
  payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
  ip_address      INET,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Treated as append-only at the application layer. Combined with a
-- periodic export to WORM/object-lock storage, this satisfies Rule
-- 204-2's "first two years in an easily accessible place, five years
-- total" retention requirement for records of recommendations made.
CREATE INDEX idx_audit_logs_user_id_created_at ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_logs_event_category ON audit_logs(event_category);

-- =====================================================================
-- 16. CONSENT_RECORDS — GDPR Art. 7 proof-of-consent ledger
-- =====================================================================
CREATE TABLE consent_records (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  consent_type consent_type NOT NULL,
  version      TEXT NOT NULL,
  granted      BOOLEAN NOT NULL,
  granted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  ip_address   INET,
  revoked_at   TIMESTAMPTZ
);

CREATE INDEX idx_consent_records_user_id ON consent_records(user_id);

-- =====================================================================
-- 17. DATA_SUBJECT_REQUESTS — GDPR/CCPA DSR tracking
-- =====================================================================
CREATE TABLE data_subject_requests (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  request_type dsr_type NOT NULL,
  status       dsr_status NOT NULL DEFAULT 'received',
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  notes        TEXT
);

CREATE INDEX idx_data_subject_requests_user_id ON data_subject_requests(user_id);

-- =====================================================================
-- 18. VOICE_SESSIONS — tier-gated voice-minute tracking
-- =====================================================================
CREATE TABLE voice_sessions (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  started_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at               TIMESTAMPTZ,
  duration_seconds       INTEGER,
  transcript_storage_uri TEXT,        -- pointer to an encrypted blob store; transcripts are never stored inline
  billed_minute_period   TEXT,        -- matches usage_counters.period_key ('YYYY-MM')
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_voice_sessions_user_id ON voice_sessions(user_id);

-- =====================================================================
-- ROW-LEVEL SECURITY — GDPR/CCPA multi-tenant isolation
-- =====================================================================
-- The application sets these per-transaction immediately after BEGIN:
--   SET LOCAL app.current_user_id = '<uuid>';
--   SET LOCAL app.current_org_id  = '<uuid-or-empty-string>';
-- `true` as the second arg to current_setting() makes an unset variable
-- return NULL instead of raising, so connections that forget to set it
-- fail closed (no rows visible) rather than failing open.
-- ---------------------------------------------------------------------

ALTER TABLE portfolios            ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_holdings    ENABLE ROW LEVEL SECURITY;
ALTER TABLE brokerage_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_strategies      ENABLE ROW LEVEL SECURITY;
ALTER TABLE executed_trades       ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_impacts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE voice_sessions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_counters        ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs            ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_portfolios ON portfolios
  USING (
    user_id = current_setting('app.current_user_id', true)::uuid
    OR (organization_id IS NOT NULL
        AND organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
  );

CREATE POLICY tenant_isolation_portfolio_holdings ON portfolio_holdings
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_brokerage_connections ON brokerage_connections
  USING (
    user_id = current_setting('app.current_user_id', true)::uuid
    OR (organization_id IS NOT NULL
        AND organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
  );

CREATE POLICY tenant_isolation_agent_strategies ON agent_strategies
  USING (
    user_id = current_setting('app.current_user_id', true)::uuid
    OR (organization_id IS NOT NULL
        AND organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
  );

CREATE POLICY tenant_isolation_executed_trades ON executed_trades
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_portfolio_impacts ON portfolio_impacts
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_voice_sessions ON voice_sessions
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_usage_counters ON usage_counters
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_audit_logs ON audit_logs
  USING (
    user_id = current_setting('app.current_user_id', true)::uuid
    OR (organization_id IS NOT NULL
        AND organization_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
  );

-- Celery ingestion workers (market data, news) write across tenants and
-- must run as a role that bypasses RLS entirely. Application API
-- connections must NEVER use this role.
--   CREATE ROLE aureus_worker BYPASSRLS LOGIN PASSWORD '<rotated-secret>';

-- =====================================================================
-- END OF PHASE 1 SCHEMA
-- =====================================================================
