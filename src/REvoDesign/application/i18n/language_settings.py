# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Internationalization settings
"""

import json
import os
from dataclasses import dataclass
from functools import partial
from typing import Any, TypedDict

from REvoDesign import ROOT_LOGGER
from REvoDesign.Qt import QtWidgets

from ...driver.ui_driver import ConfigBus
from ...Qt import QtCore

_translate = QtCore.QCoreApplication.translate

self_dir = os.path.dirname(__file__)
logging = ROOT_LOGGER.getChild(__name__)

# stores all translation files with Qt's Linguist format
language_dir = os.path.join(self_dir, "..", "..", "UI", "language")

# store language registry json file
language_json_fp = os.path.join(language_dir, "language.json")


class LanguageNameRegistry(TypedDict):
    """
    A dictionary representing a language name registry from a JSON file.

    Attributes:
    - code: The language code.
    - name: The name of the language.
    - action: The action associated with the language.
    """

    code: str
    name: str
    action: str


@dataclass(frozen=True)
class LanguageItem:
    """
    A frozen data class representing a language item.

    Attributes:
        name (str): The name of the language.
        id (str): The unique identifier for the language.
        action (Any): An action associated with the language item.
    """

    name: str
    id: str
    action: Any
    action_name: str

    @property
    def language_file(self):
        """
        Returns the absolute path to the language file.

        This property constructs and returns the absolute path to the language file
        based on the language ID and a predefined directory.

        Returns:
            str: The absolute path to the language file.
        """
        return os.path.abspath(os.path.join(language_dir, f"{self.id}.qm"))


def install_translator_early() -> QtCore.QTranslator | None:
    """Install the saved-language translator before the main window exists.

    Call this before showing the launching/splash page so that static
    .ui strings are translated from the first paint.  Returns the
    translator instance so that :class:`LanguageSwitch` can adopt it
    later via :meth:`_ensure_translator`.

    Returns:
        QTranslator | None: The installed translator, or ``None`` if
        no saved language is available (English or missing .qm).
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None

    # Read the saved language directly from the config file — ConfigBus
    # may still be headless at this point (its .ui hasn't been set yet).
    from REvoDesign.bootstrap import REVODESIGN_CONFIG_DIR

    import yaml

    main_yaml = os.path.join(REVODESIGN_CONFIG_DIR, "main.yaml")
    lan_id = None
    if os.path.exists(main_yaml):
        with open(main_yaml, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        lan_id = cfg.get("language")

    if not lan_id or not isinstance(lan_id, str) or lan_id.startswith("eng-eng"):
        return None

    with open(language_json_fp, encoding="utf-8") as f:
        registry: list[LanguageNameRegistry] = json.load(f)

    qm_path = None
    for entry in registry:
        if entry["code"] == lan_id:
            qm_path = os.path.abspath(os.path.join(language_dir, f"{lan_id}.qm"))
            break

    if not qm_path or not os.path.exists(qm_path):
        return None

    translator = QtCore.QTranslator(app)
    if translator.load(qm_path):
        app.installTranslator(translator)
        logging.info("Early translator installed: %s (%s)", lan_id, qm_path)
        return translator

    return None


class LanguageSwitch(QtWidgets.QWidget):
    """
    Language switching component, manages the language settings and switching for the application.

    Attributes:
        bus: Configuration bus for communication with other components.
        window: Main window of the application.
        language_settings: Dictionary containing language related settings.
    """

    def __init__(self, window):
        """
        Initializes the language switching component.

        Args:
            window: Main window of the application.
        """
        self.bus: ConfigBus = ConfigBus()
        self.window = window

        # language mapping
        with open(language_json_fp, encoding="utf-8") as json_file:
            self.language_settings: list[LanguageNameRegistry] = json.load(json_file)

        self.language_items = self.get_language_items()

        # Own the translator reference so that LanguageSwitch does not depend on
        # bus.ui.trans being present at every call site.  bus.ui.trans is still
        # consulted as a legacy alias via _ensure_translator().
        self._translator_installed = False
        self.trans = self._ensure_translator()
        # _ensure_translator may flip the flag to True when reusing an
        # early-installed translator from install_translator_early().

        self.register_language()
        self._set_action_clickable()

        self.restore_from_config()

    def restore_from_config(self):
        """
        Restores the language setting from the configuration.
        """
        lan = self.language_items[0]

        if lan_id := self.bus.get_value("language", str, reject_none=True):
            logging.debug(f"Language {lan_id} is loaded from configuration.")
            matches = [_language for _language in self.language_items if _language.id == lan_id]
            if matches:
                lan = matches[0]

        # When the restored language is English (no .qm file) and no
        # translator has been installed yet, the UI is already showing
        # correct source-language strings.  Skipping the retranslation
        # pass avoids an unnecessary widget-tree walk at startup.
        if lan.id.startswith("eng-eng") and not self._translator_installed:
            self._set_action_checked(language=lan)
            self.bus.set_value("language", lan.id)
            return

        self.switch_language(language=lan)
        self._set_action_checked(language=lan)

    def get_language_items(self) -> tuple[LanguageItem, ...]:
        """
        Returns a tuple of all language items.

        Returns:
            Tuple of all language items.
        """
        all_language_items = [
            LanguageItem(
                name=lan_registry["name"],
                id=lan_registry["code"],
                action=self.add_lan_to_menu(lan_registry),
                action_name=lan_registry["action"],
            )
            for lan_registry in self.language_settings
        ]
        return tuple(all_language_items)

    def _ensure_translator(self) -> QtCore.QTranslator:
        """Return the persistent translator used by the language switcher.

        Checks ``bus.ui.trans`` (legacy path), then the QApplication for
        an early-installed translator from :func:`install_translator_early`,
        and creates a fresh one only as a last resort.
        """
        existing = getattr(self.bus.ui, "trans", None)
        if (
            existing is not None
            and hasattr(existing, "load")
            and hasattr(existing, "isEmpty")
            and hasattr(existing, "translate")
        ):
            return existing

        # Reuse the translator that install_translator_early installed so
        # removeTranslator / installTranslator work on the same instance.
        app = QtWidgets.QApplication.instance()
        if app is not None:
            for child in app.children():
                if isinstance(child, QtCore.QTranslator):
                    setattr(self.bus.ui, "trans", child)
                    self._translator_installed = True
                    return child

        translator = QtCore.QTranslator(self.window)
        setattr(self.bus.ui, "trans", translator)
        return translator

    def _bind_to_action(self, language: LanguageItem):
        """
        Binds the language switching action to the specified language.

        Args:
            language: Language item to bind the action to.
        """
        language.action.triggered.connect(partial(self.switch_language, language))

    def add_lan_to_menu(self, lan_regsitry: LanguageNameRegistry):
        """
        Adds the language item to the language menu.
        """

        new_action = QtWidgets.QAction()
        new_action.setEnabled(False)
        new_action.setObjectName(lan_regsitry["action"])
        setattr(self.bus.ui, lan_regsitry["action"], new_action)
        self.bus.ui.menuLanguage.addAction(new_action)
        new_action.setText(_translate("REvoDesignPyMOL_UI", lan_regsitry["name"]))
        logging.debug(f"Adding language {lan_regsitry['name']} to menu.")
        return new_action

    def register_language(self):
        """
        Registers all languages.
        """
        for lan in self.language_items:
            logging.debug(f"Registering language {lan.name} by {lan.id} from {lan.language_file}")
            self._bind_to_action(language=lan)

    def switch_language(self, language: LanguageItem):
        """
        Switches to the specified language.

        Args:
            language: Language item to switch to.
        """
        app = QtWidgets.QApplication.instance()
        if app is None:
            raise RuntimeError("Cannot switch language without a QApplication instance.")

        # Remove the previously installed translator before loading a new one
        # so that translators never accumulate inside the application.
        if self._translator_installed:
            app.removeTranslator(self.trans)
            self._translator_installed = False

        if language.id and os.path.exists(language.language_file):
            loaded = self.trans.load(language.language_file)
            if loaded:
                app.installTranslator(self.trans)
                self._translator_installed = True
                logging.info("Loading %s (%s) from %s", language.name, language.id, language.language_file)
            else:
                logging.warning("Failed to load translation file for %s (%s)", language.name, language.id)
        else:
            logging.debug(
                "%s (%s) is not available; falling back to source-language strings.", language.name, language.id
            )

        self.bus.ui.retranslateUi(self.window)

        # Retranslate any open dialogs that support it (e.g. ValueDialog).
        if hasattr(self.bus.ui, "open_windows"):
            for window in list(self.bus.ui.open_windows):
                retranslate = getattr(window, "retranslateUi", None)
                if retranslate is not None:
                    retranslate()

        self._retranslate_language_actions()
        self._set_action_checked(language=language)
        self.bus.set_value("language", language.id)

    def _retranslate_language_actions(self) -> None:
        """Retranslate dynamically created language menu actions.

        Language actions are created in ``add_lan_to_menu()`` and are not
        covered by the ``.ui`` retranslation pass.  This method updates
        their text so that the language menu reflects the current locale.
        """
        for language in self.language_items:
            language.action.setText(_translate("REvoDesignPyMOL_UI", language.name))

    def _set_action_checked(self, language: LanguageItem):
        """
        Sets the checked state of the language actions.

        Args:
            language: Currently selected language item.
        """
        for lan in self.language_items:
            lan.action.setChecked(lan.id == language.id)

    def _set_action_clickable(self):
        """
        Sets the clickable state of the language actions.
        """
        for lan in self.language_items:
            lan_available = os.path.exists(lan.language_file) or lan.name == "English"
            lan.action.setEnabled(lan_available)
            lan.action.setCheckable(lan_available)
