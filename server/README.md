# REvoCompute Server

For the complete production build → versioned SIF → prepared SLURM activation
runbook and the new-task/runtime-family adapter contract, see
[REvoCompute Operations and Task Adapter Guide](OPERATIONS_AND_TASK_ADAPTER_GUIDE.md).

The server is a Docker-deployed Flask + Celery + Docker-runner web service for
protein bioinformatics computation — currently GREMLIN co-evolution analysis,
with a generic multi-task architecture that supports adding AlphaFold, ESM,
DiffDock, and other compute tasks without changing server code.

## Multi-Task Architecture

The server uses a YAML-based task type registry. Adding a new compute task
type selects a runtime family; several compatible task types can share one
image and SIF without duplicating dependency stacks:

| File | Owner | Contains |
|------|-------|----------|
| `config/task_types.yaml` | Developer/operator | Global executor/runtime, per-family images/SIFs, plus task I/O and constrained params |
| `config/runners/<runtime-family>.yaml` | Operator (per-machine) | One machine-specific mount/resource config shared by the family |
| `docker/runners/<runtime-family>/Dockerfile` | Developer | One dependency image for the family |
| Runtime family `definition` | Developer | Exact Apptainer definition path used for its SIF |

The server loads the registry at startup via `CONFIG_DIR`. `gremlin` is always
enabled; additional runners are gated by `ENABLED_TASKRUNNERS` in `.env`.

Each runner container follows a standard contract:
- Sees one immutable task snapshot at `/mnt/revocompute/<username>/inputs/`
  and task-owned results at `/mnt/revocompute/<username>/outputs/`. Concurrent
  tasks have isolated host snapshots even though their virtual paths match.
- Emits `REVODESIGN_STAGE:<marker>` on stdout for progress tracking
- Receives params via `TASK_PARAMS`, the complete input manifest via
  `TASK_INPUTS`, and the primary input/output via CLI args (`-i`, `-o`, `-r`)
- Runs as non-root `--user` (identity from `RUNNER_UID`/`RUNNER_GID` in `.env`)

The create-task page dynamically builds its form from `GET /compute/api/types/<name>`
— file input, params form, and sequence editor visibility all come from the
registry. Task type badges appear on the dashboard.

## Docker Deployment

This guide covers both local-image development (`--mode=dev`) and
published-image production (`--mode=prod`). Native/manual production deployment
is intentionally excluded.

## Overview

The server stack contains:

- `web`: Flask + Gunicorn API/UI service
- `maintenance`: APScheduler process for registration digests, result cleanup,
  database backups, and log rotation
- `worker`: Celery worker for background jobs
- `redis`: Celery broker/backend
- `runner` image: GREMLIN/PSSM execution container launched by `worker`

