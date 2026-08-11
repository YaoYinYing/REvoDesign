#!/bin/bash
set -e

REVODESIGN_RUNSCRIPT_PATH=$(readlink -f "$(dirname "$0")")

usage() {
    echo "Usage: $0 -i <input> -o <output_dir>"
    exit 1
}
while getopts ":i:o:" opt; do
    case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac
done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file")
output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

# Parse TASK_PARAMS
_parse_param() { python3 -c "import json,os; v=json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''); print(str(v).lower() if isinstance(v,bool) else v)"; }
_append_param() {
    local -n target_args=$1
    local flag=$2
    local key=${3:-$2}
    local value
    value=$(_parse_param "${key}")
    # Empty HTML fields are intentionally omitted so the pinned upstream CLI
    # can apply its own default. Passing `--seed ''`, for example, makes
    # argparse reject the entire task before inference starts.
    if [[ -n "${value}" && "${value}" != "None" && "${value}" != "null" ]]; then
        target_args+=("--${flag}" "${value}")
    fi
}
: "${NUMBER_OF_BATCHES:=$(_parse_param number_of_batches)}"
: "${NUMBER_OF_BATCHES:=100}"
: "${SAMPLING_TEMP:=$(_parse_param sampling_temp)}"
: "${SAMPLING_TEMP:=0.1}"
: "${CHAINS:=$(_parse_param chains)}"
: "${CHAINS:=A}"
: "${FIXED_POS:=$(_parse_param fixed_positions)}"
: "${MODE:=$(_parse_param mode)}"
: "${MODE:=single}"

echo "REVODESIGN_STAGE:${TASK_TYPE:-mpnn}"

task_type=${TASK_TYPE:-hypermpnn}
case "${task_type}" in
  hypermpnn|proteinmpnn|solublempnn)
    num_seq_per_target=$(_parse_param num_seq_per_target); : "${num_seq_per_target:=100}"
    batch_size=$(_parse_param batch_size); : "${batch_size:=1}"
    (( batch_size <= num_seq_per_target )) || {
      echo "batch_size must not exceed num_seq_per_target" >&2
      exit 1
    }
    protein_args=(
      --pdb_path "${input_file}"
      --out_folder "${output_dir}"
      --num_seq_per_target "${num_seq_per_target}"
      --sampling_temp "${SAMPLING_TEMP}"
      --batch_size "${batch_size}"
    )
    for key in seed suppress_print save_score save_probs score_only conditional_probs_only \
      conditional_probs_only_backbone unconditional_probs_only backbone_noise max_length omit_AAs; do
      _append_param protein_args "${key}"
    done
    if [[ "${task_type}" == "hypermpnn" ]]; then
      protein_args+=(--path_to_model_weights "${HYPERMPNN_WEIGHTS}" --model_name v48_020_epoch300_hyper)
    else
      _append_param protein_args model_name
    fi
    if [[ "${task_type}" == "proteinmpnn" && "$(_parse_param ca_only)" == "true" ]]; then
      [[ "$(_parse_param model_name)" != "v_48_030" ]] || {
        echo "The official CA-only model does not provide a v_48_030 checkpoint" >&2
        exit 1
      }
      protein_args+=(--ca_only)
    fi
    [[ "${task_type}" == "solublempnn" ]] && protein_args+=(--use_soluble_model)
    chains=$(_parse_param pdb_path_chains)
    [[ -n "$chains" ]] && protein_args+=(--pdb_path_chains "$chains")
    python3 "${MPNN_PATH}/protein_mpnn_run.py" "${protein_args[@]}"
    ;;
  ligandmpnn)
    ligand_args=(
      --model_type ligand_mpnn
      --pdb_path "${input_file}"
      --out_folder "${output_dir}"
      --number_of_batches "${NUMBER_OF_BATCHES}"
      --temperature "${SAMPLING_TEMP}"
    )
    for key in seed batch_size verbose fasta_seq_separation homo_oligomer zero_indexed \
      save_stats ligand_mpnn_use_atom_context ligand_mpnn_cutoff_for_score \
      ligand_mpnn_use_side_chain_context parse_atoms_with_zero_occupancy pack_side_chains \
      number_of_packs_per_design sc_num_denoising_steps sc_num_samples repack_everything \
      force_hetatm packed_suffix pack_with_ligand_context fixed_residues redesigned_residues \
      bias_AA omit_AA symmetry_residues symmetry_weights chains_to_design parse_these_chains_only; do
      _append_param ligand_args "${key}"
    done
    python3 "${LIGANDMPNN_PATH}/run.py" "${ligand_args[@]}"
    ;;
  lasermpnn)
    laser_checkpoint=$(_parse_param model_checkpoint)
    case "${laser_checkpoint:-all_data}" in
      all_data)
        laser_weights="${LASERMPNN_PATH}/model_weights/laser_weights_0p1A_nothing_heldout.pt"
        ;;
      paper)
        laser_weights="${LASERMPNN_PATH}/model_weights/laser_weights_0p1A_noise_ligandmpnn_split.pt"
        ;;
      *)
        echo "Unknown LASErMPNN model_checkpoint: ${laser_checkpoint}" >&2
        exit 1
        ;;
    esac

    laser_input_manifest=$(mktemp --suffix=.txt)
    trap 'rm -f "${laser_input_manifest}"' EXIT
    LASER_INPUT_MANIFEST="${laser_input_manifest}" python3 - <<'PY'
