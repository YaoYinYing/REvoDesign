# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

#!/usr/bin/env python3
# REvoDesign ESMFold runner — structure prediction from FASTA via esm2.
#
# Adapted from RosettaWorkshop/2._Working/4._StructureModeling/ESMFold.
# Uses pre-downloaded checkpoints at /mnt/db/weights/esm/checkpoints/.
#
# Usage: python esmfold_inference.py -i input.fasta -o output_dir [-m /mnt/db/weights/esm]

from __future__ import annotations

import argparse
import logging
import os
import sys
import typing as T
from pathlib import Path
from timeit import default_timer as timer

import torch

import esm2
from esm2.data import read_fasta

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%y/%m/%d %H:%M:%S",
)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def create_batched_sequence_dataset(
    sequences: T.List[T.Tuple[str, str]], max_tokens_per_batch: int = 1024
) -> T.Generator[T.Tuple[T.List[str], T.List[str]], None, None]:
    batch_headers, batch_sequences, num_tokens = [], [], 0
    for header, seq in sequences:
        if (len(seq) + num_tokens > max_tokens_per_batch) and num_tokens > 0:
            yield batch_headers, batch_sequences
            batch_headers, batch_sequences, num_tokens = [], [], 0
        batch_headers.append(header)
        batch_sequences.append(seq)
        num_tokens += len(seq)
    yield batch_headers, batch_sequences


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ESMFold structure prediction from FASTA")
    parser.add_argument("-i", "--fasta", type=Path, required=True, help="Input FASTA file")
    parser.add_argument("-o", "--pdb", type=Path, required=True, help="Output PDB directory")
    parser.add_argument(
        "-m", "--model-pth", type=Path, default=Path("/mnt/db/weights/esm"),
        help="Parent path to pretrained ESM data directory",
    )
    parser.add_argument("--num-recycles", type=int, default=4, help="ESMFold recycling iterations (default 4)")
    parser.add_argument("--max-tokens-per-batch", type=int, default=1024, help="Max tokens per GPU batch")
    parser.add_argument("--chunk-size", type=int, default=None, help="Axial attention chunk size (128, 64, 32)")
    parser.add_argument("--num-threads", type=int, default=8, help="CPU threads for data loading")
    args = parser.parse_args()

    if not args.fasta.exists():
        raise FileNotFoundError(args.fasta)
    args.pdb.mkdir(parents=True, exist_ok=True)

    # Read FASTA and sort by length for batching
    logger.info("Reading sequences from %s", args.fasta)
    all_sequences = sorted(read_fasta(args.fasta), key=lambda hs: len(hs[1]))
    logger.info("Loaded %d sequences from %s", len(all_sequences), args.fasta)

    # Use pre-downloaded checkpoints
    if not args.model_pth.exists() or "checkpoints" not in os.listdir(args.model_pth):
        raise FileNotFoundError(
            f"Checkpoint directory not found at {args.model_pth}/checkpoints/. "
            "Mount pre-downloaded weights at /mnt/db/weights/esm."
        )
    torch.hub.set_dir(str(args.model_pth))

    logger.info("Loading ESMFold model")
    model = esm2.pretrained.esmfold_v1()
    model = model.eval()
    model.set_chunk_size(args.chunk_size)
    torch.set_num_threads(args.num_threads)
    model.cuda()
    logger.info("Starting predictions")

    batched_sequences = create_batched_sequence_dataset(all_sequences, args.max_tokens_per_batch)
    num_completed = 0
    num_sequences = len(all_sequences)

    for headers, sequences in batched_sequences:
        start = timer()
        try:
            output = model.infer(sequences, num_recycles=args.num_recycles)
        except RuntimeError as exc:
            if "CUDA out of memory" in str(exc):
                logger.error(
                    "OOM on batch of %d sequences. Try reducing --max-tokens-per-batch.", len(sequences)
                )
                raise
            raise

        output = {key: value.cpu() for key, value in output.items()}
        pdbs = model.output_to_pdb(output)
        elapsed = timer() - start

        for header, _seq, pdb_string, mean_plddt, ptm in zip(
            headers, sequences, pdbs, output["mean_plddt"], output["ptm"]
        ):
            output_file = args.pdb / f"{header}.pdb"
            output_file.write_text(pdb_string)
            num_completed += 1
            logger.info(
                "Predicted %s: length=%d pLDDT=%.1f pTM=%.3f [%.1fs, %d/%d]",
                header, len(_seq), mean_plddt, ptm, elapsed / len(headers), num_completed, num_sequences,
            )

    logger.info("ESMFold complete: %d structures in %s", num_completed, args.pdb)
