import os
import time
import warnings
from abc import ABC
from typing import Any, Mapping, Union
from REvoDesign import issues
from REvoDesign.logger import ROOT_LOGGER
from ..basic import SingletonAbstract
logging = ROOT_LOGGER.getChild(__name__)
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[0;33m"
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN_BG = "\033[0;44m"
RED_BG = "\033[0;41m"
MAGENTA_BG = "\033[0;45m"
class CitationManager(SingletonAbstract):
    def singleton_init(self):
        self.called_citations: dict[str, Any] = {}
        self.silenced_citation_modules: list[str] = []
        self.initialize()
    @property
    def collected_citations(self) -> list[str]:
        _ = []
        for c in self.called_citations.items():
            if isinstance(c, str):
                _.append(c)
            elif isinstance(c, (list, tuple)):
                _.extend(c)
            else:
                raise issues.BadDataWarning(
                    f"{c=} must be either a dict or a str, instead of {type(c)}"
                )
        return _
    def update(self, new_citations: dict):
        if not (new_citations and isinstance(new_citations, dict)):
            warnings.warn(
                issues.NoInputWarning(
                    f"{new_citations=} is not a valid dictionary."
                )
            )
            return
        self.called_citations.update(new_citations)
    def clear(self):
        self.called_citations.clear()
    def output(self, cwd: str = "."):
        import bibtexparser
        library = bibtexparser.parse_string(
            "\n".join(self.collected_citations)
        )
        if library.failed_blocks:
            warnings.warn(
                issues.REvoDesignWarning(
                    f"Could not parse {library.failed_blocks=}"
                )
            )
        citation_output = os.path.join(
            cwd,
            "citations",
            f'{time.strftime("%Y%m%d", time.localtime())}.bib',
        )
        os.makedirs(os.path.dirname(citation_output), exist_ok=True)
        bibtexparser.write_file(
            file=open(citation_output, "w", encoding="utf8"), library=library
        )
        logging.info(f"Citation is created at {citation_output}")
    def dismiss(self, modulename: str):
        if modulename not in self.silenced_citation_modules:
            self.silenced_citation_modules.append(modulename)
class CitableModuleAbstract(ABC):
    __bibtex__: dict[str, Union[str, tuple]]
    def notice(self):
        if not self.__bibtex__:
            logging.debug("Nothing has to be cited with this module.")
            return
        if all(
            k in CitationManager().silenced_citation_modules
            for k in self.__bibtex__
        ):
            return
        logging.info(
            f"{CYAN_BG}{BOLD}[Citation Notice]{RESET}{RESET}\nThe following publications should be cited:\n"
        )
        for i, citation_item in self.__bibtex__.items():
            if i in CitationManager().silenced_citation_modules:
                continue
            if isinstance(citation_item, str):
                logging.info(
                    f"{RED_BG}{BOLD}{i}{RESET}{RESET}: {MAGENTA_BG}{citation_item}{RESET}\n"
                )
            elif isinstance(citation_item, (tuple, list)):
                for j, _c in enumerate(citation_item):
                    logging.info(
                        f"{RED_BG}{BOLD}{i}-{j}{RESET}{RESET}: {MAGENTA_BG}{_c}{RESET}\n"
                    )
            CitationManager().dismiss(i)
    def cite(self):
        citations = self.__bibtex__
        if not isinstance(citations, Mapping):
            raise TypeError("citation must be a dict.")
        CitationManager().update(new_citations=dict(citations))
        self.notice()