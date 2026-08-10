#!/bin/bash
set -e

usage() { echo "Usage: $0 -i <fasta> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file")
output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

echo "REVODESIGN_STAGE:prime"

export PRIME_INPUT_FILE="${input_file}"
export PRIME_OUTPUT_DIR="${output_dir}"
python3 -c "
import sys, os
from pathlib import Path
import torch, pandas as pd
from Bio import SeqIO
from transformers import AutoModel, AutoTokenizer

input_fasta = Path(os.environ['PRIME_INPUT_FILE'])
output_dir = Path(os.environ['PRIME_OUTPUT_DIR'])
model_dir = Path(os.environ['PRIME_MODEL_DIR'])
if not (model_dir / 'config.json').is_file():
    raise FileNotFoundError(f'Pinned Pro-Prime OGT model snapshot not found: {model_dir}')
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Loading ProPrime_650M_OGT_Prediction on {device}')
tokenizer = AutoTokenizer.from_pretrained(
    model_dir, trust_remote_code=True, local_files_only=True
)
model = AutoModel.from_pretrained(
    model_dir, trust_remote_code=True, local_files_only=True
)
model = model.eval().to(device)

seqs = list(SeqIO.parse(input_fasta, 'fasta'))
print(f'Loaded {len(seqs)} sequences')
results = []
for rec in seqs:
    with torch.no_grad():
        inputs = tokenizer([str(rec.seq)], padding=True, return_tensors='pt')
        inputs = {name: value.to(device) for name, value in inputs.items()}
        outputs = model(**inputs)
        ogt = outputs.predicted_values.reshape(-1)[0]
    results.append({'id': rec.id, 'ogt': float(ogt)})

df = pd.DataFrame(results)
out = output_dir / f'{input_fasta.stem}_ogt.csv'
df.to_csv(out, index=False)
print(f'Done: {out}')
"

touch "${output_dir}/task_finished"
echo "Pro-Prime complete."
