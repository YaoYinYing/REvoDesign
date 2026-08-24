#!/bin/bash
set -euo pipefail
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

usage() { echo "Usage: $0 -i <task.json> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do
  case "$opt" in i) manifest=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac
done
[[ -z "${manifest:-}" || -z "${output_dir:-}" ]] && usage
[[ -f "$manifest" ]] || { echo "Task manifest not found: $manifest" >&2; exit 1; }

input_file=$(primary_input)
mkdir -p "$output_dir"
output_dir=$(readlink -f "$output_dir")

binder_name=$(_parse_param binder_name binder)
chains=$(_parse_param chains A)
hotspots=$(_parse_param target_hotspot_residues "")
length_min=$(_parse_param length_min 65)
length_max=$(_parse_param length_max 150)
final_designs=$(_parse_param number_of_final_designs 1)
max_trajectories=$(_parse_param max_trajectories 20)
filters_preset=$(_parse_param filters_preset default_filters)
rank_by=$(_parse_param rank_by i_pTM)

[[ "$binder_name" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || { echo "Invalid binder_name" >&2; exit 1; }
[[ "$chains" =~ ^[A-Za-z0-9]+([,[:space:]]+[A-Za-z0-9]+)*$ ]] || { echo "Invalid chains" >&2; exit 1; }
[[ -z "$hotspots" || "$hotspots" =~ ^[A-Za-z0-9]+([,[:space:]]+[A-Za-z0-9]+)*$ ]] || {
  echo "Invalid target_hotspot_residues" >&2; exit 1;
}
(( length_min <= length_max )) || { echo "length_min must not exceed length_max" >&2; exit 1; }
(( final_designs <= max_trajectories )) || { echo "number_of_final_designs must not exceed max_trajectories" >&2; exit 1; }
chains=$(printf '%s' "$chains" | tr -s '[:space:],' ',')
hotspots=$(printf '%s' "$hotspots" | tr -s '[:space:],' ',')

filters_file="/opt/bindcraft/settings_filters/${filters_preset}.json"
[[ -f "$filters_file" ]] || { echo "Unknown filters preset: $filters_preset" >&2; exit 1; }

target_file="$output_dir/target.json"
advanced_file="$output_dir/advanced.json"
python3 - "$target_file" "$advanced_file" "$output_dir" "$input_file" "$binder_name" "$chains" \
  "$hotspots" "$length_min" "$length_max" "$final_designs" "$max_trajectories" <<'PY'
import json
import sys
from pathlib import Path

target_file, advanced_file, output_dir, input_file, binder_name, chains, hotspots = sys.argv[1:8]
length_min, length_max, final_designs, max_trajectories = map(int, sys.argv[8:12])
target = {
    "design_path": output_dir,
    "binder_name": binder_name,
    "starting_pdb": input_file,
    "chains": chains,
    "target_hotspot_residues": hotspots,
    "lengths": [length_min, length_max],
    "number_of_final_designs": final_designs,
}
with open("/opt/bindcraft/settings_advanced/default_4stage_multimer.json", encoding="utf-8") as handle:
    advanced = json.load(handle)
advanced.update(
    af_params_dir="/mnt/db/bindcraft/af_params",
    max_trajectories=max_trajectories,
    save_design_animations=False,
)
Path(target_file).write_text(json.dumps(target, indent=2), encoding="utf-8")
Path(advanced_file).write_text(json.dumps(advanced, indent=2), encoding="utf-8")
PY

echo "REVODESIGN_STAGE:parse"
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.9}"
export TF_FORCE_UNIFIED_MEMORY="${TF_FORCE_UNIFIED_MEMORY:-1}"
echo "REVODESIGN_STAGE:design"

if python3 /opt/bindcraft/bindcraft.py \
  --settings "$target_file" \
  --filters "$filters_file" \
  --advanced "$advanced_file" \
  --no-pyrosetta \
  --rank-by "$rank_by" \
  --verbose; then
  shopt -s nullglob
  accepted_designs=("$output_dir"/Accepted/*.pdb)
  if (( ${#accepted_designs[@]} < final_designs )); then
    echo "FreeBindCraft produced ${#accepted_designs[@]} of $final_designs requested accepted designs." >&2
    exit 1
  fi
  touch "$output_dir/task_finished"
  echo "FreeBindCraft complete."
else
  status=$?
  rm -f "$output_dir/task_finished"
  exit "$status"
fi
