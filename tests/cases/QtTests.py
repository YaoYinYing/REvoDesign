import glob
import os
import random
from unittest.mock import patch

import pytest
from pymol import cmd

import REvoDesign
import REvoDesign.bootstrap.set_config
import REvoDesign.tools
from REvoDesign.tools.customized_widgets import (get_widget_value,
                                                 set_widget_value)

from ..data.test_data import KeyDataDuringTests

os.environ['PYTEST_QT_API'] = 'pyqt5'


class TestREvoDesignPlugin:
    def test_plugin_gui_visibility(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        # Check if the main window of the plugin is visible
        assert test_worker.plugin.window.isVisible()
        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        for tab in test_worker.tab_widget_mapping.keys():
            test_worker.go_to_tab(tab_name=tab)
            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f'test_tab_{tab}',
            )


class TestREvoDesignPlugin_TabPrepare:
    def test_load_molecule(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check(from_rcsb=True)
        test_worker.go_to_tab(tab_name='prepare')

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)
        test_worker.save_new_experiment()

    def test_pocket(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check(from_rcsb=True)
        test_worker.go_to_tab(tab_name='prepare')

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

        pocket_file_dir = os.path.abspath('./pockets/')
        assert os.path.exists(test_worker.test_data.pocket_pse)
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

        with open(pocket_file_design_shell) as ds_fr:
            design_shell_residue_ids = ds_fr.read().strip()
            assert design_shell_residue_ids

        test_worker.save_pymol_png(basename=test_worker.test_id, spells='orient hetatm')
        test_worker.save_new_experiment()

    def test_surface(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='prepare')

        test_worker.click(widget=test_worker.plugin.ui.pushButton_run_surface_refresh)

        hetatm_residues = [
            sel
            for sel in cmd.get_names(type='selections')
            if 'pkt_hetatm_' in sel
        ][0]
        assert hetatm_residues

        KeyDataDuringTests.hetatm_pocket_sele = hetatm_residues

        test_worker.do_typing(
            test_worker.plugin.ui.comboBox_surface_exclusion, hetatm_residues
        )

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

        surface_dir = os.path.abspath('./surface_residue_records/')
        assert os.path.exists(test_worker.test_data.surface_pse)
        assert os.path.exists(surface_dir)
        surface_files = glob.glob(
            os.path.join(
                surface_dir,
                f'{test_worker.test_data.molecule}_residues_cutoff_{test_worker.test_data.suface_probe:.1f}.txt',
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

        with open(surface_file_design_shell) as ss_fr:
            surface_residue_ids = ss_fr.read().strip()
            assert surface_residue_ids

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id, spells='center')
        test_worker.save_new_experiment()


class TestREvoDesignPlugin_TabMutate:
    def test_pssm_ent_surf(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='mutate')

        expected_downloaded_file = test_worker.download_file(
            url=test_worker.test_data.PSSM_GREMLIN_DATA_URL,
            md5=test_worker.test_data.PSSM_GREMLIN_DATA_MD5,
        )

        dist_dir, expanded_files = test_worker.expand_zip(
            compressed_file=expected_downloaded_file
        )

        assert expanded_files
        pssm_file = os.path.join(
            dist_dir,
            'pssm_msa',
            f'{test_worker.test_data.molecule}_{test_worker.test_data.chain_id}_ascii_mtx_file',
        )
        assert os.path.exists(pssm_file)

        KeyDataDuringTests.pssm_file = pssm_file

        test_worker.do_typing(test_worker.plugin.ui.lineEdit_input_csv, pssm_file)
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
        test_worker.click(widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.check_existed_mutant_tree()

    def test_mpnn_surf(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )

        test_worker.go_to_tab(tab_name='mutate')

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
        test_worker.click(widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.check_existed_mutant_tree()

    def test_ddg_surf_non_biolib_calling(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        test_worker.go_to_tab(tab_name='mutate')

        local_ddg_file = test_worker.download_file(
            url=test_worker.test_data.PYTHIA_DDG_CSV_URL,
            md5=test_worker.test_data.PYTHIA_DDG_CSV_MD5,
        )

        KeyDataDuringTests.ddg_file = local_ddg_file

        test_worker.do_typing(
            test_worker.plugin.ui.comboBox_profile_type,
            test_worker.test_data.ddg_profile_type_local,
        )
        test_worker.do_typing(test_worker.plugin.ui.lineEdit_input_csv, local_ddg_file)

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
            '',
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

        test_worker.click(widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.check_existed_mutant_tree()

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

    def test_pssm_pocket_design_dunbrack(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        test_worker.go_to_tab(tab_name='mutate')

        expected_downloaded_file = test_worker.download_file(
            url=test_worker.test_data.PSSM_GREMLIN_DATA_URL,
            md5=test_worker.test_data.PSSM_GREMLIN_DATA_MD5,
        )

        dist_dir, expanded_files = test_worker.expand_zip(
            compressed_file=expected_downloaded_file
        )

        assert expanded_files
        pssm_file = os.path.join(
            dist_dir,
            'pssm_msa',
            f'{test_worker.test_data.molecule}_{test_worker.test_data.chain_id}_ascii_mtx_file',
        )
        assert os.path.exists(pssm_file)

        KeyDataDuringTests.pssm_file = pssm_file

        test_worker.do_typing(test_worker.plugin.ui.lineEdit_input_csv, pssm_file)
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
        test_worker.click(widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse)
        test_worker.check_existed_mutant_tree()

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)


@pytest.mark.order(-1)
class TestREvoDesignPlugin_TabInteract:
    def test_gremlin_homomer_all2all(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check(
            from_rcsb=True,
            pdb_code=test_worker.test_data.gremlin_homomer_molecule,
            spell=test_worker.test_data.gremlin_homomer_postfetch_spell,
        )
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )

        test_worker.go_to_tab(tab_name='interact')

        # buttons
        _next = test_worker.plugin.ui.pushButton_next
        _prev = test_worker.plugin.ui.pushButton_previous

        _accp = test_worker.plugin.ui.pushButton_interact_accept
        test_worker.plugin.ui.pushButton_interact_reject

        zipped = test_worker.download_file(
            url=test_worker.test_data.gremlin_homomer_profile_url,
            md5=test_worker.test_data.gremlin_homomer_profile_md5,
        )

        dist_dir, extracted_files = test_worker.expand_zip(compressed_file=zipped)

        gremlin_pkl_fp = os.path.join(
            dist_dir,
            'gremlin_res',
            f'{test_worker.test_data.gremlin_homomer_molecule}_{test_worker.test_data.gremlin_homomer_chain}.i90c75_aln.GREMLIN.mrf.pkl',
        )

        set_widget_value(
            test_worker.plugin.ui.lineEdit_input_gremlin_mtx, gremlin_pkl_fp
        )

        KeyDataDuringTests.gremlin_pkl_fp_homomer = gremlin_pkl_fp

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

        mutfile = os.path.join('mutagenese', 'gremlin_homomer_a2a.mut.txt')

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_before_init',
        )

        test_worker.click(test_worker.plugin.ui.pushButton_reinitialize_interact)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_init',
        )
        test_worker.save_new_experiment()

        test_worker.click(test_worker.plugin.ui.pushButton_run_interact_scan)

        test_worker.sleep(300)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_scan',
        )

        test_worker.save_pymol_png(
            basename=f'{test_worker.test_id}_interact_pairs', focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith('cep')]
        for sel in ce_links:
            cmd.disable(sel)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_pair_0',
        )

        a2a_dir = test_worker.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith('Top.') and f.endswith('.csv')
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
                test_worker.click(_next if operation > 0 else _prev, abs(operation))
                test_worker.save_screenshot(
                    widget=test_worker.plugin.window,
                    basename=f'{test_worker.test_id}_pair_{operation}',
                )
                cmd.orient(test_worker.test_data.gremlin_homomer_molecule)
                test_worker.save_pymol_png(
                    basename=f'{test_worker.test_id}_interact_pair_{i}_{operation}',
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            test_worker.click(
                test_worker.plugin.bus.w2c.get_button_from_id(
                    f'{row}_vs_{col}', prefix='matrixButton'
                )
            )
            test_worker.sleep(200)

            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}',
            )

            test_worker.save_pymol_png(
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}', focus=False
            )
            test_worker.check_existed_mutant_tree()

            cmd.orient(
                test_worker.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            test_worker.save_pymol_png(
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}_orient',
                focus=False,
            )
            test_worker.click(_accp)

        assert os.path.exists(mutfile)

        del test_worker.plugin.gremlin_worker.gremlin_tool
        del test_worker.plugin.gremlin_worker.coevolved_pairs
        del test_worker.plugin.gremlin_worker

    def test_gremlin_homomer_one2all(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check(
            from_rcsb=True,
            pdb_code=test_worker.test_data.gremlin_homomer_molecule,
            spell=test_worker.test_data.gremlin_homomer_postfetch_spell,
        )
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )

        test_worker.go_to_tab(tab_name='interact')

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

        mutfile = os.path.join('mutagenese', 'gremlin_homomer_o2a.mut.txt')

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_before_init',
        )

        test_worker.click(test_worker.plugin.ui.pushButton_reinitialize_interact)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_init',
        )
        test_worker.save_new_experiment()

        cmd.select('sele', test_worker.test_data.gremlin_homomer_o2a_sele)
        cmd.enable('sele')

        test_worker.click(test_worker.plugin.ui.pushButton_run_interact_scan)

        test_worker.sleep(200)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_scan',
        )

        test_worker.save_pymol_png(
            basename=f'{test_worker.test_id}_interact_pairs', focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith('cep')]
        for sel in ce_links:
            cmd.disable(sel)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_pair_0',
        )

        a2a_dir = test_worker.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith('Top.') and f.endswith('.csv')
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
                test_worker.click(_next if operation > 0 else _prev, abs(operation))
                test_worker.save_screenshot(
                    widget=test_worker.plugin.window,
                    basename=f'{test_worker.test_id}_pair_{operation}',
                )
                cmd.orient(test_worker.test_data.gremlin_homomer_molecule)
                test_worker.save_pymol_png(
                    basename=f'{test_worker.test_id}_interact_pair_{i}_{operation}',
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            test_worker.click(
                test_worker.plugin.bus.w2c.get_button_from_id(
                    f'{row}_vs_{col}', prefix='matrixButton'
                )
            )
            test_worker.sleep(200)

            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}',
            )

            test_worker.save_pymol_png(
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}', focus=False
            )
            test_worker.check_existed_mutant_tree()

            cmd.orient(
                test_worker.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            test_worker.save_pymol_png(
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}_orient',
                focus=False,
            )
            test_worker.click(_accp)

        assert os.path.exists(mutfile)

        del test_worker.plugin.gremlin_worker.gremlin_tool
        del test_worker.plugin.gremlin_worker.coevolved_pairs
        del test_worker.plugin.gremlin_worker

    def test_gremlin_all2all(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        test_worker.go_to_tab(tab_name='interact')

        # buttons
        _next = test_worker.plugin.ui.pushButton_next
        _prev = test_worker.plugin.ui.pushButton_previous

        _accp = test_worker.plugin.ui.pushButton_interact_accept
        test_worker.plugin.ui.pushButton_interact_reject

        gremlin_pkl_fp = os.path.join(
            test_worker.EXPANDED_DIR,
            f'{test_worker.test_data.molecule}_{test_worker.test_data.chain_id}_PSSM_GREMLIN_results',
            'gremlin_res',
            f'{test_worker.test_data.molecule}_{test_worker.test_data.chain_id}.i90c75_aln.GREMLIN.mrf.pkl',
        )

        set_widget_value(
            test_worker.plugin.ui.lineEdit_input_gremlin_mtx, gremlin_pkl_fp
        )
        KeyDataDuringTests.gremlin_pkl_fp = gremlin_pkl_fp
        set_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN,
            test_worker.test_data.gremlin_topN,
        )

        mutfile = os.path.join('mutagenese', 'gremlin_a2a.mut.txt')

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_before_init',
        )

        test_worker.click(test_worker.plugin.ui.pushButton_reinitialize_interact)

        # assert os.path.exists(test_worker.test_data.visualize_2_pse)

        # test_worker.wait_for_file(file=f'{test_worker.test_data.molecule}_GREMLIN_mtx_zscore.png', interval=100,timeout=10)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_init',
        )
        test_worker.save_new_experiment()

        test_worker.click(test_worker.plugin.ui.pushButton_run_interact_scan)

        test_worker.sleep(200)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_scan',
        )

        test_worker.save_pymol_png(
            basename=f'{test_worker.test_id}_interact_pairs', focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith('cep')]
        for sel in ce_links:
            cmd.disable(sel)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_pair_0',
        )

        a2a_dir = test_worker.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(a2a_dir)
        csv_files = [
            f
            for f in os.listdir(a2a_dir)
            if f.startswith('Top.') and f.endswith('.csv')
        ]
        assert len(csv_files) == get_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN
        )

        for operation in test_worker.test_data.gremlin_monomer_clicks_a2a:
            i = test_worker.c.i
            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                test_worker.click(_next if operation > 0 else _prev, abs(operation))
                test_worker.save_screenshot(
                    widget=test_worker.plugin.window,
                    basename=f'{test_worker.test_id}_pair_{i}_{operation}',
                )
                cmd.orient(test_worker.test_data.molecule)
                test_worker.save_pymol_png(
                    basename=f'{test_worker.test_id}_interact_pair_{i}_{operation}',
                    focus=False,
                )

                continue

            assert len(operation) == 2
            row, col = operation

            test_worker.click(
                test_worker.plugin.bus.w2c.get_button_from_id(
                    f'{row}_vs_{col}', prefix='matrixButton'
                )
            )
            test_worker.sleep(200)

            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}',
            )

            test_worker.save_pymol_png(
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}', focus=False
            )
            test_worker.check_existed_mutant_tree()

            cmd.orient(
                test_worker.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            test_worker.save_pymol_png(
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}_orient',
                focus=False,
            )
            test_worker.click(_accp)

        assert os.path.exists(mutfile)

        del test_worker.plugin.gremlin_worker.gremlin_tool
        del test_worker.plugin.gremlin_worker.coevolved_pairs
        del test_worker.plugin.gremlin_worker

    def test_gremlin_one2all_mpnn_score(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        test_worker.go_to_tab(tab_name='interact')

        sele_resi = 295
        cmd.select(
            'sele',
            f'{test_worker.test_data.molecule} and c. {test_worker.test_data.chain_id} and i. {sele_resi} and n. CA',
        )
        cmd.enable('sele')

        gremlin_pkl_fp = os.path.join(
            test_worker.EXPANDED_DIR,
            f'{test_worker.test_data.molecule}_{test_worker.test_data.chain_id}_PSSM_GREMLIN_results',
            'gremlin_res',
            f'{test_worker.test_data.molecule}_{test_worker.test_data.chain_id}.i90c75_aln.GREMLIN.mrf.pkl',
        )

        # buttons
        _next = test_worker.plugin.ui.pushButton_next
        _prev = test_worker.plugin.ui.pushButton_previous

        _accp = test_worker.plugin.ui.pushButton_interact_accept
        test_worker.plugin.ui.pushButton_interact_reject

        set_widget_value(
            test_worker.plugin.ui.lineEdit_input_gremlin_mtx,
            gremlin_pkl_fp,
        )

        set_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN,
            test_worker.test_data.gremlin_topN,
        )

        mutfile = os.path.join('mutagenese', 'gremlin_o2a.mut.txt')

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mutant_table, mutfile
        )

        set_widget_value(
            test_worker.plugin.ui.comboBox_external_scorer, 'ProteinMPNN'
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_before_init',
        )

        test_worker.click(test_worker.plugin.ui.pushButton_reinitialize_interact)

        # assert os.path.exists(test_worker.test_data.visualize_2_pse)

        # test_worker.wait_for_file(file=f'{test_worker.test_data.molecule}_GREMLIN_mtx_zscore.png', interval=100,timeout=20)

        test_worker.save_new_experiment()
        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_init',
        )

        test_worker.click(test_worker.plugin.ui.pushButton_run_interact_scan)

        test_worker.sleep(200)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_scan',
        )

        test_worker.save_pymol_png(
            basename=f'{test_worker.test_id}_interact_pairs', focus=False
        )

        ce_links = [sel for sel in cmd.get_names() if sel.startswith('cep')]
        for sel in ce_links:
            cmd.disable(sel)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_pair_0',
        )

        o2a_dir = test_worker.plugin.gremlin_worker.gremlin_workpath

        assert os.path.exists(o2a_dir)
        csv_files = [
            f
            for f in os.listdir(o2a_dir)
            if f.startswith('Top.') and f.endswith('.csv')
        ]
        assert len(csv_files) == get_widget_value(
            test_worker.plugin.ui.spinBox_gremlin_topN
        )

        for operation in test_worker.test_data.gremlin_monomer_clicks_o2a:
            i = test_worker.c.i
            if not isinstance(operation, (int, tuple)):
                continue

            if isinstance(operation, int):
                test_worker.click(_next if operation > 0 else _prev, abs(operation))
                test_worker.save_screenshot(
                    widget=test_worker.plugin.window,
                    basename=f'{test_worker.test_id}_pair_{i}_{operation}',
                )
                cmd.orient(test_worker.test_data.molecule)
                test_worker.save_pymol_png(
                    basename=f'{test_worker.test_id}_interact_pair_{i}_{operation}',
                    focus=False,
                )
                continue

            assert len(operation) == 2
            row, col = operation

            i = test_worker.c.i
            test_worker.click(
                test_worker.plugin.bus.w2c.get_button_from_id(
                    f'{row}_vs_{col}', prefix='matrixButton'
                )
            )
            test_worker.sleep(200)

            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}',
            )

            test_worker.save_pymol_png(
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}', focus=False
            )
            test_worker.check_existed_mutant_tree()

            cmd.orient(
                test_worker.mutant_tree.all_mutant_objects[0].short_mutant_id
            )

            test_worker.save_pymol_png(
                basename=f'{test_worker.test_id}_{i}_pick_{row}_{col}_orient',
                focus=False,
            )
            test_worker.click(_accp)

        cmd.orient(test_worker.test_data.molecule)

        assert os.path.exists(mutfile)

        del test_worker.plugin.gremlin_worker.gremlin_tool
        del test_worker.plugin.gremlin_worker.coevolved_pairs
        del test_worker.plugin.gremlin_worker


