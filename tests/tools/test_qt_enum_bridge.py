# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Regression test for the package manager's Qt5/Qt6 enum bridge.

The standalone package manager cannot import REvoDesign.Qt, so its bridge
lives inside package_manager.py.  This test extracts the real shipped
function from the installed source and runs it against PyQt6 directly,
without importing package_manager (which requires pymol.Qt and therefore
cannot load in a pure-PyQt6 environment).
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

QT6_PROBE = """
from PyQt6 import QtCore, QtGui, QtWidgets

{bridge}

_install_qt_enum_bridge()
# Members the old allowlist covered, plus the ones it missed
# (QFileDialog.DontResolveSymlinks, QEvent.Close, ...).
QtWidgets.QMessageBox.Ok
QtWidgets.QMessageBox.Warning
QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
QtWidgets.QFileDialog.DontResolveSymlinks
QtCore.QEvent.Close
QtCore.Qt.Tool
QtCore.Qt.RichText
QtCore.Qt.WA_ShowWithoutActivating
QtGui.QFont.Bold
print("bridge-ok")
"""


def _shipped_function_source(file_name: str, function_name: str) -> str:
    """Return the source of a function shipped in the installed package."""
    spec = importlib.util.find_spec("REvoDesign")
    assert spec is not None and spec.origin is not None
    source_path = Path(spec.origin).parent / file_name
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.unparse(node)
    raise AssertionError(f"{function_name} not found in {file_name}")


def test_qt_enum_bridge_resolves_unscoped_qt5_style_access_on_pyqt6():
    if importlib.util.find_spec("PyQt6") is None:
        pytest.skip("PyQt6 not installed")
    bridge = _shipped_function_source("tools/package_manager.py", "_install_qt_enum_bridge")
    result = subprocess.run(
        [sys.executable, "-c", QT6_PROBE.format(bridge=bridge)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "bridge-ok" in result.stdout


QT6_WRAPPER_PROBE = """
import importlib
from PyQt6 import QtCore, QtGui, QtWidgets
QtNetwork = importlib.import_module("PyQt6.QtNetwork")
QtSvg = importlib.import_module("PyQt6.QtSvg")
for _name in ("QtWebSockets", "QtUiTools"):
    try:
        globals()[_name] = importlib.import_module(f"PyQt6.{_name}")
    except ImportError:
        globals()[_name] = None

{bridge}

_install_unscoped_enum_bridge()
QtWidgets.QMessageBox.Ok
QtCore.Qt.ScrollBarAsNeeded
QtWidgets.QHeaderView.Stretch
QtNetwork.QAbstractSocket.ConnectedState
print("wrapper-bridge-ok")
"""


def test_qt_wrapper_enum_bridge_resolves_unscoped_access_on_pyqt6():
    if importlib.util.find_spec("PyQt6") is None:
        pytest.skip("PyQt6 not installed")
    bridge = _shipped_function_source("Qt/qt_wrapper.py", "_install_unscoped_enum_bridge")
    result = subprocess.run(
        [sys.executable, "-c", QT6_WRAPPER_PROBE.format(bridge=bridge)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "wrapper-bridge-ok" in result.stdout
