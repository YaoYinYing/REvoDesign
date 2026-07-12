---
name: ui-config-patterns
description: REvoDesign UI, config, and workflow conventions. Use when adding UI widgets, config keys, shortcuts, menu items, ValueDialog forms, or running the test suite.
when_to_use: new widget, config YAML changes, shortcut/dialog additions, ConfigBus usage, UI form, test run
---

# UI + Config + Workflow Patterns

## ConfigBus — the central nervous system

`ConfigBus(SingletonAbstract)` bridges UI widgets ↔ OmegaConf/Hydra YAML config. Initialized with `ui` (RuntimeUiProxy) during plugin startup.

### Reading/writing config

```python
ConfigBus().get_value("ui.header_panel.input.molecule", str)
ConfigBus().set_value("ui.header_panel.input.molecule", value)
```

- Dotted-path notation maps to YAML structure.
- In headless mode (`self.headless = True`), only `get_value`/`set_value` work; widget access requires `@require_non_headless`.
- `ConfigBus().button(name)` returns named QPushButton for signal connection.

### Config lifecycle

1. Template YAMLs at `src/REvoDesign/config/`.
2. First run: copied to `<user_data_dir>/REvoDesign/config/` via `set_REvoDesign_config_file()`.
3. Upgrade: `verify_config_tree_structure()` copies missing files; `enforce_config_key_structure()` replaces files whose key signatures differ from templates.
4. `reload_config_file(config_name, overrides)` calls `hydra.compose()` which resolves defaults lists and merges.
5. Config names are relative paths under config dir (e.g. `"rosetta-node/native"` loads `rosetta-node/native.yaml`).

### Widget binding

- `Config2WidgetIds` (in `widget_link.py`) maps config keys → widget objectNames.
- `widget_signal_tape(widget, callback)` connects the correct signal per widget type (`valueChanged`, `currentTextChanged`, `textChanged`, `stateChanged`).
- `initialize_widget_with_group()` runs GroupRegistryCollection generators (colormaps, runners) → populates combo boxes → restores values from config.
- `set_widget_value` / `get_widget_value` — unified widget I/O dispatching on isinstance (handles QSpinBox, QComboBox, QLineEdit, QCheckBox, QStackedWidget, QFontComboBox, etc.).

### Config Converter

`ConfigConverter.convert()` recursively converts `DictConfig` → plain `dict`.

## RuntimeUiProxy — the .ui bridge

- Load: `load_runtime_ui(ui_path)` → `(QWidget, RuntimeUiProxy)`.
- Access named widgets as attributes: `ui.input_molecule`, `ui.header_panel`.
- `refresh_bindings()` re-scans widget tree after retranslation, preserves `_*` attrs and `trans`.
- `retranslateUi()` dispatches to generated function or sends `LanguageChange` event.
- After editing `.ui` in Qt Designer: `python dev/tools/generate_ui_typing.py` to regenerate `types.py`. Pre-commit hook enforces freshness.
- Loading tries PyQt's `uic.loadUiType()` first, falls back to `QtUiTools.QUiLoader`.

## ValueDialog + AskedValue — dynamic forms

`ValueDialog` is a runtime-loaded form (from `UI/value_dialog.ui`). Accepts `AskedValueCollection` of `AskedValue` dataclasses:

```python
AskedValue(
    key="pdb", val="", typing=str, reason="Path to PDB file",
    required=True, source="File", ext="PDB_STRICT"
)
```

Fields: `key`, `val`, `typing` (Python type), `reason` (tooltip), `required`, `choices` (iterable or callable), `source` (None/File/FileO/Files/Directory/JsonInput/ColorPicker), `ext` (FileExtensionCollection), `multiple_choices`.

Widget dispatch by type: `multiple_choices=True` → MultiCheckableComboBox, `typing=bool` → QCheckBox, `choices=range/FloatRange` → QSpinBox/QDoubleSpinBox, `choices=iterable` → QComboBox, else → QLineEdit.

## Shortcuts YAML registry

YAML files at `shortcuts/registry/<name>.yaml` define dialogs declaratively. `DialogWrapperRegistry` loads and registers them:

```yaml
thermompnn:
  title: "ThermoMPNN"
  banner: "Perform ThermoMPNN prediction"
  options:
    - name: "pdb"
      type: str
      default: ""
      reason: "Path to the PDB file"
      source: "File"
      required: true
      ext: "PDB_STRICT"
    - name: "chains"
      type: str
      choices_from: "REvoDesign.shortcuts.dialog_hooks:get_all_chain_ids"
      multiple_choices: true
```

Value resolution prefixes in `choices_from` / `default_from`:
- `"range:1,1000"` → `range(1, 1000)`
- `"FloatRange:1.0,10.0,0.5"` → `FloatRange.from_str()`
- `"REvoDesign.module.path:func_name"` → `resolve_dotted_function()`
- `"CFG:rosetta.node_hint"` → `ConfigBus().get_value()`
- `"LAMBDA:lambda x: ..."` → `resolve_lambda_expression()`

Threaded functions use `run_wrapped_func_in_thread` which wraps with `timing()` and `run_worker_thread_in_pool`.

## Menu system

`menu.py` provides builder functions returning `MenuItem` namedtuples. Two patterns:
- **Static items**: tuple of `MenuItem(object_name, callable_path, kwargs, action_text, menu_section)`.
- **Dynamic config-edit items**: `config_edit_links()` scans config dir, creates one item per YAML with "main" sorted first.
- `callable_path` is either a direct callable or dotted string `"REvoDesign.shortcuts.wrappers.represents:wrapped_color_by_plddt"`.

## REvoDesignWidget — base window class

- `allow_repeat=False` prevents duplicate windows (raises existing via `check_repeat()`).
- `freeze_to_wait()` context manager disables/re-enables widget during async work.
- `show()` calls `attach()` (registers with `ConfigBus.ui.open_windows`); `destroyed` calls `detach()`.

## Test workflow

```bash
# Always inside a conda environment, always from a temp directory:
conda run -n REvoDesignTestFlight make fast-test          # parallel
conda run -n REvoDesignTestFlight make serial-test        # serial
conda run -n REvoDesignTestFlight make kw-test PYTEST_KW='<keyword>'  # focused
```

Tests run from `tmp-test-dir-with-unique-name/` — tests the **installed** package, not the source tree. Conftest does `os.path.abspath("..")` relative to CWD. CI/headless: `make setup-display-gha` + `export ENABLE_ROSETTA_CONTAINER_NODE_TEST=NO`.

## Before committing

```bash
make black           # runs pre-commit run --all-files (black, isort, autoflake, pyupgrade, autopep8 + custom hooks)
git add -A           # stage formatting changes together with edits
```

Exit code of `make black` is advisory — improved syntax and style = good regardless. Pre-commit hooks must pass.

## Version bumping

1. Update `__version__` in `src/REvoDesign/__init__.py`.
2. Run `make tag` — reads from **unstaged** diff of `__init__.py`. Do NOT `git add` the version change before running it.
3. `make tag` inserts dated `[new_version]` section in CHANGELOG.md, commits, creates annotated tag, pushes with `--tags`.
