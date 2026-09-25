#!/usr/bin/env bash
#
# Load exported market data into another Postgres.
#
#   ./scripts/load_market_data.sh "postgresql://...neon.tech/neondb?sslmode=require"
#   ./scripts/load_market_data.sh "$URL" market_data.sql
#
# Runs psql from inside the postgres:16 container the local stack already
# has, so there is nothing to install. The container reaches the internet
# like any other; the URL is just a remote host to it.
#
# Pair with export_market_data.sh, which writes the file. Safe to re-run:
# every statement is INSERT ... ON CONFLICT DO NOTHING.

set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-}"
FILE="${2:-market_data.sql}"

if [ -z "$TARGET" ]; then
  echo "usage: $0 <postgres-url> [file]" >&2
  exit 1
fi
[ -f "$FILE" ] || { echo "$FILE does not exist. Run ./scripts/export_market_data.sh first." >&2; exit 1; }

echo "loading $FILE ($(du -h "$FILE" | cut -f1))"
# ON_ERROR_STOP off: conflicts on a re-run are rows correctly skipped.
docker compose exec -T db psql -v ON_ERROR_STOP=0 "$TARGET" -f - < "$FILE" | tail -15

echo
echo "row counts on the target:"
docker compose exec -T db psql -tA "$TARGET" -c "
  SELECT 'scanner universe     ' || count(*) FROM scanner_universe
  UNION ALL SELECT 'scanner snapshots    ' || count(*) FROM scanner_snapshots
  UNION ALL SELECT 'leaderboard entries  ' || count(*) FROM leaderboard_entries
  UNION ALL SELECT 'catalysts            ' || count(*) FROM catalysts
  UNION ALL SELECT 'news articles        ' || count(*) FROM news_articles;"
