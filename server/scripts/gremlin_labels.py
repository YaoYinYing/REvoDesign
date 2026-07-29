# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations


def validate_position_label(label: object, alphabet: str) -> str:
    """Validate a ``<residue>_<1-based position>`` GREMLIN label."""
    label_text = str(label)
    residue, separator, position = label_text.partition("_")
    if separator != "_" or residue not in alphabet:
        raise ValueError("Position label residue must use the configured alphabet")
    if not position.isascii() or not position.isdecimal() or int(position) < 1:
        raise ValueError("Position label suffix must be a positive integer")
    return label_text
