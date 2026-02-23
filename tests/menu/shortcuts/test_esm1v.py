# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import os

import pytest

from REvoDesign.shortcuts.tools.esm2 import Esm1v, shortcut_esm1v
from tests.conftest import MEMORY_AVAILABLE_GB

# DISABLED FOR MEMEORY ISSUE


@pytest.mark.serial
@pytest.mark.skipif(MEMORY_AVAILABLE_GB < 10, reason="Not enough memory available for this test")
@pytest.mark.skipif(not Esm1v.installed, reason="Esm1v not installed")
def test_esm1v():

    sequence: str = "YINYING"

    save_dir = "predictors/esm1v"
    model_name = "esm1v_t33_650M_UR90S_1.pt"

    shortcut_esm1v(
        model_names=[model_name],
        sequence=sequence,
        dms_output=os.path.join(save_dir, f"{model_name}.csv"),
        checkpoint_dir="",
        skip_wt=False,
        mutation_col="mutation",
        offset_idx=1,
        scoring_strategy="wt-marginals",
        msa_path="",
        msa_samples=400,
        device="cpu",
    )
