# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
import uuid
from pathlib import Path

from test_tasks import _load_pssm_module, _upsert_task_for_user


def _finalize(monkeypatch, tmp_path: Path, task_type: str, runtime: str, files: dict[str, str | bytes]) -> dict:
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLED_TASKRUNNERS": runtime},
    )
    result_dir = tmp_path / task_type
    for relative_path, content in files.items():
        path = result_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content) if isinstance(content, bytes) else path.write_text(content, encoding="utf-8")
    task_id = uuid.uuid4().hex
    input_path = result_dir / next(iter(files))
    _upsert_task_for_user(
        module,
        task_id,
        filename=input_path.name,
        file_path=input_path,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )
    module.task_store.update_task(task_id, task_type=task_type)
    return module.task_runtime._finalize_results_manifest(
        module.task_store.get_task(task_id), execution_state="completed", finished_at=1_700_000_000
    )


def test_colabfold_manifest_resolves_quantitative_and_alignment_protocols(monkeypatch, tmp_path):
    manifest = _finalize(
        monkeypatch,
        tmp_path,
        "colabfold_af2",
        "colabfold_af2",
        {
            "sample_unrelaxed_rank_001_model.pdb": "MODEL        1\nENDMDL\n",
            "sample_scores_rank_001_model.json": json.dumps({"plddt": [80.0, 90.0], "ptm": 0.8, "max_pae": 20.0}),
            "sample_predicted_aligned_error_v1.json": json.dumps(
                {"predicted_aligned_error": [[1.0, 2.0], [2.0, 1.0]], "max_predicted_aligned_error": 20.0}
            ),
            "sample.a3m": ">query\nAC\n",
        },
    )

    assert manifest["output_check"]["state"] == "passed"
    assert [view["plugin"] for view in manifest["views"]] == [
        "candidate-collection",
        "metric-series",
        "matrix",
        "scalar-summary",
        "alignment",
    ]


def test_bioemu_manifest_requires_explicit_topology_trajectory_pair(monkeypatch, tmp_path):
    manifest = _finalize(
        monkeypatch,
        tmp_path,
        "bioemu",
        "bioemu",
        {"topology.pdb": "MODEL        1\nENDMDL\n", "samples.xtc": b"mock-trajectory"},
    )

    assert manifest["output_check"]["state"] == "passed"
    assert manifest["views"][0]["plugin"] == "trajectory"
    assert manifest["views"][0]["sources"] == {
        "topology": ["topology.pdb"],
        "coordinates": ["samples.xtc"],
    }
