# PSSM GREMLIN Server

The server is a Docker-deployed Flask + Celery + Docker-runner web service for
GREMLIN co-evolution analysis.

## Docker Deployment

This guide covers both local-image development (`--mode=dev`) and
published-image production (`--mode=prod`). Native/manual production deployment
is intentionally excluded.

## Overview

The server stack contains:

- `web`: Flask + Gunicorn API/UI service
- `maintenance`: APScheduler process for registration digests, optional result cleanup, and database backups
- `worker`: Celery worker for background jobs
- `redis`: Celery broker/backend
- `runner` image: GREMLIN/PSSM execution container launched by `worker`

Periodic jobs follow this package boundary:

```text
pssm_gremlin_server/maintenance/
├── model.py                 # PeriodicTask interface
├── manager.py               # imports task objects and calls register()
└── tasks/
    ├── admin_digest.py      # self-configuring admin_digest_task
    ├── database_backup.py   # consistent task/user SQLite snapshots
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
- Enough disk space for UniRef databases, logs, and result archives

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
```

### Env-file isolation

All restart helpers support `REVODESIGN_SERVER_ENV`:

```bash
REVODESIGN_SERVER_ENV=server/.env.local bash server/run/restart_pssm_flask.sh restart --mode=dev
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh restart --mode=prod
```

Fallback when `REVODESIGN_SERVER_ENV` is unset:

1. `server/.env.production` (if present)
2. `server/.env`

### Required/important variables

| Variable | Purpose |
| --- | --- |
| `SERVER_IMAGE`, `RUNNER_IMAGE` | Image names built locally in dev mode or pulled in prod mode. Production must use full published Docker Hub references. |
| `SERVER_DIR` | Host root shared by web and worker for uploads, task SQLite, and result folders (default: `./pssm_gremlin_data`). Never store the user database here. |
| `RUNNER_HOST_ROOT` | Host root allowed for Docker runner bind mounts (default: parent of `SERVER_DIR`). |
| `LOG_DIR` | Host directory for Gunicorn/Celery logs. |
| `DB_UNIREF30` | UniRef30 prefix path (default: `{SERVER_DIR}/db/uniref30/UniRef30_2022_02`). |
| `DB_UNIREF90` | UniRef90 BLAST prefix path (default: `{SERVER_DIR}/db/uniref90/uniref90`). |
| `AUTH_SECRET_KEY` | Fixed secret for signing auth tokens. Set in production so tokens survive restarts. |
| `AUTH_TOKEN_MAX_AGE` | Token lifetime in seconds (default: 604800 = 7 days). |
| `AUTH_DIR` | Host-side directory containing `users.sqlite3`; Compose mounts it only into web and maintenance. It must be outside `SERVER_DIR`. |
| `USER_DB_PATH` | Container-side path used by web and maintenance to open the user DB. Keep the default `/var/lib/revodesign-auth/users.sqlite3` unless the Compose mount target also changes. |
| `ENABLE_REGISTER` | Set to `true` to enable self-registration; configure either SMTP or Resend email delivery. |
| `SMTP_*`, `RESEND_*` | Email delivery settings. Resend takes priority when both backends are configured. |
| `SERVER_BASE_URL` | Public base URL for email links and HTTPS-sensitive auth-cookie settings. |
| `RUNNER_UID`, `RUNNER_GID` | Runner UID/GID. Dev may match the host; published production images require `1000:1000`. |
| `DOCKER_GID` | Auto-detected by `restart_pssm_flask.sh` at runtime for Docker Compose interpolation. Override only as a shell variable when detection is wrong. |
| `NPROC` | CPU threads passed to runner. |
| `MAXMEM` | Memory cap (GB) passed to hhblits (`-maxmem`) inside runner script. |
| `WORKER_CONCURRENCY` | Celery worker concurrency. |
| `GUNICORN_WORKERS` | Gunicorn worker count. |
| `PORT` | Public HTTP port. |
| `RESULT_RETENTION_DAYS` | Optional positive number of days to retain terminal-task result directories and archives. Leave unset to disable cleanup; task audit rows remain. |
| `BACKUP_DB_CRON` | Five-field crontab schedule for database snapshots. Leave unset to disable; recommended daily schedule: `0 0 * * *`. |
| `BACKUP_DB_PATH` | Snapshot directory inside the maintenance container. `/var/lib/revodesign-auth/backups` persists at `${AUTH_DIR}/backups` on the host. |
| `MAX_DB_BACKUP` | Maximum complete snapshot sets to retain. Leave unset for unlimited history; recommended value: `30`. |
| `ADMIN_USERS` | Comma-separated admin usernames for cross-user management. |
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

