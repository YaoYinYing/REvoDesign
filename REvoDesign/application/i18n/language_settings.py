from dataclasses import dataclass
from functools import partial
import os
from typing import Any
from pymol.Qt import QtWidgets
from REvoDesign import root_logger
from REvoDesign.application.ui_driver import ConfigBus

self_dir = os.path.dirname(__file__)
language_dir = os.path.join(self_dir, '..', '..', 'UI', 'language')

logging = root_logger.getChild(__name__)


@dataclass(frozen=True)
class LanguageItem:
    name: str
    id: str
    action: Any

    @property
    def language_file(self):
        return os.path.abspath(os.path.join(language_dir, f'{self.id}.qm'))


class LanguageSwitch(QtWidgets.QWidget):
    def __init__(self, window):
        self.bus: ConfigBus = ConfigBus()
        self.window = window

        # language mapping
        self.language_settings: dict[str, dict[str, Any]] = {
            'eng-eng': {
                'name': 'English',
                'action': self.bus.ui.actionEnglish,
            },
            'eng-chs': {'name': '中文', 'action': self.bus.ui.actionChinese},
            'eng-fr': {'name': 'français', 'action': self.bus.ui.actionFrench},
        }

        self.registerLanguage()
        self._set_action_checkable()

        self.restoreFromConfig()

    def restoreFromConfig(self):
        lan = self.language_items[0]

        if lan_id := self.bus.get_value('language', str, reject_none=True):
            logging.info(f'Language {lan_id} is loaded from configuration.')
            lan = [l for l in self.language_items if l.id == lan_id][0]

        self.switchLanguage(language=lan)
        self._set_action_checked(language=lan)

    @property
    def language_items(self) -> tuple[LanguageItem]:
        all_language_items = [
            LanguageItem(
                name=lan_opts.get('name'),
                id=language_id,
                action=lan_opts.get('action'),
            )
            for language_id, lan_opts in self.language_settings.items()
        ]
        return tuple(all_language_items)

    def _bind_to_action(self, language: LanguageItem):
        language.action.triggered.connect(
            partial(self.switchLanguage, language)
        )

    def registerLanguage(self):
        for lan in self.language_items:
            logging.debug(
                f'Registering language {lan.name} by {lan.id} from {lan.language_file}'
            )
            self._bind_to_action(language=lan)

    def switchLanguage(self, language: LanguageItem):
        if language.id and os.path.exists(language.language_file):
            self.bus.ui.trans.load(language.language_file)
            logging.info(
                f'loading {language.name} ({language.id}) from {language.language_file}'
            )
            QtWidgets.QApplication.instance().installTranslator(
                self.bus.ui.trans
            )

        else:
            QtWidgets.QApplication.instance().removeTranslator(
                self.bus.ui.trans
            )
        self.bus.ui.retranslateUi(self.window)
        self._set_action_checked(language=language)
        self.bus.set_value('language', language.id)

    def _set_action_checked(self, language: LanguageItem):
        for lan in self.language_items:
            lan.action.setChecked(lan.id == language.id)

    def _set_action_checkable(self):
        for lan in self.language_items:
            lan_available = (
                os.path.exists(lan.language_file) or lan.name == 'English'
            )
            lan.action.setEnabled(lan_available)
            lan.action.setCheckable(lan_available)
