# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Content validators for uploaded scientific input files.

Uploads are already checked for extension (task registry allowlist) and for
binary content (4096-byte sniff) at the HTTP layer.  These validators add
cheap, linear-time content checks so that pathological files are rejected
before third-party parsers run.  The point is DoS caps, not format policing —
a plausible real file must never be rejected, and anything that is not
clearly-binary or pathological passes.

Every validator returns ``None`` when the file is acceptable, or a
human-readable error message when it is not.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

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


def validate_pdb(path: str) -> str | None:
    """Return an error message if *path* is not a plausible PDB file.

    Lenient: only the first ``PDB_SNIFF_LINES`` lines are sniffed for the
    record keywords, so files that open with long REMARK/CRYST1 sections
    still pass.
    """
    text, error = _read_text(path, kind="PDB")
    if error is not None:
        return error
    lines = text.splitlines()
    if len(lines) > MAX_PDB_LINES:
        return f"PDB file contains more than {MAX_PDB_LINES} lines"
    if any(len(line) > MAX_PDB_RECORD_LENGTH for line in lines):
        return f"PDB file contains a line longer than {MAX_PDB_RECORD_LENGTH} characters"
    if not any(line.strip().startswith(("ATOM", "HETATM", "END")) for line in lines[:PDB_SNIFF_LINES]):
        return "PDB file must contain ATOM, HETATM, or END records near the start"
    return None


def validate_mmcif(path: str) -> str | None:
    """Return an error message if *path* is not a plausible mmCIF file.

    Lenient: only the first ``CIF_SNIFF_LINES`` lines are sniffed for the
    ``data_`` / ``_atom_site.`` markers, and atom rows are counted with the
    real loop grammar (``loop_`` columns, then data rows).
    """
    text, error = _read_text(path, kind="mmCIF")
    if error is not None:
        return error
    lines = text.splitlines()
    if any(len(line) > MAX_CIF_RECORD_LENGTH for line in lines):
        return f"mmCIF file contains a line longer than {MAX_CIF_RECORD_LENGTH} characters"
    if not any(
        line.strip().startswith("data_") or line.strip().startswith("_atom_site.") for line in lines[:CIF_SNIFF_LINES]
    ):
        return "mmCIF file must contain a data_ block or _atom_site. columns near the start"
    atom_rows = 0
    in_atom_loop = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "loop_":
            # Column definitions follow; rows only count inside _atom_site.
            in_atom_loop = False
            continue
        if stripped.startswith("_"):
            in_atom_loop = stripped.startswith("_atom_site.")
            continue
        if in_atom_loop:
            # A keyword token ends the loop; anything else is a data row
            # (real PDBx files start atom rows at column 0, no indent).
            if stripped.startswith("data_") or stripped == "stop_":
                in_atom_loop = False
                continue
            atom_rows += 1
            if atom_rows > MAX_CIF_ATOMS:
                return f"mmCIF file contains more than {MAX_CIF_ATOMS} atoms"
    return None


def _json_stats(root: Any) -> tuple[int, int]:
    """Return ``(node_count, max_depth)`` with an iterative stack walk."""
    nodes = 0
    depth = 0
    stack: list[tuple[Any, int]] = [(root, 1)]
    while stack:
        node, level = stack.pop()
        nodes += 1
        if level > depth:
            depth = level
        if isinstance(node, dict):
            stack.extend((child, level + 1) for child in node.values())
        elif isinstance(node, list):
            stack.extend((child, level + 1) for child in node)
    return nodes, depth


def validate_json(path: str) -> str | None:
    """Return an error message if *path* is not parseable JSON within caps.

    Complexity caps only — no schema checks; any well-formed JSON document
    passes.
    """
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return f"Could not read uploaded JSON file: {exc}"
    if b"\0" in data:
        return "Uploaded JSON file contains binary content (NUL byte)"
    try:
        value = json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return "Uploaded JSON file is not valid UTF-8 text"
    except (json.JSONDecodeError, ValueError, RecursionError):
        return "Uploaded file does not appear to be valid JSON"
    nodes, depth = _json_stats(value)
    if nodes > MAX_JSON_NODES:
        return f"JSON file contains more than {MAX_JSON_NODES} values"
    if depth > MAX_JSON_DEPTH:
        return f"JSON file is nested deeper than {MAX_JSON_DEPTH} levels"
    return None


_VALIDATORS: dict[str, Any] = {
    ".fasta": validate_fasta,
    ".fa": validate_fasta,
    ".faa": validate_fasta,
    ".a3m": validate_a3m,
    ".pdb": validate_pdb,
    ".cif": validate_mmcif,
    ".mmcif": validate_mmcif,
    ".json": validate_json,
}


def validate_input_file(path: str, filename: str) -> str | None:
    """Dispatch content validation by extension; return an error message or None.

    Extensions without a dedicated validator (none today) pass through
    unchanged, preserving the extension-allowlist-only behaviour.
    """
    validator = _VALIDATORS.get(os.path.splitext(filename)[1].lower())
    if validator is None:
        return None
    return validator(path)
