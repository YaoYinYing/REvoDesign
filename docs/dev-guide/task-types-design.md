# Task Types and Runtime Families

REvoCompute separates the portable scientific interface from the execution
environment and from machine-local configuration. This lets several task types
share one dependency image without copying host paths or SLURM policy into the
portable registry.

For the full build, versioned-SIF, activation, rollback, and adapter procedure,
see the [operations and task adapter guide](../../server/OPERATIONS_AND_TASK_ADAPTER_GUIDE.md).

## Ownership model

```text
task_types.yaml
├── global: job_executor + container_runtime
├── runtime_families
│   └── image + entrypoint + Dockerfile + definition + versioned SIF
└── task_types
    └── runtime selection + inputs + GPU flag + stages + typed parameters

runners/<runtime-family>.yaml
└── host mounts + environment + timeout + deployment defaults

management database
└── per-task enabled state + SLURM partition/resources
```

The executor is selected once for the deployment:

```yaml
job_executor: slurm
container_runtime: apptainer
```

Docker execution requires `docker`/`docker`; SLURM execution requires
`slurm`/`apptainer`. These global fields are not copied into each family.

## Registry data model

The implementation in `server/revocompute/task_types/__init__.py` has four
portable/runtime records:

- `RuntimeFamily`: `name`, `docker_image`, `entrypoint`, `dockerfile`,
  `definition`, and `slurm_image`.
- `TaskType`: display name, selected family, accepted input extensions,
  multi-upload limits, runner arguments, GPU requirement, stages, and params.
- `TaskParam`: typed UI/API field with defaults, choices, bounds, step, unit,
  required state, and advanced-field state.
- `RunnerConfig`: only mounts, environment, maximum runtime, and deployment
  parameter defaults.

Runner YAML must not contain `runner`, `job_executor`, `container_runtime`,
`slurm_image`, `gpus`, `nproc`, or `maxmem`. GPU eligibility belongs to the task
schema; SLURM requests belong to the management database.

The registry loader fails when `task_types.yaml` is absent, empty, structurally
invalid, or inconsistent. There is no built-in GREMLIN registry fallback that
can conceal a missing deployment file. `gremlin` remains enabled by policy;
other tasks are filtered by `ENABLED_TASKRUNNERS`.

## Portable YAML example

```yaml
job_executor: slurm
container_runtime: apptainer

runtime_families:
  mpnn:
    docker_image: revodesign-revocompute-runner-mpnn:latest
    entrypoint: [bash, /app/revocompute/run.sh]
    dockerfile: docker/runners/mpnn/Dockerfile
    definition: docker/runners/mpnn/mpnn.def
    slurm_image: /srv/revocompute/images/mpnn_20260811.sif

task_types:
  proteinmpnn:
    display_name: ProteinMPNN
    runtime_family: mpnn
    runner_args: [proteinmpnn]
    input_extension: .pdb
    input_extensions: [.pdb, .cif, .mmcif]
    primary_input_extensions: [.pdb, .cif, .mmcif]
    allow_multiple_inputs: false
    max_input_files: 1
    input_label: Protein structure
    gpus: false
    stage_markers:
      design: Design sequences
    params:
      - name: temperature
        type: float
        default: 0.1
        minimum: 0.01
        maximum: 1.0
        step: 0.01
```

One family can serve materially different commands. The MPNN family currently
shares its image across ProteinMPNN, SolubleMPNN, LigandMPNN, HyperMPNN,
LASErMPNN, and ThermoMPNN-D; the ESM family similarly serves several distinct
entrypoints. Sharing is appropriate only when the interpreter, dependency
graph, accelerator model, ABI, and license are compatible.

## Machine runner YAML

Exactly one active YAML exists per runtime family:

```yaml
mounts:
  - host_path: /mnt/db/weights/thermompnn
    container_path: /mnt/db/weights/thermompnn
    mode: ro
env:
  XDG_DATA_HOME: /mnt/db/weights/thermompnn
max_runtime_seconds: 7200
defaults: {}
```

