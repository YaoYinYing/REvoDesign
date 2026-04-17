# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""
Legacy cluster method entry.
"""

import warnings

import numpy as np

from REvoDesign.clusters.cluster_sequence import ClusterMethodAbstract, logging


class LegacyCluster(ClusterMethodAbstract):
    name = "LegacyCluster"

    def predict_labels(self, score_matrix: np.ndarray) -> np.ndarray:
        from sklearn.cluster import AgglomerativeClustering

        warnings.warn(
            "LegacyCluster uses Ward linkage for compatibility and may be methodologically limited for this input.",
            RuntimeWarning,
            stacklevel=2,
        )
        logging.warning("LegacyCluster is selected. Use AgglomerativeCluster or EvoCluster for new analyses.")
        return AgglomerativeClustering(n_clusters=self.num_clusters, linkage="ward").fit_predict(score_matrix)


__all__ = ["LegacyCluster"]
