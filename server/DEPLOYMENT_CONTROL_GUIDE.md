# REvoCompute Deployment Control Guide

This document is the authoritative guide to `server/run/restart.sh` and the
Python control module in `server/run/revocompute_ctl/`. It explains what each
command changes, how Docker images and Apptainer SIFs move through the system,
which checks happen before downtime, and how to recover safely.

For task-type and scientific-runner adaptation, see
[OPERATIONS_AND_TASK_ADAPTER_GUIDE.md](OPERATIONS_AND_TASK_ADAPTER_GUIDE.md).

## 1. The production rule

Prepare artifacts while the healthy deployment is still running, verify them,
then perform a short prepared activation:

```text
prepare selected Docker runner image(s) and matching SIF(s)
                            |
                            v
             prepared restart --dry-run
                            |
                            v
       prepared restart --keep-gateway
```

Use `--mode=prepared` for routine production restarts when no image needs to be
rebuilt. A bare `restart` does **not** infer production behavior from the env
filename: it defaults to `--mode=dev` and rebuilds Docker images.

Never bypass a failed prepared preflight by switching to dev mode. A preflight
failure means the selected artifacts or configuration are inconsistent and
must be repaired before activation.

## 2. Entry point and architecture

`restart.sh` is intentionally only a shell entry point:

```text
server/run/restart.sh
    exec python -m revocompute_ctl
        |
        +-- __main__.py    arguments, env selection, deployment lock, dispatch
        +-- steps.py       commands, restart plan, failure cleanup, readiness
        +-- env.py         env-file parsing and subprocess environment
        +-- compose.py     Docker/Compose execution and socket discovery
        +-- build.py       runner and server image builds
        +-- registry.py    runtime registry, Docker/SIF validation and SIF builds
        +-- storage.py     runner identity and host-storage validation
        +-- maintenance.py maintenance sentinel lifecycle
        +-- sweep.py       pre-stop task and SLURM-job handling
        +-- promotion.py   staged-SIF promotion and Docker/cache pruning
        +-- stamp.py       config backup and deployment audit stamp
        +-- admin.py       admin bootstrap and password reset
        +-- ui.py          CLI help and stable operator messages
```

All subprocesses route through `compose.run_cmd()`. It never logs command
arguments because proxy URLs can contain credentials.

## 3. Authority and safety boundaries

- Run commands as the non-root deployment account. The controller refuses UID
  0 and must not be invoked through `sudo`.
- Treat restart, build, prepare, up, down, reload, setup, and password reset as
  production mutations. PR review or CI babysitting alone does not authorize
  them.
- The controller takes a non-blocking file lock keyed by the real path of the
  selected env file. A second mutating command for the same deployment exits
  before changing state.
- `--dry-run` does not take the deployment lock because it does not execute the
  restart walk or write deployment state.
- Do not run direct Compose mutations alongside the controller. The lock can
  serialize supported controller commands, but it cannot stop an operator from
  running an out-of-band `docker compose` command.
- The controller validates permissions; it does not recursively repair
  ownership or modes on application data.

## 4. Sources of deployment state

### 4.1 Environment file

`REVODESIGN_SERVER_ENV` selects the env file. Relative paths are resolved from
the current working directory; the default is `server/.env.production`.

```bash
REVODESIGN_SERVER_ENV=/absolute/path/to/.env.production \
  bash server/run/restart.sh --help
```

The env file selects paths, credentials, identities, enabled runners, image
names, and Compose interpolation values. It does **not** select restart mode.

The parser accepts shell-style `KEY=value` lines, optional `export`, comments,
and surrounding quotes. Values are literal; shell expansion is not performed.
Env-file values are exported to child processes, so the file can contain
secrets and must never be printed or committed.

Effective value precedence is:

```text
controller runtime override > env-file value > invoking process environment > default
```

If `REDIS_PASSWORD` is absent, a non-dry-run command that requires the env file
generates one, appends it to the env file, and rewrites known legacy Redis URLs.

### 4.2 External configuration

