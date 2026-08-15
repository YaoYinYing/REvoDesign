# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Shared caps and the text-reading helper for the input validators."""

from __future__ import annotations

import os
from pathlib import Path

# Uploads are capped at 16 MiB by app.MAX_CONTENT_LENGTH, so a file on disk is
# never larger than that.  Every cap below is deliberately far above what can
# physically fit in 16 MiB of the corresponding format, meaning the caps only
# ever trip on degenerate content, never on a plausible real file.

# FASTA / A3M
# A 16 MiB FASTA holds at most ~4.2M one-residue sequences (~4 bytes each) and
# ~16.8M sequence characters.  Real MSA inputs (GREMLIN-style) stay far below
# this: 1M sequences x even 50 residues would be ~50 MB of upload, over the
# file-size cap.
MAX_FASTA_SEQUENCES = 1_000_000
MAX_FASTA_TOTAL_RESIDUES = 50_000_000
_FASTA_ALPHABET = frozenset("ACDEFGHIKLMNPQRSTVWYXBZJOU*-.")
# A3M (HH-suite) marks insertion columns with lowercase letters.
_A3M_ALPHABET = _FASTA_ALPHABET | frozenset("abcdefghijklmnopqrstuvwxyz")
_FASTA_WHITESPACE = frozenset(" \t\r\n\v\f")

# PDB
# Real PDB lines are ~80 chars and files have at most ~210k lines under 16 MiB.
MAX_PDB_LINES = 2_000_000
MAX_PDB_RECORD_LENGTH = 10_000
# Some PDBs open with long REMARK sections (hundreds of lines in large
# entries); peek deep enough that no real header can exhaust the window.
PDB_SNIFF_LINES = 1000

# mmCIF
# Real atom rows are ~60-80 chars, so a 16 MiB file holds ~280k atom rows;
# even giant ribosome / capsid entries stay below 1M atoms.
MAX_CIF_ATOMS = 2_000_000
MAX_CIF_RECORD_LENGTH = 100_000
CIF_SNIFF_LINES = 200

# JSON
MAX_JSON_NODES = 1_000_000  # ~8 MB of "0,0,0,..." would be needed to reach it
MAX_JSON_DEPTH = 50
# Byte ceiling applied BEFORE json.loads: a compact array of tiny values can
# allocate tens of MiB of Python objects per worker even when the node count
# passes. Scientific JSON inputs (config/metadata) are far below 1 MiB.
MAX_JSON_BYTES = 1024 * 1024


def _read_text(path: str, *, kind: str) -> tuple[str | None, str]:
    """Return ``(text, error)``; *error* is None when *text* is usable.

    The binary sniff at the HTTP layer only reads 4096 bytes, so NUL bytes
    deeper in the file are caught here.
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return None, f"Could not read uploaded {kind} file: {exc}"
    if b"\0" in data:
        return None, f"Uploaded {kind} file contains binary content (NUL byte)"
    # errors="replace" turns undecodable bytes into U+FFFD, which the alphabet
    # checks below reject; headers are not alphabet-checked, so e.g. latin-1
    # metadata in a FASTA header line still passes.
    return data.decode("utf-8", errors="replace"), None
