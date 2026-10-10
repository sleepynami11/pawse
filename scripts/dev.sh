#!/usr/bin/env bash
# Start Pawse fresh in Docker (backend + React app): bash scripts/dev.sh   (extra args go to `docker compose up`)
# Frees the app's ports first: stops our old stack, any other container publishing them, and any local
# process listening on them (e.g. a stray or Ctrl+Z-suspended uvicorn). Ports: WEB_PORT (5173), PAWSE_PORT (8765).
set -euo pipefail
cd "$(dirname "$0")/.."
export WEB_PORT="${WEB_PORT:-5173}" PAWSE_PORT="${PAWSE_PORT:-8765}"

docker compose down --remove-orphans
for port in "$PAWSE_PORT" "$WEB_PORT"; do
  for c in $(docker ps -q --filter "publish=$port"); do
    echo "Stopping container $(docker inspect -f '{{.Name}}' "$c" | tr -d /) on port $port"
    docker stop "$c" >/dev/null
  done
  for pid in $(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true); do
    cmd=$(ps -o comm= -p "$pid" || true)
    case "$cmd" in *docker*|*vpnkit*) continue ;; esac  # Docker's own port forwarder, never kill it
    echo "Stopping $cmd (pid $pid) on port $port"
    kill "$pid" 2>/dev/null || true
    kill -CONT "$pid" 2>/dev/null || true  # a suspended process only handles the kill once resumed
  done
done

exec docker compose up --build "$@"