class TestREvoDesignPlugin_TabEvaluate:
    def test_evaluate_pssm_ent_surf_best_hits(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        pse_path = test_worker.download_file(
            url=test_worker.test_data.EVALUATION_PSE_URL,
            md5=test_worker.test_data.EVALUATION_PSE_MD5,
        )
        test_worker.load_session_and_check(customized_session=pse_path)
        test_worker.go_to_tab(tab_name='evaluate')

        KeyDataDuringTests.evaluate_pse_path = pse_path

        mutagenesis_dir = os.path.abspath('mutagenese')
        mutant_file = os.path.join(
            mutagenesis_dir, 'evaluate_pssm_ent_surf.besthits.mut.txt'
        )

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_mut_table, mutant_file
        )
        set_widget_value(test_worker.plugin.ui.checkBox_show_wt, True)

        set_widget_value(
            test_worker.plugin.ui.checkBox_reverse_mutant_effect,
            test_worker.test_data.entropy_score_reversed,
        )

        test_worker.click(
            widget=test_worker.plugin.ui.pushButton_reinitialize_mutant_choosing
        )
        test_worker.click(widget=test_worker.plugin.ui.pushButton_choose_lucky_mutant)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id, focus=False)

        assert not test_worker.plugin.evaluator.mutant_tree_pssm_selected.empty
        with open(mutant_file) as mr:
            picked_mutants = mr.read().strip().split('\n')

        picked_mutants = test_worker.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            test_worker.plugin.evaluator.mutant_tree_pssm_selected.all_mutant_objects
        )
        KeyDataDuringTests.mutant_file = mutant_file
        test_worker.save_new_experiment()

    def test_evaluate_pssm_ent_surf_mannual_pick(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        pse_path = test_worker.download_file(
            url=test_worker.test_data.EVALUATION_PSE_URL,
            md5=test_worker.test_data.EVALUATION_PSE_MD5,
        )
        test_worker.load_session_and_check(customized_session=pse_path)
        test_worker.go_to_tab(tab_name='evaluate')

        mutagenesis_dir = os.path.abspath('mutagenese')
        mutant_file = os.path.join(
            mutagenesis_dir, 'evaluate_pssm_ent_surf.mannual.mut.txt'
        )

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
            int(get_widget_value(test_worker.plugin.ui.lcdNumber_selected_mutant))
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
            picked_mutants = mr.read().strip().split('\n')

        picked_mutants = test_worker.non_emtpy_list(picked_mutants)

        assert picked_mutants
        assert len(picked_mutants) == len(
            test_worker.plugin.evaluator.mutant_tree_pssm_selected.all_mutant_objects
        )
        KeyDataDuringTests.minimum_mutant_file = mutant_file
        test_worker.save_new_experiment()


class TestREvoDesignPlugin_TabCluster:
    def test_cluster(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='cluster')

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table,
            KeyDataDuringTests.mutant_file,
        )

        set_widget_value(
            test_worker.plugin.ui.spinBox_num_cluster, test_worker.test_data.cluster_num
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
            basename=f'{test_worker.test_id}_before_run',
        )
        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_cluster)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_run',
        )

        for mut_num in range(
            test_worker.test_data.cluster_min, test_worker.test_data.cluster_max + 1
        ):
            dir = f'{test_worker.test_data.molecule}_{test_worker.test_data.chain_id}_{os.path.basename(KeyDataDuringTests.mutant_file).replace(".txt","")}_designs_{mut_num}'
            assert os.path.exists(dir)
            assert all(
                [
                    os.path.exists(os.path.join(dir, f'c.{c}.fasta'))
                    for c in range(test_worker.test_data.cluster_num)
                ]
            )
            assert os.path.exists(
                os.path.join(dir, 'cluster_centers_stochastic.fasta')
            )


