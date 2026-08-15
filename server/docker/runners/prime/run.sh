#!/bin/bash
set -e
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

usage() { echo "Usage: $0 [ogt|dms] -i <task.json> -o <output_dir>"; exit 1; }
mode=ogt
if [[ "${1:-}" == "ogt" || "${1:-}" == "dms" ]]; then
    mode=$1
    shift
fi
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file")
input_file=$(primary_input)

output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Input not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

export PRIME_INPUT_FILE="${input_file}"
export PRIME_OUTPUT_DIR="${output_dir}"
export PRIME_VENDOR_DIR="${PRIME_VENDOR_DIR:-/opt/prime_model_code}"

# Preflight: the pinned Prime snapshots carry custom model code that must be
# vendored into the image (docker/runners/prime/vendor/). Weights-dir code is
# NEVER executed — tasks fail loudly instead of falling back to
# trust_remote_code.
if [[ "$mode" == "ogt" ]]; then
    model_dir="${PRIME_MODEL_DIR}"
else
    model_dir="${PRIME_DMS_MODEL_DIR}"
fi
snapshot="$(basename "$model_dir")"
[[ ! -f "$model_dir/config.json" ]] && { echo "Pinned PRIME model snapshot not found: $model_dir" >&2; exit 1; }
if [[ -f "$PRIME_VENDOR_DIR/manifest.sha256" ]]; then
    (cd "$(dirname "$model_dir")" && sha256sum -c "$PRIME_VENDOR_DIR/manifest.sha256") || {
        echo "PRIME weights integrity check FAILED: $model_dir does not match $PRIME_VENDOR_DIR/manifest.sha256" >&2
        exit 1
    }
fi
has_auto_map=$(python3 -c 'import json, sys; print("yes" if json.load(open(sys.argv[1])).get("auto_map") else "no")' "$model_dir/config.json" 2>/dev/null || echo no)
if [[ "$has_auto_map" == "yes" && ! -d "$PRIME_VENDOR_DIR/$snapshot" ]]; then
    echo "PRIME vendored model code missing: $PRIME_VENDOR_DIR/$snapshot" >&2
    echo "Copy the $snapshot snapshot's custom model code (modeling_*, tokenization_*, configuration_*" >&2
    echo "referenced by its config.json) into docker/runners/prime/vendor/$snapshot/ per vendor/README.md," >&2
    echo "then rebuild the image." >&2
    exit 1
fi
if [[ "$mode" == "ogt" ]]; then
echo "REVODESIGN_STAGE:prime"
python3 - <<'PY'
import sys, os, json, importlib
from pathlib import Path
import torch, pandas as pd
from Bio import SeqIO
from transformers import AutoConfig, AutoModel, AutoTokenizer

def load_vendored_code(model_dir):
    """Import and register the snapshot's custom model code from the image's
    vendored copy (PRIME_VENDOR_DIR). Fail closed: weights-dir code is never executed."""
    vendored_root = Path(os.environ['PRIME_VENDOR_DIR'])
    cfg = json.loads((model_dir / 'config.json').read_text(encoding='utf-8'))
    auto_map = cfg.get('auto_map')
    if not auto_map:
        return
    code_dir = vendored_root / model_dir.name
    if not code_dir.is_dir():
        raise SystemExit(
            f'PRIME vendored model code missing: {code_dir}\n'
            f"Copy the {model_dir.name} snapshot's custom model code (the modeling_*, tokenization_*, "
            f'configuration_* modules referenced by its config.json) into '
            f'docker/runners/prime/vendor/{model_dir.name}/ per vendor/README.md, then rebuild the image.'
        )
    sys.path.insert(0, str(code_dir))
    model_type = cfg.get('model_type')
    if not model_type:
        raise SystemExit(f'PRIME {model_dir.name} config.json has no model_type')

    def _entries(value):
        # config.json auto_map values are conventionally strings
        # ("AutoModel": "modeling_prime.PrimeModel"); only tokenizer maps
        # use [slow, fast] lists. Normalize both shapes.
        if isinstance(value, str):
            return [value]
        return list(value)

    def _load(entry):
        module_name, _, class_name = entry.rpartition('.')
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise SystemExit(
                f'PRIME vendored module import failed: {module_name}.py from {code_dir}: {exc}\n'
                'See docker/runners/prime/vendor/README.md.'
            ) from exc
        cls = getattr(module, class_name, None)
        if cls is None:
            raise SystemExit(
                f'PRIME vendored module {module_name}.py has no class {class_name} (from {code_dir}). '
                'See docker/runners/prime/vendor/README.md.'
            )
        return cls

    config_class = None
    for entry in _entries(auto_map.get('AutoConfig', ())):
        config_class = _load(entry)
        AutoConfig.register(model_type, config_class)
    if config_class is None:
        raise SystemExit(f'PRIME {model_dir.name} config.json auto_map has no AutoConfig entry')
    for auto_key, entries in auto_map.items():
        if auto_key == 'AutoConfig':
            continue
        for index, entry in enumerate(_entries(entries)):
            cls = _load(entry)
            if auto_key == 'AutoModel':
                AutoModel.register(config_class, cls)
            elif auto_key == 'AutoTokenizer':
                # Transformers convention: auto_map entries are [slow, fast].
                if index == 0:
                    AutoTokenizer.register(config_class, slow_tokenizer_class=cls)
                else:
                    AutoTokenizer.register(config_class, fast_tokenizer_class=cls)
            else:
                print(f'PRIME: ignoring unregistered auto_map entry {auto_key}', file=sys.stderr)

