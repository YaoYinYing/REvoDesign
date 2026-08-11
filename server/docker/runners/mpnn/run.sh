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
: "${NUM_SEQ:=$(_parse_param number_of_batches)}"
: "${NUM_SEQ:=100}"
: "${SAMPLING_TEMP:=$(_parse_param sampling_temp)}"
: "${SAMPLING_TEMP:=0.1}"
: "${CHAINS:=$(_parse_param chains)}"
: "${CHAINS:=A}"
: "${FIXED_POS:=$(_parse_param fixed_positions)}"
: "${MODE:=$(_parse_param mode)}"
: "${MODE:=single}"

echo "REVODESIGN_STAGE:${TASK_TYPE:-mpnn}"

case "${TASK_TYPE:-hypermpnn}" in
  hypermpnn)
    hyper_args=(
      --pdb_path "${input_file}"
      --out_folder "${output_dir}"
      --num_seq_per_target "$(_parse_param num_seq_per_target)"
      --sampling_temp "${SAMPLING_TEMP}"
      --path_to_model_weights "${HYPERMPNN_WEIGHTS}"
      --model_name v48_020_epoch300_hyper
      --batch_size "$(_parse_param batch_size)"
      --seed "$(_parse_param seed)"
      --suppress_print "$(_parse_param suppress_print)"
      --save_score "$(_parse_param save_score)"
      --save_probs "$(_parse_param save_probs)"
      --score_only "$(_parse_param score_only)"
      --conditional_probs_only "$(_parse_param conditional_probs_only)"
      --conditional_probs_only_backbone "$(_parse_param conditional_probs_only_backbone)"
      --unconditional_probs_only "$(_parse_param unconditional_probs_only)"
      --backbone_noise "$(_parse_param backbone_noise)"
      --max_length "$(_parse_param max_length)"
      --omit_AAs "$(_parse_param omit_AAs)"
    )
    [[ "$(_parse_param ca_only)" == "true" ]] && hyper_args+=(--ca_only)
    chains=$(_parse_param pdb_path_chains)
    [[ -n "$chains" ]] && hyper_args+=(--pdb_path_chains "$chains")
    python3 "${MPNN_PATH}/protein_mpnn_run.py" "${hyper_args[@]}"
    ;;
  ligandmpnn)
    ligand_args=(
      --model_type ligand_mpnn
      --pdb_path "${input_file}"
      --out_folder "${output_dir}"
      --number_of_batches "${NUM_SEQ}"
      --temperature "${SAMPLING_TEMP}"
      --seed "$(_parse_param seed)"
      --batch_size "$(_parse_param batch_size)"
      --verbose "$(_parse_param verbose)"
      --fasta_seq_separation "$(_parse_param fasta_seq_separation)"
      --homo_oligomer "$(_parse_param homo_oligomer)"
      --zero_indexed "$(_parse_param zero_indexed)"
      --save_stats "$(_parse_param save_stats)"
      --ligand_mpnn_use_atom_context "$(_parse_param ligand_mpnn_use_atom_context)"
      --ligand_mpnn_cutoff_for_score "$(_parse_param ligand_mpnn_cutoff_for_score)"
      --ligand_mpnn_use_side_chain_context "$(_parse_param ligand_mpnn_use_side_chain_context)"
      --parse_atoms_with_zero_occupancy "$(_parse_param parse_atoms_with_zero_occupancy)"
      --pack_side_chains "$(_parse_param pack_side_chains)"
      --number_of_packs_per_design "$(_parse_param number_of_packs_per_design)"
      --sc_num_denoising_steps "$(_parse_param sc_num_denoising_steps)"
      --sc_num_samples "$(_parse_param sc_num_samples)"
      --repack_everything "$(_parse_param repack_everything)"
      --force_hetatm "$(_parse_param force_hetatm)"
      --packed_suffix "$(_parse_param packed_suffix)"
      --pack_with_ligand_context "$(_parse_param pack_with_ligand_context)"
    )
    for mapping in \
      fixed_residues:fixed_residues redesigned_residues:redesigned_residues \
      bias_AA:bias_AA omit_AA:omit_AA symmetry_residues:symmetry_residues \
      symmetry_weights:symmetry_weights chains_to_design:chains_to_design \
      parse_these_chains_only:parse_these_chains_only; do
      key=${mapping%%:*}; flag=${mapping#*:}; value=$(_parse_param "$key")
      [[ -n "$value" ]] && ligand_args+=("--${flag}" "$value")
    done
    python3 "${LIGANDMPNN_PATH}/run.py" "${ligand_args[@]}"
    ;;
  thermompnn)
    read -r -a thermo_chains <<< "$CHAINS"
    thermo_args=(
      --pdb "${input_file}"
      --out "${output_dir}/thermompnn"
      --mode "${MODE}"
      --chains "${thermo_chains[@]}"
      --batch_size "$(_parse_param batch_size)"
      --threshold "$(_parse_param threshold)"
      --distance "$(_parse_param distance)"
    )
    [[ "$(_parse_param ss_penalty)" == "true" ]] && thermo_args+=(--ss_penalty)
    thermompnn "${thermo_args[@]}"
    ;;
  *) echo "Unknown TASK_TYPE: ${TASK_TYPE}" >&2; exit 1 ;;
esac

touch "${output_dir}/task_finished"
echo "MPNN ${TASK_TYPE} complete."
