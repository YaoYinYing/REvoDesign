import os

import pytest
from pymol import cmd

from REvoDesign.magician.designers import ColabDesigner_MPNN
from REvoDesign.tools.customized_widgets import (QButtonBrick,
                                                 get_widget_value,
                                                 set_widget_value)

from ...conftest import TestWorker
from ...data.test_data import KeyData

os.environ["PYTEST_QT_API"] = "pyqt5"


@pytest.mark.serial
@pytest.mark.very_slow
class TestREvoDesignPlugin_TabInteract:
    def test_gremlin_homomer_all2all(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()

        test_worker.load_session_and_check(
            from_rcsb=True,
            pdb_code=test_worker.test_data.gremlin_homomer_molecule,
            spell=test_worker.test_data.gremlin_homomer_postfetch_spell,
        )

        test_worker.pse_snapshot('loaded')
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )

        test_worker.go_to_tab(tab_name="interact")

        # buttons
        _next = test_worker.plugin.ui.pushButton_next
        _prev = test_worker.plugin.ui.pushButton_previous

        _accp = test_worker.plugin.ui.pushButton_interact_accept
        test_worker.plugin.ui.pushButton_interact_reject

        set_widget_value(
            test_worker.plugin.ui.lineEdit_input_gremlin_mtx, KeyDataDuringTests.gremlin_pkl_fp_homomer
        )

        set_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN,
            test_worker.test_data.gremlin_topN,
        )
        set_widget_value(
            test_worker.plugin.ui.lineEdit_interact_chain_binding,
            test_worker.test_data.gremlin_homomer_chains,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_interact_bind_chain_mode, True
        )

        mutfile = os.path.join("mutagenese", "gremlin_homomer_a2a.mut.txt")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_init",
        )

        test_worker.click(
            test_worker.plugin.ui.pushButton_reinitialize_interact
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_init",
        )
        test_worker.save_new_experiment()

        test_worker.click(test_worker.plugin.ui.pushButton_run_interact_scan)

        test_worker.sleep(300)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_scan",
        )

        test_worker.save_pymol_png(
            basename=f"{test_worker.test_id}_interact_pairs", focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith("cep")]
        for sel in ce_links:
            cmd.disable(sel)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_pair_0",
        )

        a2a_dir = test_worker.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith("Top.") and f.endswith(".csv")
        ]
        assert len(csv_files) == get_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN
        )

        cmd.save(test_worker.test_data.gremlin_homomer_a2a_pse)

        for operation in test_worker.test_data.gremlin_homomer_clicks_a2a:
            i = test_worker.c.i

            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                test_worker.click(
                    _next if operation > 0 else _prev, abs(operation)
                )
                test_worker.save_screenshot(
                    widget=test_worker.plugin.window,
                    basename=f"{test_worker.test_id}_pair_{operation}",
                )
                cmd.orient(test_worker.test_data.gremlin_homomer_molecule)
                test_worker.pse_snapshot(f'mut_{i}_{operation}')
                test_worker.save_pymol_png(
                    basename=f"{test_worker.test_id}_interact_pair_{i}_{operation}",
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            test_worker.click(
                test_worker.plugin.bus.w2c.get_button_from_id(
                    f"{row}_vs_{col}", prefix="matrixButton", button_type=QButtonBrick
                )
            )
            test_worker.sleep(200)

            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}",
            )

            test_worker.save_pymol_png(
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}",
                focus=False,
            )
            test_worker.check_existed_mutant_tree()

            cmd.orient(
                test_worker.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            test_worker.save_pymol_png(
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}_orient",
                focus=False,
            )
            test_worker.click(_accp)

        assert os.path.exists(mutfile)
        test_worker.pse_snapshot('fin')

        del test_worker.plugin.gremlin_worker.gremlin_tool
        del test_worker.plugin.gremlin_worker.coevolved_pairs
        del test_worker.plugin.gremlin_worker

    def test_gremlin_homomer_one2all(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check(
            from_rcsb=True,
            pdb_code=test_worker.test_data.gremlin_homomer_molecule,
            spell=test_worker.test_data.gremlin_homomer_postfetch_spell,
        )
        test_worker.pse_snapshot('loaded')
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )

        test_worker.go_to_tab(tab_name="interact")

        # buttons
        _next = test_worker.plugin.ui.pushButton_next
        _prev = test_worker.plugin.ui.pushButton_previous

        _accp = test_worker.plugin.ui.pushButton_interact_accept
        test_worker.plugin.ui.pushButton_interact_reject

        gremlin_pkl_fp = KeyDataDuringTests.gremlin_pkl_fp_homomer
        set_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN,
            test_worker.test_data.gremlin_topN,
        )

        set_widget_value(
            test_worker.plugin.ui.lineEdit_input_gremlin_mtx, gremlin_pkl_fp
        )

        set_widget_value(
            test_worker.plugin.ui.lineEdit_interact_chain_binding,
            test_worker.test_data.gremlin_homomer_chains,
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_interact_bind_chain_mode, True
        )

        mutfile = os.path.join("mutagenese", "gremlin_homomer_o2a.mut.txt")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_init",
        )

        test_worker.click(
            test_worker.plugin.ui.pushButton_reinitialize_interact
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_init",
        )
        test_worker.save_new_experiment()

        cmd.select("sele", test_worker.test_data.gremlin_homomer_o2a_sele)
        cmd.enable("sele")

        test_worker.pse_snapshot('sele')

        test_worker.click(test_worker.plugin.ui.pushButton_run_interact_scan)

        test_worker.sleep(200)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_scan",
        )

        test_worker.save_pymol_png(
            basename=f"{test_worker.test_id}_interact_pairs", focus=False
        )

        test_worker.pse_snapshot('check_interacts')

        ce_links = [sel for sel in cmd.get_names() if sel.startswith("cep")]
        for sel in ce_links:
            cmd.disable(sel)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_pair_0",
        )

        a2a_dir = test_worker.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith("Top.") and f.endswith(".csv")
        ]
        assert len(csv_files) == get_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN
        )

        cmd.save(test_worker.test_data.gremlin_homomer_o2a_pse)

        for operation in test_worker.test_data.gremlin_homomer_clicks_o2a:
            i = test_worker.c.i

            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                test_worker.click(
                    _next if operation > 0 else _prev, abs(operation)
                )
                test_worker.save_screenshot(
                    widget=test_worker.plugin.window,
                    basename=f"{test_worker.test_id}_pair_{operation}",
                )
                cmd.orient(test_worker.test_data.gremlin_homomer_molecule)
                test_worker.save_pymol_png(
                    basename=f"{test_worker.test_id}_interact_pair_{i}_{operation}",
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            test_worker.click(
                test_worker.plugin.bus.w2c.get_button_from_id(
                    f"{row}_vs_{col}", prefix="matrixButton", button_type=QButtonBrick
                )
            )
            test_worker.sleep(200)

            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}",
            )

            test_worker.save_pymol_png(
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}",
                focus=False,
            )
            test_worker.check_existed_mutant_tree()

            cmd.orient(
                test_worker.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            test_worker.save_pymol_png(
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}_orient",
                focus=False,
            )
            test_worker.click(_accp)

        assert os.path.exists(mutfile)

        del test_worker.plugin.gremlin_worker.gremlin_tool
        del test_worker.plugin.gremlin_worker.coevolved_pairs
        del test_worker.plugin.gremlin_worker

    def test_gremlin_all2all(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )
        test_worker.go_to_tab(tab_name="interact")

        # buttons
        _next = test_worker.plugin.ui.pushButton_next
        _prev = test_worker.plugin.ui.pushButton_previous

        _accp = test_worker.plugin.ui.pushButton_interact_accept
        test_worker.plugin.ui.pushButton_interact_reject

        set_widget_value(
            test_worker.plugin.ui.lineEdit_input_gremlin_mtx, KeyDataDuringTests.gremlin_pkl_fp
        )
        set_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN,
            test_worker.test_data.gremlin_topN,
        )

        mutfile = os.path.join("mutagenese", "gremlin_a2a.mut.txt")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_init",
        )

        test_worker.click(
            test_worker.plugin.ui.pushButton_reinitialize_interact
        )

        # assert os.path.exists(test_worker.test_data.visualize_2_pse)

        # test_worker.wait_for_file(file=f'{test_worker.test_data.molecule}_GREMLIN_mtx_zscore.png', interval=100,timeout=10)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_init",
        )
        test_worker.save_new_experiment()

        test_worker.click(test_worker.plugin.ui.pushButton_run_interact_scan)

        test_worker.sleep(200)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_scan",
        )

        test_worker.save_pymol_png(
            basename=f"{test_worker.test_id}_interact_pairs", focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith("cep")]
        for sel in ce_links:
            cmd.disable(sel)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_pair_0",
        )

        a2a_dir = test_worker.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith("Top.") and f.endswith(".csv")
        ]
        assert len(csv_files) == get_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN
        )

        for operation in test_worker.test_data.gremlin_monomer_clicks_a2a:
            i = test_worker.c.i
            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                test_worker.click(
                    _next if operation > 0 else _prev, abs(operation)
                )
                test_worker.save_screenshot(
                    widget=test_worker.plugin.window,
                    basename=f"{test_worker.test_id}_pair_{i}_{operation}",
                )
                cmd.orient(test_worker.test_data.molecule)
                test_worker.save_pymol_png(
                    basename=f"{test_worker.test_id}_interact_pair_{i}_{operation}",
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            test_worker.click(
                test_worker.plugin.bus.w2c.get_button_from_id(
                    f"{row}_vs_{col}", prefix="matrixButton", button_type=QButtonBrick
                )
            )
            test_worker.sleep(200)

            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}",
            )

            test_worker.save_pymol_png(
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}",
                focus=False,
            )
            test_worker.check_existed_mutant_tree()

            cmd.orient(
                test_worker.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            test_worker.save_pymol_png(
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}_orient",
                focus=False,
            )
            test_worker.click(_accp)

        assert os.path.exists(mutfile)

        del test_worker.plugin.gremlin_worker.gremlin_tool
        del test_worker.plugin.gremlin_worker.coevolved_pairs
        del test_worker.plugin.gremlin_worker

    @pytest.mark.skipif(
        not ColabDesigner_MPNN.installed, reason="ColabDesign not installed"
    )
    def test_gremlin_one2all_mpnn_score(self, test_worker: TestWorker, KeyDataDuringTests: KeyData):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.pse_snapshot('load')
        test_worker.go_to_tab(tab_name="config")

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            "Dunbrack Rotamer Library",
        )
        test_worker.go_to_tab(tab_name="interact")

        sele_resi = 295
        cmd.select(
            "sele",
            f"{test_worker.test_data.molecule} and c. {test_worker.test_data.chain_id} and i. {sele_resi} and n. CA",
        )
        cmd.enable("sele")

        test_worker.pse_snapshot('sele')

        # buttons
        _next = test_worker.plugin.ui.pushButton_next
        _prev = test_worker.plugin.ui.pushButton_previous

        _accp = test_worker.plugin.ui.pushButton_interact_accept
        test_worker.plugin.ui.pushButton_interact_reject

        set_widget_value(
            test_worker.plugin.ui.lineEdit_input_gremlin_mtx,
            KeyDataDuringTests.gremlin_pkl_fp,
        )

        set_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN,
            test_worker.test_data.gremlin_topN,
        )

        mutfile = os.path.join("mutagenese", "gremlin_o2a.mut.txt")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        set_widget_value(
            test_worker.plugin.ui.comboBox_external_scorer, "ProteinMPNN"
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_before_init",
        )

        test_worker.click(
            test_worker.plugin.ui.pushButton_reinitialize_interact
        )

        test_worker.save_new_experiment()
        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_init",
        )

        test_worker.click(test_worker.plugin.ui.pushButton_run_interact_scan)

        test_worker.sleep(200)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_after_scan",
        )

        test_worker.save_pymol_png(
            basename=f"{test_worker.test_id}_interact_pairs", focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith("cep")]
        for sel in ce_links:
            cmd.disable(sel)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}_pair_0",
        )

        o2a_dir = test_worker.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(o2a_dir)
        csv_files = [
            f
            for f in os.listdir(o2a_dir)
            if f.startswith("Top.") and f.endswith(".csv")
        ]
        assert len(csv_files) == get_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN
        )

        for operation in test_worker.test_data.gremlin_monomer_clicks_o2a:
            i = test_worker.c.i
            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                test_worker.click(
                    _next if operation > 0 else _prev, abs(operation)
                )
                test_worker.save_screenshot(
                    widget=test_worker.plugin.window,
                    basename=f"{test_worker.test_id}_pair_{i}_{operation}",
                )
                cmd.orient(test_worker.test_data.molecule)
                test_worker.save_pymol_png(
                    basename=f"{test_worker.test_id}_interact_pair_{i}_{operation}",
                    focus=False,
                )
                continue

            assert len(operation) == 2
            row, col = operation

            i = test_worker.c.i
            test_worker.click(
                test_worker.plugin.bus.w2c.get_button_from_id(
                    f"{row}_vs_{col}", prefix="matrixButton", button_type=QButtonBrick
                )
            )
            test_worker.sleep(200)

            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}",
            )

            test_worker.save_pymol_png(
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}",
                focus=False,
            )
            test_worker.check_existed_mutant_tree()

            cmd.orient(
                test_worker.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            test_worker.save_pymol_png(
                basename=f"{test_worker.test_id}_{i}_pick_{row}_{col}_orient",
                focus=False,
            )
            test_worker.click(_accp)

        cmd.orient(test_worker.test_data.molecule)
        test_worker.pse_snapshot('fin')

        assert os.path.exists(mutfile)

        del test_worker.plugin.gremlin_worker.gremlin_tool
        del test_worker.plugin.gremlin_worker.coevolved_pairs
        del test_worker.plugin.gremlin_worker
