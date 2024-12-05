'''
Module for citation management.
CitationManager:
    A singleton class that manages citation information.
CitableModules:
    A base class for modules that can be cited, which should contain a `__bibtex__` attribute.
'''

import os
import time
import warnings
from abc import ABC
from typing import Any, Dict, List, Mapping, Union

from REvoDesign import issues
from REvoDesign.logger import root_logger

from ..basic import SingletonAbstract

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
    """
    CitationManager is responsible for managing citations in a singleton pattern,
    ensuring that only one instance of the citation manager exists throughout the application's lifecycle.
    """

    def __init__(self):
        """
        Initialize the CitationManager instance, setting up the necessary attributes.
        """
        # Check if the instance has already been initialized
        if not hasattr(self, "initialized"):
            # Dictionary to store citation information
            self.called_citations: dict[str, Any] = {}
            # List to store names of modules for which citations have been silenced
            self.silenced_citation_modules: list[str] = []
            # Mark the instance as initialized to prevent reinitialization
            self.initialize()
            self.initialized = True

    @property
    def collected_citations(self) -> list[str]:
        """
        Collect all citations and return them as a list of strings.

        Returns:
            list[str]: A list containing all collected citations.
        """
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
        """
        Update the citation manager with new citations.

        Args:
            new_citations (dict): A dictionary containing new citations.
        """
        if not (new_citations and isinstance(new_citations, dict)):
            warnings.warn(
                issues.NoInputWarning(
                    f"{new_citations=} is not a valid dictionary."
                )
            )
            return

        self.called_citations.update(new_citations)

    def clear(self):
        """
        Clear all citations from the citation manager.
        """
        self.called_citations.clear()

    def remove(self, modulename: str):
        """
        Remove citations for a specific module.

        Args:
            modulename (str): The name of the module whose citations are to be removed.
        """
        if modulename not in self.called_citations:
            warnings.warn(
                issues.REvoDesignWarning(
                    issues.REvoDesignWarning(f"{modulename} is not in called.")
                )
            )
            return
        else:
            self.called_citations.pop(modulename)
            warnings.warn(
                issues.REvoDesignWarning(
                    issues.REvoDesignWarning(f"Will not cite {modulename}.")
                )
            )

    def format(self) -> Union[str, Dict, List]:
        """
        Format the citations. The specific implementation is not provided in this code snippet.

        Returns:
            Union[str, Dict, List]: The formatted citations in some structure.
        """
        ...

    def output(self, cwd: str = "."):
        """
        Output the citations to a .bib file in the specified directory.

        Args:
            cwd (str): The directory where the citations should be output. Defaults to the current directory.
        """
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
        """
        Dismiss the citation for a specific module, preventing it from being included in the output.

        Args:
            modulename (str): The name of the module whose citation is to be dismissed.
        """
        if modulename not in self.silenced_citation_modules:
            self.silenced_citation_modules.append(modulename)


class CitableModules(ABC):
    """
    An abstract base class for modules that require citation.

    This class provides methods to handle the citation notice and citation information in a standardized way.
    """
    # A dictionary containing citation information, where the key is the
    # citation name and the value is the citation content or a tuple of
    # multiple citation contents.
    __bibtex__: dict[str, Union[str, tuple]]

    def notice(self):
        """
        Display the citation notice.

        This method checks if there are citations to be displayed, and if the current module's citations have not been silenced, it logs the citation information.
        """
        # If the __bibtex__ dictionary is empty, log a debug message and return.
        if not self.__bibtex__:
            logging.debug("Nothing has to be cited with this module.")
            return
        # If all citation items of the current module have been silenced, return directly.
        if all(
            k in CitationManager().silenced_citation_modules
            for k in self.__bibtex__
        ):
            return

        # Log the citation notice header.
        logging.info(
            f"{CYAN_BG}{BOLD}[Citation Notice]{RESET}{RESET}\nThe following publications should be cited:\n"
        )
        # Iterate through the citation items of the current module.
        for i, citation_item in self.__bibtex__.items():
            # If the current citation item has been silenced, skip it.
            if i in CitationManager().silenced_citation_modules:
                continue
            # If the citation item is a single string, log it directly.
            if isinstance(citation_item, str):
                logging.info(
                    f"{RED_BG}{BOLD}{i}{RESET}{RESET}: {MAGENTA_BG}{citation_item}{RESET}\n"
                )
            # If the citation item is a tuple or list, log each citation content.
            elif isinstance(citation_item, (tuple, list)):
                for j, _c in enumerate(citation_item):
                    logging.info(
                        f"{RED_BG}{BOLD}{i}-{j}{RESET}{RESET}: {MAGENTA_BG}{_c}{RESET}\n"
                    )
            # Dismiss the current citation item to avoid displaying it again.
            CitationManager().dismiss(i)

    def cite(self):
        """
        Add citation to the citation manager.

        This method adds the current module's citation information to the citation manager and then displays the citation notice.
        """
        citations = self.__bibtex__
        # Check if the citation information is a dictionary.
        if not isinstance(citations, Mapping):
            raise TypeError("citation must be a dict.")
        # Update the citation manager with the current module's citation information.
        CitationManager().update(new_citations=dict(citations))
        # Display the citation notice.
        self.notice()
