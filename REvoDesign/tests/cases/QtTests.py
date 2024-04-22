import os
import glob
import random
import pytest

os.environ['PYTEST_QT_API'] = 'pyqt5'

import pytest
from pymol import cmd
from REvoDesign.tools.customized_widgets import (
    get_widget_value,
    set_widget_value,
)

from REvoDesign.tests import *


class TestREvoDesignPlugin:
    def test_plugin_gui_visibility(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        # Check if the main window of the plugin is visible
        assert WORKER.plugin.window.isVisible()
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        for tab in WORKER.tab_widget_mapping.keys():
            WORKER.go_to_tab(tab_name=tab)
            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'test_tab_{tab}',
            )


class TestREvoDesignPlugin_TabPrepare:
    def test_load_molecule(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check(from_rcsb=True)
        WORKER.go_to_tab(tab_name='prepare')

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id)
        WORKER.save_new_experiment()

    def test_pocket(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check(from_rcsb=True)
        WORKER.go_to_tab(tab_name='prepare')

        WORKER.do_typing(
            WORKER.plugin.ui.comboBox_ligand_sel,
            WORKER.test_data.substrate,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.comboBox_cofactor_sel,
            WORKER.test_data.cofactor,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_pocket,
            WORKER.test_data.pocket_pse,
        )

        WORKER.qtbot.wait(100)
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.click(
            widget=WORKER.plugin.ui.pushButton_run_pocket_detection,
        )
        WORKER.qtbot.wait(100)

        pocket_file_dir = os.path.abspath('./pockets/')
        assert os.path.exists(WORKER.test_data.pocket_pse)
        assert os.path.exists(pocket_file_dir)
        pocket_files = glob.glob(os.path.join(pocket_file_dir, '*.txt'))
        assert len(pocket_files) == 4

        pocket_file_design_shell = [
            fn for fn in pocket_files if 'design_shell' in fn
        ][0]

        KeyDataDuringTests.design_shell_file = os.path.join(
            pocket_file_dir, os.path.basename(pocket_file_design_shell)
        )

        assert pocket_file_design_shell is not None

        with open(pocket_file_design_shell, 'r') as ds_fr:
            design_shell_residue_ids = ds_fr.read().strip()
            assert design_shell_residue_ids

        WORKER.save_pymol_png(basename=WORKER.test_id, spells='orient hetatm')
        WORKER.save_new_experiment()

    def test_surface(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='prepare')

        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_surface_refresh)

        hetatm_residues = [
            sel
            for sel in cmd.get_names(type='selections')
            if 'pkt_hetatm_' in sel
        ][0]
        assert hetatm_residues

        KeyDataDuringTests.hetatm_pocket_sele = hetatm_residues

        WORKER.do_typing(
            WORKER.plugin.ui.comboBox_surface_exclusion, hetatm_residues
        )

        set_widget_value(
            WORKER.plugin.ui.doubleSpinBox_surface_cutoff,
            WORKER.test_data.suface_probe,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_surface,
            WORKER.test_data.surface_pse,
        )

        WORKER.qtbot.wait(100)
        WORKER.click(
            widget=WORKER.plugin.ui.pushButton_run_surface_detection,
        )
        WORKER.qtbot.wait(100)

        surface_dir = os.path.abspath('./surface_residue_records/')
        assert os.path.exists(WORKER.test_data.surface_pse)
        assert os.path.exists(surface_dir)
        surface_files = glob.glob(
            os.path.join(
                surface_dir,
                f'{WORKER.test_data.molecule}_residues_cutoff_{WORKER.test_data.suface_probe:.1f}.txt',
            )
        )
        assert len(surface_files) == 1

        surface_file_design_shell = [
            fn for fn in surface_files if 'residues_cutoff' in fn
        ][0]

        assert surface_file_design_shell is not None

        KeyDataDuringTests.surface_file = os.path.join(
            surface_dir, os.path.basename(surface_file_design_shell)
        )

        with open(surface_file_design_shell, 'r') as ss_fr:
            surface_residue_ids = ss_fr.read().strip()
            assert surface_residue_ids

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id, spells='center')
        WORKER.save_new_experiment()


