# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

```text
## TEMPLATE
### Added

### Changed

### Fixed

### Removed


```
## [Unreleased]

### Added
- Thread Pool Dashboard can be launched from `Runtime → Thread Pool Dashboard`, making it easy to inspect live worker threads and kill stuck installers/jobs without digging through logs.
- Package manager:
  - `_GuiThreadInvoker` and `execute_on_main_thread` for running Qt operations from worker threads to main thread.
  - Thread management: now track worker instances, expose a dashboard context menu Kill action, and default to the shared notifier so abort overlays and notifications stay in sync across workers.
    - `ThreadPoolEntry`: for tracking worker instances
    - `ThreadDashboard`: for visualizing worker threads
    - `ThreadPoolRegistry`: for registering worker instances to the registry
    - `RunningProcessRegistry`: for tracking running processes
    - `AbortButtonOverlay`: for showing abort buttons upon mouse cursor hover.
    - `ThreadExecutionManager`: for managing worker threads
  - Thread Dashboard can be opened by double clicking the header banner.
- docs: Thread management
- UI: Edit -> Runtime -> Thread Pool Dashboard for living thread views and controls

- Shared `run_worker_thread_in_pool` helper now backs Monaco bootstrap, EvoMutator, cluster runner, Qt socket client, and PyMOL plugin actions so every long-running workflow inherits the same cancellation/UI wiring.
- `tests/tools/test_package_manager.py` gained regression coverage for the new worker helpers, subprocess execution, and gist download utilities.
- Translation: Traditional Chinese (zh-tw)
- Server (PSSM_GREMLIN):
  - Task lifecycle state `packing results` between `running` and `finished`.
  - Immediate result packing after successful runs, with zip artifacts generated before `finished`.
  - Task deletion APIs:
    - single-task delete for owner/admin.
    - admin batch delete for multi-selection workflows.
  - Dashboard UX updates for task management:
    - delete actions, admin multiselect controls, owner labels, and status filters including `packing results`.
  - Create-task UX updates:
    - optional sequence editor that formats raw sequence input into FASTA with live preview.
  - Security/audit metadata in server task records:
    - `local user` (`username:groupname-uid:gid`).
    - sanitized full request-header capture.
  - Environment-driven admin controls with `ADMIN_USERS`.
  - Server env-file isolation support via `REVODESIGN_SERVER_ENV` in restart/hot-fix scripts.
  - Test env split: `server/.env.test` for test-only server runs.

### Changed
- Multi-mutagenesis buttons and other UI triggers switched from the progress-bar specific helper to the shared thread-pool utility, preventing UI freezes while keeping abort buttons responsive.
- `run_worker_thread_with_progress` -> `run_worker_thread_in_pool`, w/ dropped progressbar uses for indicating running task status.
- Editor:
  - logger control of uvicorn server. can be completely silenced.
  - Server: logs now printed as debug messages.
- Language switch: logs now printed as debug messages.
- Tests:
  - refactored tabs-case dependency flow to `pytest-dependency`:
    - `TestREvoDesignPlugin` -> `TestREvoDesignPlugin_TabPrepare` -> downstream tab/action case classes.
  - dropped active `pytest.mark.order` coupling in tabs bootstrap cases and enabled dependency-aware ordering with `--order-dependencies`.
- Test env/bootstrap:
  - test dependencies and `make prepare-test` now include `pytest-dependency`.
- Server (PSSM_GREMLIN):
  - Public/private dashboard behavior is now configurable with `PUBLIC_DASHBOARD` (`false` by default).
  - Task visibility and API access are scoped to the authenticated upload owner when `PUBLIC_DASHBOARD=false`.
  - Running-stage tracking now uses sqlite-backed `run_stage` persistence (single task stage tracker), replacing dashboard refresh reconstruction from file-based traces.
  - Runner execution flow now enforces non-root container user/group configuration and composes docker permissions from env.
  - Restart controls now provide explicit lifecycle subcommands:
    - `setup`, `build`, `up`, `down`, `restart` (default).
  - Env selection defaults updated for production-first use:
    - prefer `server/.env.production`, fallback to `server/.env`.
  - Server docs were rewritten as production-first Docker deployment instructions.

### Fixed
- Abort overlays now disappear when the cursor leaves their trigger areas and cleanup runs even when PyMOL cannot service interrupts, removing stuck abort buttons.
- Killing a worker tears down registered subprocesses and forcibly terminates straggling threads, so the dashboard accurately reflects running tasks.
- notify box and decide box now works under subthreads.
- Tests:
  - `test_pm_dialog_extras_panel_expand_collapse` now waites for the dialog to fully expand before asserting.
  - `test_utils` archive extraction now covers zip/tar path traversal rejection.
  - tab bootstrap dependencies are now session-scoped and `test_pick_design_from_profile` now depends on `tabs_prepare_pocket_session`, so CI runs pocket-session preparation before shortcut profile-picking tests.
  - `make serial-test` now includes dependency-root `bootstrap` cases so dependency-selected child tests do not emit unresolved-marker warnings when roots were excluded by marker filters.
- Security hardening:
  - archive extraction in `tools.utils.extract_archive` now validates member paths and rejects traversal entries before writing files.
  - Monaco editor tarball setup now reuses the hardened archive extractor instead of raw `tar.extractall`.
- Server (PSSM_GREMLIN):
  - task-id/content digest md5 calls now explicitly use `usedforsecurity=False` because they are non-cryptographic identifiers.
- Server (PSSM_GREMLIN):
  - Docker daemon permission failure handling for non-root runtime users in server/worker execution paths.
  - `run_stage` ORM/schema mismatch that caused sqlite update/compile failures and prevented task execution in server-image integration tests.
  - Real-server missing result artifacts by packing outputs at job completion rather than delaying zip creation until download request.
  - UniRef90 mount/prefix mismatch that caused runner exits like `/tmp/uniref90_db.fasta not found`.
  - Host absolute path leakage in dashboard/API error messages by masking to virtual server paths (`/srv/REvoDesign/PSSM_GREMLIN/upload/<filename>`).
  - Cross-user data exposure/unauthorized access paths on dashboard and task APIs when private mode is enabled.

### Removed
- Server (PSSM_GREMLIN):
  - Backward-compatibility states from older releases.
  - Legacy native/manual setup guidance from server deployment docs.



## [1.8.5] - 2026-01-14
### Added
- Server: 
  - Basic authentication guide and implementation
  - Documentation: Cloudflare tunnel as production public cloud service
- Typing annotations:
  - `get_cited`: broadcast typing hints from input function to wrapper
- Menu:
  - `MenuCollection`: joinded menu items at `MENU_LINKS`
  - Edit Configuration now supports all primary and secondary level of YAML files at user data dir.
  - Environment variables now can be edited from the editor and refreshable via menu.
  - `MenuItem`: 
    - `func` now can be a lambda string like `LAMBDA:<dotted-path:function>,<arg1>,<arg2>,<kwarg1=val1>,<kwarg2=val2>,...`
    - dynamic menu item creation
      - `action_text` for set action text, will fallback to `action` if empty.
      - `menu_section` for adding non-exist menu action to menu.
      - `is_separator` property for separator adding. set `action` to `---` will do. 
  - `MenuCollection`:
    - `bind` method now supports dynamic menu action creation under a certain menu section
  - Recent experiments:
    - `menuRecent_Experiments`: dynamically lists experiment configurations from the `experiments/` tree sorted by their last modification time for quick editing and backups.
- Phylogenetic:
  - GREMLIN in Pytorch
    - Implementation at `phylogenetics/gremlin_pytorch.py`
    - Validation at `notebooks/validate_gremlin_pytorch.ipynb`
    - Menu tool at `shortcuts/tools/evolution.py`
    - Menu wrapper at `shortcuts/wrappers/evolution.py`
    - Registered in `shortcuts/registry/evolution.yaml`
    - Minimal Tests at `tests/evo/test_gremlin_pytorch.py` w/ MSA file `tests/data/msa/4FAZA.i90c75_aln.fas`
- Tools:
  - `resolve_lambda_expression`: for resolving lambda expression from menu pop `choices_from` and `default_from`
  - `resolve_typed_arg`: for resolving typed arguments according to what the most it looks like
  - `resolve_default_value`: moved from shortcut util module
  - `resolve_dotted_config_item`: moved from shortcut util module
  - PyMOL: `load_safely` removes existing objects before reloading files, preventing duplicate-object errors when running iterative workflows. Bollowed from Caver
- Package manager:
  - `PackageManagerCommand` dataclass consolidates package manager metadata for Git bootstrap logic.
  - Tests ensuring apt-based installers leverage sudo when available.
  - Extras table now includes `python_version` key and filtrated according to current Python version.
