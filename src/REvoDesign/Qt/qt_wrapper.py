# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Qt compatibility layer used by REvoDesign runtime modules."""

from __future__ import annotations

import importlib
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt5 import QtCore as _QtCore
    from PyQt5 import QtGui as _QtGui
    from PyQt5 import QtNetwork as _QtNetwork
    from PyQt5 import QtSvg as _QtSvg
    from PyQt5 import QtWebSockets as _QtWebSockets
    from PyQt5 import QtWidgets as _QtWidgets
else:
    from pymol import Qt as _pymol_qt

    _QtCore = _pymol_qt.QtCore
    _QtGui = _pymol_qt.QtGui
    _QtWidgets = _pymol_qt.QtWidgets


QtCore = _QtCore
QtGui = _QtGui
QtWidgets = _QtWidgets


def _detect_qt_backend() -> str:
    if TYPE_CHECKING:
        return "PyQt5"
    return getattr(_pymol_qt, "PYQT_NAME", "pymol.Qt")


def _detect_qt_major(qt_backend: str) -> int:
    match = re.search(r"(\d+)$", qt_backend)
    return int(match.group(1)) if match else 0


QT_BACKEND = _detect_qt_backend()
QT_MAJOR = _detect_qt_major(QT_BACKEND)
QtSource = QT_BACKEND


def _import_optional_qt_module(module_name: str):
    if TYPE_CHECKING:
        return None

    module = getattr(_pymol_qt, module_name, None)
    if module is not None:
        return module

    if not QT_BACKEND.startswith(("PyQt", "PySide")):
        return None

    try:
        return importlib.import_module(f"{QT_BACKEND}.{module_name}")
    except ImportError:
        return None


QtNetwork = _import_optional_qt_module("QtNetwork")
QtWebSockets = _import_optional_qt_module("QtWebSockets")
QtSvg = _import_optional_qt_module("QtSvg")


def has_qt_module(module_name: str) -> bool:
    """Return True when the named Qt module is available from the active backend."""

    return globals().get(module_name) is not None


def qexec(obj: Any, *args: Any, **kwargs: Any) -> Any:
    """Execute a Qt dialog or menu through the Qt5/Qt6 compatible method name."""

    exec_method = getattr(obj, "exec", None)
    if callable(exec_method):
        return exec_method(*args, **kwargs)
    return obj.exec_(*args, **kwargs)


def _qt_enum(owner: Any, enum_name: str, member_name: str) -> Any:
    """Resolve a scoped Qt6 enum member or its flat Qt5 fallback."""

    if owner is None:
        return None

    scoped_enum = getattr(owner, enum_name, None)
    if scoped_enum is not None and hasattr(scoped_enum, member_name):
        return getattr(scoped_enum, member_name)
    return getattr(owner, member_name)


class _QtCompatNamespace:
    """Namespace of compatibility constants shared by runtime modules."""

    def __init__(self, qt_core, qt_widgets, qt_network=None, qt_websockets=None):
        self.Information = _qt_enum(qt_widgets.QMessageBox, "Icon", "Information")
        self.Warning = _qt_enum(qt_widgets.QMessageBox, "Icon", "Warning")
        self.Critical = _qt_enum(qt_widgets.QMessageBox, "Icon", "Critical")
        self.Question = _qt_enum(qt_widgets.QMessageBox, "Icon", "Question")

        self.Ok = _qt_enum(qt_widgets.QMessageBox, "StandardButton", "Ok")
        self.Yes = _qt_enum(qt_widgets.QMessageBox, "StandardButton", "Yes")
        self.No = _qt_enum(qt_widgets.QMessageBox, "StandardButton", "No")

        self.Accepted = _qt_enum(qt_widgets.QDialog, "DialogCode", "Accepted")
        self.Rejected = _qt_enum(qt_widgets.QDialog, "DialogCode", "Rejected")

        self.Checked = _qt_enum(qt_core.Qt, "CheckState", "Checked")
        self.Unchecked = _qt_enum(qt_core.Qt, "CheckState", "Unchecked")
        self.CheckStateRole = _qt_enum(qt_core.Qt, "ItemDataRole", "CheckStateRole")
        self.RichText = _qt_enum(qt_core.Qt, "TextFormat", "RichText")
        self.CustomContextMenu = _qt_enum(qt_core.Qt, "ContextMenuPolicy", "CustomContextMenu")
        self.ItemIsUserCheckable = _qt_enum(qt_core.Qt, "ItemFlag", "ItemIsUserCheckable")
        self.ItemIsEnabled = _qt_enum(qt_core.Qt, "ItemFlag", "ItemIsEnabled")

        self.AlignLeft = _qt_enum(qt_core.Qt, "AlignmentFlag", "AlignLeft")
        self.AlignRight = _qt_enum(qt_core.Qt, "AlignmentFlag", "AlignRight")
        self.AlignTop = _qt_enum(qt_core.Qt, "AlignmentFlag", "AlignTop")
        self.AlignCenter = _qt_enum(qt_core.Qt, "AlignmentFlag", "AlignCenter")
        self.AlignHCenter = _qt_enum(qt_core.Qt, "AlignmentFlag", "AlignHCenter")
        self.AlignVCenter = _qt_enum(qt_core.Qt, "AlignmentFlag", "AlignVCenter")
        self.AlignLeading = _qt_enum(qt_core.Qt, "AlignmentFlag", "AlignLeading")
        self.AlignTrailing = _qt_enum(qt_core.Qt, "AlignmentFlag", "AlignTrailing")
        self.Horizontal = _qt_enum(qt_core.Qt, "Orientation", "Horizontal")
        self.ImhDigitsOnly = _qt_enum(qt_core.Qt, "InputMethodHint", "ImhDigitsOnly")

        self.AnyAddress = _qt_enum(qt_network.QHostAddress, "SpecialAddress", "Any") if qt_network else None
        self.LocalHost = _qt_enum(qt_network.QHostAddress, "SpecialAddress", "LocalHost") if qt_network else None
        self.ConnectedState = (
            _qt_enum(qt_network.QAbstractSocket, "SocketState", "ConnectedState") if qt_network else None
        )
        self.NonSecureMode = (
            _qt_enum(qt_websockets.QWebSocketServer, "SslMode", "NonSecureMode") if qt_websockets else None
        )

    @staticmethod
    def exec(obj: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a Qt object through the compatibility wrapper."""

        return qexec(obj, *args, **kwargs)


QtCompat = _QtCompatNamespace(QtCore, QtWidgets, QtNetwork, QtWebSockets)

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtNetwork",
    "QtWebSockets",
    "QtSvg",
    "QT_BACKEND",
    "QT_MAJOR",
    "QtCompat",
    "QtSource",
    "has_qt_module",
    "qexec",
]
