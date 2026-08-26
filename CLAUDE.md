# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Engineering Principles

- Do not preserve backward compatibility. Remove obsolete paths instead of
  adding compatibility layers, fallbacks, or migrations.
- Choose the simplest implementation that fully meets the current requirements.
  Avoid speculative abstractions, configuration, and indirection.
- Grow the system in layers. Start from the smallest version that works end to
  end, and add each new capability on top of a product that already works. Never
  trade a working product for unfinished complexity.
- Keep components modular and concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce overall
  complexity or improve reliability. Do not reimplement common functionality
  without a clear reason.
- Lean on the dependencies already in the project before writing your own
  implementation or adding packages. Do not assume a library lacks a capability
  without checking its documentation and types.
- Make architectural decisions for the long term. Do not accept a stopgap that
  only works for now and is meant to be replaced later.
- The server is the single source of truth for all configuration data. Never
  duplicate task-type definitions, parameter schemas, file-extension rules,
  resource policies, or scientific constants from YAML/Python into JavaScript.
  If the JS needs data that the server owns, add an API endpoint. A JS
  fallback that mocks server config for when the API is unreachable is still
  duplication — show an error instead.
- **Never vendor third-party JS/CSS/code into the repo.** CDN-reachable frontend assets (viewer libraries, fonts, frameworks) load from the CDN at runtime with a pinned version and SRI — do not copy them into the repository, and do not fetch-and-bake them into Docker images. If a CDN dependency proves unreliable, remove the dependency, don't fork it into the codebase.
- **Pin Python packages only after checking the real distribution channels.**
  Before adding a `package==X.Y.Z` to a Dockerfile, verify:
  1. PyPI can be a stub — check `https://pypi.org/pypi/<pkg>/json` for actual
     releases (`openfold` on PyPI has only `0.0.1`; the real releases install
     from GitHub: `pip install '<pkg> @ git+https://github.com/<org>/<repo>.git@<tag>'`).
  2. Extra indexes prune old versions — the PyTorch `cu121` index no longer
     carries `2.1.2+cu121` (minimum is `2.2.0+cu121`); check the index before
     pinning a build-tagged wheel.
  3. pip's "Ignored versions that require a different python version" list
     aggregates ALL packages in one resolution pass — versions listed there
     are not necessarily versions of the package you asked for.
  4. Packages whose `setup.py` imports `torch.utils.cpp_extension` (openfold,
     torchdrug, etc.) need `nvcc` — the builder stage must use a `-devel`
     CUDA image, not `-runtime`. Their C++/CUDA extensions are compiled
     against the torch wheel's CUDA minor version, so the image's CUDA
     version must match the wheel's build tag (`+cu121` ↔ CUDA 12.1).

## Workflow

