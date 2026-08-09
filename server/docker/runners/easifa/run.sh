#!/bin/bash
set -e
usage() { echo "Usage: $0 -i <input_dir> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file"); output_dir=$(readlink -f "$output_dir")
mkdir -p "$output_dir"

_parse_param() { python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"; }
: "${TASK_TYPE_EASIFA:=$(_parse_param task_subtype)}"
: "${TASK_TYPE_EASIFA:=active-site-position-prediction}"

echo "REVODESIGN_STAGE:easifa"
cd "${EASIFA_PATH}"
python3 main_test.py --task_type "$TASK_TYPE_EASIFA" --gpu 0 --dataset_path "$(dirname "$input_file")" --checkpoint /mnt/db/weights/easifa

touch "${output_dir}/task_finished"
echo "EasIFA complete."
