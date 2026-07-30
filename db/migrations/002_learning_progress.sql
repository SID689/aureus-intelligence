-- Migration 002: user_learning_progress
-- Adds durable tracking for the daily-lesson difficulty system:
--   base_level    — user-settable starting tier (0=Foundational+, 1=Advanced, 2=Expert),
--                   pre-filled from onboarding's sophistication_tier but editable in Settings
--   lessons_completed_count — increments each time a user dismisses a lesson;
--                   every 15 lessons completed bumps the EFFECTIVE tier by one,
--                   on top of base_level, capped at 2 (Expert)
-- Run this once against your database:
--   docker compose exec db psql -U aureus -d aureus_dev -f /path/to/002_learning_progress.sql
-- or paste its contents into a psql session.

CREATE TABLE IF NOT EXISTS user_learning_progress (
  user_id                  UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  base_level               SMALLINT NOT NULL DEFAULT 0 CHECK (base_level BETWEEN 0 AND 2),
  lessons_completed_count  INTEGER NOT NULL DEFAULT 0,
  last_lesson_id_shown     TEXT,
  last_shown_date          DATE,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_learning_progress_user_id ON user_learning_progress(user_id);
