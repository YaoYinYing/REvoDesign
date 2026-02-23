# PSSM GREMLIN Server (Production-First Guide)

This server is intended to run with Docker Compose in production. Native/manual deployment is intentionally not documented here.

## Sequence database

1. Prepare the sequence databases required by the run script :

   **UniRef90**

   ```shell
   # stole from alphafold, DeepMind
   ROOT_DIR="${DOWNLOAD_DIR}/uniref90"
   SOURCE_URL="https://ftp.ebi.ac.uk/pub/databases/uniprot/uniref/uniref90/uniref90.fasta.gz"
   BASENAME=$(basename "${SOURCE_URL}")

   mkdir --parents "${ROOT_DIR}"
   aria2c "${SOURCE_URL}" --dir="${ROOT_DIR}"
   pushd "${ROOT_DIR}"
   gunzip "${ROOT_DIR}/${BASENAME}"
   popd

   ```

   **Note** that for `psiblast`, the `uniref90` database should be formated using the `makeblastdb` tool from BLAST+. this can be done by whether the `run_docker.py` (see bellow) or call your own `makeblastdb` command`.

   **UniRef30**

   ```shell
   # stole from alphafold, DeepMind
   ROOT_DIR="${DOWNLOAD_DIR}/uniref30"
   SOURCE_URL="https://wwwuser.gwdg.de/~compbiol/uniclust/2023_02/UniRef30_2023_02_hhsuite.tar.gz"
   BASENAME=$(basename "${SOURCE_URL}")

   mkdir --parents "${ROOT_DIR}"
   aria2c "${SOURCE_URL}" --dir="${ROOT_DIR}"
   tar --extract --verbose --file="${ROOT_DIR}/${BASENAME}" \
   --directory="${ROOT_DIR}"
   rm "${ROOT_DIR}/${BASENAME}"
   ```

2. After that, you should format blast database this with calling the installed `makeblastdb` tool on machine:

   ```bash
   makeblastdb -in uniref90.fasta -dbtype prot -parse_seqids -out uniref90
   ```

### Environment variables

Key options are controlled from `server/.env`:

| Variable | Purpose |
| --- | --- |
| `PSSM_GREMLIN_SERVER_DIR` | Host directory where uploads, states, and results are stored. Mounted into the containers at the same path and created automatically if missing. |
| `PSSM_GREMLIN_LOG_DIR` | Host directory that stores persistent Gunicorn and Celery logs. Bind-mounted into the containers at the same path. |
| `PSSM_GREMLIN_DB_PATH` | Absolute path to the SQLite job-tracking database file. Create the file or its parent directory on the host; Compose bind-mounts the file so the host retains ownership and backups. |
| `PSSM_GREMLIN_DB_UNIREF30`, `PSSM_GREMLIN_DB_UNIREF90` | Absolute paths/prefixes to the sequence databases. They are mounted read-only into both containers and passed to the runner as `-U`/`-u`. |
| `PSSM_GREMLIN_USERS_FILE` | Path to the HTTP Basic Auth credentials file. |
| `PSSM_GREMLIN_RUNNER_UID`, `PSSM_GREMLIN_RUNNER_GID` | Required UID/GID pair for the GREMLIN runner container. Both must point to a dedicated non-root account; the server refuses to start if they are missing or set to `root` to avoid root-owned artifacts. |
| `DOCKER_GID` | Supplementary group id injected into `web`/`worker` so they can access `/var/run/docker.sock` (for example `$(stat -Lc '%g' /var/run/docker.sock)` on Linux). |
| `PSSM_GREMLIN_NPROC`, `PSSM_GREMLIN_WORKER_CONCURRENCY`, `PSSM_GREMLIN_GUNICORN_WORKERS` | Performance knobs for the runner, Celery worker, and Gunicorn respectively. |
| `PSSM_GREMLIN_REDIS_URL` | Broker/backend URL used by Celery. Defaults to the bundled Redis service. |
| `PSSM_GREMLIN_PORT` | External HTTP port exposed by the `web` service. |
| `PUBLIC_DASHBOARD` | Optional dashboard visibility switch. Default `false` enforces per-user isolation (only task owner can list/view/download/cancel). Set `true` to expose all tasks to any authenticated user. |
| `ADMIN_USERS` | Comma-separated Basic Auth usernames treated as server admins (default `admin`). Admins can batch-delete tasks and can delete any task regardless of owner. |

Every other variable shown in `.env.example` is optional and has a sensible default.

If you prefer naming the dedicated system account explicitly inside the containers, `RUNNER_USERNAME` and `RUNNER_GROUP` may be set instead of the UID/GID pair. As with the numeric identifiers, both must refer to non-root identities.

## Runtime env-file isolation

The restart helpers support isolated env files:

```bash
# explicit env file (recommended)
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh

