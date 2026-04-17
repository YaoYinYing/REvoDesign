# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""
Agglomerative cluster method entry.
"""

import numpy as np

from REvoDesign.clusters.cluster_sequence import ClusterMethodAbstract


class AgglomerativeCluster(ClusterMethodAbstract):
    name = "AgglomerativeCluster"

    def predict_labels(self, score_matrix: np.ndarray) -> np.ndarray:
        from sklearn.cluster import AgglomerativeClustering

        distance_matrix = self.build_distance_matrix_from_scores(score_matrix)
        return AgglomerativeClustering(
            n_clusters=self.num_clusters,
            linkage="average",
            metric="precomputed",
        ).fit_predict(distance_matrix)


__all__ = ["AgglomerativeCluster"]
