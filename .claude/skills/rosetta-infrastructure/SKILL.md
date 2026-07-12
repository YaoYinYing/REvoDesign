---
name: rosetta-infrastructure
description: Rosetta/RosettaPy and sidechain-solver conventions for REvoDesign. Use when writing Rosetta tasks, adding sidechain solvers, configuring nodes, or touching the scoring/design pipeline. RosettaPy source: https://github.com/YaoYinYing/RosettaPy.
when_to_use: Rosetta task code, sidechain solver, node config, scorer/designer subclass, MutateRunnerAbstract, ExternalDesignerAbstract, ScoreClusters
---

# Rosetta + Sidechain Infrastructure

## RosettaPy library ([github.com/YaoYinYing/RosettaPy](https://github.com/YaoYinYing/RosettaPy))

REvoDesign wraps RosettaPy (PyPI: `RosettaPy`, v0.2.15), a Python package that provides a typed interface to Rosetta binaries. The library handles binary discovery, node dispatch (native/Docker/WSL/MPI), task composition, and parallel execution via joblib.

### Core class: `Rosetta` (dataclass)

```python
from RosettaPy import Rosetta, RosettaScriptsVariableGroup
```

Key attributes:
- `bin: RosettaBinary | str` — binary to run (e.g. `"rosetta_scripts"`, `"relax"`, `"cartesian_ddg"`). Resolved by `RosettaFinder` which searches `$ROSETTA_BIN`, `ROSETTA3/bin`, `ROSETTA/main/source/bin/`, or `PATH`.
- `flags: List[str]` — Rosetta flag files (`@file`). CRLF auto-converted to LF.
- `opts: List[str | RosettaScriptsVariableGroup]` — command-line options. Can mix plain strings and variable groups.
- `use_mpi: bool` — auto-set based on node type.
- `run_node: Native | MpiNode | RosettaContainer | WslWrapper` — execution backend. Default: `Native()`.
- `job_id: str` — namespace for output subdirectories.
- `output_dir: str` — root output directory. If set, auto-creates `-out:path:pdb` and `-out:path:score`.
- `save_all_together: bool` — if True, all outputs in `all/`; otherwise split into `pdb/` and `scorefile/`.
- `isolation: bool` — if True, each task runs in its own temp working directory (threadsafe).

Key methods:
- **`compose() -> List[str]`**: builds full command: binary path → `@flag` files → string opts → expanded variable groups → output paths → `-mute all` (if not verbose).
- **`run(inputs=None, nstruct=None) -> List[RosettaCmdTask]`**: dispatches tasks.
  - **Native path**: expands inputs into per-input tasks (or nstruct-per-input), runs via `joblib.Parallel`.
  - **MPI/Container/WSL path**: appends inputs + `-nstruct N` to one flat command via `apply()` context manager (may prepend `mpirun`).

### RosettaScriptsVariableGroup

Two frozen dataclasses for passing variables to Rosetta XML protocols:

- **`RosettaScriptsVariable(k, v)`**: single `-parser:script_vars k=v` pair. `.aslist` returns `["-parser:script_vars", "k=v"]`.
- **`RosettaScriptsVariableGroup(variables)`**: collection of variables. Key methods:
  - `.aslonglist` → flattened `["-parser:script_vars", "k1=v1", "-parser:script_vars", "k2=v2", ...]`.
  - `.asdict` → `{k: v, ...}`.
  - `.from_dict(d)` → classmethod constructor.
  - `.apply_to_xml_content(xml)` → replaces `%%key%%` placeholders in XML protocol strings.

### RosettaCmdTask

`RosettaPy.utils.task.RosettaCmdTask`:
- `cmd: List[str]` — the full command line.
- `task_label: Optional[str]` — if set, enables isolation and determines `runtime_dir`.
- `run()` → `subprocess.Popen(cmd)`.

### Node system

**`node_picker(node_type, **kwargs) -> NodeClassType`** factory in `RosettaPy.node`:

| hint | Node class | Notes |
|---|---|---|
| `"native"` | `Native(nproc=4)` | joblib.Parallel |
| `"docker"` | `RosettaContainer(image="rosettacommons/rosetta:latest", prohibit_mpi=True)` | Docker SDK |
| `"docker_mpi"` | `RosettaContainer(image="rosettacommons/rosetta:mpi", mpi_available=True)` | Docker + MPI |
| `"mpi"` | `MpiNode(nproc=4)` | mpirun; `from_slurm()` classmethod for SLURM |
| `"wsl"` | `WslWrapper(rosetta_bin=..., prohibit_mpi=True)` | WSL |
| `"wsl_mpi"` | `WslWrapper(rosetta_bin=..., mpi_available=True)` | WSL + MPI |

