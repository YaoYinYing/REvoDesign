# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Wrapper for gremlin
"""

from REvoDesign.shortcuts.tools.evolution import run_gremlin
from REvoDesign.shortcuts.utils import DialogWrapperRegistry

registry = DialogWrapperRegistry("evolution")
wrapped_gremlin = registry.register("run_gremlin", run_gremlin, use_thread=True, use_progressbar=True)
