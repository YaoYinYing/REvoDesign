# REvoCompute Operations and Task Adapter Guide

This guide is the end-to-end runbook for building, validating, and launching
REvoCompute with Docker Compose, SLURM, and Apptainer. It also defines the
contract for adapting a new scientific task type. Commands use placeholders;
keep deployment credentials and machine-local paths in the selected mode-0600
environment file and external configuration directory.

The short version of the production rule is: build and validate everything
while the healthy stack is still running, then use `--mode=prepared` for the
small activation window. Do not use `restart --mode=dev --build-sif` on a
healthy production system because that path stops the stack before building.

## 1. System model

```text
Browser / API client
        |
        v
   nginx gateway
        |
        +--------------------+
        |                    |
        v                    v
  Flask / Gunicorn       result files
        |
        v
      Redis <------ Celery worker
                         |
                         | global job_executor
                         |
             +-----------+-----------+
             |                       |
             v                       v
       Docker runner             srun / SLURM
             |                       |
             |                       v
             |                Apptainer SIF
             |                       |
             +-----------+-----------+
                         |
                         v
        task-isolated virtual workspace
        /mnt/revocompute/<username>/
        +-- inputs/   read-only snapshot
        `-- outputs/  writable for this task only
```

There are three configuration boundaries:

| Boundary | File or location | Ownership |
| --- | --- | --- |
| Deployment environment | `REVODESIGN_SERVER_ENV` | Host paths, Compose project, service settings, credentials |
| Portable registry | `${CONFIG_DIR}/task_types.yaml` | Global executor/runtime, runtime families, task schemas |
| Machine runner config | `${CONFIG_DIR}/runners/<family>.yaml` | Mounts, environment, timeout, parameter defaults |

The registry owns `job_executor` and `container_runtime` globally. A runtime
family owns its Docker image, entrypoint, Dockerfile, Apptainer definition, and
absolute SIF path. A task type owns accepted inputs, GPU eligibility, stage
labels, runner arguments, and typed user parameters.

## 2. Host prerequisites

Install and verify these as the non-root deployment account:

```bash
git --version
docker version
docker compose version
apptainer version
sinfo
squeue
```

For SLURM execution, the worker needs the host SLURM commands, configuration,
MUNGE socket/library, and network access to the controller. Compute nodes need
read access to every SIF and database mount plus read/write access to the task
workspace/result roots.

Never run `server/run/restart.sh` through `sudo` or as root. The script checks
this and fails closed. Prepare host directory ownership outside the script;
startup intentionally does not recursively `chmod` or `chown` production data.

## 3. Prepare the deployment environment

Create a deployment-specific file from the example and restrict it before
adding values:

```bash
cp server/.env.example server/.env.production.example-slurm
chmod 0600 server/.env.production.example-slurm
```

Set at least the deployment paths, Compose identity, image names, gateway
settings, admin list, and enabled tasks. For proxy-assisted builds, set
`REVODESIGN_BUILD_PROXY` in this file and invoke `--use-proxy`; do not put its
literal value in a command, Dockerfile, commit, or report.

Always select the file explicitly:

```bash
export REVODESIGN_SERVER_ENV=server/.env.production.example-slurm
```

Confirm Git ignores it and its mode is exactly `0600`:

```bash
git check-ignore -v "${REVODESIGN_SERVER_ENV}"
stat -c '%a %n' "${REVODESIGN_SERVER_ENV}"
```

To inspect deployment paths without dumping the environment, source the file
and print only an allowlist:

```bash
set -a
source "${REVODESIGN_SERVER_ENV}"
set +a
printf 'SERVER_DIR=%s\nCONFIG_DIR=%s\nLOG_DIR=%s\nCOMPOSE_PROJECT_NAME=%s\n' \
  "${SERVER_DIR}" "${CONFIG_DIR}" "${LOG_DIR}" "${COMPOSE_PROJECT_NAME}"