Kwargs are consumed dynamically; unknown kwargs silently ignored. Use `node_picker(hint, **config_dict)`.

### App classes (RosettaPy.app)

- **`ScoreClusters`** (`mutate_relax.py`): mutation scoring on clusters. `score(branch, variants, opts)` → per-variant `Rosetta(bin="rosetta_scripts")`. Generates `muttask`, `mutmover`, `mutprotocol` script vars. `run(cluster_dir, opts)` → reads `c.*.fasta` files, maps to variants, calls `score()` per cluster.
- **`FastRelax`** (`fastrelax.py`): relax via `relax` binary. Uses `partial_clone()` to fetch scripts if `$ROSETTA3_DB` not set. `run(nstruct, default_repeats)` → `RosettaEnergyUnitAnalyser`.
- **`CartesianDDG`** (`cart_ddg.py`): `relax(nstruct)` then `cartesian_ddg(input_pdb, mutfiles, mutants, use_legacy, ddg_iteration)` using `cartesian_ddg` binary. Returns `pd.DataFrame`.
- **`PROSS`** (`pross.py`): three-phase: `refine()` → `filterscan()` → `design()`. Uses `RosettaScriptsVariableGroup` for constraints, PSSM, fixed residues.
- **`RosettaLigand`** (`rosettaligand.py`): ligand docking with script vars for box, grid, chain.
- **`supercharge()`** (`supercharge.py`): standalone function, returns `List[RosettaCmdTask]`.

### Mutation module (RosettaPy.common.mutation)

- **`Mutation(chain_id, position, wt_res, mut_res)`**: frozen. `__str__` → `"A123B"`. `to_rosetta_format(jump_index)` → `"A 123 B"`.
- **`Chain(chain_id, sequence)`**: frozen.
- **`RosettaPyProteinSequence`**: collection of Chains. `from_pdb()`, `from_dict()`, `calculate_jump_index()` for cross-chain indexing.
- **`Mutant`**: list of Mutation + `wt_protein_sequence`. `as_mutfile` property for Rosetta mutfile format.

### Utility: partial_clone()

`RosettaPy.utils.repository.partial_clone(repo_url, target_dir, subdirectory_to_clone, subdirectory_as_env, env_variable)`:
- Shallow-clone + sparse-checkout a subdirectory from `RosettaCommons/rosetta`.
- Sets `os.environ[env_variable]` to local path.
- Used by REvoDesign's `setup_minimal_rosetta_db()` for database resolution.

### Analysers

- **`RosettaEnergyUnitAnalyser`** (`analyser/reu.py`): reads `.sc` score files into DataFrame. `.best_decoy` → `{"score": float, "decoy": str}`. `.top(rank)` → sorted tuple.
- **`RosettaCartesianddGAnalyser`** (`analyser/ddg.py`): parses JSON/`.ddg` output → DataFrame with `ddG_cart`, `Accepted`, `cutoff`.

---

## REvoDesign's Rosetta layer

### Node-based execution

REvoDesign wraps the RosettaPy node system. Node types: `"native"`, `"docker"`, `"docker_mpi"`, `"mpi"`, `"wsl"`, `"wsl_mpi"`.

- Configs: `config/rosetta-node/<hint>.yaml`, loaded via `reload_config_file("rosetta-node/<hint>")`.
- Keys: `nproc`, `prohibit_mpi`, `mpi_available`, `image` (docker), `distro`/`user`/`rosetta_bin` (WSL).
- Docker configs use `defaults: [native]` for Hydra composition.
- Node hint flows through `ConfigBus` at `rosetta.node_hint` — change in UI or `main.yaml`.
- `read_rosetta_node_config()` raises `ConfigureOutofDateError` if config missing.
- Refresh node config before each parallel run (node state can change between runs).
- `is_rosetta_runnable()`: iterates all nodes, returns True if any is available. Cached at module level (`IS_ROSETTA_RUNNABLE`).

### RosettaPy integration pattern

REvoDesign's `RosettaMutateRelax` extends `ScoreClusters`:

