# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import json
import os
from pathlib import Path

import pytest
import requests

from REvoDesign.magician.designers import ColabDesigner_MPNN
from REvoDesign.sidechain.mutate_runner.PIPPack import PIPPack_worker
from REvoDesign.tools.customized_widgets import set_widget_value
from tests.conftest import TestWorker
from tests.data.test_data import KeyData


def _openkinetics_api_key_available() -> bool:
    """Check whether an OpenKinetics API key is available via YAML config or env var."""
    try:
        from REvoDesign.magician.designers.openkinetics import resolve_api_key

        resolve_api_key()
        return True
    except Exception:
        return False


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

    def test_visualize_openkinetics_catapro(self, test_worker: TestWorker, KeyDataDuringTests: KeyData, monkeypatch):
        """Visualise tab scoring via OpenKinetics CataPro with mocked HTTP."""
        test_worker.test_id = test_worker.method_name()

        # -- build a fake HTTP layer that returns plausible OpenKinetics payloads --
        fixture_dir = Path(__file__).resolve().parents[3] / "data" / "kinetics" / "openkinetics_1SUO"
        methods_json = json.loads((fixture_dir / "methods_response.json").read_text(encoding="utf-8"))

        _status_index = [0]  # mutable counter for sequential status responses

        def _fake_request(self_, method, url, json=None, timeout=None, headers=None, **__):
            if "/methods/" in url:
                resp = requests.Response()
                resp.status_code = 200
                resp._content = json.dumps(methods_json).encode("utf-8")
                return resp
            if "/validate/" in url:
                resp = requests.Response()
                resp.status_code = 200
                resp._content = json.dumps({"valid": True}).encode("utf-8")
                return resp
            if "/submit/" in url:
                resp = requests.Response()
                resp.status_code = 200
                resp._content = json.dumps({"jobId": "test-openkinetics-job"}).encode("utf-8")
                return resp
            if "/status/" in url:
                _status_index[0] += 1
                resp = requests.Response()
                resp.status_code = 200
                # first poll returns Processing, second returns Completed
                status = "Processing" if _status_index[0] == 1 else "Completed"
                resp._content = json.dumps({"status": status}).encode("utf-8")
                return resp
            if "/result/" in url:
                # Build a result payload that echoes back whatever was submitted.
                submitted = json or {}
                submitted_data = submitted.get("data", [{"Protein Sequence": "MOCK"}])
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
                resp._content = json.dumps({"jobId": "test-openkinetics-job", "columns": columns, "data": data}).encode(
                    "utf-8"
                )
                return resp
            raise AssertionError(f"Unexpected request: {method} {url}")

        monkeypatch.setattr("requests.sessions.Session.request", _fake_request)

        # -- ensure the OpenKinetics scorer has a substrate SMILES available --
        from REvoDesign.magician.designers.openkinetics._scorers import OpenKineticsScorerAbstract

        _orig_init = OpenKineticsScorerAbstract.__init__

        def _patched_init(self_, *args, **kw):
            _orig_init(self_, *args, **kw)
            if not self_.substrate_smiles:
                self_.substrate_smiles = "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21"

        monkeypatch.setattr(OpenKineticsScorerAbstract, "__init__", _patched_init)

        # -- drive the GUI --
        test_worker.load_session_and_check()
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
        set_widget_value(test_worker.plugin.ui.comboBox_external_scorer, "OpenKinetics-CataPro-kcat/Km")
        set_widget_value(test_worker.plugin.ui.comboBox_group_name, "openkinetics_test")

        test_worker.save_screenshot(widget=test_worker.plugin.window, basename=f"{test_worker.test_id}_before_run")
        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)
        test_worker.save_pymol_png(basename=test_worker.test_id)
        test_worker.save_screenshot(widget=test_worker.plugin.window, basename=f"{test_worker.test_id}_after_run")

        pse_path = test_worker.test_data.test_data_repo + "/analysis/1SUO.xtal.openkinetics_catapro.pze"
        assert os.path.exists(pse_path)
        mt = test_worker.check_existed_mutant_tree()
        assert (
            test_worker.test_data.test_data_repo + "/analysis/1SUO.xtal.openkinetics_catapro"
            in mt.all_mutant_branch_ids
        )

    @pytest.mark.skipif(
        os.environ.get("GITHUB_ACTIONS") == "true",
        reason="Live API test skipped under GHA CI — requires a real OpenKinetics API key",
    )
    @pytest.mark.skipif(
        not _openkinetics_api_key_available(),
        reason="OpenKinetics API key not found in YAML config or OPENKINETICS_API_KEY env var",
    )
    def test_visualize_openkinetics_catapro_live(
        self, test_worker: TestWorker, KeyDataDuringTests: KeyData, monkeypatch
    ):
        """Visualise tab scoring via the real OpenKinetics API (local only)."""
        test_worker.test_id = test_worker.method_name()

        # Inject the API key into ConfigBus if only available via env var.
        import os as _os

        if _os.environ.get("OPENKINETICS_API_KEY") and not test_worker.plugin.bus.get_value(
            "scorers.openkinetics.api_key", str, default_value=None
        ):
            test_worker.plugin.bus.set_value("scorers.openkinetics.api_key", _os.environ["OPENKINETICS_API_KEY"])

        # Inject substrate SMILES since the GUI flow doesn't pass it yet.
        from REvoDesign.magician.designers.openkinetics._scorers import OpenKineticsScorerAbstract

        _orig_init = OpenKineticsScorerAbstract.__init__

        def _patched_init(self_, *args, **kw):
            _orig_init(self_, *args, **kw)
            if not self_.substrate_smiles:
                self_.substrate_smiles = "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21"

        monkeypatch.setattr(OpenKineticsScorerAbstract, "__init__", _patched_init)

        test_worker.load_session_and_check()
        test_worker.go_to_tab(tab_name="config")
        set_widget_value(test_worker.plugin.ui.comboBox_sidechain_solver, "Dunbrack Rotamer Library")
        test_worker.go_to_tab(tab_name="visualize")

        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_input_mut_table_csv,
            KeyDataDuringTests.minimum_mutant_file,
        )
        test_worker.do_typing(
            test_worker.plugin.ui.lineEdit_output_pse_visualize,
            test_worker.test_data.test_data_repo + "/analysis/1SUO.xtal.openkinetics_catapro_live.pze",
        )
        set_widget_value(test_worker.plugin.ui.comboBox_external_scorer, "OpenKinetics-CataPro-kcat/Km")
        set_widget_value(test_worker.plugin.ui.comboBox_group_name, "openkinetics_live")

        test_worker.save_new_experiment()
        test_worker.click(test_worker.plugin.ui.pushButton_run_visualizing)

        pse_path = test_worker.test_data.test_data_repo + "/analysis/1SUO.xtal.openkinetics_catapro_live.pze"
        assert os.path.exists(pse_path)
        mt = test_worker.check_existed_mutant_tree()
        assert len(mt.all_mutant_branch_ids) >= 1
