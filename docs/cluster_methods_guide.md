# Cluster Methods Guide

This guide explains:

- Advantages and shortcomings of each clustering method
- How to pick the right method for your biological task
- How to implement and register your own cluster method

The implementation references the current clustering architecture:

- Abstract base: `REvoDesign.clusters.cluster_sequence.ClusterMethodAbstract`
- Discovery namespace: `REvoDesign.clusters.methods`
- Runtime selection: `ui.cluster.method.use`

## 1. Methods Overview

REvoDesign currently exposes four methods:

- `LegacyCluster`
- `AgglomerativeCluster`
- `KMeansCluster`
- `EvoCluster`

All methods share the same pipeline for:

- pairwise sequence alignment score matrix generation
- representative selection (nearest centroid by default)
- branch FASTA output + center FASTA output

If `ui.cluster.mutate_relax=true`, representative sequences can be overridden by Rosetta lowest-energy decoys after clustering.

## 2. Advantages and Shortcomings

### 2.1 `LegacyCluster` (Ward on raw score matrix; compatibility mode)

**Advantages**

- Backward-compatible with historical behavior.
- Useful when reproducing old analyses exactly.

**Shortcomings**

- Methodologically weak for this input type:
  - Ward linkage assumes Euclidean feature space.
  - Raw pairwise alignment similarity scores are not a Euclidean feature matrix.
- May create clusters that are mathematically less reliable.
- Emits runtime warning by design.

**When to use**

- Reproducing prior published/internal results that depended on legacy behavior.

### 2.2 `AgglomerativeCluster` (average linkage on precomputed distance)

**Advantages**

- Correctly converts score matrix to a non-negative symmetric distance matrix.
- Uses `linkage="average"` + `metric="precomputed"`, which matches distance input semantics.
- Deterministic and robust default for sequence-only clustering.

**Shortcomings**

- Uses only sequence alignment signal.
- Can still merge biologically unrelated mutants if sequence signal is noisy/insufficient.

**When to use**

- Recommended default for most projects.
- Best starting point when only sequence data is trusted/available.

### 2.3 `KMeansCluster` (centroid partitioning on score matrix rows)

**Advantages**

- Fast baseline.
- Simple partitioning behavior and easy to scale.

**Shortcomings**

- Uses Euclidean geometry over score-matrix row vectors, which may not align with biological distance assumptions.
- Sensitive to cluster shape assumptions.
- Often less biologically faithful than hierarchy-based distance clustering for this domain.

**When to use**

- Quick baseline or sanity comparison.
- Large datasets where speed is more important than cluster topology fidelity.

### 2.4 `EvoCluster` (multi-signal fused distance)

**Advantages**

- Fuses multiple biological signals:
  - sequence distance
  - amino acid physico-chemical category shift
  - structural spatial signal (mutated residue positions in 3D)
  - optional PSSM effect
  - optional ESM1v effect
- Supports missing-input fallback and weight renormalization.
- Better aligned to biology when sequence-only signal is noisy.

**Shortcomings**

- More configuration and data dependencies.
- Quality depends on input quality (structure, PSSM, ESM table).
- More difficult to interpret if many weighted components are active at once.

**When to use**

- You need biologically meaningful grouping beyond sequence-only similarity.
- You have reliable auxiliary data and want controlled multi-factor clustering.

## 3. How to Pick the Right Method

Use this practical decision flow.

### Step 1: Define your primary objective

- Reproduce old behavior exactly -> `LegacyCluster`
- General-purpose, mathematically sound sequence clustering -> `AgglomerativeCluster`
- Fast partitioning baseline -> `KMeansCluster`
- Biology-aware fused clustering -> `EvoCluster`

### Step 2: Check available inputs

- Only sequence alignments available -> `AgglomerativeCluster`
- Structure + profile/model scores available -> `EvoCluster`
- Very limited compute/time -> `KMeansCluster` (baseline)

