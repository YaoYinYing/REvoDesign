# Clusters

Mutant clustering and scoring system for grouping designed variants by sequence similarity.

## Module Overview

The clustering pipeline works in three stages:

1. **Combination Generation** (`combine_positions`): Generates all possible combinations of mutations from an input mutant table at a given combination size (N-mutant designs).
2. **Sequence Clustering** (`cluster_sequence`): Clusters the generated variant sequences using one of several algorithms (agglomerative, k-means, evolutionary, legacy).
3. **Scoring** (`score_clusters`): Optionally scores clustered representatives with Rosetta energy calculations.

## ClusterRunner

Main entry point for the clustering workflow. Reads all parameters from ConfigBus (method, batch size, number of clusters, substitution matrix, evolutionary weights, etc.) and orchestrates the full clustering pipeline for each mutation count in the specified range.

::: REvoDesign.clusters.cluster_runner.ClusterRunner
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Clustering Methods

### ClusterMethodAbstract

Abstract base class for clustering algorithms. Provides shared infrastructure for pairwise sequence alignment, distance matrix computation, centroid-based representative selection, and cluster output writing. Concrete subclasses implement specific clustering strategies.

::: REvoDesign.clusters.cluster_sequence.ClusterMethodAbstract
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### ClusterMethodManager

Dispatcher that instantiates the appropriate clustering algorithm by name. Auto-discovers `ClusterMethodAbstract` subclasses via the `PluginRegistry`.

::: REvoDesign.clusters.cluster_sequence.ClusterMethodManager
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### Available Methods

The following clustering methods are auto-discovered from `REvoDesign.clusters.methods`:

- **AgglomerativeCluster** — Hierarchical agglomerative clustering
- **EvoCluster** — Evolutionary-aware clustering using sequence, physico-chemical, spatial, PSSM, and ESM-1v distance components
- **KMeansCluster** — K-means clustering
- **LegacyCluster** — Original/legacy clustering implementation

::: REvoDesign.clusters.cluster_sequence.AgglomerativeCluster
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.clusters.cluster_sequence.EvoCluster
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.clusters.cluster_sequence.KMeansCluster
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.clusters.cluster_sequence.LegacyCluster
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### Data Classes

::: REvoDesign.clusters.cluster_sequence.ClusterInputSpec
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.clusters.cluster_sequence.ClusterMethodSpec
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Combination Generation

### Combinations

Generates all unique combinations of N mutations from an input mutation table, producing a FASTA file of variant sequences ready for clustering. Enforces uniqueness of positions within each combination and validates wild-type residues against the reference sequence.

::: REvoDesign.clusters.combine_positions.Combinations
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### GenerateVariantsinFastafile

::: REvoDesign.clusters.combine_positions.GenerateVariantsinFastafile
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Scoring

::: REvoDesign.clusters.score_clusters.score_clusters
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
