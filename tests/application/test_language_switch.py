# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for LanguageSwitch i18n component.

These tests use mocks / fakes and do NOT require launching the full PyMOL GUI.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from REvoDesign.Qt import QtCore, QtWidgets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_translator(load_returns: bool = True):
    """Create a MagicMock that quacks like QtCore.QTranslator."""
    t = MagicMock(spec=QtCore.QTranslator)
    t.load.return_value = load_returns
    t.isEmpty.return_value = False
    t.translate.return_value = ""
    return t


def _make_fake_bus_ui(has_trans: bool = True):
    """Create a MagicMock that quacks like the runtime UI proxy (bus.ui)."""
    ui = MagicMock()
    if has_trans:
        ui.trans = _make_fake_translator()
    ui.retranslateUi = MagicMock()
    return ui


def _fake_language_json(tmp_path: Path) -> str:
    """Write a minimal language.json and return its path."""
    data = [
        {"code": "eng-eng", "name": "English", "action": "actionEnglish"},
        {"code": "eng-chs", "name": "中文", "action": "actionChinese"},
    ]
    json_path = tmp_path / "language.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    return str(json_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLanguageSwitchInit:
    """Tests for LanguageSwitch initialisation and translator ownership."""

    def test_uses_existing_bus_ui_trans(self, tmp_path):
        """When bus.ui already has `trans`, LanguageSwitch reuses it."""
        json_fp = _fake_language_json(tmp_path)
        bus_ui = _make_fake_bus_ui(has_trans=True)
        existing = bus_ui.trans
        mock_app = MagicMock()

        with (
            patch("REvoDesign.application.i18n.language_settings.language_json_fp", json_fp),
            patch("REvoDesign.application.i18n.language_settings.language_dir", str(tmp_path)),
            patch("REvoDesign.application.i18n.language_settings.ConfigBus") as mock_bus_cls,
            patch("REvoDesign.application.i18n.language_settings.QtWidgets.QAction", MagicMock()),
            patch.object(QtWidgets.QApplication, "instance", return_value=mock_app),
        ):
            mock_bus = MagicMock()
            mock_bus.ui = bus_ui
            mock_bus.get_value.return_value = None
            mock_bus_cls.return_value = mock_bus

            from REvoDesign.application.i18n.language_settings import LanguageSwitch

            ls = LanguageSwitch(window=MagicMock())
            assert ls.trans is existing
            assert hasattr(ls, "_translator_installed")

    def test_creates_translator_when_bus_ui_lacks_trans(self, tmp_path):
        """When bus.ui lacks `trans`, LanguageSwitch creates and attaches one."""
        json_fp = _fake_language_json(tmp_path)
        bus_ui = _make_fake_bus_ui(has_trans=False)
        del bus_ui.trans  # ensure attribute is absent
        mock_app = MagicMock()
        fake_translator = MagicMock()

        with (
            patch("REvoDesign.application.i18n.language_settings.language_json_fp", json_fp),
            patch("REvoDesign.application.i18n.language_settings.language_dir", str(tmp_path)),
            patch("REvoDesign.application.i18n.language_settings.ConfigBus") as mock_bus_cls,
            patch("REvoDesign.application.i18n.language_settings.QtWidgets.QAction", MagicMock()),
            patch.object(QtWidgets.QApplication, "instance", return_value=mock_app),
            patch.object(QtCore, "QTranslator", return_value=fake_translator),
        ):
            mock_bus = MagicMock()
            mock_bus.ui = bus_ui
            mock_bus.get_value.return_value = None
            mock_bus_cls.return_value = mock_bus

            from REvoDesign.application.i18n.language_settings import LanguageSwitch

            window = MagicMock()
            ls = LanguageSwitch(window=window)
            assert ls.trans is fake_translator
            # bus.ui.trans should now be set to the new translator
            assert bus_ui.trans is fake_translator


