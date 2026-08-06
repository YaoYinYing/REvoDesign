#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SERVER_ROOT}/docker-compose.yml"
ENV_EXAMPLE_FILE="${SERVER_ROOT}/.env.example"
PRIMARY_ENV_FILE="${SERVER_ROOT}/.env.production"
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

  printf '%s\n' "${PRIMARY_ENV_FILE}"
}

ENV_FILE="$(resolve_env_file)"

usage() {
  cat <<'USAGE'
Usage: bash server/run/restart.sh [setup|build|up|down|reload|restart]
       bash server/run/restart.sh restart [--mode=dev|--mode=prod]

Environment:
  REVODESIGN_SERVER_ENV
          Optional path to env file (absolute or relative to current working directory).
          Defaults to server/.env.production.

Subcommands:
  setup    Prepare the selected env file (create from .env.example if missing) and show detected DOCKER_GID.
  build    Build runner image and web/worker images.
  up       Start redis/web/worker with docker compose.
  down     Stop and remove the compose stack.
  reload   Send HUP to Gunicorn for a zero-downtime application reload.
  restart  Restart in dev mode by default.
           --mode=dev:  down, build local images with host UID/GID, then up.
           --mode=prod: down, pull configured images, then up without building.
USAGE
}

require_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Expected ${ENV_FILE} to exist. Run: REVODESIGN_SERVER_ENV=${ENV_FILE} bash server/run/restart.sh setup" >&2
    exit 1
  fi
}

validate_required_settings() (
  set +u
  set -a
  source "${ENV_FILE}"
  set +a
  set -u

  local missing=()
  local name=""
  local value=""
  for name in SERVER_DIR DB_UNIREF30 DB_UNIREF90 ADMIN_USERS; do
    value="${!name:-}"
    if [[ -z "${value//[[:space:]]/}" ]]; then
      missing+=("${name}")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Missing required setting(s) in ${ENV_FILE}: ${missing[*]}" >&2
    exit 1
  fi
)

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
    # Try the named group first; fall back to the user's primary group;
    # default to 1000 when neither resolves (macOS CI, etc.).
    RUNNER_GID="$(getent group "${_group}" 2>/dev/null | cut -d: -f3 || true)"
    if [[ -z "${RUNNER_GID}" ]]; then
      RUNNER_GID="$(id -g "${_user}" 2>/dev/null || true)"
    fi
    RUNNER_GID="${RUNNER_GID:-1000}"
  fi
  RUNNER_UID="${RUNNER_UID:-1000}"

  export RUNNER_UID RUNNER_GID
  echo "Using runner identity ${RUNNER_UID}:${RUNNER_GID} (user ${_user}, group ${_group})."
}

prepare_result_storage() {
  set +u
  set -a
  source "${ENV_FILE}"
  set +a
  set -u

  local results_dir="${SERVER_DIR}/results"
  mkdir -p "${results_dir}"
  if [[ "$(id -u)" == "0" ]]; then
    if ! chown "${RUNNER_UID}:${RUNNER_GID}" "${results_dir}"; then
      echo "Warning: could not change ownership of ${results_dir}; the backing filesystem may not support chown." >&2
    fi
  fi
  if ! chmod u+rwx,go+rx "${results_dir}"; then
    echo "Warning: could not change permissions of ${results_dir}; continuing with container access checks." >&2
    printf 'To apply the permissions manually, run: sudo chmod u+rwx,go+rx %q\n' "${results_dir}" >&2
  fi
}

validate_result_storage() {
  if ! "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T web \
    sh -c 'test -w "$1" && test -x "$1"' sh "${SERVER_DIR}/results"; then
    echo "Results directory is not writable by the web container: ${SERVER_DIR}/results" >&2
    exit 1
  fi
  if ! "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T gateway \
    sh -c 'test -r /srv/results && test -x /srv/results'; then
    echo "Results directory is not readable by the Nginx gateway: ${SERVER_DIR}/results" >&2
    exit 1
  fi
}

require_production_identity() {
  resolve_runner_identity
  if [[ "${RUNNER_UID}" != "1000" || "${RUNNER_GID}" != "1000" ]]; then
    echo "Production images require RUNNER_UID=1000 and RUNNER_GID=1000; got ${RUNNER_UID}:${RUNNER_GID}." >&2
    exit 1
  fi
}

validate_auth_storage() (
  set +u
  set -a
  source "${ENV_FILE}"
  set +a
  set -u
  if [[ -z "${AUTH_DIR:-}" ]]; then
    echo "AUTH_DIR must be set to a web-only host directory outside SERVER_DIR." >&2
    exit 1
  fi
  python3 -c '
import os, sys
server_dir, auth_dir = map(os.path.realpath, sys.argv[1:3])
if os.path.commonpath([server_dir, auth_dir]) == server_dir:
    raise SystemExit("AUTH_DIR must be outside SERVER_DIR")
' "${SERVER_DIR}" "${AUTH_DIR}"
)

ADMIN_LOGIN_LINES=()

