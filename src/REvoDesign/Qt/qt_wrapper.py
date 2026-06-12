# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Qt compatibility layer used by REvoDesign runtime modules."""

from __future__ import annotations

import importlib
import re
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PyQt5 import QtCore as _QtCore
    from PyQt5 import QtGui as _QtGui
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
QtUiTools = _import_optional_qt_module("QtUiTools")


def has_qt_module(module_name: str) -> bool:
    """Return True when the named Qt module is available from the active backend."""

    return globals().get(module_name) is not None


def qexec(obj: Any, *args: Any, **kwargs: Any) -> Any:
    """Execute a Qt object on both Qt5 and Qt6 bindings."""

    exec_method = getattr(obj, "exec", None)
    if callable(exec_method):
        return exec_method(*args, **kwargs)
    return obj.exec_(*args, **kwargs)


def _ensure_enum_container(owner: object, container_name: str) -> object:
    """Return an enum container on the owner, creating one when missing."""

    container = getattr(owner, container_name, None)
    if container is not None:
        return container
    container = SimpleNamespace()
    setattr(owner, container_name, container)
    return container


def _install_scoped_alias(
    owner: object, container_name: str, member_name: str, legacy_value_name: str | None = None
) -> None:
    """Install a Qt6-style scoped enum alias from a Qt5-style unscoped value."""

    legacy_name = legacy_value_name or member_name
    if not hasattr(owner, legacy_name):
        return
    container = _ensure_enum_container(owner, container_name)
    if not hasattr(container, member_name):
        setattr(container, member_name, getattr(owner, legacy_name))


def _install_flat_alias(owner: object, container_name: str, member_name: str, alias_name: str | None = None) -> None:
    """Install a flat Qt5-style alias from a scoped Qt6 enum member when missing."""

    flat_name = alias_name or member_name
    if hasattr(owner, flat_name):
        return
    container = getattr(owner, container_name, None)
    if container is not None and hasattr(container, member_name):
        setattr(owner, flat_name, getattr(container, member_name))


def _qt_enum(owner: Any, enum_name: str, member_name: str) -> Any:
    """Return a Qt enum member using Qt6 scoped lookup with Qt5 fallback."""

    if owner is None:
        return None
    enum_obj = getattr(owner, enum_name, None)
    if enum_obj is not None and hasattr(enum_obj, member_name):
        return getattr(enum_obj, member_name)
    return getattr(owner, member_name, None)


