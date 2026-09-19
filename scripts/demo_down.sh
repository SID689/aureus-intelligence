#!/usr/bin/env bash
#
# Switch the presentation environment off and clear what it created.
#
#   ./scripts/demo_down.sh
#
# This is the teardown you want after an event. It does NOT remove the
# demo code, because it does not need to: with both switches off, the
# session endpoint 404s, the provider disappears from NextAuth, the
# banner and the landing-page button are not rendered, and the snapshot
# fallback is disabled. The code is inert, and turning it back on for the
# next event is two flags rather than a revert.
#
# What it does:
#   1. DEMO_MODE=false            in backend/.env
#   2. NEXT_PUBLIC_DEMO_MODE=false in frontend/.env.local
#   3. deletes every demo account and everything cascading from it
#   4. drops the warm analysis and price caches
#   5. restarts both services so the flags take effect
#
# To remove the code as well, see the note this prints at the end.

set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf "\n\033[1;33m──\033[0m %s\n" "$1"; }

step "Switching the flags off"
python3 - <<'PY'
import pathlib, re
for path, key in (("backend/.env", "DEMO_MODE"),
                  ("frontend/.env.local", "NEXT_PUBLIC_DEMO_MODE")):
    p = pathlib.Path(path)
    if not p.exists():
        print(f"  {path}: not present, skipped")
        continue
    text = p.read_text(encoding="utf-8")
    if re.search(rf"(?m)^{key}=", text):
        text = re.sub(rf"(?m)^{key}=.*$", f"{key}=false", text)
    else:
        text = text.rstrip("\n") + f"\n{key}=false\n"
    p.write_text(text, encoding="utf-8")
    print(f"  {path}: {key}=false")
PY

step "Deleting demo accounts"
if docker compose ps backend --status running -q | grep -q .; then
  docker compose exec -T backend python -c "
from app.demo.provision import purge_demo_users
print(f'  {purge_demo_users(0)} account(s) removed')
"
else
  echo "  backend is not running, skipped. Run this again once it is up."
fi

step "Dropping the warm caches"
if docker compose ps redis --status running -q | grep -q .; then
  docker compose exec -T redis sh -c '
    n=0
    for pattern in "analysis_warm:*" "price:*" "price_miss:*"; do
      keys=$(redis-cli --scan --pattern "$pattern")
      [ -n "$keys" ] && n=$((n + $(echo "$keys" | wc -l))) && echo "$keys" | xargs redis-cli DEL > /dev/null
    done
    echo "  $n cache key(s) dropped"
  '
else
  echo "  redis is not running, skipped. The keys expire on their own."
fi

step "Recreating the containers"
# Recreate rather than restart. The backend's environment comes from
# `env_file: ./backend/.env`, which compose reads when it CREATES the
# container; a restart reuses the environment it was created with, so the
# flag in the file changes and the running process never sees it. This
# script reported success while demo mode stayed on until that was fixed.
docker compose up -d --force-recreate backend frontend > /dev/null 2>&1 || true

cat <<'NOTE'

Demo mode is off. /demo now refuses, and no account can be provisioned
without payment.

Turning it back on for the next event: set DEMO_MODE=true in backend/.env
and NEXT_PUBLIC_DEMO_MODE=true in frontend/.env.local, then
./scripts/demo_up.sh.

To remove the code as well, revert the two commits that added it:

    git log --oneline --grep="Institutional Demo Mode" --grep="demo flags" --all
    git revert <the two hashes that prints, newest first>

Read that diff before you run it. It also carries fixes that have nothing
to do with the demo and that you probably want to keep: the analysis warm
cache, the shared price cache, the backend-origin fix in next.config.ts
without which any non-compose deployment 500s, the same-origin WebSocket
fallback, the portfolio that reported -100% when nothing was priced, and
the 44px touch targets.

NOTE
