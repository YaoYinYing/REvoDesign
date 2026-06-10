# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Validate runtime UI loading and retranslation for the REvoDesign main window."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from REvoDesign.Qt import QtWidgets
from REvoDesign.Qt.ui_runtime_loader import load_runtime_ui

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_PATH = REPO_ROOT / "src/REvoDesign/UI/REvoDesign.ui"
LINGUIST_PROJECT = REPO_ROOT / "src/REvoDesign/UI/liguist.pro"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    if not UI_PATH.exists():
        print(f"Missing runtime UI file: {UI_PATH.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    if LINGUIST_PROJECT.exists():
        project_text = LINGUIST_PROJECT.read_text(encoding="utf-8")
        if "Ui_REvoDesign.py" in project_text:
            print("Translation extraction still references Ui_REvoDesign.py", file=sys.stderr)
            return 1

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _window, ui = load_runtime_ui(UI_PATH)
    try:
        ui.retranslateUi()
    except Exception as exc:  # pragma: no cover - surfaced as tool failure
        print(f"Runtime UI retranslation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if QtWidgets.QApplication.instance() is app and not app.closingDown():
            app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
