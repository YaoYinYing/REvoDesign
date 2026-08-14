#!/bin/bash
# REvoDesign Pythia-ddG runner — masked ΔΔG prediction from PDB structure.
#
# Runner contract:
#   1. Reads input PDB from /workspace/inputs/
#   2. Writes output to /workspace/outputs/
#   3. Emits REVODESIGN_STAGE:<marker> on stdout
#   4. Accepts -i <input_pdb> -o <output_dir>
#   5. Exits 0 on success

set -e
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

REVODESIGN_RUNSCRIPT_PATH=$(readlink -f "$(dirname "$0")")

usage() {
    echo ""
    echo "Usage: $0 <OPTIONS>"
    echo "Required Parameters:"
    echo "      -i  <pdb>         Input PDB structure file"
    echo "      -o  <output_dir>  Output directory"
    echo ""
    exit 1
}

while getopts ":i:o:" opt; do
    case "${opt}" in
        i) input_pdb=$OPTARG ;;
        o) output_dir=$OPTARG ;;
        ?) usage ;;
    esac
done

if [[ -z "${input_pdb:-}" ]]; then
    echo "Missing required option: -i <pdb>"
    usage
fi

input_pdb=$(python3 -c "import json,os;print(json.load(open(os.environ['TASK_MANIFEST']))['files'][0]['path'])")
input_pdb=$(primary_input)
if [[ -z "${output_dir:-}" ]]; then
    echo "Missing required option: -o <output_dir>"
    usage
fi

input_pdb=$(readlink -f "$input_pdb")
output_dir=$(readlink -f "$output_dir")

if [[ ! -f "$input_pdb" ]]; then
    echo "PDB file not found: $input_pdb"
    exit 1
fi

mkdir -p "$output_dir"

echo "Processing $input_pdb ..."
echo "Output directory: $output_dir"

echo "REVODESIGN_STAGE:pythia_ddg"

python "${REVODESIGN_RUNSCRIPT_PATH}/pythia/masked_ddg_scan.py" \
    --pdb_filename "$input_pdb" \
    --save_dir "$output_dir" \
    --device cpu

touch "${output_dir}/task_finished"
echo "Pythia-ddG prediction complete."
