# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import os

import pytest

from tests.conftest import TestWorker

os.environ["PYTEST_QT_API"] = "pyqt5"


@pytest.mark.dependency(depends=["tabs_bootstrap_ui", "tabs_bootstrap_prepare"])
class TestREvoDesignPlugin_ActionTranslate:
    def test_chinese(self, test_worker: TestWorker):
        test_worker.test_id = test_worker.method_name()
        test_worker.click(test_worker.plugin.ui.actionChinese)

        for tab in test_worker.tab_widget_mapping.keys():
            test_worker.go_to_tab(tab_name=tab)
            test_worker.save_screenshot(
                widget=test_worker.plugin.window,
                basename=f"{test_worker.test_id}_{tab}",
            )

        test_worker.save_screenshot(
            widget=test_worker.plugin.window,
            basename=f"{test_worker.test_id}",
        )

        assert test_worker.plugin.ui.label_molecule.text() == "蛋白分子："

        test_worker.click(test_worker.plugin.ui.actionEnglish)
        assert test_worker.plugin.ui.label_molecule.text() != "蛋白分子："

        assert not test_worker.plugin.ui.actionFrench.isEnabled()
