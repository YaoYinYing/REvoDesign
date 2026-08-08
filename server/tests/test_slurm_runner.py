# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for SlurmJob — sbatch script generation, state mapping, queue parsing."""

from __future__ import annotations

import json
import re
import subprocess
from unittest.mock import patch

import pytest
from revocompute.job import JobState
from revocompute.job.runners.slurm_runner import _SQUEUE_STATE_MAP, SlurmJob, _sh_quote


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
            "name": "iter",
            "value": "100",
            "verified_value": "100",
        },
    ]


# -- sbatch script generation -------------------------------------------------


def test_render_script_has_shebang_and_set_e(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_script({})
    lines = script.splitlines()
    assert lines[0] == "#!/bin/bash"
    assert "set -euo pipefail" in script


def test_render_sbatch_directives_includes_standard(tmp_path):
    job = SlurmJob("abcdef1234567890", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_script({})
    assert f"#SBATCH --job-name=revo_{'abcdef12'}" in script
    assert "#SBATCH --output=" in script
    assert "#SBATCH --error=" in script


def test_render_sbatch_directives_from_db_args(tmp_path):
    """sbatch_args from the DB are rendered as #SBATCH directives."""
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    db_args = {
        "slurm_partition": "gpu",
        "slurm_cpus_per_task": "4",
        "slurm_gres": "gpu:1",
        "slurm_mem": "16G",
        "slurm_time": "01:00:00",
        "slurm_exclusive": "true",
        # these should NOT appear — not in the field mapping
        "slurm_nodes": None,
        "slurm_ntasks": None,
    }
    script = job._render_script(db_args)
    assert "#SBATCH --partition=gpu" in script
    assert "#SBATCH --cpus-per-task=4" in script
    assert "#SBATCH --gres=gpu:1" in script
    assert "#SBATCH --mem=16G" in script
    assert "#SBATCH --time=01:00:00" in script
    assert "#SBATCH --exclusive" in script
    # None values should not appear
    assert "--nodes" not in script
    assert "--ntasks" not in script


def test_render_sbatch_exclusive_false_omitted(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    db_args = {"slurm_exclusive": "false"}
    script = job._render_script(db_args)
    assert "--exclusive" not in script  # only added when true


# -- input staging (upload suffix fix) ----------------------------------------


def test_render_input_staging_creates_hardlink(tmp_path):
    """The .upload file is hard-linked to the original filename so the runner
    sees the correct extension (e.g. .fasta, not .upload)."""
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_script({})
    assert "ln -f" in script
    # src is <hash>.upload, dst is <original> in output dir
    assert "abc123.upload" in script
    assert "input.fasta" in script


# -- apptainer invocation -----------------------------------------------------


def test_render_apptainer_invocation_binds_and_env(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_script({})
    assert "apptainer run --nv" in script
    assert "--bind" in script
    assert "/workspace/inputs" in script
    assert "/workspace/outputs" in script
    assert "export TASK_ID=" in script
    assert "export TASK_TYPE=" in script
    assert "/opt/images/gremlin_v1.sif" in script


def test_render_apptainer_invocation_passes_iter_flag(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_script({})
    assert "-r 100" in script


def test_render_apptainer_raises_without_sif_image(tmp_path):
    runner = _make_runner(slurm_image="")
    job = SlurmJob("task-1", _make_task_type(), runner, _make_entities(), str(tmp_path / "out"))
    with pytest.raises(RuntimeError, match="slurm_image"):
        job._render_script({})


def test_render_apptainer_includes_runner_mounts(tmp_path):
    from revocompute.task_types import RunnerMount

    runner = _make_runner(mounts=(RunnerMount(host_path="/data/db", container_path="/opt/db", mode="ro"),))
    job = SlurmJob("task-1", _make_task_type(), runner, _make_entities(), str(tmp_path / "out"))
    script = job._render_script({})
    assert "--bind" in script
    assert "/data/db" in script
    assert "/opt/db" in script


def test_render_apptainer_includes_runner_env(tmp_path):
    runner = _make_runner(env={"MY_VAR": "my_value"})
    job = SlurmJob("task-1", _make_task_type(), runner, _make_entities(), str(tmp_path / "out"))
    script = job._render_script({})
    assert "MY_VAR" in script
    assert "my_value" in script
    assert "export " in script


def test_render_apptainer_params_in_env(tmp_path):
    entities = _make_entities()
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), entities, str(tmp_path / "out"))
    script = job._render_script({})
    assert "TASK_PARAMS=" in script
    # extract the JSON value from the export line
    match = re.search(r"TASK_PARAMS='(.+?)'", script)
    assert match
    params = json.loads(match.group(1))
    assert params["iter"] == "100"


# -- state mapping ------------------------------------------------------------


def test_squeue_state_map_terminal():
    terminal_raw = {
        "COMPLETED",
        "CD",
        "FAILED",
        "F",
        "TIMEOUT",
        "TO",
        "CANCELLED",
        "CA",
        "NODE_FAIL",
        "NF",
        "PREEMPTED",
        "PR",
        "BOOT_FAIL",
        "BF",
        "DEADLINE",
        "DL",
        "OUT_OF_MEMORY",
        "OOM",
    }
    for raw in terminal_raw:
        state = _SQUEUE_STATE_MAP[raw]
        assert state in {
            JobState.COMPLETED,
            JobState.FAILED,
            JobState.CANCELLED,
        }, f"{raw} -> {state} should be terminal"


def test_squeue_state_map_running():
    running_raw = {"RUNNING", "R", "COMPLETING", "CG", "CONFIGURING", "CF"}
    for raw in running_raw:
        assert _SQUEUE_STATE_MAP[raw] == JobState.RUNNING


def test_squeue_state_map_pending():
    pending_raw = {"PENDING", "PD", "REQUEUED", "RQ", "RESV_DEL_HOLD", "RD"}
    for raw in pending_raw:
        assert _SQUEUE_STATE_MAP[raw] == JobState.PENDING


def test_squeue_state_map_unknown_defaults_running():
    assert _SQUEUE_STATE_MAP.get("SOME_UNKNOWN_STATE", JobState.RUNNING) == JobState.RUNNING


# -- submit / cancel integration (mocked subprocess) --------------------------


def test_submit_parses_sbatch_output(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()
    job = SlurmJob("task-1", tt, runner, entities, str(tmp_path / "out"))

    def _fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="Submitted batch job 4242\n",
            stderr="",
        )

    with patch("revocompute.job.runners.slurm_runner.subprocess.run", side_effect=_fake_run):
        jid = job.submit()
        assert jid == "4242"


def test_submit_raises_on_sbatch_failure(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()
    job = SlurmJob("task-1", tt, runner, entities, str(tmp_path / "out"))

    def _fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="",
            stderr="sbatch: error: Invalid partition",
        )

    with patch("revocompute.job.runners.slurm_runner.subprocess.run", side_effect=_fake_run):
        with pytest.raises(RuntimeError, match="sbatch failed"):
            job.submit()


def test_cancel_calls_scancel(tmp_path):
    tt = _make_task_type()
    runner = _make_runner()
    entities = _make_entities()
    job = SlurmJob("task-1", tt, runner, entities, str(tmp_path / "out"))
    job._job_id = "4242"

    def _fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="",
            stderr="",
        )

    with patch("revocompute.job.runners.slurm_runner.subprocess.run", side_effect=_fake_run) as mock_run:
        job.cancel()
        scancel_found = any(
            call.kwargs.get("args", [""])[0] == "scancel"
            or (call.args and call.args[0] and call.args[0][0] == "scancel")
            for call in mock_run.call_args_list
        )
        assert scancel_found, f"scancel not found in calls: {mock_run.call_args_list}"


def test_cancel_before_submit_is_noop_2(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    job.cancel()  # should not raise


# -- shell quoting ------------------------------------------------------------


def test_sh_quote_plain():
    assert _sh_quote("hello") == "'hello'"


def test_sh_quote_with_single_quote():
    assert _sh_quote("it's") == "'it'\"'\"'s'"


def test_sh_quote_with_spaces():
    assert _sh_quote("a b") == "'a b'"
