# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Shortcut wrappers of results exporting
"""

from REvoDesign.shortcuts.tools.exports import shortcut_dump_fasta_from_struct, shortcut_dump_sidechains
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

from ...logger import ROOT_LOGGER

logging = ROOT_LOGGER.getChild(__name__)

# Init registry for sequence-related dialogs
registry = DialogWrapperRegistry("exports")

# Register function manually
wrapped_dump_fasta_from_struct = registry.register("dump_fasta_from_struct", shortcut_dump_fasta_from_struct)

wrapped_menu_dump_sidechains = registry.register(
    "menu_dump_sidechains", shortcut_dump_sidechains, use_thread=True, has_dynamic_values=True
)
