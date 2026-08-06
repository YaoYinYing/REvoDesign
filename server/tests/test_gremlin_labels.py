# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from scripts.gremlin_labels import validate_position_label

_runner_dir = Path(__file__).resolve().parents[1] / "docker" / "runners" / "pssm_gremlin"
if str(_runner_dir) not in sys.path:
    sys.path.insert(0, str(_runner_dir))

ALPHABET = "ARNDCQEGHILKMFPSTWYV-"


@pytest.mark.parametrize("label", ("A_1", "V_42", "-_7"))
def test_validate_position_label_accepts_residue_and_numeric_position(label):
    assert validate_position_label(label, ALPHABET) == label


@pytest.mark.parametrize(
    "label",
    ("X_1", "AA_1", "A", "A_0", "A_-1", "A_first", "A_1_2", "A_1/other", "A_١"),
)
def test_validate_position_label_rejects_invalid_components(label):
    with pytest.raises(ValueError):
        validate_position_label(label, ALPHABET)
