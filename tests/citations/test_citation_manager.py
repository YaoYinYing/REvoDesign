import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from REvoDesign.citations.citation_manager import (CitableModuleAbstract,
                                                   CitationManager)


@contextmanager
def mock_citation_manager():

    yield CitationManager()
    CitationManager.reset_instance()


def test_citation_manager_singleton():
    manager1 = CitationManager()
    manager2 = CitationManager()
    assert manager1 is manager2  # Singleton pattern ensures both instances are the same


def test_citation_manager_update():

    with mock_citation_manager() as manager:
        manager.called_citations.clear()

        new_citations = {"module1": "citation1", "module2": "citation2"}
        manager.update(new_citations)

        assert manager.called_citations == new_citations


def test_citation_manager_clear():

    with mock_citation_manager() as manager:
        manager.called_citations = {"module1": "citation1"}
        manager.clear()
        assert manager.called_citations == {}


def test_citation_manager_output(test_tmp_dir):
    with mock_citation_manager() as manager:
        manager.called_citations = {"module1": "citation1"}
        manager.output(cwd=test_tmp_dir)
        citation_dir = os.path.join(test_tmp_dir, 'citations')
        assert os.path.isdir(citation_dir), "Citations directory not created"
        assert os.listdir(citation_dir), "No citation files found in citations directory"


def test_citation_manager_dismiss():
    with mock_citation_manager() as manager:
        manager.silenced_citation_modules.clear()

        manager.dismiss("module1")
        assert "module1" in manager.silenced_citation_modules


def test_citable_module_abstract_notice():
    class TestModule(CitableModuleAbstract):
        __bibtex__ = {"module1": "citation1", "module2": ("citation2a", "citation2b")}

    with mock_citation_manager() as mock_manager:

        module = TestModule()
        module.notice()


def test_citable_module_abstract_cite():
    class TestModule(CitableModuleAbstract):
        __bibtex__ = {"modulex": "citationx"}

    with mock_citation_manager() as manager, patch("REvoDesign.citations.citation_manager.CitableModuleAbstract.notice") as mock_notice, \
            patch.object(manager, "update") as mock_update:

        module = TestModule()
        module.cite()

        mock_update.assert_called_once_with(new_citations={"modulex": "citationx"})
        mock_notice.assert_called_once()


def test_citable_module_abstract_get_citable_class():
    def _myfunction():
        print("Hello World")

    cite_my_function = {"myfunction": "citation1"}
    setattr(_myfunction, "__bibtex__", cite_my_function)

    anonymous_citable_class = CitableModuleAbstract.get_citable_class(func=_myfunction)
    assert anonymous_citable_class.__bibtex__ == cite_my_function
