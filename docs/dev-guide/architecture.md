# Architecture

## Package Structure

```
src/REvoDesign/
├── __init__.py                  # Import stack: SingletonAbstract → bootstrap → ConfigBus → logger
├── REvoDesign.py                # Main PyMOL plugin entry point (REvoDesignPlugin)
├── basic/
│   ├── abc_singleton.py         # SingletonAbstract (Borg-like singleton pattern)
│   ├── abc_third_party_module.py# ThirdPartyModuleAbstract (name, installed, __bibtex__)
│   ├── designer.py              # ExternalDesignerAbstract (scorer/designer plugin base)
│   ├── mutate_runner.py         # MutateRunnerAbstract (sidechain solver base)
│   ├── plugin_registry.py       # PluginRegistry (package-scoped auto-discovery)
│   ├── data_structure.py        # IterableLoop, generic data structures
│   ├── group_registries.py      # GroupRegistryItem for dynamic UI population
│   ├── param_toggle.py          # ParamChangeRegistryItem, ParamChangeRegister
│   ├── server_monitor.py        # ServerControlAbstract for service lifecycle
│   ├── menu_item.py             # MenuCollection, MenuItem
│   └── extensions.py            # FileExtension types
├── bootstrap/
│   └── __init__.py              # Config bootstrap: verify, copy, load, cache dirs
├── driver/
│   ├── ui_driver.py             # ConfigBus (UI ↔ OmegaConf bridge singleton)
│   ├── widget_link.py           # Config2WidgetIds, PushButtons widget ↔ config maps
│   ├── group_register.py        # Widget group registries (solver lists, etc.)
│   ├── param_toggle_register.py # Param-change toggle wiring
│   ├── environ_register.py      # Environment variable registration from config
│   └── file_dialog.py           # FileDialog, IO_MODE, flattened compression
├── common/
│   ├── mutant.py                # Mutant data model
│   ├── mutant_tree.py           # MutantTree container
│   ├── multi_mutant_designer.py # MultiMutantDesigner
│   ├── mutant_visualise.py      # MutantVisualizer for PyMOL
│   ├── profile_parsers.py       # ProfileParserAbstract + parsers (PSSM, CSV, TSV)
│   └── file_extensions.py       # File extension registry (imported at bootstrap)
├── Qt/
│   ├── __init__.py              # Qt package init
│   ├── qt_wrapper.py            # Qt compat layer (QT_BACKEND, QT_MAJOR, QtCompat)
│   └── ui_runtime_loader.py     # RuntimeUiProxy — load .ui without codegen
├── magician/
│   ├── __init__.py              # Magician singleton, DESIGNER_REGISTRY, MagicianAssistant
│   ├── designers/
│   │   └── openkinetics/        # OpenKinetics API scorer (canonical plugin example)
│   │       ├── __init__.py
│   │       ├── _scorers.py      # OpenKineticsScorerAbstract + dynamic subclasses
│   │       ├── _client.py       # REST API client
│   │       ├── _models.py       # Dataclasses, exceptions, constants
│   │       └── _pdb.py          # PDB/ligand helpers
│   └── README.md                # Magician's Gimmick Orchestration Protocol
├── sidechain/
│   ├── sidechain_solver.py      # SidechainSolver singleton, RUNNER_REGISTRY
│   └── mutate_runner/           # Sidechain solver implementations
│       ├── DLPacker.py
│       ├── DLPackerPytorch.py
│       ├── DiffPack.py
│       ├── DunbrackRotamerLib.py
│       ├── PIPPack.py
│       └── RosettaMutateRelax.py
├── structure/
│   ├── SurfaceFinder.py         # Solvent-accessible surface detection
│   └── PocketSearcher.py        # Substrate-binding pocket detection
├── phylogenetics/
│   ├── gremlin_tools.py         # GREMLIN MRF analysis
│   ├── gremlin_pytorch.py       # PyTorch GREMLIN implementation
│   ├── evo_mutator.py           # Co-evolution mutation logic (GremlinAnalyser)
│   └── revo_designer.py         # REvoDesigner iterative design engine
├── clusters/
│   ├── cluster_sequence.py      # Sequence clustering for mutant reduction
│   ├── combine_positions.py     # Position combination utilities
│   ├── score_clusters.py        # Rosetta-based cluster scoring
│   └── methods/                 # Cluster algorithm implementations
├── evaluate/
│   ├── __init__.py              # Package init
│   └── evaluator.py             # Mutant evaluation and decision-making
├── editor/                      # Monaco editor integration
│   ├── __init__.py
│   ├── README.md
│   └── monaco/
│       ├── monaco.py            # MonacoEditorManager (download, install)
│       ├── server.py            # FastAPI server (file read/write, auth)
│       └── config.py            # ConfigStore for editor backend
├── issues/                      # Exception and warning hierarchy
│   ├── exceptions.py            # REvoDesignException + subclasses
│   └── warnings.py              # REvoDesignWarning + subclasses
├── shortcuts/                   # PyMOL cmd.extend command infrastructure
│   ├── __init__.py
│   ├── utils.py                 # DialogWrapperRegistry, input resolution
│   ├── wrappers.py              # Shortcut wrapper configs
│   └── registry/                # YAML shortcut definitions
├── config/                      # YAML config hierarchy (OmegaConf/Hydra)
│   ├── main.yaml                # Primary UI and workflow configuration
│   ├── environ.yaml             # Environment variables and secrets
│   ├── logger.yaml              # Logging configuration
│   ├── runtime.yaml             # Runtime-specific settings
│   ├── appearence.yaml          # Font and button matrix appearance
│   ├── editor.yaml              # Monaco editor backend configuration
│   ├── openmm.yaml              # OpenMM setup server config
│   ├── rfdiffusion/             # RFdiffusion model configs
│   ├── rosetta-node/            # Rosetta compute node definitions
│   ├── third_party/
│   │   └── scorers/
│   │       └── openkinetics_api.yaml  # OpenKinetics API settings
│   └── sidechain-solver/        # Per-solver config YAML files
├── UI/
│   ├── __init__.py
│   ├── REvoDesign.ui            # Qt Designer main window layout
│   ├── REvoDesign-PyMOL-entry.ui# Package manager installer UI
│   ├── types.py                 # Auto-generated REvoDesignUiProtocol
│   ├── preference.ui             # UI preference layout
│   ├── socket.ui                # Socket tab UI layout
│   └── language/                # Qt Linguist .ts/.qm translation files
├── logger/
│   ├── __init__.py
│   └── logger.py                # Root logger setup (initialized during import)
├── citations/
│   └── citation_manager.py      # CitableModuleAbstract, CitationManager
├── data/
│   ├── __init__.py
│   └── protein_code.py           # Static data (protein codes, etc.)
├── presets/
│   └── styles.py                 # Style presets
└── tools/
    ├── customized_widgets.py    # QButtonMatrix, dialogs, ParallelExecutor
    ├── mutant_tools.py          # Mutant serialization helpers
    ├── pymol_utils.py           # PyMOL session helper functions
    ├── download_registry.py     # File download with mirror fallback
    ├── cgo_utils.py             # CGO 3D graphics primitives
    ├── rosetta_utils.py         # Rosetta environment detection helpers
    ├── measure_utils.py         # PyMOL measurement object parsing
    ├── system_tools.py          # System info and environment detection
    ├── SessionMerger.py         # Safe PyMOL session merging
    ├── package_manager.py       # Package Manager installer internals
    ├── ssl_certificates.py      # SSL certificate management
    └── REvoDesign-manager/      # Package manager sub-tools
```

