from REvoDesign.tools.utils import get_cited
from REvoDesign.citations import CitableModuleAbstract, CitationManager
import pytest



class MyModule(CitableModuleAbstract):
    @get_cited
    def test_instance_method(self):
        print("Test instance method called")

    @classmethod
    @get_cited
    def test_classmethod(cls):
        print("Test classmethod called")

    @staticmethod
    @get_cited
    def test_staticmethod(key: str):
        print(f"Test staticmethod called: {key}")

def my_function():
    print("My function called")


def test_get_cited_instance_method():
    citation_header = "modulex_instance_method"
    MyModule.__bibtex__ = {citation_header: "citationx"}
    assert citation_header not in CitationManager().called_citations
    module = MyModule()
    module.test_instance_method()
    assert citation_header in CitationManager().called_citations

def test_get_cited_classmethod():
    citation_header = "modulex_class_method"
    MyModule.__bibtex__ = {citation_header: "citationx"}
    assert citation_header not in CitationManager().called_citations
    MyModule.test_classmethod()
    assert citation_header in CitationManager().called_citations

def test_get_cited_staticmethod():
    citation_header = "modulex_static_method"
    MyModule.__bibtex__ = {citation_header: "citationx"}
    assert citation_header not in CitationManager().called_citations
    MyModule.test_staticmethod(key='awesome!')
    assert citation_header in CitationManager().called_citations

def test_get_cited_function():
    citation_header = "modulex_function"
    assert citation_header not in CitationManager().called_citations
    # Add citation note to the function
    setattr(my_function, '__bibtex__', {citation_header: "citationx"})
    # Generate a citable function wrapper
    citable_my_function = get_cited(my_function)
    citable_my_function()
    assert citation_header in CitationManager().called_citations
    