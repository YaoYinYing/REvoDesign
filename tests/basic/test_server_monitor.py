from unittest.mock import MagicMock, create_autospec

import pytest

from REvoDesign.basic.server_monitor import (MenuActionServerMonitor,
                                             ServerProtocol)


def test_menu_action_server_monitor():
    # Create mock actions
    mock_action_on = MagicMock()
    mock_action_off = MagicMock()

    # Create a mock controller implementing ServerProtocol
    mock_controller = create_autospec(ServerProtocol, instance=True)
    mock_controller.is_running = False

    # Patch the controller to return the mock instance
    class MockController(ServerProtocol):
        def __init__(self):
            self.server_thread = None
            self.is_running = False

        def start_server(self):
            self.is_running = True

        def stop_server(self):
            self.is_running = False

        def _on_server_result(self, result):
            pass

        def _on_server_finished(self):
            pass

        def _run_server(self):
            pass

    # Create an instance of MenuActionServerMonitor
    monitor = MenuActionServerMonitor(controller=MockController, action_on=mock_action_on, action_off=mock_action_off)

    # Test initial connections
    mock_action_on.triggered.connect.assert_called_once_with(monitor.controller.start_server)
    mock_action_off.triggered.connect.assert_called_once_with(monitor.controller.stop_server)

    # Simulate triggering the actions
    monitor.controller.start_server()
    assert monitor.controller.is_running is True

    monitor.controller.stop_server()
    assert monitor.controller.is_running is False
