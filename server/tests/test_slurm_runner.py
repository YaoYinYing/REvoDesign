# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for SlurmJob — wrapper script generation, srun args, shell quoting."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from revocompute.job import JobState
from revocompute.job.runners.slurm_runner import SlurmJob, _sanitize_name, _sh_quote
from revocompute.resource_policy import ResolvedResources


def _make_task_type(**kwargs):
    from revocompute.task_types import RuntimeFamily, TaskType

    defaults = dict(
        name="gremlin",
        display_name="GREMLIN",
        runtime=RuntimeFamily(
            name="gremlin",
            docker_image="revodesign-runner:latest",
            entrypoint=("bash", "/app/run.sh"),
            dockerfile="docker/gremlin/Dockerfile",
            definition="docker/gremlin/gremlin.def",
            slurm_image="/opt/images/gremlin_v1.sif",
        ),
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

    return RunnerConfig(**kwargs)


def _make_entities():
    return [
        {
            "name": "file",
            "type": "file",
            "value": "input.fasta",
            "verified_value": "input.fasta",
            "relative_path": "input.fasta",
            "hash": "abc123",
            "mounted": "/mnt/revocompute/tester/inputs/input.fasta",
            "snapshot_path": "/srv/workspaces/tester/task-1/inputs/input.fasta",
            "snapshot_root": "/srv/workspaces/tester/task-1/inputs",
            "workspace_key": "tester",
        },
        {
            "name": "iter",
            "type": "param",
            "value": "100",
            "verified_value": "100",
        },
    ]


class _FakeSrunProcess:
    """A subprocess.Popen-shaped scheduler boundary fake."""

    def __init__(
        self,
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int | None = 0,
        pid: int = 4217,
        timeout_once: bool = False,
    ) -> None:
        self.stdout = StringIO(stdout)
        self.stderr = StringIO(stderr)
        self.returncode = returncode
        self.pid = pid
        self.timeout_once = timeout_once
        self.wait_calls = 0
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.timeout_once and not self.killed:
            self.timeout_once = False
            raise subprocess.TimeoutExpired(["srun"], timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def _policy(**overrides) -> ResolvedResources:
    defaults = dict(
        cpus=1,
        memory="4G",
        max_runtime_seconds=24 * 60 * 60,
        partition=None,
        gres=None,
        nodes=1,
        ntasks=1,
        qos=None,
        account=None,
        constraint=None,
        exclusive=False,
        requires_gpu=False,
        sources={},
    )
    defaults.update(overrides)
    return ResolvedResources(**defaults)


# -- wrapper script -----------------------------------------------------------


def test_render_wrapper_has_shebang_and_set_e(tmp_path):
    job = SlurmJob(
        "task-1",
        _make_task_type(),
        _make_runner(),
        _make_entities(),
        str(tmp_path / "out"),
        username="alice",
    )
    script = job._render_wrapper()
    lines = script.splitlines()
    assert lines[0] == "#!/bin/bash"
    assert "set -euo pipefail" in script


def test_render_input_snapshot_is_verified_without_staging(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "test -f '/srv/workspaces/tester/task-1/inputs/input.fasta'" in script
    assert "abc123  /srv/workspaces/tester/task-1/inputs/input.fasta" in script
    assert "sha256sum --check --status" in script
    assert "ln -f" not in script


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
    assert "--cpus-per-task=1" in args
    assert "--mem=4G" in args
    assert "--time=1-00:00:00" in args
    assert "--nodes=1" in args
    assert "--ntasks=1" in args
    assert f"--chdir={tmp_path / 'out'}" in args
    assert "--job-name=revocomput_unknown_gremlin_task-1" in args


def test_build_srun_args_gpu_task_reserves_one_gpu_by_default(tmp_path):
    job = SlurmJob(
        "task-1",
        _make_task_type(gpus=True),
        _make_runner(),
        _make_entities(),
        str(tmp_path / "out"),
    )

    assert "--gres=gpu:1" in job._build_srun_args()


def test_build_srun_args_gpu_task_uses_configured_gres(tmp_path):
    class _ManageDb:
        def resolve_task_resources(self, tool, *, requires_gpu, default_timeout_seconds):
            return ResolvedResources(
                cpus=1,
                memory="4G",
                max_runtime_seconds=3600,
                partition=None,
                gres="gpu:a100:1",
                nodes=1,
                ntasks=1,
                qos=None,
                account=None,
                constraint=None,
                exclusive=False,
                requires_gpu=True,
                sources={"gres": "task:slurm_gres"},
            )

    job = SlurmJob(
        "task-1",
        _make_task_type(gpus=True),
        _make_runner(),
        _make_entities(),
        str(tmp_path / "out"),
        manage_db=_ManageDb(),
    )
    args = job._build_srun_args()

    assert "--gres=gpu:a100:1" in args
    assert "--gres=gpu:1" not in args


# -- apptainer invocation -----------------------------------------------------


def test_render_apptainer_binds_and_env(tmp_path):
    job = SlurmJob(
        "task-1",
        _make_task_type(gpus=True),
        _make_runner(),
        _make_entities(),
        str(tmp_path / "out"),
    )
    script = job._render_wrapper()
    assert "apptainer run --nv" in script
    assert "--bind" in script
    # Strong containment: private /tmp + $HOME tmpfs, no host env or mounts
    # beyond the explicit binds below.
    assert "--containall" in script
    assert "--cleanenv" in script
    assert "/mnt/revocompute/tester/inputs" in script
    assert "/mnt/revocompute/tester/outputs" in script
    assert "export APPTAINERENV_TASK_ID=" in script
    assert "export APPTAINERENV_TASK_TYPE=" in script
    assert "export APPTAINERENV_TASK_MANIFEST=" in script
    assert "export APPTAINERENV_CUDA_VISIBLE_DEVICES=" in script
    assert "-i '/mnt/revocompute/tester/inputs/task.json'" in script
    assert "/opt/images/gremlin_v1.sif" in script


def test_render_apptainer_omits_nvidia_flag_for_cpu_task(tmp_path):
    job = SlurmJob("task-1", _make_task_type(gpus=False), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "apptainer run --nv" not in script
    assert "APPTAINERENV_CUDA_VISIBLE_DEVICES" not in script
    assert "apptainer run --containall --cleanenv --bind" in script


def test_render_apptainer_keeps_parameters_in_typed_json_env(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "-r 100" not in script
    assert "export APPTAINERENV_TASK_MANIFEST=" in script
    assert "-i '/mnt/revocompute/tester/inputs/task.json'" in script


def test_render_apptainer_ships_params_via_manifest(tmp_path):
    """APPTAINERENV_* forwarding collapses backslash runs (2, 4, and 8 all
    arrive as 1) — user-shaped data never travels through the environment.
    The wrapper exports only the backslash-free manifest path; params with
    backslashes live in the snapshot's task.json."""
    entities = _make_entities() + [
        {
            "name": "reaction_smiles",
            "type": "param",
            "value": "C=C(" + chr(92) + "C)",
            "verified_value": "C=C(" + chr(92) + "C)",
        }
    ]
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), entities, str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "export APPTAINERENV_TASK_MANIFEST=" in script
    assert "export APPTAINERENV_TASK_PARAMS=" not in script
    assert "export APPTAINERENV_TASK_PARAMS_FILE=" not in script
    assert "-i '/mnt/revocompute/tester/inputs/task.json'" in script
    # No param content (and no backslashes) anywhere in the wrapper.
    assert "reaction_smiles" not in script
    assert "C=C" not in script


def test_render_apptainer_passes_runtime_subcommand(tmp_path):
    task_type = _make_task_type(runner_args=("rfdiffusion",))
    job = SlurmJob("task-1", task_type, _make_runner(), _make_entities(), str(tmp_path / "out"))
    script = job._render_wrapper()
    assert "'/opt/images/gremlin_v1.sif' 'rfdiffusion' -i" in script


def test_render_apptainer_raises_without_sif_image(tmp_path):
    task_type = _make_task_type()
    task_type = replace(task_type, runtime=replace(task_type.runtime, slurm_image=""))
    job = SlurmJob("task-1", task_type, _make_runner(), _make_entities(), str(tmp_path / "out"))
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


def test_render_apptainer_quotes_paths_and_environment_values(tmp_path):
    from revocompute.task_types import RunnerMount

    entities = _make_entities()
    entities[0] = {
        **entities[0],
        "snapshot_path": "/srv/workspaces/alice's task/inputs/input file.fasta",
        "snapshot_root": "/srv/workspaces/alice's task/inputs",
        "workspace_key": "alice task",
    }
    task_type = _make_task_type(
        runtime=replace(_make_task_type().runtime, slurm_image="/opt/images/gremlin's image.sif")
    )
    runner = _make_runner(
        env={"GREMLIN_DB": "/data/db path/gremlin's db"},
        mounts=(
            RunnerMount(
                host_path="/data/db path/gremlin's db",
                container_path="/opt/db path/gremlin",
                mode="ro",
            ),
        ),
    )
    job = SlurmJob("task-1", task_type, runner, entities, str(tmp_path / "out dir"))
    script = job._render_wrapper()

    assert _sh_quote("/srv/workspaces/alice's task/inputs/input file.fasta") in script
    assert _sh_quote("/srv/workspaces/alice's task/inputs") in script
    assert _sh_quote("/data/db path/gremlin's db") in script
    assert _sh_quote("/opt/images/gremlin's image.sif") in script
    assert _sh_quote("/mnt/revocompute/alice task/inputs/task.json") in script


# -- submit / poll / cancel (mocked Popen boundary) ---------------------------


def test_submit_invokes_srun_with_resource_args_and_wrapper(tmp_path):
    output_dir = tmp_path / "out with spaces"
    resources = _policy(
        cpus=8,
        memory="32G",
        max_runtime_seconds=90 * 60,
        partition="gpu",
        gres="gpu:a100:1",
        nodes=2,
        ntasks=1,
        qos="normal",
        account="lab",
        constraint="a100&nvme",
        exclusive=True,
        requires_gpu=True,
    )
    job = SlurmJob(
        "abcdef1234567890",
        _make_task_type(gpus=True),
        _make_runner(),
        _make_entities(),
        str(output_dir),
        username="alice@example.com",
        resource_policy=resources,
    )
    fake_proc = _FakeSrunProcess(stdout="REVODESIGN_JOB_ID=4217\n", returncode=0, pid=99)

    with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
        jid = job.submit()

    wrapper = output_dir / "_slurm_wrapper_abcdef12.sh"
    assert jid == "4217"
    assert mock_popen.call_args.args[0] == [
        "srun",
        "-u",
        "--partition=gpu",
        "--cpus-per-task=8",
        "--gres=gpu:a100:1",
        "--mem=32G",
        "--time=01:30:00",
        "--nodes=2",
        "--ntasks=1",
        "--qos=normal",
        "--account=lab",
        "--constraint=a100&nvme",
        "--exclusive",
        f"--chdir={output_dir}",
        "--job-name=revocomput_alice_example_com_gremlin_abcdef12",
        "bash",
        str(wrapper),
    ]
    assert mock_popen.call_args.kwargs == {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True}
    assert wrapper.is_file()


def test_submit_parses_job_id_from_srun_stderr_banner(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    fake_proc = _FakeSrunProcess(stderr="srun: job 4217 queued and waiting for resources\n", returncode=0)

    with patch("subprocess.Popen", return_value=fake_proc):
        assert job.submit() == "4217"
    assert job.job_id == "4217"


def test_submit_rejects_unparseable_scheduler_id_and_terminates_srun(tmp_path):
    output_dir = tmp_path / "out"
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(output_dir))
    fake_proc = _FakeSrunProcess(
        stdout="tool started before SLURM_JOB_ID was exported\n", stderr="unexpected\n", returncode=None
    )

    with patch("subprocess.Popen", return_value=fake_proc):
        with pytest.raises(RuntimeError, match="did not return a scheduler job ID"):
            job.submit()
    assert job.job_id is None
    assert fake_proc.terminated is True
    assert not list(output_dir.glob("_slurm_wrapper_*.sh"))


def test_submit_propagates_srun_launch_failure_and_removes_wrapper(tmp_path):
    output_dir = tmp_path / "out"
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(output_dir))

    with patch("subprocess.Popen", side_effect=FileNotFoundError("srun not found")):
        with pytest.raises(FileNotFoundError, match="srun not found"):
            job.submit()

    assert not list(output_dir.glob("_slurm_wrapper_*.sh"))


def test_job_id_capture_emits_first_stage_as_liveness_signal(tmp_path):
    stages_seen = []
    job = SlurmJob(
        "task-1",
        _make_task_type(),
        _make_runner(),
        _make_entities(),
        str(tmp_path / "out"),
        stage_callback=stages_seen.append,
    )
    stdout = StringIO("REVODESIGN_JOB_ID=4154\n" "REVODESIGN_STAGE:gremlin\n")
    job._process = SimpleNamespace(stdout=stdout)

    job._read_stdout()

    assert job._slurm_job_id == "4154"
    assert job._job_id_event.is_set()
    assert stages_seen == ["hhblits", "gremlin"]
    assert stdout.closed


def test_submit_poll_lifecycle_maps_exit_zero_with_result_to_completed(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    fake_proc = _FakeSrunProcess(stdout="REVODESIGN_JOB_ID=4217\nREVODESIGN_STAGE:gremlin\n", returncode=0)

    with patch("subprocess.Popen", return_value=fake_proc):
        assert job.submit() == "4217"
        (tmp_path / "out" / "result.csv").write_text("score\n1.0\n")
        state = job.poll()
        assert state == JobState.COMPLETED
    assert not list((tmp_path / "out").glob("_slurm_wrapper_*.sh"))


def test_poll_returns_failed_on_exit_zero_without_result_artifact(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    fake_proc = _FakeSrunProcess(stdout="REVODESIGN_JOB_ID=4217\n", returncode=0)

    with patch("subprocess.Popen", return_value=fake_proc):
        job.submit()
        (tmp_path / "out" / "task_finished").touch()
        state = job.poll()
        assert state == JobState.FAILED


def test_poll_maps_nonzero_srun_exit_to_failed_and_saves_scheduler_logs(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"), username="bob")
    fake_proc = _FakeSrunProcess(
        stdout="REVODESIGN_JOB_ID=4217\n",
        stderr="slurmstepd: error: task exited with exit code 1\n",
        returncode=1,
    )

    with patch("subprocess.Popen", return_value=fake_proc):
        job.submit()
        assert job.poll() == JobState.FAILED

    stderr = tmp_path / "out" / "execution" / "slurm-bob-gremlin-task-1.stderr.log"
    assert stderr.read_text() == "slurmstepd: error: task exited with exit code 1\n"


def test_poll_timeout_kills_srun_and_returns_failed(tmp_path):
    job = SlurmJob(
        "task-1",
        _make_task_type(),
        _make_runner(max_runtime_seconds=1),
        _make_entities(),
        str(tmp_path / "out"),
    )
    fake_proc = _FakeSrunProcess(stdout="REVODESIGN_JOB_ID=4217\n", returncode=None, timeout_once=True)

    with patch("subprocess.Popen", return_value=fake_proc):
        job.submit()
        assert job.poll() == JobState.FAILED

    assert fake_proc.killed is True
    assert fake_proc.wait_calls == 2


def test_slurm_output_is_named_previewable_execution_diagnostics(tmp_path):
    job = SlurmJob(
        "task-1",
        _make_task_type(),
        _make_runner(),
        _make_entities(),
        str(tmp_path / "out"),
        username="alice",
    )
    job._job_id = "srun-32"
    job._stdout_lines = ["REVODESIGN_STAGE:proteinmpnn\n"]
    job._stderr_lines = ["warning\n"]

    job._save_output()

    stdout = tmp_path / "out" / "execution" / "slurm-alice-gremlin-task-1.stdout.log"
    stderr = tmp_path / "out" / "execution" / "slurm-alice-gremlin-task-1.stderr.log"
    assert stdout.read_text() == "REVODESIGN_STAGE:proteinmpnn\n"
    assert stderr.read_text() == "warning\n"
    assert job._is_execution_log(str(stdout))


def test_cancel_terminates_process(tmp_path):
    job = SlurmJob("task-1", _make_task_type(), _make_runner(), _make_entities(), str(tmp_path / "out"))
    fake_proc = _FakeSrunProcess(returncode=None, pid=99999)
    job._process = fake_proc
    job._job_id = "4217"

    job.cancel()

    assert fake_proc.terminated is True
    assert fake_proc.killed is False
    assert fake_proc.poll() == -15


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
