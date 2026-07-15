# PSSM GREMLIN Server

The server is a pip-installable package (`pssm_gremlin_server`) providing a
Flask + Celery + Docker-runner web service for GREMLIN co-evolution analysis.

## Development

```bash
# Install in editable mode with test dependencies
pip install -e "server/[test]"

# Run non-Docker tests from the repo root
pytest server/tests/ -v -k "not Docker and not docker"

# Run the server directly (no Docker)
python -m pssm_gremlin_server.pssm_gremlin
```

---

## Production Deployment

This section describes the production Docker deployment.
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
| `ENABLE_REGISTER` | Set to `true` to enable self-registration (requires Resend API key). |
| `RESEND_API_KEY` | Resend API key for sending verification and password-reset emails. |
| `RESEND_FROM_ADDR` | Sender email address (verified domain in Resend). |
| `RESEND_FROM_NAME` | Sender display name (default: REvoDesign GREMLIN Server). |
| `SERVER_BASE_URL` | Public base URL for generating verification links. |
| `REDIS_PASSWORD` | Optional Redis authentication password. |
| `RUNNER_UID`, `RUNNER_GID` | Runner UID/GID (non-root required). |
| `DOCKER_GID` | Auto-detected by `restart_pssm_flask.sh` at runtime for Docker Compose interpolation. Override only as a shell variable when detection is wrong. |
| `NPROC` | CPU threads passed to runner. |
| `MAXMEM` | Memory cap (GB) passed to hhblits (`-maxmem`) inside runner script. |
| `WORKER_CONCURRENCY` | Celery worker concurrency. |
| `GUNICORN_WORKERS` | Gunicorn worker count. |
| `PORT` | Public HTTP port. |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated allowed email domains for registration (empty = all allowed). Also normalises plus-aliased addresses. |
| `PUBLIC_DASHBOARD` | `false` by default; scopes task visibility to owner unless admin. |
| `ADMIN_USERS` | Comma-separated admin usernames for cross-user management. |
| `ADMIN_NOTIFY_EMAIL` | Comma-separated admin email addresses for new-user registration digests (default: empty = no notification). |
| `ADMIN_NEW_USER_INFORM` | Interval in minutes between new-user digest emails (default: `0` = disabled). |
| `ALLOWED_EMAIL_DOMAINS` | Comma-separated allowed email domains for self-registration (empty = all allowed). Also normalises plus-aliased addresses (`user+tag@domain` → `user@domain`). |
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

Set `ENABLE_REGISTER=true` and `RESEND_API_KEY` to allow self-registration.
Users receive a verification email; accounts must be verified before use.
Without a Resend API key, registration is disabled — use the admin API to create accounts.

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

The web and worker containers mount `/var/run/docker.sock` to spawn runner containers. This is a security boundary:

- The web/worker run as a non-root user with group-based Docker access.
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

#### Docker socket A/B attack test

Run this test after Docker, Compose, user/group, or runner-launch changes.  It
checks whether an authenticated low-privilege web user can turn task submission
into Docker daemon control.  The expected secure result is not just "the app
works"; it is that HTTP users can only submit normal FASTA tasks, cannot reach
Docker API routes, cannot choose Docker image/command/mounts, and cannot use a
cookie-only CSRF request for task writes.

Use an isolated staging instance.  Do not run destructive Docker escape payloads
on a host that stores real data.

Prepare:

```bash
export BASE_URL=http://127.0.0.1:8080
export ADMIN_USER=admin
export ADMIN_PASS='<admin-password>'

docker ps --format '{{.ID}} {{.Names}} {{.Image}} {{.Ports}}'
docker inspect server-web-1 server-worker-1 \
  --format '{{.Name}} User={{.Config.User}} Groups={{json .HostConfig.GroupAdd}} Mounts={{json .Mounts}}'
docker exec server-web-1 id
docker exec server-worker-1 id
docker exec server-web-1 ls -ln /var/run/docker.sock
docker exec server-worker-1 ls -ln /var/run/docker.sock
```

A result: the socket is not accessible from web/worker.  This proves the live
instance is not Docker-root-escape-capable, but Docker-backed task execution
will fail until permissions are fixed.  Expected evidence:

```text
/var/run/docker.sock -> srw-rw---- 1 0 0 ...
docker.from_env() from web/worker -> PermissionError(13, 'Permission denied')
submitted task -> failed with "Docker daemon unavailable" or PermissionError
```

B result: the socket is accessible from web/worker.  This is operationally
required for runner containers, but it is host-root-equivalent if arbitrary code
ever runs in web/worker.  In this case the test must prove the HTTP contract does
not expose Docker control.  Expected evidence:

