#!/usr/bin/env bash

set -euo pipefail

SERVER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${SERVER_ROOT}/.." && pwd)"
DEPLOY_SCRIPT="${SERVER_ROOT}/run/restart.sh"
QUERY_FASTA="${REPO_ROOT}/tests/data/msa/2KL8.fasta"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/revodesign-full-stack.XXXXXX")"
ENV_FILE="${WORK_DIR}/server-test.env"
RUN_ID="$(basename "${WORK_DIR}" | tr '[:upper:]' '[:lower:]' | tr '.' '-')"
export COMPOSE_PROJECT_NAME="${RUN_ID}"

RUNNER_IMAGE="revodesign-gremlin-runner-${RUN_ID}"
SERVER_IMAGE="revodesign-gremlin-server-${RUN_ID}"
STACK_STARTED=0

cleanup() {
  local status=$?
  set +e
  if [[ ${status} -ne 0 && ${STACK_STARTED} -eq 1 ]]; then
    docker compose -f "${SERVER_ROOT}/docker-compose.yml" --env-file "${ENV_FILE}" logs --no-color --tail=200
  fi
  if [[ -f "${ENV_FILE}" ]]; then
    REVODESIGN_SERVER_ENV="${ENV_FILE}" bash "${DEPLOY_SCRIPT}" down
    DOCKER_GID=0 docker compose -f "${SERVER_ROOT}/docker-compose.yml" --env-file "${ENV_FILE}" \
      down --volumes --remove-orphans
  fi
  docker image rm --force "${SERVER_IMAGE}" "${RUNNER_IMAGE}" >/dev/null 2>&1
  rm -rf "${WORK_DIR}"
  exit "${status}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ ! -f "${QUERY_FASTA}" ]]; then
  echo "Full-stack query fixture not found: ${QUERY_FASTA}" >&2
  exit 1
fi

mkdir -p \
  "${WORK_DIR}/state/server" \
  "${WORK_DIR}/state/auth" \
  "${WORK_DIR}/state/logs" \
  "${WORK_DIR}/miniuc/uc30" \
  "${WORK_DIR}/miniuc/uc90" \
  "${WORK_DIR}/testminiuc/uc30" \
  "${WORK_DIR}/testminiuc/uc90"

cp "${SERVER_ROOT}/.env.example" "${ENV_FILE}"
PORT="$(python -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
RUNNER_UID="$(id -u)"
RUNNER_GID="$(id -g)"
if [[ "${RUNNER_UID}" == "0" ]]; then
  RUNNER_UID=1000
  RUNNER_GID=1000
  chown -R "${RUNNER_UID}:${RUNNER_GID}" "${WORK_DIR}"
elif [[ "${RUNNER_GID}" == "0" ]]; then
  RUNNER_GID="${RUNNER_UID}"
fi
export RUNNER_UID RUNNER_GID
cp -r "${SERVER_ROOT}/config" "${WORK_DIR}/state/server/config"
sed -i "s|/Users/yyy/Documents/protein_design/REvoDesign/playground/miniuc/uc30|${WORK_DIR}/miniuc/uc30|" "${WORK_DIR}/state/server/config/runners/gremlin.yaml"
sed -i "s|/Users/yyy/Documents/protein_design/REvoDesign/playground/miniuc/uc90|${WORK_DIR}/miniuc/uc90|" "${WORK_DIR}/state/server/config/runners/gremlin.yaml"
cat >>"${ENV_FILE}" <<EOF

# Full-stack test overrides
SERVER_IMAGE=${SERVER_IMAGE}
RUNNER_IMAGE=${RUNNER_IMAGE}
SERVER_DIR=${WORK_DIR}/state/server
RUNNER_HOST_ROOT=${WORK_DIR}/state
LOG_DIR=${WORK_DIR}/state/logs
AUTH_DIR=${WORK_DIR}/state/auth
DB_UNIREF30=${WORK_DIR}/miniuc/uc30/miniuc30
DB_UNIREF90=${WORK_DIR}/miniuc/uc90/uniref90
ADMIN_USERS=admin
RUNNER_UID=${RUNNER_UID}
RUNNER_GID=${RUNNER_GID}
NPROC=2
MAXMEM=1
WORKER_CONCURRENCY=1
PORT=${PORT}
GUNICORN_WORKERS=1
CONFIG_DIR=${WORK_DIR}/state/server/config
ENABLED_TASKRUNNERS=gremlin
TZ=UTC
EOF

echo "Building the GREMLIN runner image..."
docker build \
  --build-arg "RUNNER_UID=${RUNNER_UID}" \
  --build-arg "RUNNER_GID=${RUNNER_GID}" \
  --build-arg RUNNER_USERNAME=revodesign \
  --build-arg RUNNER_GROUP=revodesign_appgroup \
  --file "${SERVER_ROOT}/docker/runners/pssm_gremlin/Dockerfile" \
  --tag "${RUNNER_IMAGE}" \
  "${SERVER_ROOT}"

echo "Preparing and validating miniUC databases using the GREMLIN toolchain..."
docker run --rm \
  --entrypoint /bin/bash \
  --volume "${REPO_ROOT}:/repo:ro" \
  --volume "${WORK_DIR}:/work" \
  "${RUNNER_IMAGE}" -euo pipefail -c '
    export CONDA_PREFIX=/opt/conda/envs/GREMLIN
    export PATH="${CONDA_PREFIX}/bin:${PATH}"
    makeblastdb \
      -in /repo/tests/data/msa/2KL8_blast.fasta \
      -dbtype prot -parse_seqids \
      -out /work/miniuc/uc90/uniref90
    psiblast \
      -query /repo/tests/data/msa/2KL8.fasta \
      -db /work/miniuc/uc90/uniref90 \
      -out_pssm /work/testminiuc/uc90/2KL8.ckp \
      -out_ascii_pssm /work/testminiuc/uc90/2KL8_ascii.mtx \
      -out /work/testminiuc/uc90/2KL8.out \
      -evalue 0.01 -num_iterations 3 -num_threads 2
    cd /work/miniuc/uc30
    ffindex_from_fasta -s miniuc30_a3m.ffdata miniuc30_a3m.ffindex \
      /repo/tests/data/msa/2KL8.i90c75_aln.fas
    cstranslate \
      -A "${CONDA_PREFIX}/data/cs219.lib" \
      -D "${CONDA_PREFIX}/data/context_data.crf" \
      -x 0.3 -c 4 -f -i miniuc30_a3m -o miniuc30_cs219 -I a3m -b
    cd /repo
    hhblits \
      -i tests/data/msa/2KL8.fasta \
      -oa3m /work/testminiuc/uc30/2KL8.a3m \
      -o /work/testminiuc/uc30/2KL8.hhr \
      -d /work/miniuc/uc30/miniuc30 \
      -n 4 -e 1e-10 -mact 0.35 -maxfilt 1e8 -neffmax 20 \
      -cpu 2 -nodiff -realign_max 1e7 -maxmem 1
  '

echo "Building the GREMLIN server image..."
docker build \
  --build-arg "RUNNER_UID=${RUNNER_UID}" \
  --build-arg "RUNNER_GID=${RUNNER_GID}" \
  --build-arg RUNNER_USERNAME=revodesign \
  --build-arg RUNNER_GROUP=revodesign_appgroup \
  --build-arg "PORT=${PORT}" \
  --file "${SERVER_ROOT}/docker/server/Dockerfile" \
  --tag "${SERVER_IMAGE}" \
  "${SERVER_ROOT}"

echo "Launching the full server stack from the generated test environment..."
if ! UP_OUTPUT="$(REVODESIGN_SERVER_ENV="${ENV_FILE}" bash "${DEPLOY_SCRIPT}" up 2>&1)"; then
  printf '%s\n' "${UP_OUTPUT}" | sed 's/password: .*/password: [REDACTED]/'
  echo "The server stack failed to launch." >&2
  exit 1
fi
STACK_STARTED=1
ADMIN_CREDENTIAL_FILE="$(printf '%s\n' "${UP_OUTPUT}" | sed -n 's/^Bootstrap admin credentials written to: \([^ ]*\) (mode 0600)$/\1/p' | tail -n 1)"
if [[ -z "${ADMIN_CREDENTIAL_FILE}" || ! -f "${ADMIN_CREDENTIAL_FILE}" ]]; then
  echo "The launch output did not identify the protected admin credential file." >&2
  exit 1
fi
ADMIN_PASSWORD="$(awk -F '\t' '$1 == "admin" { print $2; exit }' "${ADMIN_CREDENTIAL_FILE}")"
if [[ -z "${ADMIN_PASSWORD}" ]]; then
  echo "The protected credential file did not contain the test admin account." >&2
  exit 1
fi
echo "Loaded the generated admin password from the protected credential file."

echo "Running API, web-page, and GREMLIN pipeline checks..."
FULL_STACK_ADMIN_PASSWORD="${ADMIN_PASSWORD}" python "${SERVER_ROOT}/tests/full_stack_smoke.py" \
  --base-url "http://127.0.0.1:${PORT}" \
  --fasta "${QUERY_FASTA}"
echo "Full-stack Docker test passed."