- Application:
  - FontSetter`, `set_font`, and `REvoDesignWidget` propagate the current font to standalone dialogs, while the widget helpers now understand `QFontComboBox` instances so ValueDialog forms keep typography consistent.
- Editor:
  - Monaco editor URLs now carry autosave and autorefresh toggles/intervals so the static front-end can refresh or save files according to `editor.yaml`.
- Bootstrap configuration:
  - `_iter_yaml_rel_paths`, `verify_config_tree_structure`, and `enforce_config_key_structure` ensure user config trees mirror the template layout and key hierarchy by auto-copying missing YAML files and replacing outdated ones.
  - Tests covering the new helpers and the recursive config listing guard future refactors.
- `ui_driver`:
  - dataclass `Config`  
    - for handling configuration name/yaml path/configuration DictConfig obj
    - `__repr__` for full data representation at debug use.
    - classmethod `from_name` for creating Config obj from name under hydra config dir
    - classmethod `from_names` for creating mutiple Config obj from names
    - classmethod `from_file` for creating Config obj from yaml path
    - classmethod `from_files` for creating multiple Config obj from yamls
    - `save` for saving configuration to disk
    - `reload` for reloading configuration from disk
    - `reload_from` for reloading configuration from another yaml
    - `save_as` for saving configuration to disk with a new name
  - `ConfigBus`:
    - `cfg_group` for holding a Config obj dict: {name: Config obj}
    - use `self.cfg_group["main"].cfg` to replace `self.cfg`
- Logger:
  - `LOGGER_CONFIG` for logger configuration at global level, referenced as `bus.cfg_group['logger'].cfg` after initialization.
  - Logger module child logger for logging under this module.
  - `reload_logging_config` for reloading logging configuration (not sure if it really works, a restart may still be needed)
  - `get_current_logger_level` for getting current logger level
  - lambdas:
    - `list_all_logger_levels`: list all logger levels
    - `list_all_logger_channels`: list all logger channels
    - `list_all_logger_formatters_non_json`: list all logger formatters except JSON
    - `get_current_channel_level`: get current logger channel level
- UI: `socket.ui` for future UI splitting
- Docs: a documentation plan at `docs/plan.md`
  

### Changed
- `AGENTS.md`: refined installation guide
- Simplifed `get_cited` implementation, thanks to ChatGPT.
- `Makefile`:
  - `translate` for auto translate
- I18N:
  - `language.json` for translation registry
  - `LanguageNameRegistry` for handling language names/codes/actions
- Configuration:
  - Separated from main configuration
    - `logger`: for logger configuration
    - `runtime`: for runtime configurations
    - `openmm`: for openmm setup
    - `environ`: for environment variables holding
    - `sidechain-solver`: for sidechain solvers
    - `rosetta-node`: for rosetta-node configurations
    - `rfdiffusion`: for rfdiffusion parameter presets
    - `editor`: split from `main.yaml` into `config/editor.yaml` to isolate Monaco backend/autosave configuration
  - rename main configuration: `global_config` -> `main`
    - detect only the main configuration file, if not found, prompt and copy the full configuration tree to allow seamless upgrade (the directory will be dirty however)
  - `experiment_config` now can be used for any sub dirs like cache dir
  - `list_all_config_files` for listing all config files at first and second level
- Bootstrap:
  - Import-time initialization now calls the tree/key verification helpers so user config directories are automatically synchronized with the bundled templates.
  - Prints clearer copy/verify progress during bootstrap
- `list_all_config_files`:
  - deterministic top-level globbing and explicit recursive traversal for nested YAML keeps discoveries stable regardless of filesystem ordering.
- Experiments:
  - `load_and_save_experiment` now backs up into the `experiments/` directory before custom saves so new runs populate the Recent Experiments menu, and the test harness mirrors the new workflow entirely inside the test workspace.
- `ui_driver`:
  - `ConfigBus`:
    - `set_value` and `get_value` now supports data  getting/setting value from/to a certain Config obj name
  - Editor:
    - Added all configuration files to white list so that they can be edited.
- Logger:
  - Refactored `logger_level_setter` and `logger_level_setter_ng` for setting logger levels from menu pop
- Package manager:
  - `GitSolver` now caches detected installers, includes Linux/BSD managers (apt, dnf, yum, zypper, pacman, pkg, snap, scoop, port), and prefixes sudo only when required.
- Plugin:
  - Simplified configuration operations
  - Move some pluggin-specified imports inside the plugin class
- Makefile:
  - Build tooling: `make compile-ui` recompiles Qt forms, and `tools/translate.sh` now accepts a `stage` env flag plus formats regenerated UI modules with `black` for deterministic artifacts; `make translate` now performs the full release stage.
- Utils:
  - Modernized `resolve_lambda_expression`, 
  - Refactored the `timing` helper with structural pattern matching, prompting updated assertions in `tests/tools/test_utils.py`
- Citation Manager:
  - now uses color escape code from `RosettaPy`
  

### Fixed
- package meta: `pyproject.toml`
  - `pyright`: `pythonVersion = "3.10"`
- logging:
  - remove logging statements for `DialogWrapperRegistry.unregister` as logger has already exit when unregistering.
- Tests:
  - Minor fixes according to current changes.
  - ~~Partial user platform dirs mock  to isolate test config from production.~~ WIP
  - PyMOL session helpers now surface exceptions instead of swallowing them so debugging fetch/load failures is easier.
  - Fixed `test_value_dialog_initialization` by using test worker, as the font propagation was broken under headless environment.
  - reduce test time for:
    - unmark `TestREvoDesignPlugin`, `TestREvoDesignPlugin_TabPrepare` and `TestREvoDesignPlugin_TabVisualize` to run in fast group. Test results from Prepare module is required for downstream test cases of tabs.
    - use `Dunbrack Rotamer Library` for `test_visualize_pssm_ddg`
    - reduced mutant numbers in xlsx and csv files
    - replace test data msa file of `test_run_gremlin`
    - reduced `partial_T` for RFD test
    - reduced `mpnn_num_designs`, `pocket_pssm_residues` for `mutate` and `visualize`
    - reduced click operations of gremlin analysis:
      - `gremlin_monomer_clicks_a2a`
      - `gremlin_monomer_clicks_o2a`
      - `gremlin_homomer_clicks_a2a`
      - `gremlin_homomer_clicks_o2a`
    - reduced `gremlin_topN` from 35 to 5

### Removed
- Py39 related:
  - pairwise implementation and tests, as it can be imported from `itertools` module
- README: drop Py39 from badge
- Driver: 
  - `environ_register`: add/drop environment variables
- Menu:
  - `actionEdit_Configuration`
- I18N:
  - removed hardcoded `language_settings` at `LanguageSwitch`
- UI:
  - `actionSet_Rosetta_Path`
  - `actionSet_GNU_Parallel`
  - hardcoded language actions
- Plugin:
  - removed `save_configuration_from_ui` method due to config handling simplfied
- tests:
  - obsolete tests `tests/cases/UnitTests.py`
- CI:
  - Removed the stale CircleCI pipeline configuration (`.circleci/config.yml`).
- Docs:
  - removed the obsolete API reference and slide decks under `docs/api/` and `docs/slides/`, moving `docs/GCO.md` into `docs/legacy` as part of the new documentation plan.
- Shortcuts: dropped the unused `shortcuts/tools/ESM-1v_DMS_plot.py`.
- Tests:
  - dropped `test_list_all_config_files` case because it is not robust enough when config tree changes during development.


## [1.8.4] - 2025-12-02
### Added
- Customized widget: 
  - `pick_color`: Color picker
  - `AskedValue`: attribute `source` now supports `ColorPicker` with the last value memorized
- test data:
  - caver for future uses.
- test cases:
  - `test_window_pops` for all window pop wrappers
  - `test_version`: test version parses.
- prompts:
  - codex review
  - codex plugin migration
- doc:
  - guide for calling mutate runners in Python
- menu:
  - MD analysis:
    - load b-factors to struture (postprocessing and visualizing from r-bio3d output or Gromacs XVG figure)
    - Data sources:
      - `XvgGromacs`: for Gromacs XVG figure
      - Table file: CSV, TSV, XLS, XLSX
      - Plain text: TXT
      - PDB structure: PDB
- citation:
  - `CitableModuleAbstract`: `get_citable_class` for generating anonymous citable class for functions. 
  - documentation about `CitableModuleAbstract` and `get_cited`
- tools:
  - utils: 
    - `inspect_method_types`: for guessing method types ("InstanceMethod", "ClassMethod", "StaticMethod", "Function")
    - `get_owner_class_from_static`: for gussing owner class of static methods for citation checking.
  - download_registry:
    - `FileDownloadRegistry` now supports `alternative_base_urls` and `retry_count` for a much more certain way of fetching files.
- shortcuts:
  - dialog window pop:
    - support `real_time` mode to run the downstream tasks in real-time mode (triggered by value changes in the window forms)
    - support `Apply Now` button to run the form w/o closing the window
  - `short_residue_ranges`: for residue ranges rewritings.
- file extensions:
  - `XvgGromacs`: for Gromacs XVG figure
- Data Structures:
  - `FloatRange` dataclass that represents a range of floats. start, stop, step. For doublespin only. do not have any realist function.


### Changed
- ci:
  - main workflow test w/ PyMOL v3.1
  - flexible CI timeout limit for windows: 60 minutes
  - install dgl at windows step and macos
  - set var `ENABLE_ROSETTA_CONTAINER_NODE_TEST` to `NO` by default, enable it after docker pull
  - re-arranged matrix labels for clearances
- menu binding:
  - use str for lazy registers
- doc:
  - readme: re-arranged badge table
- tools:
  - utils: 
    - `get_cited`: enhanced for classmethods, staticmethods, normal functions
- citation:
  - `CitableModuleAbstract`: `cite` and `notice` are now classmethods, because citing is not relevant to the module functionality. It should always be citable.
- file extensions:
  - `resolve_extension` to support semi-colon separated extensions from the preset or customized.
  - 

### Fixed
- shortcuts:
  - `rosetta_tasks`: `choices_from` values
  - `ligand_converters`: now use threading in dialog registry scope 
  - `_color_by_mutation`: disable `notify_box` uses in wrapper function 
- test worker:
  - create sub dir of screenshots if not exists
- `REvoDesignWidget`: 
  - now explicitly raise `UnexpectedWorkflowError` when attaching/detaching window under headless mode
  - clean up `bus.ui.open_windows` if its empty
- utils:
  - refactored `cmap_reverser`
- typing hints:
  - gremlin tool
- editor:
  - fix tarball downloading w/ retry and mirror urls.

### Removed
- `REvoDesignWidget`: 
  - removed repetative calls of `detach` and `close`.
- `Makefile`: 
  - unused shortcuts
- Depts: DLPacker in MPS: no performance improvement at all.
- tests:
  - obsolete tests: `test_menu_item`
  - obsolete tests: `test_download_monaco_editor`
- Python vession: 3.9 dropped

### Known Issues
- CI failed on ubuntu w/ PyMOL Open Source v2.5.0, Python 3.10/3.11

## [1.8.3] - 2025-08-19
### Added
- tests:
  - cases
    - `esm1v`
    - `rfdiffusion`
  - conftest:
    - fixed imports like `from tests.conftest import ...`
    - `MEMORY_AVAILABLE_GB` for retienving memory size
    - `fetch_node_config_from_hint`: to handle node config accordingly
    - `mock_rosetta_node_config`: mock node config according to node hint
  - `sidechain_solver`: `TestSidechainSolver`
    - known issue: `DLPacker` failed this case with **segfault** on GitHub CI (py310 & py312, Ubuntu 24.04), which causes segfault
- Makefile: 
  - `install-dgl-linux`: for ci, linux, rfdiffusion
- `sidechain_solver`: `MutateRelax_worker`
- `Mutant`: 
  - `format_as` to format mutation according to the template -> shipped to `RosettaPy==0.2.13` 
- citation items: Rosetta-related functions
- config:
  - `rosetta.opts.general`: support additional options from user. default is `-ignore_unrecognized_res`
- utils:
  - `rosetta_utils`:
    - `is_rosetta_runnable`: global checkers for Rosetta availability, cached as `IS_ROSETTA_RUNNABLE`
    - `read_rosetta_config`: read rosetta options in configurations. default path is `rosetta.opts.general`
    - `ROSETTA_COMMON_CITATION`: for main citations of Rosetta
    - `copy_rosetta_citation`: copy the main citation and update with the given addition citation

### Changed
- tools:
  - Downloading handled by `FileDownloadRegistry` and `DownloadedFile`
- dialog registry yaml:
  - esm1v: `model_alias` -> `model_names`
- depts: 
  - `wandb` for py312 
  - pin `torch` to `<=2.3.0`
  - pin `RosettaPy` to `==0.2.13`
- Rosetta related classes:
  - adapted to API changes in `RosettaPy==0.2.13`
  - wrappers inherit from `CitableModuleAbstract` to add citation
- tests:
  - added all rosetta task tests to class `TestRosettaTasks`
  - `TestRosettaTasks`: output dirs named as `{test_case}/{job_id}/{test_node_hint}` patten
  - reduced test batch size of `TestRosettaTasks` so that tests run faster when parallel workers are used
  - added Rosetta tests to non-`serial` tests, as we mocked out node_hint and node config fetchings.

### Fixed
- `phylogenetics`: 
  - `REvoDesigner`: 
    - `plot_custom_indices_segments`: added dpi settings for clearer image plot.
- shortcuts:
  - fixed frozen window when running `rfdiffusion`
- tests:
  - reduce rosetta related tests to minimum nstruct and iterations
  - default sidechain solver as `Dunbrack Rotamer Library`
- linting:
  - fixed unnecessary comprehensions
  - fixed list as arguments
  - fixed assertions and unused variables
  - fixed string formating w/ f-strings
  - fixed if-else block with early return branch
  - fixed any/all calls with generator expressions instead of tuple/list comprehensions
  - fixed `not A == B` to `A != B`
  - fixed data type construction callings like `tuple()` and `list()` with `()` and `[]`
  - fixed iterable `isinstance` checks by merging as `isinstance(x, (...))`
- security vulnerabilities:
  - fixed `tempfile.mktemp` uses with `tempfile.mkstemp` in `REvoDesignPlugin.reload_molecule_info`
  - fixed `open` calls with out context stack
- `MutantTree`: 
  - fixed `self = mutate_runner.mutated_pdb_mapping(...)` with `updated_self = mutate_runner.mutated_pdb_mapping(...)`
- ci and tests:
  - renamed `GITHUB_CONTAINER_ROSETTA_TEST` -> `ENABLE_ROSETTA_CONTAINER_NODE_TEST`: for clarifying testing conditions
  - renamed `no_rosetta` -> `has_native_rosetta`
  - renamed `NO_NATIVE_ROSETTA` -> `HAS_NATIVE_ROSETTA`

### Removed
- parser: `biolib`-wrapped `pythia-ddg`
- depts: `pybiolib`
- tools: `ModelFetchSetting`
- shortcuts: 
  - fussy code of `ModelFetchSetting` instances from `rfdiffusion` and `esm1v`
- client: 
  - `InterProScaner`: not planned to be used
- unused imports

## [1.8.2] - 2025-08-13
### Added
- shortcuts: 
  - utils: 
    - `get_pymol_plugin_paths`: returns a list of paths to pymol plugins
    - `DialogWrapperRegistry.register`: `use_progressbar`: whether to use the progress bar
- ci: 
  - `shitty-code`: `fuck-u-code` code quality check
  - `deepsource`
  - `semantic-pr-check`: PR checker
  - `schedule-update-actions`: Action version checker
- json:
  - `REvoDesignExtrasTableRich.json`: a rich json to store the meta data of package manager
- `QButtonMatrix`:
  - `shape` property for performance checks
- `tools`:
  - `pymol_utils`: `PYMOL_SETTINGS`, `PyMOLSetting`, `get_pymol_settings` for future uses.

### Changed
- `package_manager`:
  - use a rich json to store the meta data of package manager
  - notification channel
  - `CheckableListView`: now accept `ExtrasGroups` object and `PlatformInfo` as platform filter, with tool tips used as descriptions for each row

### Fixed
- shortcuts: 
  - fixed directory input options on yamls
  - fixed profile design threading - bus error, indroduced from refactor works in v1.8.0
- depts:
  - `colabdesign`
    - `jax<0.6.0,>=0.4.25`
    - `colabdesign==1.1.3`

### Removed
- `package_manager`:
  - depts table
  - extras table

## [1.8.1] - 2025-07-16
### Added
- `dl_weights`: 
  - `ModelFetchSetting` now support optional `version` and `customized_directory`

### Changed
- `package_manager`: 
  - freeze dialog while initializing or task running
  - self upgrade py and ui files in one click not two


### Fixed
- Fixed typing transition of dialog returned values
- shortcut util:
  - `run_wrapped_func_in_thread`: fied typo
- `customized_widgets`:
  - `AskedValueCollection`: fixed typing copy with `multiple_choices` flag
- UI:
  - Tab Prepare: Fixed misleading label of surface exposure cutoff

### Removed
- shortcut yaml:
  - removed `AskedValue.typing=list`, replaced with `AskedValue.multiple_choices` bool

## [1.8.0] - 2025-07-15

### Added
- `FileExtensionCollection`: `from_dict` to create a new collection from a dictionary.
- `logger`: `logger_level_setter`: Set the logging level.
- `shortcuts`:
  - `dialog_hooks`: minimal function utilities for window pops to generate choices in a more complex way
  - `function_utils`: function utilities for tools
  - `registry`: a collection of window pop registry, with window inputs defined in yaml files
  - `utils`: the work horse of management of shortcut window pops from function-yaml-window routine
    - `DialogWrapperRegistry`: a registry for dialog wrappers
    - `resolve_extension`: resolve extension
    - `resolve_dotted_function`: resolve dotted function from yaml description
    - `resolve_choice_from`: resolve choice from yaml description
    - `_build_asked_value`: build asked value object according to yaml description
    - `run_wrapped_func_in_thread`: run wrapped function in thread
- menu: 
  - logger level setter
- `customized_widgets`:
  - `AskedValueDynamic`:  typed dict for dynamic value inputs to shortcut wrappers
  - `AskedValue`: added `multiple_choices` bool to explicitly allow multiple choices
- tests:
  - test marker `skipif` for pmpnn-related tests if `colabdesign` is not installed.

### Changed
- `package_manager`: 
  - `run_command` now use a streaming stdout and stderr manner, meaning the command running is now `live`
- refactored shortcuts as prove-of-concept:
  - `exports`
  - `logger`
  - `rosetta_tasks`
  - `esm`
  - `ligand`
  - `mutation`
  - `represents`
  - `rfdiffusion`
  - `structure`
  - `vina`
- `shortcuts_on_menu`:
  - rewriten redefined function as one-liners
- `shortcuts`: 
  - `vina_tools`: refactored property codes in `CgoBox`
- `customized_widgets`:
  - `QButtonMatrix`:  refactored property codes

### Fixed
- dependencies:
  - `pooch`
  - `nvtx-mock`: now we already have the real package on PyPI!!!!
- Lint:
  - weird linting issues in various places
- ci:
  - pyqt5 and python 3.10


### Removed
- fussy codes of dialog wrappers on:
  - `exports`
  - `logger`
  - `rosetta_tasks`
  - `esm`
  - `ligand`
  - `mutation`
  - `represents`
  - `rfdiffusion`
  - `structure`
  - `vina`
- pre-commit hooks
  - `pygrep-hooks`: dropped `python-no-eval` as the false positives were buggy in torch code
  - `autopep8`: ignored `lambda`-`def` transitions by `--ignore=E731` 

## [1.7.21] - 2025-03-12
### Added
- menu: 
  - RFdiffusion general task running
  - RFdiffusion substrate protential visualizer
- tools:
  - utils: 
    - `timing`: now support units like `sec`, `min`, `hr`, `ms`
  - `package_manager`: 
    - installation extras string filter to drop unnecessary extras
  - `customized_widgets`:
    - `set_widget_value` and `get_widget_value`: now support `MultiCheckableComboBox`
    - `AskedValue`: `choices` now support Callable with None output. if `None` is returned, the choice will be set as None.
    - `ValueDialog`: load and save current input as `recipe` JSON
    - `AskedValueCollection`: class method `from_list`: generate from a `List[AskedValue]`
    - some typing overloads to `set_widget_value` and `get_widget_value` (buggy)
    - `REvoDesignWidget`: a subclass of QtWidget, manager the self life cycle with `ConfigBus`
  
### Changed
- `customized_widgets`: 
  - `ValueDialog`: 
    - refactored as a `QWidget` not a `QDialog`
    - now support recipe JSON drag and drop
  - `AppendableValueDialog`: using widget signal to control the function and window behavior

  

### Fixed
- basic:
  - `FileExtensionCollection`: fixed `basename_stem`: now use string slice, not `rstrip`

### Removed
- `ask_for_values`: no longer needed

## [1.7.20] - 2025-03-11

### Added
- tools:
  - vina tools for box getting/moving/modifying, as well as axes generation. These tools were mainly adapted/refactored/derived from [GetBox Plugin.py](https://github.com/MengwuXiao/GetBox-PyMOL-Plugin/blob/master/GetBox%20Plugin.py) and now can be called as PyMOL command shortcuts.
    - `rmhet`: remove hetatoms
    - `showaxes`: show xyz axes in left bottom corner
    - `getbox`: get an axes-aligned box from a given selection
    - `movebox`: move an existed box
    - `enlargebox`: change the size of an existed box
    - `get_oriented_bounding_box`, `get_pca_box`: get binding box from a given selection, non-axes aligned
  - CGO programing interface, for `pymol.cgo` bindings:
    - `Color`, `Point`, `LineVertex`, `GraphicObject`: basic component/abstract dataclasses of GO objects.
    - `Sphere`, `Cone`, `Cylinder`, `Sausage`, `Triangle`, `TriangleSimple`: basic GO from cgo library.
    - `PseudoCurve`: abstract dataclass for pseduo curve sampling from a series of control points. More sampled points lead to more smooth curves.
      - `PseudoBezier`, ...: pseudo curve cases. Only `PseudoBezier` tested.
    - `PolyLines`: lines and triangles.
    - `Arrow`, `Cube`, `Doughnut`, `Polygon`, `Polyhedron`, `Square`, `RoundedRectangle`: detailed GO classes. `Doughnut` is a  slightly modified version of `pymol.cgo.Torus`
    - `Ellipse`, `Ellipsoid`: curve classes for ellipse and ellipsoid.
    - `TextCharPolygon`: draw a text char as wireframe or sausage-frame.
      - `TextBoard`: draw a piece of text strings as one cgo by callings of `TextCharPolygon`.
    - `GraphicObjectCollection`: a collection class of GO components, which can be used to (re)build objects into a complete (merged) GO object
  - utils:
    - `pairwise`: an implementation of `itertools.pairwise` if run on python 3.9
    - `pairwise_loop`: a derived version of `pairwise` that pairwise the last and the first item as additional pair
- doc: 
  - dev env setup for pyqt typing hints
  - a thread about some cgo details
- an easter egg
- ci: 
  - fixed PyLint badge: lint score
  - Circle CI fixed with:
    - conda image (debian bookworm)
    - fixed display
    - fixed codecov upload
    - fixed testing matrix including:
      - legacy python with pymol 3.0 (py3.9)
      - latest pymol open source (py3.12)
      - latest pymol bundle ^3.1 (py3.10)
      - legacy (v2) pymol open source (py3.11)
      - legacy (v2) pymol bundle (py3.11)
    - pinned pipeline trigger as tag release only
    - caught bug: 
      - Python 3.11/3.12: `undefined symbol: sqlite3_deserialize` caused by conda downgraded sqlite (3.45 -> 3.32)
- menu: 
  - vina tools: 
  - `rmhet` 
  - `getbox` 
  - `alterbox`: `movebox` + `enlargebox`
  - `get_pca_box`
- RFdiffusion integration, with CUDA, MPS and pure-CPU supported
- basic: 
  - `FileExtension`: `basename_stem` to find the stem of a file name if the extension is matched as the longgest one (`.gz` vs `.tar.gz`)
- tools:
  - `rfdiffusion_tools`: `SubstratePotentialVisualizer` a visualizer for RFdiffusion guiding potential `substrate_contacts`
- jsons: added RFdiffusion supports

### Changed
- bootstrap: `reload_config_file`: `overrides` and `return_hydra_config`
- config: rosetta node config now stores at `config/rosetta-node/*`, with `native` as the base one
- moved: 
  - `magician.designers.cart_ddg` --> `tools.rosetta_utils`:
    - `is_run_node_available`
    - `is_wsl_available`
    - `is_docker_available`
- tools:
  - dl_weights: `ModelFetchSetting`: 
    - now support `disable_unflatten` and `need_flatten` 
    - `flatten_archieve`: call `extract_archive` to extract the archieve
  - utils:
    - `extract_archive`: added `*.tar` support
- test:
  - worker: `inject_rosetta_node_config`: now only inject `rosetta.node_hint`
### Fixed
- ci:
  - setup display on GHA

### Removed
- `TestREvoDesign_PyMOL.py` removed bcs it is not used
- ci:
  - GHA:
    - unnecessary environment variables
- global config:
  - removed rosetta node config bcs we have isolated it to `config/rosetta-node`
- test:
  - docker file
  - docker test ci

## [1.7.19] - 2025-02-27

### Added
- `basic`:
  - `abc_singleton`:  `reset_singletons` to reset all subclasses of `SingletonAbstract` gracefully
  - `abc_third_party_module`: `TorchModuleAbstract` to add torch-driven abstract class with a cleanup function.
- `tools`:
  - `package_manager`: `MockLogger` to print logging messages to PyMOL console
- Makefile:
  - `kw-test` and `kw-test-pdb` at help msg
  - `kw-test-pdb`: debug with `pdb` 
- tests:
  - cases:
    - `test_shortcut_dump_sidechains`
    - `setup_minimal_rosetta_db`, `list_fastrelax_scripts`, `extra_res_to_opts`
  - coverage config: 
    - omit `shortcuts/wrappers` 
- dev environment:
  - partially support typing hints against PyQt5 modules

### Changed
- `package_manager`: verbose level slide to control verbose level of package manager in pip installs.
- tests:
  - `conftest`:
    - replace all `reset_instance()` statements with `reset_singletons()`
  - mark:
    - `test_shortcut_dump_fasta_from_struct` : serial
    - `color_by_mutation`: serial
- ci: 
  - use the latest PyMOL open-source version
  - only test with py3.12

### Fixed
- `monaco.server`: if lifespan fails on fetching HTML path `editor.backend.html_dir`, call `ensure_monaco` to setup monaco.
- some tests
- `pyproject.toml`: fixed missing `tqdm`
- `pre-commit` Hook: sent `isort` to the final step.
- `Esm1v`: fixed local checkpoint path

### Removed
- tests:
  - multidesigns: needs a removal or refactor
  - repetative tests on:
    - `rosettaligand`
    - `thermompnn`



## [1.7.18] - 2025-02-21
### Added
- `basic`: 
  - `ThirdPartyModuleAbstract` to describe the abstract class of third party modules, which inherits from `CitableModuleAbstract`
- menu: 
  - `ThermoMPNN`
  - `ESM-1v`(official `ESM2`, or `fair-esm`, renamed as `fair-esm2` on `https://github.com/YaoYinYing/esm2`)
  - `OpenMM-Setup` for basic simulations
- `pyproject.toml`: 
  - added `thermompnn`
  - added `esm2`
  - added `esme`: in draft
  - added `openmm`
- installation JSONs: 
  - added `thermompnn`
  - added `esm2`
  - added `esme`
  - added `openmm`
- `makefile`: 
  - added `thermompnn`
  - added `esm2`
- `utils`: 
  - `require_installed`: check if `cls.installed` is `True` before instantializing it.
  - `get_cited`: run `self.cite()` after objective method has returned.
- `basic`:
  - `server_monitor` 
    - `ServerControlAbstract`: An abstract class for server control.
- `openmm_utils`:
  - `OpenmmSetupServerControl`: A class for controlling OpenMM setup backend.
- `ui_driver`:
  - `StoresWidget` a singleton class to store some dynamic ui data

- `monaco`:
  - `edit_file_with_monaco`:
    - interplay with `MenuActionServerMonitor` from  `StoresWidget().server_switches['Editor_Backend']` to avoid calling the control without LED status change.
- UI: 
  - menu:
    - server controls now have LED to show the status of the server.
      - LED from [Grid Control](https://github.com/akej74/grid-control)
    - server controls now stored at `ConfigBus.stores.server_switches`
    - 

### Changed
- `basic`: 
  - `ExternalDesignerAbstract` and `MutateRunnerAbstract` now inherit from `ThirdPartyModuleAbstract`
- utils: 
  - `mutant_tools`: `extract_mutants_from_mutant_id` now support mutant string expression pattern like `<wt_res><chain_id><resi><mut_res>`
  - `device_picker`: listing of device names that are accessible to DL frameworks like PyTorch.
- Monaco backend:
  - `ServerControl` inherits from `ServerControlAbstract`
- tests: 
  - change `test_edit_file_with_monaco` to use `test_worker` for non-headless mode

### Fixed
- `RelaxWithCaConstraints`: fixed unexpected pymol loadings that should be controlled by `load_to_preview`.
- `quick_mutagenesis`: fixed with latest code

### Removed
- `basic`: removed `ServerProtocol`

## [1.7.17] - 2025-02-18
### Added
- tests: 
  - cases:
    - `color_by_mutation`
    - `pick_design_from_profile`
    - `shortcut_fast_relax`
    - `shortcut_relax_w_ca_constraints`
  - worker:
    - method `inject_rosetta_node_config`: to inject rosetta node config into configurations of config bus. will fallback to native if None is provided.
- Menu: 
  - `shortcut_fast_relax`
  - `shortcut_relax_w_ca_constraints`
- Qt:
  - a Qt wrapper to wrap Qt modules form `pymol.Qt` and use typing hints from `PyQt5`
- Utils:
  - `tools.dl_weights`:
    - `ModelFetchSetting` a basic dataclass to store the settings of downloading weights and do setting up works
  - `tools.rosetta_utils`:
    - `setup_minimal_rosetta_db`: a wrapper function to setup minimal rosetta db if not found
    - `list_fastrelax_scripts`: list all fastrelax scripts in rosetta db

### Changed
- tests:
  - use `pytest.mark` to mark test cases with different performances and behaviors
  - use `pytest-xdist` to run short tests in parallel
  - mark gremlin tests with `very_slow` label and run at the most end of the test run.
- `Makefile`: refactor `make all-test` to run re-organized tests. If any of the tests failed, the whole test run will complete but fail to CI. This helps to avoid CI fake passing due to test failures hidden by semicolons in testing command.
- Qt imports:
  - `from pymol.Qt import ...` --> `from REvoDesign.Qt import ...` to avoid developing time typing check errors
- shortcuts:
  - sorted tools by their functionality
  
### Fixed
- `Makefile`: remove pdb file cleanups statement in `make clean`
- typo in `shortcuts/wrappers/rosetta_tasks.py`

### Removed
- `param_toggle`: 
  - removed `QtEventSignal` Protocol bcs it's no longer used

## [1.7.16] - 2025-02-17
### Added
- ci: 
  - add rosetta docker image pull
- `file_extensions`:
  - `PDB_STRICT`: only `pdb`
  - `SDF`: only `sdf`
  - `RosettaParams`: `*.params`
- menu:
  - refactored arrangements
  - shortcuts:
    - `Rosetta Tools`:
      - `RosettaLigand`
      - `PROSS`
      - `SDF-to-Rosetta Parameters`
- config:
  - hints about `node_config`
- `FileDialog`:
  - methods `browse_multiple_files` for opening multiple files
- `customized_widgets`:
  - `getMultipleFiles`: for opening multiple files
  - `AskedValue`: `source` now support `Files` for '|' separated file names
- tests:
  - conftest: add `RosettaPy` configures

### Changed
- `customized_widgets`:
  - `AskedValue`: 
    - `choices` now accepts Iterables including `KeyView`, `ValueView`, `filter`.
  - `MultiCheckableComboBox`:
    - added methods:
      - `select_all`
      - `unselect_all`
      - `invert_selection`
    - changed methods:
      - `need_action`:
        - now support more action (`select_all`, `unselect_all`, `invert_selection`) 
  - `ValueDialog`:
    - Whether to use MultiCheckableComboBox now depends on `typing=list`, solely.
    - Table Header:
      - `Source` --> `Action`
      - Added action buttons for `select_all`, `unselect_all`, `invert_selection` of multi-checkable combo box
- `package_manager`:
  - `notify_box` and `decide`: now supports detailed messages
- major refactors of `shortcuts` module
  - `menu_shortcuts` --> `shortcuts_on_menu`
  - all wrappers now at `shortcuts.wrappers`
  - `wrappers` are still not testable due to the QDialog widget.

### Fixed

### Removed


## [1.7.15] - 2025-02-07
### Added
- `package_manager`: 
  - typing hints: `notify_box`
- menu: dump sequence

### Changed
- `MenuItem`: support args and kwargs
- renamed for consistency of namespaces:
  - Classes & Props:
    - `MagicianManager` -> `MagicianAssistant`
    - `Magician`: 
      - `magician` -> `gimmick`
      - `magician_manager` -> `magician_assistant`
      - `setup`:
        - `magician_name` -> `gimmick_name`
    - `GREMLIN_Analyser` -> `GremlinAnalyser`
  - Modules:
    | Module | Renamed |
    | :-- | :-- |
    | `FileExtentions` |`file_extensions`|
    | `MultiMutantDesigner`|`multi_mutant_designer`|
    | `external_designer`|`magician`|
    | `FontManager`|`font_manager`|
    | `Mutant`| `mutant`|
    | `MutantTree`| `mutant_tree`|
    |`ClusterRunner`|`cluster_runner`|
    |`sidechain_solver`| `sidechain`|
    | `SidechainSolver`| `sidechain_solver`|
    | `ProfileParsers`| `profile_parsers`|
    | `Evaluator`| `evaluator`|
    | `EvoMutator`| `evo_mutator`|
    | `REvoDesigner`|`revo_designer`|
    | `GREMLIN_Tools`| `gremlin_tools`|
    | `MutantVisualizer`| `mutant_visualise`|
  - Constants:
    | Constant | Renamed |
    | :-- | :-- |
    | `all_runner_c`| `ALL_RUNNER_CLASSES`|
    | `all_parser_classes`| `ALL_PARSER_CLASSES`|
    | `all_designer_classes`| `ALL_DESIGNER_CLASSES`|
    | `all_profile_or_designers`| `ALL_PROFILE_OR_DESIGNERS`|
    | `implemented_runner`| `IMPLEMENTED_RUNNER`|
    | `implemented_designers`| `IMPLEMENTED_DESIGNERS`|
    | `root_logger`| `ROOT_LOGGER`|
- move all menu shortcut functions to module `menu_shortcuts`

### Fixed
- depts: `uvicorn`

### Removed
- `qteditor`: no longer needed
- PSSM-GREMLIN calculator in plugin: no longer needed

## [1.7.14] - 2025-01-04

### Added

- Cluster:
  - summary Rosetta scoring results to ingle csv/xlsx file
- Tests:
  - mutant loading from MS Excel files (Rosetta Mutate&Relax, etc)
  - data: small molecule json file
- Utils:
  - pymol_utils:
    - `renumber_protein_chain`
- Menu:
  - Renumber Residue index: by calling `renumber_protein_chain`

### Changed

- Tab `Visualize`: added mutant loading from MS Excel files files with WT labels

### Fixed
- fixed `DLPacker_worker.run_mutate_parallel` parallel weight setup in calling `run_mutate`

### Removed

## [1.7.13] - 2025-01-03

### Added

- Utils: 
  - `require_not_none`:
    - `fallback_setup`:  Function to call if the attribute is None

### Changed

- Tab `Visualize`: added mutant loading from CSV files with WT labels
- UI: `lineEdit_group_name` -> `comboBox_group_name` to support csv col name
- `MutantVisualizer`: allow `run_mutagenesis_tasks` to handel multi-branch mutant tree
- Test: 
  - `TestWorker`: allow `check_existed_mutant_tree` to return existing mutant tree if the tree check passed
  - tests on visualizing csv with group label
  
### Fixed

- Tests: 
  - Teardown: `SingletonAbstract` subclass resets
    - to avoid instance reused across multiple tests

### Removed

## [1.7.12] - 2025-01-02

### Added
- `ConfigBus`: 
  - Headless mode
  - `require_non_headless`: raise when creating Qt-related calls in headless mode.
- Customized Widgets:
  - `widget_signal_tape`: taping common widgets with specific event signals.
- Tests: 
  - `ConfigBus`: Headless mode
  - Tab `Visualize`: mutant loading from CSV files (mutant and score as colnames)
- Utils:
  - `require_not_none`: A decorator to require non-None values of a specific object attribute.
    - Useful to interrupt unexpected workflow execution.

### Changed
- `ConfigBus`: `get_widget_value`: `converter` is now mandatory.

### Fixed
- Monaco Editor:
  - Failure on setup: mainly due to network censorship.
    - remove remainings
    - interrupt server launching
    - Notify user to set proxy as environment variable if network issues still occur.
    - This would be helpful for users living under GFW.
  - Version tag
    - drop all release candidates with `rc` in tag
- Out-of-date comment in config file `global_config.yaml`
- `ConfigBus`: typing overloads:
  - `get_value`
- Mutant Visualizer:
  - fixed direct loading of mutant object with mut and score columns from mutant file (CSV), etc.
    - by adding `GroupProfileTypeTabVisualize` with a `CallableGroupValues.list_some_blanks`

- `pyproject.toml`: added depts: `psutil`

### Removed

- `ConfigBus`: `value_converter`: no longer needed.
- UI & Evaluator & config YAML:
  - PyMOL's `rock` wrapping

## [1.7.11] - 2024-12-18

### Added

### Changed

- Menu Profile Design:
  - `wrapped_pssm_design` -> 
    - `wrapped_profile_pick_design`: decorator modified wrapper only(input: `**kwargs`)
    - `pick_design_from_profile`: the worker function, moved to `REvoDesign.tools.mutant_tools`
    - menu entry: `menu_pssm_design` -> `menu_profile_pick_design`
- ValueDialog:
  - use `QCheckbox` for bool typing values
- `QButtonMatrix`:
  - Floating hover cross -> box cross
- Monaco
  - Editor:
    - js alert -> message bubbles (`showNotification`)
    - Autosave for unsaved changes (10s)
    - Autorefresh for out-of-date content (10s)

### Fixed
- `mutant_tools`: 
  - `quick_mutagenesis`: fixed out-of-dated `designable_sequences` typing as `RosettaPyProteinSequence`.
  - `extract_mutant_from_pymol_object`: explicitly check if `mutant_score` is a None before updating mutant object with `mutant_score`.
- Tests: 
  - `ValueDialog`: 
    - Multiple widget types and `AskedValue` input
    - Incorporate `MultiCheckableComboBox` usage into `ValueDialog` tests
  - Monaco Server:
    - w|wo token
    - rate limit
    - file whitelists
    - xss-injection protection? 
- **Security Vulnerability**:
  - Monaco Server:
    - Rate limiter (max 5 failed requests per minute)
    - unified token validation
    - XSS-injection prevention
    - File Whitelists for editable and readonly.

### Removed

- Some unnecessary comprehensions
  - Pattern: `var = foo if foo is not None else bar`
    - Replaced with `var = foo or bar`, where `bar` is a fallback value of `foo`
  - Learned from ChatGPT's code.
  - example:
  
    ```python
    >>> d1={x:i for i,x in enumerate('elf')} # normal dict
    >>> d2={} # empty dict
    >>> d3=None # None
    >>> d1 or d2
    {'e': 0, 'l': 1, 'f': 2}
    >>> d2 or d3
    >>> d3 or d2
    {}
    >>> d2 or d3
    >>> d3 or d2 or d1 # `d3(None:False)` -> `d2(empty:False)` -> `d1(not None|empty:True)`
    {'e': 0, 'l': 1, 'f': 2}
    >>> d3 or d1 or d2 # `d3(None:False)` -> `d1(not None|empty:True) -> Stop Checking`
    {'e': 0, 'l': 1, 'f': 2}
    ```

## [1.7.10] - 2024-12-16

### Added
- `MutantTree`: 
  - `has`: check if a mutant full id of mutant obj exists.
- tests: 
  - `customized_widgets`:
    - `MultiCheckableComboBox`, `real_bool`,  `AskedValue`, `AskedValueCollection`, `ValueDialog`
    - `dialog_wrapper`: currently **untestable** since it is challenging with `QDialog` mocks and decorator tests
- `QButtonMatrix`: floating hover cross to locate button coordinates.

### Changed
- `REvoDesigner`: `plot_custom_indices_segments`: now convert table column names to one-indexed integers.

### Fixed

- Profile Design:
  - fixed index error
- main plugin:
  - fixed work directory setup if an empty string is passed in.
- typo:
  - `FileDialog`: `register_file_dialof_buttons` -> `register_file_dialog_buttons`
- `ConfigBus`: fixed notification on non-loaded config. This distinguishes from the case where the config is out-of-dated.
- `GREMLIN_Analyser`: fixed repetative sidechain modeling, now use `MutantTree`s `has` method to check if a mutant with full id exists.
- `ConfigBus`: fixed `get_value` raise where `No molecule is loaded in PyMOL`: check if `molecule` is None or empty string

### Removed

## [1.7.9] - 2024-12-13

### Added

- test case, which were mostly written by prompting with ChatGPT and Tongyi Lingma:
  - basic tests
  - bootstrap tests
  - citation tests
  - editor:
    - monaco: `MonacoEditorManager`, `edit_file_with_monaco`
    - server: `app`, `ServerControl`
  - tools:
    - package_manager: `GitSolver`, `PIPInstaller`, `fetch_gist_file`, `fetch_gist_json`, `filter_sensitive_data`, `get_github_repo_tags`, `run_command`, `solve_installation_config`
    - customized_widgets: `real_bool`
    - utils: `cmap_reverser`, `count_and_sort_characters`, `generate_strong_password`, `get_color`, `random_deduplicate`, `rescale_number`, `timing`,`extract_archive`, `minibatches`, `minibatches_generator`
- prompts:
  - `prompt/o1/docs.md` for docs
  - `prompt/o1/inpaint.md` for code inpainting
  - `prompt/o1/refactor.md` for refactoring code in different temperature factor(larger means more diversity)

### Changed

- renamed:
  - `CitableModules` -> `CitableModuleAbstract`: Explicitly named as an abstract class.
- moved:
  - `src/REvoDesign/citations/CitationManager.py` -> `src/REvoDesign/citations/citation_manager.py`
  - `tests/citations/test_CitationManager.py` -> `tests/citations/test_citation_manager.py`
- refactored `SingletonAbstract`:
  - `singleton_init`: an abstract method for each subclass to implement. This method will be called when the subclass is initialized, helps to avoid repeated code duplication. This method is the **only** one developer should implement in subclasses to replace the original `__init__` method.
  - `derive`: derive a new singleton class from the current one.
  - `initialize`: initialize with given arguments if no instance exists, or update existing instance.
  - Documentation about the lifecycle of the `SingletonAbstract`.
  - Note: after resetting, the original instance will **not** be destructed but left as an **orphan object** in memory, which should **never** be called in following code.
- Makefile: 
  - expand test dir to the full `tests/` directory so that other modules can be tested.
  - keyword tests now use `-vv` for more details with errors.
- refactored: 
  - `QbuttonMatrix` -> `QButtonMatrix`
    - with a subclass `QButtonMatrixGremlin` for gremlin pairs
    - attrs:
      - `df_matrix` (pd.DataFrame): Dataframe representing the matrix.
      - `sequence` (str): Full sequence of residues.
      - `func` (Optional[Callable[[int, int], None]]): Function called on button click.
      - `parent`: Parent widget.
      - `cmap` (str): Colormap name for button colors.
      - `flip_cmap` (bool): Whether to reverse the colormap.
      - `button_size` (int): Size of the buttons.
      - `zero_index_offset` (int): Offset for zero-based indexing. Default is 0.
    - uses `QButtonBrick` as basic button objects, which inherits from `QtWidgets.QPushButton`
      - Button's tooltip is set as black-bg with white text
    - methods:
      - `load_matrix_from_pair` -> now directly uses dataframes and nolonger use matrix (nested lists)
      - `_set_label_size` to set label size
      - `_make_button_tip` to set button tips
      - `map_value_to_color` -> `_map_value_to_color`
      - `report_axises` -> `signal_process`
- `hold_trigger_button`: now restore the original button stylesheets as property `original_style` and restore them back after the job is done.
- `Widget2ConfigMapper.get_button_from_id` now accept `button_type` to accept more button types (eg. `QButtonBrick`).
- `GREMLIN_Analyser`: `mutate_with_gridbuttons` now is a internal function of method `load_co_evolving_pairs`, instead of self method in this class.
- tests:
  - `test_interact.py`: `TestREvoDesignPlugin_TabInteract`: search buttons by `button_type=QButtonBrick` due to the change in `QButtonMatrix`.

### Fixed


### Removed

- installer: install from local git: currently not working.
- Makefile:
  - removed pytest args: `-x` to continue on test case error

## [1.7.8] - 2024-12-11

### Added

- Menu shortcuts:
  - Dump sidechains
  - Environment variables add/drops
  - Real SC
  - PSSM to CSV
  - Color by pLDDT
  - Configuration Edit
  - SMILES conformer sampling, driven by `RosettaPy`'s utils
    - Visualization:
      - Current Window
      - New Window
    - Mode:
      - Single
      - Batch (macos arm64 has issues with joblib-multicores, no idea on how to fix it. This is a known issue with `RosettaPy`)
    - Profile Design (by clicking the button matrix loaded from profile data)
- Text Editors:
  - Qt Text Editor: nearly done (Backup plan)
  - Monaco Editor:
    - Bootstrapable
    - Syntax highlighting
    - Code folding
    - Brower based text editor
      - HTTP(S) and/or runtime-scope token
      - Configured with Singleton `ConfigStore`
      - Driven by FastAPI, `ServerControl` and `MenuActionServerMonitor`
      - Why not `QtWebEngine`?
        - `QtWebEngine` breaks pymol's qt deps, which is observed in the past CI runs.
    - `menu_edit_file` method: re-usable method with a sharing server.
- Customized widgets:
  - `MultiCheckableComboBox`: Multiple checkable items in one widget.
  - `ValueDialog`: Fixed-keys Value input dialog with:
    - **Dynamic "Action" Column**: Shows "Browse" buttons for file inputs (`file=True`).
    - **Column Visibility**: Automatically hides the "Action" column when no file inputs are required.
  - `AppendableValueDialog`: Appendable Value input dialog.
- `real_bool`: Flexible bool type.
- Wrapping Normal Functions into Menu Dialogs.
  - `@dialog_wrapper` to simplify wrapping functions for dialog-based input collection.
  - Workflow:
    1. Define the target function.
    2. Wrap the function using `@dialog_wrapper` with `AskedValue` options.
    3. Create a menu function to handle dynamic inputs and invoke the wrapped function.
    4. Integrate the dialog with file browsing functionality for fields requiring file paths.
    
- `Makefile`: added `kw-test` to support testing with customized keywords.
- `FileExtentions`: added JSON
- installer: 
  - `GitSolver`: support `choco`, not tested
  - `collect_diagnostic_data`: drop token-like data by default
  - `REvoDesignPackageManager` construct menu with sections

### Changed

- UI:
  - refactored menubar
- `src/REvoDesign/tools/customized_widgets.py`:
  - `QbuttonMatrix`: 
    - now accept non-gremlin-pair data (DMS dataset, for example)
    - need to be refactored.
    - button tooltip on mutation info
  - `AskedValue` attrs:
    - `choices`: now accept callable with range, list or tuple output
    - `source`: support:
      - `'File'`: file input opt
      - `'Directory'`: folder input opt
      - `'JsonInput'`: multiple key-value pairs input (saved as JSON to be reusable)
    - `ext`: `FileExtensionCollection`: support multiple extensions.
  - `AskedValueCollection`: 
    - `need_action` to check if any of the values need to be interpreted as file paths or multiple key-val inputs.
    - 

### Fixed
- typos: 
  - `tools/release_tag.sh`: `Dump version` -> `Bump version`
  - `src/REvoDesign/shortcuts/shortcuts.py`: `neiborhood` -> `neighborhood`
- installer:
  - entrypoint print is moved to `__init_plugin__` to silence the output when it's used as a module.
- `expand_range`: `try-except` block to raise invalid input error correctly.
- `REvoDesigner.py`: 
  - raise `NoResultsError` if error occurs with profile data parses.
  - typing hints
- `MenuCollection`: 
  - `try-except` block to skip non-existent widget binding (this happens during developing).
- `ConfigBus`: typing hints of `get_value` method by adding overload methods.

### Removed
- `src/REvoDesign/tools/pymol_utils.py`
  - `PYMOL_VERSION` and `PYMOL_BUILD`: no longer needed.
- `src/REvoDesign/tools/utils.py`:
  - `dirname_does_exist` -> `os.path.isdir(os.path.dirname(...))`
  - `filepath_does_exists` -> `os.path.isfile`

## [1.7.7] - 2024-12-05

### Added

- module docstrings
- Configurations:
  - `environment.variables` to register some environment variables by `register_environment_variables`
- installer: 
  - path: `src/REvoDesign/tools/package_manager.py` to re-use some code
  - `issue_collection`: to fetch diagnostics.
  - updated `hold_trigger_button` with breating animation
  - `solve_installation_config`: fix with path install

### Changed

- UI:
  - menu: now handled by `MenuCollection` and `MenuItem`
- Configuration:
  - when out-of-dated, pop with `notify_box`
- Utils:
  - `src/REvoDesign/tools/system_tools.py`: 
    - `get_system_info`->`check_mac_rosetta2`:  Check if the current environment is running on an Apple Silicon Mac with Rosetta 2.
    - `CLIENT_INFO`: now use system data from `issue_collection` directly

- Tests:
  - Qt tests: reorder by tabs
  - Non-English input tests

### Fixed

- installer:
  - UI file first fetch on the very first time to launch
  - Windows CMD: gbk encoding issue
- CI: pymol-bundle: conda channels
- Depts: now explicityly use `numpy<2`

### Removed

- Utils:
  - `src/REvoDesign/tools/customized_widgets.py`: drop repetative code with imported from `package_manager`
  - `src/REvoDesign/tools/utils.py`:  drop repetative code with imported from `package_manager`

## [1.7.6] - 2024-11-28

### Added

- installer: 
  - ~~add force reinstall option~~

### Changed

- installer:
  - ~~2 JSONS now are hosted at this repository~~
  - all gist-upgradable files are now hosted within the same Gist id `c1e8bfe0fc0b9c60bf49ea04a550a044`
  - self-upgrade: colorful diff summary HTML table

- Makefile:
  - move all gist uploads together
  - `make upload-gists` to upload all gists from local.
- designer: ddg: now silent WSL warning with early checkings on `platform.system()` against non-windows platforms.

### Fixed
- UI-config item: empty value on non-empty field registered as part of `ParamChangeCollections`. This issue is introduced by the refactoring works of `v1.7.3`.

### Removed
- Makefile: 
  - `upload-manager` due to `make upload-gists`
  - `upload-manager-ui` due to `make upload-gists`

## [1.7.5] - 2024-11-26

### Added

- installer:
  - `DEPTS_TABLE_JSON` & `REvoDesignInstaller.remove_depts`: remove dependencies if user requires.
  - `THIS_FILE_URL` and `REvoDesignInstaller.self_upgrade`: self-upgrade
  - `PIPInstaller`: manager of pip-install stuffs
    - `ensurepip`: install package if not installed, only once
    - `install`: install packages
    - `uninstall`: uninstall packages
    - `ensure_package`: ensure one package is installed(by calling `self.install`)
  - `REvoDesignInstaller.proxy_in_env`: Optional `mirror` to supercharge bootstraping of  `pysocks` from mirror. Geronimo!
  - `ALLOWED_PROXY_PROTOCOLS`: explicitly restrict protocols of proxy url.
  - `MenuItem`: menu item dataclasses to register right click menu items
  - `REvoDesignInstaller`: 
    - `add_right_click_menu`: add right click menu for self management
    - `ensure_ui_file`: ensure `ui.file` is installed. Use `upgrade=True` to force upgrade.
    - `upgrade_check` handles upgrade check and upgrade process with user prompts.

### Changed

### Fixed

- installer:
  - self upgrade security checks by `difflib`
  - `REvoDesignInstaller.resize_extra_widget`: new label name `self.installer_ui.label_header` due to this refactoring.

### Removed

- installer:
  - `ensure_lower_pip`, which is deprecated in favor of PEP440 and `pip>=24`.
    - note: this is historical issue of deprecated `pip<24`'s support on local label. So I have to recently updated the pyproject.toml file of PIPPack to satisfy `pip>=24`'
  - `ensure_package`, which was imported at `v1.7.4`
  - ! translated UI code: Installer is now a cloud-upgradable scripts.
- Compiled installer ui py-file


### Known Issues
- installer: 
  - ~~Security: `THIS_FILE_URL` and `UI_FILE_URL` if self upgrades fails~~.

## [1.7.4] - 2024-11-22

### Added

- installer:
  - `ensure_package`: install package if not installed

### Changed

- installer: 
  - extras:
    - now managed at ~~https://gist.github.com/YaoYinYing/37e0e8e73951fab3a12b2d8b81791f6a~~
    - fetch dynamic extras table from gist permalink: https://gist.githubusercontent.com/YaoYinYing/37e0e8e73951fab3a12b2d8b81791f6a/raw
    - permalink guide: https://gist.github.com/atenni/5604615
    - if fetch fails, set the table as empty with a notification.
    - This helps user to fetch dynamic extras without updating the installer itself.
    - An Refresh buttom is now available for re-fetching extras table so the user can refresh it without restarting PyMOL.
  - support socks proxy with `pysocks`
    - protocols: 
      - `socks5://` with DNS resolved by the local machine
      - `socks5h://` with DNS solved by the proxy server. **RECOMMENDED** if DNS leak troubles user. See https://ipleak.net/
    - ref: https://stackoverflow.com/questions/22915705/how-to-use-pip-with-socks-proxy
    - **I know that bootstraping on pip proxy with pip is stupid, but it is a workaround, and `pysocks` is tiny.**
    - This could make sense to users with a VPS SSH access. 
      - example 1: 
        - creating a socks5 proxy at local port <7899>: `ssh -D 7899 -C <user>@<server> -p<port>`
        - use `socks5://localhost:7899` as proxy url
      - example 2:
        - creating a local forwared socks5 proxy to local port <10089>: `ssh -L 10089:localhost:10089 <user>@<server> -p<port>`
        - append jumping hosts option to ssh command if jumping is required: `[-J <jumping-host-1>,<jumping-host-2>,...]`
        - use `socks5://127.0.0.1:10089` as proxy url
        - **Port forwarding with jumping hosts and are NOT recommanded due to unstability of relay connections if users have direct options like example 1 or local proxy tools**
    - explicitly warning if ambiguous proxy url protocol `socks://` is provided
  - `ensure_lower_pip`: now uses `ensure_package` calls

### Fixed

- missing shortcuts due to the refactoring works of PR #43

### Removed

## [1.7.3] - 2024-11-21

### Added
- feat: `hold_trigger_button` now hold buttons with breathing animation to highlight the clicked button.
- feat: UI: configuration load&save shortcuts
  - `Ctrl+S`: save configuration
  - `Ctrl+Shift+L`: load a new experiment
  - `Ctrl+Shift+S`: save as a new experiment
  - `Ctrl+Shift+W`: set working directory
  - `Ctrl+N`: import PyMOL session
- test: data: uploaded to `tests/data`
- `ProfileParserAbstract`: `prefer_lower: bool` attribute for `ParamChangeRegister` to toggle `"ui.header_panel.cmap.reverse_score"`
- `TestWorker`: `pse_snapshot`: save PyMOL session snapshot when needed.
- tests: runs: use `pytest-emoji` because why not 😃


### Changed
- CI:
  - trigger: now on push/pr/release to main
  - CircleCI: use ubuntu image instead to setup the top-down stuff.
- Chore: 
  - `FileExtension`: dataclass of file extension
  - `FileExtensionCollection`: collection of file extensions
  - refact `REvoDesignFileExtentions` dataclass to `FileExtensionCollection` instances
  - `GroupRegistryItem`: dataclass of widget group value registry item
  - `GroupRegistryCollection` as a tuple collection of `GroupRegistryItem` instances
  - `FileDialog`: to handle file IO dialogs
  - `ParamChangeRegistryItem`: to handle parameter change btw 2 widgets
  - `ParamChangeRegister`: to handle parameter change registrations.
  - move `CallableGroupValues` from `ui_driver.py` to `group_register.py`
- `ClusterRunner`: `ConfigBus` is now not a class variable. Instead, it will be called when needed.
- `EvoMutator`: refactored `ChainBinder` using `biopython`
- makefile: `black`: now has been aliased to `pre-commit run --all-files`.

### Fixed
- scorer: `ddg`: drop `selection="not hetatm"` while creating input pd file.
- cache dir: now followed by `set_cache_dir`
- `ConfigBus`:`fp_lock`: 
  - `hold_trigger_button`: add `held` property to buttons that on held.
  - `fp_lock`: skip to release buttons if `held` property is set and as `True`
- lint: some `import-outside-toplevel / C0415` issues in `customized_widgets.py` and `mutant_tools.py`
- lint: some typing hints
- cluster: 
  - ui refreshing interval: 0.15s -> 0.01s
  - mutate&relax now run with progressbar
- QtTests: now use `KeyDataDuringTests` session fixture to handle data downloading and expanding. Just take, no give back.
- `GREMLIN_Analyser`: fix Python Bus error on `gremlin_tool.plot_mtx` with `run_worker_thread_with_progress` on M1 Pro Mac.

### Removed
- CI: 
  - Workflows:
    - GHA: test docker image build 
    - GHA: docker tests
  - badges: 
    - GHA: test docker images, docker tests
    - dockerhub: test docker image size (with repository deleted)
- tests: PyMOL pml tests


## [1.7.2] - 2024-11-14

### Fixed
- fix: installer against file with extras

## ["1.7.1"] - 2024-11-14

### Added

- feat: Allows to automatically register profile-parsers, sidechain solvers and designers if they are installed
- feat: Rosetta Cartesian ddG scorer, driven by `RosettaPy` [Code](https://github.com/YaoYinYing/RosettaPy), [package](https://pypi.org/project/RosettaPy/)
- feat:future: Cluster mutate and relax option toggle
- feat: `Magician`: handles to initialize and destruct designers/scorers
- feat: `ExternalDesignerAbstract`:
  - `name`: the name of the designer
  - `installed`: whether the designer is installed
  - `scorer_only`: whether the designer is a scorer only
  - `no_need_to_score_wt`: whether the designer does not need to score wild-type
  - `prefer_lower`: whether the designer prefers lower scores ~~(future use)~~ 
  - `scorer`: accept `mutant: Union[Mutant, RosettaPyProteinSequence]` instead.
  - `parallel_scorer`: 
    - accept `mutants: List[Mutant], nproc:int=2` which
    - use joblib to scale `scorer`
    - this can be overriden by customized parallelism from the subclasses, eg., `ddg.parallel_scorer`uses the native parallelism from `RosettaPy` to make thread-safe calls to Rosetta

### Changed

- chore: `Widget2ConfigMapper`: `group_config_map` -> `group_register`, with only `Tuple[Callable]` acceptable
- chore: `MutantVisualizer`/`REvoDesigner`/`GREMLIN_Analyser`/`MultiMutantDesigner`: use `magician: Magician = Magician()` to replace attributes like `gremlin_external_scorer`
- chore: move `PushButtons`,`Config2WidgetIds` from `ui_driver` to `widget_link`

### Fixed

- lint: some `import-outside-toplevel / C0415` issues in driver, remains some intra-package imports to avoid cycle import errors

### Removed

- config: Configuration: groups of profile-parsers, sidechain solvers and designers
- feat: Sidechain Solver fallbacks: due to the fact of auto-registration of installed solvers.

### Clues

- To make compatible with getting values from `ConfigBus`(Qt Widges are unpicklable) and `joblib` Parallel, one can initialize the bus a private variable(eg., `bus=ConfigBus()`) in `__init__` method and get all values, instead of a class instance variable(eg., `self.bus=ConfigBus()`). This bus instance will be released after the init is finished.

## [1.6.0] - 2024-11-12

### Added

- Hooks: Pre-commit hooks
- MutateRunnerCollections:
  - `all_runner_c`: Implemented
  - `implemented_runner`: Installed
- `PocketSearcher`: `process_multiple_resn` to support multiple resn selection in PyMOL

### Changed

- Installer: Refactors, Cleanups, Docs, Lints
- Source Dir: move into `src`
- `pyproject.toml`: use `flit_core` instead.
- extras `unittest` -> `test`
- move basic classes to `REvoDesign.basic`
- Installable Plugins classes(Mutant Runner and Designer):
  - attr: str `name` for naming
  - attr: str `installed` for checking if installed via extras
- `Mutant`: 
  - inherits from `RosettaPy.common.mutation.Mutant`
  - use `RosettaPy.common.mutation.Mutation` to replace mutant info dicts.
- `**.designable_sequences`: `RosettaPyProteinSequence` objects now
- `MutateRunnerManager`: deduplicates
- `LanguageSwitch`: now auto registered without hard coding in UI
- Configuration YAML file: `user_data_dir` by default.
- Cache dir: `user_cache_dir` by default.
- CircleCI: upgrade docker image as `latest`

### Fixed

- Logger: 
  - File handles are now optional and can be set as 'AUTO' to avoid spamming.
  - `root_logger` now initialized in `REvoDesign.logger`
- Imports sorted with multiple cyclic imports fixed.

### Removed

- `REvoDesign/__version__.py`: no longer needed for versioning
- `VERSION` alias in `__init__.py`
- `tools/release_tag.sh`: drop `pyproject.toml` version rewriting bcs no longer needed.
- `Widget2Widget`
- `WITH_DEPENDENCIES`
- Configuration YAML: drop sidechain solver groups.

## [1.5.11.post-1] - 2024-08-02

### Changed
- Entry: 
  - GitSolver for Git
  - Eusure pip < 23
- deps: bibtexparser: pin to 2 beta from github tag


## [1.5.11] - 2024-06-14
### Added
- Python 3.12 support.
- Docstrings and comments.
- A timer context manager from AF2 code.
- Test: UI tests with PyMOL GUI. This is currently an experimental feature.
- Budge: PyLint score

### Fixed
- CI: runners and test env images.
- Lints, typing hints and imports.
- Small molecule searching
- Multiple format errors
- Multiple issues with `REvoDesign/tools/mutant_tools.py` while `Mutant` is refactored

## [1.5.10] - 2024-04-17
### Added
- multiple chain binding for `Interact`
- Makefile: 
  - `macos-rosetta-test` for local PyMOL app tests
  - `pymol-test` for PyMOL shortcut tests
- PyMOL bundle V3 tests are passed.
- `IterableLoop`: Iterable looping class.
- Config: `global_config.yaml`: 
  - `work_dir`
  - `chain_binding`
- `CoevolvedPair`: add more attributes.
- README:
  - New architecture design picture for illustrating this plugin, thanks to BioRender.


### Changed
- Singleton `SidechainSolver`
  - `SidechainSolverConfig` for config term management behavior.
  - refactored falling back and refreshing
- Classes in `__init__.py` are now moved out.
- `REvoDesignFileExtentions`: Simplified namings.
- Typing: `GREMLIN_Tools`: `plot_w_a2a` and `plot_w_o2a` now return `tuple[CoevolvedPair]`
- `TestWorker`: support customized PDB fetching.
- `TestREvoDesignPlugin_TabInteract`: simplified test workflow.
- `quick_mutagenesis`: `MutantTree` input only, taking the rest from `ConfigBus` 
- README: image urls change to `github-image-cache.yaoyy.moe` thanks to Cloudflare.
- `MultiMutantDesigner`: `_is_compatible_mutant` only accept Mutant object.

### Fixed
- Bad performance in ui-test, thanks to `pytest-order`
- `MutantVisualizer`: use `designable_sequence` for full sequences.
- `existed_mutant_tree`: `NOT_ALLOWED_GROUP_ID_PREFIX` as filter of group ids
  
### Removed
- `REvoDesignWebSocketClient`: `sidechain_solver`
- `REvoDesignPlugin`: `refresh_sidechainsolver`

## [1.5.9] - 2024-04-08
### Added
- PyMOL shortcuts
  - `pssm2csv`
  - `real_sc`
  - `color_by_plddt`
  - `color_by_mutation`: deduplicated with `biopython` calling
- Citations handled by `CitationManager`
- `CitableModules` abstract:
  - `ConfigBus`: Yes `Hydra` is a citable module.
  - `PythiaBiolib`
  - `Clustering`
  - `ColabDesigner_MPNN`
  - `GREMLIN_Tools`
  - `MutateRunnerAbstract`: all mutate runner are citable
- Profile Parsing handled with `ProfileManager`, `ProfileParserAbstract` and its subclasses: 
  - `PSSM_Parser`
  - `CSVProfileParser`
  - `TSVProfileParser`: unfinished and unvalidated
  - `Pythia_ddG_Parser`

- `TestData`: `post_fetch_spell` for cartoon styles
- `tests/PyMOLTests.pml` for PyMOL commandline prompt tests

### Changed
- moved: `SingletonAbstract`: `REvoDesign.basic`, called by the root.
- `MutantVisualizer`: parsing profile via `ProfileManager`
- use `pymol2.PyMOL()` as mutate context manager in `PyMOL_mutate`. PDB in, PDB out.
- Use `ConfigBus` in `PocketSearcher` and `SurfaceFinder`

### Removed
- `REvoDesignRunnerConfig`: overdesigned
- `PocketSearcherConfig` and `SurfaceFinderConfig`
- `PyMOL_mutate.run_mutate`: `in_place` arg
- `pymol_utils.mutate` and test case `TestPymolUtils.test_mutate`
- `chain_id` arg in `SidechainSolver`

## [1.5.8-post1] - 2024-04-03
### Fixed
- fix ConfigBus: widget signals

## [1.5.8] - 2024-04-01
### Added
- `SingletonAbstract`:  a singleton abstract base class that provides a way to singletonize it's subclasses.
  - `ConfigBus`
  - `REvoDesignWebSocketServer`
  - `REvoDesignWebSocketClient`
- `MutantTree.run_mutate_parallel` to receive a Mutate Runner protocol and perform all mutant objects level mutagenesis operation. 
- `ConfigBus.get_value`: `default_value` to receive a customized default value if the fetched is None
- `SSLCertificateManager`
  
### Changed
- `msgpack` to serialize and deserialize the objects transmitted from host to client, instead of `json`. `Pickle` is still required for dumping and loading.
- `Client` as Client class
- `MeetingRoom` to handle all in-and-out event sof all clients
- `Broadcaster` to handle any ping-and-pongs of socket data
- `REvoDesignWebSocket*.messageDispatcher` to handle message processing according to their data types
- `quick_mutagenesis` is refactored according to `MutantTree.run_mutate_parallel`

### Fixed
- `Mutant.wt_sequences.setter`: `new_wt_sequences` must be at least a `Mapping`. if not `Dict` (`DictConfig`, for example, then convert it by `dict`)
- `PlatformNotSupportedWarning(RuntimeError)`: inherit from `RuntimeWarning` instead.
- typo in `REvoDesigner`: `mutant_obj.wt_sequences`

### Removed
- stderr logging handler

## [1.5.7] - 2024-03-28

### Added
- `ConfigBus.set_widget_value`: if `hard`, override config item.
- `ConfigBus.get_value`: if `reject_none`, raise `ConfigureOutofDateError`.
- Exception Classes in `REvoDesign/issues/exceptions.py` and `REvoDesign/issues/warnings.py`
- Window logo
- `CoevolvedPair`: `i_1` and `j_1` to return `1-indexed` residue index.
- `set_REvoDesign_config_file`: `delete_user_config_tree`. if true, delete users config directory. called by `actionReinitialize`
- `SidechainSolver` Fallback:
  - `MutateRunnerManager`: `get_runner` -> not `_runner_installed` -> `raise issues.DependencyError`
  - `SidechainSolver`: `setup` -> catch `issues.DependencyError` -> `fallback` to produce a fallback copy.

### Changed
- `proceed_with_comfirm_msg_box` -> `decide`
- `GREMLIN_Tools` use reversed cmap from `ConfigBus`
- `GREMLIN_Analyser.mark_pair_state`: use `cmd.orient` to focus on the in-design pair because it is super cool.
- `QbuttonMatrix`use  cmap from `ConfigBus`
- refactored `find_small_molecules_in_protein`: if no hetatm is found in this molecule, consider `(all)`

### Fixed
- `X` residue in GREMLIN pair: `except ValueError` -> `issues.BadDataWarning`
- call DLPacker to initialize with cache dir for Windows
- typo in test dir name
- `find_design_molecules`: raise `issues.MoleculeUnloadedError` if no molecule is found as enabled object
- `find_all_protein_chain_ids_in_protein`
- `make_temperal_input_pdb`: raise `issues.MoleculeUnloadedError` if no molecule is found as loaded object

### Removed
- configure item:
  - `ui.cluster.score_matrix.group`
  - `ui.interact.reverse_score`


## [1.5.6] - 2024-03-26
### Added
- language setting saved in config and try to restore it while lauching.
- `CoevolvedPair` to record pair data
- `CoevolvedPairState` to switch coevolved pair state as pymol bonding.
- `DLPacker_worker`: rescale `n_jobs` if `n_jobs > num_task`

### Changed
- logger levels
- simplified namespaces
- `Mutant.pdb_fp`: reset it if not available.
- `QbuttonMatrix` use `CoevolvedPair` as input to skip csv loading

### Fixed
- GREMLIN coevolved pairs against a target residue index
- `Mutant.get_mutant_sequence_single_chain`: detailed error messages.

### Removed
- `logger_level`
- `setup_logger_level`
- `test_setup_logger_level`

## [1.5.5] - 2024-03-22
### Added
- GitHub Actions workflow dispatch
- `pytest`: add `pytest-execution-timer` and `--durations=0` to list the slowest testcases
- `pyreverse`: skip `UnitTests.py,QtTests.py,TestData.py,QtTestWorker.py`
- `Mutant`: property `pdb_fp` for recording mutated pdb path
- `MutateRunnerAbstract`: an abstact class for mutate runners.
- `run_mutate_parallel` for mutate runners to perform parallel sidechain building from given `Mutant` to pdb path.
- `TestWorker`:
  - `existed_mutant_tree` property
  - `focus_on_tree`
  - `save_pymol_png`: add local focus

### Changed
- updated CI `actions/checkout` to `v4`
- `ConfigBus`: optional ui passing, for headless test
- `REvoDesigner`: call mutate runner to perform global-tree mutate before send sub-mutant-tree to `MutantVisualizer` one branch after another.
- `SidechainSolver` refactored
- `post_installed.set_cache_dir`: read config from `ConfigBus` instead.

### Fixed
- `MutantVisualizer.merge_sessions_via_commandline`: changed output session file.
- shifted pymol object name if loaded from a weird pdb file: `cmd.load(..., object=self.molecule)`
- `extract_smiles_from_chain`: 
  - use empty string as default arguments instead of `None`; 
  - save molecule as `SDF` format to preserve bonds
  - return as list
- `server/pssm_gremlin/pssm_gremlin`: fix `state_file` in `get_results`
  
### Removed
- `MutantVisualizer.parallel_run`
- `assert` statements


## [1.5.4] - 2024-03-14
### Added
- `LanguageSwitch` to switch languages
- config: 
  - `'ui.header_panel.cmap.reverse_score'`
  - `'ui.visualize.multi_design.*'`
  - `designable_sequences` to store all chain:sequence mapping.
- Exception templates
- test counter: `Counter` and its intance in `TestWorker`
- `MutantTree`:
  - `branch_num`: number of all branches
  - `mutant_num`: number of all mutant objects
  - `pop`: pop the last mutant from the last branch
  - `asOneMutant`: return a merged `Mutant`

### Changed
- refactored multi design and its tests
- singletonized `ConfigBus`
- Chinese traslation improved
- `set_window_font` -> `FontSetter` and `FlavoredFonts`
- `Mutant`: `full_mutant_id` -> `raw_mutant_id` (wo score).
- `ConfigBus.get_value` refactored
- `MutantTree.add_mutant_to_branch`: `mutant_info` -> `mutant_obj`
- `SidechainSolver` refactored
- `quick_mutagenesis` refactored 
- `GREMLIN_Analyser` refactored
  
### Fixed
- Unit test fail fast mechanism: any failure will stop the test process. this may save a lot of CI credits.

### Removed
- repetative color reverse checkbox on UI and cfg.
- `ConfigBus`-related arg passings
- runner configs:
  - `ClusterRunnerConfig`
  - `EvalutatorConfig`
  - `MutateWorkerConfig`
  - `SidechainSolverConfig`
  - `GREMLIN_AnalyserConfig`
- `attrs` calls: use `dataclasses` only.
- `memray` dependency in `pyproject.toml`: Linux only

## [1.5.3] - 2024-03-10

### Added
- GHA test runner:
  - daily dev: in docker, ubuntu, 3.9-3.11
  - tag release: bare, ubuntu and windows, 3.9-3.11, 3.11
- Ui translation: Simplified Chinese
  
## [1.5.2] - 2024-03-07
### Added
- UI tips for installer
- new Qt-free `ParallelExecutor`
- `git` setup in installer, via `conda` or `winget`
- UI Tranlation framework based on Qt Linguist
- `Widget2ConfigMapper.find_child`
- `make translate` to rebuild translations
- `pyreverse`; `make reverse`
- badges about `Docker Image Size` and `Codacy`

### Changed
- global root logger and main logger
- old `ParallelExecutor` -> `QtParallelExecutor`
- moving test worker and cases into `REvoDesign/tests`
- elivate `WITH_DEPENDENCIES` to `REvoDesign`
  
### Fixed
- working directory after window lauched
- `find_all_protein_chain_ids_in_protein`: empty chain id
- `TestREvoDesignPlugin_TabInteract`: swapped `col` and `row`
- Typo in `QbuttonMatrix`: `button.setObjectName(f'matrixButton_{row}_vs_{col}')` missing underscore

### Removed
- QtWidgets(`progressBar`) in Designer and Visualiser.


## [1.5.1] - 2024-02-28
### Added
- `Memray` for memory profiling: `https://bloomberg.github.io/memray/overview.html`
- garbage collection
- `Mutant.get_mutant_sequence_single_chain`: `ignore_missing` argument
- `notify_box` for `About` Message box notifications
- `TestWorker`:
  - `test_id`
  - `run_time`
  - `EXPERIMENT_DIR`
  - `save_new_experiment`
  - `sleep`
- `Widget2ConfigMapper.get_button_from_id`: `prefix` argument


### Changed
- Move Gremlin tool to `REvoDesign/phylogenetics`

### Removed
- `REvoDesignPlugin.mutant_tree_coevolved`
- `REvoDesignPlugin.gremlin_tool`
- `REvoDesignPlugin.gremlin_external_scorer`

## [1.5.0] - 2024-02-25
### Added 
- Unit Test docker image for CircleCI
- Experiments loading and saving powered by Hydra: `post_installed.experiment_config`
- UI driver:
  - `PushButtons` for button ids
  - `Config2WidgetIds` for config and widget ids
  - `Widget2ConfigMapper`:
    - `run_button_ids`
    - `buttons`
    - `config_widget_id_map`
    - `config2widget_map`
    - `widget_id2widget_map`
    - `get_button_from_id`
- `ClusterRunnerConfig` -- `ClusterRunner`
- `REvoDesigner`:
  - `mutate_runner`
- `MutateWorkerConfig`, `MutateWorker`, `VisualizingWorker`
- `SidechainSolverConfig`, `SidechainSolver` 
- Qt Test:
  - test cases:
    - `TestREvoDesignPlugin_TabCluster`
    - `TestREvoDesignPlugin_TabVisualize`
  - `TestWorker.click`: return self so that a series of clicking can be done in one liner calls
- `TestData`: more test data

### Changed
- `REvoDesignFileExtentions` to handle file extentions. Immunable dataclass
- UI driver:
  - `Widget2ConfigMapper`: Immunable changes
- `Mutant.__empty__` -> `Mutant.empty` as a property
- Most code of Tab Evalutate -> `Evalutator`
- move to mutant tools:
  - `save_mutant_choices`
  - `write_input_mutant_table`
  - `determine_profile_type`
  - `get_mutant_table_columns`
- use `PocketSearcherConfig` to control `PocketSearcher`
- use `SurfaceFinderConfig` to control `SurfaceFinder`


### Fixed
- arguments in `DLPacker_worker`
- test cases in `UnitTests`

### Removed
- `MutantVisualizer`:
  - `sidechain_solver*`
  - `REVODESIGN_CONFIG`
- `REvoDesigner`:
  - `sidechain_solver*`


## [1.5.0-beta] - 2024-02-21

### Added 
- CircleCI runner
- UI Driver for better configuration experiences
  - `ConfigBus`
  - `CallableGroupValues`
  - more mapping in `Widget2ConfigMapper`
- configuration:
  - detailed inputs as a single experiment for future uses.
- `CLIENT_INFO.nproc`
- `TestWorker`: 
  - `in_which_runner`: use variables to check ci runners
  - `in_ci_runner`: bool check of tester env. if in ci runners, skip pymol rays and screenshots. 
  - `do_typing` for typing text into `lineEdit`
- `Makefile`: `make prepare-test` for testing env prep


### Changed
- moving main file from `__init__.py` to `REvoDesign.py`
- `save_configuration`: `config_name: Union[str, None] = None` argument

### Fixed
- `DLPacker` use `pip-installable-cpu` branch
- reduced test scale on pocket residues

### Removed
- `PSSMGremlinCalculator`: `setup_url`
- `QtWidget` object passings as arguments.
- `get_widget_value`: `QtWidgets.QComboBox`'s `currentIndex()`
- `REvoDesignPlugin.cfg`, use `REvoDesignPlugin.bus.cfg` from `ConfigBus`

## [1.4.3] - 2024-02-17

### Added
- Add QtTest to Github Actions CI. See ref:
  - https://pytest-qt.readthedocs.io/en/latest/troubleshooting.html#github-actions
  - https://github.com/tlambert03/setup-qt-libs
- Qttest `TestWorker` to handle loads/downloads/expands/clicks/tab-switchs/screenshots/pymol-rays/
- Qt Test cases:
  - `Prepare`: pocket, surface
  - `Mutate`: surface-pssm, surface-ddg, surface-mpnn, pocket-pssm
  - `Evaluate`: besthits/manuals
  - `Config`: `PIPPack` with `pippack_model_1`
  - reduced data scales for faster test run

### Changed
- Reduced test cases in `TestData`
- `save_mutant_choices`: Only accept `MutantTree`
- `Mutant`:
  - `wt_sequence` -> `_wt_sequences`
  - properties:
    - `wt_sequences`
    - `mutant_description`
    - `full_mutant_id`
    - `mutant_sequences`
- `MutantTree`:
  - refactored `empty`

### Removed
- failed screenshot copying after `all-test`.

### Fixed
- `Mutant` missing wt sequences from external designer

## [1.4.2] - 2024-02-16
### Added
- QtTest cases:
  - `TestREvoDesignPlugin_TabMutate`
    - `test_pssm_ent_surf`
    - `test_mpnn_surf`
- QtTest tools
  - `navigate_to_tab`: switching tabs
  - `method_name`: fetch caller's method name
  - `save_screenshot`: save screenshots to files
  - `KeyDataDuringTests`: store key data during tests
- `pyproject.toml`:
  - `pooch` and `pytest-qt` for `unittest` extras
- `Makefile`: `ui-test` and `all-test`, for future uses.

### Changed
- `MutantTree`
  - properties:
    - `all_mutant_objects`
    - `all_mutant_branch_ids`
    - `empty`
    - `all_mutants`
    - `all_mutant_ids`
    - `__str__`
    - `__copy__`
    - `__deepcopy__`
  - rename:
    - `extend_tree_with_new_branches` -> `update_tree_with_new_branches`
  - typing hints
- `Mutant`: method`get_short_mutant_id` -> property `short_mutant_id`


### Fixed
- output session from external designer.
- `TestData`: saving paths

## [1.4.1] - 2024-02-15

### Added
- Qt Test driven by `pytest-qt`, a working phenotype
- `post_installed.WITH_DEPENDENCIES`
- `TestData` and `TestDataOnLocalMac`
- `hold_trigger_button` to process trigger button freezing as a context manager.
- server design explained
- Proxy and mirror setup of installer

### Changed
- `get_client_info` -> `CLIENT_INFO`
- `quick_mutagenesis` with `DictConfig`
- `get_system_info` as a `platform.uname_result` parser
- `system_tools.is_package_installed` -> `post_installed.is_package_installed`

### Fixed
- `old_cfg = self.cfg.__deepcopy__` -> `old_cfg = self.cfg.__deepcopy__()`
- calling of `extract_mutants_from_mutant_id` with `chain_id` argument
- freezed installer while calling `fetch_tags`: using `run_worker_thread_with_progress` after `dialog.show()`

### Removed
- `OS_INFO, OS_TYPE`
- `stderr_handler` in `logger`


## [1.4.0] - 2024-02-13

### Added
- Graphic installer/upgrader
- `README.md`: 
  - installation guided
  - extras explained
  - getting started hint


## [1.3.5] - 2024-02-13
### Added
- Configuration saving and loading
  - `save_configuration` 
  - `save_configuration_from_ui`
  - trigger: `ui.actionSave_Configurations`
- `PIPPack` as a alternative sidechain solver
- much more unitest cases.
- `Widget2Widget` as configurations among widget from to another and can be used by `refresh_widget_while_another_changed` calling.

### Changed
- widget-config item mapping -> `Widget2ConfigMapper`
- re-organized config files.
- pin `codecov/codecov-action` from `v3` to `v4`

### Fixed
- in-class `REvoDesigner.visualizer` instance to prevent repetative instantialization of `MutantVisualizer`, handled by `REvoDesigner.setup_visualizer`



## [1.3.4] - 2024-02-05
### Added
- `logging`: 
  - `stdout` up to `INFO`
  - `stderr` up to `ERROR`
  - `file` up to `DEBUG`, `JSON`
  - `notebook` up to `INFO`, `JSON`
- `widget_config_map` to store the relationships of widgets and configs
- `Mutant.__empty__` for empty checking
- `customized_widgets.get_widget_value` for future uses.
- `post_installed.ConfigConverter` for recursively conversion from `omegaconf.DictConfig` to `dict`
- 

### Changed
- refactored `customized_widgets.set_widget_value` by calling `isinstance` methods instead of `type()` checks.
- `post_installed.reload_config_file`: accept config name as argument, for future uses.
- logging level changes of installation check: for `info` to `debug`: `f'REvoDesign is installed in {os.path.dirname(__file__)}'`
- logging level changes of system check: for `warning` to `debug`: `Does it ARMed?`, `Does it Rosetta-ed?`

### Removed
- `str` returns of `extract_mutants_from_mutant_id`
- `absl-py` dependency from non-unit-test installation

### Fix
- `tools/release_tag.sh` on MacOS: using gnu-sed instead of build-in version shipped with MacOS.
- UI: logging level actions: `actionDebug`, `actionWarning`, `actionInfo`.

## [1.3.3] - 2024-02-04
### Added
- `Hydra` configurations
- `set_REvoDesign_config_file`
- `actionReconfigure` for reconfigurations, calling `reload_configurations` and `refresh_ui_from_new_configuration`
- selection arguments in `make_temperal_input_pdb`: `chain_id, segment_id, resn, selection`
- Global `designable_sequences: dict` for all chains of WT sequences.
- New webpage for PSSM/GREMLIN task server.
- WE HAVE A NEW LOGO AND BANNER!
- `macos-14` (apple silicon) runner for unit tests.
  

### Changed
- sidechain solver:
  - `buildin` -> `Dunbrack Rotamer Library`
- Mutant tools:
  - `Mutant.get_mutant_sequence` -> `Mutant.get_mutant_sequence_single_chain` for single chang sequences. use `Mutant.get_mutant_sequences` for all.
  - `extract_mutants_from_mutant_id`: receive `sequences: dict` for multiple chains.
  - `extract_mutant_from_pymol_object`: receive `sequences: dict` for multiple chains.
  - `existed_mutant_tree`: receive `sequences: dict` for multiple chains.
- Dockerized PSSM GREMLIN server image: `yaoyinying/revodesign-pssm-gremlin`.
- GitHub Action runner: use `Mambaforge` for conda env.
- Weight file handling of `DLPacker`

### Fixed
- `.github/workflows/unit_tests.yml`: reversed to `conda-incubator/setup-miniconda@v3` runner scripts to handle conda environments. 
- minor fixes on unit test cases.
- minor fixes on server APIs

### Removed
- `magic_numbers`
- "PRIME", "UniKP" in setup script.
- Windows and self-hosted runners of GitHub Actions.

## [1.3.2] - 2024-01-09

### Added
- Sidechain solver:
  - `buildin`: PyMOL mutagenesis with Dunbrack rotamer library.
  - `DLPacker`: DLPacker.

## [1.3.1] - 2023-12-26

### Added
- Loads of usage info thanks to the [ChatGPT prompt as coding helper](prompt/prompt.md) prompt!
- `get_molecule_sequence`: `keep_missing` option to save missing residue as `X`
- `extract_mutant_from_sequences`: `fix_missing` to restore missing `X` in mutant from external designer.
- Peer view in `Socket` tab
- Unit test cases, WIP.
- `existed_mutant_tree`: fetch existed mutant tree in current session.
- `refresh_user_tree`: Adding Host info and set on the top
- `pybiolib` package for [pythia biolib](https://biolib.com/YaoYinYing/pythia-wubianlab), repo at [here](https://github.com/YaoYinYing/Pythia), docker image at [here](https://hub.docker.com/r/yaoyinying/pythia-wubianlab).
  - `REvoDesign/clients/PythiaBiolibClient.py` as wrapper runner class.
  - `REvoDesign/common/MutantVisualizer.py`: add cloud runner support for Biolib.
  - `REvoDesign/phylogenetics/REvoDesigner.py`: assign sequence to profile parser before parsing.
- `make_temperal_input_pdb`: add `chain id` as option. if `None`, use all chains.
- `MutantVisualizer`: fix residue missing and resi shifting caused by Xtal structures.

### Changed
- UI changes of `Socket` tab. Similar widgets between server and client are now uniq.
- Using UUID as the key of client table.
- Moving `any_posision_has_been_selected` to `pymol_utils.py`
- Broadcast user tree before `refresh_tree_widget`
- `MultiMutantDesigner`: use `existed_mutant_tree` to fetch mutant tree
- `reload_molecule_info`: drop alternative sidechain conformers before structure saving and loading .

### Fixed
- Loop (`127.0.0.1`) as websocket server address
- External designer ProteinMPNN failure if residue is missing in crystal structure model
- Missing chain id argument in `External designer` calling of `REvoDesigner`
- PSSM-GREMLIN run script `REvoDesign_PSSM_GREMLIN.sh`

### Removed
- Mutant tree initializing methods:
  - `fetch_all_mutant_branch_ids`
  - `fetch_all_mutant_in_one_branch`
  - `fetch_mutant_tree`
- class `Mutant`: `equals_to`
- `tests/launch_REvoDesign.pymol.pml`

## [1.3.0] - 2023-12-05

### Added
- External Designer's scorer as GREMLIN design scorer option.
- `randomized_sample` and `randomized_sample_num` for external designers to randomly pick a given number of position in customized indices.
- External scorer in Multi-mutant design.
- External designer/scorer hot switching.
- `refresh_multi_mutagenesis_designer_parameters` for multi-mutagenesis instant controll
- typing notes to `Mutant` class and `MultiMutantDesigner` class.
- Server deployment user guide.
- Color icons for color map.
- [ChatGPT prompt as coding helper](prompt/prompt.md)
- Many usages and code comments, thanks to ChatGPT and a novel prompt example from tldraw's [make-real](https://github.com/tldraw/make-real) project: 
  - https://github.com/tldraw/make-real/blob/a2e9ac80d47bc9a911973e61afe9748db0139090/app/prompt.ts
- Socket tab page for teamwork.
  - self-signed SSL certificates tool, unused: 
    - `generate_ssl_context`
    - `get_certificate`
    - `create_new_certificate`
    - *Dependency Note* for MacOS user:
    ```shell
    # install openssl 
    brew install openssl@1.1
    #link brew-installed ssl library to the system lib path
    ln -s /opt/homebrew/Cellar/openssl@1.1/1.1.1w/lib/libssl.1.1.dylib /usr/local/lib/
    ln -s /opt/homebrew/Cellar/openssl@1.1/1.1.1w/lib/libcrypto.1.1.dylib /usr/local/lib
    ``` 
  - `SocketConector.py`: replaced by `QtSocketConnector`
  - `QtSocketConnector`:
    - `REvoDesignWebSocketServer`
    - `REvoDesignWebSocketClient`
  - BroadCast:
    - MutantTree: mutagenesis-triggered
    - PyMOL view: timer-triggered
- `get_client_info` for collecting sufficient client info when websocket is called:
  - Node name: `platform.uname()`
  - User login: `os.getlogin()`
  - OS type: `platform.uname()`
  - OS build: `platform.uname()`
  - Machine architecture: `platform.uname()`
  - PyMOL version: `pymol.cmd.get_version()[0]`
  - PyMOL build: `pymol.get_version_message()`
  - Python Version: `platform.python_version()`
  - IP addresses: `socket.gethostbyname_ex(socket.gethostname())[2]`
  - PyQt version: `QtCore.PYQT_VERSION_STR`
- `quick_mutagenesis` for applying quick mutageneses from a mutant tree.
- `MutantTree`: 
  - `list_mutants` to list all mutant objects, unused.
  - `diff_tree_from` to create a differential mutant tree.
- UI entry: `traceback.print_exc()` to print error traces if occurs.
- `WorkerThread`: interrupting signal, untested.


### Changed
- UI element changes:
  - `SpinBoxes` for `integers`
  - `DoubleSpinBoxes` for `floats`
  - **`lineEdit_score_minima` and `lineEdit_score_maxima` stay unchanged.**
- `accept_coevoled_mutant` and `reject_coevoled_mutant` -> `coevoled_mutant_decision`
- Capatibility change: `random.shuffle(iterable)` -> `iterable=random.sample(iterable,len(iterable))`. `random.shuffle` is deprecated. See [here](https://docs.python.org/zh-cn/3/library/random.html#random.shuffle)
- `magician.initialize` to transfer time comsuming initializing task to `run_worker_thread_with_progress` so that UI won't be frozen.
- `make_temperal_input_pdb`: reload pdb option `reload` to fix pdb reload while external designer is used to score GREMLIN's design.
- if `group_id.startswith('multi_design')`, don't use this group as mutant tree branch.
- simplified logging message of `is_distal_residue_pair`.
- `determine_system` -> `get_system_info`
- Improved logging message of `check_response_code`
- `MutantVisualizer`: Using `MutantTree` to store mutagenesis info
- `REvoDesigner`: For both profile design and external-designer design, a `MutantTree` will be created followed by calling `MutantVisualizer` with `run_mutagenesis_via_mutant_visualizer`. Thiis `MutantTree` can be called for mutant broadcasting.
  - *Performance Note*: Processor usage will be reduced in parallel run due to mutagenesis one-branch-by-another workflow.
- `PSSMGremlinCalculator`: line breaker in sequence end of fasta file, useful when `cat *.fasta`

### Fixed
- `MutantTree.emtpy` if there is one mutant left.
- Early return if External Designer returns with no designs.
- Duplicated rejection of mutants.
- In-used progressbar is status-restorable in `run_worker_thread_with_progress`. If progress bar has a range and value, they will be stored before used.
- Minor typo.
- Rescoring multi-designs if no score is available.
- Dir deleting issue of `PyMOLSessionMerger`: use `os.remove(session_path)` instead of `shutil.rmtree(os.path.dirname(session_path))`

### Removed
- `run_worker_thread_with_progress` in `MultiMutantDesigner.external_scorer.initialize()` so UI can freeze to fobbid unexpected button clicking events. 
- Magic numbers.
- `REvoDesign/UI/REvoDesign-CommentMutant.ui`

## [1.2.2] - 2023-11-17

### Added
- set `batch` for external designers
- Unit test script: `tests/launch_REvoDesign.pymol.pml`
- Add help msg for `MutantVisualizer.merge_sessions_via_commandline` to enable a more generic session merge interface.
- Add help msg for mutant tools.
- `read_customized_indice` for parsing direct input of customized residue index
- Helper function `count_and_sort_characters`
- `Mutant.equals_to` for future uses.
- `random_deduplicate` for deduplicate designs from ProteinMPNN
- `set_widget_value`: suport `QSpinBox` and `QDoubleSpinBox`
- `Mutant.wt_score`, `Mutant.get_wt_score` and `Mutant.set_wt_score` 
- `traceback.print_exc()` for try-except debugging

### Changed
- Refactor external designers (ProteinMPNN, etc.) to a separate area to allow users to add their own designers in an easier way.
- `does_dirname_exist` -> `dirname_does_exist`
- `check_file_exists` -> `filepath_does_exists`
- UI element changes for trial:
  - `comboBox_nproc` -> `spinBox_nproc`
  - `lineEdit_designer_temperature` -> `doubleSpinBox_designer_temperature`
  - `lineEdit_designer_num_samples` -> `spinBox_designer_num_samples`
  - `lineEdit_designer_batch` -> `spinBox_designer_batch`
- `set_widget_value`: Moving error to intenal function `set_value_error`
- Sending external designer setup and run processes to a worker thread
- the number of designs from external designers will not use `Counter.total()`, because it is a Python 3.10 feature. Using `len(designs["seq"]` is okay.
- Moving `mutate` to `pymol_utils.py`
- `PSSM_profile.py` -> `REvoDesigner.py`
- Moving `read_profile_design_mutations` and `process_mutations` to `mutant_tools.py`
- `PssmAnalyzer` -> `REvoDesigner`
- `REvoDesigner`: 
  - `design_protein_using_pssm` -> `setup_profile_design`
  - Refactoring of `REvoDesigner.process_position` (static function) and -> `REvoDesigner.run_profile_mutagenesis` (class function)
  - `mutagenesis_tasks`: a list of `Mutant` object
- Don not load new created temperal PDB file before mutagenesis

### Fixed
- use `int` as the type of `position` in `extract_mutants_from_mutant_id`
- `rm_aa` as `None` if not given for ProteinMPNN
- Typo in README

### Removed
- Button lock of `lineEdit_input_customized_indices`
- `num_processors`
- `pymol_pssm_script.py`
- `mutant_table_fp` for `REvoDesigner`
- arguments used in `REvoDesigner.plot_custom_indices_segments`:
  - `pop=False` 
  - `annotate=False`


## [1.2.1] - 2023-11-15

### Added
- Multiple mutagenesis design via REvoDesign session-grouped mutants
- `MutantTree.__copy__` and `MutantTree.__deepcopy__` methods.
- `set_window_font` according to OS type. MacOS use apple system default font.
- `reduce_current_session` reduce disabled (discarded) mutant object while saving Mutant Visualizing session.
- `make_temperal_input_pdb` to create a temporary file as input of mutagenesis experiments, instead of the current session.
- `PYMOL_VERSION` for future uses.
- `run_command`
- type `range` and `generator` supports of `set_widget_value`
- `refresh_design_color` to  `MultiMutantDesigner`. 
- coloring `MultiMutantDesigner.design_case_variant` in `greencyan` to show the current design case.
- `proceed_with_comfirm_msg_box`.
- `Mutant.get_mutant_sequence` for reading mutant sequence.
- A wrapper function of `ColabDesign` Framework. `ColabDesigner_MPNN` for ProteinMPNN scoring
- `autogrid_flexible_residue` for future uses.
- **ProteinMPNN design**
- design molecule, chain_id and sequence as class variables
- `Mutant.get_short_mutant_id` for reading short mutant id.
- `set_design_sequence`

### Changed
- `set_widget_value` to `tools.utils`
- temperal session path checking in `find_session_path`
- `merging_sessions` --> `merge_sessions_via_commandline` to avoid segmentation fault. This works!
- fuzzy renames: 
  - `determine_polymer_protein` --> `is_polymer_protein`
  - `determine_small_molecule` --> `find_small_molecules_in_protein`
  - `determine_molecule_objects` --> `find_design_molecules`
  - `determine_chain_id` --> `find_all_protein_chain_ids_in_protein`
  - `determine_nproc` --> `num_processors`
  - `determine_exclusion` --> `fetch_exclusion_expressions`
  - `determine_selections` --> `refresh_all_selections`
  - `check_dirname_exists` --> `does_dirname_exist`
- using `platform.uname()` in `determine_system` to avoid `os.system` command executions.
- `MutantVisualizer.merge_sessions_via_commandline`: Merge only the temperal session (mutageneses). 
- Skip repetative file creating of `make_temperal_input_pdb` if pdb file already exists. 
- `MutantVisualizer.parse_profile`: if any of external scorer is enabled, use it with highest priority.
- `extract_mutants_from_mutant_id` --> `extract_mutant_from_pymol_object`: read `Mutant` object from the PyMOL object content, instead of the object name.
- Massive refactors of `tools.utils` into several tool functions sorted by their functions and dependencies.
  
### Fixed
- `is_distal_residue_pair`
- `determine_chain_id` if sele is not specified.
- Reversible Multi-design.
- `MutantVisualizer.min_score_profile` and `MutantVisualizer.max_score_profile` in PSSM profile.
- `colabdesign` as extra option of **REvoDesign**

### Removed
- `update_REvoDesign_from_repo.sh`

## [1.2.0] - 2023-11-03
### Added
- `self.gremlin_workpath` to handle co-evolved pair results saving.
- `MutantVisualizer. parallel_run`
- Parallel checkboxs, are removed. Instead, parallelism can be toggled by `parallel_run=bool(nproc>1)`.

### Fixed
- Typo of `jum_to_a_mutant`: `jump_to_a_mutant` 
- Initial scene id from `SurfaceFinder`
- Indexes swapping issue of `GREMLIN_Tools`, vialidated by a group of conserved catalytic residue pairs.
  
### Changed
- `activate_focused` 
- Close other Mutant Group if it is not the current one.
- Disable other mutant if it is not the current one in the current group.
- README updated.
- Breaking changes on UI. 
  - reverse the list returned by `determine_nproc` since the first item will be set as the default value.
  - Repetative elements, like `comboBox_design_molecule`, `comboBox_chain_id`, `comboBox_nproc`, `comboBox_cmap` and etc., are re-arranged to the top on tabs and will be shared cross the tabs.
  - `Progressbar` is moved to the bottom of tabs and shared cross these tabs.

  
### Removed
- `MutantTree.last_branch_id` and `MutantTree.last_mutant_id`
- `save_sessionfile` 

## [1.1.11] - 2023-10-31

### Added
- Flexible mutant jumping
- `determine_selections` in order to print pymol selection objects and its residue indexes.
- `is_a_REvoDesign_session` to indicate if the current session is a designed session.
- `shorter_range` and `expand_range` for future uses.
- Logging Level controlling from menu.
- `MutantTree._walk_the_mutants` as an return-only function for mutant tree walking, which is used by `MutantTree.walk_the_mutants`,
- `MutantTree._jump_to_the_best_mutant_in_branch` as an return-only function for mutant tree walking, which is used by `MutantTree.jump_to_the_best_mutant_in_branch`,

### Fixed
- `PyMOLSessionMerger`: use `pymol` instead of `pymol2`
- using `cmd.set('rock', checkBox_rock_pymol.isChecked())` in `set_pymol_session_rock`

### Changed
- Warning if `is_a_REvoDesign_session` but do nothing else.
- `determine_system` to check if the current PyMOL is a Rosetta2-translated X86_64 build (eg. PyMOL official bundle, Rosetta-tranlated conda installed PyMOL, etc.)
- `Darwin_Rosetta`: `multiprocessing` backend in `joblib` 


### Removed
- Testing cases and testing input trigger.


## [1.1.10] - 2023-10-28
### Added
- Coloring of bond for `ce_pair` objects. `marine` for near while `salmon` for far away.
- `comboBox_mutant_ids`, together with `jum_to_a_mutant`
- 
  
### Changed
- `merge_sessions` --> `PyMOLSessionMerger`. Segmentation fault is still there. :-(
- `comboBox_group_ids.currentTextChanged` to monitor branch jumping

### Fixed
- Dataframe transposing in GREMLIN tools if i > j.


### Removed
- `plot_mtx(key='apc')` in `GREMLIN_Tools`
- `pushButton_goto_group`. 

## [1.1.9] - 2023-10-26

### Fixed
- Failure on mutant id switching after `fetch_all_mutant_branch_ids`
- Dataframe transposing in GREMLIN tools if i > j.
- Distance restraint reloading while scanning in GREMLIN tools

### Changed
- `read_enzyme_pockets.py`  --> `PocketSearcher.py`
- `findSurfaceResidues.py`  --> `SurfaceFinder.py`
- Refactored dataframe creating and saving in GRELIN tools.


## [1.1.8] - 2023-10-25
### Added
- `find_all_best_mutants` to find all best mutants in each branch.
- `MutantTree.empty` as a label of empty mutant tree object.
- GREMLIN pair score, distance, wt score, mutant score.
- `use_global_scores` for mutant profile visualizing.
- Upgrating **REvoDesign** via `install_via_pip`.
- Supporting function as `value` of `set_widget_value`. The function will be called and it's return value will be set as `value`.
- Design info reset when reinitializing co-evolution work space.

### Fixed
- GREMLIN mutants in Visualizer
- PWD jumping after compressed file flattening
- PIP installing issue from `file://` source
- Freeze `pushButton_run_visualizing` during running.
- Entrance installation from local file. Treat `source=<src_path>` as a normal path, instead of a git repository.
- `AttributeError` in GREMLIN mrf reloading as a notice.
- Typo in `GREMLIN_Tools`
- GREMLIN design focusing.

### Changed
- UI file layout
- Using `self.topN` as the number of `top_N_pairs` in GREMLIN tool One-vs-All mode, instead of hardcoded 20 pairs.
- Keeping window size fixed

### Removed
- RAR file supports, together with `unrar` dependency. 
- `upgrade_via_pip`
- Demo case.

## [1.1.7] - 2023-10-24

### Added

- `install_REvoDesign_via_pip` entrypoint at PyMOL commandline prompt
- `upgrade_via_pip` for future uses.

### Changed
- CSV as the default of `PSSM_FileExt`
- Disabling auto installlation by `install_REvoDesign_via_pip` if import error occurs.


## [1.1.6] - 2023-10-23
### Fixed
- Dependencies in `pyproject.toml`: The official PyMOL bundle uses Python v 3.7, which is not supported by the latest versions of some packages.

## [1.1.5] - 2023-10-20

### Added
- Saving mutant table using `save_visualizing_mutant_tree` in Mutant visualizing tab
- `reversed_mutant_effect` in `visualize_mutants`
- Supporting mutant fasta file in to in `MutantVisualizer`
- `extract_mutant_info` for future uses.
- Setting None to `visualizer.profile_scoring_df` if it is not available.
- `pyproject.toml`
- Moving **REvoDesign** main program as a pip-installable package. 
  ```shell
  # from local repo
  pip install git+file:///Users/yyy/Documents/protein_design/REvoDesign
  # from remote repo
  pip install git+https://github.com/YaoYinYing/REvoDesign@pip-install
  ```
### Changed
- Using `extract_mutants` in `is_this_pymol_object_a_mutant`
- Using `cmd.get_object_list` in `fetch_all_mutant_in_one_branch`
- Score overriding of `MutantVisualizer`. `self.profile_scoring_df` >> `row[self.score_col]` >> None score

### Removed
- Testing cases, because they are now obsolete.
- Group Id prefix in `fetch_all_mutant_branch_ids`
- Minor cleanings.
- `read_json_file`


### Fixed
- Key error of `get_atom_pair_cst`


## [1.1.4] - 2023-10-17

### Added
- Cmap for PSSM mutant loading
- Jumping between mutant group ids
- Showing WT sidechain lines option in mutant selecting.
- `get_atom_pair_cst` for future uses.
- `renumber_chain_ids` for future uses.
- Cmap reverser.
- Best-hit mutant jumping.
- Supporting ddG-like scoring profile, which should be used reversely.
- Apply profile scoring to `MutantVisualizer`

### Changed
- Don't show hydrogen when selecting mutants.
- Move `convert_PSSM_file_to_csv` in `PssmAnalyzer` to `convert_PSSM_file_to_df` in `MutantVisualizer`
- In `PssmAnalyzer`, `MutantVisualizer.parse_profile` is called to handle profile parsing so that transposed profile is now supported.
- Use cutoff[0] <= Score (Sub-WT) <= cutoff[1]
- Set cutoffs as `float`
- `extract_mutants`: if chain id is given, override to that that parsed via mutant string.
- `MutantVisualizer`: deduplicate code of `create_mutagenesis_objects` and `process_position`

### Fixed
- Segmentation fault while missing input session/structure file.
- Mutant extraction while missing chain id and wt sequence
- Surface residue exclusion while using PyMOL syntax
- Closing ploting instance after drawing is done.
- B-factor altering while score is not available in Mutant Visualizer
- Closing inactivive mutant group
- Disabling `self.mutant_tree_pssm.last_mutant_id` if it equals to `self.mutant_tree_pssm.current_mutant_id`

### Removed
- CheckBoxes of saving mutant table checkpoints and overiding. Set both `True` as default.
- `checkBox_generate_full_pdb` and `checkBox_create_full_pdb`, set `False` as default.
- Duplicated code that performs mutant group open and close. 
- `NestedWorkerThread`, `CallBack`, `parallel_run`
- `handle_calculation_result` from `MutantVisualizer` and `PssmAnalyzer`

## [1.1.3] - 2023-10-09

### Added
- Cmap for Mutant Visualizer
- `setup_url` for `PSSM_GREMLIN_client`

### Removed
- `create_pymol_objects` from `MutantVisualizer`
- Most of functions in `REvoDesign/phylogenetics/pymol_pssm_script.py`

### Changed
- Use `extract_mutants` to handle mutant info in mutation combination.
- Use strick matching re pattern for `extract_mutants`
- Use `MutantVisualizer` for PSSM mutant loading

### Fixed
- Missing GREMLIN co-evolved pair if i>j

## [1.1.2] - 2023-10-09

### Added
- PSSM_GREMLIN Server accessing for phylogenetic calculations
- Progress bar to handle requesting time.
- Status bar description from inputs in UI file.
- `update_REvoDesign_from_repo.bat` for Windows, not tested.

### Fixed
- PSE open file buttom at Load Mut Tab
- `getExistingDirectory`

### Changed
- Use `run_worker_thread_with_progress` to handle requests to avoid freezing windows.
- Set timeout for task posting and cancelling
- rename `test_REvoDesign.sh` as `update_REvoDesign_from_repo.sh`

## [1.1.1] - 2023-10-07

### Added
- `create_mutant_tree_from_list` for MutantTree to create a copy of the tree structure based on checkpoint file


### Changed
- use `mutant_tree_pssm_selected` to store the selected mutant tree structure
- use `remove_mutant_from_branch` and `add_mutant_to_branch` to handle the mutant selection
- mutant acceptance and rejection no longer requires enabling or disabling PyMOL objects, which makes selection clearer.

### Removed
- `refresh_mutants_that_have_been_chosen` function since we changed selected mutants into a new mutant tree.


## [1.1.0] - 2023-10-07

### Added
- Intra-chain interface detection
- A full functional port for performing iterative mutagenesis with a full discription as mutant id with score
- Mutant class to manage mutant objects
- Mutant Table file handle for co-evolved pair designs

### Fixed
- Skip detecting cofactor if not exists
- PyMOL mutagenesis to the only selected chain.
- Mutagenesis while no key or score cols is defined. this would be useful for mutant table in pure txt.
- Mutagenesis with implicit chain identifier.
- Multiple button locking.
- Fix file handle mode of mutable txt button 

### Changed
- Fetch repo path by dirname in test Scripts 
- Move `get_color` as a public function in `utils`
- Use `stick_radius` to present co-evolved pairs
- Use explicit mutant description in Mutagenesis from PSSM profile
- Use Mutant object as the mutant id value of Mutant tree.
- Minor changes of the order of `MutableFileExt`.


### Removed
- Mutant table checkpoint saving function. Replaced with mutant table saving function.
- QProgressBarton, which is no longer needed for now

## [1.0.0] - 2023-09-24

### Added
- Added surface residue analysis tools for SASA calculation and pocket identification.
- Implemented mutant loading from CSV files with customizable rejections and preferences.
- Introduced human knowledge supervision for mutant selection within the PyMOL interface.
- Included scale reduction capabilities for low-throughput wet-lab validations via sequence clustering.
- Enabled the visualization of mutant tables in PyMOL.
- Introduced co-evolution analysis using GREMLIN Markov random field profiles for effective mutant identification.
