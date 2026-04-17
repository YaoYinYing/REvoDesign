# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

import pathlib

import numpy as np
import pandas as pd
import pytest

from REvoDesign.clusters.cluster_sequence import (
    AgglomerativeCluster,
    ClusterMethodManager,
    EvoCluster,
    KMeansCluster,
    LegacyCluster,
)


class _DummySignal:
    def connect(self, _callback):
        return None


class _FakeQtParallelExecutor:
    def __init__(self, func, args, _n_jobs):
        self.func = func
        self.args = args
        self.result_signal = _DummySignal()
        self._results = []
        self._finished = False

    def start(self):
        self._results = [self.func(*arg_pair) for arg_pair in self.args]
        self._finished = True

    def isFinished(self):
        return self._finished

    def handle_result(self):
        return self._results


class _DummyProgressbar:
    def setRange(self, _min_value, _max_value):
        return None

    def setValue(self, _value):
        return None


def _write_tiny_fasta(path: pathlib.Path):
    path.write_text(
        (
            ">seq_0\nAAAAAA\n"
            ">seq_1\nAAAATA\n"
            ">seq_2\nTTTTTT\n"
            ">seq_3\nTTTTTA\n"
        ),
        encoding="utf-8",
    )


def _run_cluster(cluster_cls, monkeypatch, tmp_path, run_name):
    import REvoDesign.tools.customized_widgets as customized_widgets

    monkeypatch.setattr(customized_widgets, "QtParallelExecutor", _FakeQtParallelExecutor)

    input_fasta = tmp_path / f"{run_name}.fasta"
    _write_tiny_fasta(input_fasta)

    cluster = cluster_cls(str(input_fasta))
    cluster._save_dir = str(tmp_path / f"output_{run_name}")
    cluster.num_clusters = 2
    cluster.num_proc = 2
    cluster.batch_size = 10
    cluster.initialize_aligner()
    cluster.run_clustering(_DummyProgressbar())

    return cluster


def test_cluster_factory_selection():
    assert isinstance(ClusterMethodManager.get("LegacyCluster", fastafile="a"), LegacyCluster)
    assert isinstance(ClusterMethodManager.get("AgglomerativeCluster", fastafile="a"), AgglomerativeCluster)
    assert isinstance(ClusterMethodManager.get("KMeansCluster", fastafile="a"), KMeansCluster)
    assert isinstance(ClusterMethodManager.get("EvoCluster", fastafile="a"), EvoCluster)


def test_legacy_cluster_warns(monkeypatch, tmp_path):
    with pytest.warns(RuntimeWarning, match="LegacyCluster"):
        _run_cluster(LegacyCluster, monkeypatch, tmp_path, "legacy")


def test_kmeans_cluster_runs(monkeypatch, tmp_path):
    cluster = _run_cluster(KMeansCluster, monkeypatch, tmp_path, "kmeans")
    centers_fp = pathlib.Path(cluster.cluster_output_fp["cluster_centers"])
    assert centers_fp.exists()
    assert (centers_fp.parent / "cluster_centers_stochastic.fasta").exists()


def test_agglomerative_cluster_runs(monkeypatch, tmp_path):
    cluster = _run_cluster(AgglomerativeCluster, monkeypatch, tmp_path, "agglo")
    centers_fp = pathlib.Path(cluster.cluster_output_fp["cluster_centers"])
    assert centers_fp.exists()
    assert (centers_fp.parent / "cluster_centers_stochastic.fasta").exists()


def test_evo_distance_fallback_to_sequence_when_optional_missing(monkeypatch, tmp_path):
    cluster = EvoCluster(str(tmp_path / "dummy.fasta"))
    cluster.evo_weights = {
        "seq": 0.0,
        "physchem": 0.0,
        "spatial": 0.0,
        "pssm": 1.0,
        "esm": 0.0,
    }

    monkeypatch.setattr(cluster, "_get_mutations_per_record", lambda: [])
    monkeypatch.setattr(cluster, "_build_physchem_distance_matrix", lambda _x: None)
    monkeypatch.setattr(cluster, "_build_spatial_distance_matrix", lambda _x: None)
    monkeypatch.setattr(cluster, "_build_pssm_distance_matrix", lambda _x: None)
    monkeypatch.setattr(cluster, "_build_esm_distance_matrix", lambda _x: None)

    score_matrix = np.array(
        [
            [10.0, 8.0, 7.0],
            [8.0, 10.0, 6.0],
            [7.0, 6.0, 10.0],
        ]
    )
    expected = cluster.normalize_distance_matrix(cluster.build_distance_matrix_from_scores(score_matrix))
    actual = cluster._build_evo_distance(score_matrix)
    assert actual == pytest.approx(expected)


def test_evo_weight_renormalization_with_missing_components(monkeypatch, tmp_path):
    cluster = EvoCluster(str(tmp_path / "dummy.fasta"))
    cluster.evo_weights = {
        "seq": 1.0,
        "physchem": 0.0,
        "spatial": 0.0,
        "pssm": 1.0,
        "esm": 0.0,
    }

    monkeypatch.setattr(cluster, "_get_mutations_per_record", lambda: [])
    monkeypatch.setattr(cluster, "_build_physchem_distance_matrix", lambda _x: None)
    monkeypatch.setattr(cluster, "_build_spatial_distance_matrix", lambda _x: None)
    monkeypatch.setattr(
        cluster,
        "_build_pssm_distance_matrix",
        lambda _x: np.array(
            [
                [0.0, 1.0, 1.0],
                [1.0, 0.0, 2.0],
                [1.0, 2.0, 0.0],
            ]
        ),
    )
    monkeypatch.setattr(cluster, "_build_esm_distance_matrix", lambda _x: None)

    score_matrix = np.array(
        [
            [10.0, 8.0, 7.0],
            [8.0, 10.0, 6.0],
            [7.0, 6.0, 10.0],
        ]
    )
    seq_norm = cluster.normalize_distance_matrix(cluster.build_distance_matrix_from_scores(score_matrix))
    pssm_norm = cluster.normalize_distance_matrix(
        np.array(
            [
                [0.0, 1.0, 1.0],
                [1.0, 0.0, 2.0],
                [1.0, 2.0, 0.0],
            ]
        )
    )
    expected = cluster.normalize_distance_matrix(0.5 * seq_norm + 0.5 * pssm_norm)
    actual = cluster._build_evo_distance(score_matrix)
    assert actual == pytest.approx(expected)


