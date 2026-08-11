#!/bin/bash
set -e
usage() { echo "Usage: $0 -i <fasta> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file"); output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

_parse_param() { python3 -c "import json,os; v=json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''); print(str(v).lower() if isinstance(v,bool) else v)"; }
: "${NUM_SAMPLES:=$(_parse_param num_samples)}"; : "${NUM_SAMPLES:=10}"

echo "REVODESIGN_STAGE:bioemu"
bioemu_args=(
  "$input_file"
  "$NUM_SAMPLES"
  "$output_dir"
  --batch_size_100="$(_parse_param batch_size_100)"
  --denoiser_type="$(_parse_param denoiser_type)"
  --filter_samples="$(_parse_param filter_samples)"
)
base_seed=$(_parse_param base_seed)
[[ -n "$base_seed" ]] && bioemu_args+=(--base_seed="$base_seed")
python3 -m bioemu.sample "${bioemu_args[@]}"

touch "${output_dir}/task_finished"
echo "BioEmu complete."