class TestREvoDesignPlugin_TabVisualize:
    def test_visualize_pssm_ddg(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(test_worker.plugin.ui.comboBox_sidechain_solver, 'PIPPack')
        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver_model, 'pippack_model_1'
        )
        test_worker.go_to_tab(tab_name='visualize')

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.minimum_mutant_file,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.visualize_1_pse,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_csv_2, KeyDataDuringTests.ddg_file
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
            test_worker.plugin.ui.lineEdit_group_name,
            test_worker.test_data.visualize_1_design_case,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_before_run',
        )
        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)

        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_run',
        )

        assert os.path.exists(test_worker.test_data.visualize_1_pse)
        test_worker.check_existed_mutant_tree()

    def test_visualize_pssm_mpnn(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver,
            'Dunbrack Rotamer Library',
        )
        test_worker.go_to_tab(tab_name='visualize')

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.minimum_mutant_file,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.visualize_2_pse,
        )
        test_worker.do_typing(test_worker.plugin.ui.lineEdit_input_csv_2, '')
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
            test_worker.plugin.ui.lineEdit_group_name,
            test_worker.test_data.visualize_2_design_case,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_before_run',
        )

        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_after_run',
        )

        assert os.path.exists(test_worker.test_data.visualize_2_pse)
        test_worker.check_existed_mutant_tree()


