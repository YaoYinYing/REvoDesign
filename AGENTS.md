# AGENTS instructions

## Pre-installation reference

- Configure the headless display using `make setup-display-gha`
- Skip Docker and Rosetta to save time; they are not required for basic testing. Set environment variable `ENABLE_ROSETTA_CONTAINER_NODE_TEST=NO` to skip Rosetta.

## Python environment

- Use Miniconda for virtual environment creation.
- Requires Python=3.12.
- Create a virtual environment and install all optional dependencies with:
  
  ```shell
  # basic conda environment
  conda create -n REvoDesign python=3.12 -y

  # install pymol open source and PyQt5
  conda install -c conda-forge pymol-open-source pyqt=5 -n REvoDesign -y

  # check python and conda 
  conda info
  conda list
  which python
  which python3

  # install PyTorch. CPU only version is enough for testing.
  make install-pytorch-cpu-non-mac

  # install REvoDesign, some dependencies may fail but ok.
  make install

  # install DGL, fail is ok
  make install-dgl-linux

  # ensure the pytest suite
  make prepare-test
  ```

## Pre-commit hooks

- Enable the hooks with `pre-commit install` so they run on each commit.
- Run `pre-commit run --all-files` before pushing to ensure formatting and linting with flake8, isort, autopep8, autoflake and other hooks.

## Running tests

- Fastest and specified
  - Run `make kw-test PYTEST_KW='<keyword>'` or `make kw-test PYTEST_KW='"<keyword_a> or <keyword_b>"'` to run a keyword-based test.
- Fast and more coverage
  - Use `make fast-test` to execute the default test suite.
- Slowest yet full coverage
  - Run `make all-test` for the full test matrix.


## Documentation

- Project documentation is stored as Markdown under either the `docs/`  or related module directory; no build step is required.

## Pull request guidelines

- Follow conventional commit messages such as `feat:`, `fix:`, or `docs:`.
  - Use `[skip ci]` in the commit message to skip CI if non-code changes are made.
- Ensure pre-commit hooks and tests pass before submitting.
