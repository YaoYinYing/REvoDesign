# Getting Started

## Prerequisites

- **Python 3.10 or later** (3.12 recommended)
- **conda** (Miniconda or Anaconda)
- **PyMOL** — install via conda-forge (`pymol-open-source`). Do **not** use
  the obsolete PyMOL bundle (< v2.5.7) from the official website; it ships
  Python 3.7 and is incompatible with REvoDesign.
- **macOS (Apple Silicon) users**: The `jaxlib` build with AVX instructions
  will not work under Rosetta 2. Use a native `pymol-open-source` build or
  build `jaxlib` from source.

## 1. Create a conda Environment

```bash
conda create -n revodesign python=3.12 -y
conda activate revodesign
conda install -c conda-forge pymol-open-source pyqt=5 -y
```

For PyQt6 testing, a separate environment with `pymol-open-source` (which
ships PyQt6) can be used instead.

## 2. Install REvoDesign

Install from PyPI:

```bash
pip install revodesign
```

Or, from a local clone:

```bash
pip install .
```

The `Makefile` in the project root also provides convenience targets:

```bash
make install           # pip install with extras
make install-no-dept   # pip install, no dependency resolution
make reinstall         # reinstall after code changes
```

Optional extras (rf diffusion, ESM2, etc.) are listed in `pyproject.toml`.

## 3. Install the PyMOL Plugin

1. Open PyMOL.
2. Navigate to **Plugin > Plugin Manager > Install New Plugin**.
3. Choose **Install from PyMOLWiki or any URL**.
4. Paste the REvoDesign Package Manager URL:
   ```
   https://gist.githubusercontent.com/YaoYinYing/c1e8bfe0fc0b9c60bf49ea04a550a044/raw/REvoDesign_PyMOL.py
   ```
5. Click **Fetch** and confirm the installation.
6. The REvoDesign Package Manager will appear in the PyMOL menu. Use it to
   install or update the core REvoDesign program.

## 4. First Launch

1. Fetch a structure (e.g. `fetch 1SUO`) in the PyMOL command line.
2. Click **Menu > REvoDesign > Import PyMOL Session** (keyboard shortcut:
   `Ctrl+N`) to let REvoDesign find a designable molecule.
3. The main UI panel opens. You are ready to design.

## 5. Configuration

REvoDesign stores its configuration in the platform-specific user data
directory (e.g. `~/Library/Application Support/REvoDesign/config/` on macOS).
On first run, a copy of the default configuration is created there.

Key files:

| File | Purpose |
|---|---|
| `environ.yaml` | Environment variables and secrets (API keys). **Never commit this file.** |
| `main.yaml` | All REvoDesign UI settings, workflow parameters, and Rosetta options. |
| `logger.yaml` | Logging verbosity and output destinations. |
| `runtime.yaml` | Runtime-specific settings. |

Example `environ.yaml` for an OpenKinetics API key:

```yaml
variables:
  OPENKINETICS_API_KEY: your-openkinetics-api-key
```

To apply changes to `main.yaml`, click **File > Reconfigure** in the REvoDesign
menu. Secrets in `environ.yaml` take effect after restarting PyMOL.

## 6. Basic Workflow

A typical REvoDesign session follows five stages:

1. **Prepare** — Load a structure, identify surface residues, define the
   binding pocket, and fetch a PSSM profile.
2. **Mutate** — Score and filter mutations from the profile. Apply
   constraints (score thresholds, residue preferences, rejection rules).
3. **Evaluate** — Review the mutant table, inspect variants in 3D, and
   optionally run external scorers (Rosetta ddG, OpenKinetics, etc.).
4. **Cluster** — Group similar mutants via sequence or evolution-aware
   clustering to select representatives for validation.
5. **Visualize** — Color the structure by mutation scores, generate PyMOL
   sessions, and export results.

Each stage has a dedicated tab in the REvoDesign UI. Detailed walkthroughs
are available in the [User Guide](user-guide/index.md).

## Next Steps

- Read the [User Guide](user-guide/index.md) for detailed workflow instructions.
- See the [API Reference](api/core.md) for module-level documentation.
- Browse the [demo cases](https://github.com/YaoYinYing/REvoDesignTutorial)
  for real-world examples.
