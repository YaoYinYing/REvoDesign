from abc import (
    ABC,
    abstractmethod,
    abstractclassmethod,
    abstractproperty,
    abstractstaticmethod,
)
from typing import List, Mapping, Union, Dict, Any
from REvoDesign import root_logger
from REvoDesign import issues
import warnings
from REvoDesign import SingletonAbstract

logging = root_logger.getChild(__name__)

# Color escape sequences
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[0;33m"
RESET = "\033[0m"

BOLD = "\033[1m"

CYAN_BG = "\033[0;44m"
RED_BG = "\033[0;41m"
MAGENTA_BG = "\033[0;45m"


class CitationManager(SingletonAbstract):
    def __init__(self):
        # Check if the instance has already been initialized
        if not hasattr(self, 'initialized'):
            self.called_citations: dict[str, Any] = {}
            # Mark the instance as initialized to prevent reinitialization
            self.initialized = True

    @classmethod
    def initialize(cls):
        if not cls._instance:
            cls()
        else:
            ...

    def update(self, new_citations: dict):
        if not (new_citations and isinstance(new_citations, dict)):
            warnings.warn(
                issues.NoInputWarning(
                    f'{new_citations=} is not a valid dictionary.'
                )
            )
            return

        self.called_citations.update(new_citations)

    def clear(self):
        self.called_citations.clear()

    def remove(self, modulename: str):
        if modulename not in self.called_citations:
            warnings.warn(
                issues.REvoDesignWarning(
                    issues.REvoDesignWarning(f'{modulename} is not in called.')
                )
            )
            return
        else:
            self.called_citations.pop(modulename)
            warnings.warn(
                issues.REvoDesignWarning(
                    issues.REvoDesignWarning(f'Will not cite {modulename}.')
                )
            )

    def format(self) -> Union[str, Dict, List]:
        ...

    def output(self, cwd: str):
        ...


class CitableModules(ABC):
    @abstractproperty
    def __bibtex__(self) -> dict[str, str]:
        ...

    def notice(self):
        print(
            f'{CYAN_BG}{BOLD}[Citation Notice]{RESET}{RESET}\nThe following publications should be cited:\n'
        )
        for i, c in self.__bibtex__.items():
            print(
                f"{RED_BG}{BOLD}{i}{RESET}{RESET}: {MAGENTA_BG}{c}{RESET}\n\n"
            )

    def cite(self):
        citations = self.__bibtex__
        if not isinstance(citations, Mapping):
            raise TypeError(f'citation must be a dict.')
        CitationManager().update(new_citations=dict(citations))
        self.notice()