- **CI suddenly failing on unchanged code?** Re-run the last passing CI commit before chasing symptoms. Same commit, same pass → environment regression (pinned a dep too loose). Same commit, now fails → something external changed. Either way, you know which side the bug lives on before touching a line of code.
- **Heisenbug debugging**: When a crash moves every time you change unrelated code (different stack trace, same SIGABRT), you're looking at heap-layout-sensitive corruption, not a deterministic logic bug. The signature: same commit bisects both passing AND failing → the commit is a layout perturbator, not the root cause. Stop chasing cleanup ordering. Ask: what two object-lifetime systems are mixing? The fix is removing the boundary, not getting the teardown order right. Each failed "fix" that only shifts the crash is evidence you're treating a symptom.
- **Before committing**: Run `make black` to format all files, then `git add -A` to stage the formatting changes together with your edits. This ensures pre-commit hooks (black, isort, autoflake, pyupgrade, autopep8) pass and keeps the diff reviewable. **The exit code of `make black` is advisory — if the hooks leave the code with improved syntax and style, the result is good regardless of the exit code.**
- **After feature/bugfix work**: Update the relevant documentation in `docs/` and add an entry to `CHANGELOG.md` under the `[Unreleased]` section.
- **CHANGELOG entries**: module-scoped terse bullets in the 1.8.5-era style (`- Server:`, `- Package manager:`, `- Qt:` top-levels with one-line sub-bullets). Descriptions must be short, precise, and compact — never long prose paragraphs. The `## TEMPLATE` block must stay empty; real content belongs only in version sections or `[Unreleased]`. Docs and changelog are part of the deliverable — not an afterthought. **Code-doc alignment**: when a change alters behavior that existing docs already describe (architecture sections, dev guides, CLAUDE.md itself), update that description in the same PR — a doc that still describes the replaced design is a bug, and a reviewer asking "did you update the docs?" means the check was missed.
- **Test-case-driven fixes**: For live/integration issues, first encode the observed behavior as the smallest test case or skip guard, then make the smallest production/test change, run the focused keyword gate (for example `make kw-test PYTEST_KW=openkinetics`), and update `CHANGELOG.md`. Treat environment-dependent live API responses such as expected HTTP `4xx`/`5xx` as explicit skips, while keeping non-HTTP client errors failing.
- **PR babysitting workflow** — after opening a PR, own it through the squash-merge marker:
  1. Work on a fix branch off `main`; conventional commit messages; never push to `main` directly.
  2. Babysit CI until green, then read every bot review comment from codex and
     coderabbit and decide per comment: fix or ignore — reply with evidence
     (file:line) when ignoring a valid-looking finding. **DeepSource and Codacy are
     ignored** — their check statuses and comments are noise (stylistic lint
     profiles configured opposite to project conventions): don't fix, don't
     debate, don't treat them as blocking. No branch protection gates on them.
     Their findings get handled periodically in dedicated batch-fix PRs.
  3. **Server PRs** (`server/` — REvoCompute): follow [`server/DEPLOYMENT_CONTROL_GUIDE.md`](server/DEPLOYMENT_CONTROL_GUIDE.md). Use the absolute production env path and exactly one controller mutation at a time. If runner images changed, first run `prepare --enabled-runners=<changed-csv> --use-proxy --build-sif` while the healthy stack remains up. Then dry-run and activate with `REVODESIGN_SERVER_ENV=/repo/REvoDesign/server/.env.production.v7-slurm bash server/run/restart.sh restart --mode=prepared --keep-gateway`. When no runner image changed, skip preparation and use the same prepared activation; never use a bare restart for routine production because it defaults to dev mode and rebuilds every enabled runner plus the server. Before activation, sync `server/config/task_types.yaml` to the production `CONFIG_DIR` copy (back it up, copy it over, re-apply the two machine lines `job_executor: slurm` / `container_runtime: apptainer`). New runtime families must be appended to `ENABLED_TASKRUNNERS` in the deployment env file before activation; task types using an enabled family need no additional entry. The server only enables registered-and-listed task types. After the restart, verify `${CONFIG_DIR}/.deploy-stamp` (commit, digests, changed families, backup path). Disk-full recovery: `docker buildx prune`, `APPTAINER_CACHEDIR=/home/yinying/.apptainer/ apptainer cache clean --type all`, remove obsolete SIFs. Then live-verify the affected pages on the canonical direct edge `https://revocompute.yaoyy.moe` in incognito (cache-free); `https://revocompute-relay.yaoyy.moe` is the optional relay edge and is not a deployment blocker. When behavior changed, submit a living test with a real data file from `tests/data` through the API using the group test account (ask the user for credentials if none are in session or memory): login `POST /compute/api/auth/login` with `{"username": …, "password": …}` → Bearer token; submit `POST /compute/api/post` (multipart `file` + `task_type` + `params[name]`/`workspace`); monitor the local SLURM job (`squeue`) and read results from the API — status `GET /compute/api/running/<md5>`, manifest `GET /compute/api/results/<md5>`, logs `GET /compute/api/results/<md5>/artifacts/<path>`. Verify the served static files contain the change AND the page behaves as designed, never just one of the two.
  4. **Main program PRs** (PyMOL plugin): CI and review comments only — no server deploy. Run the relevant gates (`make kw-test PYTEST_KW='<keyword>'`); cross-Qt checks exist in `REvoDesignTestFlight` (PyQt5) and `REvoDesignTestFlightQt6`.
  5. When CI is green and every comment is fixed or consciously ignored, push a final empty marker commit `chore: Done fixing — <what was live/CI verified>` as the branch head (the plain `Done fixing` prefix is an intentional exception to the conventional-commit rule, matching the squash-merge habit); the user squash-merges from there.
