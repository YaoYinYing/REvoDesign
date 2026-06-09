# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""
KMeans cluster method entry.
"""

import numpy as np

from REvoDesign.clusters.cluster_sequence import ClusterMethodAbstract, ClusterMethodSpec


class KMeansCluster(ClusterMethodAbstract):
    name = "KMeansCluster"
    spec = ClusterMethodSpec(
        name=name,
        display_name="KMeansCluster",
        description="K-means clustering on score-profile feature vectors instead of a precomputed distance matrix.",
        representative_policy="Nearest centroid among clustered variants in score-profile space.",
    )

    def predict_labels(self, score_matrix: np.ndarray) -> np.ndarray:
        from sklearn.cluster import KMeans

        return KMeans(n_clusters=self.num_clusters, n_init="auto", random_state=0).fit_predict(score_matrix)


__all__ = ["KMeansCluster"]
