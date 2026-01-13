# REvoDesign Documentation Plan

This plan turns the scattered documentation notes into a cohesive set of guides that serve both new users and contributors. Each deliverable below should link back to the README and be written in approachable Markdown with diagrams or tables where useful.

## Goals
- Explain what REvoDesign does, why the workflow matters, and how to reproduce core tasks.
- Remove guesswork for developers by documenting architecture, APIs, and testing/CI expectations.
- Keep onboarding quick by pointing to automated setup commands and troubleshooting tips.

## Audiences
- **Practitioners**: Researchers using REvoDesign through the GUI or CLI who need task-driven tutorials.
- **Contributors**: Engineers extending the platform, writing plugins, or integrating new analyses.
- **Maintainers**: Owners of release, build, and infrastructure processes.

## Deliverables Snapshot

| Doc | Owner | Content Summary | Status Target |
| --- | ----- | --------------- | ------------- |
| README refresh | Docs WG | Link to tutorials, quick start matrix, support channels | Ready |
| `docs/tutorial.md` | UX + Bio team | Step-by-step walkthrough with screenshots/video refs | Draft |
| `docs/developer-guide.md` | Core devs | Architecture, APIs, style, contribution workflow | Draft |
| `docs/testing.md` | QA | Test tiers, fixtures, CI diagnostics | Draft |
| `docs/ci.md` | DevOps | GitHub Actions matrix, caching, credentials handling | Draft |
| `docs/ui-design.md` | UX | Widget conventions, accessibility, translation workflow | Backlog |

## User Tutorial (`docs/tutorial.md`)
1. **Introduction**
   - Short overview of REvoDesign goals; cite supported operating systems and environment setup (conda + PyMOL + PyTorch CPU).
   - Link to demo datasets and video overview.
2. **Interface Tour**
   - Break down UI panels: configuration pane, mutant tree, workspace canvas, 3D PyMOL view, log console.
   - Highlight menus with annotated screenshots.
3. **Core Workflow**
   - Importing structures, defining design hotspots, running mutant designers.
   - Visualizing results (Mutant Visualizer, GREMLIN analyzer) and interpreting metrics (ddG, PSSM).
4. **Case Studies**
   - Mini-project: mutate binding pocket, evaluate with GREMLIN clustering, export report.
   - Provide copy/paste commands, expected runtime, troubleshooting checklist.
5. **Appendix**
   - Keyboard shortcuts, data file formats, glossary of domain terms.

## Developer Guide (`docs/developer-guide.md`)

### Architecture Overview
- Explain high-level modules: Config tree/bus, Designer protocols, Mutant runners, Visualizer pipeline.
- Detail launch order: `SingletonAbstract` bootstrap → configuration verification/copying → root logger → ConfigBus → PyMOL plugin initialization.

### Key Concepts
1. **Biology Domain**
   - Mutants, mutant trees, designer/runner roles.
   - Design hotspots (pockets, surfaces, inter-chain contacts).
   - Profiles: PSSM, ddG, ESM1v ingestion and how data flows to UI widgets.
   - Evaluator workflow and interaction with PyMOL visual inspections.
   - GREMLIN analyzer integration and sequence clustering pipeline.
2. **Software & APIs**
   - Config Tree/Bus schema, experiment definitions, widget links, parameter toggles.
   - Logging guidelines, warning/exception taxonomy, file extensions.
   - PyQt wrapper strategy (importing PyQt within PyMOL), menu registry/bind/trigger pattern, Monaco editor embedding, download/file-fetch pipeline.
   - Package Manager internals: UI, bootstrap, Git solver, pip installer options, worker thread orchestration, notification UX, issue filtering, lazy loading.
   - Utility packages: CGO helpers, custom widgets (`REvoDesignWidget`, `QButtonMatrix`, etc.), PyMOL/Rosetta helpers, session merger flow.
   - Designer/Magician protocol, runner + sidechain solver, RosettaPy backend nodes and REU/ddG analyzer.
   - Citation manager, shortcut mapping, YAML config registry, `ValueDialog` pop-ups, parallel executor abstractions.

### Coding Guidelines
- Preferred patterns (dataclasses for `AskedValue`, signal tape usage, `refresh_widget_while_another_changed` for param toggles).
- Error handling, thread safety rules, style conformance (black/isort/autoflake).
- Example PR checklist referencing pre-commit and tests.

### Extension Recipes
- Adding a new designer or runner.
- Registering a menu action with Qt widgets and ConfigBus.
- Integrating a third-party model (e.g., new diffusion backend) through package manager hooks.

## UI Design & Translation (`docs/ui-design.md`)
- Component library overview with screenshots.
- Accessibility guidelines: color maps, keyboard navigation, hover aids (`QHoverCross`).
- Internationalization: translation source files, workflow for submitting `.po` files, QA steps.
- PyMOL integration tips and fallback behaviors when headless.

## Testing Strategy (`docs/testing.md`)
1. **Framework**
   - PyTest + PyQt (qtbot), CLI entry points, environment variables for headless display.
2. **Test Tiers**
   - Fast tests (parallel, coverage baseline), Serial heavy tests (UI + PyMOL interaction), Slow GREMLIN analysis suite.
3. **Test Worker Toolkit**
   - Features provided (molecule loaders, widget editors, button clickers, UI/PyMOL screenshots, mutant tree verifiers, performance reporters, config injection, teardown lifecycle).
4. **Data Management**
   - Minimal fixtures in `tests/data`, large datasets via downloadable URLs and caching guidance.
5. **Practices**
   - Memory leak avoidance, unique case naming, how to add new fixtures, when to mark tests as slow.

## Continuous Integration (`docs/ci.md`)
- Platform: GitHub Actions, default Ubuntu with optional macOS/Windows jobs.
- Python versions, Conda vs pip envs, PyMOL sources (Conda Forge vs bundled) and Rosetta Docker availability.
- Workflow breakdown:
  1. Cancel previous runs.
  2. Checkout repo, configure headless display (`make setup-display-gha`).
  3. Pull Rosetta Docker image (Ubuntu jobs only).
  4. Setup Conda, install PyMOL, PyTorch CPU, REvoDesign deps, DGL (best-effort).
  5. Run `make prepare-test`, execute fast → serial → slow suites, collect XML coverage, upload to Codecov.
  6. Cache/minimize large downloads, final cleanup.
- Troubleshooting table for flaky tests, GPU unavailability, Docker pull limits.

## Makefile & Tooling Reference (`docs/makefile.md`)
- Document shortcuts for environment prep (`make install`, `make install-pytorch-cpu-non-mac`, `make install-dgl-linux`).
- Testing helpers (`make fast-test`, `make kw-test`, `make all-test`), linting (`make black`, `pre-commit run --all-files`).
- Releasing helper (`make tag`) after changing the version number. A new commit and tag will be created and pushed to GitHub.
- Dev utilities: launching GUI, building docs, cleaning cache.

## Release Notes Process (`docs/release.md`)
- Versioning policy, changelog template, conventional commit reminders.
- CI gates before release, packages to publish, citation updates.
- Post-release checklist: notify users, update docs snapshots, create tutorial tags.

## Maintenance & Ownership (`docs/ownership.md`)
- Table of modules vs maintainers.
- Response SLAs for bug reports and security issues.
- Process for proposing doc updates (issue template + PR labels).
