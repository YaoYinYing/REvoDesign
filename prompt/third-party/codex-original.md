# package
{package name}
# upstream branch as coding read-only reference
- {repo link}

# task
1. refact this project into a pip-installable package, with `pyproject.toml` used as meta info file. 
  - move all package code to a dir called `src/{package name}`
  - switch `build-system` of `pyproject.toml` to `"flit_core >=2,<4"`, following the instruction of `PEP 517`
  - move all example data to a dir called `example`. check if there's redundant example data that used in single test purpose, if so, make them simpler. preserve some example data to , instead of deleting them all.
  - add requirements to `pyproject.toml`, with loosen version policy, eg: `biopython<2`, `torch<=2.3.0` for package compatibilities, which may be found in README or `requirements.txt` or even `setup.py`
  - cleanups: if the repo has benchmark scripts, elevate them out of the package, like `./benchmark` or something. we dont want ship the package with these.
  - python supported: py3.9-3.12 in major
  - depts: drop non-core depts about jupyter and notebook and nglview, as we only want to refactor it into a solid pacakge with its main fuction. theres no need to run it in notebooks.

2. API design
  - imports: check all package python file to use full path imports, not dot-started local ones
  - high-level runner: 
    - create an object-oriented inferece runner class according to the api provided by this package. 
    - if the repo contains inference script or notebook, learn the inference workflow and design  the class for inference tasks. 
    - also check them carefully for more workflow hints
    - then import the class to the root `__init__.py` and join it to `__all__` list
  - lint style: keep the code clean and simple. follow the `PEP8` instructions. coding like a programmer working for Google.
  - compatiblity: dont have to be backward compatible w/ the original version
  - parallelism: check if it could be paralized in native way according to the project API. otherwise, you may use `joblib` or buildin cocurrent machanism within the runner
  - **Device check**: search for any code using `cuda` as a hard-coded device.
   - Refactor to accept a **general device** parameter that can be `CUDA`, `CPU`, or `MPS`.
   - Replace `.cuda()` / device literals with `torch.device(...)` or equivalent abstraction; centralize device selection.
   - Provide safe fallbacks and runtime capability checks (skip or degrade gracefully if the requested backend is unavailable).
   - if the package uses dependencies that do not support MPS, like DGLGraph, add a fallback datatransfer to the cpu device before proceeding, then transfer back to the gpu device after the task finishes.

3. Test and CI
  - test case: for each function and class, compose their tests suite carefully. organize it with a class
  - data: use sufficient example data to prepare the test, organize them w/ `@pytest.mark.parametrize`
  - parallelism: use `"pytest-xdist"` to enable test runs with parallel workers. to for huge tests that requires a lot of resources, use `@pytest.mark.serial` to mark them excluded from the parallelism
  - depts: in order to avoid errors like `pytest: command not found` during GHA, add a pip install extra flag `[test]` to include the test suite
  - test ci: create a proper GHA workflow for testing. set trigger as commited/released/pr-created to the main branch
  - test install: install the package in GHA workflow w/ `[test]` extra flag.

4. **Repo hygiene (minor cleanups)**  
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
5. Docs
  - update the readme according to these changes. if the changes are huge, rewrite a new version and append the original version to the end. resevere the original citation/author/acknowledgement/etc.
  - changes: clearify the changes against the original
  - write detailed doc about the APIs we just shiped/refactored/updated/created
  - create a full and complehensive doc at `./docs` with sphinx as doc build engine. 
  - doc depts:  add a pip install extra flag `[docs]` to include the docs suite
  - doc ci: 
    - create a proper GHA workflow for docs building. 
    - install the package in GHA workflow w/ `[docs]` extra flag. 
    - set trigger as commited/released/pr-created to the main branch. 

6. Changelog
  - events: keep a clear change log at `CHANGELOG.md`, following the `https://keepachangelog.com/en/1.0.0/`
  - format: see `changelog header and format` section

# changelog header and format
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added

### Changed

### Fixed

### Removed

...

```

# coding spirit
  - read the code carefully like an ophthalmologist, precise and accurate. keep waste out, let key component in.
  - be patient like a hidden spy, see the details, check the code, think deeply and reason in an extraordinary way.

