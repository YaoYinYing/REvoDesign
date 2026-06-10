# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from REvoDesign.Qt import qt_wrapper


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_qtcompat_resolves_qt5_and_qt6_style_enums():
    compat_cls = qt_wrapper._QtCompatNamespace

    class _Qt5Qt:
        RichText = 11
        CustomContextMenu = 12
        Checked = 13
        Unchecked = 14
        CheckStateRole = 23
        ItemIsUserCheckable = 24
        ItemIsEnabled = 25
        AlignLeft = 15
        AlignRight = 16
        AlignTop = 17
        AlignCenter = 18
        AlignHCenter = 26
        AlignVCenter = 19
        AlignLeading = 20
        AlignTrailing = 21
        Horizontal = 27
        ImhDigitsOnly = 22

    class _Qt5Core:
        Qt = _Qt5Qt

    class _Qt6TextFormat:
        RichText = 31

    class _Qt6ContextMenuPolicy:
        CustomContextMenu = 32

    class _Qt6CheckState:
        Checked = 33
        Unchecked = 34

    class _Qt6ItemDataRole:
        CheckStateRole = 60

    class _Qt6ItemFlag:
        ItemIsUserCheckable = 61
        ItemIsEnabled = 62

    class _Qt6AlignmentFlag:
        AlignLeft = 35
        AlignRight = 36
        AlignTop = 37
        AlignCenter = 38
        AlignHCenter = 63
        AlignVCenter = 39
        AlignLeading = 40
        AlignTrailing = 41

    class _Qt6Orientation:
        Horizontal = 64

    class _Qt6InputMethodHint:
        ImhDigitsOnly = 42

    class _Qt6Qt:
        TextFormat = _Qt6TextFormat
        ContextMenuPolicy = _Qt6ContextMenuPolicy
        CheckState = _Qt6CheckState
        ItemDataRole = _Qt6ItemDataRole
        ItemFlag = _Qt6ItemFlag
        AlignmentFlag = _Qt6AlignmentFlag
        Orientation = _Qt6Orientation
        InputMethodHint = _Qt6InputMethodHint

    class _Qt6Core:
        Qt = _Qt6Qt

    class _Qt5MessageBox:
        Information = 1
        Warning = 2
        Critical = 3
        Question = 4
        Ok = 5
        Yes = 6
        No = 7

    class _Qt5TabWidget:
        Rounded = 71
        Triangular = 72

    class _Qt6Icon:
        Information = 51
        Warning = 52
        Critical = 53
        Question = 54

    class _Qt6StandardButton:
        Ok = 55
        Yes = 56
        No = 57

    class _Qt6MessageBox:
        Icon = _Qt6Icon
        StandardButton = _Qt6StandardButton

    class _Qt5Dialog:
        Accepted = 8
        Rejected = 9

    class _Qt6DialogCode:
        Accepted = 58
        Rejected = 59

    class _Qt6Dialog:
        DialogCode = _Qt6DialogCode

    class _Qt6TabShape:
        Rounded = 73
        Triangular = 74

    class _Qt6TabWidget:
        TabShape = _Qt6TabShape

    widgets_qt5 = type(
        "WidgetsQt5",
        (),
        {
            "QMessageBox": _Qt5MessageBox,
            "QDialog": _Qt5Dialog,
            "QTabWidget": _Qt5TabWidget,
        },
    )
    widgets_qt6 = type(
        "WidgetsQt6",
        (),
        {
            "QMessageBox": _Qt6MessageBox,
            "QDialog": _Qt6Dialog,
            "QTabWidget": _Qt6TabWidget,
        },
    )

    compat_qt5 = compat_cls(_Qt5Core, widgets_qt5)
    compat_qt6 = compat_cls(_Qt6Core, widgets_qt6)

    assert compat_qt5.Warning == 2
    assert compat_qt5.Yes == 6
    assert compat_qt5.RichText == 11
    assert compat_qt5.AlignTrailing == 21
    assert compat_qt5.Rounded == 71

    assert compat_qt6.Warning == 52
    assert compat_qt6.Yes == 56
    assert compat_qt6.RichText == 31
    assert compat_qt6.AlignTrailing == 41
    assert compat_qt6.Rounded == 73
    assert compat_qt6.Cancel is None


