#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SERVER_DIR}/docker-compose.yml"
PRIMARY_ENV_FILE="${SERVER_DIR}/.env.production"
FALLBACK_ENV_FILE="${SERVER_DIR}/.env"
CALLER_DIR="$(pwd)"

resolve_env_file() {
  if [[ -n "${REVODESIGN_SERVER_ENV:-}" ]]; then
    if [[ "${REVODESIGN_SERVER_ENV}" = /* ]]; then
      printf '%s\n' "${REVODESIGN_SERVER_ENV}"
    else
      printf '%s/%s\n' "${CALLER_DIR}" "${REVODESIGN_SERVER_ENV}"
    fi
    return 0
  fi

  if [[ -f "${PRIMARY_ENV_FILE}" ]]; then
    printf '%s\n' "${PRIMARY_ENV_FILE}"
  else
    printf '%s\n' "${FALLBACK_ENV_FILE}"
  fi
}

ENV_FILE="$(resolve_env_file)"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Expected ${ENV_FILE} to exist. Create it from server/.env.example, or set REVODESIGN_SERVER_ENV to another env file." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif docker-compose --version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "docker compose plugin was not found. Install Docker Compose v2 or docker-compose." >&2
  exit 1
fi

echo "Using env file: ${ENV_FILE}"
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec web pkill -HUP gunicorn

echo "Sent HUP to gunicorn for zero-downtime config reload."
