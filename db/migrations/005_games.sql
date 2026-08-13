-- Migration 005: Financial Games Engine
--
-- Backs FinWordle and the Chart Pattern Guesser at /games.
--
-- =====================================================================
-- WHY THERE IS NO `finwordle_dictionary` TABLE
-- =====================================================================
-- The word list, definitions, trading context and examples live in
-- backend/app/games/finwordle_dictionary.py rather than in Postgres, for
-- the same reasons the lesson curriculum does (see migration 004): it's
-- static editorial content with no admin UI, it has to be loaded into
-- memory as a set on every guess validation anyway, and keeping one copy
-- in version control means the definitions cannot drift from a seed
-- script. Per-user game state — the mutable part — is what lives here.
--
-- =====================================================================
-- WHY SESSIONS STORE THE ANSWER SERVER-SIDE
-- =====================================================================
-- finwordle_sessions.answer holds the target word. It is deliberately
-- never sent to the client until the round is over: the client posts a
-- guess and the server returns tile colours. If the answer were shipped
-- with the puzzle, the game would be trivially defeated by reading the
-- network tab. The same reasoning applies to
-- pattern_scenarios.correct_direction and its outcome bars.
--
-- Persisting the session also means a page refresh resumes the same game
-- instead of silently handing out a fresh word mid-round, and it's what
-- enforces one daily puzzle per user per day.
--
-- Run this once against your database:
--   docker compose exec db psql -U aureus -d aureus_dev -f /path/to/005_games.sql

BEGIN;

DO $$ BEGIN
  CREATE TYPE game_type AS ENUM ('finwordle', 'pattern_guesser');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE game_session_status AS ENUM ('in_progress', 'won', 'lost');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE finwordle_mode AS ENUM ('daily', 'practice');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── Aggregate per-user, per-game stats (drives the leaderboard) ───────
CREATE TABLE IF NOT EXISTS game_stats (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  game_type          game_type NOT NULL,
  games_played       INTEGER NOT NULL DEFAULT 0 CHECK (games_played >= 0),
  games_won          INTEGER NOT NULL DEFAULT 0 CHECK (games_won >= 0),
  current_streak     INTEGER NOT NULL DEFAULT 0 CHECK (current_streak >= 0),
  max_streak         INTEGER NOT NULL DEFAULT 0 CHECK (max_streak >= 0),
  total_score        INTEGER NOT NULL DEFAULT 0 CHECK (total_score >= 0),
  -- Streaks are a DAILY concept: they advance on the first daily win of a
  -- new day and reset when a day is skipped. Storing the date of the last
  -- counted daily result is what lets us tell "played again today" apart
  -- from "came back the next day", which a plain counter cannot.
  last_daily_played  DATE,
  last_played_at     TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, game_type)
);

CREATE INDEX IF NOT EXISTS idx_game_stats_user ON game_stats(user_id);
-- Leaderboard reads sort by these; the partial predicate keeps never-played
-- rows out of the index entirely.
CREATE INDEX IF NOT EXISTS idx_game_stats_leaderboard
  ON game_stats(game_type, max_streak DESC, total_score DESC)
  WHERE games_played > 0;

DROP TRIGGER IF EXISTS trg_game_stats_updated_at ON game_stats;
CREATE TRIGGER trg_game_stats_updated_at
  BEFORE UPDATE ON game_stats
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── FinWordle rounds ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS finwordle_sessions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mode          finwordle_mode NOT NULL,
  puzzle_date   DATE,                    -- set for daily, NULL for practice
  answer        TEXT NOT NULL,           -- server-side only until the round ends
  guesses       JSONB NOT NULL DEFAULT '[]'::jsonb,   -- ordered list of guessed words
  status        game_session_status NOT NULL DEFAULT 'in_progress',
  score_awarded INTEGER NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_finwordle_sessions_user ON finwordle_sessions(user_id, created_at DESC);
-- One daily puzzle per user per day. Partial UNIQUE so practice rounds
-- (puzzle_date IS NULL) stay unlimited, which is the whole point of that mode.
CREATE UNIQUE INDEX IF NOT EXISTS idx_finwordle_daily_once
  ON finwordle_sessions(user_id, puzzle_date)
  WHERE mode = 'daily';

DROP TRIGGER IF EXISTS trg_finwordle_sessions_updated_at ON finwordle_sessions;
CREATE TRIGGER trg_finwordle_sessions_updated_at
  BEFORE UPDATE ON finwordle_sessions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Chart pattern scenarios ──────────────────────────────────────────
-- setup_bars is what the player sees; outcome_bars and correct_direction
-- are withheld until they answer. Both are stored at generation time so
-- the reveal doesn't need a second market-data fetch (which could return
-- different data, or fail, after the player has already committed).
CREATE TABLE IF NOT EXISTS pattern_scenarios (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ticker              TEXT NOT NULL,               -- hidden until reveal
  setup_bars          JSONB NOT NULL,
  outcome_bars        JSONB NOT NULL,
  correct_direction   TEXT NOT NULL,
  forward_return_pct  NUMERIC(10,4) NOT NULL,
  threshold_pct       NUMERIC(10,4) NOT NULL,
  rationale           TEXT NOT NULL,
  setup_notes         JSONB NOT NULL DEFAULT '[]'::jsonb,
  guessed_direction   TEXT,
  was_correct         BOOLEAN,
  score_awarded       INTEGER NOT NULL DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  answered_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pattern_scenarios_user ON pattern_scenarios(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pattern_scenarios_unanswered
  ON pattern_scenarios(user_id) WHERE answered_at IS NULL;

-- ── Row-level security, consistent with other per-user tables ────────
ALTER TABLE game_stats          ENABLE ROW LEVEL SECURITY;
ALTER TABLE finwordle_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE pattern_scenarios   ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_game_stats ON game_stats;
CREATE POLICY tenant_isolation_game_stats ON game_stats
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

DROP POLICY IF EXISTS tenant_isolation_finwordle_sessions ON finwordle_sessions;
CREATE POLICY tenant_isolation_finwordle_sessions ON finwordle_sessions
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

DROP POLICY IF EXISTS tenant_isolation_pattern_scenarios ON pattern_scenarios;
CREATE POLICY tenant_isolation_pattern_scenarios ON pattern_scenarios
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

COMMIT;
