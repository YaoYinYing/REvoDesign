# PSSM/GREMLIN Server

The PSSM/GREMLIN compute service that REvoDesign uses to build position-specific
scoring matrices (PSI-BLAST against UniRef90) and GREMLIN co-evolution couplings
(HHblits against UniRef30 + a TensorFlow 1.x GREMLIN implementation).

This document has two parts:

1. **Current documentation** (this part) — status, open access, license,
   dependency versions, installation checks, example data, FAQ, and the
   maintenance/update plan for the archived server.
2. **[Historical content](#historical-content--archived-deployment-guide-commit-d167adecd9ff)**
   — the original `server/README.md`, preserved below the marker. It documents
   the last state of the service and is no longer maintained.

The code in `server/` is a faithful restore of revision
[`d167adecd9ff5821e1e9783b953edde78942d5dd`](https://github.com/YaoYinYing/REvoDesign/tree/d167adecd9ff5821e1e9783b953edde78942d5dd/server)
(2026-08-10), the last commit before the service was split out of this
repository. Feature development of the server line continues in the standalone
[REvoCompute](https://github.com/YaoYinYing/REvoCompute) project, whose
public instance is [revocompute.yaoyy.moe](https://revocompute.yaoyy.moe/compute/dashboard).

## Open-Access PSSM/GREMLIN Service

A publicly reachable instance is operated for academic use, so no one has to run
the service locally to use REvoDesign's PSSM/GREMLIN workflow:

| Item | Value |
| --- | --- |
| URL | <https://revodesign-demo.yaoyy.moe/PSSM_GREMLIN> |
| Login page | <https://revodesign-demo.yaoyy.moe/PSSM_GREMLIN/login> |
| Username | `academic_users` |
| Password | `6NrueDpvHKUp` |
| Dashboard | <https://revodesign-demo.yaoyy.moe/PSSM_GREMLIN/dashboard> |
| Task submission | <https://revodesign-demo.yaoyy.moe/PSSM_GREMLIN/create_task> |

This is a shared **guest**-role account:

- Sign in at the login page, then use **Create Task** to upload a `.fasta`
  sequence and download the result archive from the dashboard.
- The account is shared, so its dashboard lists tasks submitted by other users of
  the same account, and because task IDs, the 5-active-task cap, and downloads
  are scoped to the account rather than to a person, everyone using
  `academic_users` shares that single task namespace.
- Guest accounts cannot delete tasks, generate API keys, or change the account
  password, so the account must not be used for private or unpublished
  sequences you are not willing to see processed by a third-party host.
- Self-registration is enabled on this instance if you need an isolated account
  (CAPTCHA + email verification) — see [FAQ](#faq).
- The same sequence can be submitted through the REST API with a Bearer token
  obtained from `/PSSM_GREMLIN/api/auth/login`; see the
  [historical guide](#historical-content--archived-deployment-guide-commit-d167adecd9ff)
  for the endpoint list.

If the shared instance is unavailable, every part of the service can be rebuilt
from this directory: the deployment procedure, container images, pinned
dependency files, and the full test suite are all in-tree (see
[Installation and Verification Tests](#installation-and-verification-tests)).

## License

The server is distributed under the **GNU General Public License, version 3
only** (`GPL-3.0-only`), identical to the rest of REvoDesign:

- Repository license text: [`LICENSE`](../LICENSE) (GPL-3.0).
- Package declaration: `license = { text = "GPL-3.0-only" }` in
  [`server/pyproject.toml`](pyproject.toml).
- Every server-owned Python module, script, and test (40 files) carries the SPDX
  header `# SPDX-License-Identifier: GPL-3.0-only`; the three shell entry points
  (`REvoDesign_PSSM_GREMLIN.sh`, `run/restart_pssm_flask.sh`,
  `tests/run_full_stack_test.sh`) are covered by the same license without a
  per-file header.
- The GREMLIN runner script `server/scripts/GREMLIN_TFv1.py` and the
  `server/scripts/` helpers are covered by the same license; the GREMLIN method
  itself follows Kamisetty, Ovchinnikov & Baker, *PNAS* 110:15674 (2013).
- Container images built from this directory (`docker/server/Dockerfile`,
  `docker/runner/Dockerfile`) are derivative works and therefore also
  GPL-3.0-only.

## Dependencies and Versions

The service has two dependency layers with different reproducibility
properties: a small Python web/worker package, and a heavyweight scientific
runner environment.

### Web, worker, and maintenance processes (Python)

Declared in [`server/pyproject.toml`](pyproject.toml), `requires-python = ">=3.10"`:

| Package | Declared constraint | Reference resolution |
| --- | --- | --- |
| `APScheduler` | `>=3.11,<4` | 3.11.3 |
| `celery[redis]` | `>=5.3` | 5.3.4 (`redis` 4.6.0) |
| `docker` | `>=7.1` | 7.1.0 |
| `Flask` | `>=3.1` | 3.1.3 |
| `gunicorn` | `>=25.1` | runtime-only; installed by the server image, absent from the local test environment |
| `pydantic` | `>=2.0` | 2.13.4 |
| `SQLAlchemy` | `>=2.0` | 2.0.46 |
| `werkzeug` | unpinned | 3.1.8 |
| `itsdangerous` | unpinned | 2.2.0 |
| `resend` (extra `[resend]`) | `>=2.0` | optional; only for email delivery |
| `pytest`, `pytest-mock`, `pytest-cov`, `requests` (extra `[test]`) | `>=8`, `>=3.14`, `>=6`, `>=2.33` | 8.3.3 / 3.14.0 / 6.0.0 / 2.34.2 |

The right-hand column is one working resolution on Python 3.13; the declared
constraints are deliberately ranges. Either install the ranges as written or
freeze a resolution (`pip freeze`) for a long-lived deployment.

### GREMLIN runner (conda)

The runner image is the scientific dependency layer and is deliberately separate
from the web/worker package. Exact pins live in
[`server/env/GREMLIN.yml`](env/GREMLIN.yml) (`python=3.6.13`, `tensorflow=1.13.1`,
`biopython=1.78`, `blast=2.13.0`, `hhsuite=3.3.0`, `hmmer=3.3.2`,
`numpy=1.19.2`, `scipy=1.5.2`, `pandas=1.1.5`, `matplotlib=3.3.4`; channels
`defaults`, `conda-forge`, `bioconda`). These are fully pinned and reproducible;
the older versions are required by TensorFlow 1.13 and must not be loosened.

### Service images and host prerequisites

| Component | Version source |
| --- | --- |
| Server image base | `python:3.12-slim` (`docker/server/Dockerfile`) |
| Runner image base | `condaforge/mambaforge`, forced `--platform=linux/amd64` (`docker/runner/Dockerfile`) |
| Redis | `redis:7.2-alpine` |
| Nginx gateway | `nginx:1.28-alpine` |
| Host tooling | Docker Engine 24+ with the Compose plugin, NCBI BLAST+ (`makeblastdb`), `aria2` for the reference databases |

Reproducibility note: the two Docker base images `python:3.12-slim` and
`condaforge/mambaforge` are floating tags. Pin them by digest
(`image@sha256:…`) if a byte-identical rebuild years from now matters.

## Installation and Verification Tests

The test suite is restored unchanged from revision `d167ade`; nothing was
modified to make it pass. Three levels are available.

### 1. Server-owned test suite (no Docker required)

```bash
# from the repository root
pip install -e "server/[test]"
make -C server test          # pytest, excluding the Docker-dependent modules
make -C server test-cov      # same selection, with coverage
```

Covers configuration parsing, authentication and token handling, admin user
management, API-key restrictions, rate limiting, task lifecycle and race
conditions, process isolation, retention cleanup, database backup, log rotation,
download offload, and runner-script static checks (17 test modules in
`server/tests/`).

Observed result for the restored tree on 2026-11-11 (Python 3.13, macOS):
`282 passed` in under a minute for `make -C server test`.

### 2. Docker-dependent tests (Linux host with a reachable Docker daemon)

```bash
make -C server test-all               # includes tests/test_docker.py
make -C server test-docker-compat     # runner image + process isolation
make -C server test-docker-full-stack # end-to-end stack on a temporary port
```

`make -C server test-docker-full-stack` is the authoritative end-to-end check:
it builds both images, rebuilds the miniature UniRef30/UniRef90 databases inside
the runner, starts the Compose stack on a free port, submits
`tests/data/msa/2KL8.fasta`, waits for the GREMLIN task to finish, then asserts
the ZIP content, byte-range download support, and the expected
`gremlin_res/*.mrf.pkl` and `pssm_msa/2KL8_ascii_mtx_file` members.

### 3. Live-service smoke check

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  "https://revodesign-demo.yaoyy.moe/PSSM_GREMLIN/login"        # 200

curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"username":"academic_users","password":"6NrueDpvHKUp"}' \
  "https://revodesign-demo.yaoyy.moe/PSSM_GREMLIN/api/auth/login"   # Bearer token
```

A successful login response is `{"token": "...", "username": "academic_users"}`;
that token authorizes `POST /PSSM_GREMLIN/api/post` (multipart `file=`), task
status polling, cancellation, and result download.

## Example Datasets

| Dataset | Path | Purpose |
| --- | --- | --- |
| `2KL8` single-sequence query (79 aa) | [`tests/data/msa/2KL8.fasta`](../tests/data/msa/2KL8.fasta) | Primary query for every validation command and for the full-stack smoke test |
| `2KL8` UniRef90 subset | [`tests/data/msa/2KL8_blast.fasta`](../tests/data/msa/2KL8_blast.fasta) | Source for the miniature PSI-BLAST database (`makeblastdb`) |
| `2KL8` HHblits alignment | [`tests/data/msa/2KL8.i90c75_aln.fas`](../tests/data/msa/2KL8.i90c75_aln.fas) | Source for the miniature UniRef30 HH-suite database |
| Miniature UniRef30/UniRef90 mock DBs | `tests/data/msa/miniuc/` (git-ignored, rebuilt locally) | Tiny databases used by the Docker tests; build recipe in [`tests/data/msa/README.md`](../tests/data/msa/README.md), or let `make -C server test-docker-full-stack` build them inside the runner |
| `Sli_S4` (266 aa) | [`tests/data/fasta/Sli_S4.fasta`](../tests/data/fasta/Sli_S4.fasta) | Plugin-side FASTA fixture, also usable as an upload example |
| T5aH2 tutorial inputs | [T5aH2.fasta](https://github.com/YaoYinYing/REvoDesignTutorial/raw/refs/heads/main/T5aH2.fasta), [T5aH2_PSSM_ascii_mtx_file](https://github.com/YaoYinYing/REvoDesignTutorial/raw/refs/heads/main/T5aH2_PSSM_ascii_mtx_file) | Real-case sequence and the resulting PSSM used by the REvoDesign tutorial |
| T5aH2 full PSSM/GREMLIN archive | [T5aH2_wt_PSSM_GREMLIN_results.zip](https://github.com/YaoYinYing/REvoDesignTutorial/releases/download/T5aH2/T5aH2_wt_PSSM_GREMLIN_results.zip) (~183 MB) | Reference output of one complete server run, for output-format comparison |

Upload requirements enforced by the API: a `.fasta` extension, plain-text
content whose first non-blank line starts with `>`, and at most 16 MiB
(`MAX_CONTENT_LENGTH` in `pssm_gremlin_server/pssm_gremlin.py`). Lenient
lowercase/odd-character FASTA input is normalized by
`server/scripts/fasta_lower_char_rm.py` inside the runner.

## FAQ

**Do I need to deploy the server to use REvoDesign?**
No. Use the [open-access instance](#open-access-pssmgremlin-service). Deploy
locally only for private sequences, for throughput, or for long-term
independence from a hosted service.

**How long does one calculation take, and what limits apply?**
Runtime scales with the number of homologous sequences found for the query;
small single-domain queries finish in minutes, large multi-domain proteins take
substantially longer. Per user: at most **5** pending/running tasks
(`MAX_ACTIVE_TASKS_PER_USER`) and **30** upload submissions per hour. Login is
limited to 5 attempts/minute and self-registration to 3/hour per IP.

**Uploading the same FASTA twice returns the same task. Why?**
The task ID is `md5("<owner>:<content-md5>")`, so identical content from the same
account maps to the same task instead of duplicating work; the API redirects to
the existing task instead of enqueuing a new one.

**Why does `POST /PSSM_GREMLIN/api/post` return 403 "Bearer token required"?**
State-changing endpoints reject cookie-only authentication (CSRF defense). Log
in via `POST /PSSM_GREMLIN/api/auth/login` and send
`Authorization: Bearer <token>`. Browser page navigation keeps using the
`HttpOnly` cookie.

**Registration returns 403.**
Self-registration needs `ENABLE_REGISTER=true` *and* a configured email backend
(SMTP or Resend); otherwise an administrator must create the account through
`POST /PSSM_GREMLIN/api/auth/admin/users`. The public instance has registration
enabled.

**Why can't the shared account delete tasks or create an API key?**
`academic_users` is a `guest`-role account. Guests can sign in, submit, monitor,
download, and cancel their tasks, but deletion, API-key management, and password
changes are refused with "Guest accounts cannot perform this action".

**"Uploaded file does not appear to be a valid FASTA file".**
The first non-blank line must begin with `>`, and the extension must be
`.fasta`. Binary uploads are rejected separately.

**Tasks fail with `PermissionError(13, 'Permission denied')` in a local deployment.**
The worker cannot reach the Docker socket. Run deployment through
`server/run/restart_pssm_flask.sh`, which auto-detects `DOCKER_GID`, and compare
with `docker exec <project>-worker-1 ls -ln /var/run/docker.sock`. On Docker
Desktop/OrbStack for macOS the bind-mounted socket usually appears as group `0`.

**"Task queue unavailable — please try again later" (HTTP 503).**
The worker could not reach Redis/Celery. Check the `redis` service and
`celery-worker.log`.

**Result downloads fail or truncate behind a proxy.**
In Compose production, Nginx serves the ZIP bytes after Flask authorizes the
request with an internal `X-Accel-Redirect` (`RESULT_DOWNLOAD_MODE=nginx`); use
`RESULT_DOWNLOAD_MODE=flask` only when running the Flask container directly.
Byte-range requests are supported, so interrupted downloads can resume.

**Do results expire?**
Only if `RESULT_RETENTION_DAYS` is set; otherwise result directories are kept.
Deleted tasks lose their artifacts but keep their audit row in SQLite.

**Can the server run on macOS/Windows for production?**
The Compose stack runs on Docker Desktop for development, but the runner image
is forced to `linux/amd64` and the documented production path assumes a Linux
host with a real Docker socket. Deploy on Linux for anything long-lived.

**Where did `docs/dev-guide/server.md` go?**
It was removed from this repository in commit `3cb7db2a` together with the
standalone server split. The complete text at the archived revision is
[`docs/dev-guide/server.md@d167ade`](https://github.com/YaoYinYing/REvoDesign/blob/d167adecd9ff5821e1e9783b953edde78942d5dd/docs/dev-guide/server.md).

## Maintenance and Update Plan

**Status of this directory.** `server/` is an archived, build-and-run-capable
snapshot pinned at `d167adecd9ff5821e1e9783b953edde78942d5dd`. It is kept so the
service described in the manuscript stays reproducible and deployable, and so the
open-access instance has a public source.

- **No new features here.** Feature development of the server line continues in
  [REvoCompute](https://github.com/YaoYinYing/REvoCompute) (also GPL-3.0),
  which supersedes this Flask + Celery + Docker-runner stack.
- **Fixes still applied here:** security-relevant corrections (credential
  handling, authentication, path traversal, container exposure) and
  build/runtime breakages caused by external changes. These land as ordinary
  commits on `main`, so any deployment remains reproducible from a commit hash.
- **Dependency handling:** the runner environment is fully pinned and stays
  pinned (TensorFlow 1.13 requires the old stack). Web/worker dependencies keep
  their declared lower bounds; a security advisory affecting them is handled
  either by raising the bound here or, when that is not possible without
  behavioural change, by documenting the mitigation in this file. The two
  floating base images are the known reproducibility gap — pin them by digest
  for archival builds.
- **Change validation:** `make -C server test` must keep passing, and the
  Docker-dependent suites (`test-docker-compat`, `test-docker-full-stack`) must
  pass on a Linux host before a change to this directory is released.
- **Issue intake:** bugs and questions via the repository
  [issue tracker](https://github.com/YaoYinYing/REvoDesign/issues) (see
  `.github/ISSUE_TEMPLATE`); security reports privately via
  [GitHub Security Advisories](https://github.com/YaoYinYing/REvoDesign/security/advisories/new)
  per [`SECURITY.md`](../SECURITY.md).
- **Service continuity:** the [open-access instance](#open-access-pssmgremlin-service)
  is the supported public endpoint. If it is ever withdrawn, the replacement is
  announced in `CHANGELOG.md` and in this file, and the local deployment path in
  the historical guide remains the documented fallback — the GREMLIN runner
  image can be built once and retained, so the calculation itself depends on no
  external hosted service.
- **Review cadence:** this status block and the version tables are re-checked at
  each repository release (see `CHANGELOG.md`). Long-term maintenance beyond
  best-effort security and buildability is not committed to; sustained
  development happens in the successor project.

## Historical content — archived deployment guide (commit `d167adecd9ff`)

> **Everything below this marker is historical.** It is the complete
> `server/README.md` as of commit
> [`d167adecd9ff5821e1e9783b953edde78942d5dd`](https://github.com/YaoYinYing/REvoDesign/tree/d167adecd9ff5821e1e9783b953edde78942d5dd)
> (2026-08-10), the last revision before the service was split into REvoCompute.
> It is preserved as a record of how the deployed service was configured and
> operated; only headings were demoted one level and site-specific credentials
> were replaced with placeholders. Where it disagrees with the sections above,
> the sections above win.
>
> Notes when reading it:
>
> - It describes the state of the service at that commit, including production
>   paths, image names, and operational details specific to the deployment of the
>   time; these do not apply to a new deployment as-is.
> - `docs/dev-guide/server.md` (referenced twice below) was deleted from this
>   repository in `3cb7db2a`; read it at commit `d167ade` instead.
> - `server/.env.example`, `server/docker-compose.yml`, `server/docker/`,
>   `server/run/`, `server/scripts/`, `server/tests/` and `server/env/` are all
>   present in this tree, so the procedure below can still be executed as
>   written.
> - Copy `.env.example` to `.env.local` (development) or `.env.production`
>   (production); both are git-ignored and contain secrets.

### PSSM GREMLIN Server

The server is a Docker-deployed Flask + Celery + Docker-runner web service for
GREMLIN co-evolution analysis.

#### Docker Deployment

This guide covers both local-image development (`--mode=dev`) and
published-image production (`--mode=prod`). Native/manual production deployment
is intentionally excluded.

#### Overview

The server stack contains:

- `web`: Flask + Gunicorn API/UI service
- `maintenance`: APScheduler process for registration digests, result cleanup,
  database backups, and log rotation
- `worker`: Celery worker for background jobs
- `redis`: Celery broker/backend
- `runner` image: GREMLIN/PSSM execution container launched by `worker`

Scientific Python dependencies used by GREMLIN scripts belong to the runner's
`env/GREMLIN.yml`; they are not installed into the web and worker package.

Periodic jobs follow this package boundary:

```text
pssm_gremlin_server/maintenance/
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

#### 0. Prerequisites

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

#### 1. Prepare Sequence Databases

You need UniRef90 (for PSI-BLAST) and UniRef30 (for HH-suite workflow).

##### 1.1 UniRef90 download and extraction

```bash
DOWNLOAD_DIR=/srv/revodesign/databases
ROOT_DIR="${DOWNLOAD_DIR}/uniref90"
SOURCE_URL="https://ftp.ebi.ac.uk/pub/databases/uniprot/uniref/uniref90/uniref90.fasta.gz"
BASENAME=$(basename "${SOURCE_URL}")

mkdir -p "${ROOT_DIR}"
aria2c "${SOURCE_URL}" --dir="${ROOT_DIR}"
gunzip "${ROOT_DIR}/${BASENAME}"
```

##### 1.2 Build BLAST database for UniRef90

```bash
cd "${ROOT_DIR}"
makeblastdb -in uniref90.fasta -dbtype prot -parse_seqids -out uniref90
```

Use the BLAST prefix path (`.../uniref90`) as `DB_UNIREF90`.

##### 1.3 UniRef30 download and extraction

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

#### 2. Create a Dedicated Server User (Recommended)

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

#### 3. Configure Environment Files

Create production env file:

```bash
cp server/.env.example server/.env.production
```

##### Env-file isolation

All restart helpers support `REVODESIGN_SERVER_ENV`:

```bash
REVODESIGN_SERVER_ENV=server/.env.local bash server/run/restart_pssm_flask.sh restart --mode=dev
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh restart --mode=prod
```

When `REVODESIGN_SERVER_ENV` is unset, the helper uses
`server/.env.production` and fails clearly when that file is absent.

##### Required/important variables

| Variable | Purpose |
| --- | --- |
| `SERVER_IMAGE`, `RUNNER_IMAGE` | Image names built locally in dev mode or pulled in prod mode. Production must use full published Docker Hub references. |
| `SERVER_DIR` | Required host root shared by web and worker for uploads, task SQLite, and result folders. Never store the user database here. |
| `RUNNER_HOST_ROOT` | Host root allowed for Docker runner bind mounts (default: parent of `SERVER_DIR`). |
| `LOG_DIR` | Host directory for Gunicorn, Celery, and `maintenance.log`. |
| `DB_UNIREF30` | Required UniRef30 prefix path. |
| `DB_UNIREF90` | Required UniRef90 BLAST prefix path. |
| `ADMIN_USERS` | Required comma-separated bootstrap-administrator usernames. On an empty user database, the restart script creates each account and prints a distinct generated password; afterward, database roles control authorization. |
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

##### Authentication storage: host path versus container path

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

##### CDN IP header reference

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

#### 4. Authentication

The server uses Bearer-token authentication (replaces the old HTTP Basic Auth + `users.txt` model).

##### How auth works

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

##### Gunicorn `--preload`

Gunicorn workers are started with `--preload` so the auth secret key is
generated once in the arbiter before forking.  Without this, each worker
independently generates its own signing key, making tokens from one worker
fail validation on another.

The key is intentionally ephemeral. Restarting the web service logs users out
and invalidates outstanding verification and password-reset links.

##### First run

If the user database is empty, every username in the required `ADMIN_USERS`
list is created automatically:

- Passwords: generated separately and printed once by
  `restart_pssm_flask.sh`. Change each after first login.

Bootstrap passwords must not be stored in the env file. They are transient
first-boot values supplied by the restart script only.

Set `ENABLE_REGISTER=true` and configure either SMTP or Resend to allow
self-registration. Registration requires full name, affiliation, academic
position, and PI name. These fields appear on the user's profile page and in
the admin user-control system. Users receive a verification email and must be
verified before use. Without a working email backend, use the admin API to
create accounts.

##### API authentication

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

##### Admin user management

```bash
# Admin creates a new user (requires admin token)
curl -X POST -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","email":"user@example.com","password":"...","role":"user"}' \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/auth/admin/users"
```

`role` may be `admin`, `user`, or `guest` and is the sole authorization
authority. Server setup creates the current user schema directly and does not
alter older database layouts.

Admins cannot ban or delete their own account.  Direct self-ban/self-delete
requests return HTTP 400, and batch Disable/Delete skips the acting admin while
still applying the requested action to other selected users.

The dashboard header also links administrators to `/PSSM_GREMLIN/logs`. That
standalone page loads only the selected active Gunicorn access, Gunicorn error,
Celery worker, or maintenance log and streams it incrementally. Its lazy
file tree lists rotated ZIP archives under those same four logs and permits
individual downloads; arbitrary filesystem paths are not exposed.

##### API keys (programmatic access)

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

#### 5. Build and Run

##### Recommended helper script

No sudo required.

```bash
# initialize the env file and print detected Docker socket group
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh setup

# development: down + local build using host UID/GID + up
REVODESIGN_SERVER_ENV=server/.env.local bash server/run/restart_pssm_flask.sh restart --mode=dev

# production: down + pull configured Docker Hub images + up without building
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh restart --mode=prod

# subcommands
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh build
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh up
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh down
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh reload
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

Create a writable `AUTH_DIR` before the first start. The web process creates
`${AUTH_DIR}/users.sqlite3` with the current schema. Existing databases must
already match that schema; server setup does not migrate them.

##### Equivalent Docker Compose commands

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

##### Zero-downtime Gunicorn reload

```bash
REVODESIGN_SERVER_ENV=server/.env.production bash server/run/restart_pssm_flask.sh reload
```

#### 6. Usage

##### Create task page

- `http://<server-ip>:<port>/PSSM_GREMLIN/create_task`
- Upload ``.fasta`` files via the **Choose File** button or by **dragging and dropping** a file anywhere on the card.
- An optional sequence editor lets you paste raw protein sequences as text instead of uploading a file.

##### Dashboard

- `http://<server-ip>:<port>/PSSM_GREMLIN/dashboard`

##### Upload via curl (with token auth)

```bash
# Obtain a token first (see Authentication section above)
TOKEN="<your-token>"

curl -H "Authorization: Bearer ${TOKEN}" \
  -X POST \
  -F "file=@/path/to/input.fasta" \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/post"
```

##### Batch upload via curl

```bash
for f in *.fasta; do
  curl -H "Authorization: Bearer ${TOKEN}" -X POST -F "file=@${f}" \
    "http://<server-ip>:<port>/PSSM_GREMLIN/api/post"
done
```

##### Delete one task (single-task API)

```bash
TASK_MD5="<task-md5>"
curl -H "Authorization: Bearer ${TOKEN}" -X DELETE \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/delete/${TASK_MD5}"
```

##### Delete multiple tasks (batch API)

```bash
curl -H "Authorization: Bearer ${TOKEN}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"md5sums":["<task-md5-a>","<task-md5-b>"]}' \
  "http://<server-ip>:<port>/PSSM_GREMLIN/api/delete"
```

#### 7. Task States

Current server states:

- `pending`
- `running`
- `packing results`
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

#### 8. Public Access

Docker Compose publishes the Nginx `gateway` service. The Flask/Gunicorn `web`
service is internal-only. Nginx proxies application requests and serves result
ZIP bytes after Flask authorizes the request with an internal
`X-Accel-Redirect`. The gateway mounts only `${SERVER_DIR}/results` and mounts
it read-only.

##### Option A: Cloudflare Tunnel

Point Cloudflare Tunnel at the gateway's published `${PORT}`. Do not target the
internal Gunicorn service directly.

Reference: [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

##### Option B: Additional host reverse proxy or TLS termination

An additional host-level proxy may sit in front of the container gateway when
custom TLS termination, routing, or rate limits are required.

You can start from:

- `server/nginx_sites/REvoDesign_PSSM_GREMLIN.app`

#### 9. Security

##### Docker socket

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

##### Authentication

- Authentication signing keys are ephemeral; restarting web invalidates
  existing login, verification, and password-reset tokens.
- Browser page navigations use an `HttpOnly`/`SameSite=Lax` cookie; JavaScript
  cannot read it, so logout requires the server endpoint (`POST /api/auth/logout`).
- Rate limiting: 5 login attempts/minute/IP, 3 registrations/hour/IP.
- All state-changing endpoints require a valid Bearer token or API key.
- API keys have restricted privileges (task operations only) — Bearer tokens are required for profile changes and admin actions.
- Cookie-only writes are rejected; state-changing API calls require a Bearer
  token or API key.

##### Redis

- Redis is on an internal Docker network; do not expose its port publicly.
- The current Compose stack does not configure Redis authentication. Do not
  assume that setting `REDIS_PASSWORD` alone enables it.

##### Data

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

#### 10. Operations Notes

- Restrict Docker socket access to trusted operators only.
- Task visibility and operations are always restricted to the owner or an
  administrator.
- Regularly back up sqlite and result archives.
- If a task is deleted, result artifacts are removed, but the sqlite record remains for audit.

#### 11. Local Development

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

#### 12. Troubleshooting

##### Network issues

If `docker compose` failed due to network issues, try this:

1. Add proxy settings to your `/etc/systemd/system/docker.service.d/http-proxy.conf` file
2. Reload systemd service: `sudo systemctl daemon-reload`
3. Restart docker: `sudo systemctl restart docker`
4. Rerun restart scripts or `docker compose` commands under non-root user

A proper `http-proxy.conf` file might look like this (the proxy endpoint and the
`NO_PROXY` ranges below are site-specific examples — substitute your own):

```text
[Service]
Environment="HTTP_PROXY=socks5://<proxy-user>:<proxy-password>@<proxy-host>:<proxy-port>"
Environment="HTTPS_PROXY=socks5://<proxy-user>:<proxy-password>@<proxy-host>:<proxy-port>"
Environment="ALL_PROXY=socks5://<proxy-user>:<proxy-password>@<proxy-host>:<proxy-port>"
Environment="NO_PROXY=localhost,127.0.0.1,192.168.0.0/16,localhost,127.0.0.1,10.96.0.0/12,192.168.59.0/24,192.168.49.0/24,192.168.39.0/24,192.168.67.0/24,172.17.0.0/24,192.168.0.0/16,100.87.0.0/16,192.168.75.0/24,192.168.194.0/24,192.168.67.2"
```