def test_install_qt5_aliases_adds_qt6_compat_members():
    class _QtNamespace:
        pass

    class _WidgetAttribute:
        WA_DeleteOnClose = 101
        WA_ShowWithoutActivating = 102

    class _ScrollBarPolicy:
        ScrollBarAlwaysOff = 111

    class _GlobalColor:
        yellow = 113
        blue = 114

    class _EasingCurveType:
        OutQuad = 112

    class _FocusPolicy:
        NoFocus = 115

    class _CursorShape:
        PointingHandCursor = 116

    class _WindowType:
        Tool = 117
        FramelessWindowHint = 118
        WindowStaysOnTopHint = 119
        WindowDoesNotAcceptFocus = 120

    class _TabShape:
        Rounded = 202

    class _Icon:
        Warning = 303

    class _SizeAdjustPolicy:
        AdjustToContentsOnFirstShow = 404

    class _SegmentStyle:
        Flat = 505

    class _Weight:
        Bold = 606

    fake_core = SimpleNamespace(Qt=_QtNamespace())
    fake_core.Qt.WidgetAttribute = _WidgetAttribute
    fake_core.Qt.ScrollBarPolicy = _ScrollBarPolicy
    fake_core.Qt.GlobalColor = _GlobalColor
    fake_core.Qt.FocusPolicy = _FocusPolicy
    fake_core.Qt.CursorShape = _CursorShape
    fake_core.Qt.WindowType = _WindowType
    fake_core.QEasingCurve = type("FakeEasingCurve", (), {"Type": _EasingCurveType})
    fake_widgets = SimpleNamespace(
        QTabWidget=type("FakeTabWidget", (), {"TabShape": _TabShape}),
        QMessageBox=type("FakeMessageBox", (), {"Icon": _Icon}),
        QFrame=type("FakeFrame", (), {}),
        QSizePolicy=type("FakeSizePolicy", (), {}),
        QAbstractItemView=type("FakeItemView", (), {}),
        QHeaderView=type("FakeHeaderView", (), {}),
        QAbstractSpinBox=type("FakeSpinBox", (), {}),
        QComboBox=type("FakeComboBox", (), {"SizeAdjustPolicy": _SizeAdjustPolicy}),
        QLCDNumber=type("FakeLCDNumber", (), {"SegmentStyle": _SegmentStyle}),
        QMainWindow=type("FakeMainWindow", (), {}),
        QFormLayout=type("FakeFormLayout", (), {}),
        QLayout=type("FakeLayout", (), {}),
        QDialogButtonBox=type("FakeDialogButtonBox", (), {}),
    )
    fake_gui = SimpleNamespace(
        QPalette=type("FakePalette", (), {}),
        QFont=type("FakeFont", (), {"Weight": _Weight}),
    )

    original_core = qt_wrapper.QtCore
    original_widgets = qt_wrapper.QtWidgets
    original_gui = qt_wrapper.QtGui
    original_network = qt_wrapper.QtNetwork
    original_websockets = qt_wrapper.QtWebSockets
    original_flag = qt_wrapper._ALIASES_INSTALLED
    try:
        qt_wrapper.QtCore = fake_core
        qt_wrapper.QtWidgets = fake_widgets
        qt_wrapper.QtGui = fake_gui
        qt_wrapper.QtNetwork = None
        qt_wrapper.QtWebSockets = None
        qt_wrapper._ALIASES_INSTALLED = False
        qt_wrapper.install_qt5_aliases()
    finally:
        qt_wrapper.QtCore = original_core
        qt_wrapper.QtWidgets = original_widgets
        qt_wrapper.QtGui = original_gui
        qt_wrapper.QtNetwork = original_network
        qt_wrapper.QtWebSockets = original_websockets
        qt_wrapper._ALIASES_INSTALLED = original_flag

    assert fake_core.Qt.WA_DeleteOnClose == 101
    assert fake_core.Qt.WA_ShowWithoutActivating == 102
    assert fake_core.Qt.ScrollBarAlwaysOff == 111
    assert fake_core.Qt.yellow == 113
    assert fake_core.Qt.blue == 114
    assert fake_core.Qt.NoFocus == 115
    assert fake_core.Qt.PointingHandCursor == 116
    assert fake_core.Qt.Tool == 117
    assert fake_core.Qt.FramelessWindowHint == 118
    assert fake_core.Qt.WindowStaysOnTopHint == 119
    assert fake_core.Qt.WindowDoesNotAcceptFocus == 120
    assert fake_core.QEasingCurve.OutQuad == 112
    assert fake_gui.QFont.Bold == 606
    assert fake_widgets.QTabWidget.Rounded == 202
    assert fake_widgets.QMessageBox.Warning == 303
    assert fake_widgets.QComboBox.AdjustToContentsOnFirstShow == 404
    assert fake_widgets.QLCDNumber.Flat == 505


