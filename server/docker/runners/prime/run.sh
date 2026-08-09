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

python3 -c "
import sys, os
from pathlib import Path
import torch, pandas as pd
from Bio import SeqIO
from transformers import AutoModel

input_fasta = Path('${input_file}')
output_dir = Path('${output_dir}')
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Loading Prime_690M on {device}')
model = AutoModel.from_pretrained('AI4Protein/Prime_690M', trust_remote_code=True, cache_dir='/mnt/db/weights/prime')
model = model.eval().to(device)

seqs = list(SeqIO.parse(input_fasta, 'fasta'))
print(f'Loaded {len(seqs)} sequences')
results = []
for rec in seqs:
    with torch.no_grad():
        ogt = model.predict_ogt([str(rec.seq)], device=device)[0]
    results.append({'id': rec.id, 'ogt': float(ogt)})

df = pd.DataFrame(results)
out = output_dir / f'{input_fasta.stem}_ogt.csv'
df.to_csv(out, index=False)
print(f'Done: {out}')
"

touch "${output_dir}/task_finished"
echo "Pro-Prime complete."