import json
import os
from pathlib import Path

inputs = json.loads(os.environ.get("TASK_INPUTS", "[]"))
if not inputs:
    raise SystemExit("TASK_INPUTS did not contain any LASErMPNN structures")
allowed = {".pdb", ".cif", ".mmcif"}
paths = []
for item in inputs:
    raw_path = item.get("path", "") if isinstance(item, dict) else ""
    path = Path(raw_path)
    if "\n" in raw_path or "\r" in raw_path or path.suffix.lower() not in allowed:
        raise SystemExit(f"Unsupported LASErMPNN input: {path.name}")
    if not path.is_file():
        raise SystemExit(f"LASErMPNN input not found: {path.name}")
    paths.append(str(path))
Path(os.environ["LASER_INPUT_MANIFEST"]).write_text("\n".join(paths) + "\n", encoding="utf-8")
PY

    designs_per_input=$(_parse_param designs_per_input); : "${designs_per_input:=5}"
    designs_per_batch=$(_parse_param designs_per_batch); : "${designs_per_batch:=5}"
    inputs_simultaneously=$(_parse_param inputs_processed_simultaneously); : "${inputs_simultaneously:=1}"
    (( designs_per_batch <= designs_per_input )) || {
      echo "designs_per_batch must not exceed designs_per_input" >&2
      exit 1
    }
    laser_args=(
      "${laser_input_manifest}"
      "${output_dir}"
      "${designs_per_input}"
      --designs_per_batch "${designs_per_batch}"
      --inputs_processed_simultaneously "${inputs_simultaneously}"
      --model_weights_path "${laser_weights}"
      --device cpu
    )
    for key in chi_min_p seq_min_p disabled_residues ala_budget gly_budget fs_calc_ca_distance \
      fs_calc_burial_hull_alpha_value sequence_temp first_shell_sequence_temp chi_temp \
      budget_residue_sele_string; do
      _append_param laser_args "${key}"
    done
    for flag in use_water silent fix_beta repack_only_input_sequence ignore_ligand \
      constrain_ala_gly_sampling_to_exposed_non_secondary_structure noncanonical_aa_ligand \
      repack_all output_fasta output_fasta_only fs_no_calc_burial disable_charged_fs; do
      [[ "$(_parse_param "${flag}")" == "true" ]] && laser_args+=("--${flag}")
    done
    (
      cd "$(dirname "${LASERMPNN_PATH}")"
      python3 -m LASErMPNN.run_batch_inference "${laser_args[@]}"
    )
    ;;
  thermompnn)
    read -r -a thermo_chains <<< "$CHAINS"
    thermo_args=(
      --pdb "${input_file}"
      --out "${output_dir}/thermompnn"
      --mode "${MODE}"
      --chains "${thermo_chains[@]}"
    )
    for key in batch_size threshold distance; do
      _append_param thermo_args "${key}"
    done
    [[ "$(_parse_param ss_penalty)" == "true" ]] && thermo_args+=(--ss_penalty)
    thermompnn "${thermo_args[@]}"
    ;;
  *) echo "Unknown TASK_TYPE: ${TASK_TYPE}" >&2; exit 1 ;;
esac

touch "${output_dir}/task_finished"
echo "MPNN ${TASK_TYPE} complete."
