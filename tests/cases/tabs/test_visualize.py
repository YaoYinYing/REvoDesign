# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import os

import pytest

from REvoDesign.magician.designers import ColabDesigner_MPNN
from REvoDesign.sidechain.mutate_runner.PIPPack import PIPPack_worker
from REvoDesign.tools.customized_widgets import set_widget_value
from tests.conftest import TestWorker
from tests.data.test_data import KeyData

os.environ["PYTEST_QT_API"] = "pyqt5"


# move to fast tests
@pytest.mark.dependency(depends=["tabs_bootstrap_ui", "tabs_bootstrap_prepare"])
class TestREvoDesignPlugin_TabVisualize:

    def test_visualize_pssm_ddg(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        # 14.12s call if use PIPpack
        # set_widget_value(test_worker.plugin.ui.comboBox_sidechain_solver, "PIPPack")
        # set_widget_value(
        #     test_worker.plugin.ui.comboBox_sidechain_solver_model,
        #     "pippack_model_1",
        # )

        # 6.80s call if use Dunbrack
        set_widget_value(test_worker.plugin.ui.comboBox_sidechain_solver, "Dunbrack Rotamer Library")

        test_worker.go_to_tab(tab_name="visualize")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.minimum_mutant_file,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.visualize_1_pse,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_csv_2,
            KeyDataDuringTests.ddg_file,
        )
        set_widget_value(
            test_worker.plugin.ui.comboBox_profile_type_2,
            test_worker.test_data.visualize_1_profile_type,
        )

        set_widget_value(
            test_worker.plugin.ui.checkBox_global_score_policy,
            test_worker.test_data.visualize_1_use_global_score,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.visualize_1_score_reversed,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.comboBox_group_name,
            test_worker.test_data.visualize_1_design_case,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_run",
        )
        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)

        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_run",
        )

        assert os.path.exists(test_worker.test_data.visualize_1_pse)
        test_worker.check_existed_mutant_tree()

    @pytest.mark.skipif(not ColabDesigner_MPNN.installed, reason="ColabDesign not installed")
    def test_visualize_pssm_mpnn(self, test_worker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )
        test_worker.go_to_tab(tab_name="visualize")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.minimum_mutant_file,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.visualize_2_pse,
        )
        test_worker.do_typing(test_worker.plugin.ui.lineEdit_input_csv_2, "")
        set_widget_value(
            test_worker.plugin.ui.comboBox_profile_type_2,
            test_worker.test_data.visualize_2_profile_type,
        )

        set_widget_value(
            test_worker.plugin.ui.checkBox_global_score_policy,
            test_worker.test_data.visualize_2_use_global_score,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.visualize_2_score_reversed,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.comboBox_group_name,
            test_worker.test_data.visualize_2_design_case,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_run",
        )

        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_run",
        )

        assert os.path.exists(test_worker.test_data.visualize_2_pse)
        test_worker.check_existed_mutant_tree()

    def test_visualize_from_csv(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )
        test_worker.go_to_tab(tab_name="visualize")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.visualize_csv,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.visualize_3_pse,
        )
        test_worker.do_typing(test_worker.plugin.ui.lineEdit_input_csv_2, "")
        set_widget_value(
            test_worker.plugin.ui.comboBox_profile_type_2,
            test_worker.test_data.visualize_3_profile_type,
        )

        set_widget_value(
            test_worker.plugin.ui.checkBox_global_score_policy,
            test_worker.test_data.visualize_3_use_global_score,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.visualize_3_score_reversed,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.comboBox_group_name,
            test_worker.test_data.visualize_3_design_case,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_run",
        )

        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_run",
        )

        assert os.path.exists(test_worker.test_data.visualize_3_pse)
        mt = test_worker.check_existed_mutant_tree()
        assert mt.all_mutant_branch_ids == [test_worker.test_data.visualize_3_design_case]

    def test_visualize_from_csv_grouped(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )
        test_worker.go_to_tab(tab_name="visualize")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.visualize_csv_grouped,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.visualize_4_pse,
        )
        # test_worker.do_typing(test_worker.plugin.ui.lineEdit_input_csv_2, "")
        set_widget_value(
            test_worker.plugin.ui.comboBox_profile_type_2,
            test_worker.test_data.visualize_3_profile_type,
        )

        set_widget_value(
            test_worker.plugin.ui.checkBox_global_score_policy,
            test_worker.test_data.visualize_3_use_global_score,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.visualize_3_score_reversed,
        )
        set_widget_value(
            test_worker.plugin.ui.comboBox_best_leaf,
            test_worker.test_data.visualize_4_mutant_label,
        )
        set_widget_value(
            test_worker.plugin.ui.comboBox_totalscore,
            test_worker.test_data.visualize_4_score_label,
        )

        set_widget_value(
            test_worker.plugin.ui.comboBox_group_name,
            test_worker.test_data.visualize_4_group_label,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_run",
        )

        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_run",
        )

        assert os.path.exists(test_worker.test_data.visualize_4_pse)
        mt = test_worker.check_existed_mutant_tree()
        assert len(mt.all_mutant_branch_ids) == 3
        for _id in ["low", "medium", "high"]:
            assert _id in mt.all_mutant_branch_ids

    def test_visualize_from_excel_grouped(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )
        test_worker.go_to_tab(tab_name="visualize")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.visualize_excel,  # 12.16s call for full, 8.47s call for reduced
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.visualize_5_pse,
        )
        # test_worker.do_typing(test_worker.plugin.ui.lineEdit_input_csv_2, "")
        set_widget_value(
            test_worker.plugin.ui.comboBox_profile_type_2,
            test_worker.test_data.visualize_3_profile_type,
        )

        set_widget_value(
            test_worker.plugin.ui.checkBox_global_score_policy,
            test_worker.test_data.visualize_3_use_global_score,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.visualize_5_score_reversed,
        )
        set_widget_value(
            test_worker.plugin.ui.comboBox_best_leaf,
            test_worker.test_data.visualize_5_mutant_label,
        )
        set_widget_value(
            test_worker.plugin.ui.comboBox_totalscore,
            test_worker.test_data.visualize_5_score_label,
        )

        set_widget_value(
            test_worker.plugin.ui.comboBox_group_name,
            test_worker.test_data.visualize_5_group_label,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_run",
        )

        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_run",
        )

        assert os.path.exists(test_worker.test_data.visualize_5_pse)
        mt = test_worker.check_existed_mutant_tree()
        assert len(mt.all_mutant_branch_ids) == 4
        for _id in [f"c.{i}" for i in range(0, 4)]:
            assert _id in mt.all_mutant_branch_ids
