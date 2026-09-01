# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
import signal
from pathlib import Path

import pytest
from revocompute.job import JobState
from revocompute.resource_policy import ResolvedResources
from revocompute.task_types import RunnerConfig, RuntimeFamily, TaskType, WorkflowStage


@pytest.fixture(autouse=True)
def _isolated_runtime_state(monkeypatch, tmp_path):
    server_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("SERVER_DIR", str(tmp_path))
    monkeypatch.setenv("CONFIG_DIR", str(server_root / "config"))
    monkeypatch.setenv("ENABLED_TASKRUNNERS", "alphafold")


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

    def _update(task_id, **fields):
        del task_id
        updates.append(fields)
        return True

    monkeypatch.setattr(task_runtime.task_store, "update_task", _update)
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


def test_composer_does_not_submit_after_cancellation_claim_fails(monkeypatch):
    from revocompute import task_runtime

    runtime = RuntimeFamily("alphafold", "image", ("bash", "run.sh"), "Dockerfile", "runner.def", "image.sif")
    stage = WorkflowStage("alphafold.model", "Model", True, ("-s", "model"), ("model",))
    task_type = TaskType(
        "alphafold",
        "AlphaFold2",
        runtime,
        ".fasta",
        "FASTA",
        gpus=True,
        stage_markers={"model": "Model"},
        workflow=(stage,),
    )
    monkeypatch.setattr(task_runtime.task_store, "update_task", lambda *args, **kwargs: False)
    monkeypatch.setattr(task_runtime, "_create_job", lambda *args, **kwargs: pytest.fail("job must not be created"))

    result = task_runtime._run_compute_workflow(
        "b" * 32,
        {},
        task_type,
        RunnerConfig(),
        [],
        "/tmp/results",
        {"alphafold.model": _policy(True)},
        lambda stage_name: None,
    )

    assert result == JobState.CANCELLED


def test_composer_cancels_submitted_job_when_handle_cannot_be_persisted(monkeypatch):
    from revocompute import task_runtime

    runtime = RuntimeFamily("alphafold", "image", ("bash", "run.sh"), "Dockerfile", "runner.def", "image.sif")
    stage = WorkflowStage("alphafold.model", "Model", True, ("-s", "model"), ("model",))
    task_type = TaskType(
        "alphafold",
        "AlphaFold2",
        runtime,
        ".fasta",
        "FASTA",
        gpus=True,
        stage_markers={"model": "Model"},
        workflow=(stage,),
    )
    updates = iter((True, False))
    cancelled = []

    class _Job:
        def submit(self):
            return "42"

        def cancel(self):
            cancelled.append(True)

    monkeypatch.setattr(task_runtime.task_store, "update_task", lambda *args, **kwargs: next(updates))
    monkeypatch.setattr(task_runtime, "_create_job", lambda *args, **kwargs: _Job())

    result = task_runtime._run_compute_workflow(
        "c" * 32,
        {},
        task_type,
        RunnerConfig(),
        [],
        "/tmp/results",
        {"alphafold.model": _policy(True)},
        lambda stage_name: None,
    )

    assert result == JobState.CANCELLED
    assert cancelled == [True]


def test_workflow_recovery_claims_stops_and_requeues_once(monkeypatch):
    from revocompute import task_runtime

    task = {
        "md5sum": "d" * 32,
        "status": "running",
        "task_type": "alphafold",
        "slurm_job_id": "1234",
        "container_id": None,
        "workflow_state": json.dumps({"alphafold.features": {"status": "running"}}),
    }
    claims = []
    stops = []
    updates = []

    class _TaskType:
        workflow = (object(),)

    class _Queued:
        id = "replacement-task"

    monkeypatch.setattr(task_runtime.task_store, "list_tasks", lambda: [task])
    monkeypatch.setattr(
        task_runtime.task_store,
        "claim_task_recovery",
        lambda task_id, expected_status: claims.append((task_id, expected_status)) or True,
    )
    monkeypatch.setattr(
        task_runtime.task_store,
        "update_task",
        lambda task_id, **fields: updates.append((task_id, fields)) or True,
    )
    monkeypatch.setattr(task_runtime, "_get_task_type", lambda name: (_TaskType(), object()))
    monkeypatch.setattr(
        task_runtime,
        "_stop_orphaned_workflow_execution",
        lambda *args: stops.append(args) or "",
    )
    monkeypatch.setattr(task_runtime.run_compute_task, "apply_async", lambda *args, **kwargs: _Queued())

    assert task_runtime._recover_orphaned_tasks() == 1
    assert claims == [("d" * 32, "running")]
    assert stops == [("d" * 32, "1234", "")]
    assert updates[-1][1]["celery_task_id"] == "replacement-task"


def test_workflow_recovery_enqueue_failure_stays_discoverable(monkeypatch):
    from revocompute import task_runtime

    task = {"md5sum": "e" * 32, "status": "queued", "task_type": "alphafold"}
    updates = []

    class _TaskType:
        workflow = (object(),)

    monkeypatch.setattr(task_runtime.task_store, "list_tasks", lambda: [task])
    monkeypatch.setattr(task_runtime.task_store, "claim_task_recovery", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        task_runtime.task_store,
        "update_task",
        lambda task_id, **fields: updates.append(fields) or True,
    )
    monkeypatch.setattr(task_runtime, "_get_task_type", lambda name: (_TaskType(), object()))
    monkeypatch.setattr(task_runtime, "_stop_orphaned_workflow_execution", lambda *args: "")
    monkeypatch.setattr(
        task_runtime.run_compute_task,
        "apply_async",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("broker unavailable")),
    )

    assert task_runtime._recover_orphaned_tasks() == 1
    assert updates[-1]["status"] == "queued"
    assert "broker unavailable" in updates[-1]["error"]


def test_workflow_recovery_escalates_srun_termination(monkeypatch):
    from revocompute import task_runtime

    kills = []
    waits = iter((False, True))
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"srun task-1234")
    monkeypatch.setattr(task_runtime.os, "kill", lambda pid, sig: kills.append((pid, sig)))
    monkeypatch.setattr(task_runtime, "_wait_for_process_exit", lambda pid, timeout: next(waits))

    error = task_runtime._stop_orphaned_workflow_execution("task-1234", "srun-42", "")

    assert error == ""
    assert kills == [(42, signal.SIGTERM), (42, signal.SIGKILL)]
