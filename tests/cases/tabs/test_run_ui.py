import os

from ...conftest import TestWorker

os.environ["PYTEST_QT_API"] = "pyqt5"


class TestREvoDesignPlugin:
    def test_plugin_gui_visibility(self, test_worker: TestWorker):
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
                basename=f"test_tab_{tab}",
            )
