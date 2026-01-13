# Plan on REvoDesign documents

This plan turns the scattered documentation notes into a cohesive set of guides that serve both new users and contributors. Each deliverable below should link back to the README and be written in approachable Markdown with diagrams or tables where useful.

## Goals

- Explain what REvoDesign does, why the workflow matters, and how to reproduce core tasks.
- Remove guesswork for developers by documenting architecture, APIs, and testing/CI expectations.
- Keep onboarding quick by pointing to automated setup commands and troubleshooting tips.

## Audiences

- **Practitioners**: Researchers using REvoDesign through the GUI or CLI who need task-driven tutorials.
- **Contributors**: Engineers extending the platform, writing plugins, or integrating new analyses.
- **Maintainers**: Owners of release, build, and infrastructure processes.

## User Tutorial (`docs/tutorials/**.md`)

### 1. Introduction

### 2. UI, modules, functions, menus

### 3. Case

## Developer guide

### Key concepts in REvoDesign

#### Biology (`docs/concepts/biological.md`)

1. [Mutant](../src/REvoDesign/common/mutant.py)
2. [Mutant Tree](../src/REvoDesign/common/mutant_tree.py)
3. [Designers](../src/REvoDesign/basic/designer.py)
4. [Mutant Runners](../src/REvoDesign/basic/mutate_runner.py) and [Sidechain Solver](../src/REvoDesign/sidechain/sidechain_solver.py)
5. Design hotspots: [pockets](../src/REvoDesign/structure/PocketSearcher.py), [surfaces](../src/REvoDesign/structure/SurfaceFinder.py), inter-chain contacts
6. [Profiles](../src/REvoDesign/common/profile_parsers.py) (PSSM, ddG, ESM1v, etc): read various data sources
7. [Mutant Visualizer](../src/REvoDesign/common/mutant_visualise.py): Load mutants into PyMOL
8. [Evaluator](../src/REvoDesign/evaluate/evaluator.py), mutant decision makings
9. [Interact](../src/REvoDesign/phylogenetics/evo_mutator.py): [GREMLIN tool](../src/REvoDesign/phylogenetics/gremlin_tools.py) and Pytorch [implementation](../src/REvoDesign/phylogenetics/gremlin_pytorch.py) and [validation](../notebooks/validate_gremlin_pytorch.ipynb)
10. [Cluster](../src/REvoDesign/clusters/cluster_sequence.py): Clustering mutant sequences
11. [Rosetta Tasks](../src/REvoDesign/shortcuts/tools/rosetta_tasks.py)

#### Software and API designs (`docs/api-designs/**.md`)

1. [Singleton Abstract](../src/REvoDesign/basic/README.md)
2. Config Tree
   1. [File Tree](../src/REvoDesign/config)
   2. [Bootstrap](../src/REvoDesign/bootstrap/__init__.py)
   3. [Config utils](../src/REvoDesign/bootstrap/set_config.py)
3. [Config Bus](../src/REvoDesign/driver/ui_driver.py) and Experiments
   1. [Widget links](../src/REvoDesign/driver/widget_link.py)
   2. [Param Toggles](../src/REvoDesign/driver/param_toggle_register.py)
4. [Logger system](../src/REvoDesign/logger/logger.py)
5. Launch order
   1. basic [SingletonAbstract](../src/REvoDesign/basic/abc_singleton.py)
   2. [bootsrtrap](../src/REvoDesign/bootstrap/__init__.py) for configurations: verify, copy, load
   3. [Root logger](../../src/REvoDesign/logger/logger.py)
   4. [ConfigBus](../src/REvoDesign/driver/ui_driver.py)
   5. PyMOL [Plugin](../src/REvoDesign/REvoDesign.py) class