class TestREvoDesignPlugin_TabMutate:
    def test_pssm_ent_surf(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='mutate')

        expected_downloaded_file = WORKER.download_file(
            url=WORKER.test_data.PSSM_GREMLIN_DATA_URL,
            md5=WORKER.test_data.PSSM_GREMLIN_DATA_MD5,
        )

        dist_dir, expanded_files = WORKER.expand_zip(
            compressed_file=expected_downloaded_file
        )

        assert expanded_files
        pssm_file = os.path.join(
            dist_dir,
            'pssm_msa',
            f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}_ascii_mtx_file',
        )
        assert os.path.exists(pssm_file)

        KeyDataDuringTests.pssm_file = pssm_file

        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_csv, pssm_file)
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            KeyDataDuringTests.surface_file,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.entro_design_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_minima,
            WORKER.test_data.entropy_min_score,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.entropy_max_score,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.entropy_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.entropy_accept,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.entropy_design_case,
        )

        if os.path.exists(WORKER.test_data.entro_design_pse):
            os.remove(WORKER.test_data.entro_design_pse)

        WORKER.save_new_experiment()
        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id)

        WORKER.check_existed_mutant_tree()

    def test_mpnn_surf(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )

        WORKER.go_to_tab(tab_name='mutate')

        set_widget_value(
            WORKER.plugin.ui.comboBox_profile_type,
            WORKER.test_data.mpnn_profile_type,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.mpnn_surface_residues,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.mpnn_design_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.mpnn_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.mpnn_accept,
        )

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.mpnn_score_reversed,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.mpnn_design_case,
        )

        set_widget_value(
            WORKER.plugin.ui.doubleSpinBox_designer_temperature,
            WORKER.test_data.mpnn_temperature,
        )

        set_widget_value(
            WORKER.plugin.ui.spinBox_designer_batch,
            WORKER.test_data.mpnn_batch_designs,
        )
        set_widget_value(
            WORKER.plugin.ui.spinBox_designer_num_samples,
            WORKER.test_data.mpnn_num_designs,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_deduplicate_designs,
            WORKER.test_data.mpnn_deduplicated,
        )

        if os.path.exists(WORKER.test_data.mpnn_design_pse):
            os.remove(WORKER.test_data.mpnn_design_pse)

        WORKER.save_new_experiment()
        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id)

        WORKER.check_existed_mutant_tree()

    def test_ddg_surf_non_biolib_calling(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        WORKER.go_to_tab(tab_name='mutate')

        local_ddg_file = WORKER.download_file(
            url=WORKER.test_data.PYTHIA_DDG_CSV_URL,
            md5=WORKER.test_data.PYTHIA_DDG_CSV_MD5,
        )

        KeyDataDuringTests.ddg_file = local_ddg_file

        WORKER.do_typing(
            WORKER.plugin.ui.comboBox_profile_type,
            WORKER.test_data.ddg_profile_type_local,
        )
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_csv, local_ddg_file)

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.ddg_surface_residues,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.ddg_design_non_biolib_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_minima,
            WORKER.test_data.ddg_min_score,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.ddg_max_score,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.pocket_pssm_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            '',
        )

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.ddg_score_reversed,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.ddg_design_case,
        )

        if os.path.exists(WORKER.test_data.ddg_design_pse):
            os.remove(WORKER.test_data.ddg_design_case)

        WORKER.save_new_experiment()

        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id)

        WORKER.check_existed_mutant_tree()

    # def test_ddg_surf_biolib_calling(
    #     self, WORKER: TestWorker
    # ):
    #
    #     WORKER.load_session_and_check()
    #     WORKER.go_to_tab(tab_name='mutate')

    #     set_widget_value(
    #         WORKER.plugin.ui.comboBox_profile_type,
    #         WORKER.test_data.ddg_profile_type_biolib,
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_input_customized_indices,
    #         WORKER.test_data.ddg_surface_residues,
    #     )
    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_output_pse_mutate,
    #         WORKER.test_data.ddg_design_pse,
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_score_minima,
    #         WORKER.test_data.ddg_min_score,
    #     )
    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_score_maxima,
    #         WORKER.test_data.ddg_max_score,
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_reject_substitution,
    #         WORKER.test_data.pocket_pssm_reject,
    #     )
    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_preffer_substitution,
    #         '',
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.checkBox_reverse_mutant_effect,
    #         WORKER.test_data.ddg_score_reversed,
    #     )

    #     set_widget_value(
    #         WORKER.plugin.ui.lineEdit_design_case,
    #         WORKER.test_data.ddg_design_case,
    #     )

    #     if os.path.exists(WORKER.test_data.ddg_design_pse):
    #         os.remove(WORKER.test_data.ddg_design_case)

    #     WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

    #     WORKER.save_screenshot(
    #         widget=WORKER.plugin.window,
    #         basename=WORKER.test_id,
    #     )

    #     pythia_results = [
    #         f for f in os.listdir('pythia') if f.endswith('.csv')
    #     ]
    #     if pythia_results:
    #         WORKER.check_existed_mutant_tree()
    #         WORKER.save_pymol_png(basename=WORKER.test_id)

    def test_pssm_pocket_design_dunbrack(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        WORKER.go_to_tab(tab_name='mutate')

        expected_downloaded_file = WORKER.download_file(
            url=WORKER.test_data.PSSM_GREMLIN_DATA_URL,
            md5=WORKER.test_data.PSSM_GREMLIN_DATA_MD5,
        )

        dist_dir, expanded_files = WORKER.expand_zip(
            compressed_file=expected_downloaded_file
        )

        assert expanded_files
        pssm_file = os.path.join(
            dist_dir,
            'pssm_msa',
            f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}_ascii_mtx_file',
        )
        assert os.path.exists(pssm_file)

        KeyDataDuringTests.pssm_file = pssm_file

        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_csv, pssm_file)
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.pocket_pssm_residues,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.pocket_design_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_minima,
            WORKER.test_data.pocket_pssm_min_score,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_score_maxima,
            WORKER.test_data.pocket_pssm_max_score,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.pocket_pssm_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.pocket_pssm_accept,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.pocket_pssm_design_case,
        )

        if os.path.exists(WORKER.test_data.pocket_design_pse):
            os.remove(WORKER.test_data.pocket_design_pse)

        WORKER.save_new_experiment()
        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)
        WORKER.check_existed_mutant_tree()

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id)


