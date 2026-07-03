# Developer Guide

This guide covers the REvoDesign codebase for contributors who want to
understand the architecture, extend the plugin with new scorers or sidechain
solvers, or make changes to the core infrastructure.

- **[Architecture](architecture.md)** -- Package structure, plugin lifecycle,
  singleton and registry patterns, config system, and extension points.
- **[Adding a Scorer](adding-a-scorer.md)** -- Step-by-step walkthrough for
  writing a new scorer plugin via `ExternalDesignerAbstract` and the
  `PluginRegistry`.
- **[Adding a Sidechain Solver](adding-a-sidechain-solver.md)** -- How to
  integrate a new sidechain packing / mutation tool as a `MutateRunnerAbstract`
  subclass.
