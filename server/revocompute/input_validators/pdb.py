# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""PDB content validator: keyword sniff + biotite geometry sanity check."""

from __future__ import annotations

import io
from itertools import product
from typing import Any

import numpy as np

from revocompute.input_validators.common import (
    MAX_PDB_LINES,
    MAX_PDB_RECORD_LENGTH,
    PDB_SNIFF_LINES,
    _read_text,
)

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
    from revocompute.input_validators import run_plugins

    plugin_error = run_plugins(".pdb", path)
    if plugin_error is not None:
        return plugin_error
    return _check_pdb_geometry(lines)


# Geometry sanity check — downstream tools (RDKit via torchdrug) infer bonds
# from inter-atomic distances and reject atoms whose valence exceeds what the
# element permits.  A single misplaced atom (e.g. a terminal OXT colliding
# with another residue's carbonyl) makes the whole upload fail minutes into a
# compute job with a cryptic library error.  Reject such files at upload with
# a message naming the offending atoms.
_PDB_BOND_CUTOFF = 1.9  # angstrom — heavy-atom covalent bonds live below this
_PDB_DUPLICATE_CUTOFF = 0.5  # angstrom — same-element atoms closer than this are duplicates
# Heavy-neighbor ceilings for standard protein atoms: a normal carbonyl C has
# 3 (CA, O, next-residue N), so 4+ means a collision like a misplaced
# terminal OXT.  HETATM records are excluded, so metal coordination cannot
# false-positive here.
_MAX_VALENCE = {"C": 3, "N": 3, "O": 2, "S": 2}
_PDB_HEAVY_ELEMENTS = set(_MAX_VALENCE)

def _check_pdb_geometry(lines: list[str]) -> str | None:
    """Delegate geometry checking to the biotite-based backend."""
    return _check_pdb_geometry_biotite(lines)


def _biotite_structure_from_lines(lines: list[str]):
    """Parse PDB text into an :class:`~biotite.structure.AtomArray`.

    Uses biotite's real parser (no column slicing); only the first MODEL is
    considered, matching how downstream tools read the file.
    """
    from biotite.structure.io.pdb import PDBFile

    pdb_file = PDBFile()
    pdb_file.read(io.StringIO("\n".join(lines)))
    return pdb_file.get_structure(model=1)


def _check_pdb_geometry_biotite(lines: list[str]) -> str | None:
    """Over-valence and duplicate-position checks on biotite-parsed atoms.

    Returns ``None`` when biotite cannot parse the file — the sniff above
    already rejected clearly-binary input, and rejecting here would be
    format policing rather than a DoS/quality cap.
    """
    try:
        structure = _biotite_structure_from_lines(lines)
    except Exception:
        return None

    # Heavy protein atoms only — HETATM excluded, so metal coordination cannot
    # false-positive.
    mask = ~structure.hetero & np.isin(structure.element, list(_PDB_HEAVY_ELEMENTS))
    sub = structure[mask]
    # First alternate location per atom only (alternates overlap by design).
    # Biotite's own altloc dedup needs the altloc_id extra annotation, which
    # PDBFile does not load, so group explicitly by residue/atom identity.
    seen: set[tuple[str, str, str]] = set()
    keep: list[int] = []
    for index in range(len(sub)):
        key = (sub.chain_id[index], str(sub.res_id[index]), sub.ins_code[index], sub.atom_name[index])
        if key in seen:
            continue
        seen.add(key)
        keep.append(index)
    if not keep:
        return None  # ligand-only / all-HETATM file — nothing to geometry-check
    sub = sub[np.asarray(keep)]
    coords = sub.coord
    elements = sub.element
    # Labels for error messages: RESNAME RESID ATOM [chain]
    labels = [
        f"{res_name}{res_id} {atom_name} [{chain_id}]"
        for atom_name, res_name, res_id, chain_id in zip(
            sub.atom_name, sub.res_name, [str(v) for v in sub.res_id], sub.chain_id
        )
    ]

    # 4 Å grid over the parsed coordinates.  The neighbor search itself stays
    # a simple grid (~27 cells per atom): biotite's CellList API varies across
    # versions, and this is hot-path-simple and dependency-free.
    grid: dict[tuple[int, int, int], list[int]] = {}
    for index, (x, y, z) in enumerate(coords):
        cell = (int(x // 4), int(y // 4), int(z // 4))
        grid.setdefault(cell, []).append(index)

    counts = [0] * len(sub)
    for index in range(len(sub)):
        x, y, z = coords[index]
        element = elements[index]
        cx, cy, cz = int(x // 4), int(y // 4), int(z // 4)
        for dx, dy, dz in product((-1, 0, 1), repeat=3):
            for other in grid.get((cx + dx, cy + dy, cz + dz), ()):
                if other <= index:
                    continue
                ox, oy, oz = coords[other]
                dist = ((x - ox) ** 2 + (y - oy) ** 2 + (z - oz) ** 2) ** 0.5
                if dist < _PDB_DUPLICATE_CUTOFF:
                    return f"PDB contains overlapping atoms {labels[index]} and {labels[other]} ({dist:.2f} Å apart)"
                if dist < _PDB_BOND_CUTOFF:
                    counts[index] += 1
                    counts[other] += 1

    for index, count in enumerate(counts):
        if count > _MAX_VALENCE[elements[index]]:
            neighbors = []
            x, y, z = coords[index]
            cx, cy, cz = int(x // 4), int(y // 4), int(z // 4)
            for dx, dy, dz in product((-1, 0, 1), repeat=3):
                for other in grid.get((cx + dx, cy + dy, cz + dz), ()):
                    if other == index:
                        continue
                    ox, oy, oz = coords[other]
                    dist = ((x - ox) ** 2 + (y - oy) ** 2 + (z - oz) ** 2) ** 0.5
                    if dist < _PDB_BOND_CUTOFF:
                        neighbors.append((dist, labels[other]))
            detail = ", ".join(f"{d:.2f} Å to {n}" for d, n in sorted(neighbors)[:5])
            return (
                f"PDB atom {labels[index]} ({elements[index]}) has {count} neighbors within "
                f"{_PDB_BOND_CUTOFF} Å — RDKit-based tools will reject it: {detail}"
            )
    return None


