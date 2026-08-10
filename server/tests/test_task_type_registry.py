# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Runtime-family registry contract tests."""

from __future__ import annotations

from contextlib import contextmanager
import re
from pathlib import Path

import pytest
import yaml
from revocompute import task_types
from revocompute.schemas import TaskSubmissionRequest

SERVER_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _preserve_registry():
    task_snapshot = dict(task_types._registry)
    runtime_snapshot = dict(task_types._runtime_registry)
    try:
        yield
    finally:
        task_types._registry.clear()
        task_types._registry.update(task_snapshot)
        task_types._runtime_registry.clear()
        task_types._runtime_registry.update(runtime_snapshot)


def test_shared_tasks_resolve_one_runtime_and_runner_config():
    enabled = {
        "esm_fold",
        "esm_extract",
        "esm_1v",
        "esm_if1",
        "hypermpnn",
        "ligandmpnn",
        "thermompnn",
        "placer",
        "rfdiffusion",
    }
    with _preserve_registry():
        task_types.load_registry(
            str(SERVER_ROOT / "config" / "task_types.yaml"),
            str(SERVER_ROOT / "config" / "runners"),
            enabled,
        )

        esm_tasks = [task_types.get(name) for name in ("esm_fold", "esm_extract", "esm_1v", "esm_if1")]
        assert {tt.runtime.name for tt, _ in esm_tasks} == {"esm"}
        assert len({id(runner) for _, runner in esm_tasks}) == 1
        assert esm_tasks[0][1].mounts[0].container_path == "/mnt/db/weights/esm"

        mpnn_tasks = [task_types.get(name) for name in ("hypermpnn", "ligandmpnn", "thermompnn")]
        assert {tt.runtime.name for tt, _ in mpnn_tasks} == {"mpnn"}
        assert len({id(runner) for _, runner in mpnn_tasks}) == 1

        placer, placer_runner = task_types.get("placer")
        rfdiffusion, rfdiffusion_runner = task_types.get("rfdiffusion")
        assert placer.runtime is rfdiffusion.runtime
        assert placer_runner is rfdiffusion_runner
        assert placer.runner_args == ("placer",)
        assert rfdiffusion.runner_args == ("rfdiffusion",)


def test_runtime_build_artifacts_match_declared_images():
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))
    for name, runtime in registry["runtime_families"].items():
        dockerfile = SERVER_ROOT / runtime["dockerfile"]
        definition = SERVER_ROOT / runtime["definition"]
        runner_config = SERVER_ROOT / "config" / "runners" / f"{name}.yaml"
        assert dockerfile.is_file(), name
        assert definition.is_file(), name
        assert runner_config.is_file(), name
        assert runtime["slurm_image"].endswith(".sif"), name
        assert f"From: {runtime['docker_image']}:latest" in definition.read_text(encoding="utf-8"), name


def test_executor_settings_are_global_not_runner_yaml_fields():
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))
    assert registry["job_executor"] in {"docker", "slurm"}
    assert registry["container_runtime"] in {"docker", "apptainer"}
    forbidden = {"runner", "job_executor", "container_runtime", "slurm_image"}
    for runner_config in (SERVER_ROOT / "config" / "runners").glob("*.yaml"):
        data = yaml.safe_load(runner_config.read_text(encoding="utf-8")) or {}
        assert forbidden.isdisjoint(data), runner_config


def test_git_runner_sources_are_commit_pinned_and_clone_metadata_is_removed_in_layer():
    for dockerfile in (SERVER_ROOT / "docker" / "runners").glob("*/Dockerfile"):
        text = dockerfile.read_text(encoding="utf-8")
        for reference in re.findall(r"^ARG [A-Z0-9_]+_REF=(.+)$", text, flags=re.MULTILINE):
            assert re.fullmatch(r"[0-9a-f]{40}", reference), dockerfile
        if "git init /opt/" in text:
            assert "rm -rf /opt/" in text, dockerfile


def test_mpnn_cpu_runtime_omits_inference_unused_gpu_and_media_wheels():
    requirements = {
        line.split("==", 1)[0].lower()
        for raw in (SERVER_ROOT / "docker" / "runners" / "mpnn" / "requirements.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    }
    assert not any(package.startswith("nvidia-") for package in requirements)
    assert requirements.isdisjoint({"triton", "torchvision", "torchaudio"})
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "Dockerfile").read_text(encoding="utf-8")
    assert '--no-deps "git+${THERMOREPO}@${THERMOREF}"' in dockerfile


def test_shared_placer_rfdiffusion_runtime_uses_audited_compatible_versions():
    dockerfile = (
        SERVER_ROOT / "docker" / "runners" / "placer-rfdiffusion" / "Dockerfile"
    ).read_text(encoding="utf-8")
    for requirement in (
        "torch==2.3.1",
        "dgl==2.4.0",
        "e3nn==0.5.4",
        "networkx==3.4.2",
        "pandas==2.2.3",
        "opt_einsum==3.4.0",
    ):
        assert requirement in dockerfile
    assert "python3-openbabel" in dockerfile


def test_multi_file_task_contract_is_bounded():
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))
    for name in ("rfdiffusion", "placer"):
        task = registry["task_types"][name]
        assert task["allow_multiple_inputs"] is True
        assert 1 < task["max_input_files"] <= 64
        assert task["input_extension"] in task["input_extensions"]
        assert set(task.get("primary_input_extensions", [task["input_extension"]])) <= set(task["input_extensions"])


