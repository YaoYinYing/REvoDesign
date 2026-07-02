# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""OpenKinetics API-backed scorers and fixture helpers."""

from __future__ import annotations

from . import _scorers as _scorers_mod  # triggers class creation; see _SCORER_SPECS loop
from ._client import (
    OpenKineticsClient,
    _normalize_result_rows,
    build_openkinetics_data_rows,
    build_openkinetics_request_payload,
    get_method_metadata,
    load_openkinetics_config,
    resolve_api_key,
    sha256_file,
    write_csv_rows,
    write_json,
    write_normalized_scores_csv,
)
from ._models import (
    COFACTOR_EXCLUSIONS,
    DEFAULT_OPENKINETICS_API_KEY_ENV,
    OPENKINETICS_ENDPOINTS,
    WATER_RESIDUE_NAMES,
    LigandCandidate,
    OpenKineticsAPIError,
    OpenKineticsConfigurationError,
    OpenKineticsError,
    OpenKineticsFixturePaths,
    OpenKineticsTimeoutError,
    OpenKineticsValidationError,
)
from ._pdb import (
    _canonicalize_smiles,
    choose_primary_ligand,
    discover_ligand_candidates,
    extract_ligand_pdb_block,
    load_chain_sequence_context,
    load_mutation_labels,
    relabel_pdb_position_to_sequential,
    resolve_substrate_metadata,
    smiles_from_ligand_pdb_block,
)
from ._scorers import OPENKINETICS_SCORER_CLASS_NAMES  # noqa: F401
from ._scorers import OpenKineticsScorerAbstract

# Re-export dynamically-created scorer classes by name.
for _name in OPENKINETICS_SCORER_CLASS_NAMES:
    globals()[_name] = getattr(_scorers_mod, _name)

__all__ = [
    "OpenKineticsScorerAbstract",
    # client
    "OpenKineticsClient",
    # config
    "load_openkinetics_config",
    "resolve_api_key",
    # data helpers
    "build_openkinetics_data_rows",
    "build_openkinetics_request_payload",
    "get_method_metadata",
    "write_csv_rows",
    "write_json",
    "sha256_file",
    "write_normalized_scores_csv",
    # result normalization
    "_normalize_result_rows",
    # PDB / ligand
    "choose_primary_ligand",
    "discover_ligand_candidates",
    "extract_ligand_pdb_block",
    "load_chain_sequence_context",
    "load_mutation_labels",
    "relabel_pdb_position_to_sequential",
    "resolve_substrate_metadata",
    "smiles_from_ligand_pdb_block",
    "_canonicalize_smiles",
    # exceptions
    "OpenKineticsAPIError",
    "OpenKineticsConfigurationError",
    "OpenKineticsError",
    "OpenKineticsTimeoutError",
    "OpenKineticsValidationError",
    # dataclasses
    "LigandCandidate",
    "OpenKineticsFixturePaths",
    # constants
    "COFACTOR_EXCLUSIONS",
    "DEFAULT_OPENKINETICS_API_KEY_ENV",
    "OPENKINETICS_ENDPOINTS",
    "WATER_RESIDUE_NAMES",
]
