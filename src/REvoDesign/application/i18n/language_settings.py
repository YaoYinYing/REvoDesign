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
            lan = [_language for _language in self.language_items if _language.id == lan_id][0]

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
        if language.id and os.path.exists(language.language_file):
            self.bus.ui.trans.load(language.language_file)
            logging.info(f"loading {language.name} ({language.id}) from {language.language_file}")
            QtWidgets.QApplication.instance().installTranslator(self.bus.ui.trans)

        else:
            logging.debug(f"{language.name} ({language.id}) is not available.")
            QtWidgets.QApplication.instance().removeTranslator(self.bus.ui.trans)
        self.bus.ui.retranslateUi(self.window)
        self._set_action_checked(language=language)
        self.bus.set_value("language", language.id)

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
