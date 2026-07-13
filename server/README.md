# PSSM GREMLIN Server (Production Guide)

This document describes the production Docker deployment for the PSSM GREMLIN server.
Native/manual deployment is intentionally excluded.

## Overview

The server stack contains:

- `web`: Flask + Gunicorn API/UI service
- `worker`: Celery worker for background jobs
- `redis`: Celery broker/backend
- `runner` image: GREMLIN/PSSM execution container launched by `web`/`worker` through Docker socket access

Both `web` and `worker` must access `/var/run/docker.sock` to start runner containers.

## 0. Prerequisites

Install the following on the production host:

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
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh restart
```

Fallback when `REVODESIGN_SERVER_ENV` is unset:

1. `server/.env.production` (if present)
2. `server/.env`

### Required/important variables

| Variable | Purpose |
| --- | --- |
| `SERVER_DIR` | Host root for uploads, sqlite, and result folders. |
| `LOG_DIR` | Host directory for Gunicorn/Celery logs. |
| `DB_UNIREF30` | UniRef30 prefix path. |
| `DB_UNIREF90` | UniRef90 BLAST prefix path. |
| `AUTH_SECRET_KEY` | Fixed secret for signing auth tokens. Set in production so tokens survive restarts. |
| `AUTH_TOKEN_MAX_AGE` | Token lifetime in seconds (default: 604800 = 7 days). |
| `USER_DB_PATH` | Path to the user database (default: `{SERVER_DIR}/users.sqlite3`). |
| `ENABLE_REGISTER` | Set to `true` to enable self-registration (requires SMTP). |
| `DEFAULT_ADMIN_PASSWORD` | Password for the default admin account (created on first run if user DB is empty). |
| `SMTP_HOST` | SMTP server hostname (required for registration + email verification). |
| `SMTP_PORT` | SMTP port (default: 587). |
| `SMTP_USERNAME` | SMTP authentication username. |
| `SMTP_PASSWORD` | SMTP authentication password. |
| `SMTP_USE_TLS` | Use STARTTLS (default: `true`). |
| `SMTP_FROM_ADDR` | Sender address for verification emails. |
| `SMTP_FROM_NAME` | Sender display name. |
| `SERVER_BASE_URL` | Public base URL for generating verification links. |
| `REDIS_PASSWORD` | Optional Redis authentication password. |
| `RUNNER_UID`, `RUNNER_GID` | Runner UID/GID (non-root required). |
| `DOCKER_GID` | Group ID of Docker socket on host. |
| `NPROC` | CPU threads passed to runner. |
| `MAXMEM` | Memory cap (GB) passed to hhblits (`-maxmem`) inside runner script. |
| `WORKER_CONCURRENCY` | Celery worker concurrency. |
| `GUNICORN_WORKERS` | Gunicorn worker count. |
| `PORT` | Public HTTP port. |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated allowed email domains for registration (empty = all allowed). Also normalises plus-aliased addresses. |
| `PUBLIC_DASHBOARD` | `false` by default; scopes task visibility to owner unless admin. |
| `ADMIN_USERS` | Comma-separated admin usernames for cross-user management. |
| `TZ` | Timezone for logs. |

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

### Gunicorn `--preload`

Gunicorn workers are started with `--preload` so the auth secret key is
generated once in the arbiter before forking.  Without this, each worker
independently generates its own signing key, making tokens from one worker
fail validation on another.

### First run

If the user database is empty, a default admin account is created automatically:

- Username: `admin` (customize with `DEFAULT_ADMIN_USERNAME`)
- Password: from `DEFAULT_ADMIN_PASSWORD` env var, or a random password
  displayed in the restart script output

Change the password immediately after first login.  The `restart_pssm_flask.sh`
script generates and displays the admin password on first boot when
`DEFAULT_ADMIN_PASSWORD` is unset.

Set `ENABLE_REGISTER=true` and configure SMTP to allow self-registration.
Users receive a verification email; accounts must be verified before use.
Without SMTP, registration is disabled — use the admin API to create accounts.

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
  -d '{"username":"newuser","email":"user@example.com","password":"...","is_admin":false}' \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/admin/users"
```

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
actions. Use a Bearer token (web login) for those operations.

Rate limits: 5 login attempts/minute per IP, 3 registrations/hour per IP.

## 5. Build and Run

### Recommended helper script

No sudo required.

```bash
# initialize env values (for example DOCKER_GID)
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh setup

# full restart cycle (down + build + up)
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh restart

# subcommands
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh build
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh up
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh down
```

### Equivalent Docker Compose commands

```bash
docker compose -f server/docker-compose.yml --env-file server/.env.production down
docker compose -f server/docker-compose.yml --env-file server/.env.production --profile runner build runner
docker compose -f server/docker-compose.yml --env-file server/.env.production build web worker
docker compose -f server/docker-compose.yml --env-file server/.env.production up -d redis web worker
```

### Zero-downtime Gunicorn reload

```bash
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/hot_fix.sh
```

## 6. Usage

### Create task page

- `http://<server-ip>:<port>/PSSM_GREMLIN/create_task`

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

The web and worker containers mount `/var/run/docker.sock` to spawn runner containers. This is a security boundary:

- The web/worker run as a non-root user with group-based Docker access.
- The runner container has a SETUID `ldconfig.real` binary for shared-library cache updates.
- Consider using a Docker socket proxy (e.g. `docker-socket-proxy`) to restrict API access in untrusted environments.
- Never expose the Docker socket to a public network.

### Authentication

- Tokens are signed with `itsdangerous.URLSafeTimedSerializer` (HMAC-SHA1).
- Gunicorn uses `--preload` so the auth secret key is generated once in the
  arbiter; all workers share the same key and tokens validate consistently.
- Set `AUTH_SECRET_KEY` to a fixed, high-entropy value in production; otherwise tokens are lost on restart.
- Browser page navigations use an `HttpOnly`/`SameSite=Lax` cookie; JavaScript
  cannot read it, so logout requires the server endpoint (`POST /api/auth/logout`).
- Rate limiting: 5 login attempts/minute/IP, 3 registrations/hour/IP.
- All state-changing endpoints require a valid Bearer token or API key.
- API keys have restricted privileges (task operations only) — Bearer tokens are required for profile changes and admin actions.
- CSRF is mitigated: all state-changing requests use `fetch()` with JSON content-type and Bearer tokens or the HttpOnly cookie.

### Redis

- Set `REDIS_PASSWORD` in production to enable Redis authentication.
- Redis is on an internal Docker network; do not expose its port publicly.

### Data

- User passwords are hashed with `werkzeug.security.generate_password_hash` (pbkdf2:sha256).
- User database (`users.sqlite3`) and task database (`pssm_gremlin.sqlite3`) are stored under `SERVER_DIR`, not in the web root.
- Environment variables that are empty strings (e.g. from docker compose
  `${VAR:-}`) are treated as unset, not as valid empty values that would
  silently resolve to CWD or bypass defaults.
- Task IDs are validated against `[a-f0-9]{32}` before any filesystem access.
- File paths are validated with `_safe_join` / `_path_is_within` to prevent directory traversal.

## 10. Operations Notes

- Restrict Docker socket access to trusted operators only.
- Keep `PUBLIC_DASHBOARD=false` for private per-user isolation.
- Regularly back up sqlite and result archives.
- If a task is deleted, result artifacts are removed, but the sqlite record remains for audit.

## 11. Troubleshooting

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
