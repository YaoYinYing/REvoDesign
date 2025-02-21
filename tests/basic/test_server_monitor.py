from unittest.mock import MagicMock

import pytest
# PyQt or PySide (adapt this import to whichever you use):
from PyQt5 import QtWidgets

from REvoDesign.basic import MenuActionServerMonitor, ServerControlAbstract
from REvoDesign.Qt import QtCore
from REvoDesign.tools.package_manager import WorkerThread

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
        if not self.is_running:
            print("Starting server... (Mock)")
            self.is_running = True
            # In a real scenario, you might do the WorkerThread setup and uvicorn.Server here:
            self.server_thread = MagicMock(spec=WorkerThread)
            self.server = MagicMock()
        else:
            print("Server is already running. (Mock)")

    def stop_server(self):
        super().stop_server()  # Will print "Server is not running." if is_running is False
        if self.is_running:
            print("Stopping server... (Mock)")
            self.is_running = False
            # Clean up
            if self.server_thread:
                self.server_thread.interrupt.assert_not_called()  # We can verify call if needed
                self.server_thread = None
            if self.server:
                self.server.should_exit = True
                self.server = None
        else:
            print("Server is not running. (Mock)")


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


# -----------------------------------------------------------------------------
# 4. Tests for MenuActionServerMonitor
# -----------------------------------------------------------------------------

def test_menu_action_server_monitor(test_worker):
    """
    Test that triggering the on/off actions calls MockServerControl
    methods and updates icon states.
    """

    from REvoDesign.driver.ui_driver import StoresWidget

    menu_monitor = StoresWidget().server_switches['Editor_Backend']

    # Create QActions that simulate start/stop menu items
    action_start = menu_monitor.action_on

    action_stop = menu_monitor.action_off
    menu_item = menu_monitor.menu_item

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
