# Common

Shared data structures and utilities used across REvoDesign.

## Mutant

The `Mutant` class extends RosettaPy's `Mutant` base, adding REvoDesign-specific properties for scoring, PDB file path management, and description.

::: REvoDesign.common.mutant.Mutant
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## MutantTree

A hierarchical tree structure for organizing and navigating mutants across multiple named branches. Each branch holds a dictionary of `Mutant` objects keyed by unique mutant ID. Supports navigation (walk forward/backward), best-mutant jumping, tree comparison (diff), and parallel mutation execution.

::: REvoDesign.common.mutant_tree.MutantTree
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### Supporting Types

::: REvoDesign.common.mutant_tree.MutantDict
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.common.mutant_tree.MutateRunner
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## MultiMutantDesigner

Interactive multi-mutant design workflow controller. Reads parameters from ConfigBus and manages the step-by-step process of selecting compatible mutants from a design pool, evaluating them via an external scorer, and exporting the final design variants.

::: REvoDesign.common.multi_mutant_designer.MultiMutantDesigner
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## MutantVisualizer

Workhorse for creating PyMOL visualizations of designed mutants. Parses mutation data from various file formats (CSV, TSV, FASTA, Excel), computes scores via profile scoring or external scorers, runs sidechain repacking, and produces colored PyMOL sessions showing the mutated residues.

::: REvoDesign.common.mutant_visualise.MutantVisualizer
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Profile Parsers

Parser classes for loading mutagenesis profiles from various file formats.

### ProfileParserAbstract

::: REvoDesign.common.profile_parsers.ProfileParserAbstract
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### PSSM_Parser

::: REvoDesign.common.profile_parsers.PSSM_Parser
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### CSVProfileParser

::: REvoDesign.common.profile_parsers.CSVProfileParser
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### TSVProfileParser

::: REvoDesign.common.profile_parsers.TSVProfileParser
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### ProfileManager

::: REvoDesign.common.profile_parsers.ProfileManager
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## File Extensions

Predefined `FileExtensionCollection` instances defined in `REvoDesign.common.file_extensions` for common file types used throughout the UI. Each instance bundles related extensions with human-readable descriptions for Qt file dialogs.

### Collections

| Name | Extensions | Purpose |
|------|-----------|---------|
| `Session` | `.pze`, `.pse` | PyMOL sessions |
| `Mutable` | `.txt`, `.mut.txt`, `.csv`, `.tsv`, `.xlsx`, `.xls` | Mutant tables |
| `PDB` | `.pdb`, `.ent`, `.cif`, `.mmcif` | Protein structures |
| `PDB_STRICT` | `.pdb` | Strict PDB only |
| `MOL` | `.mol`, `.sdf` | Small molecule files |
| `SDF` | `.sdf` | SDF files |
| `PSSM` | `.csv`, `.pssm` | Position-specific scoring matrices |
| `CSV` | `.csv` | CSV files |
| `MSA` | `.fas`, `.fasta`, `.a3m` | Multiple sequence alignments |
| `A3M` | `.a3m` | HH-suite A3M format |
| `TXT` | `.txt` | Plain text files |
| `Any` | `* *` | Catch-all filter |
| `Compressed` | `.zip`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz`, `.tar.xz`, `.txz`, `.tar`, `.gz`, `.bz2`, `.xz`, `.rar` | Archives |
| `PickledObject` | `.pkl` | Pickled Python objects |
| `YAML` | `.yaml` | YAML config files |
| `JSON` | `.json` | JSON files |
| `RosettaParams` | `.params` | Rosetta parameter files |
| `Pictures` | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.tif`, `.svg`, `.pdf` | Images |
| `XvgGromacs` | `.xvg` | Gromacs XVG format |

### Supporting Classes

::: REvoDesign.basic.FileExtension
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.basic.FileExtensionCollection
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### Resolver

::: REvoDesign.basic.extensions.resolve_extension
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
