# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

def validate_position_label(label: object, alphabet: str) -> str:
    """Validate a ``<residue>_<1-based position>`` GREMLIN label."""
    label_text = str(label)
    residue, separator, position = label_text.partition("_")
    if separator != "_" or residue not in alphabet:
        raise ValueError("Position label residue must use the configured alphabet")
    if not position or any(digit not in "0123456789" for digit in position) or int(position) < 1:
        raise ValueError("Position label suffix must be a positive integer")
    return label_text
