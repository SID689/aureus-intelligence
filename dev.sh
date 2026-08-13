#!/usr/bin/env bash
#
# dev.sh — start/stop the whole Aureus development environment in one command.
#
# The stack spans two process managers: the app runs in Docker Compose, while
# Ollama runs natively on the host via Homebrew. Ollama is deliberately NOT a
# compose service — containerising it would mean re-downloading the model into
# a Docker volume and running inference inside the VM, which is measurably
# slower and costs another ~2GB on a machine that only has 8GB. Keeping it on
# the host lets it use the hardware directly.
#
# This script just drives both together so you don't have to remember the pair.
#
#   ./dev.sh up        start Ollama, wait for it, then bring up the stack
#   ./dev.sh down      stop the stack, then stop Ollama
#   ./dev.sh status    show what's currently running
#   ./dev.sh logs      tail the backend logs
#
#   ./dev.sh up --no-llm     skip Ollama (frees ~2GB; theses stay deterministic)
#
set -euo pipefail

cd "$(dirname "$0")"

OLLAMA_URL="http://localhost:11434"
WAIT_SECONDS=30

c_green() { printf '\033[0;32m%s\033[0m\n' "$1"; }
c_yellow() { printf '\033[0;33m%s\033[0m\n' "$1"; }
c_red() { printf '\033[0;31m%s\033[0m\n' "$1"; }

ollama_installed() { command -v ollama >/dev/null 2>&1; }
ollama_up() { curl -sf -m 2 "$OLLAMA_URL/api/tags" >/dev/null 2>&1; }

OLLAMA_STATE="off"   # set by start_ollama; avoids re-probing a busy machine

start_ollama() {
  if ! ollama_installed; then
    c_yellow "! Ollama not installed — skipping. Theses will use the deterministic engine."
    c_yellow "  Install with: brew install ollama && ollama pull llama3.2:3b"
    return 0
  fi
  if ollama_up; then
    OLLAMA_STATE="on"
    c_green "✓ Ollama already running"
    return 0
  fi

  echo "→ Starting Ollama..."
  brew services start ollama >/dev/null 2>&1 || true

  # Wait for the API rather than assuming it's instant — the app probes it at
  # call time, so a container that boots first would just see it as absent.
  for _ in $(seq 1 "$WAIT_SECONDS"); do
    if ollama_up; then
      OLLAMA_STATE="on"
      c_green "✓ Ollama ready"
      return 0
    fi
    sleep 1
  done
  c_yellow "! Ollama did not become ready in ${WAIT_SECONDS}s — continuing without it."
}

stop_ollama() {
  if ! ollama_installed; then return 0; fi
  echo "→ Stopping Ollama..."
  brew services stop ollama >/dev/null 2>&1 || true
  c_green "✓ Ollama stopped"
}

cmd_up() {
  local with_llm=1
  [[ "${1:-}" == "--no-llm" ]] && with_llm=0

  [[ $with_llm -eq 1 ]] && start_ollama

  echo "→ Starting Docker stack..."
  docker compose up -d
  c_green "✓ Stack up"

  echo
  echo "  Frontend   http://localhost:3000"
  echo "  API docs   http://localhost:8000/docs"
  if [[ "$OLLAMA_STATE" == "on" ]]; then
    echo "  Ollama     ${OLLAMA_URL}  (model: ${OLLAMA_MODEL:-llama3.2:3b})"
  fi
}

cmd_down() {
  echo "→ Stopping Docker stack..."
  docker compose down
  c_green "✓ Stack down"
  stop_ollama
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
  echo -n "Ollama: "
  if ! ollama_installed; then
    echo "not installed"
  elif ollama_up; then
    local models
    models=$(curl -sf -m 2 "$OLLAMA_URL/api/tags" | python3 -c \
      'import json,sys;print(", ".join(m["name"] for m in json.load(sys.stdin).get("models",[])) or "no models pulled")' 2>/dev/null || echo "?")
    c_green "running — $models"
  else
    echo "stopped"
  fi
}

case "${1:-up}" in
  up)     shift || true; cmd_up "${1:-}" ;;
  down)   cmd_down ;;
  status) cmd_status ;;
  logs)   docker compose logs -f backend ;;
  *)
    c_red "Unknown command: $1"
    echo "Usage: ./dev.sh [up [--no-llm] | down | status | logs]"
    exit 1
    ;;
esac
