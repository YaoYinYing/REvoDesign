# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Coloring of bond for `ce_pair` objects. `marine` for near while `salmon` for far away.
  
### Changed
- `merge_sessions` --> `PyMOLSessionMerger`. Segmentation fault is still there. :-(

### Fixed
- Dataframe transposing in GREMLIN tools if i > j.


### Removed
- `plot_mtx(key='apc')` in `GREMLIN_Tools`

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
