# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2023-10-07

### Add 
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


### Fixed

### Changed

### Removed