`CONFIG_DIR/task_types.yaml` is the deployed runtime registry. The controller
does not automatically copy the checkout's `server/config/` into an external
`CONFIG_DIR`; synchronization is a separate operator action.

The registry's global values select the executor and Compose override:

| `job_executor` | Required `container_runtime` | Compose override |
|---|---|---|
| `docker` | `docker` | `docker-compose.docker.yml` |
| `slurm` | `apptainer` | `docker-compose.slurm.yml` |

Each runtime family declares its Docker image, Dockerfile, Apptainer definition,
deployed SIF path, and matching runner YAML. Unsafe names and paths, incomplete
families, missing files, stale runner YAMLs, and inconsistent executor/runtime
pairs fail validation.

### 4.3 Enabled runner selection

`ENABLED_TASKRUNNERS` is a comma-separated list of runtime-family names. The
CLI can override it for one command:

```bash
--enabled-runners=mpnn,bioemu
```

An empty selection means all registered families. Unknown names fail closed.
The option selects whole runtime families, not individual task types.

## 5. Command reference

| Command | Changes deployment state? | Stops stack? | Builds/pulls? | Purpose |
|---|---:|---:|---|---|
| `setup` | Yes | No | No | Create a missing env file from `.env.example`, detect Docker GID, and ensure a Redis password |
| `prepare` | Yes | No | Builds selected runners | Prepare runner images while production remains up; optionally stage matching SIFs |
| `build` | Yes | No | Builds selected runners and server | Build local Docker artifacts without activation |
| `up` | Yes | No | Compose may resolve missing images | Start Redis, web, gateway, maintenance, and worker |
| `down` | Yes | Yes | No | Sweep in-flight work and stop the deployment |
| `reload` | Yes | No | No | Send HUP to Gunicorn for application reload |
| `restart` | Yes | Yes | Depends on mode | Run the ordered deployment walk |
| `reset-passwd USER` | Yes | No | No | Back up the auth DB, rotate one password, and invalidate its tokens |
| `help`, `-h`, `--help` | No | No | No | Print the CLI contract |

With no subcommand, the controller behaves as `restart` in dev mode. Always
spell the intended production mode explicitly.

### 5.1 Flags

| Flag | Valid use | Meaning |
|---|---|---|
| `--mode=dev` | `restart` | Build local runners and server after stopping, then activate |
| `--mode=prod` | `restart` | Pull published images after stopping, then activate |
| `--mode=prepared` | `restart` | Validate existing local artifacts before stopping; no build or pull |
| `--enabled-runners=CSV` | build/prepare/restart paths | Override enabled runtime families for this invocation |
| `--build-sif` | SLURM preparation/dev or prod restart | Build missing/stale SIFs; incompatible with prepared mode |
| `--use-proxy` | build paths | Read `REVODESIGN_BUILD_PROXY` from the selected env file |
| `--use-proxy=URL` | build paths | Supply the build proxy directly for this invocation |
| `--allowed-slurm-queue QUEUES` | SLURM paths | Override allowed SLURM partitions for this invocation |
| `--dry-run` | `restart` | Validate and report the current plan without executing it |
| `--keep-gateway` | `restart` | Serve maintenance through Nginx during application downtime |

Only the `--mode=value` spelling is accepted. `--mode prepared` is invalid.
`--use-proxy` does not request a build; it only supplies proxy arguments if the
selected command or mode builds.

