# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Compile the whitelisted Qt Designer files and rewrite generated imports."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
import re

DIRECT_QT_IMPORT_RE = re.compile(r"^from (PyQt5|PyQt6|PySide2|PySide6) import ([^\n]+)$", re.MULTILINE)
REVO_QT_IMPORT_RE = re.compile(r"^from REvoDesign\.Qt import ([^\n]+)$", re.MULTILINE)
UI_COMPILE_MAP = {
    Path("src/REvoDesign/UI/REvoDesign.ui"): Path("src/REvoDesign/UI/Ui_REvoDesign.py"),
}
QTCORE_QT_REPLACEMENTS = {
    "AlignHCenter": "QtCompat.AlignHCenter",
    "AlignCenter": "QtCompat.AlignCenter",
    "AlignLeading": "QtCompat.AlignLeading",
    "AlignLeft": "QtCompat.AlignLeft",
    "AlignRight": "QtCompat.AlignRight",
    "AlignTop": "QtCompat.AlignTop",
    "AlignTrailing": "QtCompat.AlignTrailing",
    "AlignVCenter": "QtCompat.AlignVCenter",
    "Horizontal": "QtCompat.Horizontal",
    "ImhDigitsOnly": "QtCompat.ImhDigitsOnly",
    "RichText": "QtCompat.RichText",
}
FORBIDDEN_IMPORT_RE = re.compile(r"\b(?:from|import)\s+(?:PyQt5|PyQt6|PySide2|PySide6)\b")


def find_ui_files(root: Path = REPO_ROOT) -> list[Path]:
    """Return the whitelisted UI files that should be compiled."""

    return [root / relative_path for relative_path in UI_COMPILE_MAP]


def resolve_output_path(ui_path: Path, root: Path = REPO_ROOT) -> Path:
    """Resolve the generated Python file path for a UI file."""

    relative_ui = ui_path.relative_to(root)
    return root / UI_COMPILE_MAP[relative_ui]


def select_pyuic_command() -> list[str]:
    """Select the best available pyuic command in preference order."""

    for executable in ("pyuic6", "pyuic5"):
        if shutil.which(executable):
            return [executable]

    if importlib.util.find_spec("PyQt6.uic.pyuic") is not None:
        return [sys.executable, "-m", "PyQt6.uic.pyuic"]
    if importlib.util.find_spec("PyQt5.uic.pyuic") is not None:
        return [sys.executable, "-m", "PyQt5.uic.pyuic"]

    raise RuntimeError("No pyuic command is available. Install PyQt5 or PyQt6 tooling.")


def _replace_qtcore_qt_constants(text: str) -> str:
    for old_name, new_name in QTCORE_QT_REPLACEMENTS.items():
        text = text.replace(f"QtCore.Qt.{old_name}", new_name)
    return text


def _rewrite_revo_qt_import(text: str) -> str:
    match = REVO_QT_IMPORT_RE.search(text)
    if not match:
        return text

    names = [name.strip() for name in match.group(1).split(",") if name.strip()]
    if "QtCompat" in text and "QtCompat" not in names:
        names.append("QtCompat")
    if "qexec(" in text and "qexec" not in names:
        names.append("qexec")
    rewritten = f"from REvoDesign.Qt import {', '.join(names)}"
    return REVO_QT_IMPORT_RE.sub(rewritten, text, count=1)


def rewrite_generated_qt_source(text: str) -> str:
    """Rewrite generated Qt imports and common Qt5-only constants."""

    def _replace_direct_import(match: re.Match[str]) -> str:
        names = [name.strip() for name in match.group(2).split(",") if name.strip()]
        return f"from REvoDesign.Qt import {', '.join(names)}"

    text = DIRECT_QT_IMPORT_RE.sub(_replace_direct_import, text, count=1)
    text = _replace_qtcore_qt_constants(text)
    text = re.sub(r"([A-Za-z_][A-Za-z0-9_\.]*)\.exec_\(", r"qexec(\1, ", text)
    text = _rewrite_revo_qt_import(text)
    return text


def contains_forbidden_qt_imports(text: str) -> bool:
    """Return True when rewritten text still contains direct Qt binding imports."""

    return FORBIDDEN_IMPORT_RE.search(text) is not None


def compile_ui_to_text(ui_path: Path, pyuic_command: list[str], root: Path = REPO_ROOT) -> str:
    """Compile a UI file and return the rewritten generated Python source."""

    relative_ui = ui_path.relative_to(root)
    with tempfile.TemporaryDirectory(prefix="compile-qt-ui-") as tmp_dir:
        output_path = Path(tmp_dir) / "generated.py"
        command = [*pyuic_command, str(relative_ui), "-o", str(output_path)]
        subprocess.run(command, cwd=root, check=True)
        generated_text = output_path.read_text(encoding="utf-8")

    rewritten = rewrite_generated_qt_source(generated_text)
    if contains_forbidden_qt_imports(rewritten):
        raise RuntimeError(f"Forbidden direct Qt binding import remains after rewriting {relative_ui}.")
    return rewritten


def write_compiled_ui(ui_path: Path, pyuic_command: list[str], root: Path = REPO_ROOT) -> Path:
    """Compile, rewrite, and write the generated Python companion for a UI file."""

    output_path = resolve_output_path(ui_path, root=root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(compile_ui_to_text(ui_path, pyuic_command, root=root), encoding="utf-8")
    return output_path


def check_compiled_ui(ui_path: Path, pyuic_command: list[str], root: Path = REPO_ROOT) -> bool:
    """Return True when the committed generated file matches the expected rewritten output."""

    output_path = resolve_output_path(ui_path, root=root)
    if not output_path.exists():
        return False
    expected_text = compile_ui_to_text(ui_path, pyuic_command, root=root)
    actual_text = output_path.read_text(encoding="utf-8")
    return expected_text == actual_text


def main(argv: list[str] | None = None) -> int:
    """Run the UI compilation or stale-output check."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate generated UI files without modifying them.")
    args = parser.parse_args(argv)

    pyuic_command = select_pyuic_command()
    ui_files = find_ui_files()
    stale_outputs: list[Path] = []

    for ui_path in ui_files:
        if args.check:
            if not check_compiled_ui(ui_path, pyuic_command):
                stale_outputs.append(resolve_output_path(ui_path))
        else:
            write_compiled_ui(ui_path, pyuic_command)

    if stale_outputs:
        for output_path in stale_outputs:
            print(f"Stale generated UI file: {output_path.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
