-- =====================================================================
-- 007_sentiment_pillar.sql
-- ---------------------------------------------------------------------
-- Supports the pillar refactor: Quantitative was replaced by Sentiment as
-- the third primary analysis pillar, and relocated to the Quant Lab.
--
-- WHY THIS TABLE EXISTS
-- ---------------------------------------------------------------------
-- Sentiment velocity is a comparison against history, and the free data
-- sources cannot supply that history. StockTwits' streams endpoint
-- returns a fixed page of the ~30 newest messages, which for a liquid
-- ticker spans about twelve minutes (measured). Every message is
-- therefore inside any 24-hour window, so a "24h versus 7d" comparison
-- computed from one API call is structurally zero — not a reading, an
-- artifact of the page size.
--
-- The only way to get real multi-day social velocity is to accumulate it.
-- Each analysis writes one compact snapshot here; velocity is then
-- measured against the ticker's own history. Redis carries the same data
-- as a short-lived rolling list for the hot path, but Redis is a cache
-- that may be flushed at any time (and is, by dev.sh restarts), so the
-- durable series lives in Postgres.
--
-- Snapshots are also what make the sentiment pillar auditable after the
-- fact: "why did this ticker read Bearish last Tuesday" is answerable
-- from a stored row and unanswerable from a live API that only ever
-- returns the present.
--
-- Idempotent: safe to re-run.
-- =====================================================================

BEGIN;

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

COMMIT;
