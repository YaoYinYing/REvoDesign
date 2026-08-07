# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for DockerJob with a mocked Docker client."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import docker
import pytest
from revocompute.job import JobState
from revocompute.job.runners.docker_runner import DockerJob


def _make_task_type(**kwargs):
    from revocompute.task_types import TaskType

    defaults = dict(
        name="test",
        display_name="Test Task",
        docker_image="test:latest",
        command=["bash", "run.sh"],
        input_extension=".fasta",
        input_label="FASTA file",
        stage_markers={"stage1": "Stage One", "stage2": "Stage Two"},
    )
    defaults.update(kwargs)
    return TaskType(**defaults)


def _make_runner(**kwargs):
    from revocompute.task_types import RunnerConfig

    return RunnerConfig(**kwargs)


def _make_entities(hash_value="abc123"):
    return [
        {
            "name": "file",
            "type": "file",
            "value": "input.fasta",
            "verified_value": "input.fasta",
            "hash": hash_value,
            "mounted": "/workspace/inputs/input.fasta",
        },
    ]


def _setup_submit_env(tmp_path, hash_value="abc123"):
    """Create .upload file where CONFIG expects it. Returns output_dir."""
    from revocompute.job.runners.docker_runner import CONFIG

    upload_dir = CONFIG.upload_folder
    os.makedirs(upload_dir, exist_ok=True)
    (Path(upload_dir) / f"{hash_value}.upload").write_text(">test\nACDE\n")
    output_dir = str(tmp_path / "output")
    return output_dir


# -- submit -------------------------------------------------------------------


def test_submit_creates_container_and_returns_id(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()
    output_dir = _setup_submit_env(tmp_path)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "deadbeef1234"
    mock_client.containers.run.return_value = mock_container

    job = DockerJob("task-1", tt, runner, entities, output_dir, docker_client=mock_client)
    job_id = job.submit()

    assert job_id == "deadbeef1234"
    assert job.job_id == "deadbeef1234"
    mock_client.containers.run.assert_called_once()
    call_kwargs = mock_client.containers.run.call_args.kwargs
    assert call_kwargs["image"] == "test:latest"
    assert call_kwargs["detach"] is True
    assert call_kwargs["remove"] is False


def test_submit_passes_gpu_device_request(tmp_path):
    tt = _make_task_type(gpus=True)
    runner = _make_runner()
    entities = _make_entities()
    output_dir = _setup_submit_env(tmp_path)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "gpu-job"
    mock_client.containers.run.return_value = mock_container

    job = DockerJob("gpu-task", tt, runner, entities, output_dir, docker_client=mock_client)
    job.submit()

    call_kwargs = mock_client.containers.run.call_args.kwargs
    assert call_kwargs["device_requests"] is not None


def test_submit_without_gpu_has_no_device_request(tmp_path):
    tt = _make_task_type(gpus=False)
    runner = _make_runner()
    entities = _make_entities()
    output_dir = _setup_submit_env(tmp_path)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "cpu-job"
    mock_client.containers.run.return_value = mock_container

    job = DockerJob("cpu-task", tt, runner, entities, output_dir, docker_client=mock_client)
    job.submit()

    call_kwargs = mock_client.containers.run.call_args.kwargs
    assert call_kwargs["device_requests"] is None


# -- poll ---------------------------------------------------------------------


def test_poll_parses_stage_markers_from_logs(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()
    output_dir = _setup_submit_env(tmp_path)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "test-container"
    mock_client.containers.run.return_value = mock_container

    mock_container.logs.return_value = [
        b"Starting computation\n",
        b"REVODESIGN_STAGE:stage1\n",
        b"Processing...\n",
        b"REVODESIGN_STAGE:stage2\n",
        b"Done\n",
    ]
    mock_container.wait.return_value = {"StatusCode": 0}

    stages_seen: list[str] = []

    job = DockerJob("task-1", tt, runner, entities, output_dir, docker_client=mock_client, stage_callback=stages_seen.append)
    job.submit()
    state = job.poll()

    assert state == JobState.COMPLETED
    assert stages_seen == ["stage1", "stage2"]


def test_poll_handles_nonzero_exit(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()
    output_dir = _setup_submit_env(tmp_path)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "fail-container"
    mock_client.containers.run.return_value = mock_container

    mock_container.logs.return_value = [b"Error: something went wrong\n"]
    mock_container.wait.return_value = {"StatusCode": 1}

    job = DockerJob("task-1", tt, runner, entities, output_dir, docker_client=mock_client)
    job.submit()

    with pytest.raises(docker.errors.ContainerError):
        job.poll()


def test_poll_deduplicates_stage_callbacks(tmp_path):
    """Multiple lines with the same stage marker only fire the callback once."""
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()
    output_dir = _setup_submit_env(tmp_path)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "dup-stage"
    mock_client.containers.run.return_value = mock_container

    mock_container.logs.return_value = [
        b"REVODESIGN_STAGE:stage1\n",
        b"REVODESIGN_STAGE:stage1\n",  # duplicate
        b"REVODESIGN_STAGE:stage1 extra info\n",  # same stage, different suffix
        b"REVODESIGN_STAGE:stage2\n",
    ]
    mock_container.wait.return_value = {"StatusCode": 0}

    stages_seen: list[str] = []

    job = DockerJob("task-1", tt, runner, entities, output_dir, docker_client=mock_client, stage_callback=stages_seen.append)
    job.submit()
    job.poll()

    assert stages_seen == ["stage1", "stage2"]


# -- cancel -------------------------------------------------------------------


def test_cancel_kills_container(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()
    output_dir = _setup_submit_env(tmp_path)

    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "kill-me"
    mock_client.containers.run.return_value = mock_container

    job = DockerJob("task-1", tt, runner, entities, output_dir, docker_client=mock_client)
    job.submit()
    job.cancel()

    mock_container.kill.assert_called_once()


def test_cancel_before_submit_is_noop():
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()

    job = DockerJob("task-1", tt, runner, entities, "/tmp/output", docker_client=MagicMock())
    job.cancel()  # should not raise


# -- env / command args -------------------------------------------------------


def test_build_env_includes_task_params(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = [
        {"name": "file", "type": "file", "value": "x.fasta", "verified_value": "x.fasta", "hash": "abc", "mounted": "/in/x.fasta"},
        {"name": "iter", "type": "param", "name": "iter", "value": "50", "verified_value": "50"},
    ]

    job = DockerJob("task-1", tt, runner, entities, str(tmp_path / "output"))
    env = job._build_env()

    assert env["TASK_ID"] == "task-1"
    assert env["TASK_TYPE"] == "test"
    assert "TASK_PARAMS" in env
    import json

    params = json.loads(env["TASK_PARAMS"])
    assert params["iter"] == "50"


def test_build_command_args_passes_iter_flag(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = [
        {"name": "file", "type": "file", "value": "x.fasta", "verified_value": "x.fasta", "hash": "abc", "mounted": "/in/x.fasta"},
        {"name": "iter", "type": "param", "name": "iter", "value": "200", "verified_value": "200"},
    ]

    job = DockerJob("task-1", tt, runner, entities, str(tmp_path / "output"))
    args = job._build_command_args()

    assert "-i" in args
    assert "/in/x.fasta" in args  # ponytail: first file entity's mounted path
    assert "-o" in args
    assert "/workspace/outputs" in args
    assert "-r" in args
    assert "200" in args
