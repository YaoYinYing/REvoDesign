# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

# REvoDesign ESM-1v runner — zero-shot variant effect prediction via esm2.
#
# Adapted from RosettaWorkshop/2._Working/1._MutationEffects/ESM-1v
# (generate_dms.py + predict.py). Generates all single-point mutations of a
# wild-type sequence, scores each with the ESM-1v 5-model ensemble
# (wt-marginals strategy), and writes a CSV with per-model and mean scores.
#
# Usage: python esm1v_score.py -i wt.fasta -o output_dir [-m /mnt/db/weights/esm]

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import torch

from esm2 import Alphabet, pretrained
from esm2.data import read_fasta

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%y/%m/%d %H:%M:%S",
)

ALPHABET = "ARNDCQEGHILKMFPSTWYV"

# ESM-1v ensemble checkpoint filenames (5 members).
ESM1V_MODELS = [f"esm1v_t33_650M_UR90S_{i}" for i in range(1, 6)]


def label_mutation(mutation: str, sequence: str, token_probs: torch.Tensor, alphabet: Alphabet) -> float:
    """wt-marginals score: log P(mutant) - log P(wild-type) at the mutated position.

    One forward pass over the wild-type sequence yields the marginal token
    probabilities; each mutation is read off at its position (BOS at token 0).
    """
    wt, mt = mutation[0], mutation[-1]
    pos = int(mutation[1:-1]) - 1  # label positions are 1-based
    if sequence[pos] != wt:
        raise ValueError(f"Wild-type mismatch at position {pos + 1}: {mutation}")
    wt_encoded, mt_encoded = alphabet.get_idx(wt), alphabet.get_idx(mt)
    # +1 skips the BOS token
    return (token_probs[0, 1 + pos, mt_encoded] - token_probs[0, 1 + pos, wt_encoded]).item()


def main() -> None:
    parser = argparse.ArgumentParser(description="ESM-1v zero-shot variant effect prediction")
    parser.add_argument("-i", "--fasta", type=Path, required=True, help="Input FASTA file (single WT sequence)")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output directory for CSV")
    parser.add_argument(
        "-m",
        "--model-pth",
        type=Path,
        default=Path("/mnt/db/weights/esm"),
        help="Parent path to pretrained ESM data directory",
    )
    args = parser.parse_args()

    if not args.fasta.exists():
        raise FileNotFoundError(args.fasta)
    args.output.mkdir(parents=True, exist_ok=True)

    sequences = list(read_fasta(args.fasta))
    if len(sequences) != 1:
        logger.warning("Expected a single WT sequence, got %d; scoring the first", len(sequences))
    header, sequence = sequences[0]
    logger.info("WT sequence %s (%s): %d residues", header, args.fasta, len(sequence))

    # All single-point mutations: 20 amino acids x sequence length.
    mutations = [f"{sequence[p]}{p + 1}{aa}" for p in range(len(sequence)) for aa in ALPHABET]
    logger.info("Scoring %d single-point mutations", len(mutations))

    # ESM-1v ensemble checkpoints.
    checkpoints = [args.model_pth / "checkpoints" / f"{name}.pt" for name in ESM1V_MODELS]
    missing = [str(p) for p in checkpoints if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "ESM-1v ensemble checkpoints not found: " + ", ".join(missing) + ". "
            "Mount pre-downloaded weights at /mnt/db/weights/esm."
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Scoring on %s", device)

    df = pd.DataFrame({"mutation": mutations})
    for i, checkpoint in enumerate(checkpoints, start=1):
        logger.info("Loading ensemble model %d/%d: %s", i, len(checkpoints), checkpoint.name)
        model, alphabet = pretrained.load_model_and_alphabet(str(checkpoint))
        model = model.eval().to(device)

        # wt-marginals: single forward pass on the wild-type sequence.
        _, _, batch_tokens = alphabet.get_batch_converter()([("protein1", sequence)])
        with torch.no_grad():
            token_probs = torch.log_softmax(model(batch_tokens.to(device))["logits"], dim=-1)

        df[f"score_{i}"] = [label_mutation(m, sequence, token_probs, alphabet) for m in mutations]

    df["mean_score"] = df[[f"score_{i}" for i in range(1, 6)]].mean(axis=1)

    output_file = args.output / f"{header}_esm1v_scores.csv"
    df.to_csv(output_file, index=False)
    logger.info("Wrote %d mutation scores to %s", len(df), output_file)


if __name__ == "__main__":
    main()
