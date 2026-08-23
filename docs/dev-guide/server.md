# REvoCompute Server Developer Guide

REvoCompute is a multi-user scientific compute service. Nginx is the only
public service, Flask/Gunicorn handles authenticated API and pages, Celery
workers dispatch isolated jobs, Redis carries the queue, and a maintenance
process owns scheduled cleanup, backups, digests, and log rotation.

This guide explains server behavior and developer validation. Operators should
use the [production operations and task adapter guide](../../server/OPERATIONS_AND_TASK_ADAPTER_GUIDE.md);
the registry schema is described in [task types and runtime families](task-types-design.md).

## Architecture

```text
browser / API client
         |
         v
 nginx gateway (public port)
   |                 |
   |                 `---- authorized result streaming (read-only mount)
   v
 Flask / Gunicorn ---- authentication + task/result/admin APIs
         |
         v
       Redis <---- maintenance scheduler
         |
         v
   Celery worker
         |
         | global job_executor
         +--------------------+
         |                    |
         v                    v
   Docker runner       srun -> SLURM -> Apptainer SIF
         |                    |
         +----------+---------+
                    v
       isolated task snapshot and result tree
```

The five long-lived Compose services are `gateway`, `web`, `worker`,
`maintenance`, and `redis`. Scientific runtime images are not profile-disabled
Compose services; the manifest build/pull loops prepare them and workers launch
them on demand. Only the worker receives the Docker socket. Web is internal and
the gateway mounts results read-only.

## Source layout

```text
server/
├── config/
│   ├── task_types.yaml          portable registry
│   └── runners/                 one machine config per runtime family
├── docker/runners/              Dockerfile, run.sh, and .def per family
├── revocompute/
│   ├── app.py                   app factory and shared setup
│   ├── routes.py                page, task, result, and admin routes
│   ├── task_runtime.py          workspace/result safety and manifests
│   ├── task_types/              registry loader and dataclasses
│   ├── job/runners/             Docker and SLURM implementations
│   ├── maintenance/             scheduled background operations
│   └── static/                  dynamic forms and result preview plugins
├── run/restart.sh               build, activation, password reset, preflight
├── tests/                       unit, static-contract, and integration tests
└── OPERATIONS_AND_TASK_ADAPTER_GUIDE.md
```

## Configuration boundaries

The production environment file is selected explicitly through
`REVODESIGN_SERVER_ENV`. It contains Compose identity, host paths, service
configuration, enabled tasks, and credentials. Keep it Git-ignored and mode
`0600`; never dump it in logs.

`CONFIG_DIR` points to the active registry and runner directory. In production
this is normally an external host directory mounted read-only into web, worker,
and maintenance. Missing `task_types.yaml` is fatal—there is no embedded
GREMLIN fallback that can hide deployment drift.

The registry has three ownership levels:

- global `job_executor` and `container_runtime`;
- runtime-family image, entrypoint, Dockerfile, definition, and versioned SIF;
- task input schema, family selection, GPU flag, fixed arguments, stages, and
  typed parameters.

One runner YAML per runtime family contains only mounts, environment,
`max_runtime_seconds`, and deployment defaults. Per-task enabled state and
SLURM resources live in `manage.sqlite` and are edited through the admin
configuration page.

`ENABLED_TASKRUNNERS` limits advertised/accepted tasks; GREMLIN is always
enabled. The create-task form is generated from `GET /compute/api/types/<name>`
and must not duplicate parameter definitions in JavaScript.

## Task submission and execution

The server accepts constrained single- or multi-file uploads. It preserves safe
relative paths and rejects absolute paths, traversal, unsupported types, and
symlink escape. Each submission creates a task-specific host snapshot:

```text
${SERVER_DIR}/workspaces/<username>/<task-id>/
├── inputs/
└── outputs/
```

The selected Docker or Apptainer runtime sees:

```text
/mnt/revocompute/<username>/
├── inputs/    read-only
└── outputs/   writable only for this task
```

This stable virtual username path is not a shared host home. Tasks belonging to
the same user receive separate host snapshots and cannot inspect or mutate each
other.

The launcher provides `TASK_TYPE`, verified `TASK_PARAMS`, the full
`TASK_INPUTS` manifest, a primary `-i` path, and an `-o` directory. Optional
empty form values are omitted. Runner scripts must validate required files,
write generated data only under outputs or `/tmp`, propagate scientific
failures, and create `task_finished` only after real success.

Docker and SLURM runners share this contract. SLURM starts a job in a valid
existing working directory, stores the actual SLURM job ID, polls queue/account
state, and maps cancellation to `scancel`. A task changes from queued to running
when the allocation wrapper publishes its numeric job ID; the first declared
stage is emitted once as a liveness signal, and later stage markers advance
progress. Execution is not inferred only from local `srun` process state.

GPU task types require user GPU permission and configured GPU resources.
Apptainer receives `--nv` only for GPU tasks. CPU task families must not inherit
GPU passthrough.

## Task and result states

The active task lifecycle includes `pending`, `queued`, `running`, `finished`,
`failed`, and `cancelled`, plus cleanup/deletion audit states. The legacy
`deleted:finshed` spelling remains for database compatibility.

A process exit code of zero is insufficient for `finished`: publication also
requires at least one non-empty scientific artifact. The server atomically
writes `manifest.json` after inventorying the uncompressed output tree.

The dedicated result page treats the manifest as the source of truth. It lists
metadata and supports authenticated individual download, suitable HTTP ranges,
and bounded text, table, image, and structure previews. Structure preview uses
the pinned Mol* bundle inside a sandboxed, opaque-origin iframe. The shell's
isolated CSP permits the bundle's required dynamic evaluation without weakening
the parent page, and the shell script runs only after its viewer DOM exists. The
parent owns a dedicated sun/moon preference in the
`revodesign-molstar-theme` cookie (light by default) and sends it across the
message boundary, so the opaque shell can use the matching pinned Mol* theme
without gaining storage or same-origin access.
The preview falls back safely when the asset, WebGL, or file size is unsuitable.
A ZIP is requested explicitly and built asynchronously from the manifest-approved
set plus `manifest.json`; it is not required for display or task completion.

Cleanup independently targets the selected task's result tree, optional ZIP,
and workspace snapshot. Another task from the same user must remain untouched.

## Important API routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/compute/api/types` | Enabled task and runtime-family schemas |
| `GET` | `/compute/api/types/<name>` | Dynamic submission schema |
| `POST` | `/compute/api/post` | Validated task submission |
| `GET` | `/compute/api/running/<task-id>` | Task state and trace |
| `POST` | `/compute/api/cancel/<task-id>` | Cancel owned task |
| `DELETE` | `/compute/api/delete/<task-id>` | Delete one owned task |
| `GET` | `/compute/api/results/<task-id>` | Manifest and archive state |
| `GET` | `/compute/api/results/<task-id>/artifacts/<path>` | Authorized artifact/range response |
| `POST` | `/compute/api/results/<task-id>/archive` | Request optional ZIP |
| `GET` | `/compute/api/download/<task-id>` | Download an already-created ZIP |

