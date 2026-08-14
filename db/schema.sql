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

-- =====================================================================
-- TIER ENTITLEMENT COLUMNS — added by 008_tier_entitlements.sql
-- NULL means UNLIMITED (not "unset"); 0 means genuinely zero. See
-- backend/app/core/entitlements.py for why that distinction is
-- load-bearing.
-- =====================================================================
ALTER TABLE subscription_tiers
  ADD COLUMN IF NOT EXISTS max_backtests_per_day        INTEGER,
  ADD COLUMN IF NOT EXISTS max_backtest_tickers         INTEGER,
  ADD COLUMN IF NOT EXISTS max_backtest_years           INTEGER,
  ADD COLUMN IF NOT EXISTS max_portfolio_holdings       INTEGER,
  ADD COLUMN IF NOT EXISTS max_portfolios               INTEGER,
  ADD COLUMN IF NOT EXISTS quant_lab_enabled            BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS quant_history_years          INTEGER,
  ADD COLUMN IF NOT EXISTS quant_monte_carlo_paths      INTEGER,
  ADD COLUMN IF NOT EXISTS quant_custom_peers           BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS max_sentiment_catalysts      INTEGER,
  ADD COLUMN IF NOT EXISTS sec_filing_tone_enabled      BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_usage_counters_lookup
  ON usage_counters(user_id, counter_type, period_key);

-- =====================================================================
-- BILLING: credits, API keys, treasury (migrations 009-010)
-- 1 credit = $0.001 of underlying vendor cost. See
-- backend/app/billing/credits.py for why caps are denominated in cost
-- rather than request counts.
-- =====================================================================
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
