#!/bin/bash
# REvoDesign OpenDDE runner — all-atom co-folding and structure prediction.
#
# Runner contract:
#   1. Reads input JSON from /workspace/inputs/
#   2. Writes output to /workspace/outputs/
#   3. Emits REVODESIGN_STAGE:<marker> on stdout
#   4. Accepts -i <input_json> -o <output_dir>
#   5. Exits 0 on success

set -e

REVODESIGN_RUNSCRIPT_PATH=$(readlink -f "$(dirname "$0")")

usage() {
    echo ""
    echo "Usage: $0 <OPTIONS>"
    echo "Required Parameters:"
    echo "      -i  <json>        Input JSON file (OpenDDE job spec)"
    echo "      -o  <output_dir>  Output directory"
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
    echo "Missing required option: -i <json>"
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

# Parse TASK_PARAMS JSON into env vars.
_parse_param() { python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"; }
: "${MODEL_NAME:=$(_parse_param model_name)}"
: "${MODEL_NAME:=opendde_v1}"
: "${NUM_SAMPLES:=$(_parse_param num_samples)}"
: "${NUM_SAMPLES:=1}"
: "${NUM_STEPS:=$(_parse_param num_steps)}"
: "${NUM_STEPS:=200}"
: "${NUM_CYCLES:=$(_parse_param num_cycles)}"
: "${NUM_CYCLES:=10}"
: "${USE_MSA:=$(_parse_param use_msa)}"
: "${USE_MSA:=true}"
: "${USE_TEMPLATE:=$(_parse_param use_template)}"
: "${USE_TEMPLATE:=true}"

echo "Processing $input_file ..."
echo "Output directory: $output_dir"
echo "Model: $MODEL_NAME  Samples: $NUM_SAMPLES  Steps: $NUM_STEPS  Cycles: $NUM_CYCLES"
echo "MSA: $USE_MSA  Template: $USE_TEMPLATE"

# OpenDDE inference — MSA + template search happens inside opendde pred
# if enabled (requires network access and search databases).
echo "REVODESIGN_STAGE:opendde"

opendde pred \
    -i "$input_file" \
    -o "$output_dir" \
    -n "$MODEL_NAME" \
    --sample "$NUM_SAMPLES" \
    --step "$NUM_STEPS" \
    --cycle "$NUM_CYCLES" \
    --use_msa "$USE_MSA" \
    --use_template "$USE_TEMPLATE" \
    --use_rna_msa false

touch "${output_dir}/task_finished"
echo "OpenDDE inference complete."