@pytest.mark.order(-2)
class TestREvoDesignPlugin_TabInteract:
    def test_gremlin_homomer_all2all(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check(
            from_rcsb=True,
            pdb_code=WORKER.test_data.gremlin_homomer_molecule,
            spell=WORKER.test_data.gremlin_homomer_postfetch_spell,
        )
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )

        WORKER.go_to_tab(tab_name='interact')

        # buttons
        _next = WORKER.plugin.ui.pushButton_next
        _prev = WORKER.plugin.ui.pushButton_previous

        _accp = WORKER.plugin.ui.pushButton_interact_accept
        _rjct = WORKER.plugin.ui.pushButton_interact_reject

        zipped = WORKER.download_file(
            url=WORKER.test_data.gremlin_homomer_profile_url,
            md5=WORKER.test_data.gremlin_homomer_profile_md5,
        )

        dist_dir, extracted_files = WORKER.expand_zip(compressed_file=zipped)

        gremlin_pkl_fp = os.path.join(
            dist_dir,
            'gremlin_res',
            f'{WORKER.test_data.gremlin_homomer_molecule}_{WORKER.test_data.gremlin_homomer_chain}.i90c75_aln.GREMLIN.mrf.pkl',
        )

        set_widget_value(
            WORKER.plugin.ui.lineEdit_input_gremlin_mtx, gremlin_pkl_fp
        )

        KeyDataDuringTests.gremlin_pkl_fp_homomer = gremlin_pkl_fp

        set_widget_value(
            WORKER.plugin.ui.spinBox_gremlin_topN,
            WORKER.test_data.gremlin_topN,
        )
        set_widget_value(
            WORKER.plugin.ui.lineEdit_interact_chain_binding,
            WORKER.test_data.gremlin_homomer_chains,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_interact_bind_chain_mode, True
        )

        mutfile = os.path.join('mutagenese', 'gremlin_homomer_a2a.mut.txt')

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_before_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_reinitialize_interact)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_init',
        )
        WORKER.save_new_experiment()

        WORKER.click(WORKER.plugin.ui.pushButton_run_interact_scan)

        WORKER.sleep(300)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_scan',
        )

        WORKER.save_pymol_png(
            basename=f'{WORKER.test_id}_interact_pairs', focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith('cep')]
        for sel in ce_links:
            cmd.disable(sel)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_pair_0',
        )

        a2a_dir = WORKER.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith('Top.') and f.endswith('.csv')
        ]
        assert len(csv_files) == get_widget_value(
            WORKER.plugin.ui.spinBox_gremlin_topN
        )

        cmd.save(WORKER.test_data.gremlin_homomer_a2a_pse)

        for operation in WORKER.test_data.gremlin_homomer_clicks_a2a:
            i = WORKER.c.i

            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                WORKER.click(_next if operation > 0 else _prev, abs(operation))
                WORKER.save_screenshot(
                    widget=WORKER.plugin.window,
                    basename=f'{WORKER.test_id}_pair_{operation}',
                )
                cmd.orient(WORKER.test_data.molecule)
                WORKER.save_pymol_png(
                    basename=f'{WORKER.test_id}_interact_pair_{i}_{operation}',
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            WORKER.click(
                WORKER.plugin.bus.w2c.get_button_from_id(
                    f'{row}_vs_{col}', prefix='matrixButton'
                )
            )
            WORKER.sleep(200)

            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}',
            )

            WORKER.save_pymol_png(
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}', focus=False
            )
            WORKER.check_existed_mutant_tree()

            cmd.orient(
                WORKER.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            WORKER.save_pymol_png(
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}_orient',
                focus=False,
            )
            WORKER.click(_accp)

        assert os.path.exists(mutfile)

        del WORKER.plugin.gremlin_worker.gremlin_tool
        del WORKER.plugin.gremlin_worker.coevolved_pairs
        del WORKER.plugin.gremlin_worker

    def test_gremlin_homomer_one2all(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check(
            from_rcsb=True,
            pdb_code=WORKER.test_data.gremlin_homomer_molecule,
            spell=WORKER.test_data.gremlin_homomer_postfetch_spell,
        )
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )

        WORKER.go_to_tab(tab_name='interact')

        # buttons
        _next = WORKER.plugin.ui.pushButton_next
        _prev = WORKER.plugin.ui.pushButton_previous

        _accp = WORKER.plugin.ui.pushButton_interact_accept
        _rjct = WORKER.plugin.ui.pushButton_interact_reject

        gremlin_pkl_fp = KeyDataDuringTests.gremlin_pkl_fp_homomer
        set_widget_value(
            WORKER.plugin.ui.spinBox_gremlin_topN,
            WORKER.test_data.gremlin_topN,
        )

        set_widget_value(
            WORKER.plugin.ui.lineEdit_input_gremlin_mtx, gremlin_pkl_fp
        )

        set_widget_value(
            WORKER.plugin.ui.lineEdit_interact_chain_binding,
            WORKER.test_data.gremlin_homomer_chains,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_interact_bind_chain_mode, True
        )

        mutfile = os.path.join('mutagenese', 'gremlin_homomer_o2a.mut.txt')

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_before_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_reinitialize_interact)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_init',
        )
        WORKER.save_new_experiment()

        cmd.select('sele', WORKER.test_data.gremlin_homomer_o2a_sele)
        cmd.enable('sele')

        WORKER.click(WORKER.plugin.ui.pushButton_run_interact_scan)

        WORKER.sleep(200)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_scan',
        )

        WORKER.save_pymol_png(
            basename=f'{WORKER.test_id}_interact_pairs', focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith('cep')]
        for sel in ce_links:
            cmd.disable(sel)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_pair_0',
        )

        a2a_dir = WORKER.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith('Top.') and f.endswith('.csv')
        ]
        assert len(csv_files) == get_widget_value(
            WORKER.plugin.ui.spinBox_gremlin_topN
        )

        cmd.save(WORKER.test_data.gremlin_homomer_o2a_pse)

        for operation in WORKER.test_data.gremlin_homomer_clicks_o2a:
            i = WORKER.c.i

            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                WORKER.click(_next if operation > 0 else _prev, abs(operation))
                WORKER.save_screenshot(
                    widget=WORKER.plugin.window,
                    basename=f'{WORKER.test_id}_pair_{operation}',
                )
                cmd.orient(WORKER.test_data.molecule)
                WORKER.save_pymol_png(
                    basename=f'{WORKER.test_id}_interact_pair_{i}_{operation}',
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            WORKER.click(
                WORKER.plugin.bus.w2c.get_button_from_id(
                    f'{row}_vs_{col}', prefix='matrixButton'
                )
            )
            WORKER.sleep(200)

            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}',
            )

            WORKER.save_pymol_png(
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}', focus=False
            )
            WORKER.check_existed_mutant_tree()

            cmd.orient(
                WORKER.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            WORKER.save_pymol_png(
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}_orient',
                focus=False,
            )
            WORKER.click(_accp)

        assert os.path.exists(mutfile)

        del WORKER.plugin.gremlin_worker.gremlin_tool
        del WORKER.plugin.gremlin_worker.coevolved_pairs
        del WORKER.plugin.gremlin_worker

    def test_gremlin_all2all(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        WORKER.go_to_tab(tab_name='interact')

        # buttons
        _next = WORKER.plugin.ui.pushButton_next
        _prev = WORKER.plugin.ui.pushButton_previous

        _accp = WORKER.plugin.ui.pushButton_interact_accept
        _rjct = WORKER.plugin.ui.pushButton_interact_reject

        gremlin_pkl_fp = os.path.join(
            WORKER.EXPANDED_DIR,
            f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}_PSSM_GREMLIN_results',
            'gremlin_res',
            f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}.i90c75_aln.GREMLIN.mrf.pkl',
        )

        set_widget_value(
            WORKER.plugin.ui.lineEdit_input_gremlin_mtx, gremlin_pkl_fp
        )
        KeyDataDuringTests.gremlin_pkl_fp = gremlin_pkl_fp
        set_widget_value(
            WORKER.plugin.ui.spinBox_gremlin_topN,
            WORKER.test_data.gremlin_topN,
        )

        mutfile = os.path.join('mutagenese', 'gremlin_a2a.mut.txt')

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_before_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_reinitialize_interact)

        # assert os.path.exists(WORKER.test_data.visualize_2_pse)

        # WORKER.wait_for_file(file=f'{WORKER.test_data.molecule}_GREMLIN_mtx_zscore.png', interval=100,timeout=10)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_init',
        )
        WORKER.save_new_experiment()

        WORKER.click(WORKER.plugin.ui.pushButton_run_interact_scan)

        WORKER.sleep(200)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_scan',
        )

        WORKER.save_pymol_png(
            basename=f'{WORKER.test_id}_interact_pairs', focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith('cep')]
        for sel in ce_links:
            cmd.disable(sel)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_pair_0',
        )

        a2a_dir = WORKER.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith('Top.') and f.endswith('.csv')
        ]
        assert len(csv_files) == get_widget_value(
            WORKER.plugin.ui.spinBox_gremlin_topN
        )

        for operation in WORKER.test_data.gremlin_monomer_clicks_a2a:
            i = WORKER.c.i
            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                WORKER.click(_next if operation > 0 else _prev, abs(operation))
                WORKER.save_screenshot(
                    widget=WORKER.plugin.window,
                    basename=f'{WORKER.test_id}_pair_{i}_{operation}',
                )
                cmd.orient(WORKER.test_data.molecule)
                WORKER.save_pymol_png(
                    basename=f'{WORKER.test_id}_interact_pair_{i}_{operation}',
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            WORKER.click(
                WORKER.plugin.bus.w2c.get_button_from_id(
                    f'{row}_vs_{col}', prefix='matrixButton'
                )
            )
            WORKER.sleep(200)

            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}',
            )

            WORKER.save_pymol_png(
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}', focus=False
            )
            WORKER.check_existed_mutant_tree()

            cmd.orient(
                WORKER.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            WORKER.save_pymol_png(
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}_orient',
                focus=False,
            )
            WORKER.click(_accp)

        assert os.path.exists(mutfile)

        del WORKER.plugin.gremlin_worker.gremlin_tool
        del WORKER.plugin.gremlin_worker.coevolved_pairs
        del WORKER.plugin.gremlin_worker

    def test_gremlin_one2all_mpnn_score(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        WORKER.go_to_tab(tab_name='interact')

        sele_resi = 295
        cmd.select(
            'sele',
            f'{WORKER.test_data.molecule} and c. {WORKER.test_data.chain_id} and i. {sele_resi} and n. CA',
        )
        cmd.enable('sele')

        gremlin_pkl_fp = os.path.join(
            WORKER.EXPANDED_DIR,
            f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}_PSSM_GREMLIN_results',
            'gremlin_res',
            f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}.i90c75_aln.GREMLIN.mrf.pkl',
        )

        # buttons
        _next = WORKER.plugin.ui.pushButton_next
        _prev = WORKER.plugin.ui.pushButton_previous

        _accp = WORKER.plugin.ui.pushButton_interact_accept
        _rjct = WORKER.plugin.ui.pushButton_interact_reject

        set_widget_value(
            WORKER.plugin.ui.lineEdit_input_gremlin_mtx,
            gremlin_pkl_fp,
        )

        set_widget_value(
            WORKER.plugin.ui.spinBox_gremlin_topN,
            WORKER.test_data.gremlin_topN,
        )

        mutfile = os.path.join('mutagenese', 'gremlin_o2a.mut.txt')

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        set_widget_value(
            WORKER.plugin.ui.comboBox_external_scorer, 'ProteinMPNN'
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_before_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_reinitialize_interact)

        # assert os.path.exists(WORKER.test_data.visualize_2_pse)

        # WORKER.wait_for_file(file=f'{WORKER.test_data.molecule}_GREMLIN_mtx_zscore.png', interval=100,timeout=20)

        WORKER.save_new_experiment()
        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_init',
        )

        WORKER.click(WORKER.plugin.ui.pushButton_run_interact_scan)

        WORKER.sleep(200)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_scan',
        )

        WORKER.save_pymol_png(
            basename=f'{WORKER.test_id}_interact_pairs', focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith('cep')]
        for sel in ce_links:
            cmd.disable(sel)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_pair_0',
        )

        o2a_dir = WORKER.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(o2a_dir)
        csv_files = [
            f
            for f in os.listdir(o2a_dir)
            if f.startswith('Top.') and f.endswith('.csv')
        ]
        assert len(csv_files) == get_widget_value(
            WORKER.plugin.ui.spinBox_gremlin_topN
        )

        for operation in WORKER.test_data.gremlin_monomer_clicks_o2a:
            i = WORKER.c.i
            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                WORKER.click(_next if operation > 0 else _prev, abs(operation))
                WORKER.save_screenshot(
                    widget=WORKER.plugin.window,
                    basename=f'{WORKER.test_id}_pair_{i}_{operation}',
                )
                cmd.orient(WORKER.test_data.molecule)
                WORKER.save_pymol_png(
                    basename=f'{WORKER.test_id}_interact_pair_{i}_{operation}',
                    focus=False,
                )
                continue

            assert len(operation) == 2
            row, col = operation

            i = WORKER.c.i
            WORKER.click(
                WORKER.plugin.bus.w2c.get_button_from_id(
                    f'{row}_vs_{col}', prefix='matrixButton'
                )
            )
            WORKER.sleep(200)

            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}',
            )

            WORKER.save_pymol_png(
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}', focus=False
            )
            WORKER.check_existed_mutant_tree()

            cmd.orient(
                WORKER.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            WORKER.save_pymol_png(
                basename=f'{WORKER.test_id}_{i}_pick_{row}_{col}_orient',
                focus=False,
            )
            WORKER.click(_accp)

        cmd.orient(WORKER.test_data.molecule)

        assert os.path.exists(mutfile)

        del WORKER.plugin.gremlin_worker.gremlin_tool
        del WORKER.plugin.gremlin_worker.coevolved_pairs
        del WORKER.plugin.gremlin_worker


class TestREvoDesignPlugin_TabEvaluate:
    def test_evaluate_pssm_ent_surf_best_hits(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        pse_path = WORKER.download_file(
            url=WORKER.test_data.EVALUATION_PSE_URL,
            md5=WORKER.test_data.EVALUATION_PSE_MD5,
        )
        WORKER.load_session_and_check(customized_session=pse_path)
        WORKER.go_to_tab(tab_name='evaluate')

        KeyDataDuringTests.evaluate_pse_path = pse_path

        mutagenesis_dir = os.path.abspath('mutagenese')
        mutant_file = os.path.join(
            mutagenesis_dir, 'evaluate_pssm_ent_surf.besthits.mut.txt'
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_mut_table, mutant_file
        )
        set_widget_value(WORKER.plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.entropy_score_reversed,
        )

        WORKER.click(
            widget=WORKER.plugin.ui.pushButton_reinitialize_mutant_choosing
        )
        WORKER.click(widget=WORKER.plugin.ui.pushButton_choose_lucky_mutant)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id, focus=False)

        assert not WORKER.plugin.evaluator.mutant_tree_pssm_selected.empty
        with open(mutant_file, 'r') as mr:
            picked_mutants = mr.read().strip().split('\n')

        picked_mutants = WORKER.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            WORKER.plugin.evaluator.mutant_tree_pssm_selected.all_mutant_objects
        )
        KeyDataDuringTests.mutant_file = mutant_file
        WORKER.save_new_experiment()

    def test_evaluate_pssm_ent_surf_mannual_pick(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        pse_path = WORKER.download_file(
            url=WORKER.test_data.EVALUATION_PSE_URL,
            md5=WORKER.test_data.EVALUATION_PSE_MD5,
        )
        WORKER.load_session_and_check(customized_session=pse_path)
        WORKER.go_to_tab(tab_name='evaluate')

        mutagenesis_dir = os.path.abspath('mutagenese')
        mutant_file = os.path.join(
            mutagenesis_dir, 'evaluate_pssm_ent_surf.mannual.mut.txt'
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_mut_table, mutant_file
        )
        set_widget_value(WORKER.plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.entropy_score_reversed,
        )
        _init = WORKER.plugin.ui.pushButton_reinitialize_mutant_choosing
        _next = WORKER.plugin.ui.pushButton_next_mutant
        _last = WORKER.plugin.ui.pushButton_previous_mutant
        _acp = WORKER.plugin.ui.pushButton_accept_this_mutant
        _rjct = WORKER.plugin.ui.pushButton_reject_this_mutant
        _bsh = WORKER.plugin.ui.pushButton_goto_best_hit_in_group

        WORKER.click(_init).click(_next, 2).click(_acp)

        WORKER.click(_next, 3).click(_acp)

        WORKER.click(_next, 2).click(_acp)

        WORKER.click(_next, 5).click(_bsh).click(_acp)

        assert (
            int(get_widget_value(WORKER.plugin.ui.lcdNumber_selected_mutant))
            == 4
        )

        WORKER.click(_next, 2)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id, focus=False)

        assert not WORKER.plugin.evaluator.mutant_tree_pssm_selected.empty
        with open(mutant_file, 'r') as mr:
            picked_mutants = mr.read().strip().split('\n')

        picked_mutants = WORKER.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            WORKER.plugin.evaluator.mutant_tree_pssm_selected.all_mutant_objects
        )
        KeyDataDuringTests.minimum_mutant_file = mutant_file
        WORKER.save_new_experiment()


