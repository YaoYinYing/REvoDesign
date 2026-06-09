# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import importlib.util
from pathlib import Path

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

    widgets_qt5 = type("WidgetsQt5", (), {"QMessageBox": _Qt5MessageBox, "QDialog": _Qt5Dialog})
    widgets_qt6 = type("WidgetsQt6", (), {"QMessageBox": _Qt6MessageBox, "QDialog": _Qt6Dialog})

    compat_qt5 = compat_cls(_Qt5Core, widgets_qt5)
    compat_qt6 = compat_cls(_Qt6Core, widgets_qt6)

    assert compat_qt5.Warning == 2
    assert compat_qt5.Yes == 6
    assert compat_qt5.RichText == 11
    assert compat_qt5.AlignTrailing == 21

    assert compat_qt6.Warning == 52
    assert compat_qt6.Yes == 56
    assert compat_qt6.RichText == 31
    assert compat_qt6.AlignTrailing == 41


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


def test_ui_rewrite_converts_generated_binding_imports():
    script = _load_module(
        Path(__file__).resolve().parents[2] / "dev/tools/compile_qt_ui.py",
        "compile_qt_ui",
    )
    source = (
        "from PyQt6 import QtCore, QtGui, QtWidgets\n"
        "x = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter\n"
        "y = QtCore.Qt.ImhDigitsOnly\n"
    )

    rewritten = script.rewrite_generated_qt_source(source)

    assert "from REvoDesign.Qt import QtCore, QtGui, QtWidgets, QtCompat" in rewritten
    assert "QtCompat.AlignRight | QtCompat.AlignVCenter" in rewritten
    assert "QtCompat.ImhDigitsOnly" in rewritten