input_fasta = Path(os.environ['PRIME_INPUT_FILE'])
output_dir = Path(os.environ['PRIME_OUTPUT_DIR'])
model_dir = Path(os.environ['PRIME_MODEL_DIR'])
if not (model_dir / 'config.json').is_file():
    raise FileNotFoundError(f'Pinned Pro-Prime OGT model snapshot not found: {model_dir}')
load_vendored_code(model_dir)
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Loading ProPrime_650M_OGT_Prediction on {device}')
tokenizer = AutoTokenizer.from_pretrained(
    model_dir, trust_remote_code=False, local_files_only=True
)
model = AutoModel.from_pretrained(
    model_dir, trust_remote_code=False, local_files_only=True
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
PY
else
echo "REVODESIGN_STAGE:prime_dms"
python3 - <<'PY'
import json
import os
import sys
import importlib
from pathlib import Path

import pandas as pd
import torch
from Bio import SeqIO
from transformers import AutoConfig, AutoModel, AutoTokenizer

def load_vendored_code(model_dir):
    """Import and register the snapshot's custom model code from the image's
    vendored copy (PRIME_VENDOR_DIR). Fail closed: weights-dir code is never executed."""
    vendored_root = Path(os.environ['PRIME_VENDOR_DIR'])
    cfg = json.loads((model_dir / 'config.json').read_text(encoding='utf-8'))
    auto_map = cfg.get('auto_map')
    if not auto_map:
        return
    code_dir = vendored_root / model_dir.name
    if not code_dir.is_dir():
        raise SystemExit(
            f'PRIME vendored model code missing: {code_dir}\n'
            f"Copy the {model_dir.name} snapshot's custom model code (the modeling_*, tokenization_*, "
            f'configuration_* modules referenced by its config.json) into '
            f'docker/runners/prime/vendor/{model_dir.name}/ per vendor/README.md, then rebuild the image.'
        )
    sys.path.insert(0, str(code_dir))
    model_type = cfg.get('model_type')
    if not model_type:
        raise SystemExit(f'PRIME {model_dir.name} config.json has no model_type')

    def _entries(value):
        # config.json auto_map values are conventionally strings
        # ("AutoModel": "modeling_prime.PrimeModel"); only tokenizer maps
        # use [slow, fast] lists. Normalize both shapes.
        if isinstance(value, str):
            return [value]
        return list(value)

    def _load(entry):
        module_name, _, class_name = entry.rpartition('.')
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise SystemExit(
                f'PRIME vendored module import failed: {module_name}.py from {code_dir}: {exc}\n'
                'See docker/runners/prime/vendor/README.md.'
            ) from exc
        cls = getattr(module, class_name, None)
        if cls is None:
            raise SystemExit(
                f'PRIME vendored module {module_name}.py has no class {class_name} (from {code_dir}). '
                'See docker/runners/prime/vendor/README.md.'
            )
        return cls

    config_class = None
    for entry in _entries(auto_map.get('AutoConfig', ())):
        config_class = _load(entry)
        AutoConfig.register(model_type, config_class)
    if config_class is None:
        raise SystemExit(f'PRIME {model_dir.name} config.json auto_map has no AutoConfig entry')
    for auto_key, entries in auto_map.items():
        if auto_key == 'AutoConfig':
            continue
        for index, entry in enumerate(_entries(entries)):
            cls = _load(entry)
            if auto_key == 'AutoModel':
                AutoModel.register(config_class, cls)
            elif auto_key == 'AutoTokenizer':
                # Transformers convention: auto_map entries are [slow, fast].
                if index == 0:
                    AutoTokenizer.register(config_class, slow_tokenizer_class=cls)
                else:
                    AutoTokenizer.register(config_class, fast_tokenizer_class=cls)
            else:
                print(f'PRIME: ignoring unregistered auto_map entry {auto_key}', file=sys.stderr)

input_fasta = Path(os.environ["PRIME_INPUT_FILE"])
output_dir = Path(os.environ["PRIME_OUTPUT_DIR"])
model_dir = Path(os.environ["PRIME_DMS_MODEL_DIR"])
if not (model_dir / "config.json").is_file():
    raise FileNotFoundError(f"Pinned PRIME mutation model snapshot not found: {model_dir}")

task_inputs = json.load(open(os.environ["TASK_MANIFEST"]))["files"]
input_paths = [Path(item["path"]).resolve() for item in task_inputs]
if input_fasta.resolve() not in input_paths:
    input_paths.insert(0, input_fasta)
records = []
for path in input_paths:
    for record in SeqIO.parse(path, "fasta"):
        records.append((record.id, str(path), str(record.seq).upper()))
if not records:
    raise ValueError("FASTA input must contain at least one protein sequence")

reference_id, reference_path, sequence = records[0]
amino_acids = tuple("ACDEFGHIKLMNPQRSTVWY")
for record_id, _path, record_sequence in records:
    invalid = sorted(set(record_sequence) - set(amino_acids))
    if invalid:
        raise ValueError(f"Sequence {record_id!r} contains unsupported residues: {invalid}")

load_vendored_code(model_dir)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=False, local_files_only=True)
model = AutoModel.from_pretrained(model_dir, trust_remote_code=False, local_files_only=True)
model.eval().to(device)
tokenized = tokenizer(sequence, return_tensors="pt")
input_ids = tokenized.input_ids.to(device)
attention_mask = tokenized.attention_mask.to(device)
with torch.no_grad():
    logits = model(input_ids, attention_mask=attention_mask).logits[0, 1:-1, :].log_softmax(dim=-1)
