# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Runtime-family registry contract tests."""

from __future__ import annotations

import re
from contextlib import contextmanager
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
    category_snapshot = dict(task_types._category_registry)
    executor_snapshot = task_types._job_executor
    container_snapshot = task_types._container_runtime
    try:
        yield
    finally:
        task_types._registry.clear()
        task_types._registry.update(task_snapshot)
        task_types._runtime_registry.clear()
        task_types._runtime_registry.update(runtime_snapshot)
        task_types._category_registry.clear()
        task_types._category_registry.update(category_snapshot)
        task_types._job_executor = executor_snapshot
        task_types._container_runtime = container_snapshot


def test_every_task_declares_scientific_guidance_and_semantic_steps():
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))
    assert registry["categories"]
    assert len({category["order"] for category in registry["categories"].values()}) == len(registry["categories"])
    for name, task in registry["task_types"].items():
        for field in ("summary", "use_when", "input_summary", "output_summary"):
            assert isinstance(task[field], str) and task[field].strip(), (name, field)
        assert task["considerations"] and all(isinstance(item, str) and item.strip() for item in task["considerations"])
        steps = task["input_workspace"]["steps"]
        assert steps[0]["capabilities"][0]["plugin"] in {"files", "sequence"}
        assert steps[-1]["capabilities"][-1]["plugin"] == "review"


def test_task_types_carry_categories():
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))
    task_types = registry["task_types"]
    expected = {
        "gremlin": "evolution",
        "easifa": "function",
        "bioemu": "structure",
        "esm_if1": "inverse_folding",
        "pythia_ddg": "fitness",
        "ligandmpnn": "inverse_folding",
    }
    for name, category in expected.items():
        assert name in task_types, name
        assert task_types[name].get("category") == category, (name, task_types[name])


def test_shared_tasks_resolve_one_runtime_and_runner_config():
    enabled = {"esm", "mpnn", "placer-rfdiffusion"}
    with _preserve_registry():
        task_types.load_registry(
            str(SERVER_ROOT / "config" / "task_types.yaml"),
            str(SERVER_ROOT / "config" / "runners"),
            enabled,
        )
        assert task_types.get_job_executor() == "docker"
        assert task_types.get_container_runtime() == "docker"

        esm_tasks = [task_types.get(name) for name in ("esm_extract", "esm_1v", "esm_if1")]
        assert {tt.runtime.name for tt, _ in esm_tasks} == {"esm"}
        assert not hasattr(esm_tasks[0][0].runtime, "job_executor")
        assert not hasattr(esm_tasks[0][0].runtime, "container_runtime")
        assert len({id(runner) for _, runner in esm_tasks}) == 1
        assert esm_tasks[0][1].mounts[0].container_path == "/mnt/db/weights/esm"

        mpnn_tasks = [
            task_types.get(name)
            for name in (
                "hypermpnn",
                "proteinmpnn",
                "solublempnn",
                "ligandmpnn",
                "lasermpnn",
                "thermompnn",
            )
        ]
        assert {tt.runtime.name for tt, _ in mpnn_tasks} == {"mpnn"}
        assert len({id(runner) for _, runner in mpnn_tasks}) == 1

        placer, placer_runner = task_types.get("placer")
        rfdiffusion, rfdiffusion_runner = task_types.get("rfdiffusion")
        assert placer.runtime is rfdiffusion.runtime
        assert placer_runner is rfdiffusion_runner
        assert placer.runner_args == ("placer",)
        assert rfdiffusion.runner_args == ("rfdiffusion",)


def test_esmdynamic_resolves_its_gpu_runtime_and_shared_checkpoint_cache():
    with _preserve_registry():
        task_types.load_registry(
            str(SERVER_ROOT / "config" / "task_types.yaml"),
            str(SERVER_ROOT / "config" / "runners"),
            {"esmdynamic"},
        )
        task, runner = task_types.get("esmdynamic")

        assert task.runtime.name == "esmdynamic"
        assert task.gpus is True
        assert task.input_extensions == (".fasta",)
        assert [(mount.host_path, mount.container_path) for mount in runner.mounts] == [
            (
                "/mnt/db/weights/esm/checkpoints",
                "/mnt/db/weights/esm/hub/checkpoints",
            )
        ]