prepare_admin_bootstrap() {
  set +u
  set -a
  source "${ENV_FILE}"
  set +a
  set -u

  local auth_dir="${AUTH_DIR:-${SCRIPT_DIR}/../auth-data}"
  local user_db="${auth_dir}/users.sqlite3"
  local needs_admin_bootstrap=""
  local admin_bootstrap_credentials=""
  local admin_username=""
  local admin_pw=""
  local seen_admin=""
  local -a configured_admins=()
  local -a seen_admins=()

  if [[ -n "${ADMIN_BOOTSTRAP_CREDENTIALS:-}" ]]; then
    return
  fi

  needs_admin_bootstrap="$(
    python3 - "${user_db}" <<'PY'
import sqlite3
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    print("yes")
else:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            has_users = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'"
            ).fetchone()
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] if has_users else 0
        print("yes" if count == 0 else "no")
    except sqlite3.Error:
        print("no")
PY
  )"
  if [[ "${needs_admin_bootstrap}" != "yes" ]]; then
    return
  fi

  IFS=',' read -r -a configured_admins <<< "${ADMIN_USERS}"
  for admin_username in "${configured_admins[@]}"; do
    admin_username="${admin_username#"${admin_username%%[![:space:]]*}"}"
    admin_username="${admin_username%"${admin_username##*[![:space:]]}"}"
    if [[ -z "${admin_username}" ]]; then
      continue
    fi
    if (( ${#seen_admins[@]} > 0 )); then
      for seen_admin in "${seen_admins[@]}"; do
        if [[ "${seen_admin}" == "${admin_username}" ]]; then
          echo "ADMIN_USERS must not contain duplicate usernames: ${admin_username}" >&2
          exit 1
        fi
      done
    fi
    seen_admins+=("${admin_username}")
    admin_pw="$(openssl rand -hex 16 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(16))')"
    admin_bootstrap_credentials+="${admin_username}"$'\t'"${admin_pw}"$'\n'
    ADMIN_LOGIN_LINES+=("Admin login — username: ${admin_username}  password: ${admin_pw}")
  done
  if [[ ${#ADMIN_LOGIN_LINES[@]} -eq 0 ]]; then
    echo "ADMIN_USERS must contain at least one username." >&2
    exit 1
  fi
  export ADMIN_BOOTSTRAP_CREDENTIALS="${admin_bootstrap_credentials}"
}

print_admin_logins() {
  if [[ ${#ADMIN_LOGIN_LINES[@]} -gt 0 ]]; then
    printf '%s\n' "${ADMIN_LOGIN_LINES[@]}"
  fi
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
  validate_required_settings
  ensure_docker_gid
  resolve_runner_identity

  echo "Building GREMLIN runner image..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" --profile runner build runner

  echo "Building web/worker images..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" build web worker
}

cmd_up() {
  require_env_file
  validate_required_settings
  validate_auth_storage
  prepare_admin_bootstrap
  ensure_docker_gid
  resolve_runner_identity
  prepare_result_storage
  echo "Starting services via docker compose..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up "$@" -d redis web gateway maintenance worker
  validate_result_storage
  print_admin_logins
}

cmd_down() {
  require_env_file
  ensure_docker_gid
  resolve_runner_identity
  echo "Stopping services via docker compose..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
}

cmd_reload() {
  require_env_file
  echo "Sending HUP to Gunicorn..."
  "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec web pkill -HUP gunicorn
}

cmd_restart() {
  require_env_file
  validate_required_settings
  # Source the validated deployment settings.
  set +u
  set -a
  source "${ENV_FILE}"
  set +a
  set -u

  if [[ "${MODE}" == "prod" ]]; then
    require_production_identity
  fi

  prepare_admin_bootstrap
  cmd_down

  case "${MODE}" in
    dev)
      cmd_build
      ;;
    prod)
      echo "Pulling configured production images..."
      "${COMPOSE_CMD[@]}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" --profile runner pull web gateway runner
      ;;
  esac
  cmd_up --no-build

  DOMAIN="0.0.0.0"
  PORT="${PORT:-8080}"
  echo "Deployment completed."
  echo "Nginx gateway is now running at http://${DOMAIN}:${PORT}/compute/dashboard"
}

SUBCOMMAND="${1:-restart}"
MODE="dev"

if [[ $# -gt 2 ]]; then
  echo "Too many arguments." >&2
  usage
  exit 1
fi
if [[ $# -eq 2 ]]; then
  case "$2" in
    --mode=dev)
      MODE="dev"
      ;;
    --mode=prod)
      MODE="prod"
      ;;
    --mode=*)
      echo "Invalid mode: ${2#--mode=}. Expected dev or prod." >&2
      usage
      exit 1
      ;;
    *)
      echo "Unexpected argument: $2. Use --mode=dev or --mode=prod." >&2
      usage
      exit 1
      ;;
  esac
  if [[ "${SUBCOMMAND}" != "restart" ]]; then
    echo "--mode is only supported by the restart subcommand." >&2
    usage
    exit 1
  fi
fi

echo "Using env file: ${ENV_FILE}"

pushd "${SERVER_ROOT}" >/dev/null

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
  reload)
    cmd_reload
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
