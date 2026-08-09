#!/bin/bash
set -e

usage() { echo "Usage: $0 -i <input_pdb> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file")
output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

_parse_param() { python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"; }
: "${CONTIG:=$(_parse_param contig)}"
: "${CONTIG:=100-100}"
: "${NUM_DESIGNS:=$(_parse_param num_designs)}"
: "${NUM_DESIGNS:=10}"

echo "REVODESIGN_STAGE:rfdiffusion"

cd "${RFDIFFUSION_PATH}"
python3 scripts/run_inference.py \
    "contigmap.contigs=[${CONTIG}]" \
    "inference.input_pdb=${input_file}" \
    "inference.output_prefix=${output_dir}/design" \
    "inference.num_designs=${NUM_DESIGNS}"

touch "${output_dir}/task_finished"
echo "RFdiffusion complete."
