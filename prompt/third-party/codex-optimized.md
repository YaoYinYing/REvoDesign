# Role
You are a senior Python packager and refactoring engineer. Work like you’re preparing a clean, reviewable PR in a top-tier OSS project.

# Inputs
- **Package name**: `{package_name}`
- **Upstream repository (read-only reference)**: `{repo_link}`

# High-level Goal
Refactor the repository into a **pip-installable** package using **src layout** and **PEP 517** with `flit_core`. Preserve functionality, improve API ergonomics, add tests, docs, and CI. Deliver a single, coherent pull request.

---

## 0) Pre-flight: Dependency & Device Audit

**Add these tasks before refactor:**
1. **Dependency sweep**: check the dependencies of all `.py` files and record them into `pyproject.toml`.
   - Parse imports across the repo (ignore stdlib and local package modules).
   - Map imported modules to their PyPI packages.
   - Use **loose constraints** for compatibility (e.g., `biopython < 2`, `torch <= 2.3.0`).
   - Place runtime deps under `[project.dependencies]`; move dev/test/doc-only deps to `[project.optional-dependencies]`.
2. **Device check**: search for any code using `cuda` as a hard-coded device.
   - Refactor to accept a **general device** parameter that can be `CUDA`, `CPU`, or `MPS`.
   - Replace `.cuda()` / device literals with `torch.device(...)` or equivalent abstraction; centralize device selection.
   - Provide safe fallbacks and runtime capability checks (skip or degrade gracefully if the requested backend is unavailable).
3. **Repo hygiene (minor cleanups)**  
   Purge and ignore common junk so it never ships in wheels/sdists.  
   - Delete tracked artifacts: `*.pyc`, `.DS_Store`, and any `__pycache__/` directories. 
   - Make a git add and git commit to save the cleanup.
   - Add/extend `.gitignore` (example below).  
   - In `pyproject.toml`, exclude junk from **sdist**:  
     ```toml
     [tool.flit.sdist]
     exclude = [
       "**/__pycache__/**",
       "**/*.pyc",
       "**/*.pyo",
       "**/.DS_Store"
     ]
     ```
   - (Optional) Add a repo-local cleanup step to CI before building:
     ```bash
     git rm -r --cached --quiet -- **/__pycache__ || true
     git rm -r --cached --quiet -- *.pyc *.pyo || true
     git rm -r --cached --quiet -- .DS_Store || true
     ```
   - `.gitignore` minimal baseline:
     ```
     __pycache__/
     *.py[cod]
     .DS_Store
     .pytest_cache/
     .mypy_cache/
     .ruff_cache/
     .coverage
     htmlcov/
     dist/
     build/
     *.egg-info/
     ```
   - Make another git commit to save the changes on `.gitignore`
---

## 1) Packaging & Layout

