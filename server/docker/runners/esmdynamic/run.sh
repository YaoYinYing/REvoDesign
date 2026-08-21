#!/bin/bash
# REvoDesign ESMDynamic runner — dynamic contact-map inference.
set -euo pipefail
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

usage() {
    echo "Usage: $0 -i <task.json> -o <output_dir>" >&2
    exit 1
}

while getopts ":i:o:" opt; do
    case "$opt" in
        i) input_file=$OPTARG ;;
        o) output_dir=$OPTARG ;;
        *) usage ;;
    esac
done
[[ -n "${input_file:-}" && -n "${output_dir:-}" ]] || usage

input_file=$(readlink -f "$input_file")
input_file=$(primary_input)
output_dir=$(readlink -f "$output_dir")
[[ -f "$input_file" ]] || { echo "Input file not found: $input_file" >&2; exit 1; }
mkdir -p "$output_dir"

: "${BATCH_SIZE:=$(_parse_param batch_size)}"
: "${CHUNK_SIZE:=$(_parse_param chunk_size)}"
: "${LOW_MEMORY:=$(_parse_param low_memory)}"
: "${NUM_RECYCLES:=$(_parse_param num_recycles)}"
: "${CHAIN_IDS:=$(_parse_param chain_ids)}"

echo "REVODESIGN_STAGE:esmdynamic"
args=(--fasta "$input_file" --output_dir "$output_dir" --device cuda --batch_size "${BATCH_SIZE:-1}" --chunk_size "${CHUNK_SIZE:-256}")
[[ "${LOW_MEMORY:-false}" == "true" ]] && args+=(--low_memory)
[[ -n "${NUM_RECYCLES:-}" && "${NUM_RECYCLES}" != "null" ]] && args+=(--num_recycles "$NUM_RECYCLES")
[[ -n "${CHAIN_IDS:-}" ]] && args+=(--chain_ids "$CHAIN_IDS")
run_esmdynamic "${args[@]}"

find "$output_dir" -type f -size +0c -print -quit | grep -q . || {
    echo "ESMDynamic exited without producing artifacts" >&2
    exit 1
}
touch "$output_dir/task_finished"
echo "ESMDynamic prediction complete."
