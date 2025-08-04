from unittest.mock import patch

import pytest

from REvoDesign.Qt.qt_wrapper import QtCore
from REvoDesign.tools.package_manager import (CheckableListView,
                                              LiveProcessResult)

from ..conftest import PmTestWorker, pm_test_worker


def test_pm_dialog_visualize(pm_plugin):
    assert pm_plugin.dialog is not None
    assert pm_plugin.dialog.isVisible()


def test_pm_dialog_refresh_extras_table_empty(pm_plugin, pm_test_worker: PmTestWorker):
    with patch('REvoDesign.tools.package_manager.fetch_gist_json', side_effect=lambda url: {}) as patched_fetch, patch('REvoDesign.tools.package_manager.notify_box', side_effect=lambda *args, **kargs: None) as mock_notify_box:
        pm_test_worker.click(pm_plugin.installer_ui.pushButton_refresh_extras)
        assert isinstance(pm_plugin.extra_checkbox, CheckableListView)
        assert len(pm_plugin.extra_checkbox.items.entities) == 1


@pytest.mark.parametrize("size_before, size_after, preset, triger", [
    [
        (490, 547), (652, 534), None, 'radioButton_extra_customized',
    ],
    [
        (652, 534), (490, 534), 'radioButton_extra_customized', 'radioButton_extra_none',
    ],
    [
        (652, 534), (490, 534), 'radioButton_extra_customized', 'radioButton_extra_everything',
    ],
    [
        (490, 534), (652, 534), 'radioButton_extra_everything', 'radioButton_extra_customized',
    ]
])
def test_pm_dialog_extras_panel_expand_collapse(
        size_before,
        size_after,
        preset,
        triger,
        pm_plugin,
        pm_test_worker: PmTestWorker):

    with patch.object(pm_plugin, 'resize_extra_widget') as patched_resize:
        if preset:
            pm_test_worker.click(getattr(pm_plugin.dialog, preset))
            # assert patched_resize.assert_called_once()
        pm_test_worker.save_screenshot(pm_plugin.dialog, f'{pm_test_worker.method_name}-p.{preset}')
        assert pm_plugin.dialog.size() == QtCore.QSize(*size_before)
        pm_test_worker.click(getattr(pm_plugin.dialog, triger))
        pm_test_worker.save_screenshot(pm_plugin.dialog, f'{pm_test_worker.method_name}-p.{preset}-t.{triger}')

        assert pm_plugin.dialog.size() == QtCore.QSize(*size_after)


def test_pm_dialog_select_extras(pm_plugin, pm_test_worker: PmTestWorker):
    pm_test_worker.click(pm_plugin.dialog.radioButton_extra_customized)
    pm_test_worker.save_screenshot(pm_plugin.dialog, f'{pm_test_worker.method_name}-before')
    assert not pm_plugin.extra_checkbox.checked_items

    for row in range(pm_plugin.extra_checkbox.model.rowCount()):
        item = pm_plugin.extra_checkbox.model.item(row)
        if item.isCheckable():
            item.setCheckState(QtCore.Qt.Checked)
            break
    pm_test_worker.save_screenshot(pm_plugin.dialog, f'{pm_test_worker.method_name}-after')
    assert len(pm_plugin.extra_checkbox.checked_items) == 1

    with patch('REvoDesign.tools.package_manager.notify_box', side_effect=lambda *args, **kargs: None) as mock_notify_box, \
        patch('REvoDesign.tools.package_manager.run_command', side_effect=lambda cmd, verbose, env: LiveProcessResult(args=cmd, returncode=0, stdout='Mocked stdout', stderr='Mocked stderr')) as mock_run_command, \
            patch.object(pm_plugin.pip_installer, 'install') as mock_pip_install:
        pm_test_worker.click(pm_plugin.dialog.radioButton_from_local_clone)
        pm_test_worker.click(pm_plugin.dialog.pushButton_install)
        # assert mock_pip_install.assert_called()
        # assert mock_run_command.assert_called()
