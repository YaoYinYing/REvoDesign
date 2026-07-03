# Adding a Sidechain Solver

This document explains the full workflow to integrate a new sidechain solver
into REvoDesign and validate it safely, based on the current live
implementations (`DLPacker`, `DLPackerPytorch`, `DiffPack`, `PIPPack`,
`Rosetta-MutateRelax`).

## 1. What "integrated" means

A sidechain solver is considered integrated when all of the following are true:

- It subclasses `MutateRunnerAbstract` and implements `run_mutate()` and
  `run_mutate_parallel()`.
- It is auto-discovered by the sidechain plugin registry.
- It appears in the UI solver selection when installed.
- Its model/backend presets are reflected in the sidechain "model" dropdown.
- It has install metadata in `pyproject.toml` optional deps and the installer
  extras table at `jsons/REvoDesignExtrasTableRich.json`.
- It has tests: a solver matrix inclusion test and a focused unit test for
  runner-specific request/config behavior.

## 2. Relevant extension points

| What | File |
|---|---|
| Abstract base class | `src/REvoDesign/basic/mutate_runner.py` |
| Sidechain solver registry / compatibility exports | `src/REvoDesign/sidechain/sidechain_solver.py` |
| Solver module export list | `src/REvoDesign/sidechain/mutate_runner/__init__.py` |
| Installed solver names to combo box | `src/REvoDesign/driver/group_register.py` |
| `weights_preset` / `default_weight_preset` to model combo | `src/REvoDesign/driver/param_toggle_register.py` |
| Optional dependencies | `pyproject.toml` |
| Installer extras table | `jsons/REvoDesignExtrasTableRich.json` |
| Sidechain solver matrix test | `tests/sidechain/test_sidechain_solvers.py` |
| Focused runner tests (patterns) | `tests/sidechain/test_dlpacker_pytorch_runner_config.py` |

## 3. Step-by-step integration

### Step A: Create a runner module

Create a new file under `src/REvoDesign/sidechain/mutate_runner/<Solver>.py`.

Requirements:

- Class name convention: `<Solver>_worker` (e.g. `DLPacker_worker`).
- Inherit `MutateRunnerAbstract`.
- Define class attributes:
  - `name` -- user-facing solver name (appears in UI).
  - `installed` -- set via `is_package_installed("<import_name>")`.
  - Optional presets:
    - `weights_preset: tuple[str, ...]`
    - `default_weight_preset: str`

Minimum methods:

```python
from REvoDesign.basic.mutate_runner import MutateRunnerAbstract


class YourSolver_worker(MutateRunnerAbstract):
    name = "YourSolver"
    installed = True
    weights_preset = ("default", "accurate")
    default_weight_preset = "default"

    def run_mutate(self, mutant) -> str:
        # Produce one output PDB for the mutant.
        # Return an absolute or relative filesystem path that exists.
        ...

    def run_mutate_parallel(self, mutants, nproc=2) -> list[str]:
        # Return one PDB path per mutant, preserving order.
        ...

    def reconstruct(self) -> str:
        # Optional: return reconstructed PDB path.
        ...
```

**Output naming convention**: Normalize final mutant file names to
`mutant_pdbs/<RunnerClass>/<mutant.short_mutant_id>.pdb`. If the third-party
tool emits generic basename outputs, rename or move them after the run.

### Step B: Add solver-specific config YAML (optional)

If your solver has runtime knobs, create
`src/REvoDesign/config/sidechain-solver/<solver>.yaml` and load it with:

```python
from REvoDesign.bootstrap import reload_config_file

config = reload_config_file("sidechain-solver/<solver>")["sidechain-solver"]
```

Recommended fields: backend/model mode, device, cache path, runtime toggles.

### Step C: Export the runner

Add the import and `__all__` entry in
`src/REvoDesign/sidechain/mutate_runner/__init__.py`:

```python
from .YourSolver import YourSolver_worker

__all__ = [
    ...,
    "YourSolver_worker",
]
```

Also add a compatibility import in
`src/REvoDesign/sidechain/sidechain_solver.py` if needed for explicit
imports by external callers. Note that registry auto-discovery does not
require this step, but it keeps compatibility symbols explicit.

### Step D: Install metadata

Add an optional-dependency entry in `pyproject.toml` under
`[project.optional-dependencies]`:

```toml
your_solver = [
    "your_solver @ git+https://github.com/<owner>/<repo>.git#egg=your_solver",
]
```

Add an installer extras entry in `jsons/REvoDesignExtrasTableRich.json`
with fields for `name`, `extras_id`, `depts` (package list),
`python_version` bounds, and an optional `description`.

### Step E: Wire tests

1. Add your runner to `tests/sidechain/test_sidechain_solvers.py` matrix.
   Keep skip-on-not-installed behavior via the existing helper.
2. Add a focused unit test (e.g. `tests/sidechain/test_<solver>_runner_config.py`)
   with mocked third-party modules covering:
   - Request construction from REvoDesign runner inputs.
   - Config mapping and model/backend override behavior.
   - Output rename to `<short_mutant_id>.pdb`.
   - Concurrency/resource policy if custom.

## 4. Interface contract

The runner must satisfy these invariants:

- Return existing PDB file paths.
- Preserve mutant order in `run_mutate_parallel` return list.
- No silent mismatch between number of mutants and outputs.
- Avoid output collisions in parallel mode.
- Be robust with `nproc=None`, small/large `nproc`, and empty mutant lists.

For UI model dropdown support:

- Expose model/backend options via `weights_preset`.
- Set a safe `default_weight_preset`.
- Map `use_model` override in `__init__`.

## 5. Validation

### Syntax check

```bash
python -m compileall src/REvoDesign/sidechain/mutate_runner/<Solver>.py
```

### Sidechain matrix

```bash
conda run -n <env> make kw-test PYTEST_KW='"sidechain and solver"'
```

### Focused runner test

```bash
conda run -n <env> /bin/zsh -lc 'mkdir -p tmp-test-dir-with-unique-name && \
  cd tmp-test-dir-with-unique-name && \
  python -m pytest ../tests/sidechain/test_<solver>_runner_config.py -q'
```

### Expected outcomes

- Existing solver tests remain green.
- New solver is either `PASSED` if dependency installed, or `SKIPPED` if
  intentionally not installed.
- Focused unit tests pass fully (they use mocks).

## 6. Common pitfalls

**Output file collision in parallel mode**: Create per-mutant unique working
output directories and normalize final outputs to the expected naming pattern.

**Model/backend UI dropdown does nothing**: Define `weights_preset` and
`default_weight_preset`, and consume `use_model` in the runner `__init__`.

**Cache-required backends fail intermittently**: Validate cache before
inference and auto-bootstrap once on miss when the policy allows.

**Over-committing CPU**: Cap worker count to `min(requested_nproc,
len(mutants), os.cpu_count())`. For heavy solvers, enforce one-mutant-one-core
semantics.

## 7. Reference implementations

Use these as templates:

- `src/REvoDesign/sidechain/mutate_runner/DLPackerPytorch.py`
- `src/REvoDesign/sidechain/mutate_runner/DiffPack.py`
- `tests/sidechain/test_dlpacker_pytorch_runner_config.py`
- `tests/sidechain/test_diffpack_runner_config.py`

They demonstrate config-driven runner construction, UI model override mapping,
output normalization, cache readiness handling, parallel cap behavior, and
robust mock-based focused tests.
