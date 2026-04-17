# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Cluster sequence methods and strategy registry."""

from __future__ import annotations

import decimal
import itertools
import os
import pathlib
import random
import time
from abc import ABC, abstractmethod

import matplotlib
import numpy as np
import pandas as pd
from Bio import SeqIO
from Bio.Align import PairwiseAligner, substitution_matrices
from Bio.SeqRecord import SeqRecord
from matplotlib import pyplot as plt

from REvoDesign.basic import build_plugin_registry
from REvoDesign.citations import CitableModuleAbstract
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.tools.customized_widgets import refresh_window
from REvoDesign.tools.utils import minibatches_generator

logging = ROOT_LOGGER.getChild(__name__)

matplotlib.use("Agg")


class ClusterMethodAbstract(CitableModuleAbstract, ABC):
    name: str = ""
    installed: bool = True

    def __init__(self, fastafile: str):
        self.fastafile = fastafile

        self.gap_open = -10
        self.gap_extend = -0.5
        self.substitution_matrix = "PAM30"

        self._save_dir = "./cluster"
        self.num_proc = 4
        self.batch_size = 100
        self.num_clusters = 15
        self.shuffle_variant = False
        self.debug = False
        self.resume = False
        self.overwrite = False

        self.seqs = {}
        self.seqs_list = []
        self.scores = [[]]
        self.records: list[SeqRecord] | None = None
        self.records_seqs = []
        self._current_centers: dict[int, SeqRecord] = {}
        self.cluster_output_fp = {}

        self.chain_id = "A"
        self.wt_sequence = ""
        self.structure_pdb = ""
        self.evo_pssm_profile = ""
        self.evo_esm1v_table = ""
        self.evo_esm_mutation_col = "mutation"
        self.evo_weights = {
            "seq": 1.0,
            "physchem": 0.0,
            "spatial": 0.0,
            "pssm": 0.0,
            "esm": 0.0,
        }

    def initialize_aligner(self):
        self.aligner = PairwiseAligner(
            mode="global",
            substitution_matrix=substitution_matrices.load(self.substitution_matrix),
            open_gap_score=self.gap_open,
            extend_gap_score=self.gap_extend,
        )

    def global_alignment(self, seqs, indexes):
        (i, j) = indexes
        (seqA, seqB) = seqs

        r = self.aligner.align(seqA, seqB)

        return (
            "".join(str(r.sequences[0]).split("-")),
            "".join(str(r.sequences[1]).split("-")),
            r.score,
            r[0].aligned[0][0][0],
            r[0].aligned[0][0][1],
            i,
            j,
        )

    def write_fasta_to_file(self, tmpfastafile):
        with open(tmpfastafile, "w") as f:
            for line in self.seqs:
                f.write(">" + line + "\n")
                f.write(str(self.seqs[line]) + "\n")

    def plot_score_mtx(self, mtx, vmin=1, vmax=3):
        plt.figure(figsize=(5, 5))
        plt.imshow(mtx, cmap="Blues", interpolation="none", vmin=vmin, vmax=vmax)
        plt.grid(False)
        img_fp = f"{self.save_dir}/Cluster_score_mtx.png"

        plt.savefig(img_fp)
        self.cluster_output_fp["score"] = img_fp
        plt.close()

    @staticmethod
    def handle_calculation_result(results):
        logging.debug(f"Recieving results in length: {len(results)}")
        return results

    @staticmethod
    def build_distance_matrix_from_scores(score_matrix: np.ndarray) -> np.ndarray:
        score_matrix = np.asarray(score_matrix, dtype=float)
        diagonal_scores = np.diag(score_matrix)
        distance_matrix = ((diagonal_scores[:, None] + diagonal_scores[None, :]) / 2.0) - score_matrix
        distance_matrix = np.maximum(distance_matrix, 0.0)
        distance_matrix = (distance_matrix + distance_matrix.T) / 2.0
        np.fill_diagonal(distance_matrix, 0.0)
        return distance_matrix

    @staticmethod
    def normalize_distance_matrix(distance_matrix: np.ndarray) -> np.ndarray:
        distance_matrix = np.asarray(distance_matrix, dtype=float)
        distance_matrix = (distance_matrix + distance_matrix.T) / 2.0
        np.fill_diagonal(distance_matrix, 0.0)
        max_dist = float(np.max(distance_matrix))
        if max_dist > 0:
            distance_matrix = distance_matrix / max_dist
        return distance_matrix

    @staticmethod
    def select_representative_indices(score_matrix, labels, centroid_model):
        score_matrix = np.asarray(score_matrix, dtype=float)
        labels = np.asarray(labels)
        class_to_centroid = {int(label): idx for idx, label in enumerate(centroid_model.classes_)}
        representative_indices = {}
        for cluster_id in np.unique(labels):
            candidate_indices = np.where(labels == cluster_id)[0]
            centroid_vector = centroid_model.centroids_[class_to_centroid[int(cluster_id)]]
            distances = np.linalg.norm(score_matrix[candidate_indices] - centroid_vector, axis=1)
            representative_indices[int(cluster_id)] = int(candidate_indices[np.argmin(distances)])
        return representative_indices

    def _center_output_paths(self):
        return (
            f"{self.save_dir}/cluster_centers_nearest_centroid.fasta",
            f"{self.save_dir}/cluster_centers_stochastic.fasta",
        )

    def write_cluster_center_files(self, centers_by_cluster):
        primary_fp, compat_fp = self._center_output_paths()
        for output_fp in (primary_fp, compat_fp):
            with open(output_fp, "w") as f:
                for cluster_id in range(self.num_clusters):
                    if cluster_id not in centers_by_cluster:
                        raise ValueError(f"Cluster {cluster_id} has no representative sequence.")
                    record = centers_by_cluster[cluster_id]
                    f.write(">" + record.name + "_cluster_" + str(cluster_id) + "\n")
                    f.write(str(record.seq) + "\n")
        self.cluster_output_fp["cluster_centers"] = primary_fp
        self._current_centers = dict(centers_by_cluster)

    @staticmethod
    def _match_record_by_decoy(records, decoy_name):
        if not decoy_name:
            return None
        for record in records:
            if record.id == decoy_name or record.name == decoy_name or decoy_name in record.name:
                return record
        return None

    def override_cluster_centers_with_rosetta(self, rosetta_results):
        rosetta_centers = {}
        for cluster_id in range(self.num_clusters):
            branch_fp = f"{self.save_dir}/c.{cluster_id}.fasta"
            branch_records = list(SeqIO.parse(branch_fp, "fasta"))
            if not branch_records:
                continue

            selected_record = None
            if cluster_id < len(rosetta_results):
                best_decoy = getattr(rosetta_results[cluster_id], "best_decoy", {}) or {}
                selected_record = self._match_record_by_decoy(branch_records, best_decoy.get("decoy", ""))

            if selected_record is None:
                selected_record = self._current_centers.get(cluster_id, branch_records[0])

            rosetta_centers[cluster_id] = selected_record

        if rosetta_centers:
            self.write_cluster_center_files(rosetta_centers)

    def _calculate_pairwise_scores(self, progressbar) -> np.ndarray:
        from REvoDesign.tools.customized_widgets import QtParallelExecutor

        handle = open(self.fastafile)
        self.records = list(SeqIO.parse(handle, "fasta"))
        if self.shuffle_variant:
            self.records = random.sample(self.records, len(self.records))

        nm_seqs = len(self.records)
        self.records_seqs = [r.seq for r in self.records]
        self.scores = [[0 for _ in range(nm_seqs)] for _ in range(nm_seqs)]

        seq_num = list(range(nm_seqs))
        paramlist = itertools.combinations_with_replacement(self.records_seqs, 2)
        indexlist = itertools.combinations_with_replacement(seq_num, 2)

        logging.info(f"Number of cpus used: {self.num_proc}")
        self.buffer_file = f"{self.save_dir}/buffer.csv"

        workload = int((len(seq_num) + 1) * len(seq_num) / 2)

        def processing(paramlist, indexlist, batch_size, mode="w"):
            logging.info(f"Job Number: {workload}")
            logging.info(f"Size of minibatch used: {batch_size}")
            batch_number = workload // batch_size if batch_size < workload else 1

            with open(self.buffer_file, mode) as bw:
                columns = ["S1", "S2", "Score", "Start", "End", "i", "j"]
                if mode == "w":
                    bw.write(",".join(columns))
                    bw.write("\n")

                progressbar.setRange(0, batch_number)

                for batch_count, (sub_indexlist, sub_paramlist) in enumerate(
                    zip(
                        minibatches_generator(indexlist, batch_size),
                        minibatches_generator(paramlist, batch_size),
                    ),
                    start=1,
                ):
                    start_time = time.perf_counter()
                    args_list = [(sub_param, sub_index) for sub_param, sub_index in zip(sub_paramlist, sub_indexlist)]

                    parallel_executor = QtParallelExecutor(self.global_alignment, args_list, self.num_proc - 1)
                    parallel_executor.result_signal.connect(self.handle_calculation_result)
                    parallel_executor.start()
                    logging.debug("Starting parallel execution...")

                    while not parallel_executor.isFinished():
                        refresh_window()
                        time.sleep(0.01)

                    progressbar.setValue(batch_count)
                    refresh_window()

                    sub_res = parallel_executor.handle_result()
                    end_time = time.perf_counter()
                    refresh_window()

                    logging.info(
                        f"Cluster progress: {decimal.Decimal(batch_count / batch_number) * 100:{5}.{4}} %  "
                        f"\t{batch_count} / {batch_number}\t elapse time: {end_time - start_time}"
                    )
                    res_b = [",".join([str(x) for x in list(item)]) for item in sub_res]
                    bw.write("\n".join(res_b))
                    bw.write("\n")

                progressbar.setValue(workload)

        logging.info("Calculating...")
        processing(paramlist, indexlist, self.batch_size, "w")

        logging.info("reading buffer ...")
        df = pd.read_csv(self.buffer_file)
        for i, j, _score in zip(df.i, df.j, df.Score):
            self.scores[i][j] = float(_score)
            self.scores[j][i] = float(_score)

        return np.asarray(self.scores, dtype=float)

    @abstractmethod
    def predict_labels(self, score_matrix: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def set_and_write_clusters(self, progressbar):
        from joblib import parallel_backend
        from sklearn.neighbors import NearestCentroid

        score_matrix = self._calculate_pairwise_scores(progressbar)

        with parallel_backend("threading", n_jobs=self.num_proc):
            logging.info("Clustering in progress ...")
            labels = np.asarray(self.predict_labels(score_matrix), dtype=int)
            logging.info("Clustering is done.")
            clf = NearestCentroid()
            clf.fit(score_matrix, labels)

        target_counts = pd.Series(labels).value_counts()
        target_counts.plot.barh()
        plt.title("Cluster Counts")
        plt.xlabel("Count")
        plt.ylabel("Cluster")
        img_fp = f"{self.save_dir}/variants_per_clusters.png"
        plt.savefig(img_fp)
        plt.close()
        self.cluster_output_fp["variant"] = img_fp

        nm_seqs = len(self.records)
        cluster = [[] for _ in range(self.num_clusters)]
        for i in range(0, nm_seqs):
            cluster[labels[i]].append(self.records[i])

        representative_indices = self.select_representative_indices(score_matrix, labels, clf)
        deterministic_centers = {}
        for cluster_id in range(self.num_clusters):
            if cluster_id not in representative_indices:
                raise ValueError(f"Cluster {cluster_id} has no assigned members.")
            deterministic_centers[cluster_id] = self.records[representative_indices[cluster_id]]
        self.write_cluster_center_files(deterministic_centers)

        self.cluster_output_fp["branches"] = []
        for i, item in enumerate(cluster):
            sub_cluster_branches = f"{self.save_dir}/c.{str(i)}.fasta"
            with open(sub_cluster_branches, "w") as output_handle:
                SeqIO.write(item, output_handle, "fasta")
            self.cluster_output_fp["branches"].append(sub_cluster_branches)

        df_score = pd.DataFrame(self.scores)
        df_flat = pd.read_csv(self.buffer_file)
        self.plot_score_mtx(
            df_score,
            vmin=min(df_flat["Score"].to_list()),
            vmax=max(df_flat["Score"].tolist()),
        )

    def run_clustering(self, progressbar):
        fastafile = pathlib.Path(self.fastafile).resolve()
        self.fasta_instance = fastafile.stem
        self.save_dir = pathlib.Path(self._save_dir).resolve().joinpath(self.fasta_instance)

        os.makedirs(self.save_dir, exist_ok=True)

        self._batch_size = self.batch_size
        self.batch_size = self._batch_size // self.num_proc * self.num_proc
        logging.info(f"fix batch_size {self._batch_size} to {self.batch_size}")
        self.set_and_write_clusters(progressbar)


from REvoDesign.clusters.methods.agglomerative import AgglomerativeCluster
from REvoDesign.clusters.methods.evo import EvoCluster
from REvoDesign.clusters.methods.kmeans import KMeansCluster
from REvoDesign.clusters.methods.legacy import LegacyCluster


CLUSTER_METHOD_REGISTRY = build_plugin_registry(
    base_class=ClusterMethodAbstract,
    package="REvoDesign.clusters.methods",
)
ALL_CLUSTER_METHOD_CLASSES: list[type[ClusterMethodAbstract]] = list(CLUSTER_METHOD_REGISTRY.all_classes)
IMPLEMENTED_CLUSTER_METHOD = CLUSTER_METHOD_REGISTRY.implemented_map


class ClusterMethodManager:
    @staticmethod
    def get(cluster_method_name: str, **kwargs) -> ClusterMethodAbstract:
        return CLUSTER_METHOD_REGISTRY.get(cluster_method_name, **kwargs)


Clustering = AgglomerativeCluster

__all__ = [
    "ClusterMethodAbstract",
    "LegacyCluster",
    "AgglomerativeCluster",
    "KMeansCluster",
    "EvoCluster",
    "ClusterMethodManager",
    "ALL_CLUSTER_METHOD_CLASSES",
    "IMPLEMENTED_CLUSTER_METHOD",
    "Clustering",
]