class TestREvoDesignPlugin_TabCluster:
    def test_cluster(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='cluster')

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_mut_table,
            KeyDataDuringTests.mutant_file,
        )

        set_widget_value(
            WORKER.plugin.ui.spinBox_num_cluster, WORKER.test_data.cluster_num
        )
        set_widget_value(
            WORKER.plugin.ui.spinBox_num_mut_minimun,
            WORKER.test_data.cluster_min,
        )
        set_widget_value(
            WORKER.plugin.ui.spinBox_num_mut_maximum,
            WORKER.test_data.cluster_max,
        )
        set_widget_value(
            WORKER.plugin.ui.spinBox_cluster_batchsize,
            WORKER.test_data.cluster_batch,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_shuffle_clustering,
            WORKER.test_data.cluster_shuffle,
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_before_run',
        )
        WORKER.save_new_experiment()
        WORKER.click(WORKER.plugin.ui.pushButton_run_cluster)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_run',
        )

        for mut_num in range(
            WORKER.test_data.cluster_min, WORKER.test_data.cluster_max + 1
        ):
            dir = f'{WORKER.test_data.molecule}_{WORKER.test_data.chain_id}_{os.path.basename(KeyDataDuringTests.mutant_file).replace(".txt","")}_designs_{mut_num}'
            assert os.path.exists(dir)
            assert all(
                [
                    os.path.exists(os.path.join(dir, f'c.{c}.fasta'))
                    for c in range(WORKER.test_data.cluster_num)
                ]
            )
            assert os.path.exists(
                os.path.join(dir, 'cluster_centers_stochastic.fasta')
            )