# fallback behavior when REVODESIGN_SERVER_ENV is not set:
# 1) use server/.env.production if it exists
# 2) otherwise use server/.env
```

`server/.env.test` is kept for test-only/local validation.

## 0. Prepare BLAST+ binary (for database formatting)

Install NCBI BLAST+ so `makeblastdb` is available.

Ubuntu example:

```bash
sudo apt-get update
sudo apt-get install -y ncbi-blast+
makeblastdb -version
```

## 1. Prepare sequence databases

Create database folders and format UniRef90 for PSI-BLAST.


Set `DB_UNIREF90` to the formatted DB prefix (`.../uniref90`, without extension).
Set `DB_UNIREF30` to your UniRef30 prefix path.

## 2. Create production server-role user (Ubuntu example)

Create a dedicated non-root account for server operations.

```bash
sudo adduser --system --group --no-create-home --shell /usr/sbin/nologin revodesign
sudo usermod -aG docker revodesign

sudo mkdir -p /srv/revodesign/server
sudo mkdir -p /srv/revodesign/logs
sudo chown -R revodesign:revodesign /srv/revodesign
```

Use a non-root UID/GID in `.env.production` for `RUNNER_UID` and `RUNNER_GID`.

## 3. Configure `.env`

Create production env file from template:

```bash
cp server/.env.example server/.env.production
```

Update required values in `server/.env.production`:

Test env file:

- `server/.env.test` is for local/test stack only.
- Do not use `.env.test` on production hosts.

## 4. Build/start using Docker Compose and restart scripts

### Recommended helper script

```bash
# create/patch env file values like DOCKER_GID
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh setup

# full cycle (down + build + up)
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh restart

# lifecycle subcommands
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh build
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh up
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh down
```

For local server test runs:

```bash
REVODESIGN_SERVER_ENV=server/.env.test bash server/run/restart_pssm_flask.sh restart
```

### Equivalent Docker Compose commands

```bash
docker compose -f server/docker-compose.yml --env-file server/.env.production down
docker compose -f server/docker-compose.yml --env-file server/.env.production --profile runner build runner
docker compose -f server/docker-compose.yml --env-file server/.env.production build web worker
docker compose -f server/docker-compose.yml --env-file server/.env.production up -d redis web worker
```

### Zero-downtime gunicorn reload

```bash
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/hot_fix.sh
```

## 5. Optional public access setup

### Option A (simple): Cloudflare Tunnel

Use Cloudflare Tunnel to expose the private service without opening inbound ports on the host.

High-level flow:

1. Install and authenticate `cloudflared`.
2. Create a tunnel and bind DNS record.
3. Route external host to `http://127.0.0.1:<PORT>`.

Reference: [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/).

### Option B (advanced): NGINX reverse proxy

Use NGINX when you need full reverse-proxy control (TLS termination, rate limiting, custom headers, etc.).

High-level flow:

1. Install NGINX and certificates.
2. Configure upstream to `127.0.0.1:<PORT>`.
3. Enforce HTTPS and preserve `Authorization` header.
4. Reload NGINX and validate authenticated routes.

`server/nginx_sites/REvoDesign_PSSM_GREMLIN.app` can be used as a starting point.

## Operations notes

- The web and worker containers require Docker socket access to launch runner containers.
- Keep Docker socket permissions restricted.
- Keep `users.txt` protected; Basic Auth credentials are security-critical.
- For production isolation, keep `PUBLIC_DASHBOARD=false` unless cross-user visibility is explicitly required.
