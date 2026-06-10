# Add a New Sidechain Solver to REvoDesign

This document explains the full workflow to integrate a new sidechain solver into REvoDesign and validate it safely.

It is based on the current live implementations (`DLPacker`, `DLPackerPytorch`, `DiffPack`, `PIPPack`, `Rosetta-MutateRelax`).

## 1) What “integrated” means in REvoDesign

A sidechain solver is considered integrated when all of the following are true:

- It subclasses `MutateRunnerAbstract` and implements:
  - `run_mutate(mutant) -> str`
  - `run_mutate_parallel(mutants, nproc) -> list[str]`
  - optionally `reconstruct() -> str`
- It is auto-discoverable by the sidechain plugin registry.
- It appears in UI solver selection when installed.
- Its model/backend presets are reflected in the sidechain “model” dropdown.
- It has install metadata in:
  - `pyproject.toml` optional deps
  - installer extras table JSON (`jsons/REvoDesignExtrasTableRich.json`)
- It has tests:
  - solver matrix inclusion test
  - focused unit test for runner-specific request/config behavior.

## 2) Relevant extension points

Core contract and discovery:

- Abstract base class:
  - `src/REvoDesign/basic/mutate_runner.py`
- Sidechain solver registry / compatibility exports:
  - `src/REvoDesign/sidechain/sidechain_solver.py`
- Solver module export list:
  - `src/REvoDesign/sidechain/mutate_runner/__init__.py`

UI binding for solver list and model presets:

- Installed solver names -> combo box:
  - `src/REvoDesign/driver/group_register.py`
- `weights_preset` / `default_weight_preset` -> model combo behavior:
  - `src/REvoDesign/driver/param_toggle_register.py`

Install metadata:

- Optional dependencies:
  - `pyproject.toml`
- Installer extras table:
  - `jsons/REvoDesignExtrasTableRich.json`

Tests:

- Sidechain solver matrix:
  - `tests/sidechain/test_sidechain_solvers.py`
- Focused runner tests (pattern examples):
  - `tests/sidechain/test_dlpacker_pytorch_runner_config.py`
  - `tests/sidechain/test_diffpack_runner_config.py`

## 3) Step-by-step integration

### Step A: Create a runner module

Create a new file under:

- `src/REvoDesign/sidechain/mutate_runner/<YourSolver>.py`

Requirements:

- Class name convention: `<YourSolver>_worker`
- Inherit `MutateRunnerAbstract`.
- Define class attributes:
  - `name` (user-facing solver name)
  - `installed` (`is_package_installed("<import_name>")`)
  - optional presets:
    - `weights_preset: tuple[str, ...]`
    - `default_weight_preset: str`

Minimum method behavior:

- `run_mutate(mutant)`
  - produce one output PDB for the mutant
  - return absolute/relative filesystem path that exists
- `run_mutate_parallel(mutants, nproc)`
  - return one PDB path per mutant, same order
- `reconstruct()` (if supported)
  - return reconstructed PDB path

Output naming convention (important):

- Always normalize final mutant file names to:
  - `mutant_pdbs/<RunnerClass>/<mutant.short_mutant_id>.pdb`
- If third-party tool emits generic basename outputs, rename/move after run.

### Step B: Add solver-specific config YAML

If your solver has runtime knobs, create:

- `src/REvoDesign/config/sidechain-solver/<solver>.yaml`

Use this pattern:

- Keep defaults safe and CPU-first.
- Include only runtime options needed by your wrapper.
- Read config with:
  - `reload_config_file("sidechain-solver/<solver>")["sidechain-solver"]`

Recommended fields:

- backend/model mode
- device
- cache path/read-only options
- runtime toggles (`fast`, memory mode, etc.)

### Step C: Export the runner

Add import and `__all__` entry in:

- `src/REvoDesign/sidechain/mutate_runner/__init__.py`

Also add compatibility import/export in:

- `src/REvoDesign/sidechain/sidechain_solver.py`

Notes:

- Registry is package-scoped and auto-discovers non-abstract subclasses.
- Import/export updates keep compatibility symbols explicit for external callers.

### Step D: Install metadata

Add optional extra in `pyproject.toml`:

- under `[project.optional-dependencies]`
- prefer GitHub URL format used in repo

Example:

