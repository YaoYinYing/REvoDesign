# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow

- **CI suddenly failing on unchanged code?** Re-run the last passing CI commit before chasing symptoms. Same commit, same pass → environment regression (pinned a dep too loose). Same commit, now fails → something external changed. Either way, you know which side the bug lives on before touching a line of code.
- **Heisenbug debugging**: When a crash moves every time you change unrelated code (different stack trace, same SIGABRT), you're looking at heap-layout-sensitive corruption, not a deterministic logic bug. The signature: same commit bisects both passing AND failing → the commit is a layout perturbator, not the root cause. Stop chasing cleanup ordering. Ask: what two object-lifetime systems are mixing? The fix is removing the boundary, not getting the teardown order right. Each failed "fix" that only shifts the crash is evidence you're treating a symptom.
- **Before committing**: Run `make black` to format all files, then `git add -A` to stage the formatting changes together with your edits. This ensures pre-commit hooks (black, isort, autoflake, pyupgrade, autopep8) pass and keeps the diff reviewable. **The exit code of `make black` is advisory — if the hooks leave the code with improved syntax and style, the result is good regardless of the exit code.**
- **After feature/bugfix work**: Update the relevant documentation in `docs/` and add an entry to `CHANGELOG.md` under the `[Unreleased]` section. Docs and changelog are part of the deliverable — not an afterthought.
- **Test-case-driven fixes**: For live/integration issues, first encode the observed behavior as the smallest test case or skip guard, then make the smallest production/test change, run the focused keyword gate (for example `make kw-test PYTEST_KW=openkinetics`), and update `CHANGELOG.md`. Treat environment-dependent live API responses such as expected HTTP `4xx`/`5xx` as explicit skips, while keeping non-HTTP client errors failing.
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

- `qt_wrapper.py` — detects the Qt backend from `pymol.Qt.PYQT_NAME` at import time. Exposes `QtCore`, `QtGui`, `QtWidgets`, `QT_BACKEND`, `QT_MAJOR`, plus `install_qt6_aliases()` for backward-compatible enum/class locations.
- `ui_runtime_loader.py` — loads `.ui` files at runtime via PyQt `uic.loadUiType` or `QtUiTools.QUiLoader`. The `RuntimeUiProxy` exposes named Qt objects as attributes (mimicking the old generated-UI pattern) and provides `retranslateUi()`. A `QTranslator` is stored as `.trans` for backward compatibility with legacy i18n code. `refresh_bindings()` re-scans the widget tree after retranslation, but preserves internal attrs (`_*`) and `trans`.
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
- Owns its translator reference (`self.trans`) rather than relying on `bus.ui.trans`
- `_ensure_translator()` checks for an existing translator on `bus.ui.trans` via capability checks (not `isinstance`), creates one if absent
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

### Key conventions

- **License header**: Every `.py` file starts with the GPL-3.0-only copyright block (enforced by `tools/license_notice.py`).
- **Line length**: 120 (black, flake8, autopep8, pylint all configured).
- **Python**: 3.10+ with `from __future__ import annotations` everywhere.
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

## Commit and PR guidelines

- **Commit messages**: Follow conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`). Use `[skip ci]` to skip CI for non-code changes.
- **Doc-only PRs**: When a PR only touches documentation files (e.g. `docs/`, `CLAUDE.md`, `README.md`, `mkdocs.yml`, or `.github/workflows/docs.yml`), append `[skip ci]` to the final commit message. CI testing is unnecessary for documentation-only changes.
- **PR titles**: Must follow conventional commit format — `type(scope): description` or `type: description`. Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Enforced by `semantic-pr-check` workflow on PR open/edit/sync.
- **Before pushing**: Run `make black`, then `git add -A` to stage formatting changes. Pre-commit hooks must pass.
- **Documentation**: Stored as Markdown under `docs/` or within the relevant module directory; no build step required.
