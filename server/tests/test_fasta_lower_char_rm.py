# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sys
from pathlib import Path

from scripts.fasta_lower_char_rm import char_filter

_runner_dir = Path(__file__).resolve().parents[1] / "docker" / "runners" / "pssm_gremlin"
if str(_runner_dir) not in sys.path:
    sys.path.insert(0, str(_runner_dir))


def test_char_filter_preserves_header_text():
    assert char_filter(">mixedCase header\n") == ">mixedCase header\n"


def test_char_filter_removes_lowercase_insertions_from_sequence():
    assert char_filter("ARnD.cQ*\n") == "ARD.Q*\n"
