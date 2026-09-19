#!/usr/bin/env bash
#
# Load the exported market data into a hosted Postgres.
#
#   ./scripts/load_showcase_data.sh "postgresql://...neon.tech/neondb?sslmode=require"
#   ./scripts/load_showcase_data.sh "$URL" showcase_data.sql
#
# Runs psql from inside the postgres:16 container the stack already has,
# so nothing has to be installed on the machine. The container reaches the
# internet the same way any other container does; the URL is a remote host
# as far as it is concerned.
#
# Pair with export_showcase_data.sh, which writes the file.

set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-}"
FILE="${2:-showcase_data.sql}"

if [ -z "$TARGET" ]; then
  echo "usage: $0 <postgres-url> [file]" >&2
  exit 1
fi
[ -f "$FILE" ] || { echo "$FILE does not exist. Run ./scripts/export_showcase_data.sh first." >&2; exit 1; }

echo "loading $FILE ($(du -h "$FILE" | cut -f1)) into the database at the URL given"
# ON_ERROR_STOP stays off: the file is INSERT ... ON CONFLICT DO NOTHING,
# so a re-run reports conflicts it correctly skipped rather than failing.
docker compose exec -T db psql -v ON_ERROR_STOP=0 "$TARGET" -f - < "$FILE" | tail -20

echo
echo "row counts on the target:"
docker compose exec -T db psql -tA "$TARGET" -c "
  SELECT 'scanner_universe    ' || count(*) FROM scanner_universe
  UNION ALL SELECT 'scanner_snapshots   ' || count(*) FROM scanner_snapshots
  UNION ALL SELECT 'leaderboard_entries ' || count(*) FROM leaderboard_entries
  UNION ALL SELECT 'catalysts           ' || count(*) FROM catalysts
  UNION ALL SELECT 'news_articles       ' || count(*) FROM news_articles;"
