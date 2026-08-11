#!/bin/bash
# REvoDesign OpenDDE runner — all-atom co-folding and structure prediction.
#
# Runner contract:
#   1. Reads input JSON from /workspace/inputs/
#   2. Writes output to /workspace/outputs/
#   3. Emits REVODESIGN_STAGE:<marker> on stdout
#   4. Accepts -i <input_json> -o <output_dir>
#   5. Exits 0 on success

set -euo pipefail

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

# OpenDDE's MSA client writes an ``*-update-msa.json`` file next to the input
# JSON.  Production input snapshots are deliberately mounted read-only, so run
# inference from a task-private writable copy of the complete snapshot.  Copying
# the whole snapshot also preserves relative references to auxiliary inputs.
case "$input_file" in
    */inputs/*)
        input_root="${input_file%%/inputs/*}/inputs"
        input_relative_path="${input_file#"$input_root"/}"
        ;;
    *)
        input_root=$(dirname "$input_file")
        input_relative_path=$(basename "$input_file")
        ;;
esac
opendde_input_root=$(mktemp -d "${TMPDIR:-/tmp}/revodesign-opendde.XXXXXX")
cleanup_opendde_inputs() {
    rm -rf -- "$opendde_input_root"
}
trap cleanup_opendde_inputs EXIT
cp -a -- "$input_root"/. "$opendde_input_root"/
writable_input_file="$opendde_input_root/$input_relative_path"

if [[ ! -f "$writable_input_file" ]]; then
    echo "Failed to prepare writable OpenDDE input snapshot" >&2
    exit 1
fi

# Template inference downloads missing mmCIF files beneath
# ``$OPENDDE_ROOT_DIR/search_database/mmcif``.  Keep the production database
# mount read-only and expose its trusted contents through symlinks inside a
# task-private writable root.  Newly fetched template files then live only for
# this task and disappear with the other temporary inputs.
readonly_opendde_root="${OPENDDE_ROOT_DIR:-/mnt/db/opendde}"
writable_opendde_root="$opendde_input_root/.opendde-runtime"
mkdir -p "$writable_opendde_root/search_database/mmcif"
for source_path in "$readonly_opendde_root"/*; do
    [[ -e "$source_path" ]] || continue
    source_name=$(basename "$source_path")
    [[ "$source_name" == "search_database" ]] && continue
    ln -s "$source_path" "$writable_opendde_root/$source_name"
done
if [[ -d "$readonly_opendde_root/search_database" ]]; then
    for source_path in "$readonly_opendde_root/search_database"/*; do
        [[ -e "$source_path" ]] || continue
        source_name=$(basename "$source_path")
        [[ "$source_name" == "mmcif" ]] && continue
        ln -s "$source_path" "$writable_opendde_root/search_database/$source_name"
    done
fi
if [[ -d "$readonly_opendde_root/search_database/mmcif" ]]; then
    for source_path in "$readonly_opendde_root/search_database/mmcif"/*; do
        [[ -e "$source_path" ]] || continue
        ln -s "$source_path" "$writable_opendde_root/search_database/mmcif/$(basename "$source_path")"
    done
fi
export OPENDDE_ROOT_DIR="$writable_opendde_root"

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
# Use the supported PyTorch triangle kernels and disable efficient fusion.
# The auto-selected cuequivariance/Triton path compiles a launcher at runtime
# and therefore requires a C toolchain, which is intentionally absent from the
# production inference image.
echo "REVODESIGN_STAGE:opendde"

opendde pred \
    -i "$writable_input_file" \
    -o "$output_dir" \
    -n "$MODEL_NAME" \
    --sample "$NUM_SAMPLES" \
    --step "$NUM_STEPS" \
    --cycle "$NUM_CYCLES" \
    --use_msa "$USE_MSA" \
    --use_template "$USE_TEMPLATE" \
    --trimul_kernel torch \
    --triatt_kernel torch \
    --enable_fusion false \
    --use_rna_msa false

# Some OpenDDE versions catch per-input inference exceptions and still exit 0,
# leaving MSA intermediates plus ERR/error.txt.  Only a non-empty predicted
# structure proves successful inference.
if [[ -d "$output_dir/ERR" ]] && find "$output_dir/ERR" -type f -size +0c -print -quit | grep -q .; then
    echo "OpenDDE reported an internal inference error" >&2
    exit 1
fi
if ! find "$output_dir" -type f -size +0c \
    \( -iname '*.pdb' -o -iname '*.cif' -o -iname '*.mmcif' \) \
    -print -quit | grep -q .; then
    echo "OpenDDE exited without producing a structure artifact" >&2
    exit 1
fi

touch "${output_dir}/task_finished"
echo "OpenDDE inference complete."
