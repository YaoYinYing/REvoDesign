# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

import pathlib
import random

from Bio import SeqIO
from REvoDesign.clusters.cluster_sequence import Clustering


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


def _run_cluster_once(tmp_path: pathlib.Path, run_name: str) -> tuple[str, str]:
    input_fasta = tmp_path / f"{run_name}.fasta"
    _write_tiny_fasta(input_fasta)

    cluster = Clustering(str(input_fasta))
    cluster._save_dir = str(tmp_path / f"output_{run_name}")
    cluster.num_clusters = 2
    cluster.num_proc = 2
    cluster.batch_size = 10
    cluster.initialize_aligner()

    cluster.run_clustering(_DummyProgressbar())

    center_fp = pathlib.Path(cluster.cluster_output_fp["cluster_centers"])
    compat_fp = center_fp.parent / "cluster_centers_stochastic.fasta"
    return center_fp.read_text(encoding="utf-8"), compat_fp.read_text(encoding="utf-8")


def test_cluster_representative_is_deterministic_and_not_random(monkeypatch, tmp_path):
    import REvoDesign.tools.customized_widgets as customized_widgets

    monkeypatch.setattr(customized_widgets, "QtParallelExecutor", _FakeQtParallelExecutor)

    def _raise_if_random_choice(*_args, **_kwargs):
        raise AssertionError("random.choice should not be used for cluster center selection.")

    monkeypatch.setattr(random, "choice", _raise_if_random_choice)

    first_center_content, first_compat_content = _run_cluster_once(tmp_path, "first")
    second_center_content, second_compat_content = _run_cluster_once(tmp_path, "second")

    assert first_center_content == first_compat_content
    assert second_center_content == second_compat_content
    assert first_center_content == second_center_content


class _FakeRosettaAnalyser:
    def __init__(self, decoy_name):
        self.best_decoy = {"decoy": decoy_name}


def test_rosetta_override_rewrites_cluster_centers(tmp_path):
    save_dir = tmp_path / "cluster_run"
    save_dir.mkdir(parents=True, exist_ok=True)

    cluster = Clustering(str(tmp_path / "dummy.fasta"))
    cluster.save_dir = str(save_dir)
    cluster.num_clusters = 2

    c0_fp = save_dir / "c.0.fasta"
    c1_fp = save_dir / "c.1.fasta"
    c0_fp.write_text(">c0_a\nAAAAAA\n>c0_b\nAAAATA\n", encoding="utf-8")
    c1_fp.write_text(">c1_a\nTTTTTT\n>c1_b\nTTTTTA\n", encoding="utf-8")

    cluster.write_cluster_center_files(
        {
            0: next(SeqIO.parse(c0_fp, "fasta")),
            1: next(SeqIO.parse(c1_fp, "fasta")),
        }
    )

    cluster.override_cluster_centers_with_rosetta(
        [
            _FakeRosettaAnalyser("c0_b"),
            _FakeRosettaAnalyser("c1_b"),
        ]
    )

    centers_fp = pathlib.Path(cluster.cluster_output_fp["cluster_centers"])
    content = centers_fp.read_text(encoding="utf-8")
    compat_content = (save_dir / "cluster_centers_stochastic.fasta").read_text(encoding="utf-8")

    assert ">c0_b_cluster_0" in content
    assert ">c1_b_cluster_1" in content
    assert content == compat_content