## Plugin Lifecycle

The bootstrap sequence is defined in `src/REvoDesign/__init__.py` and proceeds
through a strict ordering of imports:

1. **Garbage collector** -- `gc` is imported and enabled first.
2. **SingletonAbstract** -- The base singleton class from `basic.abc_singleton`
   is imported so all subsequent singletons work correctly.
3. **Bootstrap** -- `bootstrap/__init__.py` is loaded. It verifies the config
   directory exists, copies default YAML files from the package tree to the
   user config directory, and exposes functions like `reload_config_file()`,
   `save_configuration()`, and `set_cache_dir()`.
4. **File extensions** -- `common/file_extensions.py` registers known file
   extension types (`.pdb`, `.pse`, `.yaml`, etc.).
5. **ConfigBus** -- The central UI-to-config bridge singleton is imported
   (headless mode by default; GUI mode is activated when `.ui` is set later).
6. **Logger** -- Root logger is set up from the logger YAML config and is
   available to all subsequent modules.
7. **Version** -- `__version__` is read from the module.

At PyMOL start time, `REvoDesignPlugin.make_window()` runs:

```
load_runtime_ui(ui_path)         # Load REvoDesign.ui → (main_window, RuntimeUiProxy)
_install_language_change_filter  # Intercept Qt language change events
IconSetter(main_window)          # Set window and taskbar icon
reload_configurations()          # Initialize ConfigBus (headless → GUI mode),
                                 # register env vars, widget groups, and signals
ClusterTabController(ui, bus)    # Manage clustering tab state
FontSetter(main_window)          # Apply application font
LanguageSwitch(window)           # i18n translator setup
MenuCollection(...)              # Wire static menu items (working dir, reconfigure, etc.)
QtCore.QTimer → _bind_menu_links # Deferred: scan config files for edit/recent-experiment links
StoresWidget()                   # Server switch monitors (Editor, OpenMM)
# Wire tab-specific button signals, combo-box connections, and WebSocket setup
```

