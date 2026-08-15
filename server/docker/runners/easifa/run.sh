#!/bin/bash
set -euo pipefail
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

usage() { echo "Usage: $0 -i <task.json> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do
  case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac
done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file")
input_file=$(primary_input)

output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file" >&2; exit 1; }
mkdir -p "$output_dir"

# Apptainer shares the host /tmp by default. Use a private directory so jobs
# submitted by different users cannot inherit an unwritable cache directory.
runtime_tmp=${TMPDIR:-/tmp}
[[ -d "$runtime_tmp" && -w "$runtime_tmp" ]] || runtime_tmp=/tmp
easifa_tmp=$(mktemp -d "${runtime_tmp%/}/revodesign-easifa.XXXXXX")
trap 'rm -rf -- "$easifa_tmp"' EXIT
export TORCH_EXTENSIONS_DIR="$easifa_tmp/torch-extensions"
export MPLCONFIGDIR="$easifa_tmp/matplotlib"
mkdir -p "$TORCH_EXTENSIONS_DIR" "$MPLCONFIGDIR"

reaction_smiles=$(_parse_param reaction_smiles)
max_length=$(_parse_param max_length); : "${max_length:=1000}"
pretty=$(_parse_param pretty); : "${pretty:=true}"
verbose=$(_parse_param verbose); : "${verbose:=false}"
result_json="${output_dir}/easifa_result.json"

model_name=wo_reactions
[[ -n "$reaction_smiles" ]] && model_name=all_features
easifa_args=(
  --enzyme-structure "$input_file"
  --output "$result_json"
  --checkpoint-dir "$EASIFA_CHECKPOINT_DIR"
  --model-to-use "$model_name"
  --max-length "$max_length"
  --device cuda:0
)
if [[ -n "$reaction_smiles" ]]; then
  easifa_args+=(--rxn-smiles "$reaction_smiles")
fi
[[ "$pretty" == "true" ]] && easifa_args+=(--pretty)
[[ "$verbose" == "true" ]] && easifa_args+=(--verbose)

echo "REVODESIGN_STAGE:easifa"
python3 -c 'import torch; assert torch.cuda.is_available(), "EasIFA requires an allocated CUDA GPU"'
easifa-predict "${easifa_args[@]}"
[[ -s "$result_json" ]] || { echo "EasIFA did not produce a result JSON" >&2; exit 1; }

# Publish a table alongside the full upstream JSON so residue predictions are
# directly previewable and downloadable through the manifest-first result UI.
EASIFA_RESULT_JSON="$result_json" EASIFA_RESULT_CSV="${output_dir}/active_sites.csv" python3 - <<'PY'
import csv
import json
import os

with open(os.environ["EASIFA_RESULT_JSON"], encoding="utf-8") as handle:
    result = json.load(handle)

mapping = result.get("site_type_mapping", {})
rows = []
if result.get("multi_chain"):
    chains = result.get("chains", {})
else:
    chains = {"": result}
for chain, payload in chains.items():
    predictions = payload.get("predictions", {})
    labels = predictions.get("labels", [])
    probabilities = predictions.get("probabilities", [])
    sequence = payload.get("sequence") or result.get("input", {}).get("enzyme_sequence") or ""
    for index, label in enumerate(labels, start=1):
        probability = probabilities[index - 1] if index <= len(probabilities) else []
        rows.append({
            "chain": chain,
            "residue_index": index,
            "residue": sequence[index - 1] if index <= len(sequence) else "",
            "site_class": label,
            "site_name": mapping.get(str(label), str(label)),
            "probabilities": json.dumps(probability, separators=(",", ":")),
        })

with open(os.environ["EASIFA_RESULT_CSV"], "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=(
        "chain", "residue_index", "residue", "site_class", "site_name", "probabilities"
    ))
    writer.writeheader()
    writer.writerows(rows)
PY

touch "${output_dir}/task_finished"
echo "EasIFA2 complete."
