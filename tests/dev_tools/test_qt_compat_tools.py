# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from REvoDesign.Qt import qt_wrapper
from REvoDesign.Qt.ui_runtime_loader import RuntimeUiProxy


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_install_qt6_aliases_adds_scoped_enum_containers_and_moved_classes():
    class _QtNamespace:
        WA_DeleteOnClose = 101
        RichText = 102
        Checked = 103

    class _FakeQtGui:
        pass

    class _FakeQtWidgets:
        class QAction:
            pass

        class QActionGroup:
            pass

        class QShortcut:
            pass

        class QMessageBox:
            Warning = 201
            Yes = 202

        class QComboBox:
            AdjustToContentsOnFirstShow = 203

        class QTabWidget:
            Rounded = 204

        class QDialogButtonBox:
            Ok = 205

        class QSizePolicy:
            Fixed = 206

        class QFrame:
            StyledPanel = 207
            Raised = 208

        class QAbstractItemView:
            NoSelection = 209

        class QHeaderView:
            Stretch = 210

        class QAbstractSpinBox:
            NoButtons = 211

    class _FakeQtCore:
        Qt = _QtNamespace
        QEasingCurve = type("FakeEasingCurve", (), {"OutQuad": 301})

    original_core = qt_wrapper.QtCore
    original_gui = qt_wrapper.QtGui
    original_widgets = qt_wrapper.QtWidgets
    original_network = qt_wrapper.QtNetwork
    original_websockets = qt_wrapper.QtWebSockets
    original_installed = qt_wrapper._ALIASES_INSTALLED

    try:
        qt_wrapper.QtCore = _FakeQtCore
        qt_wrapper.QtGui = _FakeQtGui
        qt_wrapper.QtWidgets = _FakeQtWidgets
        qt_wrapper.QtNetwork = None
        qt_wrapper.QtWebSockets = None
        qt_wrapper._ALIASES_INSTALLED = False
        qt_wrapper.install_qt6_aliases()
    finally:
        qt_wrapper.QtCore = original_core
        qt_wrapper.QtGui = original_gui
        qt_wrapper.QtWidgets = original_widgets
        qt_wrapper.QtNetwork = original_network
        qt_wrapper.QtWebSockets = original_websockets
        qt_wrapper._ALIASES_INSTALLED = original_installed

    assert _FakeQtGui.QAction is _FakeQtWidgets.QAction
    assert _FakeQtGui.QActionGroup is _FakeQtWidgets.QActionGroup
    assert _FakeQtGui.QShortcut is _FakeQtWidgets.QShortcut
    assert _QtNamespace.WidgetAttribute.WA_DeleteOnClose == 101
    assert _QtNamespace.TextFormat.RichText == 102
    assert _QtNamespace.CheckState.Checked == 103


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


def test_runtime_ui_proxy_records_duplicates_and_retranslates():
    from unittest.mock import patch

    class _FakeObject:
        def __init__(self, name: str, children=None):
            self._name = name
            self._children = children or []

        def objectName(self):
            return self._name

        def findChildren(self, _type):
            return list(self._children)

    child_primary = _FakeObject("buttonBox")
    child_duplicate = _FakeObject("buttonBox")
    child_invalid = _FakeObject("invalid-name")
    root = _FakeObject("mainWindow", [child_primary, child_duplicate, child_invalid])
    calls: list[object] = []

    with patch.object(qt_wrapper.QtCore, "QTranslator", return_value=MagicMock()):
        proxy = RuntimeUiProxy(root, retranslator=lambda window: calls.append(window))

    assert proxy.mainWindow is root
    assert proxy.buttonBox is child_primary
    assert proxy._duplicate_object_names["buttonBox"] == [child_duplicate]

    proxy.retranslateUi()
    assert calls == [root]


def test_runtime_ui_proxy_exposes_trans_attribute():
    """RuntimeUiProxy must expose a QTranslator as `trans` for legacy i18n code."""
    from unittest.mock import MagicMock, patch

    class _FakeWindow:
        def objectName(self):
            return "fakeWindow"

        def findChildren(self, _type):
            return []

    window = _FakeWindow()

    with patch.object(qt_wrapper.QtCore, "QTranslator", return_value=MagicMock()) as mock_qtranslator:
        proxy = RuntimeUiProxy(window)

    assert hasattr(proxy, "trans")
    mock_qtranslator.assert_called_once_with(window)

    # `trans` must survive refresh_bindings() (regression check).
    proxy.refresh_bindings()
    assert hasattr(proxy, "trans")

    # retranslateUi must still work.
    called = []
    with patch.object(qt_wrapper.QtCore, "QTranslator", return_value=MagicMock()):
        proxy2 = RuntimeUiProxy(window, retranslator=lambda w: called.append(w))
    proxy2.retranslateUi()
    assert called == [window]
    # `trans` must survive retranslateUi's internal refresh_bindings call.
    assert hasattr(proxy2, "trans")


def test_generate_ui_typing_renders_protocol_and_check_mode(tmp_path):
    script = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/generate_ui_typing.py",
        "generate_ui_typing",
    )
    ui_path = tmp_path / "demo.ui"
    types_path = tmp_path / "types.py"
    ui_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<ui version="4.0">
 <class>Demo</class>
 <widget class="QMainWindow" name="Demo">
  <widget class="QWidget" name="centralwidget"/>
  <action name="actionSource_Code"/>
  <layout class="QVBoxLayout" name="verticalLayout"/>
 </widget>
 <buttongroups>
  <buttongroup name="buttonGroup_demo"/>
 </buttongroups>
</ui>
""",
        encoding="utf-8",
    )

    bindings = script.collect_ui_bindings(ui_path)
    rendered = script.render_types(bindings, ui_path)
    types_path.write_text(rendered, encoding="utf-8")

    assert "class REvoDesignUiProtocol(Protocol):" in rendered
    assert "trans: QtCore.QTranslator" in rendered
    assert "actionSource_Code: QtGui.QAction" in rendered
    assert "verticalLayout: QtWidgets.QVBoxLayout" in rendered
    assert "buttonGroup_demo: QtWidgets.QButtonGroup" in rendered


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


def test_import_guard_detects_ui_runtime_imports(tmp_path):
    script = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/check_qt_binding_imports.py",
        "check_qt_binding_imports_ui",
    )
    script.REPO_ROOT = tmp_path
    bad_file = tmp_path / "src" / "bad_runtime.py"
    bad_file.parent.mkdir()
    bad_file.write_text("from REvoDesign.UI.Ui_REvoDesign import Ui_REvoDesignPyMOL_UI\n", encoding="utf-8")

    errors = script.scan_file(bad_file)
    assert any("Ui_REvoDesign.py" in error for error in errors)
