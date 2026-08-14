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
--     retention requirement (recommendations, disclosures sent) remain
--     intact and referentially valid in audit_logs.
--  4. DEPRECATED (removed): this schema previously included a live
--     brokerage-execution subsystem — brokerage_connections (encrypted
--     Alpaca credentials), agent_strategies (autonomous strategy state
--     machine), and executed_trades (broker order audit trail) — backing
--     an agentic auto-trading feature. That feature has been deprecated
--     in favor of a user-facing historical Strategy Backtesting Engine
--     (see app/backtesting/); no live orders are ever submitted to a
--     broker. See db/migrations/003_remove_agentic_execution.sql for the
--     migration that removed these tables from a previously-provisioned
--     database.
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
CREATE TYPE notification_status     AS ENUM ('pending', 'delivered', 'read', 'dismissed', 'failed');
CREATE TYPE audit_event_category    AS ENUM ('recommendation', 'disclosure_shown', 'trade_execution', 'data_access', 'auth', 'consent');
CREATE TYPE consent_type            AS ENUM ('terms_of_service', 'privacy_policy', 'voice_recording', 'marketing', 'risk_disclosure');
CREATE TYPE dsr_type                AS ENUM ('access', 'erasure', 'portability', 'rectification');
CREATE TYPE dsr_status              AS ENUM ('received', 'in_progress', 'completed', 'rejected');
CREATE TYPE usage_counter_type      AS ENUM ('analysis_request', 'voice_minute');
CREATE TYPE lesson_completion_status AS ENUM ('not_started', 'in_progress', 'completed');
CREATE TYPE game_type               AS ENUM ('finwordle', 'pattern_guesser');
CREATE TYPE game_session_status     AS ENUM ('in_progress', 'won', 'lost');
CREATE TYPE finwordle_mode          AS ENUM ('daily', 'practice');

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
  voice_minutes_per_month           INTEGER,             -- NULL = unlimited
  news_feed_delay_seconds           INTEGER NOT NULL DEFAULT 900,
  model_tier                        llm_model_tier NOT NULL,
  supports_human_in_loop_alerts     BOOLEAN NOT NULL DEFAULT false,  -- flags significant news-impact rows for human review (see app/agents/risk_delta.py) — unrelated to the deprecated live-execution feature
  features                          JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_active                         BOOLEAN NOT NULL DEFAULT true,
  created_at                        TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO subscription_tiers
  (tier_name, display_name, price_cents, billing_interval, max_analysis_requests_per_day,
   voice_minutes_per_month, news_feed_delay_seconds,
   model_tier, supports_human_in_loop_alerts, features)