**Alternative executor (SLURM + Apptainer):** When the deployed
`task_types.yaml` sets `job_executor: slurm` and
`container_runtime: apptainer`, the worker dispatches every task via `srun` +
Apptainer instead of Docker. See [SLURM + Apptainer](#slurm--apptainer-deployment).

Scientific Python dependencies used by GREMLIN scripts belong to the runner's
`docker/runners/pssm_gremlin/GREMLIN.yml`; they are not installed into the web and worker package.

Periodic jobs follow this package boundary:

```text
revocompute/maintenance/
├── model.py                 # PeriodicTask interface
├── manager.py               # imports task objects and calls register()
└── tasks/
    ├── admin_digest.py      # self-configuring admin_digest_task
    ├── database_backup.py   # consistent task/user SQLite snapshots
    ├── log_rotation.py      # ZIP rotation and total-size pruning
    └── result_cleanup.py    # self-configuring result_cleanup_task
```

Each task object owns its environment configuration, enabled state, callable,
maximum instances, trigger, and `scheduler.add_job` arguments.

Only `worker` receives `/var/run/docker.sock`. The web container submits tasks
through Redis and has no Docker socket or user-database overlap with the worker.

## 0. Prerequisites

Install the following on the deployment host:

- Docker Engine 24+ with Compose plugin
- NCBI BLAST+ (`makeblastdb`)
- Enough disk space for UniRef databases, logs, and uncompressed task results

Ubuntu example:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin ncbi-blast+ aria2
makeblastdb -version
```

## 1. Prepare Sequence Databases

You need UniRef90 (for PSI-BLAST) and UniRef30 (for HH-suite workflow).

### 1.1 UniRef90 download and extraction

```bash
DOWNLOAD_DIR=/srv/revodesign/databases
ROOT_DIR="${DOWNLOAD_DIR}/uniref90"
SOURCE_URL="https://ftp.ebi.ac.uk/pub/databases/uniprot/uniref/uniref90/uniref90.fasta.gz"
BASENAME=$(basename "${SOURCE_URL}")

mkdir -p "${ROOT_DIR}"
aria2c "${SOURCE_URL}" --dir="${ROOT_DIR}"
gunzip "${ROOT_DIR}/${BASENAME}"
```

### 1.2 Build BLAST database for UniRef90

```bash
cd "${ROOT_DIR}"
makeblastdb -in uniref90.fasta -dbtype prot -parse_seqids -out uniref90
```

Use the BLAST prefix path (`.../uniref90`) as `DB_UNIREF90`.

### 1.3 UniRef30 download and extraction

```bash
DOWNLOAD_DIR=/srv/revodesign/databases
ROOT_DIR="${DOWNLOAD_DIR}/uniref30"
SOURCE_URL="https://wwwuser.gwdg.de/~compbiol/uniclust/2023_02/UniRef30_2023_02_hhsuite.tar.gz"
BASENAME=$(basename "${SOURCE_URL}")

mkdir -p "${ROOT_DIR}"
aria2c "${SOURCE_URL}" --dir="${ROOT_DIR}"
tar -xvf "${ROOT_DIR}/${BASENAME}" -C "${ROOT_DIR}"
rm -f "${ROOT_DIR}/${BASENAME}"
```

Set `DB_UNIREF30` to the UniRef30 prefix path.

## 2. Create a Dedicated Server User (Recommended)

Use a dedicated non-root account for operations.

Ubuntu example:

```bash
sudo adduser --system --group --no-create-home --shell /usr/sbin/nologin revodesign
sudo usermod -aG docker revodesign

sudo mkdir -p /srv/revodesign/server
sudo mkdir -p /srv/revodesign/auth
sudo mkdir -p /srv/revodesign/logs

# grant full and recurse access to this user
sudo chown -R revodesign:revodesign /srv/revodesign
```

Notes:

- Do not run the GREMLIN runner as root.
- Configure non-root runner identity via `RUNNER_UID`/`RUNNER_GID` or `RUNNER_USERNAME`/`RUNNER_GROUP`.
  
User IDs can be found with `id <username>`. eg:

```bash
id revodesign
> uid=129(revodesign) gid=137(revodesign) groups=137(revodesign),998(docker)
```

## 3. Configure Environment Files

Create production env file:

```bash
cp server/.env.example server/.env.production
chmod 600 server/.env.production
```

Production env files contain secrets and must not be group/world-readable.
They are ignored by Git; keep them on the deployment host and never bake them
into an image.

### Env-file isolation

All restart helpers support `REVODESIGN_SERVER_ENV`:

```bash
REVODESIGN_SERVER_ENV=server/.env.local bash server/run/restart.sh restart --mode=dev
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh restart --mode=prod
```

When `REVODESIGN_SERVER_ENV` is unset, the helper uses
`server/.env.production` and fails clearly when that file is absent.

### Required/important variables

| Variable | Purpose |
| --- | --- |
| `SERVER_IMAGE`, `RUNNER_IMAGE` | Image names built locally in dev mode or pulled in prod mode. Production must use full published Docker Hub references. |
| `SERVER_DIR` | Required host root shared by web and worker for uploads, task SQLite, and result folders. Never store the user database here. |
| `RUNNER_HOST_ROOT` | Host root allowed for Docker runner bind mounts (default: parent of `SERVER_DIR`). |
| `LOG_DIR` | Host directory for Gunicorn, Celery, and `maintenance.log`. |
| `CONFIG_DIR` | Path to the config directory containing `task_types.yaml` and `runners/`. Defaults to the source checkout; set to `/app/server/config` in Docker deployments so maintainers can ship config changes with the image. |
| `ENABLED_TASKRUNNERS` | Comma-separated list of additional task types to enable (e.g., `alphafold,esm`). `gremlin` is always enabled regardless of this setting. |
| `ADMIN_USERS` | Required comma-separated bootstrap-administrator usernames. On an empty user database, the restart script creates each account and prints a distinct generated password; afterward, database roles control authorization. |
| `AUTH_TOKEN_MAX_AGE` | Token lifetime in seconds (default: 604800 = 7 days). |
| `AUTH_DIR` | Host-side directory containing `users.sqlite3`; Compose mounts it only into web and maintenance. It must be outside `SERVER_DIR`. |
| `USER_DB_PATH` | Container-side path used by web and maintenance to open the user DB. Keep the default `/var/lib/revodesign-auth/users.sqlite3` unless the Compose mount target also changes. |
| `ENABLE_REGISTER` | Set to `true` to enable self-registration; configure either SMTP or Resend email delivery. |
| `SMTP_*`, `RESEND_*` | Email delivery settings. Resend takes priority when both backends are configured. |
| `SERVER_BASE_URL` | Public base URL for email links and HTTPS-sensitive auth-cookie settings. |
| `RUNNER_UID`, `RUNNER_GID` | Runner UID/GID. Dev may match the host; published production images require `1000:1000`. |
| `DOCKER_GID` | Auto-detected by `restart.sh` at runtime for Docker Compose interpolation. Override only as a shell variable when detection is wrong. |
| `NPROC` | CPU threads passed to runner (overridable per task type in `config/runners/<name>.yaml`). |
| `MAXMEM` | Memory cap (GB) passed to hhblits (`-maxmem`) inside runner script (overridable per task type in runner YAML). |
| `WORKER_CONCURRENCY` | Celery worker concurrency. |
| `GUNICORN_WORKERS` | Gunicorn worker count. |
| `GUNICORN_TIMEOUT` | Gunicorn request timeout in seconds (default: `120`). Result transfers are handled by Nginx and do not require a long timeout. |
| `RESULT_DOWNLOAD_MODE` | Result delivery backend: `nginx` in Compose production, or `flask` for direct local Flask development. |
| `PORT` | Public HTTP port. |
| `RESULT_RETENTION_DAYS` | Optional positive number of days to retain terminal-task result directories and archives. Fractions are allowed (`0.1` = 2.4 hours). Leave unset to disable cleanup; task audit rows remain. |
| `BACKUP_DB_CRON` | Five-field crontab schedule for database snapshots. Leave unset to disable; recommended daily schedule: `0 0 * * *`. |
| `BACKUP_DB_PATH` | Snapshot directory inside the maintenance container. `/var/lib/revodesign-auth/backups` persists at `${AUTH_DIR}/backups` on the host. |
| `MAX_DB_BACKUP` | Maximum complete snapshot sets to retain. Leave unset for unlimited history; recommended value: `30`. |
| `ROTATE_LOG_MAX_LINENO` | Optional line-count rotation threshold; unset disables this trigger. |
| `ROTATE_LOG_PERIOD` | Optional quoted five-field crontab expression for scheduled rotation (for example, `"0 0 * * *"` for daily at midnight); unset disables this trigger. |
| `MAX_LOG_SIZE` | Optional total cap for active logs plus ZIP archives; accepts bytes or K/M/G/T suffixes and removes oldest ZIPs first. A newly created archive is retained even when it temporarily exceeds the cap. |
| `ADMIN_NOTIFY_EMAIL` | Comma-separated admin email addresses for new-user registration digests (default: empty = no notification). |
| `ADMIN_NEW_USER_INFORM` | Interval in minutes between new-user digest emails (default: `0` = disabled). |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated allowed email domains for self-registration (empty = all allowed). Also normalises plus-aliased addresses (`user+tag@domain` → `user@domain`). |
| `TZ` | Timezone for logs. |
| `CLIENT_IP_HEADERS` | Comma-separated list of HTTP headers to try for the real client IP, in priority order (default: `X-Forwarded-For, X-Real-IP`). See CDN reference below. |
| `CLIENT_COUNTRY_HEADER` | Single HTTP header carrying the client country code, e.g. `CF-IPCountry` for Cloudflare (default: empty = disabled). |

### Authentication storage: host path versus container path

`AUTH_DIR` and `USER_DB_PATH` describe the same storage from two different
points of view:

```text
Docker host                           web / maintenance containers
/srv/revodesign/auth/users.sqlite3 -> /var/lib/revodesign-auth/users.sqlite3
^^^^^^^^^^^^^^^^^^^^^^^                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AUTH_DIR                               USER_DB_PATH
```

With the example configuration:

```dotenv
SERVER_DIR=/srv/revodesign/server
AUTH_DIR=/srv/revodesign/auth
USER_DB_PATH=/var/lib/revodesign-auth/users.sqlite3
```

Compose applies these boundaries:

| Process | Sees `SERVER_DIR` | Sees `AUTH_DIR` | Can open the user DB |
| --- | --- | --- | --- |
| Web | Yes | Yes, mounted at `/var/lib/revodesign-auth` | Yes |
| Maintenance | Yes | Yes, mounted at `/var/lib/revodesign-auth` | Yes, for email and backup tasks |
| Celery worker | Yes | No | No |

`AUTH_DIR` is therefore not an application data path passed to Python. It is a
Docker-host path used to create a private volume mount for web and maintenance.
It must be a sibling of, rather than a child of, `SERVER_DIR`: mounting all of
`SERVER_DIR` into the worker would otherwise expose any nested auth directory
through that parent mount.

On a new installation, create `AUTH_DIR` with write access for
`RUNNER_UID:RUNNER_GID`; web creates `users.sqlite3` there on first start. Keep
`USER_DB_PATH` at its default unless you deliberately change the target side of
the Compose volume mount.

When database backups are enabled, each successful run creates one complete
snapshot set:

```text
${AUTH_DIR}/backups/20260101T000000.000000Z/
├── tasks.sqlite3
└── users.sqlite3
```

Copies are made through SQLite's online backup API and checked before the
snapshot directory is published. `MAX_DB_BACKUP` counts these complete
timestamped directories, not individual database files.

### CDN IP header reference

| Provider | IP header | Country header |
|---|---|---|
| Cloudflare | `CF-Connecting-IP` | `CF-IPCountry` |
| Akamai | `True-Client-IP` | — |
| AWS CloudFront | `CloudFront-Viewer-Address` | `CloudFront-Viewer-Country` |
| Fastly | `Fastly-Client-IP` | — |
| Azure Front Door | `X-Azure-ClientIP` | — |
| Fly.io | `Fly-Client-IP` | — |
| Netlify | `X-Nf-Client-Connection-IP` | — |
| nginx / Traefik / Caddy / GCP | `X-Forwarded-For` | — |

Put the CDN-specific header first, then fall back to `X-Forwarded-For`. Example for Cloudflare:

```bash
CLIENT_IP_HEADERS="CF-Connecting-IP, X-Forwarded-For, X-Real-IP"
CLIENT_COUNTRY_HEADER="CF-IPCountry"
```

## 4. Runner Configuration

Database paths and resource limits no longer live in `.env`. Each runtime
family has one runner YAML at `config/runners/<runtime-family>.yaml`:

```yaml
# config/runners/gremlin.yaml — deployment-specific (machine-local)
mounts:
  - host_path: "/srv/revodesign/databases/uniref30/UniRef30_2023_02"
    container_path: "/opt/db/uniref30"
    mode: "ro"
  - host_path: "/srv/revodesign/databases/uniref90/uniref90"
    container_path: "/opt/db/uniref90"
    mode: "ro"
env:
  GREMLIN_CALC_CPU_NUM: "16"
max_runtime_seconds: 7200
defaults:
  iter: 100
```

Edit this file when deploying to a new node — not `.env`. The task type
definition at `config/task_types.yaml` (checked into git) declares the
portable runtime-to-task mapping, accepted input set, stage markers, result
patterns, and typed parameter constraints. A deployed config from the older
per-task layout must be migrated to family filenames before startup; missing
family YAMLs fail closed.

`CONFIG_DIR` must point to the directory containing both files. In Docker
deployments, set it to `/app/server/config` to use the baked-in source copy.

Execution selection is global in `task_types.yaml`; it is not repeated in
runner YAMLs:

```yaml
# config/task_types.yaml — deployed SLURM configuration
job_executor: slurm
container_runtime: apptainer
runtime_families:
  gremlin:
    docker_image: revodesign-revocompute-runner
    # dockerfile, definition, entrypoint ...
    slurm_image: /mnt/data/srv/revodesign/server-slurm/images/gremlin_v1.sif
```

With `job_executor: docker`, `container_runtime` must be `docker` and all
`slurm_image` values are inert metadata. With `job_executor: slurm`,
`container_runtime` must be `apptainer` and every runtime family must declare
an absolute `slurm_image`. Startup fails before stopping the current deployment
when required config or existing SIFs are missing.

Per-task-type SLURM resource directives (partition, cpus-per-task, mem, time,
gres, etc.) are configured via the admin UI at `/compute/configuration` and
stored in `manage.sqlite` — not in the YAML.  The web process can seed them
on first launch via `sqlite3`.

## 5. Authentication

The server uses Bearer-token authentication (replaces the old HTTP Basic Auth + `users.txt` model).

### How auth works

- **Browser access**: Logging in sets an `HttpOnly` cookie so page navigations
  (dashboard, profile, create task) are authenticated without manual header
  management.  Already-authenticated visitors to `/login` or `/register` are
  redirected to the dashboard.
- **API access**: Clients send `Authorization: Bearer <token>` for full access,
  or `X-API-Key: <key>` for long-lived programmatic access with restricted
  privileges (tasks only — no profile changes or admin actions).
- **Logout**: `POST /compute/api/auth/logout` clears the server-side
  cookie.  The profile page includes a logout button.
- **Roles**: Three account types — `admin` (full access), `user` (registered
  user with API access), `guest` (publicly shared account, web-login only).
  Guest accounts cannot use Bearer tokens or API keys and cannot change
  passwords or manage API credentials.
- **CAPTCHA**: Self-registration requires solving a math challenge to prevent
  automated signups.  The CAPTCHA token expires after 5 minutes and is
  regenerated after each failed attempt.

### Gunicorn `--preload`

Gunicorn workers are started with `--preload` so the auth secret key is
generated once in the arbiter before forking.  Without this, each worker
independently generates its own signing key, making tokens from one worker
fail validation on another.

The key is intentionally ephemeral. Restarting the web service logs users out
and invalidates outstanding verification and password-reset links.

### First run

If the user database is empty, every username in the required `ADMIN_USERS`
list is created automatically:

- Passwords: generated separately and printed once by
  `restart.sh`. Change each after first login.

Bootstrap passwords must not be stored in the env file. They are transient
first-boot values supplied by the restart script only.

`reset-passwd` rotates an existing account from the deployment host. It creates
a timestamped auth-database backup under `${SERVER_DIR}/backups`, invalidates
that user's existing bearer tokens, and writes the new username/password pair
to a mode-0600 file under `AUTH_DIR`. The password itself is never printed.

Set `ENABLE_REGISTER=true` and configure either SMTP or Resend to allow
self-registration. Registration requires full name, affiliation, academic
position, and PI name. These fields appear on the user's profile page and in
the admin user-control system. Users receive a verification email and must be
verified before use. Without a working email backend, use the admin API to
create accounts.

### API authentication

```bash
# Login to get a token
curl -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"..."}' \
  "http://<server-ip>:<port>/compute/api/auth/login"

