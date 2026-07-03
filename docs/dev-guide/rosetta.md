# Rosetta Integration

REvoDesign integrates with the [Rosetta](https://rosettacommons.org/) molecular
modeling suite through [RosettaPy](https://github.com/YaoYinYing/RosettaPy), a
Python interface that manages Rosetta execution across local, Docker, and SSH-based
compute nodes.

## Architecture

```
┌──────────────────────────────────────────┐
│  REvoDesign UI (ConfigBus)               │
│  - Rosetta options (nproc, protocol)     │
│  - Node selection (local/docker/ssh)     │
│  - Score function presets                │
├──────────────────────────────────────────┤
│  RosettaPy                               │
│  ┌────────────────────────────────────┐  │
│  │  RosettaAppBase                    │  │
│  │  ├── FastRelax                     │  │
│  │  ├── PROSS (stability design)      │  │
│  │  ├── RosettaLigand (ligand dock)   │  │
│  │  └── RosettaMutateRelax            │  │
│  ├────────────────────────────────────┤  │
│  │  RosettaEnergyUnitAnalyser         │  │
│  │  - Parse score files (.sc)         │  │
│  │  - Extract per-residue energies    │  │
│  │  - REU → kcal/mol conversion       │  │
│  ├────────────────────────────────────┤  │
│  │  Node System                       │  │
│  │  ├── LocalNode (native binary)     │  │
│  │  ├── DockerNode (container)        │  │
│  │  ├── SSHNode (remote cluster)      │  │
│  │  └── RosettaContainerNode          │  │
│  │      (Docker-in-Docker MPI)        │  │
│  └────────────────────────────────────┘  │
├──────────────────────────────────────────┤
│  Rosetta Binary                          │
│  - relax, score_jd2, mutate_relax        │
│  - RosettaScripts XML parser             │
│  - Database (chemical, scoring, etc.)    │
└──────────────────────────────────────────┘
```

## Key Components

### RosettaPy

RosettaPy is a separate package (`RosettaPy`) that provides:

- **`Rosetta`** — Core class that wraps a Rosetta binary invocation. Handles
  flag generation, working directory setup, and result parsing.
- **`RosettaAppBase`** — Abstract base for Rosetta protocols (FastRelax,
  PROSS, RosettaLigand, etc.). Each app defines its flags, input requirements,
  and output parser.
- **`RosettaEnergyUnitAnalyser`** — Parses Rosetta energy output (`.sc` files),
  extracts total score and per-residue energy breakdowns in Rosetta Energy
  Units (REU).
- **`RosettaScriptsVariableGroup`** — Programmatic interface for building
  RosettaScripts XML documents with variable groups and residue selectors.
- **Node system** — Abstracts where Rosetta runs:
  - `LocalNode` — Direct execution on the local machine.
  - `DockerNode` / `RosettaContainerNode` — Run inside Docker containers
    (supporting MPI for multi-core relaxation).
  - `SSHNode` — Execute on remote HPC clusters.

### Rosetta Utilities (`REvoDesign.tools.rosetta_utils`)

| Function | Purpose |
|----------|---------|
| `is_rosetta_runnable()` | Check whether any Rosetta backend is available |
| `is_docker_available()` | Check Docker daemon accessibility |
| `is_run_node_available()` | Check SSH/container node config |
| `is_wsl_available()` | Detect Windows Subsystem for Linux |
| `read_rosetta_config()` | Load Rosetta settings from config YAML |
| `read_rosetta_node_config()` | Load node definitions (host, port, credentials) |
| `setup_minimal_rosetta_db()` | Bootstrap a minimal Rosetta database directory |
| `list_fastrelax_scripts()` | Enumerate available FastRelax XML scripts |
| `extra_res_to_opts()` | Convert extra residue params to Rosetta flags |
| `copy_rosetta_citation()` | Output Rosetta Commons citation BibTeX |

### Rosetta Tasks (`REvoDesign.shortcuts.tools.rosetta_tasks`)

High-level shortcut functions that combine RosettaPy apps with REvoDesign
workflows:

- **`FastRelax`** — Energy minimization of a PDB structure. Configurable
  constraints, score functions, and relax rounds.
- **`PROSS`** — Protein Stabilization design. Generates stability-optimized
  sequence variants.
- **`RosettaLigand`** — Ligand docking with flexible sidechains. Used for
  substrate-binding pocket analysis.
- **`MutateRelax_worker`** — The sidechain solver that runs
  `mutate_relax` (point mutation + repacking + minimization). Registered in
  `RUNNER_REGISTRY` under `sidechain.mutate_runner.RosettaMutateRelax`.

### ddG Analysis

Cartesian ddG (ΔΔG) scoring estimates the change in folding free energy
introduced by a mutation. REvoDesign supports this through:

1. The `ddg` gimmick in `magician.designers` — an `ExternalDesignerAbstract`
   subclass that calls Rosetta cartesian ΔΔG protocol.
2. The `REvoDesign.shortcuts.tools.designs` module — contains
   `predict_point_mutation_ddG` and related design functions.

## Configuration

Rosetta settings live in `main.yaml` under the `.rosetta` namespace and in
`src/REvoDesign/config/rosetta-node/` for node definitions.

Key config items:

| Config key | Purpose |
|------------|---------|
| `ui.mutate.mutate_runner` | Active sidechain solver (e.g., `MutateRelax_worker`) |
| `ui.mutate.nproc` | Number of parallel Rosetta processes |
| `rosetta_node.type` | Node type: `local`, `docker`, `docker_mpi`, `ssh` |
| `rosetta_node.host` / `.port` | SSH node connection details |
| `rosetta_db_path` | Path to Rosetta database directory |

## Docker Integration

For users without a native Rosetta installation, REvoDesign can use the
[Rosetta Docker image](https://hub.docker.com/r/rosettacommons/rosetta):

- The `DockerNode` helper pulls and manages the container.
- `RosettaContainerNode` supports MPI for multi-core relaxation (Ubuntu only).
- Docker availability is checked at startup via `is_docker_available()`.
- Set `ENABLE_ROSETTA_CONTAINER_NODE_TEST=NO` to skip Docker tests in CI.

## Adding a New Rosetta Protocol

See [Adding a Sidechain Solver](adding-a-sidechain-solver.md) for mutating protocols.
For analysis/shortcut protocols:

1. Create a new module in `REvoDesign.shortcuts.tools`.
2. Subclass `RosettaAppBase` (or compose a `Rosetta` instance).
3. Write a shortcut function decorated with `@get_cited` for citation tracking.
4. Register in `shortcuts/registry/` as a YAML config file defining the dialog
   inputs and the function entry point.
5. Add a menu action in `REvoDesign.ui` if it needs a UI trigger.

## Limitations

- Rosetta is **not bundled** with REvoDesign — users must install it separately
  or use the Docker image.
- The Docker MPI node requires Linux; macOS/Windows are limited to serial
  Docker or local native binaries.
- Some protocols (cartesian ddG, FastRelax) require a Rosetta license for
  commercial use.
