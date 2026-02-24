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
sudo apt-get install -y docker.io docker-compose-plugin ncbi-blast+
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
sudo chown -R revodesign:revodesign /srv/revodesign
```

Notes:

- Do not run the GREMLIN runner as root.
- Configure non-root runner identity via `RUNNER_UID`/`RUNNER_GID` or `RUNNER_USERNAME`/`RUNNER_GROUP`.

## 3. Configure Environment Files

Create production env file:

```bash
cp server/.env.example server/.env.production
```

Test-only env file:

- `server/.env.test` is for local/test validation.
- Do not use `.env.test` on production hosts.

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
| `DB_PATH` | SQLite path for task tracking. |
| `DB_UNIREF30` | UniRef30 prefix path. |
| `DB_UNIREF90` | UniRef90 BLAST prefix path. |
| `USERS_FILE` | Basic-auth credential file path. |
| `RUNNER_UID`, `RUNNER_GID` | Runner UID/GID (non-root required). |
| `DOCKER_GID` | Group ID of Docker socket on host. |
| `NPROC` | CPU threads passed to runner. |
| `WORKER_CONCURRENCY` | Celery worker concurrency. |
| `GUNICORN_WORKERS` | Gunicorn worker count. |
| `PORT` | Public HTTP port. |
| `PUBLIC_DASHBOARD` | `false` by default; scopes task visibility to owner unless admin. |
| `ADMIN_USERS` | Comma-separated admin usernames for cross-user management. |

## 4. Configure Basic Auth Users

Create the users file referenced by `USERS_FILE`.

Format:

```text
# comment lines are allowed
username:password
admin:strong_admin_password
```

Protect this file with strict permissions.

## 5. Build and Run

### Recommended helper script

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

### Upload via curl (with basic auth)

```bash
curl -u "username:password" \
  -X POST \
  -F "file=@/path/to/input.fasta" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/post"
```

### Batch upload via curl

```bash
for f in *.fasta; do
  curl -u "username:password" -X POST -F "file=@${f}" \
    "http://<server-ip>:<port>/PSSM_GREMLIN/api/post"
done
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

## 9. Operations Notes

- Restrict Docker socket access to trusted operators only.
- Keep `PUBLIC_DASHBOARD=false` for private per-user isolation.
- Regularly back up sqlite and result archives.
- If a task is deleted, result artifacts are removed, but sqlite record and uploaded source file remain for debugging.
