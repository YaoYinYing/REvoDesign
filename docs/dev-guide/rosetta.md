# Rosetta Integration

REvoDesign integrates with the [Rosetta](https://rosettacommons.org/) molecular
modeling suite through [RosettaPy](https://github.com/YaoYinYing/RosettaPy), a
Python package that wraps Rosetta command-line binaries across local, Docker, MPI,
and WSL-based compute nodes.

> [!IMPORTANT]
> **RosettaPy is NOT PyRosetta.** PyRosetta is a Python binding to Rosetta's C++
> objects. RosettaPy is a subprocess wrapper around the Rosetta command-line tools.
> If you're looking for PyRosetta, see [pyrosetta.org](http://www.pyrosetta.org/).

## Architecture

```
┌──────────────────────────────────────────────┐
│  REvoDesign UI (ConfigBus)                   │
│  - Rosetta options (nproc, protocol)         │
│  - Node selection (native/docker/mpi/wsl)    │
│  - Score function presets                    │
├──────────────────────────────────────────────┤
│  RosettaPy (pip: RosettaPy)                  │
│  ┌────────────────────────────────────────┐  │
│  │  RosettaAppBase (ABC)                  │  │
│  │  ├── FastRelax                         │  │
│  │  ├── PROSS (stability design)          │  │
│  │  ├── RosettaLigand (ligand docking)    │  │
│  │  ├── Supercharge (surface charge opt)  │  │
│  │  ├── CartesianddG (ΔΔG protocol)      │  │
│  │  └── MutateRelax (point mutation)      │  │
│  ├────────────────────────────────────────┤  │
│  │  Rosetta (dataclass)                   │  │
│  │  - Flag/option generation              │  │
│  │  - Task setup (native/MPI)             │  │
│  │  - Output directory management         │  │
│  ├────────────────────────────────────────┤  │
│  │  Analysers                             │  │
│  │  ├── RosettaEnergyUnitAnalyser (REU)   │  │
│  │  └── RosettaCartesianddGAnalyser (ddG) │  │
│  ├────────────────────────────────────────┤  │
│  │  Node System (node_picker)             │  │
│  │  ├── Native (local subprocess)         │  │
│  │  ├── MpiNode (mpirun wrapper)          │  │
│  │  ├── RosettaContainer (Docker)         │  │
│  │  └── WslWrapper (Windows WSL)          │  │
│  ├────────────────────────────────────────┤  │
│  │  RosettaFinder + RosettaBinary         │  │
│  │  - Auto-discover installed binaries    │  │
│  │  - Parse binary mode/OS/compiler       │  │
│  └────────────────────────────────────────┘  │
├──────────────────────────────────────────────┤
│  Rosetta Binary (external)                   │
│  - relax, score_jd2, mutate_relax            │
│  - RosettaScripts XML parser                 │
│  - Database (chemical, scoring, etc.)        │
└──────────────────────────────────────────────┘
```

## Key Components

### RosettaPy Package

RosettaPy is distributed on PyPI (`pip install RosettaPy`) and provides:

#### `Rosetta` — Core Wrapper

A `@dataclass` that wraps a Rosetta binary invocation:

| Field | Type | Purpose |
|-------|------|---------|
| `bin` | `RosettaBinary \| str` | Binary name (e.g. `"rosetta_scripts"`) or `RosettaBinary` object |
| `flags` | `list[str]` | Flag files to include (`@file.flags`) |
| `opts` | `list[str \| RosettaScriptsVariableGroup]` | Command-line options |
| `use_mpi` | `bool` | Enable MPI parallel execution |
| `run_node` | `NodeClassType` | Where to execute (default: `Native()`) |
| `job_id` | `str` | Unique job identifier (`"default"`) |
| `output_dir` | `str` | Root output directory |
| `save_all_together` | `bool` | Flatten PDB/score output into single dirs |
| `isolation` | `bool` | Run in isolated temp directory |
| `verbose` | `bool` | Verbose logging |

Key methods: `setup_tasks_native()`, `setup_tasks_mpi()`, `run()`.

#### `RosettaBinary` and `RosettaFinder`

`RosettaBinary` is a `@dataclass` representing a discovered binary:

- **Fields**: `dirname`, `binary_name`, `mode` (static/mpi/default), `os` (linux/macos), `compiler` (gcc/clang), `release` (release/debug)
- **`from_filename(dirname, filename)`**: Parse a binary filename into its components

`RosettaFinder` searches the local filesystem for Rosetta installations and
returns `RosettaBinary` instances.

#### Node System

Nodes abstract where Rosetta runs. The `node_picker()` factory function resolves
a `NodeHintT` string to a node instance:

| Hint | Node Class | Description |
|------|-----------|-------------|
| `"native"` | `Native` | Local subprocess (default, 4 cores) |
| `"mpi"` | `MpiNode` | `mpirun` wrapper for local multi-core |
| `"docker"` | `RosettaContainer` | `rosettacommons/rosetta:latest`, MPI disabled |
| `"docker_mpi"` | `RosettaContainer` | `rosettacommons/rosetta:mpi`, MPI enabled |
| `"wsl"` | `WslWrapper` | Windows Subsystem for Linux, serial |
| `"wsl_mpi"` | `WslWrapper` | Windows Subsystem for Linux, MPI enabled |

```python
from RosettaPy.node import node_picker

# Pick a node by hint
node = node_picker("docker_mpi", nproc=8, image="rosettacommons/rosetta:mpi")
```

All nodes accept `nproc` and other kwargs via `node_picker()`. The type union is
`NodeClassType = Union[Native, MpiNode, RosettaContainer, WslWrapper]`.

#### `RosettaAppBase` — Application ABC

```python
class RosettaAppBase(ABC):
    def __init__(
        self,
        job_id: str,                          # unique job identifier
        save_dir: str,                        # output root directory
        user_opts: Optional[list[str]] = None, # extra Rosetta flags
        node_hint: NodeHintT = "native",       # node type hint
        node_config: Optional[Mapping] = None,  # node-specific kwargs
        **kwargs,
    ):
```

The `node` property can be updated at runtime via `app.node = (new_hint, new_config)`.

#### Available Apps

| App | Source | Purpose |
|-----|--------|---------|
| `FastRelax` | `RosettaPy.app.fastrelax` | All-atom energy minimization with constraints |
| `PROSS` | `RosettaPy.app.pross` | Protein Stability (PROSS) sequence design |
| `RosettaLigand` | `RosettaPy.app.rosettaligand` | Ligand docking with flexible sidechains |
| `Supercharge` | `RosettaPy.app.supercharge` | Surface charge optimization (AVNAPS) |
| `CartesianddG` | `RosettaPy.app.cart_ddg` | Cartesian ΔΔG binding free energy |
| `MutateRelax` | `RosettaPy.app.mutate_relax` | Point mutation + repacking + minimization |

#### Analysers

| Analyser | Source | Purpose |
|----------|--------|---------|
| `RosettaEnergyUnitAnalyser` | `RosettaPy.analyser.reu` | Parse `.sc` score files, extract total + per-residue REU |
| `RosettaCartesianddGAnalyser` | `RosettaPy.analyser.ddg` | Parse cartesian ΔΔG output with statistics (`get_stats()`, best decoy) |

#### `RosettaScriptsVariableGroup`

Programmatic interface for building RosettaScripts XML with variable groups and
residue selectors (`expand_input_dict()`).

### Rosetta Utilities (`REvoDesign.tools.rosetta_utils`)

All 11 functions verified against source:

| Function | Purpose |
|----------|---------|
| `is_rosetta_runnable()` | Check whether any Rosetta backend is available |
| `is_docker_available()` | Check Docker daemon accessibility |
| `is_run_node_available(node_hint)` | Check a specific node type is configured |
| `is_wsl_available()` | Detect Windows Subsystem for Linux |
| `read_rosetta_config(key_path)` | Load Rosetta options from `main.yaml` |
| `read_rosetta_node_config()` | Load node definitions (host, port, credentials) |
| `setup_minimal_rosetta_db(subdir)` | Bootstrap a minimal Rosetta database directory |
| `list_fastrelax_scripts()` | Enumerate available FastRelax XML scripts |
| `extra_res_to_opts(ligand_params)` | Convert extra-residue param files to `-in:file:extra_res_fa` flags |
| `copy_rosetta_citation(citation)` | Wrap Rosetta citations with REvoDesign BibTeX key |

### Rosetta Tasks (`REvoDesign.shortcuts.tools.rosetta_tasks`)

High-level shortcut functions combining RosettaPy apps with REvoDesign workflows.
Key subclasses wrap the upstream apps for use as `cmd.extend` commands:

- **`FastRelax`** (wraps `RosettaPy.app.FastRelax`) — energy minimization
- **`PROSS`** (wraps `RosettaPy.app.PROSS`) — stability design
- **`RosettaLigand`** (wraps `RosettaPy.app.RosettaLigand`) — ligand docking

### ddG Analysis

Cartesian ddG (ΔΔG) scoring estimates the change in binding free energy from a
mutation:

1. **`CartesianddG`** in `RosettaPy.app.cart_ddg` — runs the Rosetta cartesian
   ΔΔG protocol with `RosettaCartesianddGAnalyser` for result parsing.
2. The `ddg` gimmick in `REvoDesign.magician.designers` — an
   `ExternalDesignerAbstract` subclass that calls this protocol.
3. `REvoDesign.shortcuts.tools.designs` — contains `predict_point_mutation_ddG`
   and related functions.

### MutateRelax Worker

`MutateRelax_worker` in `REvoDesign.sidechain.mutate_runner.RosettaMutateRelax`
wraps `RosettaPy.app.MutateRelax` as a `MutateRunnerAbstract` subclass.
Registered in `RUNNER_REGISTRY`.

## Configuration

Rosetta settings live in `main.yaml` under `.rosetta.opts` and in
`src/REvoDesign/config/rosetta-node/` for node definitions.

| Config key | Purpose |
|------------|---------|
| `ui.mutate.mutate_runner` | Active sidechain solver (e.g., `MutateRelax_worker`) |
| `ui.mutate.nproc` | Number of parallel Rosetta processes |
| `rosetta.opts.general` | Default Rosetta flags (read by `read_rosetta_config()`) |
| `rosetta.node_hint` | Node type: `native`, `docker`, `docker_mpi`, `mpi`, `wsl`, `wsl_mpi` |
| `rosetta.node_config` | Node-specific kwargs (image, nproc, host, etc.) |

## Docker Integration

For users without a native Rosetta installation, RosettaPy can pull the official
Docker images:

- `rosettacommons/rosetta:latest` — serial execution (`"docker"` hint)
- `rosettacommons/rosetta:mpi` — MPI-enabled (`"docker_mpi"` hint)

Docker availability is checked at startup via `is_docker_available()`. Set
`ENABLE_ROSETTA_CONTAINER_NODE_TEST=NO` to skip Docker tests in CI.

## Adding a New Rosetta Protocol

See [Adding a Sidechain Solver](adding-a-sidechain-solver.md) for mutate protocols.
For analysis/shortcut protocols:

1. Create a new module in `REvoDesign.shortcuts.tools`.
2. Subclass `RosettaPy.app.abc.RosettaAppBase` with your protocol.
3. Write a shortcut function decorated with `@get_cited` for citation tracking.
4. Register in `shortcuts/registry/` as a YAML config defining dialog inputs
   and the function entry point.
5. Add a menu action in `REvoDesign.ui` if it needs a UI trigger.

## Platform Compatibility

From the RosettaPy README:

| Node | Linux | macOS | Windows | Notes |
|------|:-----:|:-----:|:-------:|-------|
| `Native` | ✅ | ✅ | ❌ | Requires Rosetta compiled from source |
| `MpiNode` | ✅ | ✅ | ❌ | Requires `extras=mpi` build + MPI installed |
| `RosettaContainer` | ✅ | ✅ | ✅ | Docker Desktop; macOS uses Rosetta2 translation on Apple Silicon |
| `WslWrapper` | ❌ | ❌ | ✅ | WSL2 with Rosetta built inside the distro |

`Native` and `MpiNode` require a local Rosetta build — Linux and macOS only.
`RosettaContainer` (Docker) works on all three platforms. Windows users without
Docker can use `WslWrapper` with a WSL2 Rosetta installation.

## Limitations

- Rosetta is **not bundled** with REvoDesign — users must install it separately
  or use the Docker images.
- Some protocols (cartesian ddG, FastRelax) require a Rosetta license for
  commercial use.
- **RosettaPy ≠ PyRosetta.** RosettaPy wraps the CLI; PyRosetta binds C++ objects.