def test_alphafold_and_colabfold_declare_independent_workflows():
    with _preserve_registry():
        task_types.load_registry(
            str(SERVER_ROOT / "config" / "task_types.yaml"),
            str(SERVER_ROOT / "config" / "runners"),
            {"alphafold", "colabfold_af2"},
        )
        alphafold, _ = task_types.get("alphafold")
        colabfold, _ = task_types.get("colabfold_af2")

        assert [(stage.name, stage.requires_gpu) for stage in alphafold.workflow] == [
            ("alphafold.features", False),
            ("alphafold.model", True),
        ]
        assert alphafold.runtime.name == "alphafold"
        assert alphafold.workflow[0].runner_args == ("-s", "features")
        assert alphafold.workflow[1].runner_args == ("-s", "model")
        assert alphafold.workflow[0].requires_network is False
        assert alphafold.workflow[1].requires_network is False
        assert [(stage.name, stage.requires_gpu) for stage in colabfold.workflow] == [
            ("colabfold_af2.features", False),
            ("colabfold_af2.model", True),
        ]
        assert colabfold.runtime.name == "colabfold_af2"
        assert colabfold.workflow[0].requires_network is True
        assert colabfold.workflow[1].requires_network is False


def test_input_workspace_capabilities_cover_simple_and_complex_tasks():
    enabled = {"placer-rfdiffusion", "easifa"}
    with _preserve_registry():
        task_types.load_registry(
            str(SERVER_ROOT / "config" / "task_types.yaml"),
            str(SERVER_ROOT / "config" / "runners"),
            enabled,
        )
        gremlin, _ = task_types.get("gremlin")
        rfdiffusion, _ = task_types.get("rfdiffusion")
        easifa, _ = task_types.get("easifa")

        assert [cap.plugin for cap in task_types.iter_capabilities(gremlin)] == [
            "files",
            "sequence",
            "parameters",
            "review",
        ]
        assert [cap.plugin for cap in task_types.iter_capabilities(rfdiffusion)] == [
            "files",
            "structure",
            "rfdiffusion-regions",
            "parameters",
            "review",
        ]
        region_options = next(
            cap.options for cap in task_types.iter_capabilities(rfdiffusion) if cap.plugin == "rfdiffusion-regions"
        )
        assert {"design_mode", "contig", "hotspot_res"}.issubset(region_options["fields"])
        assert region_options["modes"] == ["unconditional", "motif_scaffolding", "binder", "expert"]
        assert rfdiffusion.min_input_files == 0
        assert easifa.result_workspace[0].plugin == "residue-table-structure"
        assert [cap.plugin for cap in task_types.iter_capabilities(easifa)] == [
            "files",
            "structure",
            "parameters",
            "review",
        ]


def test_input_workspace_rejects_remote_or_unknown_plugin_configuration(tmp_path):
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))
    registry["task_types"]["gremlin"]["input_workspace"] = {
        "steps": [
            {
                "id": "material",
                "title": "Input",
                "description": "",
                "capabilities": [{"plugin": "https://example.invalid/plugin.js", "id": "remote"}],
            },
            {
                "id": "review",
                "title": "Review",
                "description": "",
                "capabilities": [{"plugin": "review", "id": "review"}],
            },
        ]
    }
    registry_path = tmp_path / "task_types.yaml"
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")

    with _preserve_registry(), pytest.raises(ValueError, match="Unknown input workspace plugin"):
        task_types.load_registry(
            str(registry_path),
            str(SERVER_ROOT / "config" / "runners"),
            set(),
        )


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
    forbidden = {"runner", "job_executor", "container_runtime", "slurm_image", "gpus"}
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
        for raw in (SERVER_ROOT / "docker" / "runners" / "mpnn" / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if (line := raw.strip()) and not line.startswith("#")
    }
    assert not any(package.startswith("nvidia-") for package in requirements)
    assert requirements.isdisjoint({"triton", "torchvision", "torchaudio"})
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "Dockerfile").read_text(encoding="utf-8")
    assert '--no-deps "git+${THERMOREPO}@${THERMOREF}"' in dockerfile


