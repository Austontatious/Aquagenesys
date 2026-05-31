#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.demo.yml}"

docker compose -f "${COMPOSE_FILE}" down