def test_evo_esm_group_weight_is_fixed(tmp_path):
    cluster = EvoCluster(str(tmp_path / "dummy.fasta"))

    mutations_per_record = [
        [type("Mut", (), {"wt_res": "A", "position": 1, "mut_res": "V"})],
        [type("Mut", (), {"wt_res": "A", "position": 1, "mut_res": "T"})],
    ]

    esm_one = tmp_path / "esm_one.csv"
    pd.DataFrame(
        {
            "mutation": ["A1V", "A1T"],
            "esm-1v_1": [1.0, 0.2],
        }
    ).to_csv(esm_one, index=False)

    esm_two = tmp_path / "esm_two.csv"
    pd.DataFrame(
        {
            "mutation": ["A1V", "A1T"],
            "esm-1v_1": [1.0, 0.2],
            "esm-1v_2": [1.0, 0.2],
        }
    ).to_csv(esm_two, index=False)

    cluster.evo_esm_mutation_col = "mutation"
    cluster.evo_esm1v_table = str(esm_one)
    dist_one = cluster._build_esm_distance_matrix(mutations_per_record)

    cluster.evo_esm1v_table = str(esm_two)
    dist_two = cluster._build_esm_distance_matrix(mutations_per_record)

    assert dist_one is not None
    assert dist_two is not None
    assert dist_one == pytest.approx(dist_two)


def test_cluster_runner_dispatches_by_method(monkeypatch, tmp_path):
    from REvoDesign.clusters.cluster_runner import ClusterRunner

    calls = {"method": None}

    class _FakeClusterMethod:
        name = "AgglomerativeCluster"

        def __init__(self):
            self.cluster_output_fp = {"score": str(tmp_path / "score.png")}
            self.save_dir = str(tmp_path / "save_dir")

        def initialize_aligner(self):
            return None

        def run_clustering(self, progressbar=None):
            del progressbar
            pathlib.Path(self.cluster_output_fp["score"]).write_text("ok", encoding="utf-8")
            return None

        def override_cluster_centers_with_rosetta(self, _results):
            return None

        def cite(self):
            return None

    def _fake_get(cluster_method_name: str, **_kwargs):
        calls["method"] = cluster_method_name
        return _FakeClusterMethod()

    class _FakeCombinations:
        def __init__(self):
            self.expected_output_fasta = ""

        def run_combinations(self):
            output = tmp_path / "comb.fasta"
            _write_tiny_fasta(output)
            self.expected_output_fasta = str(output)

    class _FakeProgress:
        def setRange(self, *_args):
            return None

        def setValue(self, *_args):
            return None

    class _FakeUI:
        def __init__(self):
            self.stackedWidget = object()
            self.progressBar = _FakeProgress()

    class _FakeBus:
        ui = _FakeUI()

        values = {
            "ui.header_panel.input.molecule": "1ABC",
            "ui.header_panel.input.chain_id": "A",
            "designable_sequences": {"A": "AAAAAA"},
            "ui.cluster.input.from_mutant_txt": str(tmp_path / "in.mut.txt"),
            "ui.cluster.batch_size": 100,
            "ui.cluster.num_cluster": 2,
            "ui.cluster.mut_num_min": 1,
            "ui.cluster.mut_num_max": 1,
            "ui.cluster.score_matrix.default": "PAM30",
            "ui.cluster.shuffle": False,
            "ui.cluster.mutate_relax": False,
            "ui.cluster.method.use": "KMeansCluster",
            "ui.cluster.evo.inputs.pssm_profile": "",
            "ui.cluster.evo.inputs.esm1v_table": "",
            "ui.cluster.evo.inputs.structure_pdb": "",
            "ui.cluster.evo.esm.mutation_col": "mutation",
            "ui.cluster.evo.weights.seq": 1.0,
            "ui.cluster.evo.weights.physchem": 0.0,
            "ui.cluster.evo.weights.spatial": 0.0,
            "ui.cluster.evo.weights.pssm": 0.0,
            "ui.cluster.evo.weights.esm": 0.0,
            "ui.header_panel.nproc": 2,
            "rosetta.node_hint": "native",
        }

        def get_value(self, key, _type=None, cfg=None, default_value=None, reject_none=False):
            del _type, cfg, reject_none
            return self.values.get(key, default_value)

    (tmp_path / "in.mut.txt").write_text("A1V\n", encoding="utf-8")

    import REvoDesign.clusters.cluster_runner as runner_module
    import REvoDesign.clusters.combine_positions as combinations_module

    monkeypatch.setattr(runner_module, "ConfigBus", _FakeBus)
    monkeypatch.setattr(runner_module.ClusterMethodManager, "get", _fake_get)
    monkeypatch.setattr(runner_module, "set_widget_value", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(combinations_module, "Combinations", _FakeCombinations)

    runner = ClusterRunner(str(tmp_path))
    runner.run_clustering()

    assert calls["method"] == "KMeansCluster"
