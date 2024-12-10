
import threading

from pymol.Qt import QtCore,QtWidgets  # type: ignore
from typing import Optional, Protocol, Type

class ServerProtocol(Protocol):
    server_thread: Optional[threading.Thread]
    is_running: bool

    def start_server(self) -> None:
        ...
    def stop_server(self) -> None:
        ...
    def _on_server_result(self, result) -> None:
        ...
    def _on_server_finished(self)-> None:
        ...
    def _run_server(self) -> None:
        ...


class MenuActionServerMonitor(QtCore.QObject): # type: ignore
    def __init__(self, controller: Type[ServerProtocol], action_on, action_off):
        super().__init__()  # Initialize QObject
        self.controller = controller()
        self.action_on = action_on
        self.action_off = action_off

        # Connect actions to controller methods
        self.action_on.triggered.connect(self.controller.start_server)
        self.action_off.triggered.connect(self.controller.stop_server)


