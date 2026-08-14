#!/bin/bash
set -e
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"
usage() { echo "Usage: $0 -i <fasta> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file")
input_file=$(primary_input)

input_file=$(python3 -c "import json,os;print(json.load(open(os.environ['TASK_MANIFEST']))['files'][0]['path'])")
# ^ runner protocol v2: -i was the manifest; the real input comes from files[0].; output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

checkpoint_root=${BIOEMU_CHECKPOINT_ROOT:-/mnt/db/weights/bioemu/checkpoints/bioemu-v1.1}
checkpoint_path=${checkpoint_root}/checkpoint.ckpt
model_config_path=${checkpoint_root}/config.yaml
[[ -s "${checkpoint_path}" ]] || { echo "BioEmu checkpoint not found: ${checkpoint_path}" >&2; exit 1; }
[[ -s "${model_config_path}" ]] || { echo "BioEmu model config not found: ${model_config_path}" >&2; exit 1; }
runtime_cache=$(mktemp -d "${TMPDIR:-/tmp}/revodesign-bioemu.XXXXXX")
trap 'rm -rf -- "${runtime_cache}"' EXIT

: "${NUM_SAMPLES:=$(_parse_param num_samples)}"; : "${NUM_SAMPLES:=10}"
: "${BATCH_SIZE_100:=$(_parse_param batch_size_100)}"; : "${BATCH_SIZE_100:=10}"
: "${DENOISER_TYPE:=$(_parse_param denoiser_type)}"; : "${DENOISER_TYPE:=dpm}"
: "${FILTER_SAMPLES:=$(_parse_param filter_samples)}"; : "${FILTER_SAMPLES:=true}"

echo "REVODESIGN_STAGE:bioemu"
bioemu_args=(
  "$input_file"
  "$NUM_SAMPLES"
  "$output_dir"
  --batch_size_100="${BATCH_SIZE_100}"
  --model_name=None
  --ckpt_path="${checkpoint_path}"
  --model_config_path="${model_config_path}"
  --cache_embeds_dir="${runtime_cache}/embeds"
  --cache_so3_dir="${runtime_cache}/so3"
  --denoiser_type="${DENOISER_TYPE}"
  --filter_samples="${FILTER_SAMPLES}"
)
base_seed=$(_parse_param base_seed)
[[ -n "$base_seed" ]] && bioemu_args+=(--base_seed="$base_seed")
python3 -m bioemu.sample "${bioemu_args[@]}"

touch "${output_dir}/task_finished"
echo "BioEmu complete."
