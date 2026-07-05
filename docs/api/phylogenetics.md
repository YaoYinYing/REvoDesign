# Phylogenetics / Co-Evolution

The phylogenetics module provides tools for evolutionary coupling analysis
using GREMLIN (Generative REgularized ModeLs of proteINs), co-evolved residue
pair discovery, and mutation design driven by co-evolutionary signals.

## Module Layout

```
REvoDesign/phylogenetics/
    __init__.py              # Exports: GremlinAnalyser, MutateWorker, VisualizingWorker
    gremlin_tools.py         # CoevolvedPair, GREMLIN_Tools
    gremlin_pytorch.py       # GremlinTorch (PyTorch), GREMLIN(), CustomAdamOpt, get_mtx()
    evo_mutator.py           # GremlinAnalyser, MutateWorker, VisualizingWorker, ChainBinder
    revo_designer.py         # REvoDesigner — iterative mutation design engine
```

## Core Classes

### GremlinAnalyser

The central high-level orchestrator for co-evolutionary analysis within the
REvoDesign UI. It manages the full workflow:

1. **Loading** -- Loads a GREMLIN MRF (Markov Random Field) pickle file and
   initializes a `GREMLIN_Tools` instance.
2. **Pair discovery** -- Runs all-vs-all or one-vs-all co-evolved pair
   analysis, depending on whether the user has a PyMOL selection active.
3. **Chain binding** -- Calculates CA-CA distances for each co-evolved pair
   via `ChainBinder`, optionally in inter-chain (homooligomeric) mode.
4. **Visualization** -- Renders co-evolved pairs as colored stick bonds in
   PyMOL using `cmd.pseudoatom` for lightweight pseudo-atom creation (avoids
   the overhead of `cmd.create()`).
5. **Navigation** -- Provides previous/next pair navigation with a
   `QButtonMatrixGremlin` widget for interactive mutation.
6. **Mutation** -- When the user clicks a cell in the co-evolution matrix, a
   `Mutant` object is constructed, scored (via the active `Magician` scorer or
   raw matrix value), and visualized as a mutagenesis object.
7. **Decision** -- Accepted mutants are stored in `mutant_tree_coevolved` and
   saved to the mutants text file.

::: REvoDesign.phylogenetics.evo_mutator.GremlinAnalyser
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### GREMLIN_Tools

Provides all GREMLIN analysis functions **except** the PyTorch model itself.
It loads an MRF, computes contact scores (raw, APC-corrected, z-score
normalized), identifies top co-evolving pairs, plots W matrices for individual
pairs, and returns `CoevolvedPair` dataclasses.

::: REvoDesign.phylogenetics.gremlin_tools.GREMLIN_Tools
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### CoevolvedPair

A dataclass representing a single co-evolved residue pair identified by
GREMLIN. Tracks zero-indexed positions, wild-type amino acids, z-scores,
per-chain-pair distances (for homooligomeric analysis), and output
file paths (PNG, CSV). Provides convenience properties for residue
selections and PyMOL selection strings.

::: REvoDesign.phylogenetics.gremlin_tools.CoevolvedPair
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### CoevolvedPairState

Maps visual states of co-evolved pairs to colors:

| State | Color | Meaning |
|-------|-------|---------|
| `available` | `marine` | Within distance cutoff, available for interaction |
| `out_of_range` | `salmon` | Beyond distance cutoff, excluded |
| `in_design` | `tv_yellow` | Currently being inspected/designed |

::: REvoDesign.phylogenetics.evo_mutator.CoevolvedPairState
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### ChainBinder

Calculates CA-CA distances between residue pairs, supporting both intra-chain
and inter-chain (homooligomeric) modes. Uses Biopython's PDB parser for
distance calculation and `joblib.Parallel` for speed.

::: REvoDesign.phylogenetics.evo_mutator.ChainBinder
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### MutateWorker

Handles profile-driven mutation design within the "Mutate" tab of the UI.
Loads a design profile (custom or Magician-based), configures the
`REvoDesigner`, and runs the mutation pipeline.

::: REvoDesign.phylogenetics.evo_mutator.MutateWorker
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### VisualizingWorker

Handles the visualization tab: loads a mutant table CSV, scores mutations
against a design profile, and creates a color-coded PyMOL session.

::: REvoDesign.phylogenetics.evo_mutator.VisualizingWorker
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## GremlinTorch (PyTorch Model)

The `gremlin_pytorch.py` module provides a pure-PyTorch reimplementation of
the original TensorFlow-based GREMLIN model. Key components:

### GremlinTorch

The PyTorch `nn.Module` implementing the GREMLIN pairwise undirected
graphical model. It learns one-body potentials (`V`) and two-body coupling
potentials (`W`) from a multiple sequence alignment (MSA).

### CustomAdamOpt

Replicates the original TensorFlow `opt_adam` behavior:
- Single-scalar `vt` for gradient variance (sum of squared gradients)
- Per-parameter `mt` for momentum
- Optional bias-correction via `b_fix` parameter

### GREMLIN() Function

The main training entry point:

```python
from REvoDesign.phylogenetics.gremlin_pytorch import GREMLIN, mk_msa

msa = mk_msa(sequence_strings)
mrf = GREMLIN(msa, opt_type="adam", opt_iter=100, device="cpu")
```

Returns an MRF dict compatible with `GREMLIN_Tools.load_mrf()`:
- `mrf["v"]` -- One-body parameters `(ncol, states)`
- `mrf["w"]` -- Two-body parameters `(#pairs, states, states)`
- `mrf["v_idx"]` -- Column index mapping for V
- `mrf["w_idx"]` -- Pair index mapping for W

### MSA Preparation

- `parse_fasta()` -- Reads FASTA files into numpy arrays
- `filt_gaps()` -- Removes columns exceeding a gap fraction threshold
- `get_eff()` -- Computes per-sequence weights from pairwise identity
- `mk_msa()` -- Full MSA processing pipeline returning a dict with aligned
  sequences, weights, effective sequence count (Neff), and index mappings

### Contact Map Utilities

- `normalize()` -- Box-Cox + z-score normalization
- `get_mtx()` -- Extracts contact scores from the MRF (raw, APC, z-score).
  Note: there are two implementations — a module-level function in
  `gremlin_pytorch.py` and an instance method `GREMLIN_Tools.get_mtx()` in
  `gremlin_tools.py`.
- `plot_mtx()` -- Quick Matplotlib visualization of the contact map

## Workflow Summary

```
MSA (FASTA)
    |
    v
mk_msa()                    # Prepare alignment, assign weights
    |
    v
GREMLIN()                   # Train model, produce MRF
    |
    v
GREMLIN_Tools               # Load MRF, compute scores, rank pairs
    |-- get_mtx()           # Contact scores (raw, APC, z-score)
    |-- get_to_coevolving_pairs()  # Build DataFrame
    |-- plot_w()            # Visualize W matrix for a pair
    |-- plot_w_a2a()        # All-vs-all pairs
    |-- plot_w_o2a()        # One-vs-all pairs
    |
    v
ChainBinder.bind_chains()   # Calculate CA-CA distances
    |
    v
GremlinAnalyser             # UI interaction, navigation, mutation
    |-- plot_coevolved_pair_in_pymol()  # Render as sticks
    |-- load_co_evolving_pairs()        # Navigate pairs (contains nested
    |                                   #   mutate_with_gridbuttons helper)
    |-- coevoled_mutant_decision()      # Accept/reject mutant
```