## 4. Authentication

The server uses Bearer-token authentication (replaces the old HTTP Basic Auth + `users.txt` model).

### How auth works

- **Browser access**: Logging in sets an `HttpOnly` cookie so page navigations
  (dashboard, profile, create task) are authenticated without manual header
  management.  Already-authenticated visitors to `/login` or `/register` are
  redirected to the dashboard.
- **API access**: Clients send `Authorization: Bearer <token>` for full access,
  or `X-API-Key: <key>` for long-lived programmatic access with restricted
  privileges (tasks only — no profile changes or admin actions).
- **Logout**: `POST /PSSM_GREMLIN/api/auth/logout` clears the server-side
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

### First run

If the user database is empty, a default admin account is created automatically:

- Username: `admin` (customize with `DEFAULT_ADMIN_USERNAME`)
- Password: auto-generated and displayed in the restart script output.
  Change immediately after first login.

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
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/login"

# Use the token for subsequent requests
curl -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/me"

# Logout (clears the auth cookie)
curl -X POST -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/logout"
```

### Admin user management

```bash
# Admin creates a new user (requires admin token)
curl -X POST -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","email":"user@example.com","password":"...","role":"user"}' \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/admin/users"
```

`role` may be `admin`, `user`, or `guest`.

Admins cannot ban or delete their own account.  Direct self-ban/self-delete
requests return HTTP 400, and batch Disable/Delete skips the acting admin while
still applying the requested action to other selected users.

### API keys (programmatic access)

Long-lived API keys are available for scripted/programmatic access. Generate and revoke
them from the Profile page (`/PSSM_GREMLIN/profile`), or via the API:

```bash
# Generate (returns plaintext key once — store it securely)
curl -X POST -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/me/api-key"

# Check status
curl -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/me/api-key"

# Revoke
curl -X DELETE -H "Authorization: Bearer <token>" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/me/api-key"
```

Use the key via the `X-API-Key` header:

```bash
curl -H "X-API-Key: revodesign_<hex>" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/me"
```

API keys never expire but have **restricted privileges**: they can submit tasks and
read results, but **cannot** change passwords, manage API keys, or perform admin
actions. Use a Bearer token (web login) for those operations.  **Guest accounts
cannot use API keys at all** — they are web-dashboard-only accounts.

Rate limits: 5 login attempts/minute per IP, 3 registrations/hour per IP.  The
login endpoint returns HTTP 429 with `retry_after_seconds`; the login page uses
that value to disable the submit button and count down until retry.

## 5. Build and Run

### Recommended helper script

No sudo required.

```bash
# initialize the env file and print detected Docker socket group
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh setup

# development: down + local build using host UID/GID + up
REVODESIGN_SERVER_ENV=server/.env.local bash server/run/restart_pssm_flask.sh restart --mode=dev

# production: down + pull configured Docker Hub images + up without building
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh restart --mode=prod

# subcommands
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh migrate-auth-db
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh build
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh up
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh down
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

Provision production bind-mounted directories as writable by UID/GID
`1000:1000`. This identity contract provides non-root execution and compatible
file ownership; it is not a container-escape boundary. The worker's Docker
socket access still grants effective Docker-daemon/host-level authority.

### Isolate an existing user database

This step is only for an upgrade where the old database still exists at
`${SERVER_DIR}/users.sqlite3`. Set `AUTH_DIR` to its new host directory, stop
the stack, and run the explicit migration once:

```bash
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh down
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh migrate-auth-db
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh restart --mode=prod
```

The migration refuses to overwrite an existing destination, checks SQLite
integrity and user counts, and moves the legacy copy into `AUTH_DIR` as a
timestamped rollback backup. To roll back while the stack is stopped, restore
that backup to the original `${SERVER_DIR}/users.sqlite3` path and deploy the
previous Compose configuration.

For a fresh installation there is nothing to migrate: create `AUTH_DIR` and
start normally. The web process creates `${AUTH_DIR}/users.sqlite3`.

### Equivalent Docker Compose commands

Development mode:

```bash
docker compose -f server/docker-compose.yml --env-file server/.env.local down
docker compose -f server/docker-compose.yml --env-file server/.env.local --profile runner build runner
docker compose -f server/docker-compose.yml --env-file server/.env.local build web worker
docker compose -f server/docker-compose.yml --env-file server/.env.local up --no-build -d redis web maintenance worker
```

Production mode:

```bash
docker compose -f server/docker-compose.yml --env-file server/.env.production down
docker compose -f server/docker-compose.yml --env-file server/.env.production --profile runner pull web runner
docker compose -f server/docker-compose.yml --env-file server/.env.production up --no-build -d redis web maintenance worker
```

