#!/usr/bin/env bash
#
# Export the read-only showcase data so a cloud demo is not empty.
#
#   ./scripts/export_showcase_data.sh            -> showcase_data.sql
#   ./scripts/export_showcase_data.sh out.sql
#
# A fresh Neon or Supabase database has the schema and nothing in it. The
# leaderboard, the catalyst timeline and the news wire are all filled by
# the background scanner over a market session or two, and a free cloud
# deployment usually runs without those workers at all. So the tables the
# demo READS get carried over from this machine, where the scanner has
# already done the work, and the free deployment serves them without ever
# running a worker.
#
# Nothing user-owned is exported: no users, portfolios, consents,
# subscriptions, credits or game sessions. What ships is market data.
#
# Load it with:
#   psql "$NEON_URL" -f showcase_data.sql

set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-showcase_data.sql}"

# Read-only market state, in dependency order.
TABLES=(
  scanner_universe
  scanner_snapshots
  scanner_runs
  leaderboard_entries
  leaderboard_events
  catalysts
  news_articles
  sentiment_snapshots
  signal_calibration
  pattern_scenarios
)

ARGS=()
for t in "${TABLES[@]}"; do ARGS+=(--table="public.$t"); done

echo "exporting: ${TABLES[*]}"
# INSERTs rather than COPY, because the target is often a hosted console or
# a psql of a different vintage, and ON CONFLICT DO NOTHING makes the file
# safe to load twice. The \restrict lines pg_dump 16.15 emits are stripped:
# they are a newer meta-command and an older psql stops on them.
docker compose exec -T db pg_dump \
  -U aureus -d aureus_dev \
  --data-only --no-owner --no-privileges \
  --on-conflict-do-nothing --rows-per-insert=500 --column-inserts \
  "${ARGS[@]}" | grep -v '^\\\(un\)\?restrict ' > "$OUT"

printf 'wrote %s (%s)\n' "$OUT" "$(du -h "$OUT" | cut -f1)"
printf 'load it with:  psql "$DATABASE_URL" -f %s\n' "$OUT"
