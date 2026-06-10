# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Generate the static typing contract for the runtime-loaded REvoDesign UI."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_PATH = REPO_ROOT / "src/REvoDesign/UI/REvoDesign.ui"
TYPES_PATH = REPO_ROOT / "src/REvoDesign/UI/types.py"

WIDGET_CLASS_MAP = {
    "QMainWindow": "QtWidgets.QMainWindow",
    "QWidget": "QtWidgets.QWidget",
    "QDialog": "QtWidgets.QDialog",
    "QTabWidget": "QtWidgets.QTabWidget",
    "QTabBar": "QtWidgets.QTabBar",
    "QGroupBox": "QtWidgets.QGroupBox",
    "QFrame": "QtWidgets.QFrame",
    "QLabel": "QtWidgets.QLabel",
    "QLineEdit": "QtWidgets.QLineEdit",
    "QTextEdit": "QtWidgets.QTextEdit",
    "QPlainTextEdit": "QtWidgets.QPlainTextEdit",
    "QPushButton": "QtWidgets.QPushButton",
    "QToolButton": "QtWidgets.QToolButton",
    "QCheckBox": "QtWidgets.QCheckBox",
    "QRadioButton": "QtWidgets.QRadioButton",
    "QComboBox": "QtWidgets.QComboBox",
    "QSpinBox": "QtWidgets.QSpinBox",
    "QDoubleSpinBox": "QtWidgets.QDoubleSpinBox",
    "QSlider": "QtWidgets.QSlider",
    "QScrollBar": "QtWidgets.QScrollBar",
    "QProgressBar": "QtWidgets.QProgressBar",
    "QTreeWidget": "QtWidgets.QTreeWidget",
    "QTreeView": "QtWidgets.QTreeView",
    "QTableWidget": "QtWidgets.QTableWidget",
    "QTableView": "QtWidgets.QTableView",
    "QListWidget": "QtWidgets.QListWidget",
    "QListView": "QtWidgets.QListView",
    "QStackedWidget": "QtWidgets.QStackedWidget",
    "QSplitter": "QtWidgets.QSplitter",
    "QScrollArea": "QtWidgets.QScrollArea",
    "QMenuBar": "QtWidgets.QMenuBar",
    "QMenu": "QtWidgets.QMenu",
    "QStatusBar": "QtWidgets.QStatusBar",
    "QToolBar": "QtWidgets.QToolBar",
    "QScrollArea": "QtWidgets.QScrollArea",
    "QScrollArea": "QtWidgets.QScrollArea",
    "QTextBrowser": "QtWidgets.QTextBrowser",
    "QTreeWidgetItem": "QtWidgets.QTreeWidgetItem",
    "QTableWidgetItem": "QtWidgets.QTableWidgetItem",
    "QSpacerItem": "QtWidgets.QSpacerItem",
}
LAYOUT_CLASS_MAP = {
    "QVBoxLayout": "QtWidgets.QVBoxLayout",
    "QHBoxLayout": "QtWidgets.QHBoxLayout",
    "QGridLayout": "QtWidgets.QGridLayout",
    "QFormLayout": "QtWidgets.QFormLayout",
}
ACTION_TYPE = "QtGui.QAction"
BUTTON_GROUP_TYPE = "QtWidgets.QButtonGroup"
FALLBACK_QOBJECT_TYPE = "QtCore.QObject"
FALLBACK_WIDGET_TYPE = "QtWidgets.QWidget"

class UiBinding:
    def __init__(self, name: str, type_name: str, warning: str | None = None) -> None:
        self.name = name
        self.type_name = type_name
        self.warning = warning


def _extract_custom_widget_map(root: ET.Element) -> dict[str, str]:
    custom_types: dict[str, str] = {}
    for custom_widget in root.findall("./customwidgets/customwidget"):
        class_name = custom_widget.findtext("class")
        if not class_name:
            continue
        custom_types[class_name] = FALLBACK_WIDGET_TYPE
    return custom_types


def _resolve_type_name(tag: str, class_name: str, custom_types: dict[str, str]) -> tuple[str, str | None]:
    if tag == "action":
        return ACTION_TYPE, None
    if tag == "layout":
        return LAYOUT_CLASS_MAP.get(class_name, FALLBACK_QOBJECT_TYPE), None
    if tag == "buttongroup":
        return BUTTON_GROUP_TYPE, None
    if tag == "widget":
        if class_name in WIDGET_CLASS_MAP:
            return WIDGET_CLASS_MAP[class_name], None
        if class_name in custom_types:
            return custom_types[class_name], f"Unknown custom widget {class_name!r}; using {custom_types[class_name]}."
        return FALLBACK_WIDGET_TYPE, f"Unknown widget class {class_name!r}; using {FALLBACK_WIDGET_TYPE}."
    return FALLBACK_QOBJECT_TYPE, f"Unknown UI element tag {tag!r}; using {FALLBACK_QOBJECT_TYPE}."


def collect_ui_bindings(ui_path: Path = UI_PATH) -> list[UiBinding]:
    root = ET.parse(ui_path).getroot()
    custom_types = _extract_custom_widget_map(root)
    bindings: dict[str, UiBinding] = {}

    for element in root.iter():
        if element.tag not in {"widget", "layout", "action", "buttongroup"}:
            continue
        name = element.attrib.get("name", "")
        class_name = element.attrib.get("class", "")
        if not name or not name.isidentifier():
            continue
        type_name, warning = _resolve_type_name(element.tag, class_name, custom_types)
        bindings.setdefault(name, UiBinding(name=name, type_name=type_name, warning=warning))

    return [bindings[name] for name in sorted(bindings)]


def render_types(bindings: list[UiBinding], ui_path: Path = UI_PATH) -> str:
    try:
        relative_ui = ui_path.relative_to(REPO_ROOT)
    except ValueError:
        relative_ui = ui_path
    lines = [
        f"# This file is generated from {relative_ui.as_posix()}.",
        "# It is used only for static typing and IDE completion.",
        "# It must not construct the UI at runtime.",
        "# Do not edit by hand. Run: python dev/tools/generate_ui_typing.py",
        "",
        "from __future__ import annotations",
        "",
        "from typing import Protocol",
        "",
        "from REvoDesign.Qt import QtCore, QtGui, QtWidgets",
        "",
        "",
        "class REvoDesignUiProtocol(Protocol):",
        '    """Static typing contract for the runtime-loaded REvoDesign main UI."""',
        "",
        "    trans: QtCore.QTranslator",
        '    """Legacy translator kept for backward compatibility with the generated-UI i18n path."""',
        "",
        "    def retranslateUi(self, window: QtWidgets.QMainWindow) -> None:",
        '        """Retranslate UI strings after a language change."""',
        "        ...",
    ]
    for binding in bindings:
        lines.append("")
        if binding.warning:
            lines.append(f"    # WARNING: {binding.warning}")
        lines.append(f"    {binding.name}: {binding.type_name}")
    lines.append("")
    return "\n".join(lines)


def write_types(check: bool = False) -> int:
    content = render_types(collect_ui_bindings())
    if check:
        current = TYPES_PATH.read_text(encoding="utf-8") if TYPES_PATH.exists() else None
        if current != content:
            print(f"Stale generated typing file: {TYPES_PATH.relative_to(REPO_ROOT)}", file=sys.stderr)
            return 1
        return 0

    TYPES_PATH.write_text(content, encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate generated typing output without modifying files.")
    args = parser.parse_args(argv)
    return write_types(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
