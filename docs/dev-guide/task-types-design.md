# Task Types — Design Model

## Configuration Layers

Three layers, each with a distinct owner:

| Layer | File | Owner | Contains |
|-------|------|-------|----------|
| Server | `.env` | Operator | `SERVER_DIR`, `PORT`, auth, Redis, `ENABLED_TASKRUNNERS`, `DOCKER_USER` |
| Runner | `config/runners/<name>.yaml` | Operator (per-machine) | Host paths for DBs/models, resource limits, default param values, extra env vars |
| Task type | `config/task_types.yaml` | Developer | Docker image, command, input format, stage markers, result patterns, user-facing param schema |

`.env` never carries runner-specific paths (`DB_UNIREF30`, `AF_DATA_DIR`, etc.).
Those live in per-runner YAML files — edit the runner YAML when deploying to a new node.

## Dataclasses

```python
@dataclass(frozen=True)
class TaskParam:
    """A parameter the user can set when submitting a job."""
    name: str                    # "model", "num_samples", "temperature"
    type: str = "str"            # "str" | "int" | "float" | "bool"
    default: Any = None          # default value (from task_types.yaml)
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class TaskType:
    """Portable task definition — same on every deployment."""
    name: str                    # "gremlin", "alphafold", "diffdock", "esm"
    display_name: str            # "PSSM-GREMLIN", "AlphaFold2"

    # Docker runner
    docker_image: str            # "revodesign/runner-gremlin:latest"
    command: list[str]           # ["bash", "/opt/run.sh"]

    # I/O
    input_extension: str         # ".fasta", ".pdb"
    input_label: str             # "FASTA file", "PDB file"

    # Optional fields with defaults
    gpus: bool = False
    result_patterns: tuple[str, ...] = ("*",)
    stage_markers: dict[str, str] = field(default_factory=dict)
    params: tuple[TaskParam, ...] = ()


@dataclass(frozen=True)
class RunnerMount:
    """A bind mount from host into the runner container."""
    host_path: str               # "/srv/revodesign/databases/uniref30"
    container_path: str          # "/opt/db/uniref30"
    mode: str = "ro"             # "ro" | "rw"


@dataclass(frozen=True)
class RunnerConfig:
    """Deployment-specific settings for a task type.

    Loaded from config/runners/<name>.yaml at startup.
    Host paths are machine-specific.
    """
    mounts: tuple[RunnerMount, ...] = ()
    env: dict[str, str] = field(default_factory=dict)     # extra env vars → container
    nproc: int | None = None      # override server default if set
    maxmem: int | None = None     # override server default if set
    max_runtime_seconds: int | None = None  # override task_type default if set
    defaults: dict[str, Any] = field(default_factory=dict)  # default param values
    # SLURM + Apptainer (set in deployed runner YAML)
    runner: str = "docker"         # "docker" | "slurm"
    container_runtime: str = ""    # "apptainer" | ""
    slurm_image: str = ""          # path to .sif image
```

## Registry

```python
_registry: dict[str, tuple[TaskType, RunnerConfig]] = {}

def register(task_type: TaskType, runner: RunnerConfig) -> None:
    """Register a task type + runner config pair."""

def get(name: str) -> tuple[TaskType, RunnerConfig]:
    """Look up a registered task type. Raises KeyError if not found."""

def list_types() -> list[TaskType]:
    """Return all registered task types (for GET /api/types)."""

def load_registry(task_types_yaml: str, runners_dir: str, enabled: set[str]) -> None:
    """Load task type definitions + per-runner configs.

    Reads task_types.yaml, then for each enabled task type (gated by
    ENABLED_TASKRUNNERS; gremlin always enabled), loads the corresponding
    config/runners/<name>.yaml if it exists.
    """
```

## YAML Files

### `config/task_types.yaml` — portable task interface (checked into git)

```yaml
task_types:
  gremlin:
    display_name: "PSSM-GREMLIN"
    docker_image: "revodesign-revocompute-runner"
    command: ["bash", "/app/revocompute/run.sh"]
    input_extension: ".fasta"
    input_label: "FASTA file"
    stage_markers:
      hhblits: "HHblits MSA generation"
      hhfilter: "HHfilter filtering"
      gremlin: "GREMLIN optimization"
      blast: "PSI-BLAST PSSM"
    result_patterns: ["*.pkl", "*_ascii_mtx_file", "*.GREMLIN.mrf.pkl"]
    params:
      - name: "iter"
        type: "int"
        default: 100
        description: "GREMLIN optimization iterations"

  esm_fold:
    display_name: "ESMFold"
    docker_image: "revodesign-revocompute-runner-esm"
    command: ["bash", "/app/revocompute/run.sh"]
    gpus: true
    input_extension: ".fasta"
    input_label: "FASTA file"
    stage_markers:
      esm_fold: "ESMFold structure prediction"
    result_patterns: ["*.pdb"]
    params:
      - name: "num_recycles"
        type: "int"
        default: 4
```

Multiple task types can share the same `docker_image` (e.g. `esm_fold`,
`esm_extract`, `esm_1v`, `esm_if1` all use `revodesign-revocompute-runner-esm`).
They dispatch on `$TASK_TYPE` set by the launcher.

### `config/runners/gremlin.yaml` — deployment-specific (machine-local)