VALUES
  ('sovereign', 'Sovereign (Free / Paper)', 0, 'free', 10,
   0, 900,
   'basic', false,
   '{"real_time_data": false}'::jsonb),

  ('elite', 'Elite', 5000, 'monthly', NULL,
   500, 0,
   'advanced', false,
   '{"real_time_data": true}'::jsonb),

  ('institutional', 'Institutional', 10000, 'monthly', NULL,
   NULL, 0,
   'custom_ensemble', true,
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
-- 7. PORTFOLIOS
-- =====================================================================
CREATE TABLE portfolios (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organization_id         UUID REFERENCES organizations(id) ON DELETE SET NULL,
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
-- 8. PORTFOLIO_HOLDINGS
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
-- 9. NEWS_ARTICLES — raw ingestion record (global, not tenant-scoped)
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
-- 10. NEWS_ALERTS — per-ticker sentiment extraction
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
-- 11. PORTFOLIO_IMPACTS — news -> holding impact + notification tracking
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
-- 12. AUDIT_LOGS — SEC Rule 204-2 recordkeeping substrate
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
-- 13. CONSENT_RECORDS — GDPR Art. 7 proof-of-consent ledger
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
-- 14. DATA_SUBJECT_REQUESTS — GDPR/CCPA DSR tracking
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
-- 15. VOICE_SESSIONS — tier-gated voice-minute tracking
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
-- 16. USER_LEARNING_PROGRESS — difficulty tier + daily-lesson counter
-- =====================================================================
-- Originally added by db/migrations/002_learning_progress.sql; folded in
-- here so a fresh install gets it without needing to replay migrations.
-- base_level is the user's chosen STARTING tier (0=New to Investing,
-- 1=Foundational+, 2=Intermediate, 3=Advanced, 4=Expert). The EFFECTIVE
-- tier also rises with lessons completed — see app/api/v1/lessons.py.
CREATE TABLE user_learning_progress (
  user_id                  UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  base_level               SMALLINT NOT NULL DEFAULT 0 CHECK (base_level BETWEEN 0 AND 4),
  lessons_completed_count  INTEGER NOT NULL DEFAULT 0,
  last_lesson_id_shown     TEXT,
  last_shown_date          DATE,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_user_learning_progress_user_id ON user_learning_progress(user_id);
CREATE TRIGGER trg_user_learning_progress_updated_at
  BEFORE UPDATE ON user_learning_progress
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 17. USER_LESSON_PROGRESS — per-lesson completion, quiz results, XP
-- =====================================================================
-- Lesson CONTENT (prose, quizzes, XP values) lives in Python under
-- backend/app/lessons/, not in this database — see the header of
-- db/migrations/004_education_modules.sql for why. `lesson_id` is
-- therefore a TEXT key referencing a lesson id defined in code, not a
-- foreign key.
CREATE TABLE user_lesson_progress (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  lesson_id         TEXT NOT NULL,
  tier              SMALLINT NOT NULL CHECK (tier BETWEEN 0 AND 4),
  status            lesson_completion_status NOT NULL DEFAULT 'not_started',
  quiz_attempts     INTEGER NOT NULL DEFAULT 0 CHECK (quiz_attempts >= 0),
  quiz_best_score   INTEGER CHECK (quiz_best_score >= 0),   -- high-water mark across attempts
  quiz_total        INTEGER CHECK (quiz_total >= 0),
  quiz_passed       BOOLEAN NOT NULL DEFAULT false,
  xp_earned         INTEGER NOT NULL DEFAULT 0 CHECK (xp_earned >= 0),
  first_viewed_at   TIMESTAMPTZ,
  completed_at      TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, lesson_id)
);

CREATE INDEX idx_user_lesson_progress_user_id ON user_lesson_progress(user_id);
CREATE INDEX idx_user_lesson_progress_user_tier ON user_lesson_progress(user_id, tier);
CREATE INDEX idx_user_lesson_progress_completed
  ON user_lesson_progress(user_id) WHERE status = 'completed';
CREATE TRIGGER trg_user_lesson_progress_updated_at
  BEFORE UPDATE ON user_lesson_progress
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- 18. GAMES — FinWordle + Chart Pattern Guesser
-- =====================================================================
-- Game CONTENT (the FinWordle word list with its definitions, trading
-- context and examples) lives in backend/app/games/finwordle_dictionary.py,
-- not here — same reasoning as the lesson curriculum, see the header of
-- db/migrations/005_games.sql. Only per-user state is stored.
--
-- finwordle_sessions.answer and pattern_scenarios.correct_direction are
-- deliberately server-side only: the API returns tile colours and setup
-- bars, never the answer, until a round is over.
CREATE TABLE game_stats (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  game_type          game_type NOT NULL,
  games_played       INTEGER NOT NULL DEFAULT 0 CHECK (games_played >= 0),
  games_won          INTEGER NOT NULL DEFAULT 0 CHECK (games_won >= 0),
  current_streak     INTEGER NOT NULL DEFAULT 0 CHECK (current_streak >= 0),
  max_streak         INTEGER NOT NULL DEFAULT 0 CHECK (max_streak >= 0),
  total_score        INTEGER NOT NULL DEFAULT 0 CHECK (total_score >= 0),
  last_daily_played  DATE,          -- distinguishes "played again today" from "came back tomorrow"
  last_played_at     TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, game_type)
);

