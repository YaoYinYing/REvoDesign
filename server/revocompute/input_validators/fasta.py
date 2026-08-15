# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""FASTA / A3M content validators."""

from __future__ import annotations

from revocompute.input_validators.common import (
    MAX_FASTA_SEQUENCES,
    MAX_FASTA_TOTAL_RESIDUES,
    _A3M_ALPHABET,
    _FASTA_ALPHABET,
    _FASTA_WHITESPACE,
    _read_text,
)


def validate_fasta(path: str, *, allow_lowercase: bool = False) -> str | None:
    """Return an error message if *path* is not a plausible FASTA/A3M file."""
    text, error = _read_text(path, kind="FASTA")
    if error is not None:
        return error
    alphabet = _A3M_ALPHABET if allow_lowercase else _FASTA_ALPHABET
    sequences = 0
    total_residues = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            sequences += 1
            if sequences > MAX_FASTA_SEQUENCES:
                return f"FASTA file contains more than {MAX_FASTA_SEQUENCES} sequences"
            continue
        if not sequences:
            return "FASTA file must start with a '>' header line"
        for char in line:
            if char in alphabet or char in _FASTA_WHITESPACE:
                if char not in _FASTA_WHITESPACE:
                    total_residues += 1
            else:
                return f"FASTA sequence contains invalid character {char!r}"
        if total_residues > MAX_FASTA_TOTAL_RESIDUES:
            return f"FASTA file contains more than {MAX_FASTA_TOTAL_RESIDUES} residues"
    if not sequences:
        return "FASTA file must contain a '>' header line"
    return None


def validate_a3m(path: str) -> str | None:
    """Return an error message if *path* is not a plausible A3M file."""
    return validate_fasta(path, allow_lowercase=True)
