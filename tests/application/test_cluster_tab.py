# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path
import importlib.util
import subprocess
import sys

import pytest

from REvoDesign.UI import Ui_REvoDesignPyMOL_UI
from REvoDesign.application.cluster_tab import ClusterTabController
from REvoDesign.Qt import QtWidgets


def _normalize_pyuic_output(text: str) -> str:
    return "\n".join(
        (
            "# Form implementation generated from reading ui file 'src/REvoDesign/UI/REvoDesign.ui'"
            if line.startswith("# Form implementation generated from reading ui file ")
            else line
        )
        for line in text.splitlines()
    )


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeBus:
    def __init__(self, values=None):
        self.values = values or {}

    def get_value(self, key, _type=None, cfg=None, default_value=None, reject_none=False):
        del _type, cfg, reject_none
        return self.values.get(key, default_value)


@pytest.fixture
def cluster_ui(app):
    window = QtWidgets.QMainWindow()
    ui = Ui_REvoDesignPyMOL_UI()
    ui.setupUi(window)
    return window, ui


def test_cluster_tab_controller_switches_pages(cluster_ui):
    _window, ui = cluster_ui
    controller = ClusterTabController(
        ui,
        _FakeBus({"ui.cluster.method.use": "EvoCluster"}),
    )

    controller.install()
    assert ui.stackedWidget_cluster_method_settings.currentWidget() is ui.page_cluster_evo

    ui.comboBox_cluster_method.setCurrentText("KMeansCluster")
    assert ui.stackedWidget_cluster_method_settings.currentWidget() is ui.page_cluster_kmeans

    ui.comboBox_cluster_method.setCurrentText("LegacyCluster")
    assert ui.stackedWidget_cluster_method_settings.currentWidget() is ui.page_cluster_legacy
    assert "deprecated" in ui.comboBox_cluster_method.toolTip().lower()


def test_cluster_tab_controller_disables_rosetta_override_until_scoring_enabled(cluster_ui):
    _window, ui = cluster_ui
    ui.checkBox_cluster_mutate_and_relax.setChecked(False)
    ui.checkBox_cluster_rosetta_override_representatives.setChecked(True)

    controller = ClusterTabController(ui, _FakeBus())
    controller.install()

    assert ui.checkBox_cluster_rosetta_override_representatives.isEnabled() is False
    assert ui.checkBox_cluster_rosetta_override_representatives.isChecked() is False

    ui.checkBox_cluster_mutate_and_relax.setChecked(True)
    assert ui.checkBox_cluster_rosetta_override_representatives.isEnabled() is True


def test_ui_regeneration_matches_committed_output(tmp_path):
    ui_path = Path(__file__).resolve().parents[2] / "src/REvoDesign/UI/REvoDesign.ui"
    generated_path = tmp_path / "Ui_REvoDesign.py"
    committed_path = Path(__file__).resolve().parents[2] / "src/REvoDesign/UI/Ui_REvoDesign.py"
    compiler = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/compile_qt_ui.py",
        "compile_qt_ui",
    )

    subprocess.run(
        [*compiler.select_pyuic_command(), str(ui_path), "-o", str(generated_path)],
        check=True,
    )
    rewritten = compiler.rewrite_generated_qt_source(generated_path.read_text(encoding="utf-8"))
    assert _normalize_pyuic_output(rewritten) == _normalize_pyuic_output(committed_path.read_text(encoding="utf-8"))