# Use the token for subsequent requests
curl -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/compute/api/auth/me"

# Logout (clears the auth cookie)
curl -X POST -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/compute/api/auth/logout"
```

### Admin user management

```bash
# Admin creates a new user (requires admin token)
curl -X POST -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","email":"user@example.com","password":"...","role":"user"}' \
  "http://<server-ip>:<port>/compute/api/auth/admin/users"
```

`role` may be `admin`, `user`, or `guest` and is the sole authorization
authority. Server setup creates the current user schema directly and does not
alter older database layouts.

Admins cannot ban or delete their own account.  Direct self-ban/self-delete
requests return HTTP 400, and batch Disable/Delete skips the acting admin while
still applying the requested action to other selected users.

The dashboard header also links administrators to `/compute/logs`. That
standalone page loads only the selected active Gunicorn access, Gunicorn error,
Celery worker, or maintenance log and streams it incrementally. Its lazy
file tree lists rotated ZIP archives under those same four logs and permits
individual downloads; arbitrary filesystem paths are not exposed.

### API keys (programmatic access)

Long-lived API keys are available for scripted/programmatic access. Generate and revoke
them from the Profile page (`/compute/profile`), or via the API:

```bash
# Generate (returns plaintext key once — store it securely)
curl -X POST -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/compute/api/auth/me/api-key"

