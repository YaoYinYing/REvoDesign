# Makefile Reference

The project root `Makefile` defines build, test, formatting, release, and
utility commands. Run `make help` to see all targets inline.

## Quick Reference

| Category | Target | Description |
|----------|--------|-------------|
| **Installation** | `install` | Install from pip with basic extras (`dlpacker`, `pippack`, `colabdesign`, `thermompnn`, `test`) and optional extras (`rfdiffusion_cpu`, `esm2`) |
| | `install-no-dept` | Install from pip with no dependencies (`--no-dependencies`) |
| | `install-pytorch-cpu-mac` | Install PyTorch 2.3 CPU build for macOS CI images |
| | `install-pytorch-cpu-non-mac` | Install PyTorch 2.3 CPU build (PyPI `--index-url https://download.pytorch.org/whl/cpu`) |
| | `install-dgl-linux` | Install DGL &lt;=2.4.0 (Linux, pip with `https://data.dgl.ai/wheels/torch-2.3/repo.html`) |
| | `install-dgl-win` | Install DGL for Windows/macOS (pip with `https://data.dgl.ai/wheels/repo.html`) |
| | `reinstall` | Clean, reformat, remove local config, then `pip install . -U` |
| | `install-pymol-plugin` | Copy the package manager startup script to `~/.pymol/startup/` |
| **Testing** | `test` | Run the `UnitTests.py` suite in an isolated temp directory |
| | `all-test` | Run all three test phases in sequence (fast parallel, serial, slow serial) and combine coverage |
| | `fast-test` | Run fast tests in parallel with `xdist` (`-n 4 -m "not serial"`) |
| | `serial-test` | Run serial tests (`-m "(serial and not very_slow) or bootstrap"`) |
| | `slow-test` | Run slow serial tests (`-m "(serial and very_slow) or bootstrap"`) |
| | `kw-test` | Run tests filtered by keyword (`-k PYTEST_KW`); supports single and multi-keyword expressions |
| | `kw-test-pdb` | Run keyword-filtered tests under `pdb` (`-s -v --pdb`) |
| | `macos-rosetta-test` | Run UI tests against the macOS PyMOL.app incentive installation (Rosetta) |
| **Formatting** | `black` | Reformat code with all pre-commit hooks (`pre-commit run --all-files`); stages black, isort, autoflake, pyupgrade, autopep8 |
| **Release** | `tag` | Bump version: extract old/new versions from `__init__.py` diff, insert dated changelog section, commit, create annotated tag |
| | `license-update` | Apply GPL-3.0 license header to all `.py` files |
| | `license-check` | Check license headers are present (`python tools/license_notice.py --check`) |
| **Translation/UI** | `compile-ui` | Compile `.ts` translation files to `.qm` binaries |
| | `translate` | Stage translation generation using `tools/translate.sh` |
| | `upload-gists` | Upload the PyMOL installer script, entry UI, and extras JSON to GitHub Gist |
| **Dev tools** | `reverse` | Generate class and package SVGs using `pyreverse` + `dot` |
| | `memray` | Profile memory under pytest, output flamegraph HTML (leak detection) |
| | `memray-live` | Profile memory in live terminal mode with `memray run --live` |
| | `clean` | Remove build artifacts, caches, coverage files, temp directories, and test outputs |
| | `help` | Print all available targets and their descriptions |
| **Setup** | `setup-display-gha` | Install X11 libraries and start Xvfb for headless Qt testing on GitHub Actions / CircleCI |
| | `prepare-test` | Install pytest, coverage, and server-test dependencies (celery, docker, Flask, SQLAlchemy) |

## Usage Notes

- **Temporary test directory**: All test targets run inside `tmp-test-dir-with-unique-name/` to ensure the *installed* package is tested, not the source tree. The conftest does `os.path.abspath("..")` relative to CWD, which fails outside this directory.
- **PYTEST_KW**: The keyword test target reads the `PYTEST_KW` variable. For multiple keywords use double quotes: `make kw-test PYTEST_KW='"citable or citation"'`.
- **Condatest environment**: Most targets expect a conda environment with PyMOL and the scientific stack installed. See the CI workflows for the full setup sequence.
- **Platform awareness**: PyTorch CPU wheels differ by platform (`install-pytorch-cpu-mac` vs `install-pytorch-cpu-non-mac`). DGL wheels also diverge between Linux and Windows/macOS.
- **black exit code**: The exit code of `make black` is advisory. Pre-commit hooks may leave the code with improved syntax and style regardless of the exit code.
