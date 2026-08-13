-- Migration 006: one pattern scenario per user per day + named-pattern questions
--
-- Two changes to pattern_scenarios:
--
-- 1. DAILY LIMIT. `puzzle_date` plus a partial UNIQUE index enforces one
--    scenario per user per calendar day at the DATABASE level rather than in
--    application code. Doing it here means two concurrent requests can't both
--    pass an application-level "have they played today?" check and each
--    insert a row — the second simply fails the constraint. Same approach
--    already used for the FinWordle daily word in migration 005.
--
-- 2. GENERALISED QUESTIONS. The game previously only ever asked "which way
--    did it resolve", so the answer key was just `correct_direction`. It now
--    also asks players to NAME the formation and to state what that formation
--    is conventionally read as, so the row needs to record which question was
--    asked, the options presented, and the answer key for that question type.
--    `correct_direction` is retained because the reveal always shows what
--    actually happened, whichever question was asked.
--
-- Existing rows are backfilled as direction questions, which is what they were.
--
-- Run once:
--   docker compose exec db psql -U aureus -d aureus_dev -f /path/to/006_pattern_daily_and_questions.sql

BEGIN;

ALTER TABLE pattern_scenarios
  ADD COLUMN IF NOT EXISTS puzzle_date        DATE,
  ADD COLUMN IF NOT EXISTS question_type      TEXT NOT NULL DEFAULT 'direction',
  ADD COLUMN IF NOT EXISTS question           TEXT NOT NULL DEFAULT 'Which way did it resolve?',
  ADD COLUMN IF NOT EXISTS choices            JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS correct_answer     TEXT,
  ADD COLUMN IF NOT EXISTS pattern_key        TEXT,
  ADD COLUMN IF NOT EXISTS pattern_confidence NUMERIC(4,2),
  ADD COLUMN IF NOT EXISTS pattern_detail     TEXT,
  ADD COLUMN IF NOT EXISTS guessed_answer     TEXT;

-- Backfill: every pre-existing row was a direction question.
UPDATE pattern_scenarios
   SET correct_answer = correct_direction
 WHERE correct_answer IS NULL;

UPDATE pattern_scenarios
   SET guessed_answer = guessed_direction
 WHERE guessed_answer IS NULL AND guessed_direction IS NOT NULL;

-- Backfill puzzle_date from creation date so historical rows don't all
-- collide on NULL, and so the unique index below can be created safely.
UPDATE pattern_scenarios
   SET puzzle_date = created_at::date
 WHERE puzzle_date IS NULL;

-- Deduplicate any same-user/same-day rows created before the limit existed,
-- keeping the earliest. The unique index cannot be built while duplicates
-- remain, and silently dropping the constraint would leave the limit
-- unenforced.
DELETE FROM pattern_scenarios ps
 USING pattern_scenarios keep
 WHERE ps.user_id = keep.user_id
   AND ps.puzzle_date = keep.puzzle_date
   AND ps.created_at > keep.created_at;

ALTER TABLE pattern_scenarios ALTER COLUMN puzzle_date SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_pattern_scenarios_daily_once
  ON pattern_scenarios(user_id, puzzle_date);

COMMIT;
