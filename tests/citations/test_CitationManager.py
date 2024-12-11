import pytest
from unittest.mock import MagicMock, patch, call
from REvoDesign.citations.CitationManager import CitationManager, CitableModules  # Replace with actual module path


def test_citation_manager_singleton():
    manager1 = CitationManager()
    manager2 = CitationManager()
    assert manager1 is manager2  # Singleton pattern ensures both instances are the same

def test_citation_manager_update():
    manager = CitationManager()
    manager.called_citations.clear()

    new_citations = {"module1": "citation1", "module2": "citation2"}
    manager.update(new_citations)

    assert manager.called_citations == new_citations

def test_citation_manager_clear():
    manager = CitationManager()
    manager.called_citations = {"module1": "citation1"}
    manager.clear()
    assert manager.called_citations == {}



def test_citation_manager_output():
    manager = CitationManager()
    manager.called_citations = {"module1": "citation1"}

    with patch("bibtexparser.parse_string") as mock_parse, \
         patch("REvoDesign.citations.CitationManager.bibtexparser.write_file") as mock_write, \
         patch("REvoDesign.citations.CitationManager.os.makedirs") as mock_makedirs:

        mock_parse.return_value = MagicMock(failed_blocks=None)

        manager.output(cwd="/mock/path")

        mock_makedirs.assert_called_once_with("/mock/path/citations", exist_ok=True)
        mock_write.assert_called_once()

        

def test_citation_manager_dismiss():
    manager = CitationManager()
    manager.silenced_citation_modules.clear()

    manager.dismiss("module1")
    assert "module1" in manager.silenced_citation_modules

def test_citable_modules_notice():
    class TestModule(CitableModules):
        __bibtex__ = {"module1": "citation1", "module2": ("citation2a", "citation2b")}

    with patch("REvoDesign.citations.CitationManager.CitationManager") as mock_manager, \
         patch("REvoDesign.citations.CitationManager.logging.info") as mock_logging:

        mock_manager.return_value = MagicMock(
            silenced_citation_modules=[]
        )

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
        __bibtex__ = {"module1": "citation1"}

    with patch("REvoDesign.citations.CitationManager.CitationManager.update") as mock_update, \
         patch("REvoDesign.citations.CitationManager.CitableModules.notice") as mock_notice:

        module = TestModule()
        module.cite()

        mock_update.assert_called_once_with({"module1": "citation1"})
        mock_notice.assert_called_once()