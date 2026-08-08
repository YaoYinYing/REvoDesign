#!/bin/bash
# REvoDesign ESM runner — ESMFold structure prediction and ESM-2 model scoring.
#
# Runner contract:
#   1. Reads input FASTA/PDB from /workspace/inputs/
#   2. Writes output to /workspace/outputs/
#   3. Emits REVODESIGN_STAGE:<marker> on stdout
#   4. Accepts -i <input> -o <output_dir>
#   5. Exits 0 on success

set -e

REVODESIGN_RUNSCRIPT_PATH=$(readlink -f "$(dirname "$0")")

usage() {
    echo ""
    echo "Usage: $0 <OPTIONS>"
    echo "Required Parameters:"
    echo "      -i  <input>        Input FASTA/PDB file"
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
output_dir=$(readlink -f "$output_dir")

if [[ ! -f "$input_file" ]]; then
    echo "Input file not found: $input_file"
    exit 1
fi

mkdir -p "$output_dir"

# Parse TASK_PARAMS JSON into env vars (docker_runner passes params this way).
# Each task type has different params; we extract known keys with defaults.
_parse_param() { python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"; }
: "${NUM_RECYCLES:=$(_parse_param num_recycles)}"
: "${MAX_TOKENS_PER_BATCH:=$(_parse_param max_tokens_per_batch)}"
: "${CHUNK_SIZE:=$(_parse_param chunk_size)}"
: "${MODEL:=$(_parse_param model)}"
: "${REPR_LAYERS:=$(_parse_param repr_layers)}"
: "${SCORING_STRATEGY:=$(_parse_param scoring_strategy)}"
: "${TEMPERATURE:=$(_parse_param temperature)}"
: "${NUM_SAMPLES:=$(_parse_param num_samples)}"

echo "Processing $input_file ..."
echo "Output directory: $output_dir"

echo "REVODESIGN_STAGE:${TASK_TYPE:-esm_fold}"

case "${TASK_TYPE:-esm_fold}" in
  esm_fold)
    python "${REVODESIGN_RUNSCRIPT_PATH}/esmfold_inference.py" \
      -i "$input_file" -o "$output_dir" -m /mnt/db/weights/esm \
      --num-recycles "${NUM_RECYCLES:-4}" \
      --max-tokens-per-batch "${MAX_TOKENS_PER_BATCH:-1024}" \
      --chunk-size "${CHUNK_SIZE:-128}"
    ;;
  esm_extract)
    esm2-extract "${MODEL:-esm2_t33_650M_UR50D}" "$input_file" "$output_dir" \
      --repr_layers "${REPR_LAYERS:-33}" --include mean per_tok
    ;;
  esm_1v)
    python "${REVODESIGN_RUNSCRIPT_PATH}/esm1v_score.py" \
      -i "$input_file" -o "$output_dir" -m /mnt/db/weights/esm
    ;;
  esm_if1)
    python "${REVODESIGN_RUNSCRIPT_PATH}/esm_if1_design.py" \
      -i "$input_file" -o "$output_dir" -m /mnt/db/weights/esm \
      --temperature "${TEMPERATURE:-1.0}" --num-samples "${NUM_SAMPLES:-1}"
    ;;
  *)
    echo "Unknown TASK_TYPE: ${TASK_TYPE}" >&2
    exit 1
    ;;
esac

touch "${output_dir}/task_finished"
echo "ESM ${TASK_TYPE} complete."
