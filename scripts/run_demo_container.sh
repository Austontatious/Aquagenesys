#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.demo.yml}"
HOST="${AQUAGENESYS_DEMO_HOST:-127.0.0.1}"
PORT="${AQUAGENESYS_DEMO_PORT:-}"
DELIBERATION_ENABLED="${AQUAGENESYS_DELIBERATION_ENABLED:-false}"
PUBLIC_DEMO="${AQUAGENESYS_PUBLIC_DEMO:-false}"
AUTO_RESET_ON_EXTINCTION="${AQUAGENESYS_AUTO_RESET_ON_EXTINCTION:-true}"
AUTO_RESET_EXTINCTION_TICKS="${AQUAGENESYS_AUTO_RESET_EXTINCTION_TICKS:-8}"
PORT_CANDIDATES=(8782 8783 8784 8785)

usage() {
  cat <<'EOF'
Usage: scripts/run_demo_container.sh [--deliberation|--no-deliberation] [--unlocked-controls|--locked-controls]

Starts the Aquagenesys demo container on a localhost-only port.

Options:
  --deliberation      Enable optional Lexi/vLLM fish deliberation for controlled testing.
  --no-deliberation   Disable model deliberation. This is the default launch mode.
  --unlocked-controls Allow reset, randomize, and deliberation toggle. This is the default limited-release mode.
  --locked-controls   Use restricted controls: reset and speed only.
  --auto-reset        Reset the run after true extinction. Enabled by default for the demo container.
  --no-auto-reset     Leave true extinction visible indefinitely.
  --auto-reset-ticks N
                      Wait N extinct ticks before auto-reset. Default: 8.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deliberation | --with-deliberation)
      DELIBERATION_ENABLED="true"
      shift
      ;;
    --no-deliberation)
      DELIBERATION_ENABLED="false"
      shift
      ;;
    --unlocked-controls)
      PUBLIC_DEMO="false"
      shift
      ;;
    --locked-controls)
      PUBLIC_DEMO="true"
      shift
      ;;
    --auto-reset)
      AUTO_RESET_ON_EXTINCTION="true"
      shift
      ;;
    --no-auto-reset)
      AUTO_RESET_ON_EXTINCTION="false"
      shift
      ;;
    --auto-reset-ticks)
      if [[ $# -lt 2 || ! "$2" =~ ^[0-9]+$ ]]; then
        echo "--auto-reset-ticks requires a non-negative integer" >&2
        exit 2
      fi
      AUTO_RESET_EXTINCTION_TICKS="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

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
export AQUAGENESYS_DELIBERATION_ENABLED="${DELIBERATION_ENABLED}"
export AQUAGENESYS_PUBLIC_DEMO="${PUBLIC_DEMO}"
export AQUAGENESYS_AUTO_RESET_ON_EXTINCTION="${AUTO_RESET_ON_EXTINCTION}"
export AQUAGENESYS_AUTO_RESET_EXTINCTION_TICKS="${AUTO_RESET_EXTINCTION_TICKS}"

docker compose -f "${COMPOSE_FILE}" build
docker compose -f "${COMPOSE_FILE}" up -d

origin="http://${HOST}:${PORT}"
for _ in $(seq 1 45); do
  if curl -fsS "${origin}/api/frame" >/dev/null 2>&1; then
    echo "Aquagenesys demo container running:"
    echo "Local origin: ${origin}"
    echo "Cloudflare Tunnel origin target: ${origin}"
    if [[ "${DELIBERATION_ENABLED}" == "true" ]]; then
      echo "Launch mode: optional AI deliberation enabled"
    else
      echo "Launch mode: --no-deliberation"
    fi
    if [[ "${PUBLIC_DEMO}" == "true" ]]; then
      echo "Controls: locked public-demo mode (reset and speed allowed)"
    else
      echo "Controls: unlocked tuning mode"
    fi
    echo "Auto-reset on extinction: ${AUTO_RESET_ON_EXTINCTION} after ${AUTO_RESET_EXTINCTION_TICKS} extinct ticks"
    echo "Stop command: scripts/stop_demo_container.sh"
    exit 0
  fi
  sleep 1
done

echo "Aquagenesys demo container did not become healthy at ${origin}" >&2
docker compose -f "${COMPOSE_FILE}" logs --tail=100 >&2
exit 1
