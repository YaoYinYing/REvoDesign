import pytest

from REvoDesign.citations import CitableModuleAbstract, CitationManager
from REvoDesign.tools.utils import get_cited


class MyModule(CitableModuleAbstract):
    @get_cited
    def test_instance_method(self, key: str = 'awesome!'):
        print(f"Test instance method called: {key}")

    @classmethod
    @get_cited
    def test_classmethod(cls, key: str = 'awesome!'):
        print(f"Test classmethod called: {key}")

    @staticmethod
    @get_cited
    def test_staticmethod(key: str = 'awesome!'):
        print(f"Test staticmethod called: {key}")


def my_function():
    print("My function called")


@pytest.mark.parametrize("citation_header, method_name, kwargs", [
    # class level methods
    # not possible to test instance method at class level
    ["modulex_class_normal_method", 'test_classmethod', None],
    ["modulex_static_method", 'test_staticmethod', None],
    ["modulex_class_method_kwargs", 'test_classmethod', {'key': 'great!'}],
    ["modulex_static_method_kwargs", 'test_staticmethod', {'key': 'great!'}],
    # object level methods
    ["modulex_object_normal_method", 'test_instance_method', None],
    ["modulex_object_class_method", 'test_classmethod', None],
    ["modulex_object_static_method", 'test_staticmethod', None],
    ["modulex_object_method_kwargs", 'test_instance_method', {'key': 'great!'}],
    ["modulex_object_class_method_kwargs", 'test_classmethod', {'key': 'great!'}],
    ["modulex_object_static_method_kwargs", 'test_staticmethod', {'key': 'great!'}],
])
def test_get_cited_class(citation_header, method_name, kwargs):
    MyModule.__bibtex__ = {citation_header: "citationx"}
    module = MyModule() if 'object' in citation_header else MyModule
    assert citation_header not in CitationManager().called_citations
    method = getattr(module, method_name)
    method(**kwargs or {})
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