def test_ligandmpnn_uses_the_pinned_upstream_cli_flags():
    run_script = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "run.sh").read_text(encoding="utf-8")

    ligand_case = run_script.split("  ligandmpnn)", 1)[1].split("    ;;", 1)[0]
    assert '--number_of_batches "${NUMBER_OF_BATCHES}"' in ligand_case
    assert '--temperature "${SAMPLING_TEMP}"' in ligand_case
    assert "--num_seq_per_target" not in ligand_case
    assert "--sampling_temp" not in ligand_case


def test_proteinmpnn_and_solublempnn_share_the_pinned_official_runtime():
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "Dockerfile").read_text(encoding="utf-8")
    run_script = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "run.sh").read_text(encoding="utf-8")
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))

    assert "MPNN_REPO=https://github.com/YaoYinYing/ProteinMPNN.git" in dockerfile
    assert "MPNN_REF=8907e6671bfbfc92303b5f79c4b5e6ce47cdef57" in dockerfile
    assert '[[ "${task_type}" == "solublempnn" ]] && protein_args+=(--use_soluble_model)' in run_script
    assert registry["task_types"]["proteinmpnn"]["runtime_family"] == "mpnn"
    assert registry["task_types"]["solublempnn"]["runtime_family"] == "mpnn"
    soluble_model = next(
        item for item in registry["task_types"]["solublempnn"]["params"] if item["name"] == "model_name"
    )
    assert soluble_model["choices"] == ["v_48_010", "v_48_020"]


def test_lasermpnn_uses_pinned_source_checkpoints_and_cpu_runtime():
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "Dockerfile").read_text(encoding="utf-8")
    run_script = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "run.sh").read_text(encoding="utf-8")
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))

    assert "LASERMPNN_REPO=https://github.com/YaoYinYing/LASErMPNN.git" in dockerfile
    assert "LASERMPNN_REF=5df210fced6764d83f01425d1fc4319a22b70c2a" in dockerfile
    assert "laser_weights_0p1A_nothing_heldout.pt" in run_script
    assert "laser_weights_0p1A_noise_ligandmpnn_split.pt" in run_script
    assert "--device cpu" in run_script
    assert "--ignore_key_mismatch" not in run_script
    assert 'item.get("path", "")' in run_script
    assert 'json.load(open(os.environ["TASK_MANIFEST"]))["files"]' in run_script
    assert "mktemp --suffix=.txt" in run_script
    task = registry["task_types"]["lasermpnn"]
    assert task["runtime_family"] == "mpnn"
    assert task["allow_multiple_inputs"] is True
    assert set(task["input_extensions"]) == {".pdb", ".cif", ".mmcif"}
    assert "protonated" in task["input_label"].lower()


def test_every_declared_submission_parameter_is_consumed_by_its_runtime_script():
    """Prevent the schema-driven form from advertising ignored scientific controls."""
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))
    for task_name, task in registry["task_types"].items():
        declared = {param["name"] for param in task.get("params", [])}
        if not declared:
            continue
        runtime = registry["runtime_families"][task["runtime_family"]]
        script = (SERVER_ROOT / Path(runtime["dockerfile"]).parent / "run.sh").read_text(encoding="utf-8")
        consumed = {
            name for name in declared if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", script)
        }
        assert consumed == declared, f"{task_name} exposes ignored parameters: {sorted(declared - consumed)}"


def test_prime_runtime_uses_pinned_ogt_model_contract():
    runtime_dir = SERVER_ROOT / "docker" / "runners" / "prime"
    dockerfile = (runtime_dir / "Dockerfile").read_text(encoding="utf-8")
    script = (runtime_dir / "run.sh").read_text(encoding="utf-8")

    assert "ProPrime_650M_OGT_Prediction-91490f95c707" in dockerfile
    assert "transformers==4.36.2" in dockerfile
    assert "outputs.predicted_values" in script
    assert "local_files_only=True" in script
    assert "AI4Protein/Prime_690M" not in script
    assert ".predict_ogt(" not in script


