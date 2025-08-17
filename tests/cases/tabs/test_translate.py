import os

from tests.conftest import TestWorker

os.environ["PYTEST_QT_API"] = "pyqt5"


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