```toml
your_solver = [
  "your_solver @ git+https://github.com/<owner>/<repo>.git#egg=your_solver",
]
```

Add installer extras entry in:

- `jsons/REvoDesignExtrasTableRich.json`

Include:

- `name`
- `extras_id`
- `depts` package list
- `python_version` bounds
- optional short `description`

### Step E: Wire tests

1. Add your runner to `tests/sidechain/test_sidechain_solvers.py` matrix.

- Keep skip-on-not-installed behavior via existing helper.

2. Add focused unit test with mocked third-party modules.

- Verify request construction from REvoDesign runner inputs.
- Verify config mapping and model/backend override behavior.
- Verify output rename to `<short_mutant_id>.pdb`.
- Verify concurrency/resource policy if custom.

## 4) Interface contract details

The runner must satisfy these invariants:

- Return existing PDB file paths.
- Preserve mutant order in `run_mutate_parallel` return list.
- No silent mismatch between number of mutants and outputs.
- Avoid output collisions in parallel mode.
- Be robust with `nproc=None`, small/large `nproc`, and empty mutant lists.

For UI model dropdown support:

- expose model/backend options via `weights_preset`
- set a safe `default_weight_preset`
- map `use_model` override in `__init__`

## 5) Validation playbook

### Fast preflight

- Syntax compile:

```bash
python -m compileall src/REvoDesign/sidechain/mutate_runner/<YourSolver>.py tests/sidechain/test_<your_solver>_runner_config.py
```

### Sidechain matrix

Run from repo root (in your test env):

```bash
make clean
conda run -n REvoDesignLatestDev /bin/zsh -lc "make kw-test PYTEST_KW='\"sidechain and solver\"'"
```

### Focused runner test

Use isolated temp workspace style used by this repo:

```bash
conda run -n REvoDesignLatestDev /bin/zsh -lc 'mkdir -p tmp-test-dir-with-unique-name && cd tmp-test-dir-with-unique-name && python -m pytest ../tests/sidechain/test_<your_solver>_runner_config.py -q'
```

### Expected outcomes

- Existing solver tests remain green.
- New solver is either:
  - `PASSED` if dependency installed, or
  - `SKIPPED` if intentionally not installed.
- Focused unit tests pass fully because they use mocks.

## 6) Common pitfalls and how to avoid them

### Pitfall: output file collision in parallel mode

Symptom:

- multiple jobs overwrite same basename output.

Fix:

- create per-mutant unique working output directories.
- always normalize final outputs to REvoDesign naming pattern.

### Pitfall: model/backend UI dropdown does nothing

Symptom:

- changing sidechain model value has no effect.

Fix:

- define `weights_preset` and `default_weight_preset`.
- consume `use_model` in runner `__init__`.

### Pitfall: cache-required backends fail intermittently

Symptom:

- runtime errors about missing read-only cache artifacts.

Fix:

- validate cache before inference.
- auto-bootstrap once on miss/invalid when policy allows.
- fail with actionable message if bootstrap fails.

### Pitfall: over-committing CPU

Symptom:

- machine becomes unresponsive during parallel mutation.

Fix:

- cap worker count to:
  - `min(requested_nproc, len(mutants), os.cpu_count())`
- for heavy solvers, enforce one-mutant-one-core semantics.

## 7) Suggested implementation checklist

- [ ] New runner module added and imports clean.
- [ ] YAML config added (if needed) and loaded in runner.
- [ ] Runner exported in mutate runner package.
- [ ] Sidechain solver compatibility exports updated.
- [ ] `pyproject.toml` extra added.
- [ ] Installer JSON extra entry added.
- [ ] Matrix test updated.
- [ ] Focused unit test added.
- [ ] Syntax compile + sidechain keyword suite + focused unit test passed.

## 8) Current reference implementations

Use these as templates:

- `src/REvoDesign/sidechain/mutate_runner/DLPackerPytorch.py`
- `src/REvoDesign/sidechain/mutate_runner/DiffPack.py`
- `tests/sidechain/test_dlpacker_pytorch_runner_config.py`
- `tests/sidechain/test_diffpack_runner_config.py`

They demonstrate:

- config-driven runner construction
- UI model override mapping
- output normalization
- cache readiness handling (DiffPack)
- parallel cap behavior (DiffPack)
- robust mock-based focused tests
