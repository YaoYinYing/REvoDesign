
import os


import pytest


from REvoDesign.sidechain_solver.mutate_runner.PIPPack import PIPPack_worker
from REvoDesign.tools.customized_widgets import (get_widget_value,
                                                 set_widget_value)

from ...conftest import TestWorker


os.environ["PYTEST_QT_API"] = "pyqt5"




class TestREvoDesignPlugin_TabConfig:
    @pytest.mark.skipif(
        not PIPPack_worker.installed, reason="PIPPack not installed"
    )
    def test_use_pippack_mpnn_design(self, test_worker:TestWorker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver, "PIPPack"
        )
        assert (
            get_widget_value(
                test_worker.plugin.ui.comboBox_sidechain_solver_model,
            )
            == "ensemble"
        )

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver_model,
            "pippack_model_1",
        )
        assert (
            get_widget_value(
                test_worker.plugin.ui.comboBox_sidechain_solver_model,
            )
            == "pippack_model_1"
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_use_PIPPack_model_1",
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)

        # back to tab mutate and run mpnn redesign, saved as another file
        test_worker.go_to_tab(tab_name="mutate")

        set_widget_value(
            test_worker.plugin.ui.comboBox_profile_type,
            test_worker.test_data.mpnn_profile_type,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_customized_indices,
            test_worker.test_data.mpnn_surface_residues,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_mutate,
            test_worker.test_data.pippack_pse,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_reject_substitution,
            test_worker.test_data.mpnn_reject,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_preffer_substitution,
            test_worker.test_data.mpnn_accept,
        )

        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.mpnn_score_reversed,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_design_case,
            test_worker.test_data.mpnn_design_case,
        )

        set_widget_value(
            test_worker.plugin.ui.doubleSpinBox_designer_temperature,
            test_worker.test_data.mpnn_temperature,
        )

        set_widget_value(
            test_worker.plugin.ui.spinBox_designer_batch,
            test_worker.test_data.mpnn_batch_designs,
        )
        set_widget_value(
            test_worker.plugin.ui.spinBox_designer_num_samples,
            test_worker.test_data.mpnn_num_designs,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_deduplicate_designs,
            test_worker.test_data.mpnn_deduplicated,
        )

        if os.path.exists(test_worker.test_data.pippack_pse):
            os.remove(test_worker.test_data.pippack_pse)

        test_worker.save_new_experiment()
        test_worker.click(
            widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.check_existed_mutant_tree()

    # deprecated
    # @patch('REvoDesign.sidechain_solver.mutate_runner.PIPPack.PIPPack_worker.installed', False)
    # def test_sidechain_solver_fallback_mpnn(self, test_worker):
    #     test_worker.test_id = test_worker.method_name()
    #     test_worker.load_session_and_check()
    #     test_worker.go_to_tab(tab_name='config')
    #     from REvoDesign.sidechain_solver.mutate_runner.PIPPack import \
    #         PIPPack_worker

    #     assert (
    #         PIPPack_worker.installed is False
    #     )

    #     set_widget_value(test_worker.plugin.ui.comboBox_sidechain_solver, 'PIPPack')
    #     assert (
    #         get_widget_value(
    #             test_worker.plugin.ui.comboBox_sidechain_solver_model,
    #         )
    #         == 'ensemble'
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.comboBox_sidechain_solver_model,
    #         'pippack_model_1',
    #     )
    #     assert (
    #         get_widget_value(
    #             test_worker.plugin.ui.comboBox_sidechain_solver_model,
    #         )
    #         == 'pippack_model_1'
    #     )

    #     test_worker.save_screenshot(
    #         widget=test_worker.plugin.window,
    #         basename=f'{test_worker.test_id}_use_PIPPack_model_1',
    #     )
    #     test_worker.save_pymol_png(basename=test_worker.test_id)

    #     # back to tab mutate and run mpnn redesign, saved as another file
    #     test_worker.go_to_tab(tab_name='mutate')

    #     set_widget_value(
    #         test_worker.plugin.ui.comboBox_profile_type,
    #         test_worker.test_data.mpnn_profile_type,
    #     )
    #     test_worker.do_typing(
    #         test_worker.plugin.ui.lineEdit_input_customized_indices,
    #         test_worker.test_data.mpnn_surface_residues,
    #     )
    #     test_worker.do_typing(
    #         test_worker.plugin.ui.lineEdit_output_pse_mutate,
    #         test_worker.test_data.sidechain_solver_fallback_pse,
    #     )

    #     test_worker.do_typing(
    #         test_worker.plugin.ui.lineEdit_reject_substitution,
    #         test_worker.test_data.mpnn_reject,
    #     )
    #     test_worker.do_typing(
    #         test_worker.plugin.ui.lineEdit_preffer_substitution,
    #         test_worker.test_data.mpnn_accept,
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.checkBox_reverse_mutant_effect,
    #         test_worker.test_data.mpnn_score_reversed,
    #     )

    #     test_worker.do_typing(
    #         test_worker.plugin.ui.lineEdit_design_case,
    #         test_worker.test_data.mpnn_design_case,
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.doubleSpinBox_designer_temperature,
    #         test_worker.test_data.mpnn_temperature,
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.spinBox_designer_batch,
    #         test_worker.test_data.mpnn_batch_designs,
    #     )
    #     set_widget_value(
    #         test_worker.plugin.ui.spinBox_designer_num_samples,
    #         test_worker.test_data.mpnn_num_designs,
    #     )
    #     set_widget_value(
    #         test_worker.plugin.ui.checkBox_deduplicate_designs,
    #         test_worker.test_data.mpnn_deduplicated,
    #     )

    #     if os.path.exists(test_worker.test_data.sidechain_solver_fallback_pse):
    #         os.remove(test_worker.test_data.sidechain_solver_fallback_pse)

    #     test_worker.save_new_experiment()
    #     test_worker.save_screenshot(
    #         widget=test_worker.plugin.window,
    #         basename=f'{test_worker.test_id}_setup',
    #     )
    #     test_worker.click(widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse)

    #     test_worker.go_to_tab(tab_name='config')
    #     test_worker.save_screenshot(
    #         widget=test_worker.plugin.window,
    #         basename=f'{test_worker.test_id}_fallbacked',
    #     )

    #     assert (
    #         get_widget_value(
    #             test_worker.plugin.ui.comboBox_sidechain_solver,
    #         )
    #         == 'Dunbrack Rotamer Library'
    #     )

    #     test_worker.save_pymol_png(basename=test_worker.test_id)

    #     test_worker.check_existed_mutant_tree()
