#!/bin/bash
# ColabFold/AlphaFold2 runner using the public MMseqs2 MSA service.
set -euo pipefail
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

usage() { echo "Usage: $0 -i <task.json> -o <output_dir> [-s all|features|model]"; exit 1; }
run_stage=all
while getopts ":i:o:s:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; s) run_stage=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
[[ "$run_stage" =~ ^(all|features|model)$ ]] || usage
input_file=$(readlink -f "$input_file"); output_dir=$(readlink -f "$output_dir")
[[ -f "$input_file" ]] || { echo "Task manifest not found: $input_file" >&2; exit 1; }
mkdir -p "$output_dir"

model_type=$(_parse_param model_type auto)
msa_mode=$(_parse_param msa_mode mmseqs2_uniref_env)
num_recycle=$(_parse_param num_recycle 3)
num_models=$(_parse_param num_models 5)
num_seeds=$(_parse_param num_seeds 1)
random_seed=$(_parse_param random_seed 0)
num_relax=$(_parse_param num_relax 1)
fasta_path=$(primary_input)
msa_marker="${output_dir}/.colabfold-msa-complete"
colabfold_batch=${COLABFOLD_BATCH:-colabfold_batch}

common_args=(
  "--data" "/mnt/colabfold"
  "--model-type" "$model_type"
  "--msa-mode" "$msa_mode"
  "--num-recycle" "$num_recycle"
  "--num-models" "$num_models"
  "--num-seeds" "$num_seeds"
  "--random-seed" "$random_seed"
  "--host-url" "https://api.colabfold.com"
)

run_msa() {
  echo "REVODESIGN_STAGE:msa_searching"
  "$colabfold_batch" "${common_args[@]}" --msa-only "$fasta_path" "$output_dir"
  find "$output_dir" -type f -name '*.a3m' -size +0c -print -quit | grep -q . || {
    echo "ColabFold produced no MSA" >&2; exit 1;
  }
  touch "$msa_marker"
  echo "ColabFold MSA complete."
}

if [[ "$run_stage" =~ ^(all|features)$ ]]; then
  run_msa
  [[ "$run_stage" == features ]] && exit 0
fi

[[ -f "$msa_marker" ]] || { echo "Validated ColabFold MSA is missing" >&2; exit 1; }
echo "REVODESIGN_STAGE:modeling"
model_args=("${common_args[@]}")
if (( num_relax > 0 )); then
  model_args+=(--amber --use-gpu-relax --num-relax "$num_relax")
fi
"$colabfold_batch" "${model_args[@]}" "$fasta_path" "$output_dir"
find "$output_dir" -type f -name '*.pdb' -size +0c -print -quit | grep -q . || {
  echo "ColabFold produced no structure" >&2; exit 1;
}
touch "${output_dir}/task_finished"
echo "ColabFold complete."
