#!/bin/bash
set -e
usage() { echo "Usage: $0 -i <fasta> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file"); output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

_parse_param() { python3 -c "import json,os; print(json.loads(os.environ.get('TASK_PARAMS','{}')).get('$1',''))"; }
: "${NUM_SAMPLES:=$(_parse_param num_samples)}"; : "${NUM_SAMPLES:=10}"

# Extract sequence from FASTA
SEQ=$(python3 -c "from Bio import SeqIO; print(str(next(SeqIO.parse('${input_file}','fasta')).seq))")

echo "REVODESIGN_STAGE:bioemu"
python3 -m bioemu.sample --sequence "$SEQ" --num_samples "$NUM_SAMPLES" --output_dir "$output_dir"

touch "${output_dir}/task_finished"
echo "BioEmu complete."