```

Do not run `env`, `set`, or `cat` on a production environment file.

## 4. Configure Docker or SLURM globally

For local Docker task execution:

```yaml
job_executor: docker
container_runtime: docker
```

For production SLURM task execution:

```yaml
job_executor: slurm
container_runtime: apptainer

runtime_families:
  example-family:
    docker_image: revodesign-revocompute-runner-example
    entrypoint: [bash, /app/revocompute/run.sh]
    dockerfile: docker/runners/example/Dockerfile
    definition: docker/runners/example/example.def
    slurm_image: /absolute/versioned/path/example_20260811.sif
```

Every production `slurm_image` must be absolute and versioned. Never overwrite
a working SIF in place. Runner YAML files must not contain `runner`,
`job_executor`, `container_runtime`, or `slurm_image`.

One active runner file exists per runtime family:

```yaml
# ${CONFIG_DIR}/runners/example-family.yaml
mounts:
  - host_path: /absolute/host/database
    container_path: /mnt/db/example
    mode: ro
env:
  EXAMPLE_DATABASE: /mnt/db/example
max_runtime_seconds: 3600
defaults:
  samples: 1
```

GPU requests belong to task types (`gpus: true`) and per-task SLURM resources
belong to the management database/UI. Do not place ignored `gpus`, `nproc`, or
`maxmem` keys in runner YAML.

## 5. Establish a read-only baseline

Before mutation, record Git, service, storage, Docker, SIF, and SLURM state:

```bash
git status --short --branch
git remote -v
git rev-parse HEAD
git log -5 --oneline --decorate
docker compose --env-file "${REVODESIGN_SERVER_ENV}" ps
docker image ls --digests
docker system df -v
df -h / "${SERVER_DIR}" "${CONFIG_DIR}"
sinfo
squeue
```

Also record image IDs, SIF byte sizes/checksums, active runner filenames, the
active registry checksum, and the current deployment commit in a timestamped
audit directory outside the Git checkout. Do not run `docker system prune` and
do not delete images, SIFs, logs, results, or workspaces.

If the worktree is dirty, identify every change and preserve it. Do not reset,
clean, or overwrite production changes.

## 6. Validate source and configuration before builds

Use the repository virtual environment when available:

```bash
cd server
.venv/bin/python -m py_compile tests/full_stack_smoke.py
.venv/bin/python -m pytest -q tests/test_tasks.py
.venv/bin/python -m pytest -q \
  --ignore=tests/test_docker.py \
  --ignore=tests/test_runner_docker_compat.py
cd ..
```

Then validate shell syntax, Compose interpolation, and registry artifacts:

```bash
bash -n server/run/restart.sh
bash -n server/docker/runners/example/run.sh
docker compose --env-file "${REVODESIGN_SERVER_ENV}" config --quiet
```

A failed preflight is a defect to fix. Do not move stale runner YAMLs back into
the active directory or bypass registry validation.

## 7. Build Docker images while production stays up

The `build` subcommand does not call `down`:

```bash
REVODESIGN_SERVER_ENV="${REVODESIGN_SERVER_ENV}" \
  bash server/run/restart.sh build --use-proxy
```

The build loop creates one image per runtime family and then the server image.
Before rebuilding a production tag, preserve its current image ID with a
timestamped rollback tag:

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker image inspect revodesign-revocompute-runner-example:latest --format '{{.Id}}'
docker tag revodesign-revocompute-runner-example:latest \
  "revodesign-rollback/example-${stamp}:latest"
```

For focused development, build a candidate tag first and validate it without
changing `latest`:

```bash
docker build \
  --build-arg RUNNER_UID="$(id -u)" \
  --build-arg RUNNER_GID="$(id -g)" \
  --build-arg RUNNER_USERNAME="$(id -un)" \
  --build-arg RUNNER_GROUP="$(id -gn)" \
  -t revodesign-revocompute-runner-example:candidate \
  -f server/docker/runners/example/Dockerfile server
```