CREATE INDEX idx_game_stats_user ON game_stats(user_id);
CREATE INDEX idx_game_stats_leaderboard
  ON game_stats(game_type, max_streak DESC, total_score DESC)
  WHERE games_played > 0;
CREATE TRIGGER trg_game_stats_updated_at
  BEFORE UPDATE ON game_stats
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE finwordle_sessions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mode          finwordle_mode NOT NULL,
  puzzle_date   DATE,                                  -- set for daily, NULL for practice
  answer        TEXT NOT NULL,                         -- withheld from the client until the round ends
  guesses       JSONB NOT NULL DEFAULT '[]'::jsonb,
  status        game_session_status NOT NULL DEFAULT 'in_progress',
  score_awarded INTEGER NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at  TIMESTAMPTZ
);

CREATE INDEX idx_finwordle_sessions_user ON finwordle_sessions(user_id, created_at DESC);
-- Partial UNIQUE: one daily puzzle per user per day, practice stays unlimited.
CREATE UNIQUE INDEX idx_finwordle_daily_once
  ON finwordle_sessions(user_id, puzzle_date) WHERE mode = 'daily';
CREATE TRIGGER trg_finwordle_sessions_updated_at
  BEFORE UPDATE ON finwordle_sessions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- One scenario per user per day, enforced by the unique index below rather
-- than in application code so concurrent requests can't both insert.
-- `question_type` selects which question was asked (predict the direction,
-- name the formation, or state the formation's conventional bias) and
-- `correct_answer` is the key for whichever it was. `correct_direction` is
-- kept separately because the reveal always shows what actually happened,
-- whichever question was asked.
CREATE TABLE pattern_scenarios (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  puzzle_date         DATE NOT NULL,
  ticker              TEXT NOT NULL,                   -- hidden until reveal
  setup_bars          JSONB NOT NULL,
  outcome_bars        JSONB NOT NULL,                  -- hidden until reveal
  correct_direction   TEXT NOT NULL,                   -- hidden until reveal
  forward_return_pct  NUMERIC(10,4) NOT NULL,
  threshold_pct       NUMERIC(10,4) NOT NULL,
  rationale           TEXT NOT NULL,
  setup_notes         JSONB NOT NULL DEFAULT '[]'::jsonb,
  question_type       TEXT NOT NULL DEFAULT 'direction',
  question            TEXT NOT NULL DEFAULT 'Which way did it resolve?',
  choices             JSONB NOT NULL DEFAULT '[]'::jsonb,
  correct_answer      TEXT,                            -- hidden until reveal
  pattern_key         TEXT,                            -- detected formation, if any
  pattern_confidence  NUMERIC(4,2),
  pattern_detail      TEXT,
  guessed_answer      TEXT,
  guessed_direction   TEXT,
  was_correct         BOOLEAN,
  score_awarded       INTEGER NOT NULL DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  answered_at         TIMESTAMPTZ
);

CREATE INDEX idx_pattern_scenarios_user ON pattern_scenarios(user_id, created_at DESC);
CREATE INDEX idx_pattern_scenarios_unanswered
  ON pattern_scenarios(user_id) WHERE answered_at IS NULL;
CREATE UNIQUE INDEX idx_pattern_scenarios_daily_once
  ON pattern_scenarios(user_id, puzzle_date);

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
ALTER TABLE portfolio_impacts     ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_lesson_progress  ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_stats            ENABLE ROW LEVEL SECURITY;
ALTER TABLE finwordle_sessions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE pattern_scenarios     ENABLE ROW LEVEL SECURITY;
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

CREATE POLICY tenant_isolation_portfolio_impacts ON portfolio_impacts
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_game_stats ON game_stats
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_finwordle_sessions ON finwordle_sessions
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_pattern_scenarios ON pattern_scenarios
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

CREATE POLICY tenant_isolation_user_lesson_progress ON user_lesson_progress
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

-- =====================================================================
-- SENTIMENT_SNAPSHOTS — time series backing the Sentiment pillar
-- Added by db/migrations/007_sentiment_pillar.sql. Social APIs serve only
-- a present-moment page, so multi-day velocity must be accumulated here
-- rather than fetched. Also the audit trail for historical pillar scores.
-- =====================================================================
CREATE TABLE IF NOT EXISTS sentiment_snapshots (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker                TEXT        NOT NULL,
  captured_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- Composite pillar score and its band label.
  overall_score         NUMERIC(6,2) NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),
  overall_label         TEXT         NOT NULL CHECK (overall_label IN ('Bullish', 'Neutral', 'Bearish')),

  -- Sub-scores. NULL means the stream produced no reading at all, which
  -- is deliberately distinct from a neutral 50 — the dynamic reweighting
  -- in app/analysis/reweighting.py drops a NULL stream rather than
  -- averaging a fabricated midpoint into the composite.
  news_score            NUMERIC(6,2) CHECK (news_score IS NULL OR (news_score BETWEEN 0 AND 100)),
  social_score          NUMERIC(6,2) CHECK (social_score IS NULL OR (social_score BETWEEN 0 AND 100)),
  sec_tone_score        NUMERIC(6,2) CHECK (sec_tone_score IS NULL OR (sec_tone_score BETWEEN 0 AND 100)),
  sec_tone_label        TEXT,

  -- Raw polarities on -1..+1, kept alongside the 0-100 scores so the
  -- series can be re-normalised later without re-fetching the articles.
  news_polarity         NUMERIC(6,4) CHECK (news_polarity IS NULL OR (news_polarity BETWEEN -1 AND 1)),
  social_polarity       NUMERIC(6,4) CHECK (social_polarity IS NULL OR (social_polarity BETWEEN -1 AND 1)),

  -- Sample sizes: a score built on 200 articles and one built on 4 are
  -- not comparable, and the difference must survive into the history.
  news_document_count   INTEGER      NOT NULL DEFAULT 0,
  social_message_count  INTEGER      NOT NULL DEFAULT 0,

  polarity_velocity     NUMERIC(6,4),
  volume_velocity       NUMERIC(8,4),   -- NULL when the sample can't support it
  velocity_label        TEXT,

  confidence            NUMERIC(4,3) CHECK (confidence IS NULL OR (confidence BETWEEN 0 AND 1)),
  -- Which model scored the text ('lexicon' | 'finbert'). Stored per row
  -- because it can change between runs when FinBERT is enabled, and a
  -- series that silently mixes two models would be misleading to compare.
  model_used            TEXT         NOT NULL DEFAULT 'lexicon'
);

