#!/bin/bash
# Dispatcher for PLACER / RFdiffusion shared runner.
# $1 = tool name (set in task_types.yaml command field).
set -e

_parse_param() { python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"; }

_run_placer() {
  usage() { echo "Usage: $0 -i <input_pdb> -o <output_dir>"; exit 1; }
  while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
  [[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
  input_file=$(readlink -f "$input_file"); output_dir=$(readlink -f "$output_dir")
  [[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
  case "$input_file" in
    */inputs/*) input_root="${input_file%%/inputs/*}/inputs" ;;
    *) input_root=$(dirname "$input_file") ;;
  esac
  mkdir -p "$output_dir"

  : "${NUM_SAMPLES:=$(_parse_param num_samples)}"; : "${NUM_SAMPLES:=50}"
  : "${PREDICT_LIGAND:=$(_parse_param predict_ligand)}"; : "${PREDICT_LIGAND:=true}"

  echo "REVODESIGN_STAGE:placer"
  local extra=""
  [[ "$PREDICT_LIGAND" == "true" ]] && extra="--predict_ligand"
  export REVOCOMPUTE_INPUT_ROOT="$input_root"
  python3 "${PLACER_PATH}/run_PLACER.py" -i "$input_root" -o "$output_dir" -n "$NUM_SAMPLES" $extra

  touch "${output_dir}/task_finished"
  echo "PLACER complete."
}

_run_rfdiffusion() {
  usage() { echo "Usage: $0 -i <input_pdb> -o <output_dir>"; exit 1; }
  while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
  [[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
  input_file=$(readlink -f "$input_file"); output_dir=$(readlink -f "$output_dir")
  [[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
  mkdir -p "$output_dir"

  : "${CONTIG:=$(_parse_param contig)}"; : "${CONTIG:=100-100}"
  : "${NUM_DESIGNS:=$(_parse_param num_designs)}"; : "${NUM_DESIGNS:=10}"

  echo "REVODESIGN_STAGE:rfdiffusion"
  cd "${RFDIFFUSION_PATH}"
  python3 scripts/run_inference.py \
    "contigmap.contigs=[${CONTIG}]" \
    "inference.input_pdb=${input_file}" \
    "inference.output_prefix=${output_dir}/design" \
    "inference.num_designs=${NUM_DESIGNS}"

  touch "${output_dir}/task_finished"
  echo "RFdiffusion complete."
}

TOOL="${1:-}"
shift || true

case "${TOOL}" in
placer)      _run_placer "$@" ;;
rfdiffusion) _run_rfdiffusion "$@" ;;
*)
  echo "Usage: $0 {placer|rfdiffusion} -i <input> -o <output>" >&2
  exit 1
  ;;
esac
