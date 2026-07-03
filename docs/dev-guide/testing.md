# Testing

REvoDesign uses **pytest** with **pytest-qt** (QtBot) for GUI testing and
**pytest-xdist** for parallel execution. Tests always run from a temporary
directory (`tmp-test-dir-with-unique-name/`) to test the *installed* package,
not the source tree.

## Test Classification

Tests are split into three tiers by execution cost:

| Tier | Target | Parallel | Coverage |
|------|--------|----------|----------|
| **Fast** | Unit tests, pure logic, mocked UI | Yes (`pytest-xdist`) | Created |
| **Serial** | GUI tests, heavy resources | No | Appended |
| **Slow** | GREMLIN analysis, full pipelines | No | Appended |

The tiers are invoked via Makefile targets:

```bash
make fast-test          # parallel fast tests
make serial-test        # serial tests (second order)
make slow-test          # slow tests (third order)
make all-test           # full matrix: fast → serial → slow
make kw-test PYTEST_KW='openkinetics'  # keyword filter
```

Test markers are auto-assigned in `conftest.py` via `pytest_collection_modifyitems`:
files with `spark` in the path get the `spark` marker, files with `_int_` in the
path get the `integration` marker.

## Conftest and Test Worker

`tests/conftest.py` is the central test harness. Key fixtures:

### `plugin` fixture

Creates a full `REvoDesignPlugin` instance inside a `qtbot` scope:

```python
@pytest.fixture(scope="function")
def plugin(qtbot, app, patch_config_user_data, patch_config_user_cache):
    cmd.reinitialize()
    reset_singletons()
    gc.collect()
    plugin = REvoDesignPlugin()
    plugin.run_plugin_gui()
    qtbot.addWidget(plugin.window)
    return plugin
```

- Isolates from the user's production config by pointing `platformdirs` at mock
  `user_data` and `cache` directories.
- Calls `reset_singletons()` between tests to prevent state leakage.
- Copies a fresh config tree (`copy_config_tree()`) from the package template.

### `PmTestWorker` helper

A helper class for package manager UI tests. Provides:

- `click(widget)` / `rclick(widget)` — Qt mouse interaction
- `do_typing(widget, text)` — text entry with widget signal triggering
- `save_screenshot(widget, basename)` — capture widget state
- `sleep(ms)` — controlled waits with `refresh_window()` pumping

### Other fixtures

| Fixture | Purpose |
|---------|---------|
| `app` | Singleton `QApplication` (created if none exists) |
| `counter` | Monotonic counter for unique test IDs |
| `pm_plugin` | Package Manager plugin with mocked GitHub/Gist responses |

## Test Data

- **Minimal data**: `tests/data/` — small PDB files, MSA test cases
  (`miniuc`, `testminiuc`), config fixtures.
- **Large data**: Fetched via URLs at runtime, not stored in the repo.

Test data paths:

```
tests/
├── data/
│   ├── test_data.py         # KeyData, TestData classes
│   └── msa/
│       ├── miniuc/          # minimal co-evolution test case
│       └── testminiuc/      # alternate test case
├── conftest.py              # shared fixtures and markers
└── magician/
    └── test_openkinetics_scorer.py  # example test module
```

## Running Tests

Tests **must** run from a temporary directory. The Makefile targets handle this
automatically, but if running `pytest` directly:

```bash
cd /tmp/test-dir && pytest /path/to/REvoDesign/tests
```

### Environment variables

| Variable | Effect |
|----------|--------|
| `PYTEST_QT_API` | Qt binding (`pyqt5` or `pyqt6`), auto-detected from `pymol.Qt.PYQT_NAME` |
| `ENABLE_ROSETTA_CONTAINER_NODE_TEST` | Set to `NO` to skip Docker + Rosetta tests |
| `OPENKINETICS_API_KEY` | Required for live OpenKinetics API tests |

### CI / headless

```bash
make setup-display-gha          # configure Xvfb virtual display
export ENABLE_ROSETTA_CONTAINER_NODE_TEST=NO
```

## CI Test Workflow

The unit test workflow (`.github/workflows/unit_tests_tag.yml`) runs on
push to `main` and on PR tags:

1. Cancel previous runs
2. Checkout + setup Xvfb
3. Pull Rosetta Docker image (conditional)
4. Create conda environment (PyMOL + PyQt)
5. Install PyTorch, REvoDesign, DGL
6. Run fast → serial → slow test matrix
7. Collect and upload coverage to Codecov

See [CI/CD](ci-cd.md) for the full workflow matrix.

## Test Worker Capabilities

The `plugin` fixture in `conftest.py` provides a fully initialized REvoDesign
GUI, enabling tests to:

- **Load molecules** — via `cmd.fetch()` or `cmd.load()`
- **Edit widgets** — `set_widget_value(widget, value)` from `customized_widgets`
- **Click buttons** — `qtbot.mouseClick(widget, Qt.LeftButton)`
- **Take screenshots** — `qtbot.screenshot(widget)` for UI and PyMOL views
- **Check mutant tree** — inspect `plugin.evaluator.tree`
- **Inject config** — `reload_config_file()` with custom YAML values
- **Reinitialize** — `reset_singletons()` + `cmd.reinitialize()` for clean state

## Writing New Tests

1. Add a test function or class in the appropriate `tests/` subdirectory.
2. Use the `plugin` fixture for GUI tests, or write plain pytest functions for
   pure-logic tests.
3. Name integration tests with `_int_` in the filename to auto-mark them.
4. For tests requiring live external APIs (OpenKinetics, etc.), guard with
   `pytest.skip` if the API key or service is unavailable.
5. Run `make kw-test PYTEST_KW='your_test_name'` before committing.

## Cleanup

```bash
make clean  # removes build artifacts, temp dirs, and cached downloads
```
