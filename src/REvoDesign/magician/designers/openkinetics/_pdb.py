# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""PDB parsing, ligand discovery, and SMILES resolution for OpenKinetics."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from Bio.PDB import PDBParser
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.tools.mutant_tools import aa3_to_aa1

from ._models import COFACTOR_EXCLUSIONS, WATER_RESIDUE_NAMES, LigandCandidate, OpenKineticsValidationError

# ---------------------------------------------------------------------------
# Mutation label I/O
# ---------------------------------------------------------------------------


def load_mutation_labels(mutation_path: str | Path, limit: int | None = None) -> list[str]:
    labels = [line.strip() for line in Path(mutation_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if limit is not None:
        labels = labels[:limit]
    return labels


def relabel_pdb_position_to_sequential(
    label: str,
    residue_numbers: tuple[int, ...],
    *,
    chain_id: str = "A",
) -> str:
    """Convert a PDB-numbered mutation label to its sequential-position equivalent.

    Mutation labels like ``AE93D`` use PDB residue numbering which may be
    non-contiguous.  :func:`REvoDesign.tools.mutant_tools.extract_mutants_from_mutant_id`
    expects sequential (1-based) positions, so this helper performs the remapping
    using the residue-number list obtained from :func:`load_chain_sequence_context`.
    """
    clean_label = label.strip()
    match = re.fullmatch(r"([A-Z]?)([A-Z])(\d+)([A-Z])", clean_label)
    if match is None:
        raise OpenKineticsValidationError(f"Unsupported mutation label format: {label!r}")

    label_chain = match.group(1) or chain_id
    pdb_position = int(match.group(3))
    try:
        seq_index = residue_numbers.index(pdb_position)
    except ValueError as exc:
        raise OpenKineticsValidationError(
            f"Residue position {pdb_position} is not present in chain {chain_id}"
        ) from exc

    seq_position = seq_index + 1  # 1-based sequential
    return f"{label_chain}{match.group(2)}{seq_position}{match.group(4)}"


# ---------------------------------------------------------------------------
# PDB sequence extraction
# ---------------------------------------------------------------------------


def load_chain_sequence_context(
    pdb_path: str | Path,
    chain_id: str = "A",
) -> tuple[RosettaPyProteinSequence, str, tuple[int, ...]]:
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("structure", str(pdb_path))
    model = next(structure.get_models())
    if chain_id not in model:
        raise OpenKineticsValidationError(f"Chain {chain_id!r} not found in {pdb_path}")

    residue_numbers: list[int] = []
    sequence_codes: list[str] = []
    for residue in model[chain_id]:
        if residue.id[0] != " ":
            continue
        residue_number = int(residue.id[1])
        try:
            residue_code = aa3_to_aa1(residue.resname)
        except ValueError as exc:
            raise OpenKineticsValidationError(
                f"Unsupported residue name {residue.resname!r} at {chain_id}{residue_number}"
            ) from exc
        residue_numbers.append(residue_number)
        sequence_codes.append(residue_code)

    if not residue_numbers:
        raise OpenKineticsValidationError(f"No protein residues found for chain {chain_id!r} in {pdb_path}")

    wt_sequences = RosettaPyProteinSequence.from_dict({chain_id: "".join(sequence_codes)})
    return wt_sequences, "".join(sequence_codes), tuple(residue_numbers)


# ---------------------------------------------------------------------------
# Ligand discovery
# ---------------------------------------------------------------------------


def discover_ligand_candidates(
    pdb_path: str | Path,
    excluded_residue_names: frozenset[str] = WATER_RESIDUE_NAMES | COFACTOR_EXCLUSIONS,
) -> list[LigandCandidate]:
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("structure", str(pdb_path))
    model = next(structure.get_models())
    ligands: list[LigandCandidate] = []
    for chain in model:
        for residue in chain:
            hetero_flag = residue.id[0]
            if hetero_flag == " ":
                continue
            residue_name = residue.resname.strip().upper()
            if residue_name in excluded_residue_names:
                continue
            atom_serials = tuple(int(atom.serial_number) for atom in residue.get_atoms())
            ligands.append(
                LigandCandidate(
                    residue_name=residue_name,
                    residue_number=int(residue.id[1]),
                    chain_id=chain.id,
                    atom_serials=atom_serials,
                    atom_count=len(atom_serials),
                )
            )
    return ligands


def choose_primary_ligand(pdb_path: str | Path) -> LigandCandidate:
    ligands = discover_ligand_candidates(pdb_path)
    if not ligands:
        raise OpenKineticsValidationError(f"No non-protein ligands were found in {pdb_path}")
    if len(ligands) > 1:
        raise OpenKineticsValidationError(
            f"Expected a single ligand candidate in {pdb_path}, found "
            f"{[ligand.ligand_identifier for ligand in ligands]}"
        )
    return ligands[0]


def extract_ligand_pdb_block(pdb_path: str | Path, ligand: LigandCandidate) -> str:
    atom_serials = set(ligand.atom_serials)
    block_lines: list[str] = []
    for line in Path(pdb_path).read_text(encoding="utf-8").splitlines():
        if line.startswith("HETATM"):
            residue_name = line[17:20].strip().upper()
            chain_id = line[21].strip()
            residue_number = int(line[22:26].strip())
            if (
                residue_name == ligand.residue_name
                and chain_id == ligand.chain_id
                and residue_number == ligand.residue_number
            ):
                block_lines.append(line)
        elif line.startswith("CONECT"):
            source_serial = int(line[6:11].strip())
            if source_serial in atom_serials:
                block_lines.append(line)
    block_lines.append("END")
    return "\n".join(block_lines) + "\n"


# ---------------------------------------------------------------------------
# SMILES resolution (RDKit required)
# ---------------------------------------------------------------------------


def _canonicalize_smiles(smiles: str) -> str:
    from rdkit import Chem

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise OpenKineticsValidationError(f"Invalid SMILES string: {smiles!r}")
    return Chem.MolToSmiles(molecule)


def smiles_from_ligand_pdb_block(pdb_block: str) -> str:
    try:
        from rdkit import Chem
    except ImportError as exc:
        raise OpenKineticsValidationError("RDKit is required for SMILES generation from PDB ligand blocks") from exc

    molecule = Chem.MolFromPDBBlock(pdb_block, sanitize=True, removeHs=False)
    if molecule is None:
        raise OpenKineticsValidationError("Failed to convert ligand PDB block to SMILES")
    return Chem.MolToSmiles(molecule)


# ---------------------------------------------------------------------------
# Substrate metadata
# ---------------------------------------------------------------------------


def resolve_substrate_metadata(
    pdb_path: str | Path,
    structure_id: str = "1SUO",
) -> dict[str, Any]:
    ligand = choose_primary_ligand(pdb_path)
    ligand_pdb_block = extract_ligand_pdb_block(pdb_path, ligand)
    substrate_smiles = smiles_from_ligand_pdb_block(ligand_pdb_block)

    return {
        "structure_id": structure_id,
        "ligand_identifier": ligand.ligand_identifier,
        "ligand_residue_name": ligand.residue_name,
        "ligand_residue_number": ligand.residue_number,
        "ligand_chain_id": ligand.chain_id,
        "ligand_atom_count": ligand.atom_count,
        "substrate_smiles": substrate_smiles,
        "smiles_resolution": "rdkit",
        "pdb_block_sha256": hashlib.sha256(ligand_pdb_block.encode("utf-8")).hexdigest(),
    }
