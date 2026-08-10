#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${SERVER_ROOT}/docker-compose.yml"
COMPOSE_SLURM_FILE="${SERVER_ROOT}/docker-compose.slurm.yml"
COMPOSE_RUNNERS_FILE="${SERVER_ROOT}/docker-compose.runners.generated.yml"
ENV_EXAMPLE_FILE="${SERVER_ROOT}/.env.example"
PRIMARY_ENV_FILE="${SERVER_ROOT}/.env.production"
CALLER_DIR="$(pwd)"

# Return compose -f arguments.  When USE_SLURM is set, the slurm override
# file is appended so the worker container gets SLURM client bind-mounts.
compose_files() {
  local files=("-f" "${COMPOSE_FILE}")
  [[ -f "${COMPOSE_RUNNERS_FILE}" ]] && files+=("-f" "${COMPOSE_RUNNERS_FILE}")
  if [[ "${USE_SLURM:-0}" == "1" ]] && [[ -f "${COMPOSE_SLURM_FILE}" ]]; then
    files+=("-f" "${COMPOSE_SLURM_FILE}")
  fi
  printf '%s\n' "${files[@]}"
}

runtime_manifest() {
  local registry_file="${CONFIG_DIR:-${SERVER_ROOT}/config}/task_types.yaml"
  if [[ ! -f "${registry_file}" ]]; then
    echo "Runtime registry is missing: ${registry_file}" >&2
    return 1
  fi
  awk '
    function unquote(value) {
      sub(/^[[:space:]]+/, "", value)
      sub(/[[:space:]]+$/, "", value)
      if (value ~ /^".*"$/ || value ~ /^\047.*\047$/) {
        value = substr(value, 2, length(value) - 2)
      }
      return value
    }
    function emit() {
      if (name == "") return
      if (image == "" || dockerfile == "" || definition == "" || slurm_image == "") {
        print "Incomplete runtime family: " name > "/dev/stderr"
        failed = 1
        return
      }
      print name "\t" image "\t" dockerfile "\t" definition "\t" slurm_image
      emitted++
    }
    /^runtime_families:[[:space:]]*$/ { in_runtimes = 1; next }
    in_runtimes && /^[^[:space:]#]/ { emit(); in_runtimes = 0; next }
    in_runtimes && /^  [^[:space:]#][^:]*:[[:space:]]*$/ {
      emit()
      name = $0
      sub(/^  /, "", name)
      sub(/:[[:space:]]*$/, "", name)
      image = dockerfile = definition = slurm_image = ""
      next
    }
    in_runtimes && /^    docker_image:/ {
      image = $0; sub(/^    docker_image:[[:space:]]*/, "", image); image = unquote(image); next
    }
    in_runtimes && /^    dockerfile:/ {
      dockerfile = $0; sub(/^    dockerfile:[[:space:]]*/, "", dockerfile); dockerfile = unquote(dockerfile); next
    }
    in_runtimes && /^    definition:/ {
      definition = $0; sub(/^    definition:[[:space:]]*/, "", definition); definition = unquote(definition); next
    }
    in_runtimes && /^    slurm_image:/ {
      slurm_image = $0; sub(/^    slurm_image:[[:space:]]*/, "", slurm_image); slurm_image = unquote(slurm_image); next
    }
    END {
      if (in_runtimes) emit()
      if (emitted == 0) {
        print "No runtime families declared in registry" > "/dev/stderr"
        failed = 1
      }
      if (failed) exit 1
    }
  ' "${registry_file}"
}

runtime_definition() {
  local definition=""
  definition="$(runtime_manifest | awk -F '\t' -v family="$1" '$1 == family { print $4; found = 1 } END { if (!found) exit 1 }')" || {
    echo "Unknown runtime family: $1" >&2
    return 1
  }
  printf '%s\n' "${definition}"
}

yaml_scalar() {
  local file="$1"
  local key="$2"
  awk -v wanted="${key}" '
    function unquote(value) {
      sub(/^[[:space:]]+/, "", value)
      sub(/[[:space:]]+$/, "", value)
      if (value ~ /^".*"$/ || value ~ /^\047.*\047$/) value = substr(value, 2, length(value) - 2)
      return value
    }
    $0 ~ "^" wanted ":[[:space:]]*" {
      value = $0
      sub("^" wanted ":[[:space:]]*", "", value)
      print unquote(value)
      found = 1
      exit
    }
    END { if (!found) exit 1 }
  ' "${file}"
}

validate_runtime_files() {
  local config_root="${CONFIG_DIR:-${SERVER_ROOT}/config}"
  local registry_file="${config_root}/task_types.yaml"
  local runners_dir="${config_root}/runners"
  local manifest=""
  local name=""
  local image=""
  local dockerfile=""
  local definition=""
  local runner_yaml=""
  local bootstrap=""
  local definition_image=""
  local expected_image=""
  local image_leaf=""
  local slurm_image=""
  local job_executor=""
  local container_runtime=""
  local known_families=" "

  manifest="$(runtime_manifest)" || return 1
  job_executor="$(yaml_scalar "${registry_file}" job_executor 2>/dev/null || true)"
  container_runtime="$(yaml_scalar "${registry_file}" container_runtime 2>/dev/null || true)"
  if [[ "${job_executor}" != "docker" && "${job_executor}" != "slurm" ]]; then
    echo "job_executor must be docker or slurm in ${registry_file}" >&2
    return 1
  fi
  if [[ ("${job_executor}" == "docker" && "${container_runtime}" != "docker") || \
        ("${job_executor}" == "slurm" && "${container_runtime}" != "apptainer") ]]; then
    echo "container_runtime is inconsistent with job_executor in ${registry_file}" >&2
    return 1
  fi
  [[ -d "${runners_dir}" ]] || {
    echo "Runtime runner directory is missing: ${runners_dir}" >&2
    return 1
  }

  while IFS=$'\t' read -r name image dockerfile definition slurm_image; do
    if [[ ! "${name}" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
      echo "Runtime family name is not safe for Compose: ${name}" >&2
      return 1
    fi
    for relative_path in "${dockerfile}" "${definition}"; do
      case "${relative_path}" in
        /*|..|../*|*/..|*/../*|*\\*)
          echo "Runtime family ${name} has unsafe build path: ${relative_path}" >&2
          return 1
          ;;
      esac
      if [[ ! -f "${SERVER_ROOT}/${relative_path}" ]]; then
        echo "Runtime family ${name} is missing build artifact: ${SERVER_ROOT}/${relative_path}" >&2
        return 1
      fi
    done

    runner_yaml="${runners_dir}/${name}.yaml"
    if [[ ! -f "${runner_yaml}" ]]; then
      echo "Runtime family ${name} is missing runner configuration: ${runner_yaml}" >&2
      return 1
    fi
    if [[ "${job_executor}" == "slurm" && "${slurm_image}" != /* ]]; then
      echo "SLURM runtime family ${name} must declare an absolute slurm_image" >&2
      return 1
    fi

    bootstrap="$(awk '$1 == "Bootstrap:" { sub(/^[^:]*:[[:space:]]*/, ""); print; exit }' "${SERVER_ROOT}/${definition}")"
    definition_image="$(awk '$1 == "From:" { sub(/^[^:]*:[[:space:]]*/, ""); print; exit }' "${SERVER_ROOT}/${definition}")"
    expected_image="${image}"
    image_leaf="${image##*/}"
    if [[ "${image_leaf}" != *:* && "${image}" != *@* ]]; then
      expected_image="${image}:latest"
    fi
    if [[ "${bootstrap}" != "docker-daemon" || "${definition_image}" != "${expected_image}" ]]; then
      echo "Runtime family ${name} definition must use docker-daemon image ${expected_image}" >&2
      return 1
    fi
    known_families+="${name} "
  done <<< "${manifest}"

  for runner_yaml in "${runners_dir}"/*.yaml; do
    [[ -f "${runner_yaml}" ]] || continue
    name="$(basename "${runner_yaml}" .yaml)"
    if [[ "${known_families}" != *" ${name} "* ]]; then
      echo "Stale runner configuration has no runtime family: ${runner_yaml}" >&2
      return 1
    fi
  done
}

generate_runner_compose() {
  # Generate one optional build service per declared runtime family.
  local out="${COMPOSE_RUNNERS_FILE}"
  local name=""
  local image=""
  local dockerfile=""
  local definition=""
  local slurm_image=""
  echo "# Auto-generated by restart.sh — do not edit." > "${out}"
  echo "services:" >> "${out}"
  while IFS=$'\t' read -r name image dockerfile definition slurm_image; do
    [[ "${name}" == "gremlin" ]] && continue  # base runner already in docker-compose.yml
    cat >> "${out}" <<EOF
  runner-${name}:
    profiles: ["runner"]
    image: ${image}
    build:
      context: .
      dockerfile: ${dockerfile}
      args:
        RUNNER_UID: \${RUNNER_UID}
        RUNNER_GID: \${RUNNER_GID}
        RUNNER_USERNAME: \${RUNNER_USERNAME}
        RUNNER_GROUP: \${RUNNER_GROUP}
    command: ["sleep", "infinity"]
    restart: "no"
EOF
  done < <(runtime_manifest)
}

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
       bash server/run/restart.sh restart [--mode=dev|--mode=prod|--mode=prepared]

       SLURM flags (when task_types.yaml selects job_executor: slurm):
           --allowed-slurm-queue q1,q2,...     Comma-separated SLURM partitions.
           --build-sif                         Build .sif images from .def files
                                               (requires apptainer on PATH).

       Build flags (build / restart --mode=dev):
           --use-proxy=<url>                   Use proxy for apt/pip/git during
                                               Docker builds via predefined
                                               non-persisted build arguments.

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
           --mode=prepared: validate local images, SIFs, configuration, and
                            Compose before down, then up without build or pull.
           --use-proxy=<url>  Pass redacted, non-persisted proxy build arguments.
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
  unset SERVER_DIR ADMIN_USERS
  set -a
  source "${ENV_FILE}"
  set +a
  set -u

  local missing=()
  local name=""
  local value=""
  for name in SERVER_DIR ADMIN_USERS; do
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

# ---------------------------------------------------------------------------
# SLURM + Apptainer bootstrapping
# ---------------------------------------------------------------------------

validate_slurm_images() {
  local missing=0
  local name=""
  local image=""
  local dockerfile=""
  local definition=""
  local slurm_image=""

  while IFS=$'\t' read -r name image dockerfile definition slurm_image; do
    if [[ ! -f "${slurm_image}" ]]; then
      echo "[SLURM] Missing SIF image: ${slurm_image}" >&2
      echo "        Build it:  apptainer build --fakeroot ${slurm_image} ${SERVER_ROOT}/${definition}" >&2
      missing=$((missing + 1))
    else
      echo "[SLURM] Found SIF image: ${slurm_image}"
    fi
  done < <(runtime_manifest)

  if [[ ${missing} -gt 0 ]]; then
    echo "[SLURM] ${missing} SIF image(s) missing. Rerun with --build-sif to auto-build, or build manually." >&2
    return 1
  fi
}

build_slurm_images() {
  local name=""
  local image=""
  local dockerfile=""
  local definition=""
  local slurm_image=""
  local def_file=""
  local built=0

  if ! command -v apptainer >/dev/null 2>&1; then
    echo "[SLURM] apptainer not found on PATH; cannot build requested SIF images." >&2
    return 1
  fi

  while IFS=$'\t' read -r name image dockerfile definition slurm_image; do
    def_file="${SERVER_ROOT}/${definition}"
    if [[ -z "${def_file}" || ! -f "${def_file}" ]]; then
      echo "[SLURM] No .def file for runtime family '${name}': ${def_file}" >&2
      return 1
    fi
    if [[ -f "${slurm_image}" ]]; then
      echo "[SLURM] SIF image already exists: ${slurm_image} — skipping."
      continue
    fi
    echo "[SLURM] Building ${slurm_image} from ${def_file}..."
    apptainer build --fakeroot "${slurm_image}" "${def_file}" || {
      echo "[SLURM] Build failed for ${name}." >&2
      return 1
    }
    built=$((built + 1))
  done < <(runtime_manifest)

  if [[ ${built} -gt 0 ]]; then
    echo "[SLURM] Built ${built} SIF image(s)."
  fi
}

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
  local proxy_build_args=()
  require_env_file
  validate_required_settings
  set -a
  source "${ENV_FILE}"
  set +a
  validate_runtime_files
  ensure_docker_gid
  resolve_runner_identity
  generate_runner_compose

  if [[ -n "${USE_PROXY:-}" ]]; then
    echo "Using configured proxy for Docker builds (credential redacted)."
    proxy_build_args+=(
      --build-arg "HTTP_PROXY=${HTTP_PROXY}"
      --build-arg "HTTPS_PROXY=${HTTPS_PROXY}"
      --build-arg "NO_PROXY=${NO_PROXY}"
      --build-arg "http_proxy=${HTTP_PROXY}"
      --build-arg "https_proxy=${HTTPS_PROXY}"
      --build-arg "no_proxy=${NO_PROXY}"
    )
  fi

  echo "Building runner images..."
  while IFS=$'\t' read -r name image dockerfile definition slurm_image; do
    echo "  → ${image} (${name})"
    docker build \
      "${proxy_build_args[@]}" \
      --build-arg RUNNER_UID="${RUNNER_UID}" \
      --build-arg RUNNER_GID="${RUNNER_GID}" \
      --build-arg RUNNER_USERNAME="${RUNNER_USERNAME}" \
      --build-arg RUNNER_GROUP="${RUNNER_GROUP}" \
      -t "${image}" -f "${SERVER_ROOT}/${dockerfile}" "${SERVER_ROOT}"
  done < <(runtime_manifest)

  echo "Building web/worker images..."
  if [[ -n "${USE_PROXY:-}" ]]; then
    local _server_df="${SERVER_ROOT}/docker/server/Dockerfile"
    docker build \
      "${proxy_build_args[@]}" \
      --build-arg RUNNER_UID="${RUNNER_UID}" \
      --build-arg RUNNER_GID="${RUNNER_GID}" \
      --build-arg RUNNER_USERNAME="${RUNNER_USERNAME}" \
      --build-arg RUNNER_GROUP="${RUNNER_GROUP}" \
      --build-arg PORT="${PORT:-8080}" \
      -t "${SERVER_IMAGE:-revodesign-revocompute-server}" \
      -f "${_server_df}" "${SERVER_ROOT}"
  else
    "${COMPOSE_CMD[@]}" $(compose_files) --env-file "${ENV_FILE}" build web worker
  fi

}

validate_prepared_images() {
  local image=""
  local name=""
  local dockerfile=""
  local definition=""
  local slurm_image=""
  local required_images=(
    "${SERVER_IMAGE:-revodesign-revocompute-server:latest}"
    "nginx:1.28-alpine"
    "redis:7.2-alpine"
  )
  while IFS=$'\t' read -r name image dockerfile definition slurm_image; do
    required_images+=("${image}")
  done < <(runtime_manifest)
  for image in "${required_images[@]}"; do
    if ! docker image inspect "${image}" >/dev/null; then
      echo "Prepared Docker image is missing: ${image}" >&2
      return 1
    fi
  done
}

validate_compose_model() {
  "${COMPOSE_CMD[@]}" $(compose_files) --env-file "${ENV_FILE}" config --quiet
}

wait_for_services() {
  local expected=(redis web gateway maintenance worker)
  local running=""
  local service=""
  local attempt=0
  for attempt in $(seq 1 30); do
    running="$("${COMPOSE_CMD[@]}" $(compose_files) --env-file "${ENV_FILE}" ps --status running --services)"
    for service in "${expected[@]}"; do
      if ! grep -qx "${service}" <<< "${running}"; then
        sleep 2
        continue 2
      fi
    done
    echo "All prepared deployment services are running."
    return 0
  done
  echo "Prepared deployment readiness failed; not all required services are running." >&2
  return 1
}

cmd_up() {
  require_env_file
  validate_required_settings
  set -a
  source "${ENV_FILE}"
  set +a
  validate_runtime_files
  if [[ "${USE_SLURM}" == "1" ]]; then
    validate_slurm_images
  fi
  validate_auth_storage
  prepare_admin_bootstrap
  ensure_docker_gid
  resolve_runner_identity
  prepare_result_storage
  echo "Starting services via docker compose..."
  "${COMPOSE_CMD[@]}" $(compose_files) --env-file "${ENV_FILE}" up "$@" -d redis web gateway maintenance worker
  validate_result_storage
  print_admin_logins
}

cmd_down() {
  require_env_file
  ensure_docker_gid
  resolve_runner_identity
  echo "Stopping services via docker compose..."
  "${COMPOSE_CMD[@]}" $(compose_files) --env-file "${ENV_FILE}" down
}

cmd_reload() {
  require_env_file
  echo "Sending HUP to Gunicorn..."
  "${COMPOSE_CMD[@]}" $(compose_files) --env-file "${ENV_FILE}" exec web pkill -HUP gunicorn
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

  validate_runtime_files

  if [[ "${MODE}" == "prod" ]]; then
    require_production_identity
  fi

  prepare_admin_bootstrap

  # Production pulls and development builds must use the same generated
  # runtime-family service manifest from the selected CONFIG_DIR.
  generate_runner_compose

  # A deployment that expects existing SIFs must prove they are present before
  # stopping the healthy stack. Building new SIFs still happens after the
  # corresponding Docker images have been built or pulled.
  if [[ "${USE_SLURM}" == "1" && "${BUILD_SIF}" == "0" ]]; then
    validate_slurm_images
  fi
  if [[ "${USE_SLURM}" == "1" && "${BUILD_SIF}" == "1" ]] && ! command -v apptainer >/dev/null 2>&1; then
    echo "[SLURM] apptainer not found on PATH; refusing to stop the current deployment." >&2
    return 1
  fi

  if [[ "${MODE}" == "prepared" ]]; then
    validate_prepared_images
    if [[ "${USE_SLURM}" == "1" ]]; then
      validate_slurm_images
    fi
    validate_auth_storage
    validate_compose_model
  fi

  cmd_down

  case "${MODE}" in
    dev)
      cmd_build
      ;;
    prod)
      echo "Pulling configured production images..."
      "${COMPOSE_CMD[@]}" $(compose_files) --env-file "${ENV_FILE}" pull web gateway
      while IFS=$'\t' read -r name image dockerfile definition slurm_image; do
        echo "  → ${image} (${name})"
        docker pull "${image}"
      done < <(runtime_manifest)
      ;;
    prepared)
      echo "Activating validated prepared images without builds or pulls."
      ;;
  esac

  # -- SLURM bootstrapping (after Docker images are built/pulled so
  #    build_slurm_images can convert the cached Docker image to SIF)
  if [[ "${USE_SLURM}" == "1" ]]; then
    echo "[SLURM] SLURM+Apptainer runner enabled."
    if [[ "${BUILD_SIF}" == "1" ]]; then
      build_slurm_images
    fi
    if [[ "${BUILD_SIF}" == "1" ]]; then
      validate_slurm_images
    fi
  fi
  cmd_up --no-build
  if [[ "${MODE}" == "prepared" ]]; then
    wait_for_services
  fi

  DOMAIN="0.0.0.0"
  PORT="${PORT:-8080}"
  echo "Deployment completed."
  echo "Nginx gateway is now running at http://${DOMAIN}:${PORT}/compute/dashboard"
  if [[ "${USE_SLURM}" == "1" ]]; then
    echo "[SLURM] SLURM runner is enabled. Configure per-task SLURM settings at /compute/configuration"
  fi
}

SUBCOMMAND="${1:-restart}"
MODE="dev"
USE_SLURM=0
BUILD_SIF=0
USE_PROXY=""
shift  # consume subcommand
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode=dev)
      MODE="dev"
      if [[ "${SUBCOMMAND}" != "restart" ]]; then
        echo "--mode is only supported by the restart subcommand." >&2
        usage
        exit 1
      fi
      ;;
    --mode=prod)
      MODE="prod"
      if [[ "${SUBCOMMAND}" != "restart" ]]; then
        echo "--mode is only supported by the restart subcommand." >&2
        usage
        exit 1
      fi
      ;;
    --mode=prepared)
      MODE="prepared"
      if [[ "${SUBCOMMAND}" != "restart" ]]; then
        echo "--mode is only supported by the restart subcommand." >&2
        usage
        exit 1
      fi
      ;;
    --mode=*)
      echo "Invalid mode: ${1#--mode=}. Expected dev, prod, or prepared." >&2
      usage
      exit 1
      ;;
    --mode)
      echo "Too many arguments. Use --mode=dev, --mode=prod, or --mode=prepared." >&2
      usage
      exit 1
      ;;
    --allowed-slurm-queue)
      shift
      if [[ -z "${1:-}" || "${1:0:2}" == "--" ]]; then
        echo "--allowed-slurm-queue requires a value." >&2
        exit 1
      fi
      export SLURM_ALLOWED_QUEUES="$1"
      ;;
    --build-sif)
      BUILD_SIF=1
      ;;
    --use-proxy=*)
      USE_PROXY="${1#--use-proxy=}"
      export HTTP_PROXY="${USE_PROXY}"
      export HTTPS_PROXY="${USE_PROXY}"
      export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,.local}"
      ;;
    *)
      echo "Unexpected argument: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if [[ "${MODE}" == "prepared" && "${BUILD_SIF}" == "1" ]]; then
  echo "--build-sif is incompatible with --mode=prepared; prepare and validate SIFs before activation." >&2
  exit 1
fi

_REGISTRY_FILE="${SERVER_ROOT}/config/task_types.yaml"
if [[ -f "${ENV_FILE}" ]]; then
  _CONFIG_ROOT="$(
    set +u
    set -a
    source "${ENV_FILE}"
    set +a
    printf '%s' "${CONFIG_DIR:-${SERVER_ROOT}/config}"
  )"
  _REGISTRY_FILE="${_CONFIG_ROOT}/task_types.yaml"
fi
_JOB_EXECUTOR="$(yaml_scalar "${_REGISTRY_FILE}" job_executor 2>/dev/null || true)"
case "${_JOB_EXECUTOR}" in
  slurm)
    USE_SLURM=1
    export SLURM_ENABLED=true
    ;;
  docker)
    USE_SLURM=0
    export SLURM_ENABLED=false
    if [[ "${BUILD_SIF}" == "1" || -n "${SLURM_ALLOWED_QUEUES:-}" ]]; then
      echo "SLURM flags require job_executor: slurm in ${_REGISTRY_FILE}" >&2
      exit 1
    fi
    ;;
  *)
    echo "job_executor must be docker or slurm in ${_REGISTRY_FILE}" >&2
    exit 1
    ;;
esac

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