class TestREvoDesignPlugin_TabVisualize:
    def test_visualize_pssm_ddg(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(WORKER.plugin.ui.comboBox_sidechain_solver, 'PIPPack')
        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver_model, 'pippack_model_1'
        )
        WORKER.go_to_tab(tab_name='visualize')

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.minimum_mutant_file,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_visualize,
            WORKER.test_data.visualize_1_pse,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_csv_2, KeyDataDuringTests.ddg_file
        )
        set_widget_value(
            WORKER.plugin.ui.comboBox_profile_type_2,
            WORKER.test_data.visualize_1_profile_type,
        )

        set_widget_value(
            WORKER.plugin.ui.checkBox_global_score_policy,
            WORKER.test_data.visualize_1_use_global_score,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.visualize_1_score_reversed,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_group_name,
            WORKER.test_data.visualize_1_design_case,
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_before_run',
        )
        WORKER.save_new_experiment()
        WORKER.click(WORKER.plugin.ui.pushButton_run_visualizing)

        WORKER.save_pymol_png(basename=WORKER.test_id)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_run',
        )

        assert os.path.exists(WORKER.test_data.visualize_1_pse)
        WORKER.check_existed_mutant_tree()

    def test_visualize_pssm_mpnn(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        WORKER.go_to_tab(tab_name='visualize')

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.minimum_mutant_file,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_visualize,
            WORKER.test_data.visualize_2_pse,
        )
        WORKER.do_typing(WORKER.plugin.ui.lineEdit_input_csv_2, '')
        set_widget_value(
            WORKER.plugin.ui.comboBox_profile_type_2,
            WORKER.test_data.visualize_2_profile_type,
        )

        set_widget_value(
            WORKER.plugin.ui.checkBox_global_score_policy,
            WORKER.test_data.visualize_2_use_global_score,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.visualize_2_score_reversed,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_group_name,
            WORKER.test_data.visualize_2_design_case,
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_before_run',
        )

        WORKER.save_new_experiment()
        WORKER.click(WORKER.plugin.ui.pushButton_run_visualizing)
        WORKER.save_pymol_png(basename=WORKER.test_id)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_after_run',
        )

        assert os.path.exists(WORKER.test_data.visualize_2_pse)
        WORKER.check_existed_mutant_tree()


