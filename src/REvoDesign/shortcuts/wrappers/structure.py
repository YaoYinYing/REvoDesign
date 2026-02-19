# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Shortcut wrappers of structure manipulation
"""

from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.tools.pymol_utils import renumber_protein_chain

# Create registry for 'structure' category
registry = DialogWrapperRegistry("structure")

wrapped_resi_renumber = registry.register("resi_renumber", renumber_protein_chain, use_thread=True)
