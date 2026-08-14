# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

# REvoDesign ESM-IF1 runner — inverse folding (sequence design from backbone).
#
# Adapted from esm2/examples/inverse_folding/sample_sequences.py. Samples
# amino-acid sequences that fold to the input PDB backbone with ESM-IF1
# (GVP-Transformer) and writes them to a FASTA file.
#
# Usage: python esm_if1_design.py -i input.pdb -o output_dir [-m /mnt/db/weights/esm]

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import numpy as np
import torch

import esm2
import esm2.inverse_folding  # noqa: F401  (registers esm2.inverse_folding.util)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%y/%m/%d %H:%M:%S",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="ESM-IF1 inverse folding: sample sequences from a backbone")
    parser.add_argument("-i", "--pdb", type=Path, required=True, help="Input PDB structure file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output directory")
    parser.add_argument(
        "-m",
        "--model-pth",
        type=Path,
        default=Path("/mnt/db/weights/esm"),
        help="Parent path to pretrained ESM data directory",
    )
    parser.add_argument("--temperature", type=float, default=1.0, help="Sampling temperature (higher = more diverse)")
    parser.add_argument("--num-samples", type=int, default=1, help="Number of sequences to sample")
    parser.add_argument("--chain", type=str, default="A", help="Chain ID to design")
    args = parser.parse_args()

    if not args.pdb.exists():
        raise FileNotFoundError(f"PDB file not found: {args.pdb}")
    args.output.mkdir(parents=True, exist_ok=True)

    # Use pre-downloaded ESM weights from model_pth (torch.hub cache layout).
    if not args.model_pth.exists() or "checkpoints" not in os.listdir(args.model_pth):
        raise FileNotFoundError(
            f"Checkpoint directory not found at {args.model_pth}/checkpoints/. "
            "Mount pre-downloaded weights at /mnt/db/weights/esm."
        )
    torch.hub.set_dir(str(args.model_pth))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using device: %s", device)

    logger.info("Loading ESM-IF1 model")
    model, _ = esm2.pretrained.esm_if1_gvp4_t16_142M_UR50()
    model = model.eval().to(device)

    # Backbone coordinates in the format expected by the GVP encoder.
    coords, native_seq = esm2.inverse_folding.util.load_coords(str(args.pdb), args.chain)
    logger.info("Native sequence (chain %s): %s", args.chain, native_seq)

    output_file = args.output / f"{args.pdb.stem}_designs.fasta"
    with open(output_file, "w") as f:
        for i in range(args.num_samples):
            with torch.no_grad():
                sampled_seq = model.sample(coords, temperature=args.temperature, device=device)
            recovery = float(np.mean([a == b for a, b in zip(native_seq, sampled_seq)]))
            logger.info("Sample %d/%d: %s (recovery %.2f)", i + 1, args.num_samples, sampled_seq, recovery)
            f.write(f">design_{i + 1}\n{sampled_seq}\n")
    logger.info("Wrote %d designed sequences to %s", args.num_samples, output_file)


if __name__ == "__main__":
    main()