Page routes include `/compute/login`, `/compute/dashboard`,
`/compute/create_task`, `/compute/results/<task-id>`, and admin-only user,
runtime-configuration, and log views. Logged-out protected pages return 401;
logout clears the HttpOnly cookie server-side.

## Authentication and authorization

Browser navigation uses an `HttpOnly`, `SameSite=Lax` cookie. API clients use a
Bearer token or limited API key. Cookie-only state-changing requests are
rejected. API keys cannot perform profile or admin operations. Task reads and
writes are restricted to the owner or an administrator.

Signing keys are ephemeral per preloaded web launch, so restart invalidates
active login, verification, and password-reset tokens. Login and registration
are rate-limited. Administrators cannot remove their own last administrative
authority, and banned users cannot authenticate.

Fresh deployments bootstrap configured admins through transient generated
passwords; secrets are never persisted in the environment file. To rotate a
specific administrator or user credential, run as the non-root deployment
account:

```bash
REVODESIGN_SERVER_ENV=server/.env.production \
  bash server/run/restart.sh reset-passwd <username>
```

The plaintext generated password is shown once to the interactive operator and
must not be copied into logs, commits, or reports.

## Build and activation semantics

```bash
# Build all declared runtime families and the server; does not stop the stack.
REVODESIGN_SERVER_ENV=server/.env.production \
  bash server/run/restart.sh build

# Same build with the proxy configured as REVODESIGN_BUILD_PROXY in the env.
REVODESIGN_SERVER_ENV=server/.env.production \
  bash server/run/restart.sh build --use-proxy

# Activate existing local images/SIFs after complete preflight; no build/pull.
REVODESIGN_SERVER_ENV=server/.env.production \
  bash server/run/restart.sh restart --mode=prepared
```

