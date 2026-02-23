#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SERVER_DIR}/docker-compose.yml"
ENV_FILE="${SERVER_DIR}/.env"
ENV_EXAMPLE_FILE="${SERVER_DIR}/.env.example"

usage() {
  cat <<'USAGE'
Usage: bash server/run/restart_pssm_flask.sh [setup|build|up|down|restart]

Subcommands:
  setup    Prepare server/.env defaults (create from .env.example if missing) and auto-detect DOCKER_GID.
  build    Build runner image and web/worker images.
  up       Start redis/web/worker with docker compose.
  down     Stop and remove the compose stack.
  restart  Run down + build + up. Default when no subcommand is provided.
USAGE
}

require_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Expected ${ENV_FILE} to exist. Run: bash server/run/restart_pssm_flask.sh setup" >&2
    exit 1
  fi
}

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

set_env_var() {
  local key="$1"
  local value="$2"
  if grep -Eq "^${key}=" "${ENV_FILE}"; then
    sed -i.bak -E "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
    rm -f "${ENV_FILE}.bak"
  else
    printf '\n%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
  fi
}

cmd_setup() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    if [[ ! -f "${ENV_EXAMPLE_FILE}" ]]; then
      echo "Missing ${ENV_EXAMPLE_FILE}; cannot initialize ${ENV_FILE}." >&2
      exit 1
    fi
    cp "${ENV_EXAMPLE_FILE}" "${ENV_FILE}"
    echo "Created ${ENV_FILE} from ${ENV_EXAMPLE_FILE}."
  fi

  if [[ -z "${DOCKER_GID:-}" ]]; then
    DOCKER_GID="$(detect_docker_gid || true)"
  fi
  if [[ -n "${DOCKER_GID:-}" ]]; then
    set_env_var "DOCKER_GID" "${DOCKER_GID}"
    echo "Set DOCKER_GID=${DOCKER_GID} in ${ENV_FILE}."
  else
    echo "Unable to auto-detect Docker socket group id; set DOCKER_GID manually in ${ENV_FILE}." >&2
  fi

  echo "Setup completed. Review ${ENV_FILE} before starting services."
}

cmd_build() {
  require_env_file
  if [[ -z "${DOCKER_GID:-}" ]]; then
    DOCKER_GID="$(detect_docker_gid || true)"
    if [[ -n "${DOCKER_GID}" ]]; then
      export DOCKER_GID
      echo "Using Docker socket group id ${DOCKER_GID}."
    fi
  fi

  echo "Building GREMLIN runner image..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" --profile runner build runner

  echo "Building web/worker images..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" build web worker
}

cmd_up() {
  require_env_file
  echo "Starting services via docker compose..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d redis web worker
}

cmd_down() {
  require_env_file
  echo "Stopping services via docker compose..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
}

cmd_restart() {
  cmd_down
  cmd_build
  cmd_up

  set +u
  set -a
  source "${ENV_FILE}"
  set +a
  set -u

  DOMAIN="${DOMAIN:-0.0.0.0}"
  PORT="${PORT:-8080}"
  echo "Deployment completed."
  echo "Flask app is now running at http://${DOMAIN}:${PORT}/PSSM_GREMLIN/dashboard"
}

SUBCOMMAND="${1:-restart}"

pushd "${SERVER_DIR}" >/dev/null

case "${SUBCOMMAND}" in
  setup)
    cmd_setup
    ;;
  build)
    cmd_build
    ;;
  up)
    cmd_up
    ;;
  down)
    cmd_down
    ;;
  restart)
    cmd_restart
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown subcommand: ${SUBCOMMAND}" >&2
    usage
    exit 1
    ;;
esac

popd >/dev/null
