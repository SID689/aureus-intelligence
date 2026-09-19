#!/usr/bin/env bash
#
# Apply the schema and every migration, in order, to any Postgres.
#
#   ./scripts/migrate.sh                      # the local compose database
#   ./scripts/migrate.sh "$NEON_URL"          # a hosted one
#
# Ordering is the whole point: db/schema.sql first, then db/migrations/*
# by filename. Several migrations depend on types the previous one created,
# and 014 adds a value to an enum, which Postgres refuses inside a
# transaction block. Running each file through psql separately keeps every
# statement in its own implicit transaction, which is what that needs.
#
# Safe to re-run: the migrations are written with IF NOT EXISTS / IF NOT
# EXISTS guards. schema.sql is not, so on a database that already has the
# schema it will report "already exists" and continue.

set -uo pipefail
cd "$(dirname "$0")/.."

TARGET="${1:-}"

run() {
  local file="$1"
  printf '  %-44s ' "$(basename "$file")"
  if [ -z "$TARGET" ]; then
    docker compose exec -T db psql -v ON_ERROR_STOP=0 -U aureus -d aureus_dev -q -f - < "$file" > /tmp/migrate.out 2>&1
  else
    # Through the container's psql, so a hosted database needs no client
    # installed on this machine. Falls back to a local psql if the stack
    # is not running.
    if docker compose ps db --status running -q > /dev/null 2>&1 && [ -n "$(docker compose ps db --status running -q 2>/dev/null)" ]; then
      docker compose exec -T db psql -v ON_ERROR_STOP=0 -q "$TARGET" -f - < "$file" > /tmp/migrate.out 2>&1
    else
      psql -v ON_ERROR_STOP=0 -q "$TARGET" -f "$file" > /tmp/migrate.out 2>&1
    fi
  fi
  # psql prefixes its diagnostics with "psql:<file>:<line>: ", so ERROR is
  # never at the start of a line. Anchoring the match was the difference
  # between this script reporting a clean run and reporting the truth.
  #
  # Three diagnostics are expected rather than wrong:
  #   already exists          - a re-run over objects that are already there
  #   duplicate key           - seed rows that are already seeded
  #   no unique or exclusion  - db/schema.sql and 009 both seed
  #     constraint matching     vendor_subscriptions, and schema.sql
  #                             replaces UNIQUE(vendor) with
  #                             (vendor, plan_name) afterwards, so 009's
  #                             second attempt no longer matches a
  #                             constraint. The rows are already in place;
  #                             the failing statement has nothing to add.
  local errors real
  errors=$(grep -c 'ERROR:' /tmp/migrate.out || true)
  if [ "$errors" -gt 0 ]; then
    real=$(grep 'ERROR:' /tmp/migrate.out \
           | grep -vci -e 'already exists' -e 'duplicate key' -e 'no unique or exclusion constraint' || true)
    if [ "$real" -gt 0 ]; then
      printf 'FAILED\n'
      grep 'ERROR:' /tmp/migrate.out \
        | grep -vi -e 'already exists' -e 'duplicate key' -e 'no unique or exclusion constraint' | head -5
      return 1
    fi
    printf 'ok (%s already in place)\n' "$errors"
  else
    printf 'ok\n'
  fi
}

if [ -z "$TARGET" ]; then
  echo "applying to the local compose database"
else
  echo "applying to the database in the connection string given"
fi

failed=0
run db/schema.sql || failed=1
for f in db/migrations/*.sql; do run "$f" || failed=1; done

if [ "$failed" -eq 0 ]; then
  echo "schema is up to date"
else
  echo "one or more files failed, see the output above"
  exit 1
fi
