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
    def test_staticmethod(key: str ='awesome!'):
        print(f"Test staticmethod called: {key}")

def my_function():
    print("My function called")


@pytest.mark.parametrize("citation_header, method_name", [
    # class level methods
    # ["modulex_method", 'test_instance_method'], # not possible to test instance method at class level
    ["modulex_class_method", 'test_classmethod'],
    ["modulex_static_method", 'test_staticmethod'],
    # object level methods
    ["modulex_object_method", 'test_instance_method'],
    ["modulex_object_class_method", 'test_classmethod'],
    ["modulex_object_static_method", 'test_staticmethod']
])
def test_get_cited_class(citation_header, method_name):
    MyModule.__bibtex__ = {citation_header: "citationx"}
    module= MyModule() if 'object' in citation_header else MyModule
    assert citation_header not in CitationManager().called_citations
    method=getattr(module, method_name)
    method()
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
    