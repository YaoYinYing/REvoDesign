# Developer Guide

This guide covers the REvoDesign codebase for contributors who want to
understand the architecture, extend the plugin with new scorers or sidechain
solvers, or make changes to the core infrastructure.

- **[Concepts](concepts.md)** -- Key biological and software design concepts
	  explained: mutant, mutant tree, designers, mutate runners, hotspots,
	  profiles, GREMLIN, clusters, and the core software patterns.
- **[Architecture](architecture.md)** -- Package structure, plugin lifecycle,
  singleton and registry patterns, config system, and extension points.
- **[Adding a Scorer](adding-a-scorer.md)** -- Step-by-step walkthrough for
  writing a new scorer plugin via `ExternalDesignerAbstract` and the
  `PluginRegistry`.
- **[Adding a Sidechain Solver](adding-a-sidechain-solver.md)** -- How to
  integrate a new sidechain packing / mutation tool as a `MutateRunnerAbstract`
  subclass.
- **[Adding a Profile Parser](how-to-add-profile.md)** -- How to support a new
  mutagenesis profile format by subclassing `ProfileParserAbstract`.
- **[Adding a Configuration File](how-to-add-config.md)** -- How to add a new
  YAML config file and wire it into the widget system.
- **[Adding a Shortcut / PyMOL Command](how-to-add-shortcut.md)** -- How to
  register a new function as a `cmd.extend` command with a dialog popup and
  menu entry.
- **[Makefile Reference](makefile-reference.md)** -- A command-by-command
  reference for all `make` targets: installation, testing, formatting, release,
  translation, dev tools, and CI setup.
- **[PSSM/GREMLIN Server](server.md)** -- Backend compute service for
  PSSM profile generation and GREMLIN co-evolution analysis. Architecture,
  API endpoints, Docker deployment, and run scripts.
- **[CI/CD](ci-cd.md)** -- GitHub Actions workflows, matrix configuration,
  environment variables, and required secrets.
