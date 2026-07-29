# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from scripts.fasta_lower_char_rm import char_filter


def test_char_filter_preserves_header_text():
    assert char_filter(">mixedCase header\n") == ">mixedCase header\n"


def test_char_filter_removes_lowercase_insertions_from_sequence():
    assert char_filter("ARnD.cQ*\n") == "ARD.Q*\n"