### Zero-downtime Gunicorn reload

```bash
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/hot_fix.sh
```

## 6. Usage

### Create task page

- `http://<server-ip>:<port>/PSSM_GREMLIN/create_task`
- Upload ``.fasta`` files via the **Choose File** button or by **dragging and dropping** a file anywhere on the card.
- An optional sequence editor lets you paste raw protein sequences as text instead of uploading a file.

### Dashboard

- `http://<server-ip>:<port>/PSSM_GREMLIN/dashboard`

### Upload via curl (with token auth)

```bash
# Obtain a token first (see Authentication section above)
TOKEN="<your-token>"

curl -H "Authorization: Bearer ${TOKEN}" \
  -X POST \
  -F "file=@/path/to/input.fasta" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/post"
```

### Batch upload via curl

```bash
for f in *.fasta; do
  curl -H "Authorization: Bearer ${TOKEN}" -X POST -F "file=@${f}" \
    "http://<server-ip>:<port>/PSSM_GREMLIN/api/post"
done
```

### Delete one task (single-task API)

```bash
TASK_MD5="<task-md5>"
curl -H "Authorization: Bearer ${TOKEN}" -X DELETE \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/delete/${TASK_MD5}"
```

### Delete multiple tasks (batch API)

```bash
curl -H "Authorization: Bearer ${TOKEN}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"md5sums":["<task-md5-a>","<task-md5-b>"]}' \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/delete"
```

## 7. Task States

Current server states:

- `pending`
- `running`
- `packing results`
- `finished`
- `failed`
- `cancelled`
- `deleted:finshed`
- `deleted:cancel`

Deletion is tracked in sqlite (soft-delete). Task records remain for audit/debug.
The `deleted:finshed` spelling is intentionally preserved for runtime compatibility.

## 8. Optional Public Access

### Option A (simple): Cloudflare Tunnel

Use Cloudflare Tunnel to expose the internal service without opening inbound ports.

Reference: [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

### Option B (advanced): NGINX reverse proxy

Use NGINX when you need custom TLS termination, routing, and rate limits.

You can start from:

- `server/nginx_sites/REvoDesign_PSSM_GREMLIN.app`

## 9. Security

### Docker socket

Only the worker mounts `/var/run/docker.sock` to spawn runner containers. This
separates Docker authority from the public web process, but it is not a
container-escape boundary:

- The worker runs as a non-root user for file ownership, but Docker socket
  access remains effectively Docker-daemon/host-level authority regardless of
  its primary UID.
- `restart_pssm_flask.sh` auto-detects `DOCKER_GID` at runtime and exports it
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

- Set `AUTH_SECRET_KEY` to a fixed, high-entropy value in production; otherwise tokens are lost on restart.
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

## 10. Operations Notes

- Restrict Docker socket access to trusted operators only.
- Task visibility and operations are always restricted to the owner or an
  administrator.
- Regularly back up sqlite and result archives.
- If a task is deleted, result artifacts are removed, but the sqlite record remains for audit.

## 11. Local Development

```bash
# Install in editable mode with test dependencies
pip install -e "server/[test]"

# Run the server-owned non-Docker suite
make -C server test

# Run the same coverage target used by server CI
make -C server test-cov

# Run the server directly without Docker
python -m pssm_gremlin_server.pssm_gremlin
```

Full test and security validation guidance is maintained in
`docs/dev-guide/server.md`.

## 12. Troubleshooting

### Network issues

If `docker compose` failed due to network issues, try this:

1. Add proxy settings to your `/etc/systemd/system/docker.service.d/http-proxy.conf` file
2. Reload systemd service: `sudo systemctl daemon-reload`
3. Restart docker: `sudo systemctl restart docker`
4. Rerun restart scripts or `docker compose` commands under non-root user

A proper `http-proxy.conf` file might look like this:

```text
[Service]
Environment="HTTP_PROXY=socks5://oreo:oreo@192.168.194.98:17890"
Environment="HTTPS_PROXY=socks5://oreo:oreo@192.168.194.98:17890"
Environment="ALL_PROXY=socks5://oreo:oreo@192.168.194.98:17890"
Environment="NO_PROXY=localhost,127.0.0.1,192.168.0.0/16,localhost,127.0.0.1,10.96.0.0/12,192.168.59.0/24,192.168.49.0/24,192.168.39.0/24,192.168.67.0/24,172.17.0.0/24,192.168.0.0/16,100.87.0.0/16,192.168.75.0/24,192.168.194.0/24,192.168.67.2"
```
