# CI/CD

The project uses GitHub Actions for continuous integration and delivery.

## CI Workflows

### `unit_tests_tag.yml` -- Bare Tests (primary)

Triggered on push/PR to `main`, release creation, and manual `workflow_dispatch`.

| Aspect | Configuration | Notes |
|--------|---------------|-------|
| Platform | GitHub Actions | Matrix jobs with caching via `actions/cache` |
| Operating systems | Ubuntu (primary), macOS | Ubuntu and macOS on push/PR; Windows entries commented out |
| Python versions | 3.10, 3.11, 3.12 | Matrix fan-out |
| Environment managers | Conda, Pip | Conda for PyMOL + scientific stack; Pip for Python deps |
| PyMOL channels | PyMOL Open Source (conda-forge), PyMOL Bundle (Schrödinger) v2 & v3 | OSS builds and official bundle (commented out for non-Linux) |
| Rosetta integration | Rosetta Docker (Ubuntu-only) | Gated by `ENABLE_ROSETTA_CONTAINER_NODE_TEST` |
| Qt versions | Qt5 (primary), Qt6 | Cross-Qt matrix entry for Ubuntu py3.12 |
| Timeout | 35 min (Linux), 60 min (Windows) | Per-job timeout-minutes |

**Active matrix entries:**

| os | python-version | pymol-version | qt-version | Notes |
|----|---------------|---------------|------------|-------|
| ubuntu-latest | 3.10, 3.11, 3.12 | pymol-open-source | 5 | Primary Linux sweep |
| ubuntu-latest | 3.12 | pymol-open-source | 6 | Qt6 validation |
| macos-15 | 3.11 | pymol-open-source | 5 | macOS open-source build |

**Workflow steps:**

1. Cancel Previous Runs -- cancels stale in-progress runs for the same ref
2. Checkout Repository -- `actions/checkout@v7`
3. Setup Qt headless Display -- `make setup-display-gha` on Ubuntu; `pyvista/setup-headless-display-action` on Windows/macOS
4. Verify Docker Version and Pull Rosetta Image -- pulls `rosettacommons/rosetta:mpi` on Ubuntu; sets `ENABLE_ROSETTA_CONTAINER_NODE_TEST=YES`
5. Setup Conda -- `conda-incubator/setup-miniconda` with libmamba solver
6. Setup PyMOL -- conda install `pymol-open-source` + `pyqt=5` (or `pyqt>=6`); adds `blast` and `hhsuite` on Ubuntu
7. Install REvoDesign -- PyTorch CPU wheel, then `make install`
8. Install DGL -- platform-specific (`install-dgl-linux` or `install-dgl-win`)
9. Full Unit Test -- `make prepare-test && make all-test`; sets `REVODESIGN_RUN_OPENKINETICS_LIVE` and `OPENKINETICS_API_KEY` on the Ubuntu 3.12 entry only
10. Convert coverage report to XML -- `coverage xml`
11. Upload coverage reports to Codecov -- `codecov/codecov-action@v7`
12. Clean up -- `make clean`

### `lint_badge.yml` -- Pylint

Triggered on push/PR to `main`, release creation, and manual `workflow_dispatch`. Runs `pylint` on the
`src/` package using a custom GitHub Action
(`YaoYinYing/pylint-github-action`) that posts a pylint score badge to
Cloudflare R2.

### `semantic-pr-check.yml` -- Semantic PR Check

Triggered on `pull_request_target` events (opened, edited, synchronize).
Uses `amannn/action-semantic-pull-request` to validate PR titles follow
conventional commit format (`type(scope): description`). This is a required
status check for merging.

### `docker-image.yml` -- Docker Image for Server

Manually triggerable (`workflow_dispatch`). Builds two Docker images:
- `revodesign-pssm-gremlin-non-root` -- runner image (PSSM + Gremlin computation)
- `revodesign-pssm-gremlin-server-non-root` -- server image (Flask REST API)

Both images are tagged with the current date and `latest`, then pushed to
Docker Hub under `yaoyinying/`. The runner's `Dockerfile` and server's
`Dockerfile` live under `server/docker/`. Desktop README on Docker Hub is
refreshed from `server/README.md`.

### `schedule-update-actions.yml` -- GitHub Actions Version Updater

Runs weekly (Sunday 00:00 UTC) via scheduled trigger, or manually via `workflow_dispatch`. Uses
`saadmk11/github-actions-version-updater` to open a PR updating GitHub Action
references to their latest versions. Requires a `PAT` secret with `workflow`
scope.

### `publish-pypi.yml` -- Python Publish Workflow

Publishes the package to PyPI. Triggered by:
- Pushing a `v*` tag
- Creating a GitHub Release
- Manual `workflow_dispatch` with target selection (pypi / testpypi)

The workflow:
1. Checks out the repository
2. Builds the distribution with `build`
3. Sanitizes `pyproject.toml` in the publish copy -- strips `git+` direct URL
   dependencies (which PyPI rejects)
4. Uploads to PyPI (on tagged releases) or TestPyPI (on `[testpypi]` commit
   messages or manual dispatch)

### `docs.yml` -- Documentation Site

Triggered on push to `main` when files under `docs/`, `src/`, or `mkdocs.yml`
change. Also `workflow_dispatch`. Builds an MkDocs site with Material theme
and `mkdocstrings[python]`, then deploys to GitHub Pages. Requires the
`pages` environment and `id-token: write` for OIDC deployment.

## Environment Variables

| Variable | Purpose | Set in |
|----------|---------|--------|
| `ENABLE_ROSETTA_CONTAINER_NODE_TEST` | Enable Rosetta Docker container tests | `unit_tests_tag.yml` (after pull) |
| `REVODESIGN_RUN_OPENKINETICS_LIVE` | Enable live API tests for OpenKinetics scorer | `unit_tests_tag.yml` (Ubuntu 3.12 only) |
| `OPENKINETICS_API_KEY` | API key for OpenKinetics live tests | `unit_tests_tag.yml` (from secrets) |
| `CODECOV_TOKEN` | Token for coverage upload | `unit_tests_tag.yml` (from secrets) |
| `PAT` | Personal access token for version updater PRs | `schedule-update-actions.yml` (from secrets) |
| `PYPI_PASSWORD` | PyPI API token | `publish-pypi.yml` (from secrets) |
| `TEST_PYPI_PASSWORD` | TestPyPI API token | `publish-pypi.yml` (from secrets) |
| `DOCKER_GITHUB_REPO_SECRET` | Docker Hub password | `docker-image.yml` (from secrets) |

## Required Secrets

| Secret | Workflow |
|--------|----------|
| `OPENKINETICS_API_KEY` | unit_tests_tag |
| `CODECOV_TOKEN` | unit_tests_tag |
| `CLOUDFLARE_API_TOKEN` | lint_badge |
| `R2_BUCKET` | lint_badge |
| `PAT` | schedule-update-actions |
| `PYPI_PASSWORD` | publish-pypi |
| `TEST_PYPI_PASSWORD` | publish-pypi |
| `DOCKER_GITHUB_REPO_SECRET` | docker-image |
