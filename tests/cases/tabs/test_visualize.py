# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import json as json_module
import os
from pathlib import Path

import pytest
import requests

from REvoDesign.magician.designers import ColabDesigner_MPNN
from REvoDesign.magician.designers.openkinetics import (
    CataProKcatKmScorer,
    load_chain_sequence_context,
    relabel_pdb_position_to_sequential,
)
from REvoDesign.sidechain.mutate_runner.PIPPack import PIPPack_worker
from REvoDesign.tools.customized_widgets import set_widget_value
from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id
from tests.conftest import TestWorker
from tests.data.test_data import KeyData

TESTS_DIR = Path(__file__).resolve().parents[2]
OPENKINETICS_FIXTURE_DIR = TESTS_DIR / "data" / "kinetics" / "openkinetics_1SUO"
OPENKINETICS_LIVE_MUTANT_FILE = TESTS_DIR / "data" / "mutagenese" / "evaluate_pssm_ent_surf.besthits.mut.txt"
OPENKINETICS_LIVE_PDB = TESTS_DIR / "data" / "pdb" / "1SUO.pdb"


def _real_openkinetics_api_key() -> str:
    if os.environ.get("REVODESIGN_RUN_OPENKINETICS_LIVE") != "1":
        pytest.skip("Set REVODESIGN_RUN_OPENKINETICS_LIVE=1 to submit to the live OpenKinetics API")
    key = os.environ.get("OPENKINETICS_API_KEY", "").strip()
    if not key:
        pytest.skip("Set OPENKINETICS_API_KEY env var for live OpenKinetics tests")
    return key


@pytest.mark.integration
@pytest.mark.very_slow
def test_visualize_openkinetics_catapro_live_submit():
    """Live OpenKinetics submit smoke for the Visualise-tab 1SUO mutant file."""
    wt_sequences, _, residue_numbers = load_chain_sequence_context(OPENKINETICS_LIVE_PDB, chain_id="A")
    variants = []
    for label in OPENKINETICS_LIVE_MUTANT_FILE.read_text(encoding="utf-8").splitlines():
        mutant = extract_mutants_from_mutant_id(
            relabel_pdb_position_to_sequential(label, residue_numbers, chain_id="A"),
            wt_sequences,
        )
        variants.append(
            {
                "variant_id": label,
                "mutation": label,
                "protein_sequence": mutant.mutated_sequence.get_sequence_by_chain(chain_id="A"),
            }
        )

    scorer = CataProKcatKmScorer(
        api_key=_real_openkinetics_api_key(),
        cache_enabled=False,
        timeout_seconds=60,
    )
    scorer.initialize(pdb_path=OPENKINETICS_LIVE_PDB)
    result = scorer.score_variants(
        variants,
        substrate_smiles=scorer.substrate_smiles,
        wait=False,
        use_cache=False,
    )

    assert result["status"] == "submitted"
    assert len(result["job_id"]) > 0
    assert len(variants) == len(OPENKINETICS_LIVE_MUTANT_FILE.read_text(encoding="utf-8").splitlines())


# move to fast tests
@pytest.mark.dependency(depends=["tabs_bootstrap_ui", "tabs_bootstrap_prepare"], scope="session")
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

    def test_visualize_openkinetics_catapro(
        self,
        test_worker: TestWorker,
        KeyDataDuringTests: KeyData,
        monkeypatch,
        tmp_path,
    ):
        """Visualise tab scoring via OpenKinetics CataPro with mocked HTTP."""
        test_worker.test_id = test_worker.method_name()
        monkeypatch.setenv("OPENKINETICS_API_KEY", "test-openkinetics-key")
        from REvoDesign.magician.designers.openkinetics._client import load_openkinetics_config

        openkinetics_config = load_openkinetics_config()
        monkeypatch.setattr(
            "REvoDesign.magician.designers.openkinetics._scorers.load_openkinetics_config",
            lambda: {**openkinetics_config, "cache_dir": str(tmp_path / "openkinetics-cache")},
        )

        methods_json = json_module.loads(
            (OPENKINETICS_FIXTURE_DIR / "methods_response.json").read_text(encoding="utf-8")
        )

        status_index = [0]
        submitted_data = []

        def _fake_request(self_, method, url, json=None, timeout=None, headers=None, **__):
            json_payload = json
            if "/methods/" in url:
                resp = requests.Response()
                resp.status_code = 200
                resp._content = json_module.dumps(methods_json).encode("utf-8")
                return resp
            if "/validate/" in url:
                resp = requests.Response()
                resp.status_code = 200
                resp._content = json_module.dumps({"valid": True}).encode("utf-8")
                return resp
            if "/submit/" in url:
                submitted_data[:] = list((json_payload or {}).get("data", []))
                resp = requests.Response()
                resp.status_code = 200
                resp._content = json_module.dumps({"jobId": "test-openkinetics-job"}).encode("utf-8")
                return resp
            if "/status/" in url:
                status_index[0] += 1
                resp = requests.Response()
                resp.status_code = 200
                status = "Processing" if status_index[0] == 1 else "Completed"
                resp._content = json_module.dumps({"status": status}).encode("utf-8")
                return resp
            if "/result/" in url:
                columns = ["kcat/Km (1/(s*mM))"]
                data = []
                for i, row in enumerate(submitted_data):
                    seq = row.get("Protein Sequence", "MOCK")
                    data.append(
                        {
                            "Protein Sequence": seq,
                            "variant_id": f"variant_{i}",
                            "kcat/Km (1/(s*mM))": 10.0 + i,
                        }
                    )
                resp = requests.Response()
                resp.status_code = 200
                resp._content = json_module.dumps(
                    {"jobId": "test-openkinetics-job", "columns": columns, "data": data}
                ).encode("utf-8")
                return resp
            raise AssertionError(f"Unexpected request: {method} {url}")

        test_worker.load_session_and_check(from_rcsb=True)
        monkeypatch.setattr("requests.sessions.Session.request", _fake_request)
        test_worker.go_to_tab(tab_name="config")
        set_widget_value(test_worker.plugin.ui.comboBox_sidechain_solver, "Dunbrack Rotamer Library")
        test_worker.go_to_tab(tab_name="visualize")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.minimum_mutant_file,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.test_data_repo + "/analysis/1SUO.xtal.openkinetics_catapro.pze",
        )
        set_widget_value(test_worker.plugin.ui.comboBox_profile_type_2, "OpenKinetics-CataPro-kcat/Km")
        set_widget_value(test_worker.plugin.ui.comboBox_group_name, "openkinetics_test")

        test_worker.save_screenshot(widget=test_worker.plugin.window, basename=f"{test_worker.test_id}_before_run")
        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)
        test_worker.save_pymol_png(basename=test_worker.test_id)
        test_worker.save_screenshot(widget=test_worker.plugin.window, basename=f"{test_worker.test_id}_after_run")

        pse_path = test_worker.test_data.test_data_repo + "/analysis/1SUO.xtal.openkinetics_catapro.pze"
        assert os.path.exists(pse_path)
        mt = test_worker.check_existed_mutant_tree()
        assert "openkinetics_test" in mt.all_mutant_branch_ids
        assert len(submitted_data) == 4