def _install_qtcore_scoped_aliases() -> None:
    qt_namespace = getattr(QtCore, "Qt", None)
    if qt_namespace is None:
        return

    scoped_map = {
        "WidgetAttribute": (
            "WA_DeleteOnClose",
            "WA_Hover",
            "WA_ShowWithoutActivating",
            "WA_TransparentForMouseEvents",
            "WA_TranslucentBackground",
        ),
        "ContextMenuPolicy": ("CustomContextMenu",),
        "TextFormat": ("RichText", "PlainText"),
        "CheckState": ("Checked", "Unchecked", "PartiallyChecked"),
        "Orientation": ("Horizontal", "Vertical"),
        "AlignmentFlag": (
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
        "MouseButton": ("LeftButton", "RightButton", "MiddleButton"),
        "KeyboardModifier": ("NoModifier", "ControlModifier", "ShiftModifier", "AltModifier", "MetaModifier"),
        "ScrollBarPolicy": ("ScrollBarAsNeeded", "ScrollBarAlwaysOff", "ScrollBarAlwaysOn"),
        "GlobalColor": ("yellow", "blue", "red", "green", "black", "white"),
        "FocusPolicy": ("NoFocus",),
        "CursorShape": ("PointingHandCursor",),
        "WindowType": ("Tool", "FramelessWindowHint", "WindowStaysOnTopHint", "WindowDoesNotAcceptFocus"),
        "InputMethodHint": ("ImhDigitsOnly",),
        "BrushStyle": ("NoBrush",),
        "DropAction": ("CopyAction", "MoveAction", "LinkAction", "IgnoreAction"),
    }
    for container_name, member_names in scoped_map.items():
        for member_name in member_names:
            _install_scoped_alias(qt_namespace, container_name, member_name)

    flat_aliases = (
        ("WidgetAttribute", "WA_DeleteOnClose"),
        ("WidgetAttribute", "WA_Hover"),
        ("WidgetAttribute", "WA_ShowWithoutActivating"),
        ("WidgetAttribute", "WA_TransparentForMouseEvents"),
        ("WidgetAttribute", "WA_TranslucentBackground"),
        ("ContextMenuPolicy", "CustomContextMenu"),
        ("TextFormat", "RichText"),
        ("TextFormat", "PlainText"),
        ("CheckState", "Checked"),
        ("CheckState", "Unchecked"),
        ("CheckState", "PartiallyChecked"),
        ("ItemFlag", "ItemIsUserCheckable"),
        ("ItemFlag", "ItemIsEnabled"),
        ("Orientation", "Horizontal"),
        ("Orientation", "Vertical"),
        ("ScrollBarPolicy", "ScrollBarAsNeeded"),
        ("ScrollBarPolicy", "ScrollBarAlwaysOff"),
        ("ScrollBarPolicy", "ScrollBarAlwaysOn"),
        ("GlobalColor", "yellow"),
        ("GlobalColor", "blue"),
        ("GlobalColor", "red"),
        ("GlobalColor", "green"),
        ("GlobalColor", "black"),
        ("GlobalColor", "white"),
        ("FocusPolicy", "NoFocus"),
        ("CursorShape", "PointingHandCursor"),
        ("WindowType", "Tool"),
        ("WindowType", "FramelessWindowHint"),
        ("WindowType", "WindowStaysOnTopHint"),
        ("WindowType", "WindowDoesNotAcceptFocus"),
        ("AlignmentFlag", "AlignLeft"),
        ("AlignmentFlag", "AlignRight"),
        ("AlignmentFlag", "AlignHCenter"),
        ("AlignmentFlag", "AlignJustify"),
        ("AlignmentFlag", "AlignTop"),
        ("AlignmentFlag", "AlignBottom"),
        ("AlignmentFlag", "AlignVCenter"),
        ("AlignmentFlag", "AlignCenter"),
        ("AlignmentFlag", "AlignLeading"),
        ("AlignmentFlag", "AlignTrailing"),
        ("BrushStyle", "NoBrush"),
        ("DropAction", "CopyAction"),
        ("DropAction", "MoveAction"),
        ("DropAction", "LinkAction"),
        ("DropAction", "IgnoreAction"),
    )
    for container_name, member_name in flat_aliases:
        _install_flat_alias(qt_namespace, container_name, member_name)

    for member_name in ("Linear", "InQuad", "OutQuad", "InOutQuad"):
        _install_scoped_alias(QtCore.QEasingCurve, "Type", member_name)
        _install_flat_alias(QtCore.QEasingCurve, "Type", member_name)


def _install_qtwidgets_scoped_aliases() -> None:
    scoped_targets = (
        (getattr(QtWidgets, "QTabWidget", None), "TabShape", ("Rounded", "Triangular")),
        (getattr(QtWidgets, "QTabWidget", None), "TabPosition", ("North", "South", "West", "East")),
        (
            getattr(QtWidgets, "QComboBox", None),
            "SizeAdjustPolicy",
            ("AdjustToContents", "AdjustToContentsOnFirstShow", "AdjustToMinimumContentsLengthWithIcon"),
        ),
        (
            getattr(QtWidgets, "QComboBox", None),
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
        ),
        (getattr(QtWidgets, "QMessageBox", None), "Icon", ("NoIcon", "Information", "Warning", "Critical", "Question")),
        (
            getattr(QtWidgets, "QMessageBox", None),
            "StandardButton",
            ("Ok", "Yes", "No", "Cancel", "Close", "Apply", "Reset", "Save", "Discard"),
        ),
        (
            getattr(QtWidgets, "QDialogButtonBox", None),
            "StandardButton",
            ("Ok", "Save", "Cancel", "Close", "Yes", "No", "Apply", "Reset", "RestoreDefaults", "Help"),
        ),
        (
            getattr(QtWidgets, "QSizePolicy", None),
            "Policy",
            ("Fixed", "Minimum", "Maximum", "Preferred", "Expanding", "MinimumExpanding", "Ignored"),
        ),
        (
            getattr(QtWidgets, "QFrame", None),
            "Shape",
            ("NoFrame", "Box", "Panel", "StyledPanel", "HLine", "VLine", "WinPanel"),
        ),
        (getattr(QtWidgets, "QFrame", None), "Shadow", ("Plain", "Raised", "Sunken")),
        (
            getattr(QtWidgets, "QAbstractItemView", None),
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
        ),
        (
            getattr(QtWidgets, "QAbstractItemView", None),
            "SelectionBehavior",
            ("SelectItems", "SelectRows", "SelectColumns"),
        ),
        (
            getattr(QtWidgets, "QAbstractItemView", None),
            "SelectionMode",
            ("SingleSelection", "MultiSelection", "ExtendedSelection", "ContiguousSelection", "NoSelection"),
        ),
        (getattr(QtWidgets, "QAbstractItemView", None), "ScrollMode", ("ScrollPerItem", "ScrollPerPixel")),
        (
            getattr(QtWidgets, "QHeaderView", None),
            "ResizeMode",
            ("Interactive", "Stretch", "Fixed", "ResizeToContents"),
        ),
        (getattr(QtWidgets, "QAbstractSpinBox", None), "ButtonSymbols", ("UpDownArrows", "PlusMinus", "NoButtons")),
        (getattr(QtWidgets, "QLCDNumber", None), "SegmentStyle", ("Flat", "Outline", "Filled")),
        (getattr(QtWidgets, "QMainWindow", None), "DockOption", ("AllowTabbedDocks", "AnimatedDocks")),
        (getattr(QtWidgets, "QFormLayout", None), "ItemRole", ("LabelRole", "FieldRole")),
        (getattr(QtWidgets, "QLayout", None), "SizeConstraint", ("SetNoConstraint",)),
    )
    for owner, container_name, member_names in scoped_targets:
        if owner is None:
            continue
        for member_name in member_names:
            _install_scoped_alias(owner, container_name, member_name)

    # QStackedLayout.StackingMode: scoped enum in Qt6 (StackAll, StackOne).
    # Provide flat aliases (Qt5-style) so that code referencing
    # QtWidgets.QStackedLayout.StackAll continues to work under Qt6.
    for member_name in ("StackAll", "StackOne"):
        _install_scoped_alias(getattr(QtWidgets, "QStackedLayout", None), "StackingMode", member_name)
        _install_flat_alias(getattr(QtWidgets, "QStackedLayout", None), "StackingMode", member_name)


def _install_qtgui_scoped_aliases() -> None:
    qfont = getattr(QtGui, "QFont", None)
    qpalette = getattr(QtGui, "QPalette", None)
    qpainter = getattr(QtGui, "QPainter", None)
    if qfont is not None:
        for member_name in (
            "Thin",
            "ExtraLight",
            "Light",
            "Normal",
            "Medium",
            "DemiBold",
            "Bold",
            "ExtraBold",
            "Black",
        ):
            _install_scoped_alias(qfont, "Weight", member_name)
    if qpalette is not None:
        for member_name in (
            "Window",
            "WindowText",
            "Base",
            "AlternateBase",
            "Text",
            "Button",
            "ButtonText",
            "Highlight",
            "HighlightedText",
        ):
            _install_scoped_alias(qpalette, "ColorRole", member_name)
    if qpainter is not None:
        _install_scoped_alias(qpainter, "RenderHint", "Antialiasing")
        _install_flat_alias(qpainter, "RenderHint", "Antialiasing")


def _install_qtnetwork_scoped_aliases() -> None:
    if QtNetwork is None:
        return
    for member_name in ("Any", "LocalHost"):
        _install_scoped_alias(QtNetwork.QHostAddress, "SpecialAddress", member_name)
    _install_scoped_alias(QtNetwork.QAbstractSocket, "SocketState", "ConnectedState")


def _install_qtwebsockets_scoped_aliases() -> None:
    if QtWebSockets is None:
        return
    for member_name in ("NonSecureMode", "SecureMode"):
        _install_scoped_alias(QtWebSockets.QWebSocketServer, "SslMode", member_name)


def _install_moved_class_aliases() -> None:
    moved_classes = {
        "QAction": getattr(QtWidgets, "QAction", None),
        "QActionGroup": getattr(QtWidgets, "QActionGroup", None),
        "QShortcut": getattr(QtWidgets, "QShortcut", None),
    }
    for attr_name, fallback in moved_classes.items():
        if fallback is not None and not hasattr(QtGui, attr_name):
            setattr(QtGui, attr_name, fallback)


_ALIASES_INSTALLED = False


def install_qt6_aliases() -> None:
    """Install Qt6-style aliases for legacy Qt5 backends."""

    global _ALIASES_INSTALLED
    if _ALIASES_INSTALLED:
        return

    _install_moved_class_aliases()
    _install_qtcore_scoped_aliases()
    _install_qtwidgets_scoped_aliases()
    _install_qtgui_scoped_aliases()
    _install_qtnetwork_scoped_aliases()
    _install_qtwebsockets_scoped_aliases()
    _ALIASES_INSTALLED = True


def install_qt5_aliases() -> None:
    """Backward-compatible alias for the older helper name."""

    install_qt6_aliases()


class _QtCompatNamespace:
    """Namespace of compatibility constants shared by runtime modules."""

    def __init__(self, qt_core, qt_widgets, qt_network=None, qt_websockets=None):
        self.Warning = _qt_enum(qt_widgets.QMessageBox, "Icon", "Warning")
        self.Information = _qt_enum(qt_widgets.QMessageBox, "Icon", "Information")
        self.Critical = _qt_enum(qt_widgets.QMessageBox, "Icon", "Critical")
        self.Question = _qt_enum(qt_widgets.QMessageBox, "Icon", "Question")
        self.Ok = _qt_enum(qt_widgets.QMessageBox, "StandardButton", "Ok")
        self.Yes = _qt_enum(qt_widgets.QMessageBox, "StandardButton", "Yes")
        self.No = _qt_enum(qt_widgets.QMessageBox, "StandardButton", "No")
        self.Cancel = _qt_enum(qt_widgets.QMessageBox, "StandardButton", "Cancel")
        self.WA_DeleteOnClose = _qt_enum(qt_core.Qt, "WidgetAttribute", "WA_DeleteOnClose")
        self.WA_Hover = _qt_enum(qt_core.Qt, "WidgetAttribute", "WA_Hover")
        self.WA_TranslucentBackground = _qt_enum(qt_core.Qt, "WidgetAttribute", "WA_TranslucentBackground")
        self.WA_TransparentForMouseEvents = _qt_enum(qt_core.Qt, "WidgetAttribute", "WA_TransparentForMouseEvents")
        self.CustomContextMenu = _qt_enum(qt_core.Qt, "ContextMenuPolicy", "CustomContextMenu")
        self.RichText = _qt_enum(qt_core.Qt, "TextFormat", "RichText")
        self.PlainText = _qt_enum(qt_core.Qt, "TextFormat", "PlainText")
        self.Checked = _qt_enum(qt_core.Qt, "CheckState", "Checked")
        self.Unchecked = _qt_enum(qt_core.Qt, "CheckState", "Unchecked")
        self.PartiallyChecked = _qt_enum(qt_core.Qt, "CheckState", "PartiallyChecked")
        self.CheckStateRole = _qt_enum(qt_core.Qt, "ItemDataRole", "CheckStateRole")
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
        self.ScrollBarAsNeeded = _qt_enum(qt_core.Qt, "ScrollBarPolicy", "ScrollBarAsNeeded")
        self.ScrollBarAlwaysOff = _qt_enum(qt_core.Qt, "ScrollBarPolicy", "ScrollBarAlwaysOff")
        self.ScrollBarAlwaysOn = _qt_enum(qt_core.Qt, "ScrollBarPolicy", "ScrollBarAlwaysOn")
        self.AdjustToContentsOnFirstShow = _qt_enum(
            qt_widgets.QComboBox, "SizeAdjustPolicy", "AdjustToContentsOnFirstShow"
        )
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


install_qt6_aliases()
QtCompat = _QtCompatNamespace(QtCore, QtWidgets, QtNetwork, QtWebSockets)

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtNetwork",
    "QtWebSockets",
    "QtSvg",
    "QtUiTools",
    "QT_BACKEND",
    "QT_MAJOR",
    "QtCompat",
    "QtSource",
    "has_qt_module",
    "install_qt6_aliases",
    "install_qt5_aliases",
    "qexec",
]