# Check status
curl -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/compute/api/auth/me/api-key"

# Revoke
curl -X DELETE -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/compute/api/auth/me/api-key"
```

Use the key via the `X-API-Key` header:

```bash
curl -H "X-API-Key: revodesign_<hex>" \
  "http://<server-ip>:<port>/compute/api/auth/me"
```

API keys never expire but have **restricted privileges**: they can submit tasks and
read results, but **cannot** change passwords, manage API keys, or perform admin
actions. Use a Bearer token (web login) for those operations.  **Guest accounts
cannot use API keys at all** — they are web-dashboard-only accounts.

Rate limits: 5 login attempts/minute per IP, 3 registrations/hour per IP.  The
login endpoint returns HTTP 429 with `retry_after_seconds`; the login page uses
that value to disable the submit button and count down until retry.

## 6. Build and Run

### Recommended helper script

No sudo required.

```bash
# initialize the env file and print detected Docker socket group
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh setup

# development: down + local build using host UID/GID + up
REVODESIGN_SERVER_ENV=server/.env.local bash server/run/restart.sh restart --mode=dev

# production: down + pull configured Docker Hub images + up without building
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh restart --mode=prod

# prepared production: preflight local images/SIFs/config, then down + up only
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh restart --mode=prepared

# subcommands
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh build
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh up
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh down
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh reload
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh reset-passwd <username>
```

`restart` defaults to `--mode=dev` for backward compatibility. Only the
`--mode=value` spelling is accepted, and mode is independent from the selected
environment file:

- `REVODESIGN_SERVER_ENV` selects paths, secrets, and resource settings.
- `--mode=dev` builds the runner and server images locally, then starts with
  `--no-build`. This is the authoritative development workflow and preserves
  host UID/GID ownership for writable bind mounts.
- `--mode=prod` pulls the configured `SERVER_IMAGE` and `RUNNER_IMAGE`, then
  starts with `--no-build`. Published images use the fixed `1000:1000` identity,
  so production mode rejects any other `RUNNER_UID` or `RUNNER_GID`.
- `--mode=prepared` activates locally prepared production artifacts. Before it
  stops anything, it verifies all server/runtime Docker images, every required
  SIF, the external registry and runner files, auth-storage separation, and the
  rendered Compose model. It performs no build or pull, starts with
  `--no-build`, and waits for all five Compose services to report running.
- `job_executor: slurm` in the selected registry automatically merges
  `docker-compose.slurm.yml`, bind-mounts SLURM client tools + MUNGE, validates
  SIF images, and exports `SLURM_ENABLED=true` to the services.
- `--build-sif` auto-builds missing `.sif` images from `.def` files before
  starting services (requires Apptainer on PATH). It is accepted only when the
  registry selects SLURM.

Provision production bind-mounted directories as writable by UID/GID
`1000:1000`. This identity contract provides non-root execution and compatible
file ownership; it is not a container-escape boundary. The worker's Docker
socket access still grants effective Docker-daemon/host-level authority.

Create a writable `AUTH_DIR` before the first start. The web process creates
`${AUTH_DIR}/users.sqlite3` with the current schema. Existing databases must
already match that schema; server setup does not migrate them.

### Equivalent Docker Compose commands

These commands are equivalent only after `users.sqlite3` contains an account.
On a fresh installation, use the helper script's `up` or `restart` command so
it can generate and pass transient bootstrap credentials. A direct Compose
startup with an empty user database is rejected.

Development mode:

```bash
docker compose -f server/docker-compose.yml --env-file server/.env.local down
docker compose -f server/docker-compose.yml --env-file server/.env.local --profile runner build runner
docker compose -f server/docker-compose.yml --env-file server/.env.local build web worker
docker compose -f server/docker-compose.yml --env-file server/.env.local up --no-build -d redis web gateway maintenance worker
```

Production mode:

```bash
docker compose -f server/docker-compose.yml --env-file server/.env.production down
docker compose -f server/docker-compose.yml --env-file server/.env.production --profile runner pull web gateway runner
docker compose -f server/docker-compose.yml --env-file server/.env.production up --no-build -d redis web gateway maintenance worker
```

### Zero-downtime Gunicorn reload

```bash
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart.sh reload
```

## 7. Usage

### Create task page

- `http://<server-ip>:<port>/compute/create_task`
- Select a task type from the dropdown — the form adapts dynamically (file
  extension, hints, params inputs, sequence editor visibility).
