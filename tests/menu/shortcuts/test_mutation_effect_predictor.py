# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import pandas as pd
import pytest
from RosettaPy.common.mutation import RosettaPyProteinSequence

from REvoDesign.shortcuts.tools.mutation_effect_predictors import ThermoMpnnPredictor, shortcut_thermompnn
from tests.conftest import TestWorker


@pytest.mark.serial
# a variant test from RosettaPy's short app tests
@pytest.mark.parametrize(
    "job_id,mode,threshold,long_dist,ss_penalty",
    [
        ["ssm_single", "single", None, None, False],
        # ['ssm_single_ss_penalty', 'single', None, None, True],
        # ['ssm_single_higher_threshold', 'single', 10, None, False],
        # ['ssm_additive', 'additive', None, None, False],
        # ['ssm_epistatic', 'epistatic', None, None, False],
        # ['ssm_epistatic_longdist', 'epistatic', None, None,False]
    ],
)
@pytest.mark.skipif(not ThermoMpnnPredictor.installed, reason="ThermoMpnnPredictor not installed")
def test_shortcut_thermompnn(job_id, mode, threshold, long_dist, ss_penalty, test_worker: TestWorker, monkeypatch):
    pdb = "../tests/data/6zcy_lig.pdb"
    test_worker.test_id = test_worker.method_name()
    test_worker.load_session_and_check(customized_session=pdb)

    save_dir = "predictors/thermompnn"

    def _mock_init(self, pdb, save_dir, prefix, chains, mode, batch_size, threshold, distance, ss_penalty, device):
        del save_dir, chains, batch_size, threshold, distance, ss_penalty, device
        self.prefix = prefix
        self.mode = mode
        self.sequence = RosettaPyProteinSequence.from_pdb(pdb)

    monkeypatch.setattr(ThermoMpnnPredictor, "__init__", _mock_init)
    monkeypatch.setattr(ThermoMpnnPredictor, "run", lambda self: pd.DataFrame({"ddG": [-1.0], "Mutation": ["MA1A"]}))
    monkeypatch.setattr(ThermoMpnnPredictor, "cleanup", lambda self: None)

    shortcut_thermompnn(
        pdb=pdb,
        save_dir=save_dir,
        prefix=job_id,
        mode=mode,
        threshold=threshold or -0.5,
        distance=long_dist or 5.0,
        ss_penalty=ss_penalty,
        device="cpu",
        load_to_preview=True,
        top_ranked=100,
    )

    test_worker.save_new_experiment(experiment_name=f"{test_worker.test_id}_{job_id}")

    test_worker.check_existed_mutant_tree()
    test_worker.save_pymol_png(basename=f"{test_worker.test_id}_{job_id}", focus=False)
