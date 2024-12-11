import os
import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, call
from REvoDesign.citations.CitationManager import CitationManager, CitableModules  # Replace with actual module path


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
        citation_dir=os.path.join(test_tmp_dir,'citations')
        assert os.path.isdir(citation_dir), "Citations directory not created"
        assert os.listdir(citation_dir), "No citation files found in citations directory"

        



def test_citation_manager_dismiss():
    with mock_citation_manager() as manager:
        manager.silenced_citation_modules.clear()

        manager.dismiss("module1")
        assert "module1" in manager.silenced_citation_modules

def test_citable_modules_notice():
    class TestModule(CitableModules):
        __bibtex__ = {"module1": "citation1", "module2": ("citation2a", "citation2b")}

    with mock_citation_manager() as mock_manager, patch("REvoDesign.citations.CitationManager.logging.info") as mock_logging:



        module = TestModule()
        module.notice()

        mock_logging.assert_has_calls([
            call("\033[0;44m\033[1m[Citation Notice]\033[0m\033[0m\nThe following publications should be cited:\n"),
            call("\033[0;41m\033[1mmodule1\033[0m\033[0m: \033[0;45mcitation1\033[0m\n"),
            call("\033[0;41m\033[1mmodule2-0\033[0m\033[0m: \033[0;45mcitation2a\033[0m\n"),
            call("\033[0;41m\033[1mmodule2-1\033[0m\033[0m: \033[0;45mcitation2b\033[0m\n"),
        ])

def test_citable_modules_cite():
    class TestModule(CitableModules):
        __bibtex__ = {"modulex": "citationx"}

    with mock_citation_manager() as manager, patch("REvoDesign.citations.CitationManager.CitableModules.notice") as mock_notice, \
        patch.object(manager, "update") as mock_update:

        module = TestModule()
        module.cite()

        mock_update.assert_called_once_with(new_citations={"modulex": "citationx"})
        mock_notice.assert_called_once()
