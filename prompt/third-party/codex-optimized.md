
# Role
You are a senior Python packager and refactoring engineer. Work like you’re preparing a clean, reviewable PR in a top-tier OSS project.

# Inputs
- **Package name**: `{package_name}`
- **Upstream repository (read-only reference)**: `{repo_link}`

# High-level Goal
Refactor the repository into a **pip-installable** package using **src layout** and **PEP 517** with `flit_core`. Preserve functionality, improve API ergonomics, add tests, docs, and CI. Deliver a single, coherent pull request.

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
- Use `build-system` = `{"requires": ["flit_core >=2,<4"], "build-backend": "flit_core.buildapi"}`
- Add `[project]` metadata (name, version placeholder, description, authors, license, classifiers, urls).
- Add `[project.optional-dependencies]`:
  - `test = ["pytest", "pytest-xdist", "pytest-cov"]`
  - `docs = ["sphinx", "furo", "myst-parser", "sphinx-autodoc-typehints"]`
- Add `[project.dependencies]` with **loose** pins discovered from README/requirements/setup:
  - Examples: `biopython < 2`, `torch <= 2.3.0`
- Drop Jupyter/notebook/nglview and similar non-core runtime deps.
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

**High-level runner**
- Implement an object-oriented **inference runner** that reflects the package’s workflow (infer from existing scripts/notebooks):
  - `class InferenceRunner:`
    - `__init__(self, config: Optional[Mapping]=None, *, n_jobs: int=1, verbose: bool=False)`
    - `from_config(cls, path: str) -> "InferenceRunner"` (classmethod)
    - `prepare(self) -> None`
    - `run(self, inputs: Any) -> Outputs`
    - `save_results(self, outputs: Outputs, path: str) -> None`
    - `load_model(self, path: str) -> None` (if applicable)
  - Use **type hints** and **Google-style docstrings**.
  - Add **parallelism** if the native API supports it; otherwise, prefer `concurrent.futures` (built-in) or `joblib` as a fallback.
- Re-export in `src/{package_name}/__init__.py` and add to `__all__`.

**Style**
- PEP 8 compliance. Keep code small, clear, and review-friendly. Prefer composition over god objects.

**Compatibility**
- No strict backward-compat guarantee with pre-refactor structure.

---

## 3) Tests & CI

**Tests**
- One test suite per **public function/class**; cover happy-path + key edge cases.
- Use `pytest` with `@pytest.mark.parametrize` for data-driven cases.
- Introduce `@pytest.mark.serial` for heavyweight tests; default jobs run in parallel, serial-marked ones run single-threaded.
- Provide `tests/conftest.py` fixtures for example data.

**Parallelism**
- Use `pytest-xdist` (`-n auto`) in CI. Exclude `serial` marked tests from xdist runs.

**Installation for tests**
- Ensure `pip install .[test]` works.

**GitHub Actions**
- `test.yml`:
  - Triggers: push/pull_request to default branch and release tags.
  - Matrix: `python-version: [3.9, 3.10, 3.11, 3.12]`, `os: ubuntu-latest`.
  - Steps: checkout → setup python → cache pip → `pip install .[test]` → run tests in parallel → upload coverage artifact.

---

## 4) Documentation

**README**
- Update to reflect new install, usage, API entry points, and differences from upstream.

**Sphinx site**
- `docs/` using Sphinx + MyST:
  - `conf.py` with `sphinx.ext.autodoc`, `sphinx.ext.napoleon`, `sphinx-autodoc-typehints`, `myst_parser`.
  - `index.md` with quickstart, API overview, and links to `example/`.
  - `api/` auto-doc stubs (e.g., `api/{package_name}.md`) generated via `autodoc`.
- Install for docs in CI with `pip install .[docs]`.

**Docs CI**
- `docs.yml`:
  - Triggers: push/pull_request to main and release tags.
  - Build Sphinx; on `main` push, save HTML as artifact (optionally deploy if configured).

---

## 5) Changelog

- Maintain `CHANGELOG.md` with **Keep a Changelog** format and **SemVer**.
- Add sections: Unreleased / Added / Changed / Fixed / Removed.

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
3. **`pyproject.toml` (full content)** ready for `flit_core`.
4. **Updated `src/{package_name}/__init__.py`** (with `__all__` and version placeholder).
5. **`src/{package_name}/runner.py`** implementing `InferenceRunner` (typed, docstrings).
6. **At least 3 focused test files** under `tests/` demonstrating parameterization and a `serial` example.
7. **`.github/workflows/test.yml`** and **`docs.yml`** (full, minimal but robust).
8. **`docs/conf.py`** + **`docs/index.md`** + a small **API stub** page.
9. **`README.md`** (updated install/usage/API notes) and **`CHANGELOG.md`** with an initial entry.
10. **Unified diffs** for any modified existing files; **full content** for any new files.
11. **One-sentence commit subjects + body** for a small series of logical commits; then a **PR title and description**.

**Conventions**

* Use **absolute imports**.
* Use **Google-style docstrings** and **type hints**.
* Keep external dependencies minimal.
* Prefer standard library; allow `joblib` only if necessary.
* Avoid notebook-only utilities and GUI extras in runtime deps.

**Quality Gates (Definition of Done)**

* `pip install .` and `pip install .[test]` and `pip install .[docs]` succeed on Python 3.9–3.12.
* `pytest -q` passes locally with parallel workers; `@pytest.mark.serial` cases run and pass sequentially.
* `python -c "import {package_name}; from {package_name} import InferenceRunner"` succeeds.
* Docs build without warnings (`-W`) and produce an index with API links.
* CI workflows green on all matrix jobs.

---

## 7) Notes & Safeguards

* If large example data exists, keep a **minimal** subset sufficient for tests/docs; document any reductions in README.
* Do **not** remove core functionality.
* Where behavior changes are unavoidable (API cleanups), reflect them in README + CHANGELOG with concise rationale.