vocab = tokenizer.get_vocab()

def mutation_score(wildtype, substitutions):
    return sum(
        (
            logits[position - 1, vocab[mutant]]
            - logits[position - 1, vocab[wildtype[position - 1]]]
        ).item()
        for position, mutant in substitutions
    )

if len(records) == 1:
    rows = []
    for position, wildtype in enumerate(sequence, start=1):
        for mutant in amino_acids:
            if mutant == wildtype:
                continue
            rows.append(
                {
                    "position": position,
                    "wildtype": wildtype,
                    "mutant_residue": mutant,
                    "mutant": f"{wildtype}{position}{mutant}",
                    "predict_score": mutation_score(sequence, [(position, mutant)]),
                }
            )
    out = output_dir / f"{input_fasta.stem}_prime_dms.csv"
else:
    rows = []
    for record_id, source_path, variant_sequence in records[1:]:
        if len(variant_sequence) != len(sequence):
            raise ValueError(
                f"Combinatorial sequence {record_id!r} length {len(variant_sequence)} does not match "
                f"reference {reference_id!r} length {len(sequence)}"
            )
        substitutions = [
            (position, mutant)
            for position, (wildtype, mutant) in enumerate(zip(sequence, variant_sequence), start=1)
            if mutant != wildtype
        ]
        mutation_label = ":".join(
            f"{sequence[position - 1]}{position}{mutant}" for position, mutant in substitutions
        ) or "WT"
        rows.append(
            {
                "reference_id": reference_id,
                "sequence_id": record_id,
                "source_file": Path(source_path).name,
                "mutations": mutation_label,
                "mutation_count": len(substitutions),
                "predict_score": mutation_score(sequence, substitutions),
            }
        )
    out = output_dir / f"{input_fasta.stem}_prime_combinatorial.csv"

pd.DataFrame(rows).to_csv(out, index=False)
print(f"Done: {out}")
PY
fi

touch "${output_dir}/task_finished"
echo "Pro-Prime complete."