- **PR lessons learned**: Do not repeatedly trigger automated reviews; request one review pass, batch valid findings, and verify locally between pushes. Runner builds use the final Docker tag directly—never create `:next` or `:previous` image tags. Replacing `:latest` retires the old digest through dangling-image pruning. For SIFs, record the exact source Docker digest and SIF hash in `images/digest/image-sif.json` and refuse activation on mismatch.
- **Standalone bootstrapper encoding**: Keep `src/REvoDesign/tools/package_manager.py` ASCII-only because it is published as `REvoDesign_PyMOL.py` and may be saved through locale-aware Windows tools. A UTF-8-to-GBK transcode turns characters such as `→` into bytes beginning with `0xA1`, which Python 3 rejects while parsing the file as UTF-8. Preserve both the GBK-compilation regression test and the `check-standalone-source-ascii` pre-commit guard; non-ASCII text remains acceptable in normal packaged modules.
- **Simplified-Chinese Windows living test**: After merging the installer change, republish both `REvoDesign_PyMOL.py` and `manifest.json` before testing so the Gist artifacts match the merged source. Test the documented first-install flow early on a Simplified-Chinese Windows machine with the system UTF-8 option **off** (the default CP936/GBK adverse path); record `chcp`, download the raw Gist through the normal user path, install it in PyMOL, and confirm bootstrap and installation succeed. Repeat with **Region → Administrative language settings → Change system locale → “Beta: Use Unicode UTF-8 for worldwide language support”** enabled and the machine rebooted (CP65001); bootstrap and installation must also succeed. The UTF-8 guidance lives in the docs only — the package manager no longer probes code pages or shows a dialog. The toggle is a user workaround for non-English CMD/Windows PowerShell streams, not a prerequisite or substitute for CP936 compatibility.
- **Version bumping**:
  1. Update `__version__` in `src/REvoDesign/__init__.py` (validate format at https://regex101.com/r/6AoOI9/1).
  2. Run `make tag` — it extracts old/new versions from the git diff, inserts a dated `[new_version]` section in `CHANGELOG.md`, commits `CHANGELOG.md` + `__init__.py`, creates an annotated tag with the changelog between versions, and pushes with `--tags`.
  - **Important**: `make tag` reads versions from the *unstaged* diff of `__init__.py`, so do NOT `git add` the version change before running it.

## Build and Test

```bash
# Install dev environment
conda create -n REvoDesignTestFlight python=3.12 -y
conda install -c conda-forge pymol-open-source pyqt=5 -n REvoDesignTestFlight -y
make install-pytorch-cpu-non-mac
make install

# Optional: DGL (Linux only, failure is non-fatal)
make install-dgl-linux

# Test dependencies
make prepare-test

# Run tests (always inside a conda environment)
conda run -n <env> make fast-test          # parallel fast tests
conda run -n <env> make serial-test        # serial tests
conda run -n <env> make slow-test          # slowest tests
conda run -n <env> make all-test           # full test matrix
conda run -n <env> make kw-test PYTEST_KW='<keyword>'          # single keyword
conda run -n <env> make kw-test PYTEST_KW='"<kw1> or <kw2>"'   # multiple keywords

# CI / headless environments
make setup-display-gha                     # configure virtual display
export ENABLE_ROSETTA_CONTAINER_NODE_TEST=NO  # skip Docker + Rosetta for basic testing

# Formatting and linting
make black          # runs pre-commit run --all-files
pre-commit install  # enable git hooks

# Regenerate UI typing contract (after .ui changes)
python dev/tools/generate_ui_typing.py
python dev/tools/generate_ui_typing.py --check   # validate freshness only
```

Tests run from a temporary directory (`tmp-test-dir-with-unique-name/`) to test the *installed* package, not the source tree. The conftest at repo root does `os.path.abspath("..")` relative to CWD, which fails outside that temp dir.

### Qt version testing

Two conda environments exist for cross-Qt testing:
- **PyQt5**: `REvoDesignTestFlight` (PyQt5 explicitly installed)
- **PyQt6**: `REvoDesignTestFlightQt6` (PyQt6 from `pymol-open-source`)

## Architecture

### Qt compatibility layer (`src/REvoDesign/Qt/`)

All Qt imports MUST go through `REvoDesign.Qt` — never import PyQt5 or PyQt6 directly. The `check_qt_binding_imports.py` pre-commit hook enforces this.

- `qt_wrapper.py` — detects the Qt backend from `pymol.Qt.PYQT_NAME` at import time. Exposes `QtCore`, `QtGui`, `QtWidgets`, `QT_BACKEND`, `QT_MAJOR`, plus `install_qt6_aliases()` (scoped enum containers on Qt5) and the generic `_install_unscoped_enum_bridge()` (mirrors every scoped-enum member onto its owning class so Qt5-style flat access works on Qt6 with no per-API bookkeeping). The standalone package manager ships the same bridge as `_install_qt_enum_bridge()` in `package_manager.py`; regression coverage is `tests/tools/test_qt_enum_bridge.py` (runs against real PyQt6 in the CI qt6 job).
- `ui_runtime_loader.py` — loads `.ui` files at runtime via PyQt `uic.loadUiType` or `QtUiTools.QUiLoader`. The `RuntimeUiProxy` exposes named Qt objects as attributes (mimicking the old generated-UI pattern) and provides `retranslateUi()`. `refresh_bindings()` re-scans the widget tree after retranslation while preserving internal attributes (`_*`).
- `Ui_REvoDesign.py` is **deprecated** — the pre-commit hook `reject_generated_main_ui.py` prevents it from being re-introduced.

### Singleton and ConfigBus (`src/REvoDesign/driver/ui_driver.py`)

`SingletonAbstract` is a custom Borg-like singleton: `__new__` returns the cached `_instance`, and `__init__` calls `singleton_init()` only once (guarded by `self.initialized`). Subclasses must implement `singleton_init`.

`ConfigBus(SingletonAbstract)` is the central nervous system — a bidirectional bridge between UI widgets and OmegaConf/Hydra YAML configuration:
- Created as a singleton, initialized with `ui` (the `RuntimeUiProxy`) during plugin startup.
- `Widget2ConfigMapper` maps config item names ↔ widget IDs ↔ widget objects, using `Config2WidgetIds` and `PushButtons` registries.
- In headless mode (`self.headless = True`) only `get_value`/`set_value` work; widget access requires `@require_non_headless`.
- `StoresWidget` is a companion singleton holding server-switch references.

### Plugin lifecycle (`src/REvoDesign/REvoDesign.py`)

`REvoDesignPlugin(QtWidgets.QWidget)` is the main PyMOL plugin entry point:
1. `load_runtime_ui()` loads `UI/REvoDesign.ui` → returns `(window, RuntimeUiProxy)`
2. Sets `self.bus.ui = ui` on the `ConfigBus` singleton, which transitions it from headless to GUI mode
3. Initializes sub-systems: `SurfaceFinder`, `PocketSearcher`, `ClusterRunner`, `MultiMutantDesigner`, `GremlinAnalyser`, `Evaluator`
4. Sets up i18n via `LanguageSwitch(window)`
5. Wires keyboard shortcuts from `REvoDesign.shortcuts`

### Internationalization (`src/REvoDesign/application/i18n/language_settings.py`)

`LanguageSwitch` manages translator lifecycle:
- Owns the translator reference passed back by `install_translator_early()` and creates one only when early installation is unavailable
- `switch_language()` removes the previous translator before installing the new one, preventing accumulation
- Dynamic language menu actions are retranslated via `_retranslate_language_actions()`

### Runtime UI proxy and type contracts

- `REvoDesignUiProtocol` (in `src/REvoDesign/UI/types.py`) is auto-generated from `REvoDesign.ui` by `dev/tools/generate_ui_typing.py`. It defines typed attributes for static analysis/IDE completion only — it never constructs the UI.
- The protocol is regenerated on `.ui` file changes (pre-commit hook `generate-ui-typing`).
- `RuntimeUiProxy` acts like a namespace: named children from the `.ui` become attributes. Duplicate names are recorded in `_duplicate_object_names`; only the first-seen object becomes the attribute.

### Pre-commit hooks (local/custom)

| Hook | Purpose |
|------|---------|
| `generate-ui-typing` | Re-generate `types.py` when `.ui` changes |
| `check-ui-typing` | Fail if `types.py` is stale |
| `validate-ui-i18n` | Smoke-test runtime UI loading + i18n pipeline |
| `reject-generated-main-ui` | Ensure `Ui_REvoDesign.py` is never re-introduced |
| `check-qt-binding-imports` | Reject direct PyQt5/PyQt6 imports |
| `check-changelog-duplicates` | Reject duplicate `### Section` headers within a version block in CHANGELOG.md |

### Key conventions

- **License header**: Every `.py` file starts with the GPL-3.0-only copyright block (enforced by `tools/license_notice.py`).
- **Line length**: 120 (black, flake8, autopep8, pylint all configured).
- **Python**: 3.10+ with `from __future__ import annotations` everywhere.
- **Test file size**: Keep test files under 1000 lines. Split by concern (auth, security, race conditions, etc.) rather than letting a single file grow unbounded.
- **Imports**: First-party package is `REvoDesign`; internal imports use fully-qualified paths (`from REvoDesign.Qt import QtCore`).
- **Config files**: YAML under `src/REvoDesign/config/`, managed by OmegaConf/Hydra. The config directory is determined by `platformdirs` user config path.
- **Version**: Set in `src/REvoDesign/__init__.py` (`__version__`). Use `make tag` to bump.

### Threading: QThread vs `threading.Thread`

**Rule: Long-lived event-loop servers (uvicorn, asyncio) MUST use `threading.Thread`, never `QThread`.**

`WorkerThread` (`src/REvoDesign/tools/package_manager.py`) is a `QThread` subclass. QThread creates a SIP-managed C++ QObject whose Python wrapper can outlive the C++ object during GC. When cross-thread Qt signals touch the stale wrapper, `sipWrapper_dealloc` → `forgetObject` → `QMessageLogger::fatal` → SIGABRT. This is a Heisenbug: heap-layout-sensitive corruption that moves every time code changes.

- **Use `threading.Thread`** for uvicorn servers, asyncio event loops, and any long-lived background work that isn't tightly coupled to Qt widgets.
- **Use `WorkerThread` (QThread)** for short-lived Qt-adjacent background jobs (e.g. `RunningProcessRegistry`) where signals/slots are needed.
- When joining a `threading.Thread` from the main thread, pump Qt events with `QApplication.processEvents()` so the UI doesn't freeze.
- The `_run_server_and_mark_stopped` pattern wraps `server.run()` in a `try/finally` that clears `is_running`, so a thread exit (clean or crash) syncs state without Qt signals.
- Mocking `threading.Thread` in tests: `MagicMock()` with `is_alive.return_value = False` — no `spec=WorkerThread` since `is_alive` is a `threading.Thread` API.

## Adapting a new scientific runner — intake

When asked "adapt \<tool\> to revocompute", follow the **Design-Build-Test-Learn
(DBTL) cycle** (detailed below) to close the loop and improve future adaptations.

The deliverable is a task-type registry entry + one runner YAML + `Dockerfile`/`run.sh`/`.def`
+ contract tests + a living SLURM test, following `server/OPERATIONS_AND_TASK_ADAPTER_GUIDE.md`.
To start a DBTL pass, provide at minimum the sections under **"Tool"** and **"Minimal run"**
below — missing critical items (weights, hardware constraints, minimal run params) will
block the build step and should be resolved first.

- **Tool**: name, repo URL, full commit hash to pin, CLI entrypoint, license.
- **Hardware**: GPU or CPU; CUDA/torch versions it needs; typical per-run memory and walltime.
- **Inputs**: accepted file extensions; which is the primary input; multiple/nested inputs needed?
- **Parameters**: the user-facing knobs — name, type, default, min/max/choices, description — and
  the CLI flag each maps to.
- **Outputs**: files produced (extensions); the success signal (completion marker, required outputs,
  exit codes) and how to detect a silently failed run.
- **Dependencies**: Python/torch/framework versions; model weights (URL, size, license, offline staging
  path); runtime network or cache needs.
- **Minimal run**: one working command line on a tiny input, plus a sample input file or a pointer
  to `tests/data`.

If the minimal run, weights, or hardware constraints are missing, ask for
them before building anything — the pin and the smoke case are the contract.

## Design-Build-Test-Learn cycle

After adapting a new runner, follow the DBTL cycle to close the loop and
improve future adaptations:

- **Design**: Document dependency pins, hardware requirements, input/output
  contracts, and parameter schemas before touching any files. Record why a new
  runtime family was needed versus sharing an existing one. Capture the
  minimal run parameters (small input, conservative caps) for smoke testing.
- **Build**: Construct the Dockerfile, runner YAML, `.def` file, and task type
  registry entry. Build the candidate image tag (`:candidate`) while production
  stays up. Validate proxy‑free ENV in the final image layer.
- **Test**: Run the Docker smoke test (minimum safe parameters through the API
  with a test account). Before production activation, run an actual
  server‑to‑worker‑to‑SLURM‑to‑Apptainer smoke: submit a task through the real
  API, monitor the local SLURM job (`squeue`), and read result logs from the API
  (status `GET /compute/api/running/<md5>`, manifest
  `GET /compute/api/results/<md5>`, logs
  `GET /compute/api/results/<md5>/artifacts/<path>`). Verify served static
  files contain the change and the page behaves as designed.
- **Learn**: After the cycle, update this section with what was learned —
  version gotchas (e.g. jax 0.4.x vs 0.6.x incompatibility), OpenCL ICD
  registration gotchas for OpenMM relax, conda‑versus‑pip resolution choices,
  or any parameter that proved unnecessary. Record the effective walltime and
  resource usage so future adaptations can set conservative defaults. Add any
  new task‑type patterns to the registry’s `RUNTIME_FAMILIES.md` table.

## Commit and PR guidelines

- **Commit messages**: Follow conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`). Use `[skip ci]` to skip CI for non-code changes.
- **Doc-only PRs**: When a PR only touches documentation files (e.g. `docs/`, `CLAUDE.md`, `README.md`, `mkdocs.yml`, or `.github/workflows/docs.yml`), append `[skip ci]` to the final commit message. CI testing is unnecessary for documentation-only changes.
- **PR titles**: Must follow conventional commit format — `type(scope): description` or `type: description`. Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Enforced by `semantic-pr-check` workflow on PR open/edit/sync.
- **Before pushing**: Run `make black`, then `git add -A` to stage formatting changes. Pre-commit hooks must pass.
- **Documentation**: Stored as Markdown under `docs/` or within the relevant module directory; no build step required.
