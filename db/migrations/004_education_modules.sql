-- Migration 004: education modules — per-lesson progress, quizzes, XP
--
-- Adds the durable per-user, per-lesson tracking that the /education course
-- browser needs, and widens the difficulty tier range to accommodate the new
-- Module 0 ("New to Investing") beginner tier and the Intermediate tier.
--
-- =====================================================================
-- WHY THERE IS NO `educational_modules` TABLE
-- =====================================================================
-- Lesson prose, quiz questions, XP values and read-time estimates live in
-- Python (backend/app/lessons/), not in Postgres. That's deliberate:
-- there is no admin UI for authoring lessons, the content is static
-- editorial material, and keeping it in code means it's version-controlled,
-- reviewable in a diff, and structurally incapable of drifting out of sync
-- with a separate seed script. What is genuinely per-user and mutable —
-- completion status, quiz scores, XP earned — is what belongs in the
-- database, and that's what this migration creates.
--
-- `user_lesson_progress.lesson_id` is therefore a TEXT key referencing a
-- lesson id defined in code (e.g. 'b001'), not a foreign key. Removing a
-- lesson from the curriculum leaves orphan rows; that's acceptable (they're
-- simply ignored on read) and preferable to blocking content edits on a
-- database migration.
--
-- =====================================================================
-- TIER RENUMBERING — THE IMPORTANT PART
-- =====================================================================
-- The tier scheme gained two new levels. Because base_level is stored as an
-- integer, the existing stored values now point at different content:
--
--   old 0 (Foundational+) -> new 1
--   old 1 (Advanced)      -> new 3
--   old 2 (Expert)        -> new 4
--
-- Without remapping, every existing user would be silently demoted to
-- beginner content. The UPDATE below performs that remap, and it must run
-- in descending order (2 first) so values aren't remapped twice as they
-- pass through intermediate states.
--
-- Run this once against your database:
--   docker compose exec db psql -U aureus -d aureus_dev -f /path/to/004_education_modules.sql

BEGIN;

-- ── 1. Widen the tier range ──────────────────────────────────────────
ALTER TABLE user_learning_progress
  DROP CONSTRAINT IF EXISTS user_learning_progress_base_level_check;

-- ── 2. Remap existing users to their equivalent new tier ─────────────
-- Descending order matters: remapping 1->3 before 2->4 would be fine, but
-- remapping 0->1 before 1->3 would sweep the just-moved rows along with it.
UPDATE user_learning_progress SET base_level = 4 WHERE base_level = 2;
UPDATE user_learning_progress SET base_level = 3 WHERE base_level = 1;
UPDATE user_learning_progress SET base_level = 1 WHERE base_level = 0;

ALTER TABLE user_learning_progress
  ADD CONSTRAINT user_learning_progress_base_level_check
  CHECK (base_level BETWEEN 0 AND 4);

-- ── 3. Per-lesson progress ───────────────────────────────────────────
DO $$ BEGIN
  CREATE TYPE lesson_completion_status AS ENUM ('not_started', 'in_progress', 'completed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS user_lesson_progress (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  lesson_id         TEXT NOT NULL,          -- id defined in app/lessons/ (not an FK; see header)
  tier              SMALLINT NOT NULL CHECK (tier BETWEEN 0 AND 4),
  status            lesson_completion_status NOT NULL DEFAULT 'not_started',

  -- Quiz results. quiz_best_score is the high-water mark across attempts,
  -- which is what accuracy stats and the XP bonus are computed from — a
  -- user who retakes a quiz and does worse shouldn't lose banked progress.
  quiz_attempts     INTEGER NOT NULL DEFAULT 0 CHECK (quiz_attempts >= 0),
  quiz_best_score   INTEGER CHECK (quiz_best_score >= 0),
  quiz_total        INTEGER CHECK (quiz_total >= 0),
  quiz_passed       BOOLEAN NOT NULL DEFAULT false,

  -- XP actually banked for this lesson (lesson XP + quiz bonus if passed).
  -- Stored rather than derived so the historical award survives a later
  -- change to a tier's XP value — users keep what they earned.
  xp_earned         INTEGER NOT NULL DEFAULT 0 CHECK (xp_earned >= 0),

  first_viewed_at   TIMESTAMPTZ,
  completed_at      TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (user_id, lesson_id)
);

CREATE INDEX IF NOT EXISTS idx_user_lesson_progress_user_id ON user_lesson_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_user_lesson_progress_user_tier ON user_lesson_progress(user_id, tier);
CREATE INDEX IF NOT EXISTS idx_user_lesson_progress_completed
  ON user_lesson_progress(user_id) WHERE status = 'completed';

DROP TRIGGER IF EXISTS trg_user_lesson_progress_updated_at ON user_lesson_progress;
CREATE TRIGGER trg_user_lesson_progress_updated_at
  BEFORE UPDATE ON user_lesson_progress
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Tenant isolation, consistent with the other per-user tables.
ALTER TABLE user_lesson_progress ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_user_lesson_progress ON user_lesson_progress;
CREATE POLICY tenant_isolation_user_lesson_progress ON user_lesson_progress
  USING (user_id = current_setting('app.current_user_id', true)::uuid);

-- ── 4. Backfill: credit the daily-lesson count users already accrued ──
-- Pre-existing users have a lessons_completed_count from the daily-lesson
-- card but no per-lesson rows, so the course browser would show them at 0%
-- with a non-zero counter. There's no record of WHICH lessons those were,
-- so we can't fabricate specific rows — instead the API treats
-- lessons_completed_count as a separate legacy counter and reports both.
-- No backfill is performed here deliberately; see education.py's
-- `legacy_daily_lessons_completed` field.

COMMIT;