## Singleton Pattern

`SingletonAbstract` (in `basic/abc_singleton.py`) is a Borg-like singleton:

- `__new__` returns the cached `_instance` if one exists, otherwise creates it.
- `__init__` calls `singleton_init()` only once, guarded by a `self.initialized`
  flag.
- Subclasses implement the abstract `singleton_init()` method for custom
  initialization logic.
- `initialize()` class method creates the instance on first call, or updates
  existing instance attributes on subsequent calls.
- `derive(name)` dynamically creates a new subclass with its own independent
  `_instance` (used for per-class singleton isolation).
- `reset_instance()` clears `_instance` for testing cleanup.

Key singleton subclasses:

| Class | Purpose |
|---|---|
| `ConfigBus` | Central UI-to-Config bridge |
| `Magician` | External designer/scorer gimmick manager |
| `SidechainSolver` | Manages the active mutate runner |
| `StoresWidget` | Holds server-switch references |

## Qt Compatibility Layer

All Qt imports go through `REvoDesign.Qt` -- never import PyQt5 or PyQt6
directly. The `check-qt-binding-imports.py` pre-commit hook enforces this.

- **Backend detection**: `qt_wrapper.py` imports `pymol.Qt` at runtime and
  inspects `pymol.Qt.PYQT_NAME`. This yields `QT_BACKEND` (e.g. `"PyQt5"`,
  `"PyQt6"`) and `QT_MAJOR` (5 or 6).
- **Optional modules**: `QtNetwork`, `QtWebSockets`, `QtSvg`, `QtUiTools` are
  imported lazily via `_import_optional_qt_module()`. Availability is checked
  with `has_qt_module(name)`.
- **Enum compatibility**: `install_qt6_aliases()` installs scoped enum
  containers on Qt5 backends (e.g. `Qt.WidgetAttribute.WA_DeleteOnClose`)
  and flat aliases on Qt6 (e.g. `Qt.WA_DeleteOnClose`) so code works on both.
- **`QtCompat`**: A `_QtCompatNamespace` instance with commonly used enum
  values (message box buttons, alignment flags, check states).
- **`qexec(obj)`**: Wraps `obj.exec()` / `obj.exec_()` for Qt5/Qt6
  compatibility.

**Runtime UI loading**: `load_runtime_ui()` in `ui_runtime_loader.py` loads
`.ui` files at runtime via `PyQt5.uic.loadUiType` or `QtUiTools.QUiLoader`,
bypassing the need for pre-generated Python UI code. The returned
`RuntimeUiProxy` exposes named Qt objects as attributes and provides
`retranslateUi()`.

