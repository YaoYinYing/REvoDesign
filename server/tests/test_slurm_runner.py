# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for SlurmJob — wrapper script generation, srun args, shell quoting."""

from __future__ import annotations

import os
import subprocess
from unittest.mock import patch

import pytest
from revocompute.job import JobState
from revocompute.job.runners.slurm_runner import SlurmJob, _sanitize_name, _sh_quote


def _make_task_type(**kwargs):
    from revocompute.task_types import TaskType

    defaults = dict(
        name="gremlin",
        display_name="GREMLIN",
        docker_image="revodesign-runner:latest",
        command=["bash", "/app/run.sh"],
        input_extension=".fasta",
        input_label="FASTA file",
        stage_markers={
            "hhblits": "HHblits MSA",
            "gremlin": "GREMLIN opt",
        },
    )
    defaults.update(kwargs)
    return TaskType(**defaults)


def _make_runner(**kwargs):
    from revocompute.task_types import RunnerConfig

    defaults = dict(runner="slurm", slurm_image="/opt/images/gremlin_v1.sif")
    defaults.update(kwargs)
    return RunnerConfig(**defaults)


def _make_entities():
    return [
        {
            "name": "file",
            "type": "file",
            "value": "input.fasta",
            "verified_value": "input.fasta",
            "hash": "abc123",
            "mounted": "/workspace/inputs/input.fasta",
        },
        {
            "name": "iter",
            "type": "param",
            "value": "100",
            "verified_value": "100",
        },
    ]


# -- wrapper script -----------------------------------------------------------


def test_render_wrapper_has_shebang_and_set_e(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    lines = script.splitlines()
    assert lines[0] == "#!/bin/bash"
    assert "set -euo pipefail" in script


def test_render_input_staging_creates_hardlink(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "ln -f" in script
    assert "abc123.upload" in script
    assert "input.fasta" in script


# -- srun arguments -----------------------------------------------------------


def test_build_srun_args_includes_job_name(tmp_path):
    job = SlurmJob(
        "abcdef1234567890",
        _make_task_type(),
        _make_runner(),
        _make_entities(),
        str(tmp_path / "out"),
        username="testuser",
    )
    args = job._build_srun_args()
    job_name = next(a for a in args if a.startswith("--job-name="))
    assert "revocomput_testuser_gremlin_abcdef12" == job_name.split("=", 1)[1]


def test_build_srun_args_no_db_defaults(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    args = job._build_srun_args()
    # Without a manage_db, only --job-name is emitted
    assert len(args) == 1
    assert args[0].startswith("--job-name=")


# -- apptainer invocation -----------------------------------------------------


def test_render_apptainer_binds_and_env(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "apptainer run --nv" in script
    assert "--bind" in script
    assert "/workspace/inputs" in script
    assert "/workspace/outputs" in script
    assert "export APPTAINERENV_TASK_ID=" in script
    assert "export APPTAINERENV_TASK_TYPE=" in script
    assert "/opt/images/gremlin_v1.sif" in script


def test_render_apptainer_passes_iter_flag(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "-r 100" in script


def test_render_apptainer_raises_without_sif_image(tmp_path):
    runner = _make_runner(slurm_image="")
    job = SlurmJob("task-1", _make_task_type(), runner, _make_entities(), str(tmp_path / "out"))
    with pytest.raises(RuntimeError, match="slurm_image"):
        job._render_wrapper()


def test_render_apptainer_includes_runner_mounts(tmp_path):
    from revocompute.task_types import RunnerMount

    runner = _make_runner(mounts=(RunnerMount(host_path="/data/db", container_path="/opt/db", mode="ro"),))
    job = SlurmJob("task-1", _make_task_type(), runner, _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "--bind" in script
    assert "/data/db" in script
    assert "/opt/db" in script


def test_render_apptainer_includes_runner_env(tmp_path):
    runner = _make_runner(env={"MY_VAR": "my_value"})
    job = SlurmJob("task-1", _make_task_type(), runner, _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "MY_VAR" in script
    assert "my_value" in script
    assert "export APPTAINERENV_" in script


# -- submit / cancel (mocked Popen) -------------------------------------------


def test_submit_launches_srun(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))

    fake_proc = subprocess.Popen(["true"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    fake_proc.pid = 12345

    with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
        jid = job.submit()
        assert jid == "srun-12345"
        args = mock_popen.call_args[0][0]
        assert args[0] == "srun"


def test_poll_returns_completed_on_exit_zero(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    fake_proc = subprocess.Popen(["true"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    fake_proc.pid = 12345
    fake_proc.returncode = 0

    with patch("subprocess.Popen", return_value=fake_proc):
        job.submit()
        # process already exited, poll should detect that
        state = job.poll()
        assert state == JobState.COMPLETED


def test_cancel_terminates_process(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    job._process = subprocess.Popen(["sleep", "10"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    job._job_id = "srun-99999"
    try:
        job.cancel()
        # After cancel, process should be terminated
        assert job._process.poll() is not None
    finally:
        if job._process.poll() is None:
            job._process.kill()
            job._process.wait()


def test_cancel_before_submit_is_noop(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    job.cancel()  # should not raise


# -- shell quoting ------------------------------------------------------------


def test_sh_quote_plain():
    assert _sh_quote("hello") == "'hello'"


def test_sh_quote_with_single_quote():
    assert _sh_quote("it's") == "'it'\"'\"'s'"


def test_sh_quote_with_spaces():
    assert _sh_quote("a b") == "'a b'"


# -- name sanitization --------------------------------------------------------


def test_sanitize_name_alphanumeric():
    assert _sanitize_name("testuser") == "testuser"


def test_sanitize_name_with_special_chars():
    assert _sanitize_name("user@domain") == "user_domain"


def test_sanitize_name_empty():
    assert _sanitize_name("") == "unknown"
