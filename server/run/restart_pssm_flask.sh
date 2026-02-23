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

resolve_socket_path() {
  local path="$1"
  local target=""
  local depth=0

  if [[ "${path}" == unix://* ]]; then
    path="${path#unix://}"
  fi

  while [[ -L "${path}" && ${depth} -lt 10 ]]; do
    target="$(readlink "${path}" 2>/dev/null || true)"
    if [[ -z "${target}" ]]; then
      break
    fi
    if [[ "${target}" = /* ]]; then
      path="${target}"
    else
      path="$(cd "$(dirname "${path}")" && pwd)/${target}"
    fi
    depth=$((depth + 1))
  done

  if [[ -S "${path}" ]]; then
    printf '%s\n' "${path}"
    return 0
  fi
  return 1
}

detect_docker_gid() {
  local endpoint=""
  local socket_candidates=()
  local resolved_path=""
  local gid=""

  endpoint="$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)"
  if [[ "${endpoint}" == unix://* ]]; then
    socket_candidates+=("${endpoint}")
  fi
  socket_candidates+=("/var/run/docker.sock")

  for candidate in "${socket_candidates[@]}"; do
    if ! resolved_path="$(resolve_socket_path "${candidate}")"; then
      continue
    fi
    gid="$(
      stat -Lc '%g' "${resolved_path}" 2>/dev/null ||
        stat -f '%g' "${resolved_path}" 2>/dev/null ||
        stat -c '%g' "${resolved_path}" 2>/dev/null ||
        true
    )"
    if [[ -n "${gid}" ]]; then
      printf '%s\n' "${gid}"
      return 0
    fi
  done
  return 1
}

if [[ -z "${DOCKER_GID:-}" ]]; then
  DOCKER_GID="$(detect_docker_gid || true)"
  if [[ -n "${DOCKER_GID}" ]]; then
    export DOCKER_GID
    echo "Using Docker socket group id ${DOCKER_GID}."
  else
    echo "Unable to auto-detect Docker socket group id; default DOCKER_GID from compose will be used." >&2
  fi
fi

echo "${ENV_FILE}"
echo "Building GREMLIN runner image..."
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" --profile runner build runner

echo "Building web/worker images..."
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" build web worker


echo "Restarting services via docker compose..."
"${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --build redis web worker

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