class TestREvoDesignPlugin_TabConfig:
    def test_use_pippack_mpnn_design(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        set_widget_value(test_worker.plugin.ui.comboBox_sidechain_solver, 'PIPPack')
        assert (
            get_widget_value(
                test_worker.plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'ensemble'
        )

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver_model,
            'pippack_model_1',
        )
        assert (
            get_widget_value(
                test_worker.plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'pippack_model_1'
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_use_PIPPack_model_1',
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)

        # back to tab mutate and run mpnn redesign, saved as another file
        test_worker.go_to_tab(tab_name='mutate')

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
        test_worker.click(widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse)

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=test_worker.test_id,
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.check_existed_mutant_tree()

    @patch('REvoDesign.bootstrap.set_config.WITH_DEPENDENCIES.PIPPACK', False)
    def test_sidechain_solver_fallback_mpnn(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name='config')

        assert (
            REvoDesign.bootstrap.set_config.WITH_DEPENDENCIES.PIPPACK
        )

        set_widget_value(test_worker.plugin.ui.comboBox_sidechain_solver, 'PIPPack')
        assert (
            get_widget_value(
                test_worker.plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'ensemble'
        )

        set_widget_value(
            test_worker.plugin.ui.comboBox_sidechain_solver_model,
            'pippack_model_1',
        )
        assert (
            get_widget_value(
                test_worker.plugin.ui.comboBox_sidechain_solver_model,
            )
            == 'pippack_model_1'
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_use_PIPPack_model_1',
        )
        test_worker.save_pymol_png(basename=test_worker.test_id)

        # back to tab mutate and run mpnn redesign, saved as another file
        test_worker.go_to_tab(tab_name='mutate')

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
            test_worker.test_data.sidechain_solver_fallback_pse,
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

        if os.path.exists(test_worker.test_data.sidechain_solver_fallback_pse):
            os.remove(test_worker.test_data.sidechain_solver_fallback_pse)

        test_worker.save_new_experiment()
        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_setup',
        )
        test_worker.click(widget=test_worker.plugin.ui.pushButton_run_PSSM_to_pse)

        test_worker.go_to_tab(tab_name='config')
        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_fallbacked',
        )

        assert (
            get_widget_value(
                test_worker.plugin.ui.comboBox_sidechain_solver,
            )
            == 'Dunbrack Rotamer Library'
        )

        test_worker.save_pymol_png(basename=test_worker.test_id)

        test_worker.check_existed_mutant_tree()


class TestREvoDesignPlugin_ActionTranslate:
    def test_chinese(self, test_worker):
        test_worker.test_id = test_worker.method_name()
        test_worker.click(test_worker.plugin.ui.actionChinese)

        for tab in test_worker.tab_widget_mapping.keys():
            test_worker.go_to_tab(tab_name=tab)
            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f'{test_worker.test_id}_{tab}',
            )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}',
        )

        assert test_worker.plugin.ui.label_molecule.text() == '蛋白分子：'

        test_worker.click(test_worker.plugin.ui.actionEnglish)
        assert test_worker.plugin.ui.label_molecule.text() != '蛋白分子：'

        assert not test_worker.plugin.ui.actionFrench.isEnabled()