def test_enabled_runtime_requires_family_runner_config(tmp_path):
    with _preserve_registry(), pytest.raises(FileNotFoundError, match="requires runner configuration"):
        task_types.load_registry(
            str(SERVER_ROOT / "config" / "task_types.yaml"),
            str(tmp_path),
            {"esm_fold"},
        )


@pytest.mark.parametrize(
    ("job_executor", "container_runtime", "slurm_image", "message"),
    [
        ("singularity", "apptainer", "/images/test.sif", "Unsupported global job_executor"),
        ("docker", "apptainer", "/images/test.sif", "requires container_runtime: docker"),
        ("slurm", "docker", "/images/test.sif", "requires container_runtime: apptainer"),
        ("slurm", "apptainer", "", "must declare slurm_image"),
    ],
)
def test_invalid_global_executor_contract_is_rejected(
    tmp_path, job_executor, container_runtime, slurm_image, message
):
    registry = tmp_path / "task_types.yaml"
    registry.write_text(
        f"job_executor: {job_executor}\n"
        f"container_runtime: {container_runtime}\n"
        "runtime_families:\n"
        "  test:\n"
        "    docker_image: example/test\n"
        "    entrypoint: [run]\n"
        "    dockerfile: Dockerfile\n"
        "    definition: test.def\n"
        f"    slurm_image: {slurm_image}\n"
        "task_types:\n"
        "  gremlin:\n"
        "    display_name: GREMLIN\n"
        "    runtime_family: test\n"
        "    input_extension: .fasta\n"
        "    input_label: FASTA\n",
        encoding="utf-8",
    )
    (tmp_path / "test.yaml").write_text("{}\n", encoding="utf-8")
    with _preserve_registry(), pytest.raises(ValueError, match=message):
        task_types.load_registry(str(registry), str(tmp_path), set())


def test_unknown_runtime_family_is_rejected(tmp_path):
    registry = tmp_path / "task_types.yaml"
    registry.write_text(
        "job_executor: docker\n"
        "container_runtime: docker\n"
        "runtime_families: {}\n"
        "task_types:\n"
        "  gremlin:\n"
        "    display_name: GREMLIN\n"
        "    runtime_family: missing\n"
        "    input_extension: .fasta\n"
        "    input_label: FASTA\n",
        encoding="utf-8",
    )
    with _preserve_registry(), pytest.raises(ValueError, match="unknown runtime family"):
        task_types.load_registry(str(registry), str(tmp_path), set())


@pytest.mark.parametrize(
    ("task_fields", "message"),
    [
        ("    input_extensions: []\n", "at least one input extension"),
        (
            "    input_extensions: [.fasta]\n    primary_input_extensions: [.pdb]\n",
            "primary input extensions",
        ),
        ("    max_input_files: 0\n", "positive integer"),
        ("    max_input_files: 2\n", "multiple inputs are disabled"),
    ],
)
def test_invalid_input_contract_is_rejected(tmp_path, task_fields, message):
    registry = tmp_path / "task_types.yaml"
    registry.write_text(
        "job_executor: docker\n"
        "container_runtime: docker\n"
        "runtime_families:\n"
        "  test:\n"
        "    docker_image: example/test\n"
        "    entrypoint: [run]\n"
        "    dockerfile: Dockerfile\n"
        "    definition: test.def\n"
        "    slurm_image: /images/test.sif\n"
        "task_types:\n"
        "  gremlin:\n"
        "    display_name: GREMLIN\n"
        "    runtime_family: test\n"
        "    input_extension: .fasta\n"
        "    input_label: FASTA\n"
        + task_fields,
        encoding="utf-8",
    )
    (tmp_path / "test.yaml").write_text("{}\n", encoding="utf-8")
    with _preserve_registry(), pytest.raises(ValueError, match=message):
        task_types.load_registry(str(registry), str(tmp_path), set())


def test_shared_runner_passes_full_snapshot_root_to_placer():
    script = (SERVER_ROOT / "docker" / "runners" / "placer-rfdiffusion" / "run.sh").read_text(
        encoding="utf-8"
    )
    assert 'input_root="${input_file%%/inputs/*}/inputs"' in script
    assert 'run_PLACER.py" -i "$input_root"' in script


def test_submission_resolves_defaults_and_constraints():
    runtime = task_types.RuntimeFamily(
        name="test",
        docker_image="test:latest",
        entrypoint=("bash", "run.sh"),
        dockerfile="docker/test/Dockerfile",
        definition="docker/test/test.def",
    )
    task = task_types.TaskType(
        name="test",
        display_name="Test",
        runtime=runtime,
        input_extension=".fasta",
        input_label="FASTA",
        params=(
            task_types.TaskParam(name="count", type="int", default=4, minimum=1, maximum=8),
            task_types.TaskParam(name="mode", choices=("fast", "careful"), default="fast"),
            task_types.TaskParam(name="enabled", type="bool", default=True),
        ),
    )
    with _preserve_registry():
        task_types.register(task, task_types.RunnerConfig(defaults={"count": 6}))
        submission = TaskSubmissionRequest.model_validate({"task_type": "test", "params": {"mode": "careful"}})
        assert submission.coerce_params() == {"count": 6, "mode": "careful", "enabled": True}

        with pytest.raises(ValueError, match="at most 8"):
            TaskSubmissionRequest.model_validate({"task_type": "test", "params": {"count": 9}})
        with pytest.raises(ValueError, match="valid bool"):
            TaskSubmissionRequest.model_validate({"task_type": "test", "params": {"enabled": "maybe"}})
