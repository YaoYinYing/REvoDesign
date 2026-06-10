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
    """Execute a Qt object on both Qt5 and Qt6 bindings."""

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
    return getattr(owner, member_name, None)


def _alias_attr(target: Any, old_name: str, source: Any, enum_name: str, member_name: str) -> None:
    """Install a Qt5-style alias when a Qt6 scoped enum is available."""

    if target is None or source is None or hasattr(target, old_name):
        return
    enum_obj = getattr(source, enum_name, None)
    if enum_obj is None or not hasattr(enum_obj, member_name):
        return
    setattr(target, old_name, getattr(enum_obj, member_name))


def _alias_many(target: Any, source: Any, enum_name: str, members: tuple[str, ...]) -> None:
    for member_name in members:
        _alias_attr(target, member_name, source, enum_name, member_name)


def _install_qtcore_aliases() -> None:
    qt_namespace = getattr(QtCore, "Qt", None)
    if qt_namespace is None:
        return

    _alias_attr(qt_namespace, "WA_DeleteOnClose", qt_namespace, "WidgetAttribute", "WA_DeleteOnClose")
    _alias_attr(qt_namespace, "WA_ShowWithoutActivating", qt_namespace, "WidgetAttribute", "WA_ShowWithoutActivating")
    _alias_attr(qt_namespace, "CustomContextMenu", qt_namespace, "ContextMenuPolicy", "CustomContextMenu")
    _alias_attr(qt_namespace, "RichText", qt_namespace, "TextFormat", "RichText")
    _alias_attr(qt_namespace, "PlainText", qt_namespace, "TextFormat", "PlainText")
    _alias_many(qt_namespace, qt_namespace, "CheckState", ("Checked", "Unchecked", "PartiallyChecked"))
    _alias_many(qt_namespace, qt_namespace, "Orientation", ("Horizontal", "Vertical"))
    _alias_many(qt_namespace, qt_namespace, "ScrollBarPolicy", ("ScrollBarAsNeeded", "ScrollBarAlwaysOff", "ScrollBarAlwaysOn"))
    _alias_many(qt_namespace, qt_namespace, "GlobalColor", ("yellow", "blue", "red", "green", "black", "white"))
    _alias_many(qt_namespace, qt_namespace, "FocusPolicy", ("NoFocus",))
    _alias_many(qt_namespace, qt_namespace, "CursorShape", ("PointingHandCursor",))
    _alias_many(
        qt_namespace,
        qt_namespace,
        "WindowType",
        ("Tool", "FramelessWindowHint", "WindowStaysOnTopHint", "WindowDoesNotAcceptFocus"),
    )
    _alias_many(
        qt_namespace,
        qt_namespace,
        "AlignmentFlag",
        (
            "AlignLeft",
            "AlignRight",
            "AlignHCenter",
            "AlignJustify",
            "AlignTop",
            "AlignBottom",
            "AlignVCenter",
            "AlignCenter",
            "AlignLeading",
            "AlignTrailing",
        ),
    )
    _alias_many(qt_namespace, qt_namespace, "MouseButton", ("LeftButton", "RightButton", "MiddleButton"))
    _alias_many(
        qt_namespace,
        qt_namespace,
        "KeyboardModifier",
        ("NoModifier", "ControlModifier", "ShiftModifier", "AltModifier", "MetaModifier"),
    )
    _alias_many(QtCore.QEasingCurve, QtCore.QEasingCurve, "Type", ("Linear", "InQuad", "OutQuad", "InOutQuad"))


