# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
