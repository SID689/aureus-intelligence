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
#
# The output goes to a file rather than through `tail`, which was showing
# the last fifteen lines and therefore hiding every error that happened
# before them. A load that fails on the first table and succeeds on the
# last looked identical to one that worked.
LOG=$(mktemp)
docker compose exec -T db psql -v ON_ERROR_STOP=0 "$TARGET" -f - < "$FILE" > "$LOG" 2>&1 || true

rows=$(grep -c '^INSERT' "$LOG" || true)
errs=$(grep -c 'ERROR:' "$LOG" || true)
printf '  %s insert statements applied, %s error(s)\n' "$rows" "$errs"

if [ "$errs" -gt 0 ]; then
  echo
  echo "  distinct errors:"
  grep 'ERROR:' "$LOG" | sed 's/^psql:[^:]*:[0-9]*: //' | sort -u | head -10 | sed 's/^/    /'
  echo
  echo "  full log: $LOG"
fi

echo
echo "row counts on the target:"
docker compose exec -T db psql -tA "$TARGET" -c "
  SELECT 'scanner universe     ' || count(*) FROM scanner_universe
  UNION ALL SELECT 'scanner snapshots    ' || count(*) FROM scanner_snapshots
  UNION ALL SELECT 'leaderboard entries  ' || count(*) FROM leaderboard_entries
  UNION ALL SELECT 'catalysts            ' || count(*) FROM catalysts
  UNION ALL SELECT 'news articles        ' || count(*) FROM news_articles;"