There is no `--drain` flag. A restart's pre-stop sweep handles current work as
described in [Section 10](#10-in-flight-work-and-maintenance).

## 6. Restart modes

| Mode | Artifact action | Preflight before stop | Typical use |
|---|---|---|---|
| `dev` (default) | Build enabled runner images and the server image | Basic env, registry, identity, and SIF-presence checks | Development or intentional local rebuild |
| `prod` | Pull server/gateway and enabled runner images | Basic validation plus required `1000:1000` production identity | Published, pullable artifacts only |
| `prepared` | No build and no pull | Full image/SIF/config/storage/Compose/resource-policy preflight | Routine production activation |

The env filename and mode are independent. Selecting
`.env.production.v7-slurm` without `--mode=prepared` still selects dev mode.

### 6.1 Dev mode

Dev mode performs:

```text
stop -> build runner images -> build server image -> optional SIF build
     -> staged-SIF promotion -> up --no-build -> prune -> stamp
```

On SLURM, rebuilding a Docker runner without rebuilding its SIF creates an
artifact mismatch. Do not use a bare dev restart as a routine SLURM restart.
Adding `--build-sif` repairs the pairing, but dev mode performs both the Docker
build loop and stale-SIF construction after the stack stops. Even when Docker
is fully cached, large SIF conversions extend the maintenance window.

### 6.2 Prod mode

Prod mode performs:

```text
stop -> pull published images -> optional SIF build -> staged-SIF promotion
     -> up --no-build -> prune -> stamp
```

Prod mode requires `RUNNER_UID=1000` and `RUNNER_GID=1000`. It is unsuitable
for local-only tags: pulling happens after the stack stops.

### 6.3 Prepared mode

Prepared mode performs the full preflight first, then:

```text
config backup -> capture image baselines -> stop -> activate existing images
              -> promote staged SIFs -> up --no-build -> readiness
              -> prune -> stamp
```

Prepared mode is the normal production choice when artifacts already match.
It refuses `--build-sif`; SIF creation belongs in the preceding `prepare`
phase so expensive work happens while the healthy stack is running.

## 7. Prepared-mode preflight

Before stopping the current deployment, prepared mode validates:

1. the env file and required `SERVER_DIR`/`ADMIN_USERS` values;
2. the registry schema, executor/runtime pairing, build definitions, runner
   YAMLs, enabled-family names, and safe paths;
3. local server, Nginx, Redis, and enabled runner Docker images;
4. every enabled deployed or staged SIF;
5. the SIF-to-Docker image identity and recorded SIF SHA-256;
6. `AUTH_DIR` separation from `SERVER_DIR` and runner access;
7. Docker socket GID and runner UID/GID resolution;
8. result-storage access;
9. rendered Compose interpolation via `docker compose config --quiet`; and
10. resolved task resource policies inside a throwaway prepared worker.

Any failure aborts before `down`. Fix the stated invariant; do not retry with a
less safe mode.

`--dry-run` omits storage creation and the throwaway worker audit because both
would execute writes or containers. It still performs the read-only prepared
artifact and Compose checks and reports the current restart walk, image
baseline comparison, and stale SIF set. It does not simulate a future build.

## 8. Docker image lifecycle

Runner images are built directly to each configured final tag, normally
`:latest`. There are no controller-managed candidate, next, or rollback Docker
tags. Before restart, the controller records the current image IDs; the deploy
stamp compares those baselines with the final IDs.

`prepare` builds selected runtime families only. `build` builds selected
families and then web/worker. Neither command stops or activates the stack.
Docker decides layer reuse; selecting a family asks Docker to build it, not to
perform source-level change detection.

Build proxy values are passed as predefined build arguments, redacted from
controller output, and cleared by final runtime stages. Never hard-code proxy
credentials in Dockerfiles.

### 8.1 Post-restart pruning and cache behavior

Every successful restart currently runs:

```bash
docker image prune -f
docker buildx prune -f
```

This removes retired dangling images and unused BuildKit records. Shared or
referenced layers may remain cached while intermediate or replaced-image cache
records disappear. A later build can therefore show some families entirely
cached and rebuild other, unchanged families from their first `RUN` layer.
Once an early layer misses, all dependent layers rebuild; package-manager
`--no-cache` options make the rebuild slower but do not cause the original
Docker cache miss.

After that uncached build completes, the new cache records and final images are
current again, so an immediate second dev restart will commonly report every
Docker layer as cached. That only describes cache reuse: the controller still
asked Docker to build every enabled family.

Treat cache pruning as part of the current controller behavior when estimating
build time. Manual cache cleanup is destructive to build performance and should
be used only for measured disk pressure.

## 9. SLURM and SIF lifecycle

For SLURM, the Docker image is the build source and the SIF is the compute-node
runtime. They are one artifact pair and must match.

### 9.1 Staleness and identity

For each family, `images/digest/image-sif.json` records:

- the exact source Docker image ID; and
- the SHA-256 of the built SIF.

The manifest is authoritative. Unrecorded SIFs are stale and must be rebuilt;
file timestamps never prove artifact identity. Prepared activation rejects a
deployed or staged SIF that does not match the current Docker image.

### 9.2 Atomic staging

`prepare --build-sif` follows this path for each selected stale family:

```text
current Docker tag
      |
      v
<family>.sif.next.build  -- successful Apptainer build -->  <family>.sif.next
      |                                                        |
      +-- failure: delete partial file                          |
                                                               v
                                  prepared restart after stop: os.replace()
                                                               |
                                                               v
                                                    deployed <family>.sif
```

The controller records the Docker image ID before the Apptainer build and
checks it again afterward. If the tag changed concurrently, it discards the
staged result rather than recording or promoting a mismatched SIF.

An existing valid `.next` is reused. Missing or stale families are rebuilt;
unchanged families are skipped. Promotion happens only during restart after
the application services stop.

## 10. In-flight work and maintenance

Before stopping a SLURM deployment, the controller asks the running worker for
this deployment's numeric SLURM job IDs and calls `scancel`. It then:

- returns workflow tasks to `queued`, clears their job/container IDs, and marks
  running workflow steps interrupted so they can resume; and
- records ordinary queued/running tasks as failed with “Cancelled by server
  restart.”

If the worker is already unavailable, the sweep prints a warning and continues;
the operator must inspect task and SLURM state manually.

With `--keep-gateway`, the controller:

1. creates `${SERVER_DIR}/.maintenance`, pausing submissions;
2. recreates and retains Nginx while stopping Redis, web, maintenance, and
   worker;
3. starts the complete stack;
4. restarts Nginx after web recreation so its Docker DNS is fresh; and
5. removes the maintenance sentinel only after successful finalization.

Prepared mode additionally waits up to 60 seconds for Redis, web, gateway,
maintenance, and worker to report running. If activation or readiness fails,
the sentinel remains until a known-good stack is restored.

## 11. Standard workflows

Set the deployment env once in the shell examples below:

```bash
export REVODESIGN_SERVER_ENV=/repo/REvoDesign/server/.env.production.v7-slurm
```

### 11.1 Routine restart; no runner or server image change

```bash
bash server/run/restart.sh restart --mode=prepared --keep-gateway --dry-run
bash server/run/restart.sh restart --mode=prepared --keep-gateway
```

Do not add `--use-proxy`; prepared mode does not build.

### 11.2 Rebuild selected changed runners

Build Docker images and stage matching SIFs while the existing stack stays up:

```bash
bash server/run/restart.sh prepare \
  --enabled-runners=mpnn,bioemu \
  --build-sif \
  --use-proxy
```

Then validate and activate:

```bash
bash server/run/restart.sh restart --mode=prepared --keep-gateway --dry-run
bash server/run/restart.sh restart --mode=prepared --keep-gateway
```

Name the changed runtime families explicitly. The controller does not inspect
Git changes to discover them.

### 11.3 Build all local Docker artifacts without activation

```bash
bash server/run/restart.sh build --use-proxy
```

This builds all enabled runners plus web/worker and leaves the current stack
running. On SLURM, follow any changed runner image with a matching SIF build
before prepared activation.

### 11.4 Activate published images

```bash
bash server/run/restart.sh restart --mode=prod --keep-gateway
```

Use this only when every configured tag is published and the deployment uses
the required `1000:1000` identity. Prefer prepared mode for local SLURM images.

### 11.5 Config-only activation

Synchronize and validate the external `CONFIG_DIR` first, preserving its
machine-specific executor/runtime settings. Then use the routine prepared
workflow. The restart creates a timestamped config backup, but it does not copy
the checkout configuration for you.

### 11.6 Direct lifecycle commands

```bash
bash server/run/restart.sh up
bash server/run/restart.sh reload
bash server/run/restart.sh down
bash server/run/restart.sh reset-passwd USERNAME
```

`reload` affects Gunicorn only; it does not reload Celery worker code or rebuild
images. `reset-passwd` writes the new plaintext credential to a mode-0600 file
under `AUTH_DIR` and writes a mode-0600 database backup under
`SERVER_DIR/backups/`.

## 12. Backups and deploy stamp

Before a production-like restart, the controller copies `CONFIG_DIR` to:

```text
${SERVER_DIR}/backups/config-<timestamp>
```

The copy is performed in a throwaway server-image container as the configured
runner identity. A successful prepared/prod restart—and dev restart when
`CONFIG_DIR` is explicitly configured—writes:

```text
${CONFIG_DIR}/.deploy-stamp
```

The JSON stamp contains:

- checkout commit and dirty-worktree flag;
- restart mode and timestamp;
- duration of each completed step;
- changed and unchanged image families;
- current and baseline image IDs;
- SHA-256 values for SIFs changed by this deployment;
- registry SHA-256; and
- config-backup path.

The stamp is the deployment audit record, not a health check. Verify runtime
state separately.

## 13. Failure behavior and recovery

| Symptom | Meaning | Safe response |
|---|---|---|
| `Another server control command is already running` | The per-env mutation lock is held | Let the active command finish; do not start direct Compose operations |
| `Prepared SIF does not match Docker image` | Docker tag and deployed/staged SIF are different artifacts | Run `prepare --enabled-runners=<family> --build-sif`, then retry prepared dry-run |
| `Prepared Docker image is missing` | Required local image is absent | Build/prepare it while the live stack remains up |
| `Missing SIF image` | Enabled SLURM family has no deployed or staged SIF | Prepare that family with `--build-sif` |
| Docker image changed during SIF build | A tag was retagged concurrently or out of band | Stop the competing mutation and rebuild the SIF |
| Compose container-name conflict | Another Compose/controller operation overlapped or left an orphan | Stop concurrent operations, inspect exact containers, then retry one controller command |
| Gateway returns 502 after web recreation | Nginx retained stale Docker DNS or web is down | Inspect web state; restart gateway only after web is running |
| Pre-stop sweep cannot reach worker | Tasks may not have been marked or cancelled | Inspect the task DB/API and `squeue` before further changes |
| Prepared readiness fails | One or more required services did not remain running | Inspect `docker compose ps` and logs; repair before retrying |
| Unexpected full Docker rebuild | Dev mode was selected or BuildKit records were pruned | Check explicit mode and the pruning behavior in Section 8.1 |
| Permission validation fails | Host paths are not accessible to the runner identity | Provision the exact path/ACL outside the controller; do not run as root |

Do not delete or overwrite broad paths during recovery. Resolve exact container,
image, SIF, or staging targets first.

## 14. Post-activation verification

At minimum, verify:

1. the command completed without a traceback;
2. all five Compose services are running;
3. `GET /compute/health` returns HTTP 200 through the canonical edge;
4. Nginx resolves the current web container and authenticated routes behave as
   expected;
5. `${CONFIG_DIR}/.deploy-stamp` records the intended commit, mode, registry,
   backup, and changed families;
6. maintenance mode is absent and submissions are accepted; and
7. when behavior or a runner changed, one real API → worker → SLURM → Apptainer
   task completes and its result manifest/logs are readable.

Do not call a deployment successful based only on container creation or only on
the deploy stamp.

## 15. Tests and maintenance

Focused controller coverage:

```bash
pytest -q server/tests/test_restart_ctl.py
pytest -q server/tests/test_process_isolation.py
```

The tests cover argument behavior, lock exclusion, step cleanup, environment
handling, SIF staging and digest checks, maintenance, pre-stop sweep, gateway
refresh, and deploy stamps. Static tests also pin several operator-facing
messages; update tests if those messages intentionally change.

When changing the controller:

- keep `restart.sh` a thin entry point;
- preserve one subprocess path so secrets are not accidentally logged;
- add the smallest regression check for any new branch or failure invariant;
- update this guide, the relevant server documentation, and `CHANGELOG.md`; and
- validate the prepared dry-run before any live activation.
