# REvoCompute Operations and Task Adapter Guide

This guide is the end-to-end runbook for building, validating, and launching
REvoCompute with Docker Compose, SLURM, and Apptainer. It also defines the
contract for adapting a new scientific task type. Commands use placeholders;
keep deployment credentials and machine-local paths in the selected mode-0600
environment file and external configuration directory.

The short version of the production rule is: build and validate everything
while the healthy stack is still running, then use `--mode=prepared` for the
small activation window. SIF rebuilds are the exception: run
`restart --use-proxy --build-sif`, which stops the stack, stages each stale
SIF as `<sif>.next`, and promotes it after the build (no manual SIF
deletion) — so plan the batch runner changes around the outage window.

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

**Conda vs pip guidance:** Prefer pip-based installs (`python:X-slim` + `pip install`) for
new runner families when scientific dependencies (JAX, ColabDesign, OpenMM) have
compatible CUDA wheels on PyPI. Use conda when:
- A conda-forge package precisely matches a host driver/ABI constraint that pip
  wheels cannot satisfy (e.g. older jaxlib CUDA segfault constraints as in the
  `alphafold` family with host driver >=570).
- Pre-existing conda environments are already deployed and shared across families.
Sharing a family deduplicates Docker/SIF storage; it must not force CPU tasks to
inherit a large GPU stack or allow incompatible package upgrades. A new family is
justified only when dependencies, accelerator needs, system ABI, or license make
sharing unsafe — see the table in `RUNTIME_FAMILIES.md`. The FreeBindCraft
adaptation used a pip-based `python:3.11-slim` image with `jax[cuda12]==0.6.0`
because sharing the `alphafold` family would force an incompatible jax upgrade
(0.4.35 → 0.6.x) that would break existing alphafold tasks.

**OpenCL ICD note:** GPU tasks that use OpenMM relax (e.g. FreeBindCraft) prefer
the OpenCL platform and require the OpenCL ICD loader plus an NVIDIA ICD vendor
file. Install `ocl-icd-libopencl1` and create
`/etc/OpenCL/vendors/nvidia.icd` containing `libnvidia-opencl.so.1`. This
enables `openmm.Platform.getPlatformNames()` to report `OpenCL` alongside `CPU`
and (if CUDA wheels are installed) `CUDA`. The environment variable
`OPENMM_PLATFORM_ORDER=OpenCL,CUDA` sets the preferred order (FreeBindCraft
sets this). Without the ICD, OpenMM falls back to CPU, which may be significantly
slower.

For CPU-only tasks, omit `--nv` (Apptainer/SLURM) and do not register the ICD.

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

Every production `slurm_image` must be absolute and versioned. The control
module never overwrites a working SIF in place: restarts stage rebuilds as
`<sif>.next` and promote them after `down`, saving the previous file as
`<sif>.previous` (see §8). Runner YAML files must not contain `runner`,
`job_executor`, `container_runtime`, `slurm_image`, or `gpus`.

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

The portable registry in `${CONFIG_DIR}/task_types.yaml` is machine-owned
and `restart.sh` does not sync it. After any change to the checked-in
`server/config/task_types.yaml`, back up the host copy, copy the repo file
over it, and re-apply the two machine lines (`job_executor: slurm`,
`container_runtime: apptainer`) before the next restart. Verify with
`GET /compute/api/types` after activation.

GPU requests belong to task types (`gpus: true`) and per-task SLURM resources
are managed through the admin UI and are not placed in runner YAML.

Configure canonical `cpus`, `memory`, and `max_runtime_seconds` globally or per
task in `/compute/configuration`. Per-task values inherit from global defaults
when left empty. SLURM partition/GRES/nodes/tasks/QOS/account/constraint and
exclusive placement are separate validated fields. Legacy database values
(`cpus`, `memory`, `max_runtime_seconds`, and `slurm_time`) are
migration fallbacks only; do not create new ones.

Before migration, back up `manage.sqlite`. Record the effective policy shown by
the admin API for every enabled task, write canonical overrides, and compare
again before activation. Accepted tasks snapshot their resolved policy, so do
not edit queued task records manually. Prepared activation runs the candidate
worker's read-only resource audit before `down` and refuses invalid memory,
runtime, GPU, or partition configuration.

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

