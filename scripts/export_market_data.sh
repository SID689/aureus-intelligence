#!/usr/bin/env bash
#
# Copy the market data out of this machine's database, to bootstrap
# another one.
#
#   ./scripts/export_market_data.sh                 -> market_data.sql
#   ./scripts/export_market_data.sh out.sql
#
# A newly created database has the schema and nothing in it, so the
# leaderboard has no ranked names, the catalyst timeline has no dates and
# the news wire is blank. Those tables are filled by the background
# scanner over a market session or two, and a deployment without workers
# never fills them at all.
#
# This machine has already done that work. What ships is market data
# only: no users, portfolios, subscriptions, consents, credits or game
# sessions.
#
# Load it with scripts/load_market_data.sh, which runs psql from inside
# the postgres container so no database client has to be installed.

set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-market_data.sql}"

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
# INSERTs rather than COPY, because the target is often a hosted console
# or a psql of a different vintage, and ON CONFLICT DO NOTHING makes the
# file safe to load twice. The \restrict lines pg_dump 16.15 emits are
# stripped: they are a newer meta-command and an older psql stops on them.
docker compose exec -T db pg_dump \
  -U aureus -d aureus_dev \
  --data-only --no-owner --no-privileges \
  --on-conflict-do-nothing --rows-per-insert=500 --column-inserts \
  "${ARGS[@]}" | grep -v '^\\\(un\)\?restrict ' > "$OUT"

printf 'wrote %s (%s)\n' "$OUT" "$(du -h "$OUT" | cut -f1)"
printf 'load it with:  ./scripts/load_market_data.sh "$DATABASE_URL" %s\n' "$OUT"