### Step 3: Control complexity

- Start with `AgglomerativeCluster` as baseline.
- Move to `EvoCluster` only when you can justify each extra signal with a biological hypothesis.
- Keep weights simple first (for example, sequence + one extra component), then expand if needed.

### Step 4: Validate biological plausibility

- Inspect cluster branch FASTA files and representative variants.
- Compare outputs across methods for stability.
- If clusters are unstable or biologically mixed:
  - reduce `num_cluster` pressure
  - revise Evo weights
  - improve mutation effect inputs (PSSM/ESM/structure quality)

## 4. Core Config Keys

### Global method selection

- `ui.cluster.method.use`

Typical values:

- `AgglomerativeCluster` (default)
- `EvoCluster`
- `KMeansCluster`
- `LegacyCluster`

### Evo-specific inputs

- `ui.cluster.evo.inputs.pssm_profile`
- `ui.cluster.evo.inputs.esm1v_table`
- `ui.cluster.evo.inputs.structure_pdb`
- `ui.cluster.evo.esm.mutation_col`
- `ui.cluster.evo.weights.seq`
- `ui.cluster.evo.weights.physchem`
- `ui.cluster.evo.weights.spatial`
- `ui.cluster.evo.weights.pssm`
- `ui.cluster.evo.weights.esm`

## 5. Implement and Join Your Own Cluster Method

This section describes the minimum required implementation path.

### 5.1 Create a new method module

Add a new file under:

- `src/REvoDesign/clusters/methods/your_method.py`

### 5.2 Subclass the abstract base

Your class must inherit from `ClusterMethodAbstract` and define:

- unique class attribute `name`
- `predict_labels(self, score_matrix) -> np.ndarray`

Minimal template:

```python
import numpy as np

from REvoDesign.clusters.cluster_sequence import ClusterMethodAbstract


class YourCluster(ClusterMethodAbstract):
    name = "YourCluster"

    def predict_labels(self, score_matrix: np.ndarray) -> np.ndarray:
        # Convert scores to distance when your algorithm expects distances.
        distance_matrix = self.build_distance_matrix_from_scores(score_matrix)

        # Return one label per sequence.
        # Replace this with your own algorithm.
        from sklearn.cluster import AgglomerativeClustering

        return AgglomerativeClustering(
            n_clusters=self.num_clusters,
            linkage="average",
            metric="precomputed",
        ).fit_predict(distance_matrix)
```

### 5.3 Registration behavior

No manual class list editing is required.

`PluginRegistry` auto-discovers subclasses in `REvoDesign.clusters.methods` at import time.

Requirements:

- Class is importable from the new module
- Class has a non-empty unique `name`
- Class is not abstract

If duplicate names are found, startup/import fails fast with conflict details.

### 5.4 Select your method in config

Set:

- `ui.cluster.method.use: YourCluster`

### 5.5 If your method needs extra runtime inputs

The cluster runner currently passes common attributes and Evo inputs.

If your method needs additional method-specific parameters:

- Add new config keys under `ui.cluster` (or a method-specific subtree)
- Extend `ClusterRunner` to read and inject those parameters into the method instance before `run_clustering`.

### 5.6 Recommended tests for new methods

At minimum:

- Factory/registry selection test
- Runnable clustering test on tiny FASTA fixture
- Determinism/reproducibility test
- Missing-input fallback test (if method uses optional inputs)
- Compatibility output test:
  - `cluster_centers_nearest_centroid.fasta`
  - `cluster_centers_stochastic.fasta`

## 6. Practical Recommendations

- Use `AgglomerativeCluster` as your default baseline.
- Use `EvoCluster` for biology-first projects with trusted auxiliary inputs.
- Treat `LegacyCluster` as compatibility mode, not as new-analysis default.
- Keep representative policy transparent:
  - nearest-centroid by default
  - Rosetta override only when mutate-relax scoring is enabled and available.
