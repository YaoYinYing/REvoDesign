# REvoDesign

**A PyMOL plugin for enzyme redesign** — REvoDesign combines structural and
evolutionary information to help protein designers engineer enzymes with
greater confidence and less manual effort.

## Key Features

- **Surface Residue Analysis** — Identify solvent-accessible residues and
  design pockets around substrates and cofactors with customizable cutoffs.
- **Mutant Loading & Scoring** — Load designable mutants from PSSM-like CSV
  tables with configurable rejections and preferences.
- **Human Knowledge Supervision** — Visually inspect and curate mutants
  directly inside the PyMOL interface.
- **Sequence Clustering** — Reduce mutant set size for low-throughput
  wet-lab validation using one of several built-in clustering methods.
- **Co-Evolution Analysis** — Search for co-evolved residue pairs via the
  GREMLIN Markov random field profile.
- **Visualization** — Color structures by mutation scores, generate PyMOL
  sessions, and export results.
- **Multi-User Collaboration** — Share designs across a team with the socket
  broadcast system.

## Quick Start

```bash
conda create -n revodesign python=3.12 -y
conda activate revodesign
conda install -c conda-forge pymol-open-source pyqt=5 -y
```

Then launch PyMOL, open **Plugin > Plugin Manager > Install New Plugin**,
choose **Install from PyMOLWiki or any URL**, and paste the Package Manager URL:

```
https://gist.githubusercontent.com/YaoYinYing/c1e8bfe0fc0b9c60bf49ea04a550a044/raw/REvoDesign_PyMOL.py
```

Click **Fetch**, confirm, and use the REvoDesign Package Manager to install
the main program.

## Learn More

| Link | What you will find |
|---|---|
| [Getting Started](getting-started.md) | Prerequisites, install, first launch |
| [User Guide](user-guide/index.md) | Walkthroughs for each workflow stage |
| [API Reference](api/core.md) | Full API documentation |
| [GitHub Repository](https://github.com/YaoYinYing/REvoDesign) | Source code, issues, discussions |