6. Issues: [warnnings](../src/REvoDesign/issues/warnings.py) and [exceptions](../src/REvoDesign/issues/exceptions.py)
7. File Extensions: [basic class](../src/REvoDesign/basic/extensions.py) and [registry](../src/REvoDesign/common/file_extensions.py)
8. [Qt Wrapper](../src/REvoDesign/Qt/qt_wrapper.py): import PyQt from PyMOL
9. Menu actions: [registry](src/REvoDesign/application/menu.py), [bind, trigger](../src/REvoDesign/basic/menu_item.py)
10. [Designers](../src/REvoDesign/basic/designer.py) and [Magician Protocol](../src/REvoDesign/magician/__init__.py). See also this [README](../src/REvoDesign/magician/README.md)
11. [Mutant Runners](../src/REvoDesign/sidechain/mutate_runner) and [Sidechain Solver](../src/REvoDesign/sidechain/sidechain_solver.py). [How to use them outside REvoDesign workflow?](../src/REvoDesign/sidechain/mutate_runner/README.md)
12. Rosetta related: RosettaPy, Backend Nodes, Python programming interface, REU/ddG Analyser
13. [Citation Manager System](../src/REvoDesign/citations/citation_manager.py) and [`get_cited` decorator](../src/REvoDesign/tools/utils.py)
14. Editor: Monaco, [bootstrap](../src/REvoDesign/editor/monaco/monaco.py), [server control, whitelist](../src/REvoDesign/editor/monaco/server.py)
15. [Download Registry and File fetches](../src/REvoDesign/tools/download_registry.py): retrieve,retry,switch mirrors,validate, store, flatten
16. [Package Manager](../src/REvoDesign/tools/package_manager.py) (also the package manager util at `tools`)
    1. UI: stored at `../src/REvoDesign/UI/REvoDesign-PyMOL-entry.ui`, uploaed to Gist via `make upload-gists`
    2. bootstrap of UI and Extras rich table
    3. Extras registry:
       1. stored at `../jsons/REvoDesignExtrasTableRich.json`, uploaded to Gist via `make upload-gists`
       2. fetch, record, solve, filter, show, install
    4. Git solving
    5. live run command
    6. pip installer (commit, tag, branch, extras)
    7. Package Manager
    8. Worker Thread
    9. Unified worker thread wrapping
    10. notify box and decide forks
    11. issue collections and sensitive data filtering
    12. trigger button holding and animation
    13. lazy loading of REvoDesign packages
17. Menu shortcuts
       1. [`AskedValue` dataclasses](../src/REvoDesign/tools/customized_widgets.py): representation of data form inputs, collected by `AskedValueCollection`
       2. YAML config: [registry](../src/REvoDesign/shortcuts/registry) and [wrapper](../src/REvoDesign/shortcuts/wrappers), dynamic inputs, [resolve inputs from various sources](../src/REvoDesign/shortcuts/utils.py)
       3. Window pop-ups w/ [`ValueDialog`]((../src/REvoDesign/tools/customized_widgets.py)): create, edit, submit, destroy, real-time updates. See also the [README](../src/REvoDesign/shortcuts/README.md).

18. Tools Uitilities:
    1. [CGO](../src/REvoDesign/tools/cgo_utils.py): high-level API for PyMOL CGO generation, for future uses. Contains an easter egg.
    2. [Customized widgets](../src/REvoDesign/tools/customized_widgets.py): Customized widgets for REvoDesign.
        1. `REvoDesignWidget`: base class for customized widgets in REvoDesign.
        2. `ButtonCoords` and `QButtonBrick`: data class for button coordinates and button brick.
        3. `QHoverCross`: hover cross widget.
        4. `QButtonMatrix`: button matrix widget for profile design and GREMLIN.
        5. `QButtonMatrixGremlin`: button matrix widget for GREMLIN.
        6. `set_widget_value` and `get_widget_value`: set and get widget values in a unified way.
        7. `widget_signal_tape`: Tape for widget signals to certain events.
        8. `refresh_widget_while_another_changed`: refresh widget while another widget changed for param toggles
        9. `ParallelExecutor` and `QtParallelExecutor`: Parallel executors for REvoDesign.
        10. `create_cmap_icon`: Color Map Icon
        11. `dialog_wrapper`: Dialog wrapper for creating window pop-ups according to input parameters.
    3. [Mutant Tools](../src/REvoDesign/tools/mutant_tools.py): Mutant related tools
    4. [PyMOL Utils](../src/REvoDesign/tools/pymol_utils.py): PyMOL related helpers
    5. [Rosetta Utils](../src/REvoDesign/tools/rosetta_utils.py): Rosetta related helpers
    6. [Session merger](../src/REvoDesign/tools/SessionMerger.py): Merge PyMOL sessions in a safe way (via commandline interface calls to avoid segfaults caused by loading the same-name objects into a PyMOL session)
19. PyMOL extended command [auto-completion](../src/REvoDesign/shortcuts/README.autocompletion.md)

### HOW-TOs

#### Functions (`docs/how-to/add-new-functions.md`)

1. Add a new designer
2. Add a new mutate runner
3. Support a new profile format
4. Add a new Rosetta Protocol
5. Add a new design function

#### Code (`docs/how-to/add-new-code.md`)

1. Add a new config file
2. Convert a new function into a window pop and register it to a QMenu
3. Add a new dependency extra record
4. Modify the UIs and translate them
5. Synchronize the gists for the PM