class TestREvoDesignPlugin_TabConfig:
    def test_use_pippack_mpnn_design(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.load_session_and_check()
        WORKER.go_to_tab(tab_name='config')

        set_widget_value(WORKER.plugin.ui.comboBox_sidechain_solver, 'PIPPack')
        assert (
            get_widget_value(
                WORKER.plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'ensemble'
        )

        set_widget_value(
            WORKER.plugin.ui.comboBox_sidechain_solver_model,
            'pippack_model_1',
        )
        assert (
            get_widget_value(
                WORKER.plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'pippack_model_1'
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_use_PIPPack_model_1',
        )
        WORKER.save_pymol_png(basename=WORKER.test_id)

        # back to tab mutate and run mpnn redesign, saved as another file
        WORKER.go_to_tab(tab_name='mutate')

        set_widget_value(
            WORKER.plugin.ui.comboBox_profile_type,
            WORKER.test_data.mpnn_profile_type,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_input_customized_indices,
            WORKER.test_data.mpnn_surface_residues,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_output_pse_mutate,
            WORKER.test_data.pippack_pse,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_reject_substitution,
            WORKER.test_data.mpnn_reject,
        )
        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_preffer_substitution,
            WORKER.test_data.mpnn_accept,
        )

        set_widget_value(
            WORKER.plugin.ui.checkBox_reverse_mutant_effect,
            WORKER.test_data.mpnn_score_reversed,
        )

        WORKER.do_typing(
            WORKER.plugin.ui.lineEdit_design_case,
            WORKER.test_data.mpnn_design_case,
        )

        set_widget_value(
            WORKER.plugin.ui.doubleSpinBox_designer_temperature,
            WORKER.test_data.mpnn_temperature,
        )

        set_widget_value(
            WORKER.plugin.ui.spinBox_designer_batch,
            WORKER.test_data.mpnn_batch_designs,
        )
        set_widget_value(
            WORKER.plugin.ui.spinBox_designer_num_samples,
            WORKER.test_data.mpnn_num_designs,
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_deduplicate_designs,
            WORKER.test_data.mpnn_deduplicated,
        )

        if os.path.exists(WORKER.test_data.pippack_pse):
            os.remove(WORKER.test_data.pippack_pse)

        WORKER.save_new_experiment()
        WORKER.click(widget=WORKER.plugin.ui.pushButton_run_PSSM_to_pse)

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=WORKER.test_id,
        )
        WORKER.save_pymol_png(basename=WORKER.test_id)

        WORKER.check_existed_mutant_tree()


class TestREvoDesignPlugin_ActionTranslate:
    def test_chinese(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()
        WORKER.click(WORKER.plugin.ui.actionChinese)

        for tab in WORKER.tab_widget_mapping.keys():
            WORKER.go_to_tab(tab_name=tab)
            WORKER.save_screenshot(
                widget=WORKER.plugin.window,
                basename=f'{WORKER.test_id}_{tab}',
            )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}',
        )

        assert WORKER.plugin.ui.label_molecule.text() == '蛋白分子：'

        WORKER.click(WORKER.plugin.ui.actionEnglish)
        assert WORKER.plugin.ui.label_molecule.text() != '蛋白分子：'

        assert not WORKER.plugin.ui.actionFrench.isEnabled()


