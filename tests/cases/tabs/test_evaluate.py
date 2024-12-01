import os

from REvoDesign.tools.customized_widgets import (get_widget_value,
                                                 set_widget_value)

from ...conftest import TestWorker
from ...data.test_data import KeyData

os.environ["PYTEST_QT_API"] = "pyqt5"


class TestREvoDesignPlugin_TabEvaluate:
    def test_evaluate_pssm_ent_surf_best_hits(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.go_to_tab(tab_name="evaluate")

        test_worker.load_session_and_check(customized_session=KeyDataDuringTests.evaluate_pse_path)

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mut_table, KeyDataDuringTests.mutant_file
        )
        set_widget_value(test_worker.plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.entropy_score_reversed,
        )

        test_worker.click(
            widget=test_worker.plugin.ui.pushButton_reinitialize_mutant_choosing
        )
        test_worker.click(
            widget=test_worker.plugin.ui.pushButton_choose_lucky_mutant
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id, focus=False)

        assert not test_worker.plugin.evaluator.mutant_tree_pssm_selected.empty
        with open(KeyDataDuringTests.mutant_file) as mr:
            picked_mutants = mr.read().strip().split("\n")

        picked_mutants = test_worker.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            test_worker.plugin.evaluator.mutant_tree_pssm_selected.all_mutant_objects
        )
        test_worker.save_new_experiment()

    def test_evaluate_pssm_ent_surf_mannual_pick(self, test_worker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()

        test_worker.load_session_and_check(customized_session=KeyDataDuringTests.evaluate_pse_path)
        test_worker.go_to_tab(tab_name="evaluate")

        mutant_file = KeyDataDuringTests.minimum_mutant_file
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mut_table, mutant_file
        )
        set_widget_value(test_worker.plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.entropy_score_reversed,
        )
        _init = test_worker.plugin.ui.pushButton_reinitialize_mutant_choosing
        _next = test_worker.plugin.ui.pushButton_next_mutant
        test_worker.plugin.ui.pushButton_previous_mutant
        _acp = test_worker.plugin.ui.pushButton_accept_this_mutant
        test_worker.plugin.ui.pushButton_reject_this_mutant
        _bsh = test_worker.plugin.ui.pushButton_goto_best_hit_in_group

        test_worker.click(_init).click(_next, 2).click(_acp)

        test_worker.click(_next, 3).click(_acp)

        test_worker.click(_next, 2).click(_acp)

        test_worker.click(_next, 5).click(_bsh).click(_acp)

        assert (
            int(
                get_widget_value(
                    test_worker.plugin.ui.lcdNumber_selected_mutant
                )
            )
            == 4
        )

        test_worker.click(_next, 2)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id, focus=False)

        assert not test_worker.plugin.evaluator.mutant_tree_pssm_selected.empty
        with open(mutant_file) as mr:
            picked_mutants = mr.read().strip().split("\n")

        picked_mutants = test_worker.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            test_worker.plugin.evaluator.mutant_tree_pssm_selected.all_mutant_objects
        )
        test_worker.save_new_experiment()
