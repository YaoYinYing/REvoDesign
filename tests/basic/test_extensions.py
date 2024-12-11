import pytest

from REvoDesign.basic.extensions import FileExtension, FileExtensionCollection


def test_file_extension_properties():
    ext = FileExtension(ext="txt", description="Text File")

    assert ext.ext == "txt"
    assert ext.description == "Text File"
    assert ext.filter_string == "Text File ( *.txt )"

def test_file_extension_collection_add():
    ext1 = FileExtension(ext="txt", description="Text File")
    ext2 = FileExtension(ext="md", description="Markdown File")
    
    collection1 = FileExtensionCollection((ext1,))
    collection2 = FileExtensionCollection((ext2,))

    combined = collection1 + collection2
    assert len(combined.extensions) == 2
    assert ext1 in combined.extensions
    assert ext2 in combined.extensions

def test_file_extension_collection_contains():
    ext1 = FileExtension(ext="txt", description="Text File")
    ext2 = FileExtension(ext="md", description="Markdown File")

    collection = FileExtensionCollection((ext1, ext2))

    assert ext1 in collection
    assert "txt" in collection
    assert ".txt" not in collection
    assert "html" not in collection

def test_file_extension_collection_list_all():
    ext1 = FileExtension(ext="txt", description="Text File")
    ext2 = FileExtension(ext="md", description="Markdown File")

    collection = FileExtensionCollection((ext1, ext2))

    assert collection.list_all == ["txt", "md"]

def test_file_extension_collection_list_dot_ext():
    ext1 = FileExtension(ext="txt", description="Text File")
    ext2 = FileExtension(ext="md", description="Markdown File")

    collection = FileExtensionCollection((ext1, ext2))

    assert collection.list_dot_ext == [".txt", ".md"]

def test_file_extension_collection_match():
    ext1 = FileExtension(ext="txt", description="Text File")
    ext2 = FileExtension(ext="md", description="Markdown File")

    collection = FileExtensionCollection((ext1, ext2))

    assert collection.match("txt") is True
    assert collection.match(".txt") is True
    assert collection.match("html") is False

def test_file_extension_collection_squeeze():
    ext1 = FileExtension(ext="txt", description="Text File")
    ext2 = FileExtension(ext="md", description="Markdown File")
    ext3 = FileExtension(ext="csv", description="CSV File")

    collection1 = FileExtensionCollection((ext1, ext2))
    collection2 = FileExtensionCollection((ext2, ext3))

    squeezed = FileExtensionCollection.squeeze((collection1, collection2))

    assert len(squeezed.extensions) == 3
    assert ext1 in squeezed.extensions
    assert ext2 in squeezed.extensions
    assert ext3 in squeezed.extensions

def test_file_extension_collection_filter_string():
    ext1 = FileExtension(ext="txt", description="Text File")
    ext2 = FileExtension(ext="md", description="Markdown File")

    collection = FileExtensionCollection((ext1, ext2))

    assert collection.filter_string == "Text File ( *.txt );;Markdown File ( *.md )"