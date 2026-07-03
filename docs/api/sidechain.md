# Sidechain

Sidechain packing and mutation runner system for generating mutant protein structures.

## Architecture Overview

The sidechain system uses a two-layer design:

1. **SidechainSolver** — A singleton that manages configuration and lifecycle. It reads the desired solver name, repack radius, and model from ConfigBus, then instantiates and caches the appropriate `MutateRunnerAbstract` subclass.
2. **MutateRunnerAbstract** — An abstract base class defining the interface for mutation runners. Concrete implementations (discovered via `build_plugin_registry` from `REvoDesign.sidechain.mutate_runner`) each wrap a specific sidechain packing tool.

## SidechainSolver

Singleton that manages sidechain packing workflows. Reads configuration from the UI (solver name, repack radius, model), creates the appropriate mutate runner via `MutateRunnerManager`, and provides a `refresh()` method to reconfigure when settings change.

::: REvoDesign.sidechain.sidechain_solver.SidechainSolver
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## SidechainSolverConfig

Immutable configuration dataclass holding the solver name, repack radius, and model. Supports change detection via `reconfigured()`.

::: REvoDesign.sidechain.sidechain_solver.SidechainSolverConfig
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## MutateRunnerAbstract

Abstract base class for mutation runners. All mutation tools must implement `run_mutate()` (single mutation) and `run_mutate_parallel()` (batch mutation). Integrates with the citation system via `CitableModuleAbstract`.

::: REvoDesign.basic.mutate_runner.MutateRunnerAbstract
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## MutateRunnerManager

Dataclass that discovers and instantiates mutation runners by name. The `get()` static method looks up a runner class from the auto-discovered registry and returns an instance initialized with the provided PDB file, model, and radius.

::: REvoDesign.sidechain.sidechain_solver.MutateRunnerManager
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Runner Registry

Auto-discovered mutation runners indexed by name. Created at import time by `build_plugin_registry` scanning `REvoDesign.sidechain.mutate_runner` for `MutateRunnerAbstract` subclasses.

### Available Runners

The following runners are discovered from `REvoDesign.sidechain.mutate_runner`:

- **DLPacker_worker** — Mutation using DLPacker (deep learning sidechain packing)
- **PIPPack_worker** — Mutation using PIPPack (rotamer-based packing)
- **Dunbrack_worker** — Mutation using the Dunbrack rotamer library
- **DiffPack_worker** — Mutation using DiffPack (diffusion-based sidechain packing)
- **RosettaMutateRelax** — Mutation and relaxation using Rosetta

### Registry Access

::: REvoDesign.sidechain.sidechain_solver.RUNNER_REGISTRY
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.sidechain.sidechain_solver.ALL_RUNNER_CLASSES
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.sidechain.sidechain_solver.IMPLEMENTED_RUNNER
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Usage from Python

See `src/REvoDesign/sidechain/mutate_runner/README.md` for usage examples.

Basic workflow:

```python
from RosettaPy.common.mutation import RosettaPyProteinSequence
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id
from REvoDesign.sidechain.mutate_runner import DLPacker_worker

pdb_file = '8x3e.cleaned.pdb'
seq = RosettaPyProteinSequence.from_pdb(pdb_file, True)

mut_lists = ['AQ122A', 'AQ266A', 'AL72M', 'AL72M_AQ122A', 'AQ122A_AQ266A']
mut_objs = [extract_mutants_from_mutant_id(m, seq) for m in mut_lists]

worker = DLPacker_worker(pdb_file, 6)
pdb_paths = worker.run_mutate_parallel(mut_objs, 6)
```