All Git sources must be pinned to full commit hashes. Build tools belong in a
discarded builder stage. Removing a compiler in a later layer does not remove
its bytes from image history.

Validate a candidate with networking disabled and isolated inputs/outputs:

```bash
smoke_dir=$(mktemp -d /tmp/revocompute-example-smoke.XXXXXX)
chmod 0777 "${smoke_dir}"
docker run --rm --network none \
  -e TASK_TYPE=example \
  -e 'TASK_PARAMS={"samples":1}' \
  -e 'TASK_INPUTS=[{"name":"input.pdb","path":"/mnt/revocompute/test/inputs/input.pdb","relative_path":"nested/input.pdb"}]' \
  -v /path/to/approved/input.pdb:/mnt/revocompute/test/inputs/input.pdb:ro \
  -v "${smoke_dir}":/mnt/revocompute/test/outputs:rw \
  revodesign-revocompute-runner-example:candidate \
  -i /mnt/revocompute/test/inputs/input.pdb \
  -o /mnt/revocompute/test/outputs
```

## 8. Build versioned SIFs without stopping production

Do not use `restart --build-sif` for a production upgrade. Build each family
manually from its exact registry `definition` after the corresponding Docker
candidate is complete.

```text
Dockerfile + pinned source
          |
          v
candidate Docker image ---- offline runner smoke
          |
          v
Apptainer definition
          |
          v
versioned .sif.partial ---- inspect/checksum/smoke
          |
          v
atomic rename to versioned .sif
          |
          v
external registry update
```

Example:

```bash
version=20260811_01
partial="/absolute/image-dir/example_${version}.sif.partial"
final="/absolute/image-dir/example_${version}.sif"

apptainer build --fakeroot "${partial}" \
  server/docker/runners/example/example.def
apptainer inspect "${partial}"
sha256sum "${partial}"
mv "${partial}" "${final}"
```

Adjust `--fakeroot` only to the host's established Apptainer privilege model.
Do not weaken system security or run the deployment script as root. A failed
build leaves the old SIF and active registry untouched.

Smoke the SIF through the same `run.sh` contract before registry promotion:

```bash
apptainer run --cleanenv \
  --bind /path/to/input.pdb:/mnt/revocompute/test/inputs/input.pdb:ro \
  --bind /path/to/output:/mnt/revocompute/test/outputs:rw \
  "${final}" \
  -i /mnt/revocompute/test/inputs/input.pdb \
  -o /mnt/revocompute/test/outputs
```

For a GPU task add `--nv` and prove SLURM allocated a GPU. CPU tasks must not
receive `--nv`.

## 9. Back up and promote external configuration

Back up configuration outside the active config directory, preserving modes:

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_root="${SERVER_DIR}/backups/config-${stamp}"
mkdir -p "${backup_root}"
cp -a "${CONFIG_DIR}/." "${backup_root}/"
```

Do not delete older backups. Move obsolete runner files to a timestamped
directory outside `${CONFIG_DIR}/runners`; one active YAML must remain per
family.

Only after candidate SIF validation, update each family's `slurm_image` to the
new absolute versioned path. Preserve real production mounts, partitions,
constraints, defaults, and timeouts.

Measure the prepared registry without running images:

```bash
python server/tools/audit_runtime_sizes.py \
  --task-types "${CONFIG_DIR}/task_types.yaml" \
  --require-all --json
```

Save the JSON outside the worktree and compare deduplicated runtime-family
totals, not one copy per task type.

## 10. Prepared activation and rollback

The safe activation sequence is:

```text
validate registry/runners/images/SIFs/Compose
                    |
             any failure? ---- yes ---> keep current stack running
                    |
                    no
                    v
                  down
                    |
                    v
          up --no-build (no pull)
                    |
                    v
            readiness checks
              |           |
            pass        failure
              |           |
            smoke      restore config,
                       tags and old SIF paths
