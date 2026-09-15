-- 013_catalysts_scanner_alerts.sql
--
-- Three features that share one pipeline:
--   1. Catalysts         — dated corporate and macro events, every tier
--   2. Market scanner    — universe snapshots, runs, the Strong Buy board
--   3. Premium alerts    — per-user notification history + Web Push
--
-- Everything is additive. No existing table changes shape except
-- subscription_tiers, which gains one boolean.

-- ── 1. Catalysts ─────────────────────────────────────────────────────────
-- One row per dated event. `dedupe_key` is the natural key from the source
-- (earnings by fiscal quarter, 8-K by accession+item, FOMC by date), so
-- re-ingesting is idempotent and a rescheduled earnings date UPDATES the
-- row rather than appearing twice.
CREATE TABLE IF NOT EXISTS catalysts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dedupe_key      TEXT NOT NULL UNIQUE,
    scope           TEXT NOT NULL CHECK (scope IN ('company', 'sector', 'macro')),
    ticker          TEXT,
    sector          TEXT,
    catalyst_type   TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    event_date      DATE NOT NULL,
    event_time      TEXT,
    -- NULL means the source did not say. A provider calendar date for a
    -- quarter that has not reported is a schedule, not a confirmation,
    -- and presenting it as certain would be a small lie told often.
    date_confirmed  BOOLEAN,
    impact          TEXT NOT NULL CHECK (impact IN ('high', 'medium', 'low')),
    direction       TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (direction IN ('positive', 'negative', 'neutral', 'unknown')),
    source          TEXT NOT NULL,
    source_url      TEXT,
    details         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT catalysts_company_has_ticker CHECK ((scope = 'company') = (ticker IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_catalysts_ticker_date
    ON catalysts (ticker, event_date) WHERE ticker IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_catalysts_scope_date
    ON catalysts (scope, event_date) WHERE scope <> 'company';

-- ── 2. Scanner universe ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scanner_universe (
    ticker             TEXT PRIMARY KEY,
    company_name       TEXT NOT NULL,
    gics_sector        TEXT,
    gics_sub_industry  TEXT,
    indices            TEXT[] NOT NULL DEFAULT '{}',
    active             BOOLEAN NOT NULL DEFAULT TRUE,
    source             TEXT NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 3. Pillar snapshots ──────────────────────────────────────────────────
-- The scanner's cache, and the reason it can cover 500 names without
-- exhausting provider quotas. Each pillar carries its OWN timestamp because
-- each goes stale at a different rate: filings move quarterly, daily bars
-- once a day, news by the hour. Refreshing all three together on the
-- fastest clock is what would make a universe scan unaffordable.
CREATE TABLE IF NOT EXISTS scanner_snapshots (
    ticker                    TEXT NOT NULL,
    horizon                   TEXT NOT NULL,
    price                     DOUBLE PRECISION,

    fundamental_z             DOUBLE PRECISION,
    fundamental_score         DOUBLE PRECISION,
    fundamental_completeness  DOUBLE PRECISION,
    fundamental_at            TIMESTAMPTZ,

    technical_z               DOUBLE PRECISION,
    technical_score           DOUBLE PRECISION,
    technical_completeness    DOUBLE PRECISION,
    technical_at              TIMESTAMPTZ,

    sentiment_z               DOUBLE PRECISION,
    sentiment_score           DOUBLE PRECISION,
    sentiment_completeness    DOUBLE PRECISION,
    sentiment_at              TIMESTAMPTZ,

    composite                 DOUBLE PRECISION,
    conviction                DOUBLE PRECISION,
    agreement                 DOUBLE PRECISION,
    data_completeness         DOUBLE PRECISION,
    -- estimated_at: pooled from whatever pillar values were on hand.
    -- verified_at:  pooled from pillars all fresh inside this run's
    --               verification window. Only a verified composite can
    --               move a stock onto or off the board.
    estimated_at              TIMESTAMPTZ,
    verified_at               TIMESTAMPTZ,

    consecutive_failures      INTEGER NOT NULL DEFAULT 0,
    last_error                TEXT,
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, horizon)
);
CREATE INDEX IF NOT EXISTS idx_scanner_snapshots_rank
    ON scanner_snapshots (horizon, composite DESC NULLS LAST);

-- ── 4. Scanner runs ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scanner_runs (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    horizon                TEXT NOT NULL,
    status                 TEXT NOT NULL CHECK (status IN ('running', 'completed', 'skipped', 'failed')),
    market_phase           TEXT,
    started_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at            TIMESTAMPTZ,
    universe_size          INTEGER,
    budget_units           INTEGER,
    units_spent            INTEGER NOT NULL DEFAULT 0,
    refreshed_fundamental  INTEGER NOT NULL DEFAULT 0,
    refreshed_technical    INTEGER NOT NULL DEFAULT 0,
    refreshed_sentiment    INTEGER NOT NULL DEFAULT 0,
    estimated              INTEGER NOT NULL DEFAULT 0,
    verified               INTEGER NOT NULL DEFAULT 0,
    entries                INTEGER NOT NULL DEFAULT 0,
    exits                  INTEGER NOT NULL DEFAULT 0,
    errors                 INTEGER NOT NULL DEFAULT 0,
    note                   TEXT
);
CREATE INDEX IF NOT EXISTS idx_scanner_runs_recent ON scanner_runs (horizon, started_at DESC);

-- ── 5. Leaderboard ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leaderboard_entries (
    horizon            TEXT NOT NULL,
    ticker             TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (status IN ('active', 'exited')),
    composite          DOUBLE PRECISION NOT NULL,
    conviction         DOUBLE PRECISION,
    agreement          DOUBLE PRECISION,
    data_completeness  DOUBLE PRECISION,
    price              DOUBLE PRECISION,
    driver_pillar      TEXT,
    primary_catalyst   JSONB,
    entered_at         TIMESTAMPTZ NOT NULL,
    last_verified_at   TIMESTAMPTZ NOT NULL,
    peak_composite     DOUBLE PRECISION,
    exited_at          TIMESTAMPTZ,
    exit_reason        TEXT,
    -- Drives the re-alert cooldown. Survives an exit, so a stock that
    -- bounces out and back in within the cooldown does not page every
    -- premium user twice for what is really one opportunity.
    last_alerted_at    TIMESTAMPTZ,
    PRIMARY KEY (horizon, ticker)
);
CREATE INDEX IF NOT EXISTS idx_leaderboard_active
    ON leaderboard_entries (horizon, status, composite DESC);

CREATE TABLE IF NOT EXISTS leaderboard_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    horizon     TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    event       TEXT NOT NULL CHECK (event IN ('entered', 'exited')),
    composite   DOUBLE PRECISION,
    conviction  DOUBLE PRECISION,
    reason      TEXT,
    run_id      UUID REFERENCES scanner_runs(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_leaderboard_events_recent ON leaderboard_events (horizon, created_at DESC);

-- ── 6. Alerts and per-user notification history ────────────────────────
-- One market_alerts row per event, fanned out to user_notifications only
-- for users entitled at the moment of the alert. Entitlement is checked
-- at fan-out AND at read, so a downgrade stops access immediately rather
-- than leaving a history the user can keep mining.
CREATE TABLE IF NOT EXISTS market_alerts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind              TEXT NOT NULL CHECK (kind IN ('strong_buy_entry')),
    horizon           TEXT NOT NULL,
    ticker            TEXT NOT NULL,
    company_name      TEXT,
    composite         DOUBLE PRECISION NOT NULL,
    conviction        DOUBLE PRECISION,
    price             DOUBLE PRECISION,
    driver_pillar     TEXT,
    primary_catalyst  JSONB,
    title             TEXT NOT NULL,
    body              TEXT NOT NULL,
    recipients        INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_market_alerts_recent ON market_alerts (created_at DESC);

CREATE TABLE IF NOT EXISTS user_notifications (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_id           UUID NOT NULL REFERENCES market_alerts(id) ON DELETE CASCADE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at            TIMESTAMPTZ,
    delivered_ws_at    TIMESTAMPTZ,
    delivered_push_at  TIMESTAMPTZ,
    UNIQUE (user_id, alert_id)
);
CREATE INDEX IF NOT EXISTS idx_user_notifications_feed ON user_notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_notifications_unread
    ON user_notifications (user_id) WHERE read_at IS NULL;

-- ── 7. Web Push subscriptions ────────────────────────────────────────────
-- endpoint is unique because it identifies a browser profile, not a user.
-- If a second account signs in on the same browser and subscribes, the row
-- is reassigned rather than duplicated — otherwise the first account's
-- alerts would keep arriving on a device it no longer uses.
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint         TEXT NOT NULL UNIQUE,
    p256dh           TEXT NOT NULL,
    auth             TEXT NOT NULL,
    user_agent       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_success_at  TIMESTAMPTZ,
    failure_count    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user ON push_subscriptions (user_id);

-- ── 8. Entitlement flag ──────────────────────────────────────────────────
ALTER TABLE subscription_tiers
    ADD COLUMN IF NOT EXISTS leaderboard_enabled BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE subscription_tiers
   SET leaderboard_enabled = TRUE,
       features = COALESCE(features, '{}'::jsonb) || '{"leaderboard_alerts": true}'::jsonb
 WHERE tier_name IN ('elite', 'institutional');

UPDATE subscription_tiers
   SET leaderboard_enabled = FALSE,
       features = COALESCE(features, '{}'::jsonb) || '{"leaderboard_alerts": false}'::jsonb
 WHERE tier_name = 'sovereign';
