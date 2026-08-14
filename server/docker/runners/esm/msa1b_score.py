#!/usr/bin/env python3
# REvoDesign ESM runner — MSA-1B masked-marginal variant-effect profile.
#
# Contract: -i <a3m> -o <output_dir> -m <torch_hub_dir>
# Writes per-position log-probability and entropy profiles for the query
# (first) sequence of the alignment, computed with ESM-MSA-1b.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import argparse
import csv
import itertools
import string

import torch

DELETE_KEYS = dict.fromkeys(string.ascii_lowercase)
DELETE_KEYS["."] = None
DELETE_KEYS["*"] = None
TRANSLATION = str.maketrans(DELETE_KEYS)


def remove_insertions(sequence: str) -> str:
    """Remove insertions (lowercase/. /*) — required to load a3m rows."""
    return sequence.translate(TRANSLATION)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ESM-MSA-1b masked-marginal profile")
    parser.add_argument("-i", "--input", required=True, help="Input alignment (.a3m)")
    parser.add_argument("-o", "--output-dir", required=True)
    parser.add_argument("-m", "--model-pth", required=True, help="torch.hub cache dir")
    parser.add_argument("--msa-samples", type=int, default=32, help="MSA rows to load")
    return parser.parse_args()


def read_a3m(path: str, nseq: int) -> list[str]:
    rows = []
    # PTC-W6004: sandboxed runner; path is the mounted read-only input snapshot
    with open(path, encoding="utf-8") as handle:  # skipcq: PTC-W6004
        for record in itertools.islice(_fasta_blocks(handle), nseq):
            rows.append(remove_insertions(record[1]))
    return rows


def _fasta_blocks(handle):
    """Yield (header, sequence) pairs; sequence lines are joined."""
    header, buf = None, []
    for line in handle:
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                yield header, "".join(buf)
            header, buf = line[1:], []
        else:
            buf.append(line)
    if header is not None:
        yield header, "".join(buf)


def main() -> None:
    args = parse_args()
    torch.hub.set_dir(args.model_pth)
    import esm2

    model, alphabet = esm2.pretrained.esm_msa1b_t12_100M_UR50S()
    model = model.eval().cuda()

    rows = read_a3m(args.input, args.msa_samples)
    query = rows[0]
    converter = alphabet.get_batch_converter()
    msa = [(f"seq{i}", seq) for i, seq in enumerate(rows)]
    _, _, tokens = converter([msa])

    # masked marginals over the query (first) sequence
    all_log_probs = []
    for i in range(1, len(query) + 1):
        masked = tokens.clone()
        masked[0, 0, i] = alphabet.mask_idx
        with torch.no_grad():
            logits = model(masked.cuda())["logits"]
        all_log_probs.append(torch.log_softmax(logits[0, 0, i], dim=-1).cpu())
    log_probs = torch.stack(all_log_probs)  # [L, V]

    # entropy per position = -sum p log p
    probs = torch.exp(log_probs)
    entropy = -(probs * log_probs).sum(dim=-1)

    with open(f"{args.output_dir}/msa1b_profile.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["position", "residue", "log_prob", "entropy"])
        for i, residue in enumerate(query):
            writer.writerow([i + 1, residue, f"{log_probs[i, alphabet.get_idx(residue)].item():.6f}",
                             f"{entropy[i].item():.6f}"])

    wt_log_probs = torch.stack(
        [log_probs[i, alphabet.get_idx(residue)] for i, residue in enumerate(query)]
    )
    mean_entropy = entropy.mean().item()
    with open(f"{args.output_dir}/msa1b_summary.json", "w") as handle:
        import json

        json.dump(
            {
                "model": "esm_msa1b_t12_100M_UR50S",
                "sequence_length": len(query),
                "msa_rows": len(rows),
                "mean_entropy": mean_entropy,
                "mean_log_prob": wt_log_probs.mean().item(),
            },
            handle,
            indent=2,
        )
    print(f"msa1b profile complete: {len(query)} positions, mean entropy {mean_entropy:.4f}")


if __name__ == "__main__":
    main()
