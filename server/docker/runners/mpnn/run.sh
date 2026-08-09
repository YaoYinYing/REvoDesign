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
_parse_param() { python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"; }
: "${NUM_SEQ:=$(_parse_param num_seq)}"
: "${NUM_SEQ:=100}"
: "${SAMPLING_TEMP:=$(_parse_param sampling_temp)}"
: "${SAMPLING_TEMP:=0.1}"
: "${CHAINS:=$(_parse_param chains)}"
: "${CHAINS:=A}"
: "${FIXED_POS:=$(_parse_param fixed_positions)}"

echo "REVODESIGN_STAGE:${TASK_TYPE:-mpnn}"

case "${TASK_TYPE:-hypermpnn}" in
  hypermpnn)
    # Parse PDB → JSONL, then run ProteinMPNN with HyperMPNN weights.
    python3 "${MPNN_PATH}/helper_scripts/parse_multiple_chains.py" \
      --input_path="$(dirname "$input_file")" --output_path="${output_dir}/parsed.jsonl"
    python3 "${MPNN_PATH}/protein_mpnn_run.py" \
      --jsonl_path "${output_dir}/parsed.jsonl" --out_folder "${output_dir}" \
      --num_seq_per_target "${NUM_SEQ}" --sampling_temp "${SAMPLING_TEMP}" \
      --path_to_model_weights "${HYPERMPNN_WEIGHTS}" --model_name v48_020_epoch300_hyper \
      --batch_size 1
    ;;
  ligandmpnn)
    python3 "${LIGANDMPNN_PATH}/run.py" \
      --pdb_path "${input_file}" --out_folder "${output_dir}" \
      --num_seq_per_target "${NUM_SEQ}" --sampling_temp "${SAMPLING_TEMP}" \
      --seed 111 --batch_size 1
    ;;
  thermompnn)
    thermompnn --pdb "${input_file}" --out "${output_dir}/thermompnn" \
      --mode single --chains "${CHAINS}" --batch_size 256
    ;;
  *) echo "Unknown TASK_TYPE: ${TASK_TYPE}" >&2; exit 1 ;;
esac

touch "${output_dir}/task_finished"
echo "MPNN ${TASK_TYPE} complete."