@pytest.mark.order(-1)
class TestREvoDesignPlugin_TabVisualize_MultiDesign:
    def test_multiple_design(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()

        if not KeyDataDuringTests.evaluate_pse_path:
            KeyDataDuringTests.evaluate_pse_path = WORKER.download_file(
                url=WORKER.test_data.EVALUATION_PSE_URL,
                md5=WORKER.test_data.EVALUATION_PSE_MD5,
            )

        WORKER.load_session_and_check(
            customized_session=KeyDataDuringTests.evaluate_pse_path
        )
        WORKER.go_to_tab(tab_name='visualize')

        set_widget_value(
            WORKER.plugin.ui.checkBox_multi_design_use_external_scorer, False
        )
        set_widget_value(
            WORKER.plugin.ui.checkBox_multi_design_color_by_scores, False
        )

        WORKER.do_typing(
            widget=WORKER.plugin.ui.lineEdit_multi_design_mutant_table,
            text=WORKER.test_data.multi_mut_txt,
            strict_mode=True,
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_{WORKER.c.i}',
        )

        md_init = WORKER.plugin.bus.button('multi_design_initialize')
        md_new = WORKER.plugin.bus.button('multi_design_start_new_design')
        md_next = WORKER.plugin.bus.button('multi_design_right')
        md_prev = WORKER.plugin.bus.button('multi_design_left')
        md_stop = WORKER.plugin.bus.button('multi_design_end_this_design')
        md_save = WORKER.plugin.bus.button(
            'multi_design_export_mutants_from_table'
        )

        WORKER.click(md_init).click(md_new)

        for i in random.sample(
            WORKER.test_data.multi_design_steps,
            3,
        ):
            j = WORKER.c.i
            WORKER.click(md_next, times=i)
            WORKER.save_pymol_png(basename=f'{WORKER.test_id}_{j}_{i}')

            WORKER.sleep(30)

        WORKER.click(md_prev, 1)

        WORKER.click(md_save)

        WORKER.sleep(30)

        assert os.path.exists(WORKER.test_data.multi_mut_txt)

    def test_multiple_design_mpnn_score(self, WORKER: TestWorker):
        WORKER.test_id = WORKER.method_name()

        if not KeyDataDuringTests.evaluate_pse_path:
            KeyDataDuringTests.evaluate_pse_path = WORKER.download_file(
                url=WORKER.test_data.EVALUATION_PSE_URL,
                md5=WORKER.test_data.EVALUATION_PSE_MD5,
            )

        WORKER.load_session_and_check(
            customized_session=KeyDataDuringTests.evaluate_pse_path
        )
        WORKER.go_to_tab(tab_name='visualize')

        WORKER.do_typing(
            widget=WORKER.plugin.ui.lineEdit_multi_design_mutant_table,
            text=WORKER.test_data.multi_mut_txt_mpnn,
            strict_mode=True,
        )

        set_widget_value(
            WORKER.plugin.ui.comboBox_profile_type_2,
            WORKER.test_data.multi_design_scorer,
        )

        WORKER.save_screenshot(
            widget=WORKER.plugin.window,
            basename=f'{WORKER.test_id}_{WORKER.c.i}',
        )

        md_init = WORKER.plugin.bus.button('multi_design_initialize')
        md_new = WORKER.plugin.bus.button('multi_design_start_new_design')
        md_next = WORKER.plugin.bus.button('multi_design_right')
        md_prev = WORKER.plugin.bus.button('multi_design_left')
        md_stop = WORKER.plugin.bus.button('multi_design_end_this_design')
        md_save = WORKER.plugin.bus.button(
            'multi_design_export_mutants_from_table'
        )

        WORKER.click(md_init).click(md_new)

        for i in random.sample(
            WORKER.test_data.multi_design_steps,
            3,
        ):
            j = WORKER.c.i
            WORKER.click(md_next, times=i)
            WORKER.save_pymol_png(basename=f'{WORKER.test_id}_{j}_{i}')

            WORKER.sleep(30)

        WORKER.click(md_save)

        WORKER.sleep(30)

        assert (
            WORKER.plugin.multi_designer.all_design_multi_design_mutant_object
        )

        assert os.path.exists(WORKER.test_data.multi_mut_txt_mpnn)


if __name__ == '__main__' or __name__ == 'pymol':
    pytest.main()
