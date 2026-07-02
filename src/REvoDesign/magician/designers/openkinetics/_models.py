# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""OpenKinetics data models, exceptions, and defaults."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class OpenKineticsError(RuntimeError):
    """Base OpenKinetics integration error."""


class OpenKineticsConfigurationError(OpenKineticsError):
    """Raised when required local configuration is missing or invalid."""


class OpenKineticsAPIError(OpenKineticsError):
    """Raised for HTTP or remote API failures."""


class OpenKineticsTimeoutError(OpenKineticsError):
    """Raised when a remote job does not complete within the timeout."""


class OpenKineticsValidationError(OpenKineticsError):
    """Raised when prepared OpenKinetics input data is invalid."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LigandCandidate:
    residue_name: str
    residue_number: int
    chain_id: str
    atom_serials: tuple[int, ...]
    atom_count: int

    @property
    def ligand_identifier(self) -> str:
        return f"{self.residue_name}:{self.chain_id}:{self.residue_number}"


@dataclass(frozen=True)
class OpenKineticsFixturePaths:
    output_dir: Path
    manifest_path: Path
    readme_path: Path
    input_variants_path: Path
    api_input_path: Path
    substrate_path: Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OPENKINETICS_BASE_URL = "https://predictor.openkinetics.org/api/v1"
DEFAULT_OPENKINETICS_API_KEY_ENV = "OPENKINETICS_API_KEY"
DEFAULT_OPENKINETICS_POLL_INTERVAL_SECONDS = 3
DEFAULT_OPENKINETICS_TIMEOUT_SECONDS = 600

OPENKINETICS_ENDPOINTS = {
    "methods": "/methods/",
    "validate": "/validate/",
    "submit": "/submit/",
    "status": "/status/{job_id}/",
    "result": "/result/{job_id}/",
}

WATER_RESIDUE_NAMES = frozenset({"HOH", "WAT"})
COFACTOR_EXCLUSIONS = frozenset({"HEM"})
