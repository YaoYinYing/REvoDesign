# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Shortcut wrappers of sequence designs
"""

from REvoDesign.shortcuts.tools.designs import shortcut_pssm2csv
from REvoDesign.shortcuts.utils import DialogWrapperRegistry
from REvoDesign.tools.mutant_tools import pick_design_from_profile

registry = DialogWrapperRegistry("designs")

wrapped_pssm2csv = registry.register("pssm2csv", shortcut_pssm2csv, use_thread=True)

wrapped_profile_pick_design = registry.register("profile_pick_design", pick_design_from_profile)
