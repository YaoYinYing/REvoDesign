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
    docker_image: "revodesign/runner-gremlin:latest"
    command: ["bash", "/opt/gremlin/run_gremlin.sh"]
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
```

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
    docker_user: str
    port: int
    task_types_config: str   # path to task_types.yaml
    runners_dir: str         # path to config/runners/
```

`uniref30_db`, `uniref90_db`, `nproc`, `maxmem`, `docker_image` are gone —
they live in `config/runners/gremlin.yaml` now.
