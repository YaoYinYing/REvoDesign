# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


from unittest.mock import MagicMock

import pytest

from REvoDesign.basic.server_monitor import MenuActionServerMonitor, ServerControlAbstract
from REvoDesign.Qt import QtCore, QtWidgets

# -----------------------------------------------------------------------------
# 1. Mock / Derived Test Class
# -----------------------------------------------------------------------------


class MockServerControl(ServerControlAbstract):
    """
    Concrete test class that implements start_server. We mock out the actual
    uvicorn server calls for unit testing, only toggling `is_running`.
    """

    def start_server(self):
        super().start_server()  # Will print "Server is already running." if is_running is True
        if not self.is_running and not (self.server_thread and self.server_thread.is_alive()):
            print("Starting server... (Mock)")
            self.is_running = True
            self.server_thread = MagicMock()
            self.server_thread.is_alive.return_value = False
            self.server = MagicMock()
        else:
            print("Server is already running. (Mock)")


@pytest.fixture(autouse=True)
def reset_mock_server_control():
    """Keep singleton state from leaking between server-monitor tests."""
    MockServerControl.reset_instance()
    yield
    MockServerControl.reset_instance()


# -----------------------------------------------------------------------------
# 2. PyTest Fixtures for Qt
# -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    """
    A fixture that ensures there's a QApplication instance running
    for the duration of the tests in this module.
    """
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])
    yield app
    # Teardown (not usually required for a shared QApplication, but good practice)
    app.quit()


# -----------------------------------------------------------------------------
# 3. Basic Tests for the ServerControlAbstract Implementation
# -----------------------------------------------------------------------------


def test_server_control_start_stop():
    """
    Test the basic start/stop logic of MockServerControl (derived from ServerControlAbstract).
    """
    control = MockServerControl()

    # Initially should not be running
    assert not control.is_running

    # Start server
    control.start_server()
    assert control.is_running

    # Attempt to start server again (should show 'Server is already running.' message)
    control.start_server()
    assert control.is_running

    # Stop server
    control.stop_server()
    assert not control.is_running

    # Attempt to stop server again (should show 'Server is not running.' message)
    control.stop_server()
    assert not control.is_running


def test_stop_request_marks_timed_out_server_not_running(monkeypatch):
    """A slow shutdown must not leave the public running state enabled."""
    control = MockServerControl()
    control.start_server()
    control.server_thread.is_alive.return_value = True
    monkeypatch.setattr(
        "REvoDesign.basic.server_monitor.time.monotonic",
        MagicMock(side_effect=[0, 6]),
    )

    control.stop_server()

    assert not control.is_running
    assert control.server_thread is not None
    assert control.server is not None


# -----------------------------------------------------------------------------
# 4. Tests for MenuActionServerMonitor
# -----------------------------------------------------------------------------


def test_menu_action_server_monitor(qapp):
    """
    Test that triggering the on/off actions calls MockServerControl
    methods and updates icon states.
    """

    # Create QActions that simulate start/stop menu items
    action_start = QtWidgets.QAction()
    action_stop = QtWidgets.QAction()
    menu_item = QtWidgets.QMenu()
    menu_monitor = MenuActionServerMonitor(MockServerControl, action_start, action_stop, menu_item)

    assert menu_item is not None

    # Initially, is_running should be False
    assert not menu_monitor.controller.is_running
    # The initial icon is set to 'blue.png' in the snippet
    # We'll just verify the icon's filename matches the path segment
    assert not menu_item.icon().isNull()

    # Trigger the start action
    action_start.trigger()
    assert menu_monitor.controller.is_running

    # Trigger the stop action
    action_stop.trigger()
    assert not menu_monitor.controller.is_running
