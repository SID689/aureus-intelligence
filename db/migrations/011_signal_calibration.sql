-- 011_signal_calibration.sql
--
-- Persist the measured behaviour of each analysis sub-signal, so the
-- aggregator's standardisation constants can be refreshed on a schedule
-- instead of living forever as literals in a Python file.
--
-- WHY THIS TABLE EXISTS
-- analysis/aggregation.py converts each 0-100 sub-signal into a z-score
-- before pooling it, using that signal's measured centre and dispersion
-- (analysis/calibration.py). Those numbers are CROSS-SECTIONAL
-- STATISTICS, not constants of nature: they were measured over a
-- specific universe on a specific date, and they drift when the market
-- regime shifts or when a scorer is edited. Baked into source they go
-- stale silently, and a stale centre biases every score that depends
-- on it — which, after the aggregation rewrite, is all of them.
--
-- The Python literals remain as a fallback, so a fresh database or a
-- failed refresh degrades to the last reviewed measurement rather than
-- to nothing.
--
-- NOTE: rho (how correlated the signals are) is deliberately NOT stored
-- here and is NOT auto-refreshed. Measuring it correctly requires
-- judgement — the first attempt measured it in score space and got
-- ~0.0, an artifact of saturated scorers, when the raw-metric answer is
-- ~0.35. An automatic job would happily re-introduce that error every
-- month. rho stays a reviewed constant in calibration.py.

CREATE TABLE IF NOT EXISTS signal_calibration (
    label           TEXT PRIMARY KEY,
    signal_group    TEXT NOT NULL CHECK (
                        signal_group IN ('technical','fundamental','sentiment','quantitative')
                    ),
    -- Observations behind the estimate. The loader shrinks toward the
    -- prior by this, so a thin sample is used cautiously rather than
    -- discarded.
    n               INTEGER NOT NULL CHECK (n > 0),
    mean            DOUBLE PRECISION NOT NULL CHECK (mean >= 0 AND mean <= 100),
    -- A signal that never moves would divide by ~0 downstream.
    sd              DOUBLE PRECISION NOT NULL CHECK (sd > 0),
    -- Provenance, so a suspicious row can be traced to the run that
    -- produced it rather than being taken on faith.
    universe_size   INTEGER NOT NULL,
    window_days     INTEGER NOT NULL,
    measured_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE signal_calibration IS
    'Measured centre/dispersion per analysis sub-signal, refreshed by '
    'app.workers.analysis_tasks.recalibrate_signals. Falls back to the '
    'literals in app/analysis/calibration.py when absent or rejected.';

-- The loader reads every row at once and needs the newest timestamp to
-- decide whether the set is stale.
CREATE INDEX IF NOT EXISTS idx_signal_calibration_measured_at
    ON signal_calibration (measured_at DESC);