The `prepare` subcommand builds only the selected runner images and does not
call `down` or rebuild web/worker:

```bash
REVODESIGN_SERVER_ENV="${REVODESIGN_SERVER_ENV}" \
  bash server/run/restart.sh prepare --enabled-runners=example --use-proxy
```

Add `--build-sif` to stage the selected runners' SIFs while production remains
up. The broader `build` subcommand builds every enabled runner plus web/worker:

```bash
REVODESIGN_SERVER_ENV="${REVODESIGN_SERVER_ENV}" \
  bash server/run/restart.sh build --use-proxy
```

`--use-proxy` reads `REVODESIGN_BUILD_PROXY` from the selected environment
file and passes it only as build arguments. Final runner stages explicitly
clear proxy variables. Never add a literal proxy URL to a Dockerfile.

A bare `restart` uses `--mode=dev`: it stops the stack, rebuilds every runtime
family and the server image, then starts the stack. This is expected behavior,
but it is not the activation command for an existing SLURM/SIF deployment. If
the configured SIFs are already prepared, use `restart --mode=prepared`.
Docker runner images need rebuilding only to produce a replacement SIF or test
Docker execution.

The build loop creates one image per runtime family and then the server image.
The deployment tag scheme is `next` → `latest` → `previous`, managed
automatically:

- `prepare` and `build` tag selected runner families as `<image>:next` and leave the running
  deployment untouched. A candidate can be validated as `:next` (or a
  hand-built `:candidate`) without changing `latest`.
- A `restart` captures the pre-down digests, stops the stack, then promotes:
  changed families advance `latest` → `previous` → `:next` → `latest`;
  unchanged families see zero churn (the redundant `:next` tag is dropped).
  `previous` always survives the post-deploy prune, so the last deployment
  is one `restart --rollback` away.
- `--mode=prod` pulls `latest` directly; the pre-pull image id becomes
  `previous`.
- `--mode=prepared` promotes selected runner images that a prior `prepare` or
  `build` left at `:next`; other images remain unchanged.

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

Validate a candidate with networking disabled and isolated inputs/outputs.
Runner protocol v2 passes a task manifest, not environment variables: the
runner reads `TASK_MANIFEST` (path to `task.json`) and receives `-i` as
that same manifest path; `run.sh` derives parameters and the primary
input from it via the shared `task_context.sh` helpers. Add `--gpus all`
and the real weights mount for GPU tasks.

```bash
smoke_dir=$(mktemp -d /tmp/revocompute-example-smoke.XXXXXX)
chmod 0777 "${smoke_dir}"
cat > "${smoke_dir}/task.json" <<'EOF'
{
  "task_type": "example",
  "params": {"samples": 1},
  "files": [{"name": "input.pdb", "path": "/mnt/revocompute/test/inputs/input.pdb", "relative_path": "nested/input.pdb"}]
}
EOF
docker run --rm --network none \
  -e TASK_MANIFEST=/mnt/revocompute/test/task.json \
  -v "${smoke_dir}/task.json":/mnt/revocompute/test/task.json:ro \
  -v /path/to/approved/input.pdb:/mnt/revocompute/test/inputs/input.pdb:ro \
  -v "${smoke_dir}":/mnt/revocompute/test/outputs:rw \
  revodesign-revocompute-runner-example:candidate \
  -i /mnt/revocompute/test/task.json \
  -o /mnt/revocompute/test/outputs
```

## 8. Rebuild SIFs from current images

SIFs rebuild through staged `.next` files — the running SIF is never touched
in place and no manual delete is needed:

```bash
REVODESIGN_SERVER_ENV="${REVODESIGN_SERVER_ENV}" \
  bash server/run/restart.sh restart --use-proxy --build-sif
```