def _install_qtwidgets_aliases() -> None:
    _alias_many(QtWidgets.QTabWidget, QtWidgets.QTabWidget, "TabShape", ("Rounded", "Triangular"))
    _alias_many(QtWidgets.QTabWidget, QtWidgets.QTabWidget, "TabPosition", ("North", "South", "West", "East"))
    _alias_many(
        QtWidgets.QFrame,
        QtWidgets.QFrame,
        "Shape",
        ("NoFrame", "Box", "Panel", "StyledPanel", "HLine", "VLine", "WinPanel"),
    )
    _alias_many(QtWidgets.QFrame, QtWidgets.QFrame, "Shadow", ("Plain", "Raised", "Sunken"))
    _alias_many(
        QtWidgets.QSizePolicy,
        QtWidgets.QSizePolicy,
        "Policy",
        ("Fixed", "Minimum", "Maximum", "Preferred", "Expanding", "MinimumExpanding", "Ignored"),
    )
    _alias_many(
        QtWidgets.QAbstractItemView,
        QtWidgets.QAbstractItemView,
        "EditTrigger",
        (
            "NoEditTriggers",
            "CurrentChanged",
            "DoubleClicked",
            "SelectedClicked",
            "EditKeyPressed",
            "AnyKeyPressed",
            "AllEditTriggers",
        ),
    )
    _alias_many(
        QtWidgets.QAbstractItemView,
        QtWidgets.QAbstractItemView,
        "SelectionBehavior",
        ("SelectItems", "SelectRows", "SelectColumns"),
    )
    _alias_many(
        QtWidgets.QAbstractItemView,
        QtWidgets.QAbstractItemView,
        "SelectionMode",
        ("SingleSelection", "MultiSelection", "ExtendedSelection", "ContiguousSelection", "NoSelection"),
    )
    _alias_many(
        QtWidgets.QAbstractItemView,
        QtWidgets.QAbstractItemView,
        "ScrollMode",
        ("ScrollPerItem", "ScrollPerPixel"),
    )
    _alias_many(QtWidgets.QMainWindow, QtWidgets.QMainWindow, "DockOption", ("AnimatedDocks", "AllowTabbedDocks"))
    _alias_many(QtWidgets.QFormLayout, QtWidgets.QFormLayout, "ItemRole", ("LabelRole", "FieldRole"))
    _alias_many(QtWidgets.QLayout, QtWidgets.QLayout, "SizeConstraint", ("SetNoConstraint",))
    _alias_many(QtWidgets.QHeaderView, QtWidgets.QHeaderView, "ResizeMode", ("Interactive", "Stretch", "Fixed", "ResizeToContents"))
    _alias_many(QtWidgets.QAbstractSpinBox, QtWidgets.QAbstractSpinBox, "ButtonSymbols", ("UpDownArrows", "PlusMinus", "NoButtons"))
    _alias_many(QtWidgets.QLCDNumber, QtWidgets.QLCDNumber, "SegmentStyle", ("Flat", "Outline", "Filled"))
    _alias_many(
        QtWidgets.QComboBox,
        QtWidgets.QComboBox,
        "InsertPolicy",
        (
            "NoInsert",
            "InsertAtTop",
            "InsertAtCurrent",
            "InsertAtBottom",
            "InsertAfterCurrent",
            "InsertBeforeCurrent",
            "InsertAlphabetically",
        ),
    )
    _alias_many(
        QtWidgets.QComboBox,
        QtWidgets.QComboBox,
        "SizeAdjustPolicy",
        ("AdjustToContents", "AdjustToContentsOnFirstShow", "AdjustToMinimumContentsLengthWithIcon"),
    )
    _alias_many(
        QtWidgets.QDialogButtonBox,
        QtWidgets.QDialogButtonBox,
        "StandardButton",
        ("Ok", "Save", "Cancel", "Close", "Yes", "No", "Apply", "Reset", "RestoreDefaults", "Help"),
    )
    _alias_many(
        QtWidgets.QMessageBox,
        QtWidgets.QMessageBox,
        "Icon",
        ("Information", "Warning", "Critical", "Question", "NoIcon"),
    )
    _alias_many(
        QtWidgets.QMessageBox,
        QtWidgets.QMessageBox,
        "StandardButton",
        ("Ok", "Yes", "No", "Cancel", "Close", "Apply", "Reset", "Save", "Discard"),
    )


def _install_qtgui_aliases() -> None:
    _alias_many(QtGui.QFont, QtGui.QFont, "Weight", ("Thin", "ExtraLight", "Light", "Normal", "Medium", "DemiBold", "Bold", "ExtraBold", "Black"))
    _alias_many(
        QtGui.QPalette,
        QtGui.QPalette,
        "ColorRole",
        (
            "Window",
            "WindowText",
            "Base",
            "AlternateBase",
            "Text",
            "Button",
            "ButtonText",
            "Highlight",
            "HighlightedText",
        ),
    )