- Upload input files via the **Choose File** button or by **dragging and dropping** a file anywhere on the card.
- For ``.fasta`` task types, an optional sequence editor lets you paste raw
  protein sequences as text instead of uploading a file.

### Dashboard

- `http://<server-ip>:<port>/compute/dashboard`

### Upload via curl (with token auth)

```bash
# Obtain a token first (see Authentication section above)
TOKEN="<your-token>"

curl -H "Authorization: Bearer ${TOKEN}" \
  -X POST \
  -F "file=@/path/to/input.fasta" \
  "http://<server-ip>:<port>/compute/api/post"
```

### Batch upload via curl

```bash
for f in *.fasta; do
  curl -H "Authorization: Bearer ${TOKEN}" -X POST -F "file=@${f}" \
    "http://<server-ip>:<port>/compute/api/post"
done
```

### Delete one task (single-task API)

```bash
TASK_MD5="<task-md5>"
curl -H "Authorization: Bearer ${TOKEN}" -X DELETE \
  "http://<server-ip>:<port>/compute/api/delete/${TASK_MD5}"
```

### Delete multiple tasks (batch API)

```bash
curl -H "Authorization: Bearer ${TOKEN}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"md5sums":["<task-md5-a>","<task-md5-b>"]}' \
  "http://<server-ip>:<port>/compute/api/delete"
```

## 8. Task States

Current server states:

- `pending`
- `queued`
- `running`
- `finished`
- `failed`
- `cancelled`
- `deleting:finished`
- `deleting:cancel`
- `cleaned:finished`
- `cleaned:cancel`
- `deleted:finshed`
- `deleted:cancel`

Deletion is tracked in sqlite (soft-delete). Task records remain for audit/debug.
The `deleting:*` states are short-lived maintenance claims that prevent a
concurrent resubmission from reusing artifacts while cleanup is in progress.
The final `cleaned:*` states identify automatic retention cleanup; `deleted:*`
states remain reserved for explicit user deletion.
The `deleted:finshed` spelling is intentionally preserved for runtime compatibility.

`finished` means `manifest.json` has been atomically published in the
uncompressed result tree. Individual manifest-listed files are previewed or
downloaded through authenticated endpoints and can be streamed by Nginx. A
full ZIP is an optional asynchronous cache created only after an explicit
archive request. It contains only files published by the manifest and is not
part of task completion.

The dashboard groups previewable artifacts into a scientific gallery. Images,
bounded CSV/TSV tables, and text use local preview plugins. PDB/mmCIF files use
the pinned Mol* Viewer 5.10.0 bundle with subresource-integrity verification;
if that asset or WebGL is unavailable, the dashboard falls back to a local
alpha-carbon trace. Inline image and structure previews have size limits so a
large artifact is downloaded instead of being loaded wholesale into browser
memory.