`restart --build-sif` stages `<sif>.next` for every family whose SIF is
missing or **older than the family's docker image** — image updates that
were deployed without a SIF rebuild (in any earlier restart) are caught
automatically. Limit a catch-up build to one family with
`--enabled-runners=<name>` when the full set would be too costly. After
`down`, promotion moves the staged file into place with `os.replace`,
saving the current SIF as `<sif>.previous` for `restart --rollback`.
Staging is atomic (built to `<sif>.next.build`, renamed on success), so a
killed build can never leave a corrupt `.next`. One SIF per family at the
registry path; no versioned `.sif.partial` files. `--build-sif` is
incompatible with `--mode=prepared`. For a focused single-family
iteration, the manual build from the exact registry `definition` remains
available:

```bash
apptainer build --fakeroot "/absolute/image-dir/example_v1.sif" \
  server/docker/runners/example/example.def
```

Adjust `--fakeroot` only to the host's established Apptainer privilege model.
Do not weaken system security or run the deployment script as root. If disk
space runs out, recover before retrying: `docker buildx prune`, clean the
Apptainer cache with `APPTAINER_CACHEDIR=/home/yinying/.apptainer/ apptainer
cache clean --type all`, and remove obsolete SIFs under
`/mnt/data/srv/revodesign/server-slurm/images/`.

Smoke the SIF through the same `run.sh` contract (protocol v2: `-i` is the
task manifest path, `TASK_MANIFEST` points at it):

```bash
smoke_dir=$(mktemp -d /tmp/revocompute-example-smoke.XXXXXX)
chmod 0777 "${smoke_dir}"
cat > "${smoke_dir}/task.json" <<'EOF'
{"task_type": "example", "params": {"samples": 1},
 "files": [{"name": "input.pdb", "path": "/mnt/revocompute/test/inputs/input.pdb", "relative_path": "input.pdb"}]}
EOF
apptainer run --cleanenv --containall \
  -e TASK_MANIFEST=/mnt/revocompute/test/task.json \
  --bind "${smoke_dir}/task.json":/mnt/revocompute/test/task.json:ro \
  --bind /path/to/input.pdb:/mnt/revocompute/test/inputs/input.pdb:ro \
  --bind "${smoke_dir}":/mnt/revocompute/test/outputs:rw \
  "/absolute/image-dir/example_v1.sif" \
  -i /mnt/revocompute/test/task.json \
  -o /mnt/revocompute/test/outputs
```

For a GPU task add `--nv` and prove SLURM allocated a GPU. CPU tasks must not
receive `--nv`.

## 9. Deploy stamp and external configuration backup

Every prepared/prod `restart` automates the backup and writes a deploy stamp:

- **Config backup** — before `down`, `${CONFIG_DIR}` is copied (as the
  runner identity, inside a throwaway container) to
  `${SERVER_DIR}/backups/config-<timestamp>`. Older backups are never
  deleted. For a manual, standalone backup the same result is:

  ```bash
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  backup_root="${SERVER_DIR}/backups/config-${stamp}"
  mkdir -p "${backup_root}"
  cp -a "${CONFIG_DIR}/." "${backup_root}/"
  ```

- **Deploy stamp** — after a successful `up`, `${CONFIG_DIR}/.deploy-stamp`
  records the commit sha and dirty flag, mode, per-step timings,
  changed/unchanged families, `latest`/`previous`/`next` digests, SIF
  sha256s for changed families, the registry sha256, and the config-backup
  path. `restart --rollback` consumes it: it verifies the `previous` image
  tags and SIFs exist, restores the config backup when the registry sha256
  has drifted, retags `previous` → `latest` for the changed set, and sweeps
  down/up to readiness — never touching tasks, results, or the user database.

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

### Offline model weights

Treat model weights like versioned runtime artifacts, not disposable home
directory caches. Download into a staging directory on a filesystem with
enough capacity, verify the publisher checksum, reject archive traversal, and
promote the extracted tree to a shared, read-only path. Mount only that path in
the family runner YAML and set the tool's documented cache/data variables to
it. Where supported, prove a production smoke succeeds without runtime network
downloads.

ThermoMPNN-D requires both upstream archives: its ThermoMPNN ensemble weights
and the vanilla ProteinMPNN backbone weights. The MPNN runner sets
`XDG_DATA_HOME`, `THERMOMPNN_WEIGHT_DIR`, and
`THERMOMPNN_VANILLA_WEIGHT_DIR`, validates representative non-empty checkpoint
files, and refuses runtime downloads. BioEmu, ESM, EasIFA, and similar families
must likewise use operator-provisioned shared weight mounts rather than
`/home/<user>/.cache`, which may be small or node-local.

