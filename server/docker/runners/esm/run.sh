#!/bin/bash
# REvoDesign ESM runner — ESM-2 embedding, ESM-1v scoring, ESM-IF1 design.
#
# Runner contract:
#   1. Reads input FASTA/PDB from /workspace/inputs/
#   2. Writes output to /workspace/outputs/
#   3. Emits REVODESIGN_STAGE:<marker> on stdout
#   4. Accepts -i <input> -o <output_dir>
#   5. Exits 0 on success

set -e
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

REVODESIGN_RUNSCRIPT_PATH=$(readlink -f "$(dirname "$0")")

usage() {
    echo ""
    echo "Usage: $0 <OPTIONS>"
    echo "Required Parameters:"
    echo "      -i  <task.json>    Task manifest (primary input resolved from files[0])"
    echo "      -o  <output_dir>   Output directory"
    echo ""
    exit 1
}

while getopts ":i:o:" opt; do
    case "${opt}" in
        i) input_file=$OPTARG ;;
        o) output_dir=$OPTARG ;;
        ?) usage ;;
    esac
done

if [[ -z "${input_file:-}" ]]; then
    echo "Missing required option: -i <input>"
    usage
fi

if [[ -z "${output_dir:-}" ]]; then
    echo "Missing required option: -o <output_dir>"
    usage
fi

input_file=$(readlink -f "$input_file")
input_file=$(primary_input)

output_dir=$(readlink -f "$output_dir")

if [[ ! -f "$input_file" ]]; then
    echo "Input file not found: $input_file"
    exit 1
fi

mkdir -p "$output_dir"

# Parse TASK_PARAMS JSON into env vars (docker_runner passes params this way).
# Each task type has different params; we extract known keys with defaults.
: "${MSA_SAMPLES:=$(_parse_param msa_samples)}"
: "${NUM_RECYCLES:=$(_parse_param num_recycles)}"
: "${MAX_TOKENS_PER_BATCH:=$(_parse_param max_tokens_per_batch)}"
: "${CHUNK_SIZE:=$(_parse_param chunk_size)}"
: "${MODEL:=$(_parse_param model)}"
: "${REPR_LAYERS:=$(_parse_param repr_layers)}"
: "${TEMPERATURE:=$(_parse_param temperature)}"
: "${NUM_SAMPLES:=$(_parse_param num_samples)}"
: "${INCLUDE:=$(_parse_param include)}"
: "${TOKS_PER_BATCH:=$(_parse_param toks_per_batch)}"
: "${TRUNCATION_SEQ_LENGTH:=$(_parse_param truncation_seq_length)}"
: "${CHAIN:=$(_parse_param chain)}"

echo "Processing $input_file ..."
echo "Output directory: $output_dir"

echo "REVODESIGN_STAGE:${TASK_TYPE:-esm_extract}"

case "${TASK_TYPE:-esm_extract}" in
  esm_msa)
    python "${REVODESIGN_RUNSCRIPT_PATH}/msa1b_score.py" \
      -i "$input_file" -o "$output_dir" -m /mnt/db/weights/esm \
      --msa-samples "${MSA_SAMPLES:-32}"
    ;;
  esm_extract)
    read -r -a repr_layer_args <<< "${REPR_LAYERS:-33}"
    read -r -a include_args <<< "${INCLUDE:-mean per_tok}"
    esm2-extract "${MODEL:-esm2_t33_650M_UR50D}" "$input_file" "$output_dir" \
      --toks_per_batch "${TOKS_PER_BATCH:-4096}" \
      --repr_layers "${repr_layer_args[@]}" \
      --include "${include_args[@]}" \
      --truncation_seq_length "${TRUNCATION_SEQ_LENGTH:-1022}"
    ;;
  esm_1v)
    python "${REVODESIGN_RUNSCRIPT_PATH}/esm1v_score.py" \
      -i "$input_file" -o "$output_dir" -m /mnt/db/weights/esm
    ;;
  esm_if1)
    python "${REVODESIGN_RUNSCRIPT_PATH}/esm_if1_design.py" \
      -i "$input_file" -o "$output_dir" -m /mnt/db/weights/esm \
      --temperature "${TEMPERATURE:-1.0}" --num-samples "${NUM_SAMPLES:-1}" \
      --chain "${CHAIN:-A}"
    ;;
  *)
    echo "Unknown TASK_TYPE: ${TASK_TYPE}" >&2
    exit 1
    ;;
esac

touch "${output_dir}/task_finished"
echo "ESM ${TASK_TYPE} complete."

# TODO esm anchor missing
