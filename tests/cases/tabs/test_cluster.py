# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import os

import pytest

from REvoDesign.tools.customized_widgets import set_widget_value
from tests.conftest import TestWorker
from tests.data.test_data import KeyData

os.environ["PYTEST_QT_API"] = "pyqt5"


@pytest.mark.serial
@pytest.mark.dependency(depends=["tabs_bootstrap_ui", "tabs_bootstrap_prepare"], scope="session")
class TestREvoDesignPlugin_TabCluster:
    def test_cluster(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="cluster")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table,
            KeyDataDuringTests.mutant_file,
        )

        set_widget_value(
            test_worker.plugin.ui.spinBox_num_cluster,
            test_worker.test_data.cluster_num,
        )
        set_widget_value(
            test_worker.plugin.ui.spinBox_num_mut_minimun,
            test_worker.test_data.cluster_min,
        )
        set_widget_value(
            test_worker.plugin.ui.spinBox_num_mut_maximum,
            test_worker.test_data.cluster_max,
        )
        set_widget_value(
            test_worker.plugin.ui.spinBox_cluster_batchsize,
            test_worker.test_data.cluster_batch,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_shuffle_clustering,
            test_worker.test_data.cluster_shuffle,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_run",
        )
        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_cluster)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_run",
        )

        m = test_worker.test_data.molecule
        c = test_worker.test_data.chain_id

        bn = f'{m}_{c}_{os.path.basename(KeyDataDuringTests.mutant_file).replace(".txt","")}_designs_'

        for mut_num in range(
            test_worker.test_data.cluster_min,
            test_worker.test_data.cluster_max + 1,
        ):
            dir = f"{bn}{mut_num}"
            assert os.path.exists(dir)
            assert all(
                [os.path.exists(os.path.join(dir, f"c.{c}.fasta")) for c in range(test_worker.test_data.cluster_num)]
            )
            assert os.path.exists(os.path.join(dir, "cluster_centers_stochastic.fasta"))