**Target layout**
```

.
├── src/{package\_name}/
│   ├── **init**.py
│   └── ... (all package code moved here; no benchmarks/notebooks)
├── example/
│   └── ... (curated minimal examples; no duplicates)
├── tests/
├── docs/
├── benchmark/            # if repo has benchmarks, move them here (outside the package)
├── pyproject.toml
├── README.md
├── CHANGELOG.md
└── .github/workflows/
├── test.yml
└── docs.yml

````

**pyproject.toml (flit)**
- `build-system`: `{"requires": ["flit_core >=2,<4"], "build-backend": "flit_core.buildapi"}`
- `[project]` metadata (name, version placeholder, description, authors, license, classifiers, urls).
- `[project.dependencies]`: results of the **dependency sweep** with **loose** pins discovered from README/requirements/setup/source imports.
- `[project.optional-dependencies]`:
  - `test = ["pytest", "pytest-xdist", "pytest-cov"]`
  - `docs = ["sphinx", "furo", "myst-parser", "sphinx-autodoc-typehints"]`
- Drop Jupyter/notebook/nglview and other non-core runtime deps.
- If CLI exists, expose via `[project.scripts]`.
- Python versions: **3.9–3.12** via `Requires-Python`.

**Data & examples**
- Move all example data under `example/`.
- If single-test-only bulky samples exist, **shrink** to minimal repros but keep at least one per scenario.

**Benchmarks**
- If present, move them to top-level `benchmark/` (not inside `src/`).

---

## 2) API Design & Code Hygiene

**Imports**
- Replace relative (dot-started) imports with **absolute package imports** everywhere.

**Device abstraction (from Pre-flight)**
- Introduce a unified device selection utility, e.g.:
  - `def resolve_device(preferred: Literal["CUDA","CPU","MPS"]|None=None) -> torch.device: ...`
  - Capability detection with `torch.cuda.is_available()` / `torch.backends.mps.is_available()`.
  - All tensor/model moves use `.to(device)`; **remove** raw `.cuda()` calls.
- Thread this device through public APIs and the runner (see below).

**High-level runner**
- Implement an object-oriented **inference runner** reflecting the package’s workflow:
  - `class InferenceRunner:`
    - `__init__(self, config: Optional[Mapping]=None, *, device: Literal["CUDA","CPU","MPS"]|None=None, n_jobs: int=1, verbose: bool=False)`
    - `from_config(cls, path: str) -> "InferenceRunner"`
    - `prepare(self) -> None`
    - `run(self, inputs: Any) -> Outputs`
    - `save_results(self, outputs: Outputs, path: str) -> None`
    - `load_model(self, path: str) -> None` (if applicable)
  - Use **type hints** and **Google-style docstrings**.
  - Add **parallelism** if native API supports it; otherwise, use `concurrent.futures` or `joblib`.

**Re-export**
- Re-export in `src/{package_name}/__init__.py` and add to `__all__`.

**Style**
- PEP 8 compliance. Keep code small, clear, and review-friendly.

**Compatibility**
- No strict backward-compat guarantee with pre-refactor structure.

---

## 3) Tests & CI

**Tests**
- One test suite per **public function/class**; cover happy-path + key edge cases.
- Use `pytest` with `@pytest.mark.parametrize` for data-driven cases.
- Introduce `@pytest.mark.serial` for heavyweight tests.

**Device-aware tests**
- Add tests for device resolution and device-agnostic execution:
  - Parametrize over `["CPU","CUDA","MPS"]` but **skip** gracefully if backend not available.
  - Verify no `.cuda()` remains; ensure `.to(device)` paths are hit.
- For large GPU tests, mark as `serial` and/or `gpu` and skip in default CI.

**Parallelism**
- Use `pytest-xdist` (`-n auto`) in CI. Exclude `serial`/`gpu` marked tests from xdist runs.

**Installation for tests**
- Ensure `pip install .[test]` works.

**GitHub Actions**
- `test.yml`:
  - Triggers: push/pull_request to default branch and release tags.
  - Matrix: `python-version: [3.9, 3.10, 3.11, 3.12]`, `os: ubuntu-latest`.
  - Steps: checkout → setup python → cache pip → `pip install .[test]` → run tests in parallel (`-m "not serial and not gpu"`) → upload coverage artifact.

---

## 4) Documentation

**README**
- Update to reflect new install, usage, API entry points, **device selection**, and differences from upstream.

**Sphinx site**
- `docs/` using Sphinx + MyST:
  - `conf.py` with `sphinx.ext.autodoc`, `sphinx.ext.napoleon`, `sphinx-autodoc-typehints`, `myst_parser`.
  - `index.md` with quickstart, device notes, API overview, and links to `example/`.
  - `api/` auto-doc stubs (e.g., `api/{package_name}.md`).

**Docs CI**
- `docs.yml`:
  - Triggers: push/pull_request to main and release tags.
  - Build Sphinx; on `main` push, save HTML as artifact (optionally deploy if configured).

---

## 5) Changelog

- Maintain `CHANGELOG.md` with **Keep a Changelog** format and **SemVer**.
- Sections: Unreleased / Added / Changed / Fixed / Removed.

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog,
and this project adheres to Semantic Versioning.

## [Unreleased]
### Added
### Changed
### Fixed
### Removed
````

---

## 6) Implementation Plan (what to output)

**Produce the following in your response:**

1. **Refactor Plan Summary** (bullet list).
2. **Proposed File Tree** (final, after refactor).
3. **`pyproject.toml` (full content)** ready for `flit_core` **including dependency sweep results**.
4. **Updated `src/{package_name}/__init__.py`** (with `__all__` and version placeholder).
5. **`src/{package_name}/devices.py`** (device resolver) and **`src/{package_name}/runner.py`** (`InferenceRunner`, typed, docstrings).
6. **At least 3 focused test files** under `tests/` (parametrized), plus device-aware tests with conditional skips and a `serial` example.
7. **`.github/workflows/test.yml`** and **`docs.yml`** (full, minimal but robust).
8. **`docs/conf.py`** + **`docs/index.md`** + a small **API stub** page (include device notes).
9. **`README.md`** (install/usage/API/device notes) and **`CHANGELOG.md`** with an initial entry.
10. **Unified diffs** for any modified existing files; **full content** for any new files.
11. **One-sentence commit subjects + body** for a small series of logical commits; then a **PR title and description**.

**Conventions**

* Absolute imports only.
* Google-style docstrings + type hints.
* Minimal external deps; prefer stdlib; allow `joblib` if needed.
* No notebook-only utilities/GUI extras in runtime deps.

**Quality Gates (Definition of Done)**

* `pip install .`, `pip install .[test]`, `pip install .[docs]` succeed on Python 3.9–3.12.
* `pytest -q` passes locally with parallel workers; `@pytest.mark.serial` and `@pytest.mark.gpu` (if any) are handled correctly.
* **No `.cuda()` calls remain**; device selection is centralized and supports `CUDA`/`CPU`/`MPS`.
* Docs build without warnings (`-W`) and include device usage notes.
* CI workflows green on all matrix jobs.
* **No `*.pyc`, `.DS_Store`, or `__pycache__/` present in wheels/sdists**.

---

## 7) Notes & Safeguards

* If large example data exists, keep a **minimal** subset sufficient for tests/docs; document reductions in README.
* Do **not** remove core functionality.
* Reflect any unavoidable behavior changes (API cleanups) in README + CHANGELOG with concise rationale.