def test_prime_family_exposes_distinct_ogt_and_dms_contracts():
    with _preserve_registry():
        task_types.load_registry(
            str(SERVER_ROOT / "config" / "task_types.yaml"),
            str(SERVER_ROOT / "config" / "runners"),
            {"prime", "prime_dms"},
        )
        ogt, ogt_runner = task_types.get("prime")
        dms, dms_runner = task_types.get("prime_dms")
        assert ogt.runtime is dms.runtime
        assert ogt_runner is dms_runner
        assert ogt.runner_args == ("ogt",)
        assert dms.runner_args == ("dms",)
        assert dms.allow_multiple_inputs is True
        assert dms.max_input_files == 64
        assert set(dms.input_extensions) == {".fasta", ".fa", ".faa"}

    dockerfile = (SERVER_ROOT / "docker" / "runners" / "prime" / "Dockerfile").read_text(encoding="utf-8")
    script = (SERVER_ROOT / "docker" / "runners" / "prime" / "run.sh").read_text(encoding="utf-8")
    assert "Prime_690M-7b75010748d2" in dockerfile
    assert '"predict_score"' in script
    assert 'tuple("ACDEFGHIKLMNPQRSTVWY")' in script
    assert '"position": position' in script
    assert '"mutation_count": len(substitutions)' in script
    assert 'f"{input_fasta.stem}_prime_combinatorial.csv"' in script


def test_shared_placer_rfdiffusion_runtime_uses_audited_compatible_versions():
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "placer-rfdiffusion" / "Dockerfile").read_text(encoding="utf-8")
    for requirement in (
        "torch==2.3.1",
        "dgl==2.4.0",
        "e3nn/e3nn/archive/ef93f876c9985b3816aefb2982b3cf4325df6ba4.tar.gz",
        "networkx==3.4.2",
        "pandas==2.2.3",
        "opt_einsum==3.4.0",
    ):
        assert requirement in dockerfile
    assert "python3-openbabel" in dockerfile


def test_bioemu_runtime_pins_release_and_driver_compatible_torch_once():
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "bioemu" / "Dockerfile").read_text(encoding="utf-8")
    run_script = (SERVER_ROOT / "docker" / "runners" / "bioemu" / "run.sh").read_text(encoding="utf-8")
    runner = yaml.safe_load((SERVER_ROOT / "config" / "runners" / "bioemu.yaml").read_text(encoding="utf-8"))
    assert "python:3.11-slim" in dockerfile
    assert '"bioemu[cuda]==1.4.1"' in dockerfile
    assert '"torch==2.7.1"' in dockerfile
    assert '"jax[cuda12]==0.5.3"' in dockerfile
    assert "https://download.pytorch.org/whl/cu128" in dockerfile
    assert dockerfile.count('"torch==2.7.1"') == 1
    assert dockerfile.index('"torch==2.7.1"') < dockerfile.index('"bioemu[cuda]==1.4.1"')
    assert "--ckpt_path=" in run_script
    assert "--model_config_path=" in run_script
    assert "--model_name=None" in run_script
    assert "--cache_embeds_dir=" in run_script
    assert "--cache_so3_dir=" in run_script
    assert runner["mounts"][0]["host_path"] == "/mnt/db/weights/bioemu"
    assert runner["mounts"][0]["mode"] == "ro"


def test_easifa_runtime_uses_pinned_official_easifa2_single_prediction_contract():
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "easifa" / "Dockerfile").read_text(encoding="utf-8")
    run_script = (SERVER_ROOT / "docker" / "runners" / "easifa" / "run.sh").read_text(encoding="utf-8")
    assert "EASIFA_REF=146ed9ca6ccbc7458bd2d343ec2de0ce149c9aad" in dockerfile
    assert "EASIFA_REPO=https://github.com/wangxr0526/EasIFA2.0_Core.git" in dockerfile
    assert "EASIFA_METADATA_REF=f26aecd922a48d935315fe7d4f61381a388492af" in dockerfile
    assert "EASIFA_ENV_SHA256=da5751abd99297eaae813591a8b32a006d244d0d8ba376712223d83f24fe88f2" in dockerfile
    assert "libexpat1" in dockerfile
    assert "libxext6" in dockerfile
    assert "libxrender1" in dockerfile
    assert 'easifa-predict "${easifa_args[@]}"' in run_script
    assert "main_test.py" not in run_script
    assert "--checkpoint-dir" in run_script
    assert "--device cuda:0" in run_script
    assert "active_sites.csv" in run_script


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
            {"esm_extract"},
        )


