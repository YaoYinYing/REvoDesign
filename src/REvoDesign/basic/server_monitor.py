# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import os
import threading
import time
from abc import abstractmethod

import uvicorn

from REvoDesign.Qt import QtCore, QtGui, QtWidgets

from ..basic import SingletonAbstract

this_dir = os.path.dirname(os.path.abspath(__file__))


class ServerControlAbstract(SingletonAbstract):
    """
    A singleton class that manages the Monaco backend server lifecycle.

    Attributes:
        server_thread (threading.Thread): The thread that runs the Uvicorn server.
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
        self.server_thread: threading.Thread | None = None
        self.is_running = False
        self.server: uvicorn.Server | None = None

    @abstractmethod
    def start_server(self):
        """
        Behavior of the server start action.
        """
        if self.is_running:
            print("Server is already running.")
            return

    def stop_server(self):
        """
        Behavior of the server stop action.
        """
        if not self.is_running:
            print("Server is not running.")
            return

        print("Stopping server...")
        if self.server:
            self.server.should_exit = True
        if self.server_thread and self.server_thread.is_alive():
            # ponytail: join the plain threading.Thread (not QThread) while
            # pumping Qt events so the UI doesn't freeze. No SIP wrapper
            # lifetime issues because there is no QThread involved.
            deadline = time.monotonic() + 5
            while self.server_thread.is_alive() and time.monotonic() < deadline:
                QtWidgets.QApplication.processEvents()
                self.server_thread.join(0.05)
        self.server_thread = None
        self.server = None
        self.is_running = False

    def _run_server(self):
        """
        The function executed in the worker thread.
        """
        if self.server:
            self.server.run()


class MenuActionServerMonitor(QtCore.QObject):
    def __init__(
        self,
        controller: type[ServerControlAbstract],
        action_on: QtWidgets.QAction,
        action_off: QtWidgets.QAction,
        menu_item: QtWidgets.QMenu | None = None,
    ):
        super().__init__()  # Initialize QObject
        try:
            self.controller = controller()
        except Exception as e:
            print(f"Error initializing controller: {e}")
            action_off.setEnabled(False)
            action_on.setEnabled(False)
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
