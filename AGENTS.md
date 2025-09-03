# AGENTS instructions

## Python environment

- Requires Python >=3.9.
- Create a virtual environment and install all optional dependencies with:
  `python -m venv .venv && source .venv/bin/activate && make install`
- The extras installed by `make install` cover the project's optional features and test requirements.

## Pre-installation reference

- The workflow in `.github/workflows/unit_tests_tag.yml` shows the CI setup.
- For local runs, configure the headless display, create the `REvoDesign` conda environment, and install `pymol-open-source<3.1`.
- Skip Docker and Rosetta to save time; they are not required for basic testing.

## Pre-commit hooks

- Enable the hooks with `pre-commit install` so they run on each commit.
- Run `pre-commit run --all-files` before pushing to ensure formatting and linting with flake8, isort, autopep8, autoflake and other hooks.

## Running tests

- Use `make fast-test` to execute the default test suite.
- Run `make all-test` for the full test matrix.

## Documentation

- Project documentation is stored as Markdown under the `docs/` directory; no build step is required.

## Pull request guidelines

- Follow conventional commit messages such as `feat:`, `fix:`, or `docs:`.
- Ensure pre-commit hooks and tests pass before submitting.
