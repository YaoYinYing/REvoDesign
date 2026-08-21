# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

RUNNER_SCRIPT = Path(__file__).resolve().parents[1] / "docker" / "runners" / "pssm_gremlin" / "run.sh"
OPENDDE_RUNNER_SCRIPT = Path(__file__).resolve().parents[1] / "docker" / "runners" / "opendde" / "run.sh"
MPNN_RUNNER_SCRIPT = Path(__file__).resolve().parents[1] / "docker" / "runners" / "mpnn" / "run.sh"
ALPHAFOLD_RUNNER_SCRIPT = Path(__file__).resolve().parents[1] / "docker" / "runners" / "alphafold" / "run.sh"
ESMDYNAMIC_RUNNER_SCRIPT = Path(__file__).resolve().parents[1] / "docker" / "runners" / "esmdynamic" / "run.sh"
SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_prepared_activation_audits_resources_before_stopping_services():
    steps_source = (SERVER_ROOT / "run" / "revocompute_ctl" / "steps.py").read_text(encoding="utf-8")
    preflight = steps_source.split("def _prepared_preflight", 1)[1].split("\ndef ", 1)[0]
    assert "validate_resource_policies" in preflight
    assert "--no-deps --entrypoint python worker" in steps_source
    assert "-m revocompute.resource_audit" in steps_source


def test_slurm_pre_stop_sweep_preserves_pending_and_resumable_workflows():
    sweep = (SERVER_ROOT / "run" / "revocompute_ctl" / "sweep.py").read_text(encoding="utf-8")
    down = (SERVER_ROOT / "run" / "revocompute_ctl" / "steps.py").read_text(encoding="utf-8")

    assert "squeue" not in sweep
    assert 'task.get("slurm_job_id")' in sweep
    assert 'task.get("status") in {"queued", "running"}' in sweep
    assert '"scancel"' in sweep
    assert 'if task.get("status") in {"queued", "running"}:' in sweep
    assert '"pending"' not in sweep
    assert "_record_failure" in sweep and "task_store" in sweep
    assert "_record_failure(" in sweep
    assert 'status="queued"' in sweep
    assert 'json.loads(task.get("workflow_state") or "{}")' in sweep
    assert 'getattr(_get_task_type(task_type)[0], "workflow", ())' in sweep
    assert "pre_stop_sweep_slurm" in down


def test_runner_script_does_not_eval_user_controlled_commands():
    script = RUNNER_SCRIPT.read_text()

    assert 'eval "$cmd"' not in script
    assert "eval $cmd" not in script
    assert "bash -c" not in script
    assert "sh -c" not in script


def test_runner_script_executes_pipeline_commands_as_arrays():
    script = RUNNER_SCRIPT.read_text()

    for command in ("hhblits", "hhfilter", "GREMLIN_TFv1.py", "psiblast"):
        assert command in script

    assert '"${cmd[@]}"' in script


