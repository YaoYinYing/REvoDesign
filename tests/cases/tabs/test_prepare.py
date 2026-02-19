# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import glob
import os

import pytest
from pymol import cmd

from REvoDesign.tools.customized_widgets import set_widget_value
from tests.conftest import TestWorker

os.environ["PYTEST_QT_API"] = "pyqt5"

# move to the fast


@pytest.mark.order(2)
class TestREvoDesignPlugin_TabPrepare:
    def test_load_molecule(self, test_worker: TestWorker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check(from_rcsb=True)
        test_worker.go_to_tab(tab_name="prepare")

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)
        test_worker.save_new_experiment()

    def test_pocket(self, test_worker: TestWorker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check(from_rcsb=True)
        test_worker.go_to_tab(tab_name="prepare")

        test_worker.do_typing(
            test_worker.plugin.ui.comboBox_ligand_sel,
            test_worker.test_data.substrate,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.comboBox_cofactor_sel,
            test_worker.test_data.cofactor,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_pocket,
            test_worker.test_data.pocket_pse,
        )

        test_worker.qtbot.wait(100)
        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.click(
            widget=test_worker.plugin.ui.pushButton_run_pocket_detection,
        )
        test_worker.qtbot.wait(100)

        pocket_file_dir = os.path.abspath("./pockets/")
        assert os.path.exists(test_worker.test_data.pocket_pse)
        assert os.path.exists(pocket_file_dir)
        pocket_files = glob.glob(os.path.join(pocket_file_dir, "*.txt"))
        assert len(pocket_files) == 4

        pocket_file_design_shell = [fn for fn in pocket_files if "design_shell" in fn][0]

        assert pocket_file_design_shell is not None

        with open(pocket_file_design_shell) as ds_fr:
            design_shell_residue_ids = ds_fr.read().strip()
            assert design_shell_residue_ids

        test_worker.save_pymol_png(basename=test_worker.test_id, spells="orient hetatm")
        test_worker.save_new_experiment()
        test_worker.pse_snapshot("fin")

    def test_surface(self, test_worker: TestWorker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="prepare")

        test_worker.click(widget=test_worker.plugin.ui.pushButton_run_surface_refresh)

        hetatm_residues = [sel for sel in cmd.get_names(type="selections") if "pkt_hetatm_" in sel][0]
        assert hetatm_residues

        test_worker.do_typing(test_worker.plugin.ui.comboBox_surface_exclusion, hetatm_residues)

        set_widget_value(
            test_worker.plugin.ui.doubleSpinBox_surface_cutoff,
            test_worker.test_data.suface_probe,
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_surface,
            test_worker.test_data.surface_pse,
        )

        test_worker.qtbot.wait(100)
        test_worker.click(
            widget=test_worker.plugin.ui.pushButton_run_surface_detection,
        )
        test_worker.qtbot.wait(100)

        surface_dir = os.path.abspath("./surface_residue_records/")
        assert os.path.exists(test_worker.test_data.surface_pse)
        assert os.path.exists(surface_dir)
        surface_files = glob.glob(
            os.path.join(
                surface_dir,
                f"{test_worker.test_data.molecule}_residues_cutoff_{test_worker.test_data.suface_probe:.1f}.txt",
            )
        )
        assert len(surface_files) == 1

        surface_file_design_shell = [fn for fn in surface_files if "residues_cutoff" in fn][0]

        assert surface_file_design_shell is not None

        with open(surface_file_design_shell) as ss_fr:
            surface_residue_ids = ss_fr.read().strip()
            assert surface_residue_ids

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id, spells="center")
        test_worker.save_new_experiment()
        test_worker.pse_snapshot("fin")