```text
limited user /api/auth/admin/users -> 403
cookie-only POST /PSSM_GREMLIN/api/post -> 403 Bearer token required
POST /containers/create and GET /containers/json on the Flask port -> 404
path-like FASTA filename upload -> normal task only, sanitized filename, no host-path mount selection
server code fixes image, command, user, environment, and mounts from server config
```

The following probe creates a temporary non-admin user, checks the CSRF gate,
submits a harmless FASTA with a path-like filename, probes Docker-like HTTP
routes, and verifies API-key privilege limits:

```bash
python - <<'PY'
import json, re, uuid
import os
import requests

base = os.environ["BASE_URL"]
admin_user = os.environ["ADMIN_USER"]
admin_pass = os.environ["ADMIN_PASS"]

def show(label, resp):
    ctype = resp.headers.get("content-type", "")
    body = resp.text[:220].replace("\n", " ")
    if "application/json" in ctype:
        try:
            data = resp.json()
            body = {k: ("[redacted]" if k in {"token", "api_key"} else v) for k, v in data.items()}
        except Exception:
            pass
    print(json.dumps({"label": label, "status": resp.status_code, "location": resp.headers.get("Location"), "body": body}, sort_keys=True))

admin = requests.Session()
r = admin.post(f"{base}/PSSM_GREMLIN/api/auth/login", json={"username": admin_user, "password": admin_pass}, timeout=10)
show("admin_login", r)
r.raise_for_status()
admin_h = {"Authorization": "Bearer " + r.json()["token"]}

name = "limited_" + uuid.uuid4().hex[:8]
pw = "Pw_" + uuid.uuid4().hex + "!aA1"
r = admin.post(
    f"{base}/PSSM_GREMLIN/api/auth/admin/users",
    headers=admin_h,
    json={"username": name, "email": name + "@audit.local", "password": pw, "affiliation": "audit", "is_admin": False},
    timeout=10,
)
show("create_limited", r)

limited = requests.Session()
r = limited.post(f"{base}/PSSM_GREMLIN/api/auth/login", json={"username": name, "password": pw}, timeout=10)
show("limited_login", r)
r.raise_for_status()
limited_h = {"Authorization": "Bearer " + r.json()["token"]}

r = limited.get(f"{base}/PSSM_GREMLIN/api/auth/admin/users", headers=limited_h, timeout=10)
show("limited_admin_list", r)

files = {"file": ("../../../../var/run/docker.sock.fasta", b">audit\nACDEFGHIKLMNPQRSTVWY\n")}
r = limited.post(f"{base}/PSSM_GREMLIN/api/post", files=files, allow_redirects=False, timeout=10)
show("cookie_only_upload", r)

files = {"file": ("../../../../--privileged--var-run-docker-sock.fasta", b">audit\nACDEFGHIKLMNPQRSTVWY\n")}
r = limited.post(f"{base}/PSSM_GREMLIN/api/post", files=files, headers=limited_h, allow_redirects=False, timeout=15)
show("bearer_upload_pathlike_name", r)
loc = r.headers.get("Location") or ""
match = re.search(r"/running/([0-9a-f]{32})", loc)
if match:
    md5 = match.group(1)
    show("running_after_upload", limited.get(f"{base}/PSSM_GREMLIN/api/running/{md5}", headers=limited_h, timeout=10))
    show("delete_uploaded_task", limited.delete(f"{base}/PSSM_GREMLIN/api/delete/{md5}", headers=limited_h, timeout=10))

for method, path in [
    ("get", "/containers/json"),
    ("get", "/version"),
    ("post", "/containers/create"),
    ("get", "/PSSM_GREMLIN/api/docker"),
    ("post", "/PSSM_GREMLIN/api/docker/run"),
]:
    resp = getattr(limited, method)(base + path, headers=limited_h, timeout=10)
    show(f"probe_{method}_{path}", resp)

r = limited.post(f"{base}/PSSM_GREMLIN/api/auth/me/api-key", headers=limited_h, timeout=10)
show("limited_generate_api_key", r)
if r.status_code == 201:
    api_h = {"X-API-Key": r.json()["api_key"]}
    clean = requests.Session()
    show("apikey_admin_list", clean.get(f"{base}/PSSM_GREMLIN/api/auth/admin/users", headers=api_h, timeout=10))
    files = {"file": ("api-key-task.fasta", b">audit\nACDEFGHIKLMNPQRSTVWY\n")}
    show("apikey_upload_task", clean.post(f"{base}/PSSM_GREMLIN/api/post", files=files, headers=api_h, allow_redirects=False, timeout=15))
PY
```