def _install_qtnetwork_aliases() -> None:
    if QtNetwork is None:
        return
    _alias_attr(QtNetwork.QHostAddress, "Any", QtNetwork.QHostAddress, "SpecialAddress", "Any")
    _alias_attr(QtNetwork.QHostAddress, "LocalHost", QtNetwork.QHostAddress, "SpecialAddress", "LocalHost")
    _alias_attr(
        QtNetwork.QAbstractSocket,
        "ConnectedState",
        QtNetwork.QAbstractSocket,
        "SocketState",
        "ConnectedState",
    )


def _install_qtwebsockets_aliases() -> None:
    if QtWebSockets is None:
        return
    _alias_attr(
        QtWebSockets.QWebSocketServer,
        "NonSecureMode",
        QtWebSockets.QWebSocketServer,
        "SslMode",
        "NonSecureMode",
    )
    _alias_attr(
        QtWebSockets.QWebSocketServer,
        "SecureMode",
        QtWebSockets.QWebSocketServer,
        "SslMode",
        "SecureMode",
    )


_ALIASES_INSTALLED = False


def install_qt5_aliases() -> None:
    """Install common Qt5-style aliases onto Qt6-scoped enums."""

    global _ALIASES_INSTALLED
    if _ALIASES_INSTALLED:
        return
    _install_qtcore_aliases()
    _install_qtwidgets_aliases()
    _install_qtgui_aliases()
    _install_qtnetwork_aliases()
    _install_qtwebsockets_aliases()
    _ALIASES_INSTALLED = True


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
        self.Cancel = _qt_enum(qt_widgets.QMessageBox, "StandardButton", "Cancel")

        self.Accepted = _qt_enum(qt_widgets.QDialog, "DialogCode", "Accepted")
        self.Rejected = _qt_enum(qt_widgets.QDialog, "DialogCode", "Rejected")

        self.Checked = _qt_enum(qt_core.Qt, "CheckState", "Checked")
        self.Unchecked = _qt_enum(qt_core.Qt, "CheckState", "Unchecked")
        self.PartiallyChecked = _qt_enum(qt_core.Qt, "CheckState", "PartiallyChecked")
        self.CheckStateRole = _qt_enum(qt_core.Qt, "ItemDataRole", "CheckStateRole")
        self.RichText = _qt_enum(qt_core.Qt, "TextFormat", "RichText")
        self.PlainText = _qt_enum(qt_core.Qt, "TextFormat", "PlainText")
        self.CustomContextMenu = _qt_enum(qt_core.Qt, "ContextMenuPolicy", "CustomContextMenu")
        self.WA_DeleteOnClose = _qt_enum(qt_core.Qt, "WidgetAttribute", "WA_DeleteOnClose")
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

        self.Rounded = _qt_enum(qt_widgets.QTabWidget, "TabShape", "Rounded")
        self.Triangular = _qt_enum(qt_widgets.QTabWidget, "TabShape", "Triangular")
        self.AnyHostAddress = _qt_enum(qt_network.QHostAddress, "SpecialAddress", "Any") if qt_network else None
        self.LocalHostAddress = _qt_enum(qt_network.QHostAddress, "SpecialAddress", "LocalHost") if qt_network else None
        self.ConnectedState = (
            _qt_enum(qt_network.QAbstractSocket, "SocketState", "ConnectedState") if qt_network else None
        )
        self.NonSecureMode = (
            _qt_enum(qt_websockets.QWebSocketServer, "SslMode", "NonSecureMode") if qt_websockets else None
        )

        self.AnyAddress = self.AnyHostAddress
        self.LocalHost = self.LocalHostAddress

    @staticmethod
    def exec(obj: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a Qt object through the compatibility wrapper."""

        return qexec(obj, *args, **kwargs)


install_qt5_aliases()
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
    "install_qt5_aliases",
    "qexec",
]
