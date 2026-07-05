# User Guide

REvoDesign is a PyMOL plugin for semi-rational enzyme redesign. It integrates
structural analysis, evolutionary data, and computational mutagenesis into a
graphical workflow.

## Workflow

REvoDesign's tabbed interface follows the stages of a rational design pipeline:

| Stage | Tab | What you do |
|-------|-----|-------------|
| **Prepare** | Prepare | Load structure, detect binding pockets and surface-exposed hotspots |
| **Mutate** | Mutate | Generate virtual saturation mutagenesis libraries under PSSM constraints |
| **Evaluate** | Evaluate | Visually inspect and accept/reject mutants in the MutantTree |
| **Cluster** | Cluster | Reduce library size via sequence-based clustering with optional Rosetta energy scoring |
| **Visualize** | Visualize | Cross-screen with external tools (ddG, ESM-1v) and display experimental data on structure |
| **Interact** | Interact | Explore co-evolved residue pairs via GREMLIN MRF and design combinatorial mutants |
| **Socket** | Socket | Collaborate with other users on shared sessions |
| **Config** | Config | Inspect and edit configuration files |

## Contents

- **[Installation](installation.md)** — Detailed Package Manager GUI setup,
  system requirements, self-upgrade, and configuration reset.
- **[Interface Overview](interface-overview.md)** — UI zones, drop-down menus,
  language switching, and configuration management.
- **[Workflow Tutorial](workflow-tutorial.md)** — Step-by-step walkthrough
  using CYP450 (1SUO) from pocket detection through co-evolution analysis.
- **[Cluster Methods](cluster-methods.md)** — Available clustering algorithms
  and how to choose between them.
- **[OpenKinetics](openkinetics.md)** — Using the OpenKinetics API for
  external scoring of mutants.
- **[Advanced Design Tools](advanced-design.md)** — Profile Design heatmap,
  ThermoMPNN stability prediction, and RFdiffusion backbone generation.
- **[Programmatic Mutagenesis](programmatic-mutagenesis.md)** — Generate mutant
  PDBs from Python for downstream MD, docking, and free energy calculations.

## Quick Reference

| I want to... | Go to |
|-------------|-------|
| Install REvoDesign for the first time | [Installation](installation.md) |
| Understand the UI layout | [Interface Overview](interface-overview.md) |
| Follow a complete design workflow | [Workflow Tutorial](workflow-tutorial.md) |
| Pick a clustering method | [Cluster Methods](cluster-methods.md) |
| Use the Profile Design heatmap | [Advanced Design Tools](advanced-design.md) |
| Predict stability with ThermoMPNN | [Advanced Design Tools](advanced-design.md) |
| Run RFdiffusion backbone design | [Advanced Design Tools](advanced-design.md) |
| Generate mutant PDBs for MD/docking | [Programmatic Mutagenesis](programmatic-mutagenesis.md) |
| Install Rosetta for energy scoring | [Rosetta Integration](../dev-guide/rosetta.md) |
| Set up the PSSM/GREMLIN server | [PSSM/GREMLIN Server](../dev-guide/server.md) |
