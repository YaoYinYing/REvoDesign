# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Verify the Job ABC and its concrete implementations."""

from __future__ import annotations

from abc import abstractmethod

import pytest
from revocompute.job import Job, JobState
from revocompute.job.runners.docker_runner import DockerJob
from revocompute.job.runners.slurm_runner import SlurmJob


def _make_task_type():
    from revocompute.task_types import TaskType

    return TaskType(
        name="test",
        display_name="Test Task",
        docker_image="test:latest",
        command=["bash", "run.sh"],
        input_extension=".fasta",
        input_label="FASTA file",
        stage_markers={
            "stage1": "Stage One",
            "stage2": "Stage Two",
        },
    )


def _make_runner_config():
    from revocompute.task_types import RunnerConfig

    return RunnerConfig()


def _make_entities():
    return [
        {"name": "file", "type": "file", "value": "input.fasta", "verified_value": "input.fasta", "hash": "abc123", "mounted": "/workspace/inputs/input.fasta"},
        {"name": "iter", "type": "param", "name": "iter", "value": "100", "verified_value": "100"},
    ]


# -- Job ABC completeness -----------------------------------------------------


def test_job_is_abstract():
    """Job cannot be instantiated directly — it has abstract methods."""
    with pytest.raises(TypeError):
        Job("id", None, None, [], "/tmp")  # type: ignore[abstract]


def test_docker_job_is_concrete():
    """DockerJob implements all abstract methods."""
    tt = _make_task_type()
    runner = _make_runner_config()
    entities = _make_entities()
    job = DockerJob("test-id", tt, runner, entities, "/tmp/output")
    assert isinstance(job, Job)
    # No TypeError means all abstract methods are implemented


def test_slurm_job_is_concrete():
    """SlurmJob implements all abstract methods."""
    tt = _make_task_type()
    runner = _make_runner_config()
    entities = _make_entities()
    job = SlurmJob("test-id", tt, runner, entities, "/tmp/output")
    assert isinstance(job, Job)


def test_all_abstract_methods_listed():
    """Every abstract method in Job is implemented by both subclasses."""
    abstract_methods = {
        name for name, method in Job.__dict__.items()
        if hasattr(method, "__isabstractmethod__") and method.__isabstractmethod__
    }
    assert abstract_methods == {"submit", "poll", "cancel"}

    for cls in (DockerJob, SlurmJob):
        for name in abstract_methods:
            impl = getattr(cls, name, None)
            assert impl is not None, f"{cls.__name__}.{name} is missing"
            assert not hasattr(impl, "__isabstractmethod__") or not impl.__isabstractmethod__, (
                f"{cls.__name__}.{name} is still abstract"
            )


# -- Job properties -----------------------------------------------------------


def test_file_entities_filter():
    tt = _make_task_type()
    runner = _make_runner_config()
    entities = [
        {"name": "file1", "type": "file", "value": "a.fasta", "verified_value": "a.fasta", "hash": "aaa", "mounted": "/in/a.fasta"},
        {"name": "param1", "type": "param", "name": "x", "value": "1", "verified_value": "1"},
        {"name": "file2", "type": "file", "value": "b.fasta", "verified_value": "b.fasta", "hash": "bbb", "mounted": "/in/b.fasta"},
    ]
    job = DockerJob("test-id", tt, runner, entities, "/tmp/output")
    assert len(job.file_entities) == 2
    assert job.file_entities[0]["name"] == "file1"
    assert job.file_entities[1]["name"] == "file2"


def test_param_entities_filter():
    tt = _make_task_type()
    runner = _make_runner_config()
    entities = [
        {"name": "file1", "type": "file", "value": "a.fasta", "verified_value": "a.fasta", "hash": "aaa", "mounted": "/in/a.fasta"},
        {"name": "p1", "type": "param", "name": "x", "value": "1", "verified_value": "1"},
        {"name": "p2", "type": "param", "name": "y", "value": "2", "verified_value": "2"},
    ]
    job = DockerJob("test-id", tt, runner, entities, "/tmp/output")
    assert len(job.param_entities) == 2


def test_job_id_starts_none():
    tt = _make_task_type()
    runner = _make_runner_config()
    job = DockerJob("test-id", tt, runner, [], "/tmp/output")
    assert job.job_id is None


# -- JobState enum ------------------------------------------------------------


def test_job_state_values():
    assert JobState.PENDING.value == "pending"
    assert JobState.RUNNING.value == "running"
    assert JobState.COMPLETED.value == "completed"
    assert JobState.FAILED.value == "failed"
    assert JobState.CANCELLED.value == "cancelled"
