# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Validate runtime UI loading, retranslation, and i18n for the REvoDesign main window."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from REvoDesign.Qt import QtWidgets
from REvoDesign.Qt.ui_runtime_loader import load_runtime_ui

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_PATH = REPO_ROOT / "src/REvoDesign/UI/REvoDesign.ui"
LINGUIST_PROJECT = REPO_ROOT / "src/REvoDesign/UI/liguist.pro"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


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
    window, ui = load_runtime_ui(UI_PATH)
    try:
        # --- RuntimeUiProxy i18n contract ---
        require(hasattr(ui, "trans"), "RuntimeUiProxy must expose a `trans` attribute for legacy i18n code")
        trans = ui.trans
        require(hasattr(trans, "load"), "translator must expose `load`")
        require(hasattr(trans, "isEmpty"), "translator must expose `isEmpty`")
        require(hasattr(trans, "translate"), "translator must expose `translate`")

        # retranslateUi must work
        ui.retranslateUi(window)

        # `trans` must survive retranslateUi's internal refresh_bindings call
        require(hasattr(ui, "trans"), "RuntimeUiProxy.trans must survive retranslateUi -> refresh_bindings")

        # --- Dynamic language action registry ---
        require(hasattr(ui, "menuLanguage"), "menuLanguage menu must be available for dynamic actions")
        new_action = QtWidgets.QAction()
        new_action.setObjectName("actionTestLang")
        ui.actionTestLang = new_action
        ui.menuLanguage.addAction(new_action)
        require(hasattr(ui, "actionTestLang"), "RuntimeUiProxy must accept dynamic action attributes")
        require(ui.actionTestLang is new_action, "RuntimeUiProxy must retain dynamic action attributes")

        # --- LanguageSwitch instantiation / exercise (smoke) ---
        # LanguageSwitch depends on a ConfigBus singleton that has `ui` already
        # attached.  Set it up with the proxy we just loaded so the smoke check
        # runs without a full application bootstrap.
        from REvoDesign.application.i18n.language_settings import LanguageSwitch
        from REvoDesign.driver.ui_driver import ConfigBus

        config_bus = ConfigBus()
        config_bus.ui = ui

        lang_switch = LanguageSwitch(window)
        require(hasattr(lang_switch, "trans"), "LanguageSwitch must own a `trans` reference")
        require(lang_switch.trans is not None, "LanguageSwitch.trans must not be None")
        require(hasattr(lang_switch.trans, "load"), "LanguageSwitch.trans must be a translator-like object")

        # English / source-language switch must not raise
        english = lang_switch.language_items[0]
        lang_switch.switch_language(english)

        print("Runtime UI i18n validation OK")

    except Exception as exc:  # pragma: no cover - surfaced as tool failure
        print(f"Runtime UI i18n validation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if QtWidgets.QApplication.instance() is app and not app.closingDown():
            app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