```yaml
mounts:
  - host_path: "/srv/revodesign/databases/uniref30/UniRef30_2023_02"
    container_path: "/opt/db/uniref30"
    mode: "ro"
  - host_path: "/srv/revodesign/databases/uniref90/uniref90"
    container_path: "/opt/db/uniref90"
    mode: "ro"
env:
  GREMLIN_CALC_CPU_NUM: "16"
  OMP_NUM_THREADS: "16"
nproc: 16
maxmem: 64
max_runtime_seconds: 7200
defaults:
  iter: 100
```

## Runner Contract

Each container:
1. Reads input from `/workspace/inputs/`
2. Writes output to `/workspace/outputs/`
3. Emits `REVODESIGN_STAGE:<marker>` on stdout for progress tracking
4. Reads `TASK_PARAMS` env var (JSON string) for user-provided parameters
5. Exits 0 on success

## ComputeConfig After Migration

```python
@dataclass(frozen=True, slots=True)
class ComputeConfig:
    """Server-level configuration only — no task-type-specific fields."""
    server_dir: str
    upload_folder: str
    results_folder: str
    db_path: str
    port: int
    slurm_enabled: bool
    slurm_allowed_queues: list[str]
    task_types_config: str   # path to task_types.yaml
    runners_dir: str         # path to config/runners/
```

`uniref30_db`, `uniref90_db`, `nproc`, `maxmem`, `docker_image` are gone —
they live in `config/runners/gremlin.yaml` now.

## Auto-Discovery

`restart.sh` scans `docker/runners/*/Dockerfile` at build time.  Each
directory becomes a build target:

```
docker/runners/
  pssm_gremlin/Dockerfile  → revodesign-revocompute-runner       (base, no suffix)
  pythia_ddg/Dockerfile    → revodesign-revocompute-runner-pythia_ddg
  esm/Dockerfile           → revodesign-revocompute-runner-esm
  opendde/Dockerfile       → revodesign-revocompute-runner-opendde
```

The naming convention: `revodesign-revocompute-runner{-<dirname>}`, where
`pssm_gremlin` is the special base case (no suffix).  `task_types.yaml`
references images by these tags.

`generate_runner_compose()` writes a `docker-compose.runners.generated.yml`
override with one service per discovered directory.  `compose_files()`
auto-includes it.  Adding a new runner is creating a directory under
`docker/runners/` — no compose or restart.sh edits needed.

All runner images are built **in parallel** (`&` / `wait`) — wall-clock
time is the slowest image, not the sum.

## Entities and InputForm

When a user submits a task, the HTTP handler builds an `input_form` JSON blob
that captures *what* was submitted and *how* it was validated.  This blob is
stored in the `input_form` column of the tasks table and read by the worker at
runtime to set up Docker mounts and params.

### Structure

```json
{
  "user": "alice",
  "submitted_at": "2026-08-06T12:34:56+00:00",
  "entities": [
    {
      "name": "file",
      "type": "file",
      "value": "2KL8.fasta",
      "verified_value": "2KL8.fasta",
      "mounted": "/workspace/inputs/2KL8.fasta",
      "hash": "3855bf8ca11fda660cd9406adab909df"
    },
    {
      "name": "iter",
      "type": "int",
      "value": "100",
      "verified_value": 100
    }
  ]
}
```

### Entity kinds

| Kind | Fields | Purpose |
|------|--------|---------|
| **file** | `name`, `type`, `value` (original filename), `verified_value` (sanitised filename), `mounted` (container path), `hash` (task MD5) | The uploaded input file. The on-disk file is `CONFIG.upload_folder/<hash>.fasta`; the runner sees it at `mounted`. |
| **param** | `name`, `type`, `value` (raw form string), `verified_value` (Pydantic-coerced) | A user-facing parameter. `value` is the string from the HTML form; `verified_value` is the typed coercion (e.g. `"100"` → `100`). |

### Why the upload directory is mounted directly

The runner gets `/workspace/inputs` → `CONFIG.upload_folder` (e.g.
`/srv/revodesign/compute/upload/`), not the per-task `results/<md5sum>/`
directory.  The upload directory lives outside the web container's
`SERVER_DIR` bind mount, so the Docker daemon always sees it.  By contrast,
`results/<md5sum>/` is created inside the bind mount and may not sync to
the host filesystem in time for Docker to mount it.

### Filename preservation via hardlink

The uploaded file is stored on disk as `<md5sum>.fasta` (hash-based, no
collisions).  The runner script uses `readlink -f` to resolve the input
filename before constructing output filenames — if the input is
`2KL8.fasta`, the outputs are `2KL8.GREMLIN.mrf.pkl`, `2KL8_ascii_mtx_file`,
etc.

`readlink -f` resolves symlinks to their canonical targets, so a symlink
`2KL8.fasta` → `3855bf8c.fasta` would cause every output file to be prefixed
`3855bf8c.*` instead of `2KL8.*`.  Hardlinks (`os.link()`) don't have this
problem — `readlink -f` returns the accessed name as-is.

Before each run, the worker creates a hardlink `<original>.fasta` →
`<md5sum>.fasta` in the upload directory.  The hardlink is removed in the
`finally` block after the container exits, regardless of success or failure.
