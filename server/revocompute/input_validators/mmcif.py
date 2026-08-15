# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""mmCIF content validator."""

from __future__ import annotations

from revocompute.input_validators.common import CIF_SNIFF_LINES, MAX_CIF_ATOMS, MAX_CIF_RECORD_LENGTH, _read_text


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
