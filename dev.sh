#!/usr/bin/env bash
#
# dev.sh — start/stop the whole Aureus development environment in one command.
#
# Ollama has been removed from the product (see
# backend/app/analysis/llm_provider.py): paid tiers synthesise with
# Anthropic and the free tier is deterministic, so there is no longer a
# second process manager to coordinate. This script is now a thin,
# memorable wrapper over Docker Compose.
#
#   ./dev.sh up        bring the stack up
#   ./dev.sh down      take it down (Postgres volume preserved)
#   ./dev.sh status    show what is running
#   ./dev.sh logs      tail the backend
#
set -euo pipefail

cd "$(dirname "$0")"


c_green() { printf '\033[0;32m%s\033[0m\n' "$1"; }
c_yellow() { printf '\033[0;33m%s\033[0m\n' "$1"; }
c_red() { printf '\033[0;31m%s\033[0m\n' "$1"; }

cmd_up() {
  echo "→ Starting Docker stack..."
  docker compose up -d
  c_green "✓ Stack up"

  echo
  echo "  Frontend   http://localhost:3000"
  echo "  API docs   http://localhost:8000/docs"
}

cmd_down() {
  echo "→ Stopping Docker stack..."
  docker compose down
  c_green "✓ Stack down"
  echo
  echo "  Postgres data volume is preserved — nothing was deleted."
}

cmd_status() {
  echo "Docker:"
  if docker compose ps --format '  {{.Name}}  {{.Status}}' 2>/dev/null | grep -q .; then
    docker compose ps --format '  {{.Name}}  {{.Status}}'
  else
    echo "  (no containers running)"
  fi
  echo
}

case "${1:-up}" in
  up)     cmd_up ;;
  down)   cmd_down ;;
  status) cmd_status ;;
  logs)   docker compose logs -f backend ;;
  *)
    c_red "Unknown command: $1"
    echo "Usage: ./dev.sh [up | down | status | logs]"
    exit 1
    ;;
esac
