import os
from abc import abstractmethod
from typing import Optional, Type

import uvicorn

from REvoDesign.Qt import QtCore, QtGui, QtWidgets
from REvoDesign.tools.package_manager import WorkerThread

from ..basic import SingletonAbstract

this_dir = os.path.dirname(os.path.abspath(__file__))





class ServerControlAbstract(SingletonAbstract):
    """
    A singleton class that manages the Monaco backend server lifecycle.

    Attributes:
        server_thread (WorkerThread): The worker thread that runs the Uvicorn server.
        is_running (bool): Indicates whether the server is running.
        server (Uvicorn Server): The Uvicorn server instance.

    Usage:
        Register the server control actions in the application's menu actions:

        ```python
        MenuActionServerMonitor(ServerControl, ui.actionStartEditor, ui.actionStopEditor)
        ```

        The ServerMonitor will automatically start and stop the server when the actions are triggered.
    """

    def singleton_init(self):
        self.server_thread: WorkerThread = None  # type: ignore # WorkerThread instance
        self.is_running = False
        self.server: uvicorn.Server = None  # type: ignore # Uvicorn Server instance

    @abstractmethod
    def start_server(self):
        '''
        Behavior of the server start action.
        '''
        if self.is_running:
            print("Server is already running.")
            return

    def stop_server(self):
        '''
        Behavior of the server stop action.
        '''
        if not self.is_running:
            print("Server is not running.")
            return

        print("Stopping server...")
        if self.server:
            self.server.should_exit = True
        if self.server_thread:
            self.server_thread.interrupt()
        self.is_running = False

    def _run_server(self):
        """
        The function executed in the worker thread.
        """
        if self.server:
            self.server.run()

    def _on_server_result(self, result):
        """
        Handle results from the WorkerThread.
        """
        print(f"Server result: {result}")

    def _on_server_finished(self):
        """
        Handle the completion of the WorkerThread.
        """
        self.is_running = False
        print("Server thread finished.")


class MenuActionServerMonitor(QtCore.QObject):
    def __init__(
        self,
        controller: Type[ServerControlAbstract],
        action_on: QtWidgets.QAction,
        action_off: QtWidgets.QAction,
        menu_item: Optional[QtWidgets.QMenu] = None,
    ):
        super().__init__()  # Initialize QObject
        try:
            self.controller = controller()
        except Exception as e:
            print(f"Error initializing controller: {e}")
            self.controller = None
            if self.menu_item is not None:
                self.menu_item.setEnabled(False)
            self.action_off.setEnabled(False)
            self.action_on.setEnabled(False)
            return
        self.action_on = action_on
        self.action_off = action_off
        self.menu_item = menu_item

        # Set initial LED status
        if self.menu_item is not None:
            self.menu_item.setIcon(QtGui.QIcon(os.path.join(this_dir, "../meta/icons/leds/blue.png")))

        # Connect actions to controller methods
        self.action_on.triggered.connect(self._start_server)
        self.action_off.triggered.connect(self._stop_server)

    def _start_server(self):
        self.controller.start_server()
        self._update_led_status()

    def _stop_server(self):
        self.controller.stop_server()
        self._update_led_status()

    def _update_led_status(self):
        """
        Update the LED status based on self.controller.is_running.
        """
        if self.menu_item is not None:
            if self.controller.is_running:
                return self.menu_item.setIcon(QtGui.QIcon(os.path.join(this_dir, "../meta/icons/leds/green.png")))
            return self.menu_item.setIcon(QtGui.QIcon(os.path.join(this_dir, "../meta/icons/leds/red.png")))