#### Maintenance (`docs/how-to/get-codebase-maintainable.md`)

1. Write tests and get them to pass
2. Get codebase formatted
3. Bump version and record changes in CHANGELOG
4. Troubleshoot when failed to get a CI green check
5. Vibe-coding tool uses (certain functions, tests, docs, etc.) under strict control
6. Typing checker matters, yet it's not always the law. **Don't** fight against it and struggle to get it right.

### PSSM_GREMLIN (`docs/pssm_gremlin_server.md`)

1. [Run script](../server/REvoDesign_PSSM_GREMLIN.sh) for direct execution
2. Server setup
   1. Documentation at this [README](../server/README.md)
   2. Docker image at [DockerHub](https://hub.docker.com/r/yaoyinying/revodesign-pssm-gremlin)
   3. Also [Dockerfile for making the image](../server/docker/Dockerfile)
   4. Environment [inside container](../server/env/GREMLIN.yml) and [for the server](../server/env/REvoDesign.yml)

### UI design (`docs/ui-designs.md`)

REvoDesign uses `Qt Designer` for UI design. UI files are located in `src/REvoDesign/UI` directory. Translated UI code is compiled via `PYQT Integration` extension of VS Code.

### Translation (`docs/ui-translation.md`)

REvoDesign uses `Qt Linguist` for UI translation. Translation files (`*.qm, *.ts`) are located in `src/REvoDesign/UI/language` directory. Available languages must be registered in `src/REvoDesign/UI/language/language.json` so that they can be loaded by REvoDesign.

Package manager currently doesn't have any translations.

### Testing (`docs/testing.md`)

1. Framework: PyTest + PyQt(Qtbot)
2. Test classification: avoid memory leaks during tests, which lead to slower test runs
   1. Fast Tests: Fastest and parallelizable (coverage created). `pytest-xdist` is used.
   2. Serial: Heavy and resource-occupying (coverage appended)
   3. Slow Tests: Gremlin analysis (coverage appended)
3. [Test Worker](../tests/conftest.py) (for launching tests w/ head and handles specialised GUI interacts w/ REvoDesign main window)
   1. Load molecules
   2. Edit widgets
   3. Click buttons
   4. UI screenshots
   5. PyMOL screenshots
   6. Check mutant tree
   7. Unique test case name
   8. Performance report
   9. Config injection
   10. Reinitialize everything
4. Test data
   1. Minimal at `tests/data`
   2. Large case as urls
5. Test runs
   The test run must be under `<repo-root>/tmp-test-dir-with-unique-name` to avoid polluting the repo. Shortcut commands in Makefile have already included this.
6. Cleanup:
   Run `make clean` to remove all temporary files.
7. Test the changes on local machine before pushing to repo.
   Keyword testings first, then the fast, finally the full.

### CI file for GHA (`docs/ci-gha.md`)

- [Test suite](../.github/workflows/unit_tests_tag.yml)
- [linting badge](../.github/workflows/lint_badge.yml)
- [PR semantic check](../.github/workflows/schedule-update-actions.yml)
- [PSSM GREMLIN docker image](../.github/workflows/docker-image.yml)
- [Action version upgrader](../.github/workflows/schedule-update-actions.yml)

> [!WARNING]
> DO NOT EVER USE CIRCLECI.

#### CI concept

Test REvoDesign with different versions of Python and PyMOL releases across different platforms.

| Aspect                     | Configuration                                                                                             | Notes                                                                                              |
|----------------------------|-----------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| Platform                   | GitHub Actions                                                                                            | Mirrors prod workflows; supports matrix jobs + caching.                                            |
| Operating systems          | Ubuntu (primary), macOS, Windows                                                                          | Linux images run daily; macOS/Windows triggered for release validation when additional coverage needed. |
| Python versions            | 3.10, 3.11, 3.12                                                                                          | Matrix fan-out ensures backward compatibility across supported interpreters.                       |
| Environment managers       | Conda, Pip                                                                                                | Conda used for PyMOL + scientific stack; pip wheel path covers lightweight smoke tests.            |
| PyMOL channels / versions  | PyMOL Open Source (Conda-Forge), PyMOL Bundled (Schrödinger) v2 & v3                                      | Ensures plugin works both with OSS builds and official bundle APIs.                                |
| Rosetta integration        | Rosetta Docker (docker_mpi node injection, Ubuntu-only)                                                   | Pulled conditionally using `ENABLE_ROSETTA_CONTAINER_NODE_TEST`; skipped in lightweight workflows. |

#### CI workflow

1. Cancel previous runs
2. Checkout repository
3. Setup Qt headless virtual display device
4. Pull Rosetta Docker image
5. Setup Conda environment
6. Setup PyMOL
7. Setup REvoDesign
   1. pytorch
   2. REvoDesign, all dependencies as possible
   3. DGL, required by RFDiffusion
   4. Ensure test suites
   5. Run all tests (in order of fast, serial, slowest)
   6. collect coverage data as xml
   7. upload coverage data to Codecov
   8. cleanup environment

### Release process (`docs/release-tag.md`)

1. Check the latest CI results
2. Document any changes in the changelog `CHANGELOG.md`
3. Change the version number in `src/REvoDesign/__init__.py`, make sure the new version is correct and could pass the [checker](https://regex101.com/r/6AoOI9/1) or match the regex:

   ```regex
   v?(?:(?:(?P<epoch>[0-9]+)!)?(?P<release>[0-9]+(?:\.[0-9]+)*)(?P<pre>[-_\.]?(?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))[-_\.]?(?P<pre_n>[0-9]+)?)?(?P<post>(?:-(?P<post_n1>[0-9]+))|(?:[-_\.]?(?P<post_l>post|rev|r)[-_\.]?(?P<post_n2>[0-9]+)?))?(?P<dev>[-_\.]?(?P<dev_l>dev)[-_\.]?(?P<dev_n>[0-9]+)?)?)(?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?
   ```

   It also can be checked via the test suite:

   ```bash
   make kw-test PYTEST_KW='test_version'
   ```

4. Save the file `src/REvoDesign/__init__.py`
5. Commit the changes by running `make tag`. A new tag will be created in tag history and the changelog.

### Code Quality (`docs/code-quality.md`)

Various tools are engaged to maintain the code quality.

#### Cloud-based

- Maintainability: Codebase maintainability check
- DeepSource: Code Quality analysis
- CodeRabbit: Code Review (150 files maximum)
- Codecov: Test coverage tracking
- Qlty: Code Quality analysis
- ChatGPT Codex: Code Review

#### Pre-commit hooks

See the [pre-commit hooks](../.pre-commit-config.yaml) for details.

- `pyupgrade`
- `pycln`
- `pygrep-hooks`
- `check-manifest`
- `autopep8`
- `flake8`
- `autoflake`
- `isort`
- `black`

> [!IMPORTANT]
> Note that the hooks will not be run before committing, as current quality gate wont allow it. ;-)

### Makefile shortcuts (`docs/makefile-shortcuts.md`)

(see `Makefile` for details)

| command              | description                                                                                               |
|----------------------|-----------------------------------------------------------------------------------------------------------|
| help                 | Print this message and exit                                                                               |
| setup-display-gha    | Setup ubuntu display for GitHub Actions and CircleCI                                                      |
| upload-gists         | Upload Gist files                                                                                         |
| install-pymol-plugin | Install PyMOL plugin                                                                                      |
| install              | Install from pip                                                                                          |
| install-no-dept      | Install from pip, no dependencies                                                                         |
| install-pytorch-cpu  | Install torch-cpu for ci runner image                                                                     |
| install-dgl-linux    | Install DGL(<=2.4.0) for Ubuntu                                                                           |
| install-dgl-win      | Install DGL(<=2.2.1) for Windows and macOS                                                                |
| reinstall            | Reinstall after code changes                                                                              |
| compile-ui           | Compile UI to Python code                                                                                 |
| translate            | Translate UI translation into binaries                                                                    |
| prepare-test         | Run pip to install pytest-related packages                                                                |
| test                 | Run the UnitTest suite                                                                                    |
| all-test             | Run all tests (firstly the parallel(also the fastest), secondly the serial(also the slower), finally the slowest) |
| fast-test            | Run all fast tests (first order)                                                                          |
| serial-test          | Run all serial tests (second order)                                                                       |
| slow-test            | Run all slow tests (third order)                                                                          |
| kw-test              | Run the Keyword Test suite                                                                                |
| kw-test-pdb          | Run the Keyword Test suite with pdb                                                                       |
| macos-rosetta-test   | Run UI tests versus PyMOL incentive installation (MacOS Application)                                      |
| memray               | Memoray profile for leakage, saved as html file                                                           |
| memray-live          | Memoray profile for leakage in live mode                                                                  |
| tag                  | Bump a new tag from package version to github tag                                                         |
| black                | Reformat the code with pre-commit hook                                                                    |
| reverse              | Run pyreverse for package and methods and create SVGs                                                     |
| license-update       | License updates for all files                                                                             |
| license-check        | Check license for all files                                                                               |
| clean                | Clean up build and generated files                                                                        |
