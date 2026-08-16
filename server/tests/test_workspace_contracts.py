# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import pytest
from revocompute.workspace_contracts import (
    WorkspaceValidationError,
    normalize_rfdiffusion,
    parse_contig,
    serialize_contig,
    validate_rfdiffusion_structure,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("100-100", "100-100"),
        ("10-40/A163-181/10-40", "10-40/A163-181/10-40"),
        ("A1-150/0 70-100", "A1-150/0 70-100"),
    ],
)
def test_contig_round_trip(raw, expected):
    assert serialize_contig(parse_contig(raw)) == expected


def test_binder_normalization_is_canonical():
    result = normalize_rfdiffusion(
        {
            "mode": "binder",
            "segments": [
                {"kind": "fixed", "chain": "A", "start": 1, "end": 50},
                {"kind": "chain_break"},
                {"kind": "generated", "min_length": 70, "max_length": 100},
            ],
            "hotspots": [{"chain": "A", "residue": 10}],
        }
    )
    assert result["params"] == {
        "design_mode": "binder",
        "contig": "A1-50/0 70-100",
        "hotspot_res": "[A10]",
    }


def test_binder_requires_hotspots():
    with pytest.raises(WorkspaceValidationError, match="hotspots"):
        normalize_rfdiffusion(
            {
                "mode": "binder",
                "segments": [
                    {"kind": "fixed", "chain": "A", "start": 1, "end": 10},
                    {"kind": "chain_break"},
                    {"kind": "generated", "min_length": 20, "max_length": 30},
                ],
                "hotspots": [],
            }
        )


def test_structure_cross_validation_rejects_absent_residue(tmp_path):
    path = tmp_path / "input.pdb"
    path.write_text(
        "ATOM      1  CA  GLY A   1      10.000  10.000  10.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    normalized = normalize_rfdiffusion(
        {
            "mode": "motif_scaffolding",
            "segments": [{"kind": "fixed", "chain": "A", "start": 2, "end": 2}],
            "hotspots": [],
        }
    )
    with pytest.raises(WorkspaceValidationError, match="A2"):
        validate_rfdiffusion_structure(normalized, str(path))