@pytest.mark.order(-2)
class TestREvoDesignPlugin_TabVisualize_MultiDesign:
    def test_multiple_design(self, test_worker):
        test_worker.test_id = test_worker.method_name()

        if not KeyDataDuringTests.evaluate_pse_path:
            KeyDataDuringTests.evaluate_pse_path = test_worker.download_file(
                url=test_worker.test_data.EVALUATION_PSE_URL,
                md5=test_worker.test_data.EVALUATION_PSE_MD5,
            )

        test_worker.load_session_and_check(
            customized_session=KeyDataDuringTests.evaluate_pse_path
        )
        test_worker.go_to_tab(tab_name='visualize')

        set_widget_value(
            test_worker.plugin.ui.checkBox_multi_design_use_external_scorer, False
        )
        set_widget_value(
            test_worker.plugin.ui.checkBox_multi_design_color_by_scores, False
        )

        test_worker.do_typing(
            widget=test_worker.plugin.ui.lineEdit_multi_design_mutant_table,
            text=test_worker.test_data.multi_mut_txt,
            strict_mode=True,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_{test_worker.c.i}',
        )

        md_init = test_worker.plugin.bus.button('multi_design_initialize')
        md_new = test_worker.plugin.bus.button('multi_design_start_new_design')
        md_next = test_worker.plugin.bus.button('multi_design_right')
        md_prev = test_worker.plugin.bus.button('multi_design_left')
        test_worker.plugin.bus.button('multi_design_end_this_design')
        md_save = test_worker.plugin.bus.button(
            'multi_design_export_mutants_from_table'
        )

        test_worker.click(md_init).click(md_new)

        for i in random.sample(
            test_worker.test_data.multi_design_steps,
            3,
        ):
            j = test_worker.c.i
            test_worker.click(md_next, times=i)
            test_worker.save_pymol_png(basename=f'{test_worker.test_id}_{j}_{i}')

            test_worker.sleep(30)

        test_worker.click(md_prev, 1)

        test_worker.click(md_save)

        test_worker.sleep(30)

        assert os.path.exists(test_worker.test_data.multi_mut_txt)

    def test_multiple_design_mpnn_score(self, test_worker):
        test_worker.test_id = test_worker.method_name()

        if not KeyDataDuringTests.evaluate_pse_path:
            KeyDataDuringTests.evaluate_pse_path = test_worker.download_file(
                url=test_worker.test_data.EVALUATION_PSE_URL,
                md5=test_worker.test_data.EVALUATION_PSE_MD5,
            )

        test_worker.load_session_and_check(
            customized_session=KeyDataDuringTests.evaluate_pse_path
        )
        test_worker.go_to_tab(tab_name='visualize')

        test_worker.do_typing(
            widget=test_worker.plugin.ui.lineEdit_multi_design_mutant_table,
            text=test_worker.test_data.multi_mut_txt_mpnn,
            strict_mode=True,
        )

        set_widget_value(
            test_worker.plugin.ui.comboBox_profile_type_2,
            test_worker.test_data.multi_design_scorer,
        )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f'{test_worker.test_id}_{test_worker.c.i}',
        )

        md_init = test_worker.plugin.bus.button('multi_design_initialize')
        md_new = test_worker.plugin.bus.button('multi_design_start_new_design')
        md_next = test_worker.plugin.bus.button('multi_design_right')
        test_worker.plugin.bus.button('multi_design_left')
        test_worker.plugin.bus.button('multi_design_end_this_design')
        md_save = test_worker.plugin.bus.button(
            'multi_design_export_mutants_from_table'
        )

        test_worker.click(md_init).click(md_new)

        for i in random.sample(
            test_worker.test_data.multi_design_steps,
            3,
        ):
            j = test_worker.c.i
            test_worker.click(md_next, times=i)
            test_worker.save_pymol_png(basename=f'{test_worker.test_id}_{j}_{i}')

            test_worker.sleep(30)

        test_worker.click(md_save)

        test_worker.sleep(30)

        assert (
            test_worker.plugin.multi_designer.all_design_multi_design_mutant_object
        )

        assert os.path.exists(test_worker.test_data.multi_mut_txt_mpnn)


def main(args=None):
    pytest.main(args=args)


if __name__ == '__main__' or __name__ == 'pymol':
    print(f'Parent: {__name__}')
    main(args=None)