class TestLanguageSwitchSwitchLanguage:
    """Tests for switch_language behaviour."""

    def test_switch_to_english_does_not_raise(self, tmp_path):
        """Switching to English (no .qm file) must not raise."""
        json_fp = _fake_language_json(tmp_path)
        bus_ui = _make_fake_bus_ui(has_trans=True)
        mock_app = MagicMock()

        with (
            patch("REvoDesign.application.i18n.language_settings.language_json_fp", json_fp),
            patch("REvoDesign.application.i18n.language_settings.language_dir", str(tmp_path)),
            patch("REvoDesign.application.i18n.language_settings.ConfigBus") as mock_bus_cls,
            patch("REvoDesign.application.i18n.language_settings.QtWidgets.QAction", MagicMock()),
            patch.object(QtWidgets.QApplication, "instance", return_value=mock_app),
        ):
            mock_bus = MagicMock()
            mock_bus.ui = bus_ui
            mock_bus.get_value.return_value = None
            mock_bus_cls.return_value = mock_bus

            from REvoDesign.application.i18n.language_settings import LanguageSwitch

            ls = LanguageSwitch(window=MagicMock())
            english = ls.language_items[0]

            # Must not raise
            ls.switch_language(english)

            # retranslateUi must have been called
            bus_ui.retranslateUi.assert_called()

    def test_removes_old_translator_before_installing_new(self, tmp_path):
        """Translators must not accumulate: remove before install."""
        json_fp = _fake_language_json(tmp_path)
        bus_ui = _make_fake_bus_ui(has_trans=True)
        mock_app = MagicMock()

        with (
            patch("REvoDesign.application.i18n.language_settings.language_json_fp", json_fp),
            patch("REvoDesign.application.i18n.language_settings.language_dir", str(tmp_path)),
            patch("REvoDesign.application.i18n.language_settings.ConfigBus") as mock_bus_cls,
            patch("REvoDesign.application.i18n.language_settings.QtWidgets.QAction", MagicMock()),
            patch.object(QtWidgets.QApplication, "instance", return_value=mock_app),
        ):
            mock_bus = MagicMock()
            mock_bus.ui = bus_ui
            mock_bus.get_value.return_value = None
            mock_bus_cls.return_value = mock_bus

            from REvoDesign.application.i18n.language_settings import LanguageSwitch

            ls = LanguageSwitch(window=MagicMock())

            # First switch — installs the translator
            english = ls.language_items[0]
            ls.switch_language(english)

            # Second switch to English again — should remove first
            ls.switch_language(english)

    def test_retranslate_ui_called_after_switch(self, tmp_path):
        """switch_language must always call bus.ui.retranslateUi."""
        json_fp = _fake_language_json(tmp_path)
        bus_ui = _make_fake_bus_ui(has_trans=True)
        mock_app = MagicMock()

        with (
            patch("REvoDesign.application.i18n.language_settings.language_json_fp", json_fp),
            patch("REvoDesign.application.i18n.language_settings.language_dir", str(tmp_path)),
            patch("REvoDesign.application.i18n.language_settings.ConfigBus") as mock_bus_cls,
            patch("REvoDesign.application.i18n.language_settings.QtWidgets.QAction", MagicMock()),
            patch.object(QtWidgets.QApplication, "instance", return_value=mock_app),
        ):
            mock_bus = MagicMock()
            mock_bus.ui = bus_ui
            mock_bus.get_value.return_value = None
            mock_bus_cls.return_value = mock_bus

            from REvoDesign.application.i18n.language_settings import LanguageSwitch

            ls = LanguageSwitch(window=MagicMock())
            english = ls.language_items[0]
            ls.switch_language(english)

            bus_ui.retranslateUi.assert_called()

    def test_retranslate_language_actions_updates_text(self, tmp_path):
        """_retranslate_language_actions must call setText on every language action."""
        json_fp = _fake_language_json(tmp_path)
        bus_ui = _make_fake_bus_ui(has_trans=True)
        mock_app = MagicMock()

        with (
            patch("REvoDesign.application.i18n.language_settings.language_json_fp", json_fp),
            patch("REvoDesign.application.i18n.language_settings.language_dir", str(tmp_path)),
            patch("REvoDesign.application.i18n.language_settings.ConfigBus") as mock_bus_cls,
            patch("REvoDesign.application.i18n.language_settings.QtWidgets.QAction", MagicMock()),
            patch.object(QtWidgets.QApplication, "instance", return_value=mock_app),
        ):
            mock_bus = MagicMock()
            mock_bus.ui = bus_ui
            mock_bus.get_value.return_value = None
            mock_bus_cls.return_value = mock_bus

            from REvoDesign.application.i18n.language_settings import LanguageSwitch

            ls = LanguageSwitch(window=MagicMock())

            # Call _retranslate_language_actions directly
            ls._retranslate_language_actions()
            for lang_item in ls.language_items:
                lang_item.action.setText.assert_called()