1. Subclass `RosettaPy.app.mutate_relax.ScoreClusters`.
2. Construct `Rosetta(bin="rosetta_scripts", flags=..., opts=[..., rsv_group], output_dir=..., job_id=..., run_node=node)`.
3. Per variant: `RosettaScriptsVariableGroup.from_dict({"muttask": ..., "mutmover": ..., "mutprotocol": ...})`.
4. Call `rosetta.run(inputs=branch_tasks)` — per-variant dispatch with `-out:prefix`, `-out:file:scorefile`.
5. `enable_progressbar=False` — joblib handles parallelism, RosettaPy progress bar would conflict.

### Rosetta config reading (REvoDesign)

- `read_rosetta_config()`: `ConfigBus().get_value("rosetta.opts.general", str)` split → option list.
- `read_rosetta_node_config()`: reads `rosetta.node_hint`, loads `rosetta-node/<hint>.yaml`, merges with `nproc` from `ui.header_panel.nproc`.
- Ligand params: `extra_res_to_opts()` converts pipe-separated `.params` paths → `-extra_res_fa`/`-extra_res_cen` flags. Validates existence and suffix.

### Rosetta database resolution

`setup_minimal_rosetta_db()` three-tier lookup:
1. `$ROSETTA3_DB` env var.
2. Derived from `$ROSETTA_BIN` parent's `database/`.
3. `partial_clone()` into `user_cache_dir`.

---

## Sidechain solver plugin system

`build_plugin_registry(base_class=MutateRunnerAbstract, package="REvoDesign.sidechain.mutate_runner")` auto-discovers runner subclasses.

### MutateRunnerAbstract interface

Every runner subclass MUST define:
- `name: str` — e.g. `"DiffPack"`, `"DLPackerPytorch"`, `"Rosetta-MutateRelax"`.
- `installed: bool` — computed at import time via `is_package_installed()` or `IS_ROSETTA_RUNNABLE`.
- `__init__(self, pdb_file, radius, use_model)` — loads per-runner config from `reload_config_file("sidechain-solver/<name>")`.
- `run_mutate(mutant)` — single mutant.
- `run_mutate_parallel(mutants, nproc)` — parallel batch. Python solvers use `joblib.Parallel`; Rosetta uses `rosetta.run(inputs=...)`.
- `reconstruct()` — repack without mutations.
- `__bibtex__: dict` — BibTeX citation. Use `copy_rosetta_citation()` for Rosetta-based runners.

Class must be importable from `REvoDesign.sidechain.mutate_runner`.

### Per-runner config

Config under `config/sidechain-solver/<name>.yaml`, loaded by `__init__`. Keys typically at `sidechain-solver.<name>.inference.*`:
- **DiffPack**: `device`, `backend`, `hetero_policy`, `fast`, `memory_mode`, `cache_root`, `config`. `_ensure_cache_ready()` validates schedule cache.
- **DLPackerPytorch**: `device`, `weights_prefix`, `rotamer_policy`. Sets `$DLPACKER_PRETRAINED_WEIGHT`.

`SidechainSolver` singleton wraps registry. `setup()` creates temp PDB via `make_temperal_input_pdb()`. `refresh()` compares config, re-initializes if changed.

### RosettaMutateRelax specifics

Extends `RosettaPy.app.mutate_relax.ScoreClusters` (not `MutateRunnerAbstract` directly). Uses Rosetta XML protocols + `RosettaScriptsVariableGroup` per variant. `run_mutate_parallel` refreshes node config before each run.

---

## Scoring / MGOP pattern

`Magician` (singleton) owns `gimmick` (active scorer/designer). `ExternalDesignerAbstract` base with `scorer(mutant)` and/or `designer(**kwargs)`.

- `Magician.setup(name_cfg_item)` reads config to pick gimmick, initializes/pre-heats it.
- ConfigBus key `ui.interact.use_external_scorer` drives switching.
- `__bibtex__` on every scorer/runner for auto-generated citations.

### OpenKinetics scorers

27 dynamically-generated subclasses of `OpenKineticsScorerAbstract` (factory via `type()`). Each has:
- `built_in_defaults` (closure-created classmethod).
- `prefer_lower` (True for Km, False otherwise).
- SQLite per-variant cache (SHA256: sequence + substrate + method + prediction type).
- `parallel_scorer` batches all mutants into single API call (not joblib — deliberate design).
- Requires substrate SMILES; `resolve_substrate_metadata()` extracts from PDB metadata if not provided.
- 5-tuple registration: `(class_name, display_name, method, prediction_type, bibtex_key)`.

---

## Citation management

`ROSETTA_COMMON_CITATION` — module-level BibTeX dict. `copy_rosetta_citation()` shallow-copies and updates with subclass-specific citations. Set `__bibtex__` via this for Rosetta-based runners.
