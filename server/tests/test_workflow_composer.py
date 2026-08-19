# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
from pathlib import Path

from revocompute.job import JobState
from revocompute.resource_policy import ResolvedResources
from revocompute.task_types import RuntimeFamily, RunnerConfig, TaskType, WorkflowStage


def _policy(requires_gpu: bool) -> ResolvedResources:
    return ResolvedResources(
        cpus=8,
        memory="16G",
        max_runtime_seconds=3600,
        partition="gpu" if requires_gpu else "cpu",
        gres="gpu:1" if requires_gpu else None,
        nodes=1,
        ntasks=1,
        qos=None,
        account=None,
        constraint=None,
        exclusive=False,
        requires_gpu=requires_gpu,
        sources={},
    )


def test_composer_resumes_after_completed_feature_stage(monkeypatch):
    server_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("SERVER_DIR", str(server_root))
    monkeypatch.setenv("CONFIG_DIR", str(server_root / "config"))
    monkeypatch.setenv("ENABLED_TASKRUNNERS", "alphafold")
    from revocompute import task_runtime

    runtime = RuntimeFamily("alphafold", "image", ("bash", "run.sh"), "Dockerfile", "runner.def", "image.sif")
    stages = (
        WorkflowStage("alphafold.features", "Features", False, ("-s", "features"), ("msa",)),
        WorkflowStage("alphafold.model", "Model", True, ("-s", "model"), ("model",)),
    )
    task_type = TaskType(
        "alphafold",
        "AlphaFold2",
        runtime,
        ".fasta",
        "FASTA",
        gpus=True,
        stage_markers={"msa": "MSA", "model": "Model"},
        workflow=stages,
    )
    updates = []
    created = []

    class _Job:
        def submit(self):
            return "42"

        def poll(self):
            return JobState.COMPLETED

    def _create(*args, **kwargs):
        created.append((args[1], kwargs["resource_policy"]))
        return _Job()

    monkeypatch.setattr(task_runtime, "_create_job", _create)
    monkeypatch.setattr(task_runtime.task_store, "update_task", lambda task_id, **fields: updates.append(fields))
    task = {
        "username": "tester",
        "workflow_state": json.dumps({"alphafold.features": {"status": "completed", "job_id": "41"}}),
    }

    result = task_runtime._run_compute_workflow(
        "a" * 32,
        task,
        task_type,
        RunnerConfig(),
        [],
        "/tmp/results",
        {"alphafold.features": _policy(False), "alphafold.model": _policy(True)},
        lambda stage: None,
    )

    assert result == JobState.COMPLETED
    assert len(created) == 1
    assert created[0][0].name == "alphafold-model"
    assert created[0][0].gpus is True
    assert created[0][1].requires_gpu is True
    final_state = json.loads(updates[-1]["workflow_state"])
    assert final_state["alphafold.features"]["status"] == "completed"
    assert final_state["alphafold.model"]["status"] == "completed"