```

Activate only after rollback tags, old SIFs, config backups, free-space checks,
and smoke inputs are ready:

```bash
REVODESIGN_SERVER_ENV="${REVODESIGN_SERVER_ENV}" \
  bash server/run/restart.sh restart --mode=prepared
```

Prepared mode performs all artifact/config/Compose checks before `down`, then
starts with existing images and no build or pull. Verify Compose services,
nginx routing, login, task schema, worker/maintenance/Redis health, and fresh
logs. If readiness fails, do not loop restarts: restore the config backup,
restore rollback image tags and old SIF paths, start the previous deployment,
and verify the gateway.

`--mode=prod` is for genuinely published, pullable images. Do not use it for
local-only runtime tags because it performs pulls after stopping the stack.

## 11. Add a task to an existing runtime family

Prefer an existing family when the tool has a compatible interpreter,
framework, CPU/GPU model, system libraries, and license. Sharing a family
deduplicates Docker/SIF storage; it must not force CPU tasks to inherit a large
GPU stack or allow incompatible package upgrades.

### 11.1 Add the portable task schema

Add an entry under `task_types`:

```yaml
task_types:
  example_score:
    display_name: Example Score
    runtime_family: example-family
    runner_args: [score]
    gpus: false
    input_extension: .pdb
    input_extensions: [.pdb, .cif, .mmcif]
    primary_input_extensions: [.pdb, .cif, .mmcif]
    allow_multiple_inputs: true
    max_input_files: 32
    input_label: Protein structures
    stage_markers:
      parse: Parse structures
      score: Score structures
    params:
      - name: samples
        type: int
        default: 1
        minimum: 1
        maximum: 100
        description: Independent samples per input
      - name: temperature
        type: float
        default: 0.1
        minimum: 0
        advanced: true
```

Supported parameter types are `str`, `int`, `float`, and `bool`. Use `choices`,
`minimum`, `maximum`, `step`, `unit`, `required`, and `advanced` to constrain the
schema. Do not expose host paths, devices, checkpoint paths, executor flags, or
integrity-bypass switches as user parameters.

Add the task name to `ENABLED_TASKRUNNERS` in the deployment environment. The
frontend form is generated from this schema; do not create a second hard-coded
parameter list in JavaScript.

### 11.2 Implement the runner contract

The family `run.sh` receives:

- `TASK_TYPE`: selected task type;
- `TASK_PARAMS`: JSON object of verified schema values;
- `TASK_INPUTS`: JSON array with `name`, mounted `path`, and `relative_path`;
- `-i`: primary mounted input path;
- `-o`: task-owned output directory;
- optional `runner_args` before `-i`/`-o`.

Example skeleton:

```bash
#!/bin/bash
set -euo pipefail

while getopts ':i:o:' opt; do
  case "${opt}" in
    i) input_file=${OPTARG} ;;
    o) output_dir=${OPTARG} ;;
    *) exit 2 ;;
  esac
done

[[ -f "${input_file}" ]] || { echo 'Primary input is missing' >&2; exit 1; }
mkdir -p "${output_dir}"

param() {
  python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"
}

echo 'REVODESIGN_STAGE:parse'
# Read inputs only. Write temporary/generated files under output_dir or /tmp.

echo 'REVODESIGN_STAGE:score'
python3 /opt/example/run.py \
  --input "${input_file}" \
  --output "${output_dir}" \
  --samples "$(param samples)"