## 9. Public Access

Docker Compose publishes the Nginx `gateway` service. The Flask/Gunicorn `web`
service is internal-only. Nginx proxies application requests and serves
authorized individual artifacts or optional ZIP bytes with an internal
`X-Accel-Redirect`. The gateway mounts only `${SERVER_DIR}/results` and mounts
it read-only.

### Option A: Cloudflare Tunnel

Point Cloudflare Tunnel at the gateway's published `${PORT}`. Do not target the
internal Gunicorn service directly.

Reference: [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

### Option B: Additional host reverse proxy or TLS termination

An additional host-level proxy may sit in front of the container gateway when
custom TLS termination, routing, or rate limits are required.

You can start from:

- `server/nginx_sites/REvoCompute.app`

## 10. Security

### Docker socket

Only the worker mounts `/var/run/docker.sock` to spawn runner containers. This
separates Docker authority from the public web process, but it is not a
container-escape boundary:

- The worker runs as a non-root user for file ownership, but Docker socket
  access remains effectively Docker-daemon/host-level authority regardless of
  its primary UID.
- `restart.sh` auto-detects `DOCKER_GID` at runtime and exports it
  for Docker Compose.  Do not persist host-specific socket groups in the env
  file.  If tasks fail with `PermissionError(13, 'Permission denied')`, compare
  the helper output with `docker exec server-worker-1 ls -ln
  /var/run/docker.sock`.  On Docker Desktop/OrbStack for macOS the bind-mounted
  socket commonly appears as group `0`, even when the host socket target has a
  user-owned group.
- The runner container has a SETUID `ldconfig.real` binary for shared-library cache updates.
- Consider using a Docker socket proxy (e.g. `docker-socket-proxy`) to restrict API access in untrusted environments.
- Never expose the Docker socket to a public network.

Security regression checks for Docker socket exposure, admin self-lockout,
banned users, and login throttling are maintained in
`docs/dev-guide/server.md#security-validation`.

### Authentication

- Authentication signing keys are ephemeral; restarting web invalidates
  existing login, verification, and password-reset tokens.
- Browser page navigations use an `HttpOnly`/`SameSite=Lax` cookie; JavaScript
  cannot read it, so logout requires the server endpoint (`POST /api/auth/logout`).
- Rate limiting: 5 login attempts/minute/IP, 3 registrations/hour/IP.
- All state-changing endpoints require a valid Bearer token or API key.
- API keys have restricted privileges (task operations only) — Bearer tokens are required for profile changes and admin actions.
- Cookie-only writes are rejected; state-changing API calls require a Bearer
  token or API key.

### Redis

- Redis is on an internal Docker network; do not expose its port publicly.
- The current Compose stack does not configure Redis authentication. Do not
  assume that setting `REDIS_PASSWORD` alone enables it.

### Data

- User passwords are hashed with `werkzeug.security.generate_password_hash` (pbkdf2:sha256).
- The user database is stored under the web/maintenance-only `AUTH_DIR`. The task database,
  uploads, and results remain under `SERVER_DIR`, which web and worker share.
- All API request payloads are validated through typed Pydantic models
  (``schemas.py``) before reaching business logic — malformed input is rejected
  at the boundary.
- Environment variables that are empty strings (e.g. from docker compose
  `${VAR:-}`) are treated as unset, not as valid empty values that would
  silently resolve to CWD or bypass defaults.
- Task IDs are validated against `[a-f0-9]{32}` before any filesystem access.
- File paths are validated with `_safe_join` / `_path_is_within` to prevent directory traversal.

## 11. Operations Notes

- Restrict Docker socket access to trusted operators only.
- Task visibility and operations are always restricted to the owner or an
  administrator.
- Regularly back up sqlite and finalized result trees. Optional ZIP files are derived caches.
- If a task is deleted, result artifacts are removed, but the sqlite record remains for audit.

## 12. Local Development

```bash
# Install in editable mode with test dependencies
pip install -e "server/[test]"

# Run the server-owned non-Docker suite
make -C server test

# Run the same coverage target used by server CI
make -C server test-cov

# Run the server directly without Docker
python -m revocompute.app
```

Full test and security validation guidance is maintained in
`docs/dev-guide/server.md`.

## 13. SLURM + Apptainer Deployment

The server supports a SLURM + Apptainer runner backend as an alternative to
Docker-out-of-Docker.  When enabled, the worker submits `srun` jobs that run
Apptainer containers on SLURM compute nodes instead of launching Docker
containers locally.

### 13.1 Maintainer Workflow — Step by Step

This is the checklist for enabling a task type on a SLURM deployment.

#### Step 1: Prerequisites on the deployment host

The host running the server containers must have:

- **SLURM client** — `srun`, `squeue`, `scancel`, `sacct`, `sinfo` (bind-mounted into the worker)
- **MUNGE** — `/run/munge` socket + `libmunge.so.2` (SLURM authentication)
- **Apptainer** — on PATH if using `--build-sif`, or at least on the SLURM compute nodes
- **SLURM config** — `/etc/slurm-llnl/` accessible to the worker (host networking)

Verify connectivity from the worker container after startup:
```bash
docker exec server-slurm-worker-1 srun --version
docker exec server-slurm-worker-1 sinfo
```

#### Step 2: Create the `.env` file

Copy an existing SLURM env and customise:

```bash
cp server/.env.production.v7-slurm server/.env.production.v8-custom
```

Key SLURM-specific variables:

| Variable | Purpose |
|----------|---------|
| `COMPOSE_PROJECT_NAME` | **Must differ from production** (e.g. `server-slurm`). Compose isolation prevents one deployment from interfering with another. |
| `SERVER_IMAGE` | **Must differ from production** (e.g. `revodesign-revocompute-server-slurm`). Image tag collision would overwrite the wrong image. |
| `PORT` | Choose a free host port (e.g. `8081`). |
| `SLURM_ALLOWED_QUEUES` | Comma-separated partition names visible in `/compute/configuration` (e.g. `normal,gpu`). |
| `ENABLED_TASKRUNNERS` | Comma-separated list of additional task types beyond `gremlin` (e.g. `pythia_ddg`). |
| `CONFIG_DIR` | Path to deployed config directory containing `task_types.yaml` and `runners/`. |
| `REDIS_URL` | `redis://redis:6379/0` for bridge containers; `redis://127.0.0.1:6380/0` for host-networked worker (set in `docker-compose.slurm.yml`). |

#### Step 3: Configure the executor and runtime families

Select SLURM once in `<CONFIG_DIR>/task_types.yaml` and set each family’s SIF:

```yaml
job_executor: slurm
container_runtime: apptainer
runtime_families:
  pythia_ddg:
    docker_image: revodesign-revocompute-runner-pythia_ddg
    entrypoint: [bash, /app/revocompute/run.sh]
    dockerfile: docker/runners/pythia_ddg/Dockerfile
    definition: docker/runners/pythia_ddg/pythia_ddg.def
    slurm_image: /mnt/data/srv/revodesign/server-slurm/images/pythia_ddg_v1.sif
```

Fields `mounts`, `env`, `nproc`, `max_runtime_seconds`, and `defaults` work
identically for both executors and remain in the corresponding runner YAML.

Per-task SLURM resource directives (partition, cpus-per-task, mem, time,
gres, etc.) are configured via the admin UI at `/compute/configuration` and
stored in `manage.sqlite` — not in the YAML.

#### Step 4: Create the `.def` file

Each runtime family declares its exact Apptainer definition path in
`config/task_types.yaml`. The restart helper rejects missing definitions; it
does not guess with `find`.

```def
Bootstrap: docker-daemon
From: revodesign-revocompute-runner-pythia:latest

%post
    echo "Pythia-ddG runner containerised"

%runscript
    exec bash /app/revocompute/run.sh "$@"
```

The `.def` uses `Bootstrap: docker-daemon` to convert a locally-built Docker
image into SIF.  The Docker image must already exist in the local Docker
daemon (built by `cmd_build` in `restart.sh`).

**Convention:** place the `.def` alongside the Dockerfile and keep its `From:`
image equal to the runtime family's `docker_image`. Pythia's repository-bundled
checkpoints are intentionally retained because they are small.

The `prime` family serves two distinct model contracts. **Pro-Prime OGT
prediction** uses the pinned `AI4Protein/ProPrime_650M_OGT_Prediction` snapshot
at `PRIME_MODEL_DIR`. **PRIME DMS** uses the pinned `AI4Protein/Prime_690M`
snapshot at `PRIME_DMS_MODEL_DIR`, matching the upstream
`notebooks/run_proteingym.ipynb` scoring rule. One input sequence produces an
exhaustive single-substitution DMS CSV. If the upload contains multiple FASTA
records or files, the first sequence is the reference and each remaining
sequence is scored as a supplied combinatorial variant; all substitutions'
log-probability differences are summed.

The older `prime_base.pt` file belongs to the legacy `Prime_1` mutant-effect
implementation. It is preserved for rollback and provenance, but renaming it
to `checkpoint.pt` neither makes it an OGT checkpoint nor makes it equivalent
to the immutable Hugging Face snapshots used by these production tasks.

The shared `mpnn` family pins a commit-identical fork of the official
`dauparas/ProteinMPNN` repository.
**ProteinMPNN** uses its vanilla (or explicitly selected CA-only) checkpoints;
**SolubleMPNN** is a distinct task that passes the upstream
`--use_soluble_model` flag and permits only the published `v_48_010` and
`v_48_020` soluble checkpoints. HyperMPNN, LigandMPNN, and ThermoMPNN-D remain
separate task contracts in the same dependency image. **LASErMPNN** also uses
this CPU family for ligand-conditioned sequence and side-chain design. It
accepts multiple protonated PDB/mmCIF snapshots, preserves nested upload paths,
and exposes the upstream all-data default and paper-analysis checkpoints as
explicit choices; arbitrary checkpoint paths and key-mismatch bypasses remain
server controlled.

The `easifa` family uses the pinned official EasIFA2 Core single-prediction
interface, not the legacy EasIFA dataset benchmark. Its read-only checkpoint
mount contains only `all_features`, `wo_reactions`, and `rxn_model` directories
from the pinned `xiaoruiwang/EasIFA2.0_Metadata` revision. A structure without
reaction SMILES selects `wo_reactions`; supplying `reactants>>products` selects
`all_features`. Checkpoint paths and CUDA device selection remain operator
controlled. Each successful task publishes the complete upstream JSON plus an
`active_sites.csv` residue table for manifest-first preview and download.

#### Step 5: Build and deploy

```bash
REVODESIGN_SERVER_ENV=server/.env.production.v7-slurm \
  bash server/run/restart.sh restart --mode=dev --build-sif
```

This runs in order:

1. **`cmd_down`** — stops the existing stack
2. **`cmd_build`** — builds each declared runtime family once, then web/worker
3. **`build_slurm_images`** — converts each Docker image to `.sif` via Apptainer
   (skips images that already exist at the target path)
4. **`validate_slurm_images`** — confirms all SIF files exist at their expected paths
5. **`cmd_up`** — starts the compose stack

| Flag | Purpose |
|------|---------|
| `--build-sif` | Auto-builds `.sif` images from `.def` files (requires Apptainer on PATH) |

The SIF build runs **after** Docker builds because `.def` files use
`Bootstrap: docker-daemon` which reads from the local Docker image cache.
Order matters — building SIF before Docker images exist would fail.

#### Step 6: Configure per-task SLURM resources

After startup, go to `/compute/configuration` and set per-task-type SLURM
parameters: partition, cpus-per-task, memory, time limit, GRES, etc.  These
are stored in `manage.sqlite` in the server directory and become `--option=value`
flags on the `srun` command line.

#### Step 7: Verify

Submit a test task and monitor:

```bash
# Watch SLURM queue
squeue --name=revocomput_

# Check task status via API
curl -H "Authorization: Bearer <token>" \
  "http://<server>:<port>/compute/api/status/<task_md5>"
```

### 13.2 docker-compose.slurm.yml

The override file adds:

- **worker** → `network_mode: host` (needed to reach the SLURM controller)
- **worker** → bind-mounted SLURM tools (`srun`, `sbatch`, `squeue`, `scancel`, `sacct`, `sinfo`)
- **worker** → bind-mounted MUNGE socket + library (SLURM authentication)
- **redis** → published on `6380:6379` (host `:6379` is occupied; worker uses `REDIS_URL=redis://127.0.0.1:6380/0`)
- **web, worker, maintenance** → `CONFIG_DIR` mounted read-only

### 13.3 Architecture

```
Worker (host network)                   SLURM controller
  │                                         │
  ├─ srun bash _slurm_wrapper.sh ──────────►│
  │                                         │
  │     SLURM compute node                  │
  │       ├─ apptainer run --nv *.sif       │
  │       │   ├─ /mnt/revocompute/<user>/inputs  (snapshot, ro) │
  │       │   ├─ /mnt/revocompute/<user>/outputs (task-owned, rw)│
  │       │   └─ DB mounts (ro, from YAML)  │
  │       │                                 │
  │       └─ stdout/stderr → srun pipes → worker threads
  │                                         │
  └─ Popen.wait() → exit code               │
```

### 13.4 SIF Image Build (Manual)

When the auto-build isn't suitable, build manually:

```bash
# 1. Build the Docker image
docker build -t revodesign-revocompute-runner-pythia:latest \
  -f server/docker/runners/pythia_ddg/Dockerfile server/

# 2. Convert to SIF (any .def file under docker/runners/ works)
apptainer build --fakeroot /path/to/pythia_ddg_v1.sif \
  server/docker/runners/pythia_ddg/pythia_ddg.def
```

The `restart.sh --build-sif` flag automates both steps for every runtime family
in a registry whose global executor is SLURM.

### 13.5 Runtime Size Gate

Do not estimate savings from Dockerfile text. After building on the designated
Linux builder, record both expanded Docker bytes and compressed SIF bytes:

```bash
python server/tools/audit_runtime_sizes.py \
  --task-types "${CONFIG_DIR}/task_types.yaml" \
  --require-all \
  --json > runtime-sizes.json
```

The command only inspects artifacts already present; it never pulls, builds,
or runs them. Compare the JSON with the previous production release before
promotion. Runtime-family sharing reduces the number of distinct artifacts;
the MPNN family additionally omits inference-unused CUDA stub, Triton,
torchvision, and torchaudio wheels. Removing build tools in a later Docker
layer is not counted as a size optimization because earlier layer bytes remain.

### 13.6 GPU Privilege Gating

Users must have `allow_gpu_use=true` (toggled by admins via the User Control
page) to submit task types marked `gpus: true` in `task_types.yaml`.  This
is enforced at submission time — unprivileged users receive 403 before the
job is enqueued.

### 13.6 slurm_job_id Persistence

The SLURM job ID (`srun-<pid>`) is stored in the `slurm_job_id` column of
the tasks table.  When a user cancels a running SLURM task, the web process
calls `scancel` with this ID before terminating the `srun` process.

### 13.7 Live Output

The `SlurmJob` class captures `srun` stdout/stderr via `subprocess.Popen`
pipes in background threads.  `REVODESIGN_STAGE:` markers are parsed from
stdout in real time and forwarded to the stage callback — matching the
Docker runner's live progress behaviour.

### 13.8 Task States

SLURM tasks use an additional `queued` status:
- **`queued`** — `srun` is waiting for a SLURM allocation (resource contention)
- **`running`** — first `REVODESIGN_STAGE:` marker received, job is executing

This transition happens via the stage callback: when the first
`REVODESIGN_STAGE:` line appears on stdout, the status moves from `queued`
to `running`.

## 14. Troubleshooting

### Network issues

If `docker compose` failed due to network issues, try this:

1. Add proxy settings to your `/etc/systemd/system/docker.service.d/http-proxy.conf` file
2. Reload systemd service: `sudo systemctl daemon-reload`
3. Restart docker: `sudo systemctl restart docker`
4. Rerun restart scripts or `docker compose` commands under non-root user

A proper `http-proxy.conf` file might look like this:

```text
[Service]
Environment="HTTP_PROXY=http://proxy-user:proxy-password@proxy.internal:8080"
Environment="HTTPS_PROXY=http://proxy-user:proxy-password@proxy.internal:8080"
Environment="ALL_PROXY=http://proxy-user:proxy-password@proxy.internal:8080"
Environment="NO_PROXY=localhost,127.0.0.1,192.168.0.0/16,localhost,127.0.0.1,10.96.0.0/12,192.168.59.0/24,192.168.49.0/24,192.168.39.0/24,192.168.67.0/24,172.17.0.0/24,192.168.0.0/16,100.87.0.0/16,192.168.75.0/24,192.168.194.0/24,192.168.67.2"
```
