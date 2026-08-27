# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json

from live_task_matrix import CASES, REPO_ROOT, WORKSPACES, form_value


def test_live_matrix_preserves_case_except_for_booleans():
    assert form_value("esm2_t6_8M_UR50D") == "esm2_t6_8M_UR50D"
    assert form_value("A") == "A"
    assert form_value(True) == "true"
    assert WORKSPACES["rfdiffusion"]["capabilities"]["design_regions"]["mode"] == "unconditional"
    opendde = json.loads((REPO_ROOT / CASES["opendde"][0]).read_text(encoding="utf-8"))
    assert opendde and isinstance(opendde, list)
