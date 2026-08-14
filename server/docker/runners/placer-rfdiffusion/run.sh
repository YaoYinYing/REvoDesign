#!/bin/bash
# Dispatcher for PLACER / RFdiffusion shared runner.
# $1 = tool name (set in task_types.yaml command field).
set -e
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"


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
  # input_root above derives from the manifest path; the real primary file
  # comes from the manifest itself.
  input_file=$(primary_input)
  mkdir -p "$output_dir"

  : "${NUM_SAMPLES:=$(_parse_param num_samples)}"; : "${NUM_SAMPLES:=50}"
  : "${USE_SM:=$(_parse_param use_sm)}"; : "${USE_SM:=true}"

  echo "REVODESIGN_STAGE:placer"
  export REVOCOMPUTE_INPUT_ROOT="$input_root"
  local -a placer_args=(-i "$input_root" -o "$output_dir" -n "$NUM_SAMPLES")
  [[ "$USE_SM" == "false" ]] && placer_args+=(--no-use_sm)
  for switch_key in cautious exclude_common_ligands predict_multi ignore_ligand_hydrogens; do
    [[ "$(_parse_param "$switch_key")" == "true" ]] && placer_args+=("--${switch_key}")
  done
  local value key flag
  for mapping in fixed_ligand:fixed_ligand predict_ligand:predict_ligand bonds:bonds \
    mutate:mutate crop_centers:crop_centers corruption_centers:corruption_centers; do
    key=${mapping%%:*}; flag=${mapping#*:}; value=$(_parse_param "$key")
    if [[ -n "$value" ]]; then
      local -a values
      read -r -a values <<< "$value"
      placer_args+=("--${flag}" "${values[@]}")
    fi
  done
  for mapping in target_res:target_res fixed_ligand_noise:fixed_ligand_noise rerank:rerank; do
    key=${mapping%%:*}; flag=${mapping#*:}; value=$(_parse_param "$key")
    [[ -n "$value" ]] && placer_args+=("--${flag}" "$value")
  done
  python3 "${PLACER_PATH}/run_PLACER.py" "${placer_args[@]}"

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
  local -a rf_args=(
    "contigmap.contigs=[${CONTIG}]" \
    "inference.input_pdb=${input_file}" \
    "inference.output_prefix=${output_dir}/design" \
    "inference.num_designs=${NUM_DESIGNS}")
  local mapping key hydra_key value
  for mapping in \
    design_startnum:inference.design_startnum symmetry:inference.symmetry recenter:inference.recenter \
    radius:inference.radius model_only_neighbors:inference.model_only_neighbors write_trajectory:inference.write_trajectory \
    empty_cache_per_design:inference.empty_cache_per_design cautious:inference.cautious align_motif:inference.align_motif \
    symmetric_self_cond:inference.symmetric_self_cond final_step:inference.final_step deterministic:inference.deterministic \
    cyclic:inference.cyclic cyc_chains:inference.cyc_chains inpaint_seq:contigmap.inpaint_seq \
    inpaint_str:contigmap.inpaint_str inpaint_str_helix:contigmap.inpaint_str_helix \
    inpaint_str_strand:contigmap.inpaint_str_strand inpaint_str_loop:contigmap.inpaint_str_loop \
    provide_seq:contigmap.provide_seq length:contigmap.length diffuser_T:diffuser.T diffuser_b_0:diffuser.b_0 \
    diffuser_b_T:diffuser.b_T diffuser_schedule_type:diffuser.schedule_type partial_T:diffuser.partial_T \
    noise_scale_ca:denoiser.noise_scale_ca final_noise_scale_ca:denoiser.final_noise_scale_ca \
    ca_noise_schedule_type:denoiser.ca_noise_schedule_type noise_scale_frame:denoiser.noise_scale_frame \
    final_noise_scale_frame:denoiser.final_noise_scale_frame frame_noise_schedule_type:denoiser.frame_noise_schedule_type \
    hotspot_res:ppi.hotspot_res guiding_potentials:potentials.guiding_potentials guide_scale:potentials.guide_scale \
    guide_decay:potentials.guide_decay substrate:potentials.substrate sidechain_input:preprocess.sidechain_input \
    motif_sidechain_input:preprocess.motif_sidechain_input; do
    key=${mapping%%:*}; hydra_key=${mapping#*:}; value=$(_parse_param "$key")
    [[ -n "$value" ]] && rf_args+=("${hydra_key}=${value}")
  done
  python3 scripts/run_inference.py "${rf_args[@]}"

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