def _run_with_manifest(script, input_file, output_dir, env, params=None, extra_args=()):
    """Run a runner script under the v2 protocol: write task.json next to
    the input, point -i at it, and set TASK_MANIFEST + TASK_CONTEXT_SRC."""
    manifest_path = input_file.parent / "task.json"
    manifest_path.write_text(
        json.dumps(
            {
                "task_id": "testtask",
                "task_type": "test",
                "params": params or {},
                "files": [
                    {
                        "name": "primary",
                        "path": str(input_file),
                        "relative_path": input_file.name,
                        "hash": "abc",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    env["TASK_MANIFEST"] = str(manifest_path)
    env.setdefault(
        "TASK_CONTEXT_SRC",
        str(SERVER_ROOT / "docker" / "runners" / "common" / "task_context.sh"),
    )
    return subprocess.run(
        ["bash", str(script), *extra_args, "-i", str(manifest_path), "-o", str(output_dir)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_esmdynamic_runner_uses_the_manifest_parameters(tmp_path):
    input_file = tmp_path / "input.fasta"
    output_dir = tmp_path / "outputs"
    bin_dir = tmp_path / "bin"
    args_file = tmp_path / "esmdynamic.args"
    input_file.write_text(">test\nACDE\n", encoding="utf-8")
    bin_dir.mkdir()
    runner = bin_dir / "run_esmdynamic"
    runner.write_text(
        "#!/bin/bash\n"
        'printf \'%s\\n\' "$@" > "$ESMDYNAMIC_ARGS_FILE"\n'
        'for arg in "$@"; do [[ $previous == output_dir ]] && output_dir=$arg; previous=${arg#--}; done\n'
        'mkdir -p "$output_dir"\n'
        'printf result > "$output_dir/result.txt"\n',
        encoding="utf-8",
    )
    runner.chmod(0o755)
    env = os.environ.copy()
    env.update({"PATH": f"{bin_dir}:{env['PATH']}", "ESMDYNAMIC_ARGS_FILE": str(args_file)})
    completed = _run_with_manifest(
        ESMDYNAMIC_RUNNER_SCRIPT,
        input_file,
        output_dir,
        env,
        params={"batch_size": 2, "chunk_size": 128, "low_memory": True, "num_recycles": 3},
    )

    assert completed.returncode == 0, completed.stderr
    args = args_file.read_text(encoding="utf-8")
    assert "--batch_size\n2\n" in args
    assert "--chunk_size\n128\n" in args
    assert "--low_memory" in args
    assert "--num_recycles\n3\n" in args
    assert (output_dir / "task_finished").is_file()


def test_alphafold_runner_drains_final_stage_before_exit(tmp_path):
    input_file = tmp_path / "input.fasta"
    output_dir = tmp_path / "outputs"
    alphafold_root = tmp_path / "alphafold"
    fake_context = tmp_path / "task_context.sh"
    fake_python = tmp_path / "fake-python"
    delayed_translator = tmp_path / "delayed-stage.awk"
    patterns = tmp_path / "alphafold.stages"
    input_file.write_text(">test\nAAAA\n", encoding="utf-8")
    output_dir.mkdir()
    alphafold_root.mkdir()
    fake_context.write_text(
        '_parse_param() { printf "%s\\n" "$2"; }\n' 'primary_input() { printf "%s\\n" "$FAKE_PRIMARY_INPUT"; }\n',
        encoding="utf-8",
    )
    fake_python.write_text(
        "#!/bin/bash\n"
        "set -e\n"
        'for arg in "$@"; do case "$arg" in --output_dir=*) output_dir=${arg#*=} ;; esac; done\n'
        'printf "Running model model_1\\n" >&2\n'
        'mkdir -p "$output_dir/model"\n'
        'printf "MODEL\\n" > "$output_dir/model/ranked_0.pdb"\n',
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    delayed_translator.write_text(
        '{ print > "/dev/stderr"; system("sleep 0.2"); print "REVODESIGN_STAGE:modeling"; fflush() }\n',
        encoding="utf-8",
    )
    patterns.write_text("modeling:Running model model_\n", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "ALPHAFOLD_PATH": str(alphafold_root),
            "ALPHAFOLD_PYTHON": str(fake_python),
            "ALPHAFOLD_STAGE_TRANSLATOR": str(delayed_translator),
            "ALPHAFOLD_STAGE_PATTERNS": str(patterns),
            "FAKE_PRIMARY_INPUT": str(input_file),
            "TASK_CONTEXT_SRC": str(fake_context),
            "TMPDIR": str(tmp_path),
        }
    )
    completed = _run_with_manifest(ALPHAFOLD_RUNNER_SCRIPT, input_file, output_dir, env)

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.index("REVODESIGN_STAGE:modeling") < completed.stdout.index("AlphaFold complete.")
    assert (output_dir / "task_finished").is_file()


def test_alphafold_feature_stage_stops_before_modeling(tmp_path):
    input_file = tmp_path / "input.fasta"
    output_dir = tmp_path / "outputs"
    alphafold_root = tmp_path / "alphafold"
    fake_context = tmp_path / "task_context.sh"
    fake_python = tmp_path / "fake-python"
    fake_args = tmp_path / "alphafold.args"
    input_file.write_text(">first\nAAAA\n>second\nBBBB\n", encoding="utf-8")
    output_dir.mkdir()
    alphafold_root.mkdir()
    fake_context.write_text(
        '_parse_param() { [[ "$1" == model_preset ]] && printf "multimer\\n" || printf "%s\\n" "$2"; }\n'
        'primary_input() { printf "%s\\n" "$FAKE_PRIMARY_INPUT"; }\n',
        encoding="utf-8",
    )
    fake_python.write_text(
        "#!/bin/bash\n"
        "set -e\n"
        'printf "%s\\n" "$@" > "$FAKE_ARGS_FILE"\n'
        'for arg in "$@"; do\n'
        '  case "$arg" in --output_dir=*) output_dir=${arg#*=} ;; --run_stage=*) stage=${arg#*=} ;; esac\n'
        "done\n"
        '[[ "$stage" == features ]]\n'
        'mkdir -p "$output_dir/input"\n'
        'printf "FEATURES\\n" > "$output_dir/input/features.pkl"\n',
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "ALPHAFOLD_PATH": str(alphafold_root),
            "ALPHAFOLD_PYTHON": str(fake_python),
            "FAKE_ARGS_FILE": str(fake_args),
            "FAKE_PRIMARY_INPUT": str(input_file),
            "TASK_CONTEXT_SRC": str(fake_context),
            "ALPHAFOLD_STAGE_TRANSLATOR": str(SERVER_ROOT / "docker" / "runners" / "common" / "stage_translate.py"),
            "ALPHAFOLD_STAGE_PATTERNS": str(SERVER_ROOT / "docker" / "runners" / "alphafold" / "alphafold.stages"),
            "TMPDIR": str(tmp_path),
        }
    )

    completed = _run_with_manifest(
        ALPHAFOLD_RUNNER_SCRIPT,
        input_file,
        output_dir,
        env,
        params={"model_preset": "multimer"},
        extra_args=("-s", "features"),
    )

    assert completed.returncode == 0, completed.stderr
    args = fake_args.read_text(encoding="utf-8")
    assert "--model_preset=multimer" in args
    assert "--uniref30_database_path=" in args
    assert "--uniprot_database_path=" in args
    assert "--pdb70_database_path=" not in args
    assert (output_dir / ".alphafold-features-complete").is_file()
    assert not (output_dir / "task_finished").exists()


def test_alphafold_image_applies_staged_pipeline_to_pinned_source():
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "alphafold" / "Dockerfile").read_text()
    patch = (SERVER_ROOT / "docker" / "runners" / "alphafold" / "staged_pipeline.patch").read_text()
    assert "git -C /opt/alphafold apply --check /tmp/staged_pipeline.patch" in dockerfile
    assert "FLAGS.run_stage == 'model'" in patch
    assert "FLAGS.run_stage == 'features'" in patch
    assert '"openmm-cuda-12==8.2.0"' in dockerfile
    assert '"nvidia-cuda-nvrtc-cu12==12.6.85"' in dockerfile


def test_alphafold_runner_uses_cuda_amber_relaxation_for_model_stage():
    script = ALPHAFOLD_RUNNER_SCRIPT.read_text(encoding="utf-8")

    assert "use_gpu_relax=true" in script
    assert '[[ "$run_stage" == features ]] && use_gpu_relax=false' in script
    assert '"--use_gpu_relax=${use_gpu_relax}"' in script


def test_opendde_runner_uses_writable_snapshot_copy_and_checks_outputs():
    script = OPENDDE_RUNNER_SCRIPT.read_text()

    assert 'mktemp -d "${TMPDIR:-/tmp}/revodesign-opendde.XXXXXX"' in script
    assert 'cp -a -- "$input_root"/. "$opendde_input_root"/' in script
    assert '-i "$writable_input_file"' in script
    assert 'find "$output_dir/ERR" -type f -size +0c' in script
    assert "-iname '*.pdb' -o -iname '*.cif' -o -iname '*.mmcif'" in script
    assert "--trimul_kernel torch" in script
    assert "--triatt_kernel torch" in script
    assert "--enable_fusion false" in script
    assert script.index('find "$output_dir"') < script.index('touch "${output_dir}/task_finished"')


def _write_fake_opendde(bin_dir: Path) -> None:
    executable = bin_dir / "opendde"
    executable.write_text(
        """#!/bin/bash
set -euo pipefail
[[ "$1" == "pred" ]]
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        -i) input_file=$2; shift 2 ;;
        -o) output_dir=$2; shift 2 ;;
        *) shift ;;
    esac
done
snapshot_root=${input_file%/structures/job.json}
test -f "$snapshot_root/config/settings.json"
printf '{}\n' > "${input_file%.json}-update-msa.json"
if [[ "${FAKE_OPENDDE_CHECK_RUNTIME_ROOT:-no}" == "yes" ]]; then
    test -f "$OPENDDE_ROOT_DIR/checkpoint/opendde.pt"
    printf 'downloaded template\n' > "$OPENDDE_ROOT_DIR/search_database/mmcif/fetched.cif"
fi
if [[ "${FAKE_OPENDDE_RESULT:-yes}" == "yes" ]]; then
    printf 'data_model\n' > "$output_dir/model.cif"
elif [[ "${FAKE_OPENDDE_RESULT:-yes}" == "error" ]]; then
    mkdir -p "$output_dir/ERR" "$output_dir/job/msa"
    printf 'internal failure\n' > "$output_dir/ERR/error.txt"
    printf '>query\nAAAA\n' > "$output_dir/job/msa/intermediate.a3m"
fi
"""
    )
    executable.chmod(0o755)


def test_opendde_runner_preserves_read_only_nested_snapshot(tmp_path):
    input_root = tmp_path / "workspace" / "inputs"
    input_file = input_root / "structures" / "job.json"
    auxiliary = input_root / "config" / "settings.json"
    output_dir = tmp_path / "outputs"
    bin_dir = tmp_path / "bin"
    input_file.parent.mkdir(parents=True)
    auxiliary.parent.mkdir(parents=True)
    output_dir.mkdir()
    bin_dir.mkdir()
    input_file.write_text("{}\n")
    auxiliary.write_text("{}\n")
    _write_fake_opendde(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    completed = _run_with_manifest(OPENDDE_RUNNER_SCRIPT, input_file, output_dir, env)

    assert completed.returncode == 0, completed.stderr
    assert (output_dir / "model.cif").read_text() == "data_model\n"
    assert (output_dir / "task_finished").is_file()
    assert not (input_file.parent / "job-update-msa.json").exists()
    assert auxiliary.read_text() == "{}\n"


def test_opendde_runner_uses_task_private_template_cache(tmp_path):
    input_root = tmp_path / "workspace" / "inputs"
    input_file = input_root / "structures" / "job.json"
    auxiliary = input_root / "config" / "settings.json"
    output_dir = tmp_path / "outputs"
    bin_dir = tmp_path / "bin"
    database_root = tmp_path / "database"
    source_cache = database_root / "search_database" / "mmcif"
    input_file.parent.mkdir(parents=True)
    auxiliary.parent.mkdir(parents=True)
    output_dir.mkdir()
    bin_dir.mkdir()
    source_cache.mkdir(parents=True)
    (database_root / "checkpoint").mkdir()
    (database_root / "checkpoint" / "opendde.pt").write_text("checkpoint\n")
    input_file.write_text("{}\n")
    auxiliary.write_text("{}\n")
    _write_fake_opendde(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["OPENDDE_ROOT_DIR"] = str(database_root)
    env["FAKE_OPENDDE_CHECK_RUNTIME_ROOT"] = "yes"
    completed = _run_with_manifest(OPENDDE_RUNNER_SCRIPT, input_file, output_dir, env)

    assert completed.returncode == 0, completed.stderr
    assert not (source_cache / "fetched.cif").exists()
    assert (output_dir / "model.cif").is_file()


def test_opendde_runner_rejects_zero_exit_without_results(tmp_path):
    input_root = tmp_path / "workspace" / "inputs"
    input_file = input_root / "structures" / "job.json"
    auxiliary = input_root / "config" / "settings.json"
    output_dir = tmp_path / "outputs"
    bin_dir = tmp_path / "bin"
    input_file.parent.mkdir(parents=True)
    auxiliary.parent.mkdir(parents=True)
    output_dir.mkdir()
    bin_dir.mkdir()
    input_file.write_text("{}\n")
    auxiliary.write_text("{}\n")
    _write_fake_opendde(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_OPENDDE_RESULT"] = "no"
    completed = _run_with_manifest(OPENDDE_RUNNER_SCRIPT, input_file, output_dir, env)

    assert completed.returncode != 0
    assert "without producing a structure artifact" in completed.stderr
    assert not (output_dir / "task_finished").exists()


def test_opendde_runner_rejects_error_and_msa_intermediates(tmp_path):
    input_root = tmp_path / "workspace" / "inputs"
    input_file = input_root / "structures" / "job.json"
    auxiliary = input_root / "config" / "settings.json"
    output_dir = tmp_path / "outputs"
    bin_dir = tmp_path / "bin"
    input_file.parent.mkdir(parents=True)
    auxiliary.parent.mkdir(parents=True)
    output_dir.mkdir()
    bin_dir.mkdir()
    input_file.write_text("{}\n")
    auxiliary.write_text("{}\n")
    _write_fake_opendde(bin_dir)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["FAKE_OPENDDE_RESULT"] = "error"
    completed = _run_with_manifest(OPENDDE_RUNNER_SCRIPT, input_file, output_dir, env)

    assert completed.returncode != 0
    assert "reported an internal inference error" in completed.stderr
    assert not (output_dir / "task_finished").exists()


def test_ligandmpnn_runner_omits_blank_optional_cli_values(tmp_path):
    input_file = tmp_path / "input.pdb"
    output_dir = tmp_path / "outputs"
    ligand_root = tmp_path / "LigandMPNN"
    capture = tmp_path / "argv.json"
    input_file.write_text("ATOM\n", encoding="utf-8")
    output_dir.mkdir()
    ligand_root.mkdir()
    (ligand_root / "model_params").mkdir()
    (ligand_root / "model_params" / "ligandmpnn_v_32_010_25.pt").write_bytes(b"checkpoint")
    (ligand_root / "run.py").write_text(
        "import json, os, sys\n"
        "open(os.environ['CAPTURE_ARGV'], 'w', encoding='utf-8').write(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "TASK_TYPE": "ligandmpnn",
            "LIGANDMPNN_PATH": str(ligand_root),
            "CAPTURE_ARGV": str(capture),
        }
    )
    completed = _run_with_manifest(
        MPNN_RUNNER_SCRIPT,
        input_file,
        output_dir,
        env,
        params={"seed": "", "batch_size": 2, "verbose": 0, "chains_to_design": ""},
    )

    assert completed.returncode == 0, completed.stderr
    argv = json.loads(capture.read_text(encoding="utf-8"))
    assert "--seed" not in argv
    assert "--chains_to_design" not in argv
    assert argv[argv.index("--batch_size") + 1] == "2"
    assert argv[argv.index("--verbose") + 1] == "0"
    assert (output_dir / "task_finished").is_file()


def test_final_docker_images_clear_build_proxy_environment():
    dockerfiles = [SERVER_ROOT / "docker" / "server" / "Dockerfile"]
    dockerfiles.extend(sorted((SERVER_ROOT / "docker" / "runners").glob("*/Dockerfile")))
    expected = (
        'ENV HTTP_PROXY="" HTTPS_PROXY="" ALL_PROXY="" \\\n'
        '    http_proxy="" https_proxy="" all_proxy="" NO_PROXY="" no_proxy=""'
    )

    assert dockerfiles
    for dockerfile in dockerfiles:
        final_stage = dockerfile.read_text().rsplit("\nFROM ", 1)[-1]
        assert expected in final_stage, dockerfile
        assert final_stage.rfind("RUN ") < final_stage.index(expected), dockerfile


def test_esm_image_installs_the_esm1v_csv_dependency():
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "esm" / "Dockerfile").read_text()

    assert '"pandas==2.2.3"' in dockerfile
    assert '"scipy==1.12.0"' in dockerfile
    assert '"torch-geometric==2.5.3"' in dockerfile
    assert '"biotite==0.41.0"' in dockerfile
    assert 'python -c "import esm2, esm2.inverse_folding, pandas"' in dockerfile


def test_easifa_image_requires_the_installed_prediction_cli():
    dockerfile = (SERVER_ROOT / "docker" / "runners" / "easifa" / "Dockerfile").read_text()

    assert "/opt/easifa-env/bin/python -m pip install" in dockerfile
    assert '/opt/easifa-env/bin/python -c "import easifa_core"' in dockerfile
    assert "test -x /opt/easifa-env/bin/easifa-predict" in dockerfile
    assert 'cpp_extension.load("torch_ext"' in dockerfile
    assert "import torch_ext" in dockerfile
    assert "RUN ! command -v c++" in dockerfile


def test_easifa_runner_reuses_the_read_only_esm_checkpoint_cache():
    runner = (SERVER_ROOT / "config" / "runners" / "easifa.yaml").read_text()

    assert 'host_path: "/mnt/db/weights/esm/checkpoints"' in runner
    assert 'container_path: "/home/revodesign/.cache/torch/hub/checkpoints"' in runner
    assert 'HOME: "/home/revodesign"' not in runner


def test_easifa_runner_uses_private_runtime_caches():
    script = (SERVER_ROOT / "docker" / "runners" / "easifa" / "run.sh").read_text()

    assert 'mktemp -d "${runtime_tmp%/}/revodesign-easifa.XXXXXX"' in script
    assert 'export TORCH_EXTENSIONS_DIR="$easifa_tmp/torch-extensions"' in script
    assert 'export MPLCONFIGDIR="$easifa_tmp/matplotlib"' in script


def test_thermompnn_uses_preprovisioned_read_only_weights():
    runner = (SERVER_ROOT / "config" / "runners" / "mpnn.yaml").read_text()
    script = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "run.sh").read_text()

    assert 'host_path: "/mnt/db/weights/thermompnn"' in runner
    assert 'container_path: "/mnt/db/weights/thermompnn"' in runner
    assert 'container_path: "/app/revocompute/model_params"' in runner
    assert 'LIGANDMPNN_MODEL_PARAMS: "/app/revocompute/model_params"' in runner
    assert 'mode: "ro"' in runner
    assert 'XDG_DATA_HOME: "/mnt/db/weights/thermompnn"' in runner
    assert "ThermoMPNN-ens1.ckpt ThermoMPNN-D-ens1.ckpt" in script
    assert (
        "THERMOMPNN_VANILLA_WEIGHT_DIR: " '"/mnt/db/weights/thermompnn/ProteinMPNN/vanilla/vanilla_model_weights"'
    ) in runner
    assert "ThermoMPNN ProteinMPNN backbone checkpoint is missing" in script
    assert "runtime downloads are disabled" in script


def test_ligandmpnn_runner_uses_a_mounted_absolute_checkpoint():
    script = (SERVER_ROOT / "docker" / "runners" / "mpnn" / "run.sh").read_text()

    assert "checkpoint_ligand_mpnn" in script
    assert "ligandmpnn_v_32_010_25.pt" in script
    assert "LIGANDMPNN_MODEL_PARAMS" in script


def test_slurm_runner_limits_threaded_libraries_to_the_allocation():
    script = (SERVER_ROOT / "revocompute" / "job" / "runners" / "slurm_runner.py").read_text()

    assert "SLURM_CPUS_PER_TASK" in script
    assert "APPTAINERENV_OMP_NUM_THREADS" in script
    assert "APPTAINERENV_MKL_NUM_THREADS" in script
    assert "APPTAINERENV_OPENBLAS_NUM_THREADS" in script
    assert "APPTAINERENV_NPROC" in script
    assert "APPTAINERENV_GREMLIN_CALC_CPU_NUM" in script
    assert "APPTAINERENV_VECLIB_MAXIMUM_THREADS" in script
    assert "APPTAINERENV_TF_NUM_INTRAOP_THREADS" in script
    assert "cmd += ' -j \"${allocated_cpus}\"'" in script


PRIME_DIR = SERVER_ROOT / "docker" / "runners" / "prime"


def test_prime_runner_vendors_model_code_instead_of_trust_remote_code():
    script = (PRIME_DIR / "run.sh").read_text(encoding="utf-8")
    dockerfile = (PRIME_DIR / "Dockerfile").read_text(encoding="utf-8")

    assert "trust_remote_code=True" not in script
    assert script.count("trust_remote_code=False") == 4  # tokenizer + model in both branches
    assert (
        "COPY --chown=${RUNNER_UID}:${RUNNER_GID} ./docker/runners/prime/vendor/ /opt/prime_model_code/" in dockerfile
    )
    assert "PRIME_VENDOR_DIR" in script
    assert "sys.path.insert(0, str(code_dir))" in script
    assert "vendor/README.md" in script
    assert (PRIME_DIR / "vendor" / "README.md").is_file()
    assert (PRIME_DIR / "vendor" / "placeholder.txt").is_file()


def _write_fake_prime_model(tmp_path, auto_map=True) -> Path:
    model_dir = tmp_path / "weights" / "ProPrime_650M_OGT_Prediction-91490f95c707"
    model_dir.mkdir(parents=True)
    config = {"model_type": "prime"}
    if auto_map:
        config["auto_map"] = {
            "AutoConfig": ["modeling_prime.PrimeConfig"],
            "AutoModel": ["modeling_prime.PrimeForPrediction"],
            "AutoTokenizer": ["tokenization_prime.PrimeTokenizer"],
        }
    (model_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return model_dir


def test_manifest_param_escaping_round_trip(tmp_path):
    """The v2 protocol must preserve param values byte-for-byte: backslash
    runs, quotes, shell metacharacters, newlines, and unicode all survive
    manifest -> task_context.py -> stdout."""
    values = {
        "smiles": "C=C(" + chr(92) + "C)" + chr(92) * 3 + "N",
        "quote": "it's 'quoted' \"double\"",
        "shell": "$(id) `whoami` ${HOME} && ; | > <",
        "newline": "line1" + chr(10) + "line2",
        "unicode": "β-转角-残基-序列",
        "backslash_run": chr(92) * 8,
    }
    manifest_path = tmp_path / "task.json"
    manifest_path.write_text(
        json.dumps(
            {
                "task_id": "t",
                "task_type": "test",
                "params": values,
                "files": [
                    {
                        "name": "primary",
                        "path": str(tmp_path / "input.fasta"),
                        "relative_path": "input.fasta",
                        "hash": "x",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["TASK_MANIFEST"] = str(manifest_path)
    context_py = SERVER_ROOT / "docker" / "runners" / "common" / "task_context.py"
    for key, expected in values.items():
        completed = subprocess.run(
            ["python3", str(context_py), "param", key],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == expected + chr(10), f"{key!r} did not round-trip: {completed.stdout!r}"

    # the bash wrapper path: one nasty value through _parse_param
    env["TASK_CONTEXT_SRC"] = str(SERVER_ROOT / "docker" / "runners" / "common" / "task_context.sh")
    bash_script = 'source "$TASK_CONTEXT_SRC"\nprintf "%s" "$(_parse_param smiles)"'
    completed = subprocess.run(["bash", "-c", bash_script], env=env, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == values["smiles"]


def test_prime_runner_fails_closed_without_vendored_model_code(tmp_path):
    model_dir = _write_fake_prime_model(tmp_path)
    input_file = tmp_path / "input.fasta"
    input_file.write_text(">test\nACDEFGHIK\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"

    manifest_path = input_file.parent / "task.json"
    manifest_path.write_text(
        json.dumps(
            {
                "params": {},
                "files": [{"name": "primary", "path": str(input_file), "relative_path": "input.fasta", "hash": "x"}],
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["TASK_MANIFEST"] = str(manifest_path)
    env["TASK_CONTEXT_SRC"] = str(SERVER_ROOT / "docker" / "runners" / "common" / "task_context.sh")
    env["PRIME_MODEL_DIR"] = str(model_dir)
    env["PRIME_VENDOR_DIR"] = str(tmp_path / "vendor")
    completed = subprocess.run(
        ["bash", str(PRIME_DIR / "run.sh"), "ogt", "-i", str(manifest_path), "-o", str(output_dir)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "PRIME vendored model code missing" in completed.stderr
    assert "vendor/README.md" in completed.stderr
    assert "trust_remote_code" not in completed.stderr
    assert not (output_dir / "task_finished").exists()


def test_prime_runner_rejects_weights_manifest_mismatch(tmp_path):
    model_dir = _write_fake_prime_model(tmp_path)
    (model_dir / "weights.bin").write_bytes(b"checkpoint")
    input_file = tmp_path / "input.fasta"
    input_file.write_text(">test\nACDEFGHIK\n", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    vendor_dir = tmp_path / "vendor"
    vendor_dir.mkdir()
    (vendor_dir / "manifest.sha256").write_text(
        "0" * 64 + "  ProPrime_650M_OGT_Prediction-91490f95c707/weights.bin\n",
        encoding="utf-8",
    )

    manifest_path = input_file.parent / "task.json"
    manifest_path.write_text(
        json.dumps(
            {
                "params": {},
                "files": [{"name": "primary", "path": str(input_file), "relative_path": "input.fasta", "hash": "x"}],
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["TASK_MANIFEST"] = str(manifest_path)
    env["TASK_CONTEXT_SRC"] = str(SERVER_ROOT / "docker" / "runners" / "common" / "task_context.sh")
    env["PRIME_MODEL_DIR"] = str(model_dir)
    env["PRIME_VENDOR_DIR"] = str(vendor_dir)
    completed = subprocess.run(
        ["bash", str(PRIME_DIR / "run.sh"), "ogt", "-i", str(manifest_path), "-o", str(output_dir)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "weights integrity check FAILED" in completed.stderr
    assert not (output_dir / "task_finished").exists()