## 10. Prepared activation and rollback

The safe activation sequence is:

```text
plan: --dry-run prints the walk + per-family change predictions
                    |
drain (optional): --drain=N blocks submissions, waits for SLURM jobs
                    |
            validate registry/runners/images/SIFs/Compose
                    |
             any failure? ---- yes ---> keep current stack running
                    |
                    no
                    v
       config backup + digest baseline + down (sweep kills stragglers)
                    |
                    v
        promote: :next -> :latest, latest -> previous, SIF .next in place
                    |
                    v
          up --no-build (no pull)
                    |
                    v
            readiness checks
              |           |
            pass        failure
              |           |
       prune + deploy    restart --rollback (stamp-verified previous set,
       stamp written      config restored on registry drift)
              |
            smoke
```

Dry-run first — it reads only and predicts exactly which families will
change:

```bash
REVODESIGN_SERVER_ENV="${REVODESIGN_SERVER_ENV}" \
  bash server/run/restart.sh restart --mode=prepared --dry-run
```

Activate only after the dry-run prediction matches the prepared artifacts:

```bash
REVODESIGN_SERVER_ENV="${REVODESIGN_SERVER_ENV}" \
  bash server/run/restart.sh restart --mode=prepared --drain=15
```

`--drain=15` blocks new submissions through the web-visible
`${SERVER_DIR}/.maintenance` sentinel (the API answers 503 "Server is in
maintenance; submissions are paused") and waits up to 15 minutes for
in-flight SLURM jobs to finish; the
pre-stop sweep cancels the remainder. The sentinel is removed after a
successful restart and on failure.

Prepared mode performs all artifact/config/Compose checks before `down`, then
starts with existing images and no build or pull. Verify Compose services,
nginx routing, login, task schema, worker/maintenance/Redis health, and fresh
logs. If readiness fails, do not loop restarts — the deployment is one
command away from the previous state:

```bash
REVODESIGN_SERVER_ENV="${REVODESIGN_SERVER_ENV}" \
  bash server/run/restart.sh restart --rollback
```

`--rollback` refuses when no deploy stamp exists, or when any stamped
`previous` image/SIF is missing, naming the stamped commit. It never touches
tasks, results, or the user database.

`--mode=prod` is for genuinely published, pullable images. Do not use it for
local-only runtime tags because it performs pulls after stopping the stack.

## 11. Add a task to an existing runtime family

### 11.0 Current runtime families and their stacks

The per-family stack table (base image/CUDA, Python, frameworks, GPU flags)
lives in [`RUNTIME_FAMILIES.md`](RUNTIME_FAMILIES.md) — pick the family whose
stack matches the new tool before creating a new one.

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
    category: structure
    intro: One-line plain-language description shown on the create-task page.
    runtime_family: example-family
    runner_args: [score]
    gpus: false
    input_extension: .pdb
    input_extensions: [.pdb, .cif, .mmcif]
    primary_input_extensions: [.pdb, .cif, .mmcif]
    allow_multiple_inputs: true
    max_input_files: 32
    input_label: Protein structures
    input_workspace: *structure_workspace
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

`input_workspace` is required on every task type — startup fails closed when a
registry entry omits it. Reference one of the shared `workspace_templates`
anchors defined at the top of the registry (`file`, `fasta`, `structure`), or
declare an inline `capabilities` list.

Supported parameter types are `str`, `text`, `int`, `float`, and `bool` —
`int` and `float` render as number inputs, the rest as text. Use `choices`,
`minimum`, `maximum`, `step`, `unit`, `required`, and `advanced` to constrain
the schema. Do not expose host paths, devices, checkpoint paths, executor
flags, or integrity-bypass switches as user parameters.

Add the task name to `ENABLED_TASKRUNNERS` in the deployment environment. The
frontend form is generated from this schema; do not create a second hard-coded
parameter list in JavaScript.

### 11.2 Implement the runner contract (protocol v2)

The family `run.sh` receives:

- `TASK_MANIFEST`: absolute path to the immutable `task.json` manifest;
- `-i`: that same manifest path;
- `-o`: task-owned output directory;
- optional `runner_args` before `-i`/`-o`.

The manifest carries `params` (verified schema values) and `files` (each with
`name`, mounted `path`, and `relative_path`). The shared `task_context.sh`
helpers read it: `_parse_param <name> [default]` and `primary_input` (the
first file's mounted path). There are no `TASK_PARAMS`/`TASK_INPUTS`
environment variables.

Example skeleton:

```bash
#!/bin/bash
set -euo pipefail
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

while getopts ':i:o:' opt; do
  case "${opt}" in
    i) input_file=${OPTARG} ;;
    o) output_dir=${OPTARG} ;;
    *) exit 2 ;;
  esac
done

[[ -f "${input_file}" ]] || { echo 'Task manifest not found' >&2; exit 1; }
mkdir -p "${output_dir}"
input_file=$(primary_input)

echo 'REVODESIGN_STAGE:parse'
# Read inputs only. Write temporary/generated files under output_dir or /tmp.

echo 'REVODESIGN_STAGE:score'
python3 /opt/example/run.py \
  --input "${input_file}" \
  --output "${output_dir}" \
  --samples "$(_parse_param samples 1)"

# Create the completion marker only after the scientific command exits zero.
touch "${output_dir}/task_finished"
```

Never let a scientific program update files in `inputs/`. Some upstream tools
write MSA caches or normalized inputs next to their source; redirect those
paths to `outputs/` or `/tmp`. Do not mask an internal per-input failure merely
because the upstream process exits zero—validate required outputs and fail the
runner when the scientific result failed.

For multiple inputs, parse the manifest's `files` list rather than scanning a
username-wide host directory. Preserve `relative_path`, reject unsupported
types, and pass only task-snapshot mounted paths to the tool.

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

If the pinned upstream needs code changes, vendor a minimal build-time patch
file in `docker/runners/<family>/` and apply it in the Dockerfile — never fork
the whole repository. Verify the tool does not silently override CLI flags
from model checkpoints: RFdiffusion copies each checkpoint's training config
over the hydra overrides and re-applied them with `bool("false")` (which is
True), flipping `preprocess.sidechain_input` back on for the binder model.
See `docker/runners/placer-rfdiffusion/rfdiffusion-bool-override.patch`.

### 11.4 Test the adapter

At minimum, add tests that prove:

1. the task resolves to the intended shared runtime and one runner YAML;
2. source references are full commit hashes;
3. every declared parameter is consumed by `run.sh`;
4. actual upstream CLI flags match the pinned version's `--help`;
5. CPU images omit unintended NVIDIA/Triton/torchvision/torchaudio packages;
6. nested input paths reach the tool through the manifest `files` list;
7. inputs remain read-only and outputs are task-local;
8. success creates manifestable artifacts and failure does not report complete.

Run an isolated Docker smoke and, before production activation, an actual
server-to-worker-to-SLURM-to-Apptainer smoke with minimum safe parameters —
submit it through the real API with the group test account using a data file
from `tests/data`, then monitor the local SLURM job and read the result logs
from the API (status `GET /compute/api/running/<md5>`, manifest
`GET /compute/api/results/<md5>`, logs `GET /compute/api/results/<md5>/artifacts/<path>`).
The full flow lives in the root CLAUDE.md server live-test workflow.

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
- Production `CONFIG_DIR` registry synced from the repo copy (backup made,
  machine lines re-applied).
- SIFs rebuilt via `restart --use-proxy --build-sif` (stale families staged
  as `.next` and promoted in place); each SIF smoked through the `run.sh`
  contract.
- External config backed up outside the active directory.
- Registry/runner/Compose/prepared-image/SIF preflight passes.
- `restart --mode=prepared` activates with no build or pull.
- Gateway, web, worker, maintenance, Redis, schema, and logs verified.
- Real SLURM smoke records task ID, job ID, resources, GPU passthrough, duration,
  manifest, individual download, preview, and optional archive behavior.
- Local branch head equals its remote tracking branch after push.

If any prerequisite fails, keep or restore the healthy deployment and report
the evidence-backed blocker. Never force activation through a failed preflight.