# Create the completion marker only after the scientific command exits zero.
touch "${output_dir}/task_finished"
```

Never let a scientific program update files in `inputs/`. Some upstream tools
write MSA caches or normalized inputs next to their source; redirect those
paths to `outputs/` or `/tmp`. Do not mask an internal per-input failure merely
because the upstream process exits zero—validate required outputs and fail the
runner when the scientific result failed.

For multiple inputs, parse `TASK_INPUTS` rather than scanning a username-wide
host directory. Preserve `relative_path`, reject unsupported types, and pass
only task-snapshot mounted paths to the tool.

### 11.3 Pin and build dependencies

Use a full immutable Git commit and remove `.git` in the same builder layer:

```dockerfile
ARG EXAMPLE_REPO=https://github.com/owner/example.git
ARG EXAMPLE_REF=0123456789abcdef0123456789abcdef01234567
RUN git init /opt/example && \
    git -C /opt/example remote add origin ${EXAMPLE_REPO} && \
    git -C /opt/example fetch --depth 1 origin ${EXAMPLE_REF} && \
    git -C /opt/example checkout --detach FETCH_HEAD && \
    rm -rf /opt/example/.git
```

Install build tools only in the builder stage, consolidate package operations,
and pin scientific dependencies. Do a real import and inference smoke; README
dependency lists frequently omit transitive imports used by inference.

Every Dockerfile must leave proxy variables empty in the final image:

```dockerfile
ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \
    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""
```

### 11.4 Test the adapter

At minimum, add tests that prove:

1. the task resolves to the intended shared runtime and one runner YAML;
2. source references are full commit hashes;
3. every declared parameter is consumed by `run.sh`;
4. actual upstream CLI flags match the pinned version's `--help`;
5. CPU images omit unintended NVIDIA/Triton/torchvision/torchaudio packages;
6. nested input paths reach the tool through `TASK_INPUTS`;
7. inputs remain read-only and outputs are task-local;
8. success creates manifestable artifacts and failure does not report complete.

Run an isolated Docker smoke and, before production activation, an actual
server-to-worker-to-SLURM-to-Apptainer smoke with minimum safe parameters.

## 12. Add a new runtime family

Create a new family only when dependencies, accelerator needs, system ABI, or
license make sharing unsafe. Add exactly these artifacts:

```text
server/config/task_types.yaml
server/config/runners/<family>.yaml
server/docker/runners/<family>/Dockerfile
server/docker/runners/<family>/run.sh
server/docker/runners/<family>/<family>.def
server/tests/... focused contract tests
```

The `.def` must use the same Docker image declared by the registry:

```def
Bootstrap: docker-daemon
From: revodesign-revocompute-runner-example:latest

%runscript
    exec bash /app/revocompute/run.sh "$@"
```

Add one runner YAML, not one per task. Preflight rejects missing, stale, and
duplicate family configurations.

## 13. Result and cleanup contract

Scientific outputs remain uncompressed. The server inventories them into the
manifest used for artifact listing, individual download, range responses, and
text/table/image/structure previews. Archive creation is optional and includes
only manifest-approved artifacts plus `manifest.json`; runner code must not
recursively ZIP arbitrary task directories.

Cleanup treats these as independent targets:

```text
task result tree
optional task ZIP
task workspace snapshot
```

Deletion of one disposable task must not affect another task owned by the same
username.

## 14. Release checklist

- Worktree changes understood; no reset, clean, force-push, merge, or implicit PR.
- Environment file ignored and mode `0600`; no credentials in diffs/logs.
- Existing service/image/SIF/config rollback artifacts recorded.
- Non-container tests and focused adapter tests pass.
- Candidate Docker image built while production stays up.
- Candidate imports and real minimum inference pass offline.
- Versioned SIF built through `.partial`, inspected, checksummed, and smoked.
- External config backed up outside the active directory.
- Registry/runner/Compose/prepared-image/SIF preflight passes.
- `restart --mode=prepared` activates with no build or pull.
- Gateway, web, worker, maintenance, Redis, schema, and logs verified.
- Real SLURM smoke records task ID, job ID, resources, GPU passthrough, duration,
  manifest, individual download, preview, and optional archive behavior.
- Local branch head equals its remote tracking branch after push.

If any prerequisite fails, keep or restore the healthy deployment and report
the evidence-backed blocker. Never force activation through a failed preflight.
