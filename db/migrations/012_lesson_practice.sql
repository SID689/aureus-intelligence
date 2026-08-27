-- 012_lesson_practice.sql
--
-- Numeric practice drills alongside the multiple-choice quiz.
--
-- WHY SEPARATE COLUMNS RATHER THAN REUSING THE QUIZ ONES
-- A lesson can have both, they are attempted independently, and they are
-- worth different XP — a numeric answer cannot be guessed, where four
-- options hand you 25% for free. Folding both into quiz_best_score would
-- make "did they pass the quiz" unanswerable, and would let a strong
-- practice score paper over a failed quiz.
--
-- Mirrors the quiz columns exactly, including the high-water-mark
-- semantics: a worse retake never lowers the recorded best.

ALTER TABLE user_lesson_progress
    ADD COLUMN IF NOT EXISTS practice_attempts   INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS practice_best_score INTEGER,
    ADD COLUMN IF NOT EXISTS practice_total      INTEGER,
    ADD COLUMN IF NOT EXISTS practice_passed     BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN user_lesson_progress.practice_best_score IS
    'High-water mark across attempts at the numeric drills, mirroring quiz_best_score.';
