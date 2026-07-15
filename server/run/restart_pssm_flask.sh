#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SERVER_DIR}/docker-compose.yml"
ENV_EXAMPLE_FILE="${SERVER_DIR}/.env.example"
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
    return 0
  fi
  if [[ -f "${FALLBACK_ENV_FILE}" ]]; then
    printf '%s\n' "${FALLBACK_ENV_FILE}"
    return 0
  fi

  # For `setup`, default to creating .env.production when neither file exists.
  printf '%s\n' "${PRIMARY_ENV_FILE}"
}

ENV_FILE="$(resolve_env_file)"

usage() {
  cat <<'USAGE'
Usage: bash server/run/restart_pssm_flask.sh [setup|build|up|down|restart]

Environment:
  REVODESIGN_SERVER_ENV
          Optional path to env file (absolute or relative to current working directory).
          Default behavior: use server/.env.production when present, otherwise server/.env.

Subcommands:
  setup    Prepare the selected env file (create from .env.example if missing) and show detected DOCKER_GID.
  build    Build runner image and web/worker images.
  up       Start redis/web/worker with docker compose.
  down     Stop and remove the compose stack.
  restart  Run down + build + up. Default when no subcommand is provided.
USAGE
}

require_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Expected ${ENV_FILE} to exist. Run: REVODESIGN_SERVER_ENV=${ENV_FILE} bash server/run/restart_pssm_flask.sh setup" >&2
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

  # Docker Desktop and OrbStack run the daemon behind a macOS socket path, but
  # containers see the bind-mounted /var/run/docker.sock as root:root.  The
  # supplementary group must match the container-visible socket group.
  if [[ "$(uname -s)" == "Darwin" ]]; then
    printf '0\n'
    return 0
  fi

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

ensure_docker_gid() {
  if [[ -z "${DOCKER_GID:-}" ]]; then
    DOCKER_GID="$(detect_docker_gid || true)"
  fi
  if [[ -z "${DOCKER_GID:-}" ]]; then
    echo "Unable to auto-detect Docker socket group id; set DOCKER_GID for this command." >&2
    exit 1
  fi
  export DOCKER_GID
  echo "Using Docker socket group id ${DOCKER_GID}."
}

resolve_runner_identity() {
  # Auto-derive RUNNER_UID / RUNNER_GID from RUNNER_USERNAME / RUNNER_GROUP
  # when numeric IDs aren't already set.  This lets the env file declare
  # "RUNNER_USERNAME=revodesign" without hardcoding per-host uid/gid.
  local _user="${RUNNER_USERNAME:-revodesign}"
  local _group="${RUNNER_GROUP:-revodesign_appgroup}"

  if [[ -z "${RUNNER_UID:-}" ]]; then
    RUNNER_UID="$(id -u "${_user}" 2>/dev/null || echo "")"
  fi
  if [[ -z "${RUNNER_GID:-}" ]]; then
    RUNNER_GID="$(getent group "${_group}" 2>/dev/null | cut -d: -f3 || stat -f '%g' /dev/null 2>/dev/null || echo "")"
  fi
  # Fallback for environments where id/getent aren't available (macOS CI, etc.)
  RUNNER_UID="${RUNNER_UID:-1000}"
  RUNNER_GID="${RUNNER_GID:-1000}"

  export RUNNER_UID RUNNER_GID
  echo "Using runner identity ${RUNNER_UID}:${RUNNER_GID} (user ${_user}, group ${_group})."
}

cmd_setup() {
  local _detected_docker_gid=""

  if [[ ! -f "${ENV_FILE}" ]]; then
    if [[ ! -f "${ENV_EXAMPLE_FILE}" ]]; then
      echo "Missing ${ENV_EXAMPLE_FILE}; cannot initialize ${ENV_FILE}." >&2
      exit 1
    fi
    cp "${ENV_EXAMPLE_FILE}" "${ENV_FILE}"
    echo "Created ${ENV_FILE} from ${ENV_EXAMPLE_FILE}."
  fi

  if _detected_docker_gid="$(detect_docker_gid || true)" && [[ -n "${_detected_docker_gid}" ]]; then
    echo "Detected Docker socket group id ${_detected_docker_gid}; restart/build/up/down auto-export it for Docker Compose."
  else
    echo "Unable to auto-detect Docker socket group id; set DOCKER_GID when running build/up/restart." >&2
  fi

  echo "Setup completed. Using env file: ${ENV_FILE}"
  echo "Review ${ENV_FILE} before starting services."
}

cmd_build() {
  require_env_file
  ensure_docker_gid
  resolve_runner_identity

  echo "Building GREMLIN runner image..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" --profile runner build runner

  echo "Building web/worker images..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" build web worker
}

cmd_up() {
  require_env_file
  ensure_docker_gid
  resolve_runner_identity
  echo "Starting services via docker compose..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d redis web worker
}

cmd_down() {
  require_env_file
  ensure_docker_gid
  echo "Stopping services via docker compose..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
}

cmd_restart() {
  # Source env early — first boot may need a generated admin password.
  set +u
  set -a
  source "${ENV_FILE}"
  set +a
  set -u

  _user_db="${SERVER_DIR}/users.sqlite3"
  if [[ ! -f "${_user_db}" ]]; then
    # First boot — generate and export the admin password.
    _admin_pw="$(openssl rand -hex 16 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(16))')"
    export DEFAULT_ADMIN_PASSWORD="${_admin_pw}"
  fi

  cmd_down
  cmd_build
  cmd_up

  DOMAIN="0.0.0.0"
  PORT="${PORT:-8080}"
  echo "Deployment completed."
  echo "Flask app is now running at http://${DOMAIN}:${PORT}/PSSM_GREMLIN/dashboard"
  if [[ -n "${_admin_pw:-}" ]]; then
    echo "Admin login — username: admin  password: ${_admin_pw}"
  fi
}

SUBCOMMAND="${1:-restart}"

echo "Using env file: ${ENV_FILE}"

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
