#!/bin/bash
set -e
usage() { echo "Usage: $0 -i <input_pdb> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file"); output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

_parse_param() { python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"; }
: "${NUM_SAMPLES:=$(_parse_param num_samples)}"; : "${NUM_SAMPLES:=50}"
: "${PREDICT_LIGAND:=$(_parse_param predict_ligand)}"; : "${PREDICT_LIGAND:=true}"

echo "REVODESIGN_STAGE:placer"
EXTRA=""
[[ "$PREDICT_LIGAND" == "true" ]] && EXTRA="--predict_ligand"

python3 "${PLACER_PATH}/run_PLACER.py" -i "$(dirname "$input_file")" -o "$output_dir" -n "$NUM_SAMPLES" $EXTRA

touch "${output_dir}/task_finished"
echo "PLACER complete."