## Plugin Registry System

`PluginRegistry` (in `basic/plugin_registry.py`) is a frozen dataclass that
performs **package-scoped auto-discovery** of plugin classes:

- On initialization, it imports all modules under a given `package` path
  (using `pkgutil.iter_modules`).
- It collects non-abstract subclasses of `base_class` and indexes them by
  their `name` attribute.
- Duplicate `name` values raise a `ValueError`.
- `build_plugin_registry()` is a convenience factory function.

Two registries are used in practice:

```python
# src/REvoDesign/magician/__init__.py
DESIGNER_REGISTRY = build_plugin_registry(
    base_class=ExternalDesignerAbstract,
    package="REvoDesign.magician.designers",
)

# src/REvoDesign/sidechain/sidechain_solver.py
RUNNER_REGISTRY = build_plugin_registry(
    base_class=MutateRunnerAbstract,
    package="REvoDesign.sidechain.mutate_runner",
)
```

Each registry exposes `.all_classes`, `.implemented_map` (name to class),
`.installed_names` (filtered by the `installed` class attribute), and
`.get(name, **kwargs)` for instantiation.

## Config System

Configuration is managed by **OmegaConf/Hydra** with a YAML hierarchy stored
under `src/REvoDesign/config/`. The user config directory is determined by
`platformdirs` and defaults are copied there at first launch.

- **`Config` dataclass** (in `driver/ui_driver.py`): wraps a name, file path,
  and `DictConfig`. Provides `from_name()`, `from_file()`, `save()`,
  `reload()`, `save_to_experiment()`.
- **`ConfigBus` singleton**: Loads all YAML config files from the config
  directory into `self.cfg_group` (a `dict[str, Config]`). The `"main"` group
  holds the primary configuration.
- **`Widget2ConfigMapper`**: Maps between config item keys, widget IDs, and
  Qt widget objects using `Config2WidgetIds` and `PushButtons` registries.
- **Headless mode**: When no `ui` is provided at init, `ConfigBus.headless =
  True`. Methods that need widgets use `@require_non_headless` decorator and
  raise if called in headless mode.

Values are read with `get_value(cfg_item, converter, ...)` and written with
`set_value(cfg_item, value)`. Widget-to-config synchronization is wired via
`register_widget_changes_to_cfg()` which connects each widget's signal to an
updater that writes the new value into the OmegaConf tree.

## Extension Points Summary

Two abstract base classes define the plugin extension points:

### ExternalDesignerAbstract (designer.py)

Base class for **external scorers/designers** (the "Magician's Gimmick").

| Attribute/Method | Purpose |
|---|---|
| `name` | Unique plugin name (used for registry lookup) |
| `installed` | Whether the dependency is available |
| `scorer_only` | If True, only `scorer()` is implemented (no `designer()`) |
| `prefer_lower` | Whether lower scores are better |
| `initialize()` | One-time setup (load models, validate config) |
| `scorer(mutant)` | Score a single mutant, return `float` |
| `designer(**kwargs)` | Generate new designs (optional) |
| `parallel_scorer(mutants, nproc)` | Default parallelizes via `joblib.Parallel` |

Auto-discovered by `DESIGNER_REGISTRY` under `magician.designers`.

### MutateRunnerAbstract (mutate_runner.py)

Base class for **sidechain solvers** (mutation/packing tools).

| Attribute/Method | Purpose |
|---|---|
| `name` | Unique solver name |
| `installed` | Whether the dependency is available |
| `weights_preset` | Model/backend options for the UI dropdown |
| `default_weight_preset` | Default option in the dropdown |
| `run_mutate(mutant)` | Run single mutation, return PDB path |
| `run_mutate_parallel(mutants, nproc)` | Run mutations in parallel |
| `reconstruct()` | Optional reconstruction support |

Auto-discovered by `RUNNER_REGISTRY` under `sidechain.mutate_runner`.
