#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SERVER_DIR}/docker-compose.yml"
ENV_FILE="${SERVER_DIR}/.env"

pushd "${SERVER_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Expected ${ENV_FILE} to exist. Copy server/.env.example and update it before restarting." >&2
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

if [[ -z "${DOCKER_GID:-}" && -S /var/run/docker.sock ]]; then
  DOCKER_GID="$(
    stat -Lc '%g' /var/run/docker.sock 2>/dev/null ||
      stat -Lf '%g' /var/run/docker.sock 2>/dev/null ||
      stat -c '%g' /var/run/docker.sock 2>/dev/null ||
      stat -f '%g' /var/run/docker.sock 2>/dev/null ||
      true
  )"
  if [[ -n "${DOCKER_GID}" ]]; then
    export DOCKER_GID
    echo "Using Docker socket group id ${DOCKER_GID}."
  fi
fi

echo "${ENV_FILE}"
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" build


echo "Restarting services via docker compose..."
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" restart redis web worker

set +u
set -a
source "${ENV_FILE}"
set +a
set -u

DOMAIN="${PSSM_GREMLIN_DOMAIN:-localhost}"
PORT="${PSSM_GREMLIN_PORT:-8080}"

echo "Deployment completed."
echo "Your Flask app is now running at http://${DOMAIN}:${PORT}"

popd
