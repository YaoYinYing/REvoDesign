# Cluster Methods Guide

This guide explains the clustering methods available in REvoDesign, how to
choose the right one for your biological task, and how to add your own
method.

All methods share the same pipeline:

- Pairwise sequence alignment score matrix generation
- Representative selection (nearest centroid by default)
- Branch FASTA output and center FASTA output

When `ui.cluster.mutate_relax` is `true`, representative sequences can be
overridden by Rosetta lowest-energy decoys after clustering.

## Built-in Methods

### AgglomerativeCluster (default)

Average-linkage agglomerative clustering on a precomputed distance matrix.

**Advantages**

- Correctly converts the score matrix to a non-negative symmetric distance
  matrix.
- Uses `linkage="average"` and `metric="precomputed"`, matching distance
  input semantics.
- Deterministic and robust for sequence-only clustering.

**Shortcomings**

- Uses only sequence alignment signal.
- May merge biologically unrelated mutants if the sequence signal is noisy.

**When to use**

- Recommended default for most projects.
- Best starting point when only sequence data is available.

---

### EvoCluster

Multi-signal fused distance clustering that combines several biological
signals.

**Advantages**

- Fuses multiple signals: sequence distance, amino acid physico-chemical
  category shift, structural spatial signal (mutated residue positions in
  3D), optional PSSM effect, and optional ESM1v effect.
- Supports missing-input fallback and weight renormalization.
- Produces biologically meaningful groupings when sequence-only signal is
  insufficient.

**Shortcomings**

- More configuration and data dependencies.
- Quality depends on input quality (structure, PSSM, ESM table).
- Harder to interpret when many weighted components are active at once.

**When to use**

- You need biologically informed grouping beyond sequence similarity.
- You have reliable auxiliary data (structure, profiles) and want controlled
  multi-factor clustering.

---

### KMeansCluster

Centroid partitioning on score matrix rows.

**Advantages**

- Fast baseline with simple partitioning behavior.
- Scales easily to large datasets.

**Shortcomings**

- Uses Euclidean geometry over score-matrix row vectors, which may not align
  with biological distance assumptions.
- Sensitive to cluster shape assumptions.
- Often less biologically faithful than hierarchy-based distance clustering
  for this domain.

**When to use**

- Quick baseline or sanity comparison.
- Large datasets where speed matters more than cluster topology fidelity.

---

### LegacyCluster

Ward linkage on the raw score matrix, retained for backward compatibility.

**Advantages**

- Backward-compatible with historical behavior.
- Useful when reproducing old analyses exactly.

**Shortcomings**

- Ward linkage assumes a Euclidean feature space, but raw pairwise alignment
  similarity scores are not a Euclidean feature matrix.
- May create clusters that are mathematically less reliable.
- Emits a runtime warning by design.

**When to use**

- Reproducing prior results that depended on legacy behavior.

## How to Pick the Right Method

### Step 1: Define your primary objective

| Goal | Method |
|---|---|
| Reproduce old behavior exactly | `LegacyCluster` |
| General-purpose, sound sequence clustering | `AgglomerativeCluster` |
| Fast partitioning baseline | `KMeansCluster` |
| Biology-aware fused clustering | `EvoCluster` |

### Step 2: Check available inputs

- **Only sequence alignments** — `AgglomerativeCluster`
- **Structure + profile/model scores** — `EvoCluster`
- **Very limited compute/time** — `KMeansCluster` (baseline)

### Step 3: Control complexity

- Start with `AgglomerativeCluster` as your baseline.
- Move to `EvoCluster` only when you can justify each extra signal with a
  biological hypothesis.
- Keep weights simple first (e.g. sequence plus one extra component), then
  expand if needed.

### Step 4: Validate biological plausibility

- Inspect cluster branch FASTA files and representative variants.
- Compare outputs across methods for stability.
- If clusters are unstable or biologically mixed, reduce `num_cluster`
  pressure, revise Evo weights, or improve mutation effect inputs
  (PSSM/ESM/structure quality).

## Configuration

### Global method selection

Set `ui.cluster.method.use` to one of:

- `AgglomerativeCluster` (default)
- `EvoCluster`
- `KMeansCluster`
- `LegacyCluster`

### EvoCluster-specific inputs

| Config key | Purpose |
|---|---|
| `ui.cluster.evo.inputs.pssm_profile` | PSSM profile file |
| `ui.cluster.evo.inputs.esm1v_table` | ESM1v score table |
| `ui.cluster.evo.inputs.structure_pdb` | Structure PDB file |
| `ui.cluster.evo.esm.mutation_col` | Column name for mutations in ESM table |
| `ui.cluster.evo.weights.seq` | Sequence distance weight |
| `ui.cluster.evo.weights.physchem` | Physico-chemical shift weight |
| `ui.cluster.evo.weights.spatial` | Spatial distance weight |
| `ui.cluster.evo.weights.pssm` | PSSM effect weight |
| `ui.cluster.evo.weights.esm` | ESM1v effect weight |

### General cluster settings

| Config key | Purpose |
|---|---|
| `ui.cluster.num_cluster` | Target number of clusters |
| `ui.cluster.mut_num_min` | Minimum mutation count per variant |
| `ui.cluster.mut_num_max` | Maximum mutation count per variant |
| `ui.cluster.score_matrix.default` | Alignment score matrix (default: PAM30) |
| `ui.cluster.batch_size` | Batch size for alignment computation |
| `ui.cluster.random_seed` | Random seed for shuffling |
| `ui.cluster.shuffle` | Shuffle input before clustering |
| `ui.cluster.mutate_relax` | Enable Rosetta relax for representative override |

## Implementing a Custom Cluster Method

1. Create a new file at
   `src/REvoDesign/clusters/methods/your_method.py`.

2. Subclass `ClusterMethodAbstract` from
   `REvoDesign.clusters.cluster_sequence`.

   Your class must define:
   - A unique class attribute `name`
   - A `predict_labels(self, score_matrix) -> np.ndarray` method

   Minimal template:

   ```python
   import numpy as np
   from REvoDesign.clusters.cluster_sequence import ClusterMethodAbstract

   class YourCluster(ClusterMethodAbstract):
       name = "YourCluster"

       def predict_labels(self, score_matrix: np.ndarray) -> np.ndarray:
           distance_matrix = self.build_distance_matrix_from_scores(score_matrix)
           # Replace with your own algorithm
           from sklearn.cluster import AgglomerativeClustering
           return AgglomerativeClustering(
               n_clusters=self.num_clusters,
               linkage="average",
               metric="precomputed",
           ).fit_predict(distance_matrix)
   ```

3. **No manual registration needed.** `PluginRegistry` auto-discovers
   subclasses in `REvoDesign.clusters.methods` at import time. Your class
   must be importable, have a non-empty unique `name`, and not be abstract.
   Duplicate names cause a fast failure on startup with conflict details.

4. Set `ui.cluster.method.use: YourCluster` in the configuration.

5. If your method needs additional runtime inputs, add new config keys under
   `ui.cluster` and extend `ClusterRunner` to inject them into the method
   instance before `run_clustering`.

## Practical Recommendations

- Use `AgglomerativeCluster` as your default baseline.
- Use `EvoCluster` for biology-first projects with trusted auxiliary inputs.
- Treat `LegacyCluster` as compatibility mode, not a new-analysis default.
- Keep representative policy transparent: nearest-centroid by default,
  Rosetta override only when `mutate_relax` scoring is enabled.
