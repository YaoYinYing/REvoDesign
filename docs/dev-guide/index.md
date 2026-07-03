# Developer Guide

This guide covers the REvoDesign codebase for contributors who want to
understand the architecture, extend the plugin with new scorers or sidechain
solvers, or make changes to the core infrastructure.

- **[Concepts](concepts.md)** -- Key biological and software design concepts
	  explained: mutant, mutant tree, designers, mutate runners, hotspots,
	  profiles, GREMLIN, clusters, and the core software patterns.
- **[Architecture](architecture.md)** -- Package structure, plugin lifecycle,
  singleton and registry patterns, config system, and extension points.
- **[Concepts](concepts.md)** -- Key biological and software design concepts:
  mutant, mutant tree, designers, mutate runners, hotspots, profiles, GREMLIN,
  clusters, and core software patterns.
- **[Testing](testing.md)** -- Test framework (pytest + QtBot), test
  classification (fast/serial/slow), conftest harness, test data, and CI
  workflow.
- **[CI/CD](ci-cd.md)** -- GitHub Actions workflows, matrix configuration,
  environment variables, and required secrets.
- **[PSSM/GREMLIN Server](server.md)** -- Backend compute service for
  PSSM profile generation and GREMLIN co-evolution analysis.
- **[Monaco Editor](editor.md)** -- Embedded VS Code editor for YAML
  configuration editing with syntax highlighting and file whitelisting.
- **[Rosetta Integration](rosetta.md)** -- RosettaPy bridge for energy
  minimization, ddG scoring, ligand docking, and sidechain packing.
- **[Translation (i18n)](translation.md)** -- Qt Linguist-based multi-language
  support, adding new languages, and the translation pipeline.
- **[UI Design](ui-design.md)** -- Qt Designer workflow, `.ui` files, object
  naming conventions, and the runtime UI loading system.
- **[CGO Graphics](cgo.md)** -- Compiled Graphics Objects: PyMOL's low-level
  OpenGL drawing API and REvoDesign's high-level `cgo_utils` wrapper.
- **[Makefile Reference](makefile-reference.md)** -- A command-by-command
  reference for all `make` targets.
- **[Package Manager](package-manager.md)** -- Standalone installer internals:
  thread management, Git solving, pip installation, and extras registry.
- **[Adding a Scorer](adding-a-scorer.md)** -- Step-by-step walkthrough for
  writing a new scorer plugin via `ExternalDesignerAbstract`.
- **[Adding a Sidechain Solver](adding-a-sidechain-solver.md)** -- How to
  integrate a new sidechain packing / mutation tool.
- **[Adding a Profile Parser](how-to-add-profile.md)** -- How to support a new
  mutagenesis profile format.
- **[Adding a Configuration File](how-to-add-config.md)** -- How to add a new
  YAML config file and wire it into the widget system.
- **[Adding a Shortcut](how-to-add-shortcut.md)** -- How to register a new
  function as a `cmd.extend` command with a dialog popup and menu entry.
- **[Codacy Fix Playbook](codex-codacy.md)** -- AI-assisted workflow for
  triaging and fixing Codacy findings in risk-prioritized batches.
- **[DeepSource Fix Playbook](codex-deepsource.md)** -- AI-assisted workflow
  for triaging and fixing DeepSource findings with minimal, verified diffs.
