# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import pytest
from PyQt5 import QtCore, QtWidgets

from REvoDesign.tools import package_manager

pytest.importorskip("PyQt5")


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    yield app


def test_execute_on_main_thread_runs_inline_on_gui_thread(qapp):
    main_thread_id = int(QtCore.QThread.currentThreadId())
    recorded_ids: list[int] = []

    def marker():
        recorded_ids.append(int(QtCore.QThread.currentThreadId()))
        return "ok"

    result = package_manager.execute_on_main_thread(marker)
    assert result == "ok"
    assert recorded_ids == [main_thread_id]


# def test_execute_on_main_thread_marshals_from_worker(qapp):
#     gui_thread_id = int(QtCore.QThread.currentThreadId())
#     gui_ids: list[int] = []
#     worker_ids: list[int] = []
#     result_holder: dict[str, str] = {}

#     def marker():
#         gui_ids.append(int(QtCore.QThread.currentThreadId()))
#         return "gui-result"

#     def worker():
#         worker_ids.append(int(QtCore.QThread.currentThreadId()))
#         result_holder["value"] = package_manager.execute_on_main_thread(marker)

#     thread = threading.Thread(target=worker, name="gui-marshaler-test")
#     thread.start()

#     start = time.time()
#     deadline = start + 5
#     while "value" not in result_holder and time.time() < deadline:
#         qapp.processEvents()
#         thread.join(timeout=0.01)
#         time.sleep(0.01)

#     thread.join(timeout=0.1)
#     assert "value" in result_holder, "Worker thread finished without producing a result"
#     assert result_holder["value"] == "gui-result"
#     assert gui_ids == [gui_thread_id]
#     assert worker_ids
#     assert worker_ids[0] != gui_thread_id


def test_notify_box_uses_executor(monkeypatch):
    called: dict[str, object] = {}

    def fake_executor(func, *args, **kwargs):
        called["func"] = func
        called["args"] = args
        called["kwargs"] = kwargs
        return "sentinel"

    monkeypatch.setattr(package_manager, "execute_on_main_thread", fake_executor)
    result = package_manager.notify_box("hello", details="detail")

    assert result == "sentinel"
    assert called["func"] is package_manager._show_notification_dialog
    assert called["args"] == ("hello", None, "detail")