def test_empty_registry_is_rejected(tmp_path):
    registry = tmp_path / "task_types.yaml"
    registry.write_text("{}\n", encoding="utf-8")
    with _preserve_registry(), pytest.raises(ValueError, match="Task registry is empty"):
        task_types.load_registry(str(registry), str(tmp_path), set())


@pytest.mark.parametrize(
    ("job_executor", "container_runtime", "slurm_image", "message"),
    [
        ("singularity", "apptainer", "/images/test.sif", "Unsupported global job_executor"),
        ("docker", "apptainer", "/images/test.sif", "requires container_runtime: docker"),
        ("slurm", "docker", "/images/test.sif", "requires container_runtime: apptainer"),
        ("slurm", "apptainer", "", "must declare slurm_image"),
    ],
)
def test_invalid_global_executor_contract_is_rejected(tmp_path, job_executor, container_runtime, slurm_image, message):
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
        "categories:\n"
        "  other: {label: Other, description: Other methods, order: 1}\n"
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
        "    input_label: FASTA\n" + task_fields,
        encoding="utf-8",
    )
    (tmp_path / "test.yaml").write_text("{}\n", encoding="utf-8")
    with _preserve_registry(), pytest.raises(ValueError, match=message):
        task_types.load_registry(str(registry), str(tmp_path), set())


def test_shared_runner_passes_full_snapshot_root_to_placer():
    script = (SERVER_ROOT / "docker" / "runners" / "placer-rfdiffusion" / "run.sh").read_text(encoding="utf-8")
    assert 'input_root="${input_file%%/inputs/*}/inputs"' in script
    assert 'placer_args=(-i "$input_root" -o "$output_dir" -n "$NUM_SAMPLES")' in script
    assert 'run_PLACER.py" "${placer_args[@]}"' in script


def test_shared_runner_gives_rfdiffusion_writable_runtime_directories():
    script = (SERVER_ROOT / "docker" / "runners" / "placer-rfdiffusion" / "run.sh").read_text(encoding="utf-8")
    assert '"hydra.run.dir=/tmp/rfdiffusion-hydra"' in script
    assert '"hydra.output_subdir=null"' in script
    assert '"inference.schedule_directory_path=/tmp/rfdiffusion-schedules"' in script
    assert '"inference.output_prefix=${output_dir}/design"' in script


def test_rfdiffusion_defaults_match_pinned_upstream_inference_config():
    registry = yaml.safe_load((SERVER_ROOT / "config" / "task_types.yaml").read_text(encoding="utf-8"))
    params = {param["name"]: param.get("default") for param in registry["task_types"]["rfdiffusion"]["params"]}

    # RosettaCommons/RFdiffusion@86507b6, config/inference/base.yaml.
    expected = {
        "num_designs": 10,
        "design_startnum": 0,
        "recenter": True,
        "radius": 10.0,
        "model_only_neighbors": False,
        "write_trajectory": True,
        "empty_cache_per_design": False,
        "cautious": True,
        "align_motif": True,
        "symmetric_self_cond": True,
        "final_step": 1,
        "deterministic": False,
        "cyclic": False,
        "cyc_chains": "a",
        "diffuser_T": 50,
        "diffuser_b_0": 0.01,
        "diffuser_b_T": 0.07,
        "diffuser_schedule_type": "linear",
        "noise_scale_ca": 1.0,
        "final_noise_scale_ca": 1.0,
        "ca_noise_schedule_type": "constant",
        "noise_scale_frame": 1.0,
        "final_noise_scale_frame": 1.0,
        "frame_noise_schedule_type": "constant",
        "guide_scale": 10.0,
        "guide_decay": "constant",
        "sidechain_input": False,
        "motif_sidechain_input": True,
    }
    assert {name: params[name] for name in expected} == expected

    # Empty UI strings are omitted by the runner and are Hydra-null equivalent.
    nullable = {
        "symmetry",
        "inpaint_seq",
        "inpaint_str",
        "inpaint_str_helix",
        "inpaint_str_strand",
        "inpaint_str_loop",
        "provide_seq",
        "length",
        "partial_T",
        "hotspot_res",
        "guiding_potentials",
        "substrate",
    }
    assert all(params[name] in (None, "") for name in nullable)


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
