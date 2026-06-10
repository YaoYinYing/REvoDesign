# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Reject direct Qt binding imports and common Qt5-only runtime patterns."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_ROOTS = ("src", "dev", "tests")
ALLOWED_DIRECT_BINDING_IMPORTS = {
    Path("src/REvoDesign/Qt/qt_wrapper.py"),
    Path("src/REvoDesign/Qt/ui_runtime_loader.py"),
}
ALLOWED_QT5_PATTERN_FILES = {
    Path("src/REvoDesign/Qt/qt_wrapper.py"),
    Path("dev/tools/check_qt_binding_imports.py"),
    Path("src/REvoDesign/tools/package_manager.py"),
}
ALLOWED_TEST_FILES = {
    Path("tests/dev_tools/test_qt_binding_imports_guard.py"),
}
FORBIDDEN_RUNTIME_PATTERNS = (
    ".exec_(",
    "QMessageBox.Warning",
    "QMessageBox.Information",
    "QMessageBox.Critical",
    "QMessageBox.Question",
    "QMessageBox.Yes",
    "QMessageBox.No",
    "QMessageBox.Ok",
    "QtCore.Qt.WA_DeleteOnClose",
    "QTabWidget.Rounded",
)


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root_name in SEARCH_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in {".venv", "__pycache__", ".pytest_cache", ".mypy_cache"} for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def scan_file(path: Path) -> list[str]:
    """Return lint errors for a single file."""

    try:
        relative_path = path.relative_to(REPO_ROOT)
    except ValueError:
        relative_path = path
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    allow_direct_imports = relative_path in ALLOWED_DIRECT_BINDING_IMPORTS or relative_path in ALLOWED_TEST_FILES
    check_runtime_patterns = relative_path.parts[0] in {"src", "dev"} and relative_path not in ALLOWED_QT5_PATTERN_FILES

    if not allow_direct_imports:
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"PyQt5", "PyQt6", "PySide2", "PySide6"}:
                        errors.append(f"{relative_path}:{node.lineno}: direct Qt binding import is not allowed")
                    if "Ui_REvoDesign" in alias.name:
                        errors.append(
                            f"{relative_path}:{node.lineno}: runtime import of Ui_REvoDesign.py is not allowed"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module in {"PyQt5", "PyQt6", "PySide2", "PySide6"}:
                errors.append(f"{relative_path}:{node.lineno}: direct Qt binding import is not allowed")
            elif isinstance(node, ast.ImportFrom) and node.module and "Ui_REvoDesign" in node.module:
                errors.append(f"{relative_path}:{node.lineno}: runtime import of Ui_REvoDesign.py is not allowed")

    for lineno, line in enumerate(text.splitlines(), start=1):
        if check_runtime_patterns:
            for pattern in FORBIDDEN_RUNTIME_PATTERNS:
                if pattern in line:
                    errors.append(f"{relative_path}:{lineno}: forbidden Qt5-only pattern {pattern!r}")
    return errors


def main() -> int:
    """Run the static Qt import guard."""

    errors: list[str] = []
    for path in _iter_python_files():
        errors.extend(scan_file(path))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