A bare `restart` defaults to `--mode=dev`, so it performs down, builds every
runtime family and server image, and starts again. This explains why it rebuilds
an unrelated family such as EasIFA. `--mode=prod` pulls after stopping and is
safe only when every configured tag is genuinely published and pullable.

For an existing SLURM deployment, prebuild the Docker images while the
healthy stack runs, then activate with `restart --build-sif`. The activation
is a `--mode=dev` restart: the stack goes down, then the Docker build step
re-runs (cache-warm after the prebuild) and each stale SIF is rebuilt during
the outage. Stale SIFs are staged as `<sif>.next`, promoted in place after
the build, and the replaced SIF is kept as `<sif>.previous`. Add
`--drain=<minutes>` to pause submissions and drain in-flight SLURM jobs
first; without it the pre-stop sweep cancels them when the stack goes down.

Never run the restart helper with `sudo` or as root. It intentionally does not
recursively chmod/chown application data. Build proxies are passed as build
arguments and cleared in final runtime stages; do not hard-code them in
Dockerfiles.

## Model data and caches

Large or required model data belongs on operator-managed shared storage,
mounted read-only through the family runner YAML. Do not rely on
`/home/<runner>/.cache`: it may be small, node-local, or unavailable on another
compute node.

Provision downloads in staging, verify checksums, validate archive paths, and
then promote. ThermoMPNN-D requires both its ensemble weights and the vanilla
ProteinMPNN weights. BioEmu checkpoints, ESM checkpoints, EasIFA metadata, and
other runtime data follow the same offline/shared-storage principle. Runner
preflight should fail clearly before inference when required data is missing.

## Development and tests

```bash
python -m pip install -e 'server/[test]'

cd server
python -m py_compile tests/full_stack_smoke.py
python -m pytest -q tests/test_tasks.py
python -m pytest -q \
  --ignore=tests/test_docker.py \
  --ignore=tests/test_runner_docker_compat.py
cd ..

bash -n server/run/restart.sh
git diff --check
```

Docker integration tests are opt-in because they build/run images. The full
stack shell helper creates and destroys an isolated stack; do not point it at
production. Production smoke testing uses `tests/full_stack_smoke.py` against
the deployed Nginx gateway with credentials supplied through environment
variables, after confirming that submitting a real SLURM job is acceptable.

New task adapters need focused tests for schema validation, upstream CLI flag
compatibility, optional-empty argument omission, nested paths, read-only input,
failure propagation, output validation, and CPU/GPU gating. The final evidence
must include a minimum real server → worker → SLURM → Apptainer smoke.

## Security validation

Before release, retain automated coverage for these boundaries:

- web and maintenance containers do not receive `/var/run/docker.sock`;
- only the gateway publishes the public port and its result mount is read-only;
- task IDs and artifact paths reject traversal and symlink escape;
- logged-out protected pages and admin APIs reject access;
- cookie-only writes, banned users, and unauthorized task access fail closed;
- admins cannot self-lockout the deployment;
- multi-file task snapshots do not cross task boundaries;
- deleting one task does not remove another user's or same-user task data;
- optional archives contain only manifest-approved artifacts;
- runner output cannot turn an internal failure into a finished task.

Docker socket access gives the worker daemon-level authority even when its
process UID is non-root. Keep the worker trusted, never expose the socket over a
network, and consider a restricted socket proxy for less-trusted environments.
Redis is authenticated with `REDIS_PASSWORD` (generated by `restart setup` and
embedded in the Celery URIs); the SLURM override additionally publishes
`127.0.0.1:6380` for the host-networked worker only.

## REvoDesign integration

The desktop/plugin client should authenticate through the gateway and consume
the task-type and manifest APIs rather than assuming GREMLIN-only forms or a
ZIP-first result. Individual artifacts and their metadata are the stable
integration contract; archive generation is an optional user action.