def test_qexec_prefers_exec_and_falls_back_to_exec_():
    calls: list[str] = []

    class _Qt6Dialog:
        def exec(self, *args, **kwargs):
            calls.append(f"exec:{args}:{kwargs}")
            return "qt6"

    class _Qt5Dialog:
        def exec_(self, *args, **kwargs):
            calls.append(f"exec_:{args}:{kwargs}")
            return "qt5"

    assert qt_wrapper.qexec(_Qt6Dialog(), 1, mode="a") == "qt6"
    assert qt_wrapper.qexec(_Qt5Dialog(), 2, mode="b") == "qt5"
    assert calls == ["exec:(1,):{'mode': 'a'}", "exec_:(2,):{'mode': 'b'}"]


def test_import_guard_detects_forbidden_binding_imports(tmp_path):
    script = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/check_qt_binding_imports.py",
        "check_qt_binding_imports",
    )
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("from PyQt5 import QtCore\n", encoding="utf-8")

    errors = script.scan_file(bad_file)
    assert errors
    assert "direct Qt binding import" in errors[0]


def test_import_guard_detects_qt5_only_patterns(tmp_path):
    script = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/check_qt_binding_imports.py",
        "check_qt_binding_imports_patterns",
    )
    script.REPO_ROOT = tmp_path
    bad_file = tmp_path / "src" / "bad_runtime.py"
    bad_file.parent.mkdir()
    bad_file.write_text("dialog.exec_()\nQtCore.Qt.WA_DeleteOnClose\nQTabWidget.Rounded\n", encoding="utf-8")

    errors = script.scan_file(bad_file)
    assert any(".exec_(" in error for error in errors)
    assert any("QtCore.Qt.WA_DeleteOnClose" in error for error in errors)
    assert any("QTabWidget.Rounded" in error for error in errors)


def test_ui_rewrite_converts_generated_binding_imports():
    script = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/compile_qt_ui.py",
        "compile_qt_ui",
    )
    source = (
        "from PyQt6 import QtCore, QtGui, QtWidgets\n"
        "x = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter\n"
        "y = QtCore.Qt.InputMethodHint.ImhDigitsOnly\n"
        "z = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Preferred)\n"
        "w = QtWidgets.QComboBox(parent=self.widget)\n"
    )

    rewritten = script.rewrite_generated_qt_source(source)

    assert "from REvoDesign.Qt import QtCore, QtGui, QtWidgets, QtCompat" in rewritten
    assert "QtCompat.AlignRight | QtCompat.AlignVCenter" in rewritten
    assert "QtCompat.ImhDigitsOnly" in rewritten
    assert "QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)" in rewritten
    assert "QtWidgets.QComboBox(self.widget)" in rewritten


def test_ui_rewrite_converts_pyqt5_imports():
    script = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/compile_qt_ui.py",
        "compile_qt_ui_pyqt5",
    )
    rewritten = script.rewrite_generated_qt_source("from PyQt5 import QtCore, QtGui, QtWidgets\n")
    assert rewritten.strip() == "from REvoDesign.Qt import QtCore, QtGui, QtWidgets"


def test_ui_compiler_whitelist_is_single_revodesign_ui():
    script = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/compile_qt_ui.py",
        "compile_qt_ui_whitelist",
    )
    assert script.UI_COMPILE_MAP == {
        Path("src/REvoDesign/UI/REvoDesign.ui"): Path("src/REvoDesign/UI/Ui_REvoDesign.py"),
    }


def test_package_manager_uses_local_qt_helpers():
    package_manager_source = (
        Path(__file__).resolve().parents[2] / "src/REvoDesign/tools/package_manager.py"
    ).read_text(encoding="utf-8")

    assert "from REvoDesign" not in package_manager_source
    assert "import REvoDesign" not in package_manager_source
    assert "def _qt_enum(" in package_manager_source
    assert "def _qt_exec(" in package_manager_source
    assert "def _install_qt5_aliases_for_manager()" in package_manager_source
