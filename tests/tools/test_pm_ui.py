# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


from unittest.mock import patch

import pytest

from REvoDesign.Qt.qt_wrapper import QtCore
from REvoDesign.tools.package_manager import CheckableListView, LiveProcessResult
from tests.conftest import PmTestWorker


def test_pm_dialog_visualize(pm_test_worker: PmTestWorker):
    assert pm_test_worker.plugin.dialog is not None
    assert pm_test_worker.plugin.dialog.isVisible()


def test_pm_dialog_refresh_extras_table_empty(pm_test_worker: PmTestWorker):
    with (
        patch("REvoDesign.tools.package_manager.fetch_gist_json", side_effect=lambda url: {}) as patched_fetch,
        patch(
            "REvoDesign.tools.package_manager.notify_box", side_effect=lambda *args, **kargs: None
        ) as mock_notify_box,
    ):
        pm_test_worker.click(pm_test_worker.plugin.installer_ui.pushButton_refresh_extras)
        assert isinstance(pm_test_worker.plugin.extra_checkbox, CheckableListView)
        assert len(pm_test_worker.plugin.extra_checkbox.items.entities) == 1
        patched_fetch.assert_called_once()

@pytest.mark.parametrize(
    "size_change, preset, triger",
    [
        [
            "increase",
            None,
            "radioButton_extra_customized",
        ],
        [
            "decrease",
            "radioButton_extra_customized",
            "radioButton_extra_none",
        ],
        [
            "decrease",
            "radioButton_extra_customized",
            "radioButton_extra_everything",
        ],
        [
            "increase",
            "radioButton_extra_everything",
            "radioButton_extra_customized",
        ],
    ],
)
def test_pm_dialog_extras_panel_expand_collapse(size_change, preset, triger, pm_test_worker: PmTestWorker):

    with patch.object(pm_test_worker.plugin, "resize_extra_widget") as patched_resize:
        if preset:
            pm_test_worker.click(getattr(pm_test_worker.plugin.dialog, preset))
            # assert patched_resize.assert_called_once()
        pm_test_worker.save_screenshot(pm_test_worker.plugin.dialog, f"{pm_test_worker.method_name}-p.{preset}")

        dialog = pm_test_worker.plugin.dialog
        pm_test_worker.sleep(300)
        before_size = dialog.size()
        pm_test_worker.click(getattr(pm_test_worker.plugin.dialog, triger))
        pm_test_worker.save_screenshot(
            pm_test_worker.plugin.dialog, f"{pm_test_worker.method_name}-p.{preset}-t.{triger}"
        )

        def wait_for_width_change(start_width: int, direction: int, min_delta: int = 20):

            def _changed():
                delta = dialog.size().width() - start_width
                return delta * direction >= min_delta

            pm_test_worker.qtbot.waitUntil(_changed, timeout=2000)
            return dialog.size().width()

        direction_map = {"increase": 1, "decrease": -1}
        expected_direction = direction_map.get(size_change, 0)

        if expected_direction:
            final_width = wait_for_width_change(before_size.width(), expected_direction)
            assert (final_width - before_size.width()) * expected_direction >= 20
        else:
            pm_test_worker.sleep(200)
            assert abs(dialog.size().width() - before_size.width()) < 5


def test_pm_dialog_select_extras(pm_test_worker: PmTestWorker):
    pm_test_worker.click(pm_test_worker.plugin.dialog.radioButton_extra_customized)
    pm_test_worker.save_screenshot(pm_test_worker.plugin.dialog, f"{pm_test_worker.method_name}-before")
    assert not pm_test_worker.plugin.extra_checkbox.checked_items

    for row in range(pm_test_worker.plugin.extra_checkbox.model.rowCount()):
        item = pm_test_worker.plugin.extra_checkbox.model.item(row)
        if item.isCheckable():
            item.setCheckState(QtCore.Qt.Checked)
            break
    pm_test_worker.save_screenshot(pm_test_worker.plugin.dialog, f"{pm_test_worker.method_name}-after")
    assert len(pm_test_worker.plugin.extra_checkbox.checked_items) == 1

    # buggy patch but correct assertion
    with (
        patch(
            "REvoDesign.tools.package_manager.notify_box", side_effect=lambda *args, **kargs: None
        ) as mock_notify_box,
        patch(
            "REvoDesign.tools.package_manager.run_command",
            side_effect=lambda cmd, verbose, env: LiveProcessResult(
                args=cmd, returncode=0, stdout="Mocked stdout", stderr="Mocked stderr"
            ),
        ) as mock_run_command,
        patch.object(pm_test_worker.plugin.pip_installer, "install") as mock_pip_install,
    ):
        pm_test_worker.click(pm_test_worker.plugin.dialog.radioButton_from_local_clone)
        pm_test_worker.click(pm_test_worker.plugin.dialog.pushButton_install)

        mock_pip_install.assert_called_once()
        # mock_run_command.assert_called_once()


def test_pm_dialog_menu_pop(pm_test_worker: PmTestWorker):
    pm_test_worker.save_screenshot(pm_test_worker.plugin.menu, f"{pm_test_worker.method_name}-before")

    with patch.object(pm_test_worker.plugin, "show_menu") as mock_show_menu:

        pm_test_worker.click(pm_test_worker.plugin.dialog.label_header)
        pm_test_worker.rclick(pm_test_worker.plugin.dialog.label_header)

        pm_test_worker.save_screenshot(pm_test_worker.plugin.menu, f"{pm_test_worker.method_name}-after")
        # mock_show_menu.assert_called_once()
