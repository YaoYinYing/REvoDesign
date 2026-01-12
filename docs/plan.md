# Plan on REvoDesign documents

## User Tutorial

### 1. Introduction

### 2. UI, modules, functions, menus

### 3. Case

## Developer guide



### Key concepts in REvoDesign

#### Biology
1. Mutant
2. Mutant Tree
3. Designers
4. Mutant Runners and Sidechain Solver
5. Design hotspots: pockets, surfaces, inter-chain contacts
6. Profiles (PSSM, ddG, ESM1v, etc): read various data sources
7. Mutant Visualizer: Load mutants into PyMOL
8. Evaluator, mutant decision makings
9. Interact: GREMLIN analyser
10. Cluster: Clustering mutant sequences


#### Software and API designs
1. Config Tree
2. Config Bus and Experiments
   1. Widget links
   2. Param Toggles
3. Logger system
4. Launch order: 
   1. basic SingletonAbstract
   2. bootsrtrap for configurations: verify, copy, load
   3. Root logger
   4. ConfigBus
   5. PyMOL Plugin class
5. Issues: warnnings and exceptions
6. File Extensions
7. Qt Wrapper: import PyQt from PyMOL
8. Menu actions: registry, bind, trigger
9.  Designers and Magician Protocol
10. Mutant Runners and Sidechain Solver
11. Rosetta related: RosettaPy, Backend Nodes, Python programming interface, REU/ddG Analyser
12. Citation Manager System
13. Editor: Monaco, bootstrap, server control, whitelist
14. Download Registry and File fetches: retrieve,retry,switch mirrors,validate, store, flatten
15. Package Manager (also the package manager util at `tools`)
16. Menu shortcuts
   1.  `AskedValue` dataclasses: representation of data form inputs, collected by `AskedValueCollection`
   2.  YAML config: registry and wrapper, dynamic inputs
   3.  Window pop-ups w/ `ValueDialog`: create, edit, submit, destroy, real-time updates
17. Tools Uitilities:
    1.  CGO: high-level API for PyMOL CGO generation, for future uses.
    2.  Customized widgets: Customized widgets for REvoDesign.
        1.  `REvoDesignWidget`: base class for customized widgets in REvoDesign.
        2.  `ButtonCoords` and `QButtonBrick`: data class for button coordinates and button brick.
        3.  `QHoverCross`: hover cross widget.
        4.  `QButtonMatrix`: button matrix widget for profile design and GREMLIN.
        5.  `QButtonMatrixGremlin`: button matrix widget for GREMLIN.
        6.  `set_widget_value` and `get_widget_value`: set and get widget values in a unified way.
        7.  `widget_signal_tape`: Tape for widget signals to certain events.
        8.  `refresh_widget_while_another_changed`: refresh widget while another widget changed for param toggles
        9.  `ParallelExecutor` and `QtParallelExecutor`: Parallel executors for REvoDesign.
        10. `create_cmap_icon`: Color Map Icon
        11. `dialog_wrapper`: Dialog wrapper for creating window pop-ups according to input parameters.
    3.  Mutant Tools: Mutant related tools
    4.  PyMOL Utils: PyMOL related helpers
    5.  Rosetta Utils: Rosetta related helpers
    6.  Session merger: Merge PyMOL sessions in a safe way (via commandline interface calls)

### UI design
### Translation

### Testing
1. Framework: PyTest + PyQt(Qtbot)
2. Test classification: avoid memory leaks during tests, which lead to slower test runs
   1. Fast Tests: Fastest and parallelizable (coverage created)
   2. Serial: Heavy and Runtime occupied (coverage appended)
   3. Slow Tests: Gremlin analysis (coverage appended)
3. Test Worker (for launching tests w/ head and handles specialised GUI interacts w/ REvoDesign main window)
   1. load molecules
   2. edit widgets
   3. click buttons
   4. UI screenshots
   5. PyMOL screenshots
   6. check mutant tree
   7. unique test case name
   8. performance report
   9. config injection
   10. reinitialize everything
4. Test data
   1. Minimal at `tests/data`
   2. Large case as urls
   

### CI

#### Basic

Platform: GitHub Actions

OS: Ubuntu by default, MacOS and Windows can be added if needed.

Python Version: as required in matrix

Environments: Conda, Pip

PyMOL versions:
- PyMOL Open Source (Conda-Forge), v2 or v3
- PyMOL Bundled (Schrodinger, officially), v2 or v3


Rosetta: Rosetta Docker (inject rosetta node as docker_mpi, only available for Ubuntu)

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

### Makefile shortcuts