-- The dominant query is "this ticker's recent history, newest first".
CREATE INDEX IF NOT EXISTS idx_sentiment_snapshots_ticker_time
  ON sentiment_snapshots(ticker, captured_at DESC);

-- Retention sweep support: snapshots are only useful while recent.
CREATE INDEX IF NOT EXISTS idx_sentiment_snapshots_captured_at
  ON sentiment_snapshots(captured_at);

-- At most one snapshot per ticker per hour. Without this, a user
-- refreshing the analysis page ten times in a minute writes ten rows that
-- are all the same reading, which then act as ten independent
-- observations in the velocity baseline and bias it toward whatever was
-- true during the refresh burst.
--
-- `AT TIME ZONE 'UTC'` is required, not cosmetic. date_trunc() over a
-- TIMESTAMPTZ is only STABLE — its result depends on the session
-- TimeZone setting — and Postgres refuses to index a non-IMMUTABLE
-- expression. Converting to a plain TIMESTAMP first pins the bucket to
-- UTC and makes the expression IMMUTABLE, which also means the bucket
-- boundary can't shift with a client's timezone.
CREATE UNIQUE INDEX IF NOT EXISTS uq_sentiment_snapshot_ticker_hour
  ON sentiment_snapshots(ticker, (date_trunc('hour', captured_at AT TIME ZONE 'UTC')));

COMMENT ON TABLE sentiment_snapshots IS
  'Time series of sentiment pillar readings per ticker. Exists because social APIs '
  'serve only a present-moment snapshot, so multi-day velocity must be accumulated '
  'rather than fetched. Also the audit trail for historical pillar scores.';
