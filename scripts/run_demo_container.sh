#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.demo.yml}"
HOST="${AQUAGENESYS_DEMO_HOST:-127.0.0.1}"
PORT="${AQUAGENESYS_DEMO_PORT:-}"
PORT_CANDIDATES=(8782 8783 8784 8785)

docker compose -f "${COMPOSE_FILE}" down --remove-orphans >/dev/null 2>&1 || true

port_is_free() {
  local host="$1"
  local port="$2"
  python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError:
        sys.exit(1)
PY
}

if [[ -z "${PORT}" ]]; then
  for candidate in "${PORT_CANDIDATES[@]}"; do
    if port_is_free "${HOST}" "${candidate}"; then
      PORT="${candidate}"
      break
    fi
  done
fi

if [[ -z "${PORT}" ]]; then
  echo "No free demo port found in: ${PORT_CANDIDATES[*]}" >&2
  exit 1
fi

if ! port_is_free "${HOST}" "${PORT}"; then
  echo "Selected demo port is occupied: ${HOST}:${PORT}" >&2
  exit 1
fi

export AQUAGENESYS_DEMO_HOST="${HOST}"
export AQUAGENESYS_DEMO_PORT="${PORT}"

docker compose -f "${COMPOSE_FILE}" build
docker compose -f "${COMPOSE_FILE}" up -d

origin="http://${HOST}:${PORT}"
for _ in $(seq 1 45); do
  if curl -fsS "${origin}/api/frame" >/dev/null 2>&1; then
    echo "Aquagenesys demo container running:"
    echo "Local origin: ${origin}"
    echo "Cloudflare Tunnel origin target: ${origin}"
    echo "Recommended launch mode: --no-deliberation"
    echo "Stop command: scripts/stop_demo_container.sh"
    exit 0
  fi
  sleep 1
done

echo "Aquagenesys demo container did not become healthy at ${origin}" >&2
docker compose -f "${COMPOSE_FILE}" logs --tail=100 >&2
exit 1
