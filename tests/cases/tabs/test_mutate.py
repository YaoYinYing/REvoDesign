import os

import pytest

from REvoDesign.magician.designers import ColabDesigner_MPNN
from REvoDesign.tools.customized_widgets import set_widget_value
from tests.conftest import TestWorker
from tests.data.test_data import KeyData

os.environ["PYTEST_QT_API"] = "pyqt5"


@pytest.mark.serial
class TestREvoDesignPlugin_TabMutate:
    def test_pssm_ent_surf(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="mutate")

        pssm_file = KeyDataDuringTests.pssm_file

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_csv, pssm_file
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_customized_indices,
            KeyDataDuringTests.surface_file,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_mutate,
            test_worker.test_data.entro_design_pse,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_score_minima,
            test_worker.test_data.entropy_min_score,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_score_maxima,
            test_worker.test_data.entropy_max_score,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_reject_substitution,
            test_worker.test_data.entropy_reject,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_preffer_substitution,
            test_worker.test_data.entropy_accept,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_design_case,
            test_worker.test_data.entropy_design_case,
        )

        if os.path.exists(test_worker.test_data.entro_design_pse):
            os.remove(test_worker.test_data.entro_design_pse)

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
        test_worker.pse_snapshot('fin')

    @pytest.mark.skipif(
        not ColabDesigner_MPNN.installed, reason="ColabDesign not installed"
    )
    def test_mpnn_surf(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )

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
            test_worker.test_data.mpnn_design_pse,
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

        if os.path.exists(test_worker.test_data.mpnn_design_pse):
            os.remove(test_worker.test_data.mpnn_design_pse)

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

    def test_ddg_surf_non_biolib_calling(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )
        test_worker.go_to_tab(tab_name="mutate")

        test_worker.do_typing(
            test_worker.plugin.ui.comboBox_profile_type,
            test_worker.test_data.ddg_profile_type_local,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_csv, KeyDataDuringTests.ddg_file
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_customized_indices,
            test_worker.test_data.ddg_surface_residues,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_mutate,
            test_worker.test_data.ddg_design_non_biolib_pse,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_score_minima,
            test_worker.test_data.ddg_min_score,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_score_maxima,
            test_worker.test_data.ddg_max_score,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_reject_substitution,
            test_worker.test_data.pocket_pssm_reject,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_preffer_substitution,
            "",
        )

        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.ddg_score_reversed,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_design_case,
            test_worker.test_data.ddg_design_case,
        )

        if os.path.exists(test_worker.test_data.ddg_design_pse):
            os.remove(test_worker.test_data.ddg_design_case)

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

        test_worker.pse_snapshot('fin')

    # def test_ddg_surf_biolib_calling(
    #     self, test_worker
    # ):
    #
    #     test_worker.load_session_and_check()
    #     test_worker.go_to_tab(tab_name='mutate')

    #     set_widget_value(
    #         test_worker.plugin.ui.comboBox_profile_type,
    #         test_worker.test_data.ddg_profile_type_biolib,
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.lineEdit_input_customized_indices,
    #         test_worker.test_data.ddg_surface_residues,
    #     )
    #     set_widget_value(
    #         test_worker.plugin.ui.lineEdit_output_pse_mutate,
    #         test_worker.test_data.ddg_design_pse,
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.lineEdit_score_minima,
    #         test_worker.test_data.ddg_min_score,
    #     )
    #     set_widget_value(
    #         test_worker.plugin.ui.lineEdit_score_maxima,
    #         test_worker.test_data.ddg_max_score,
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.lineEdit_reject_substitution,
    #         test_worker.test_data.pocket_pssm_reject,
    #     )
    #     set_widget_value(
    #         test_worker.plugin.ui.lineEdit_preffer_substitution,
    #         '',
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.checkBox_reverse_mutant_effect,
    #         test_worker.test_data.ddg_score_reversed,
    #     )

    #     set_widget_value(
    #         test_worker.plugin.ui.lineEdit_design_case,
    #         test_worker.test_data.ddg_design_case,
    #     )

    #     if os.path.exists(test_worker.test_data.ddg_design_pse):
    #         os.remove(test_worker.test_data.ddg_design_case)

    #     test_worker.click(widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse)

    #     test_worker.save_screenshot(
    #         widget=test_worker.plugin.window,
    #         basename=test_worker.test_id,
    #     )

    #     pythia_results = [
    #         f for f in os.listdir('pythia') if f.endswith('.csv')
    #     ]
    #     if pythia_results:
    #         test_worker.check_existed_mutant_tree()
    #         test_worker.save_pymol_png(basename=test_worker.test_id)

    def test_pssm_pocket_design_dunbrack(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )
        test_worker.go_to_tab(tab_name="mutate")

        pssm_file = KeyDataDuringTests.pssm_file

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_csv, pssm_file
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_customized_indices,
            test_worker.test_data.pocket_pssm_residues,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_mutate,
            test_worker.test_data.pocket_design_pse,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_score_minima,
            test_worker.test_data.pocket_pssm_min_score,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_score_maxima,
            test_worker.test_data.pocket_pssm_max_score,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_reject_substitution,
            test_worker.test_data.pocket_pssm_reject,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_preffer_substitution,
            test_worker.test_data.pocket_pssm_accept,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_design_case,
            test_worker.test_data.pocket_pssm_design_case,
        )

        if os.path.exists(test_worker.test_data.pocket_design_pse):
            os.remove(test_worker.test_data.pocket_design_pse)

        test_worker.save_new_experiment()
        test_worker.click(
            widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse
        )
        test_worker.check_existed_mutant_tree()

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)
        test_worker.pse_snapshot('fin')