Mounts must preserve the deployment's real database and checkpoint locations.
Model caches required for inference should be provisioned on shared storage,
mounted read-only, and validated before launch. Runtime downloads into a small
or compute-node-local home directory are not a production weight strategy.

## Submission and workspace contract

The API validates task type, files, relative paths, and params before it creates
the task. Each task receives an immutable host snapshot:

```text
${SERVER_DIR}/workspaces/<username>/<task-id>/
├── inputs/
└── outputs/
```

Both Docker and Apptainer expose only that task's snapshot at the stable virtual
path:

```text
/mnt/revocompute/<username>/
├── inputs/    read-only
└── outputs/   writable for this task
```

The username in the virtual path does not imply a shared mutable host home.
Two concurrent tasks for the same user see the same virtual prefix in their
separate containers, backed by different host directories.

Multi-file uploads preserve safe `relative_path` values. Absolute paths,
traversal, unsupported extensions, and symlink escape are rejected. The worker
verifies staged file checksums before launch and binds inputs read-only.

Runner adapters receive:

- `TASK_TYPE`: selected task name;
- `TASK_PARAMS`: JSON object containing validated, non-empty parameter values;
- `TASK_INPUTS`: JSON array containing `name`, mounted `path`, and preserved
  `relative_path` for every input;
- `-i`: primary input path;
- `-o`: task-owned output directory;
- any fixed `runner_args` before the generic input/output flags.

Optional empty form fields are omitted instead of being passed as empty CLI
arguments. Every user-visible parameter must map to an actual flag supported by
the pinned upstream revision. Path, checkpoint, device, and integrity-bypass
arguments remain server/operator controlled.

## Execution lifecycle

```text
validated submission
        |
        v
task snapshot + input checksums
        |
        v
resolve global executor and selected family
        |
        +-------------------+
        |                   |
        v                   v
DockerJob              SlurmJob
docker create/run      srun + Apptainer
        |                   |
        +---------+---------+
                  v
        stage markers + exit status
                  |
                  v
       validate real output artifacts
                  |
                  v
       atomically publish manifest.json
```

GPU tasks require both `gpus: true` and user GPU permission. SLURM adds the
configured GPU resource and Apptainer `--nv`; CPU tasks receive neither. A
zero process exit is not enough for success: the worker also requires a
non-empty scientific artifact. Adapters must propagate internal per-input
failure and create `task_finished` only after the scientific command succeeds.

Upstream programs that write beside their input need explicit redirection to
`outputs/` or `/tmp`; attempts to update the read-only snapshot are defects, not
a reason to make inputs writable.

## Result contract

The uncompressed output tree and its atomically published `manifest.json` are
the source of truth. Authenticated endpoints support artifact metadata,
individual downloads, suitable byte-range requests, and bounded text, table,
image, and structure previews. The dedicated result page selects a preview
plugin by manifest metadata and safely falls back to download when a file is
too large or unsupported.

A ZIP is an explicit asynchronous derived artifact. It contains only the
manifest-approved files plus `manifest.json`; task completion does not depend
on archive creation. Cleanup independently targets the result tree, optional
ZIP, and selected task workspace.

## Adding or changing a task

1. Choose an existing compatible family or declare a new one.
2. Add the constrained task schema and fixed `runner_args`.
3. Implement the family `run.sh` dispatch using `TASK_INPUTS` and
   `TASK_PARAMS`.
4. Confirm every emitted upstream flag against the pinned command's `--help`.
5. Add/update exactly one runner YAML for the family.
6. Add static contract, validation, and failure-semantics tests.
7. Build and smoke Docker without stopping production.
8. Build a versioned `.sif.partial`, inspect/smoke it, then atomically promote.
9. Back up external configuration and activate with `--mode=prepared`.
10. Exercise the real server → worker → SLURM → Apptainer path using the
    smallest safe input.

Do not generate profile-disabled runner Compose services. Runtime images are
built/pulled from the registry manifest and launched on demand; Compose manages
only gateway, web, worker, maintenance, and Redis.
