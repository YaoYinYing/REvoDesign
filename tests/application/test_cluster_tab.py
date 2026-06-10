# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from pathlib import Path
from typing import cast

import pytest

from REvoDesign.Qt.ui_runtime_loader import load_runtime_ui
from REvoDesign.UI.types import REvoDesignUiProtocol
from REvoDesign.application.cluster_tab import ClusterTabController


class _FakeBus:
    def __init__(self, values=None):
        self.values = values or {}

    def get_value(self, key, _type=None, cfg=None, default_value=None, reject_none=False):
        del _type, cfg, reject_none
        return self.values.get(key, default_value)


@pytest.fixture
def cluster_ui(app):
    ui_path = Path(__file__).resolve().parents[2] / "src/REvoDesign/UI/REvoDesign.ui"
    window, ui_proxy = load_runtime_ui(ui_path)
    return window, cast(REvoDesignUiProtocol, ui_proxy)


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


def test_runtime_ui_exposes_representative_attributes(cluster_ui):
    window, ui = cluster_ui

    assert window.objectName() == "REvoDesignPyMOL_UI"
    assert ui.actionSource_Code.text()
    assert ui.comboBox_surface_exclusion is not None
    assert ui.tabWidget is not None
    assert ui.pushButton_run_surface_refresh is not None

    ui.retranslateUi(window)