Treat a failure in the expected status codes above as a security regression.
If B can access Docker and an HTTP user can influence image, command, privileged
mode, bind source paths, or socket mounts, this is a real host-root escape path.

#### Admin self-lockout check

Run this after admin user-management changes.  The expected result is that an
admin cannot remove their own access, either through a single-user action or a
batch action.

Expected results:

```text
self PUT user_status=banned -> 400 Administrators cannot ban their own account
self DELETE -> 400 Administrators cannot delete their own account
batch disable [self, other] -> count 1, self stays active, other becomes banned
batch delete [self, other] -> count 1, self remains undeleted, other is deleted
```

#### Banned-user authentication check

Run this after account-status or token-auth changes.  The check creates a
temporary user, confirms it can log in before the ban, bans it, and verifies
that new login, old Bearer token, and pre-existing API key are all rejected.

Expected results:

```text
pre_ban_login -> 200
pre_ban_api_key -> 201
ban_user -> 200
post_ban_login -> 403 Account has been suspended
post_ban_old_bearer_me -> 401 Authentication required
post_ban_api_key_me -> 401 Authentication required
```

Command:

```bash
python - <<'PY'
import json, os, uuid
import requests

base = os.environ["BASE_URL"]
admin_user = os.environ["ADMIN_USER"]
admin_pass = os.environ["ADMIN_PASS"]

def show(label, resp):
    ctype = resp.headers.get("content-type", "")
    body = resp.text[:180].replace("\n", " ")
    if "application/json" in ctype:
        try:
            data = resp.json()
            body = {k: ("[redacted]" if k in {"token", "api_key"} else v) for k, v in data.items()}
        except Exception:
            pass
    print(json.dumps({"label": label, "status": resp.status_code, "body": body}, sort_keys=True))

admin = requests.Session()
r = admin.post(f"{base}/PSSM_GREMLIN/api/auth/login", json={"username": admin_user, "password": admin_pass}, timeout=10)
show("admin_login", r)
r.raise_for_status()
admin_h = {"Authorization": "Bearer " + r.json()["token"]}

name = "bancheck_" + uuid.uuid4().hex[:8]
pw = "Pw_" + uuid.uuid4().hex + "!aA1"
r = admin.post(
    f"{base}/PSSM_GREMLIN/api/auth/admin/users",
    headers=admin_h,
    json={"username": name, "email": name + "@audit.local", "password": pw, "affiliation": "audit", "is_admin": False},
    timeout=10,
)
show("create_user", r)

r = admin.get(f"{base}/PSSM_GREMLIN/api/auth/admin/users", headers=admin_h, timeout=10)
r.raise_for_status()
user_id = next(u["id"] for u in r.json()["users"] if u["username"] == name)

limited = requests.Session()
r = limited.post(f"{base}/PSSM_GREMLIN/api/auth/login", json={"username": name, "password": pw}, timeout=10)
show("pre_ban_login", r)
r.raise_for_status()
limited_h = {"Authorization": "Bearer " + r.json()["token"]}

r = limited.post(f"{base}/PSSM_GREMLIN/api/auth/me/api-key", headers=limited_h, timeout=10)
show("pre_ban_api_key", r)
api_key = r.json().get("api_key") if r.status_code == 201 else None

r = admin.put(f"{base}/PSSM_GREMLIN/api/auth/admin/users/{user_id}", headers=admin_h, json={"user_status": "banned"}, timeout=10)
show("ban_user", r)
show("post_ban_login", requests.post(f"{base}/PSSM_GREMLIN/api/auth/login", json={"username": name, "password": pw}, timeout=10))
show("post_ban_old_bearer_me", requests.get(f"{base}/PSSM_GREMLIN/api/auth/me", headers=limited_h, timeout=10))
if api_key:
    show("post_ban_api_key_me", requests.get(f"{base}/PSSM_GREMLIN/api/auth/me", headers={"X-API-Key": api_key}, timeout=10))
PY
```

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
- CSRF is mitigated: state-changing endpoints require a Bearer token in the
  `Authorization` header (browser same-origin policy prevents cross-origin
  requests from setting custom headers).  The `HttpOnly` cookie is used for
  read-only page navigations only.

### Redis

- Set `REDIS_PASSWORD` in production to enable Redis authentication.
- Redis is on an internal Docker network; do not expose its port publicly.

### Data

- User passwords are hashed with `werkzeug.security.generate_password_hash` (pbkdf2:sha256).
- User database (`users.sqlite3`) and task database (`pssm_gremlin.sqlite3`) are
  stored under `SERVER_DIR`, not in the web root.
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
