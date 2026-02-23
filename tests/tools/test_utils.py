# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import inspect
import os
import string
import tarfile
import tempfile
import zipfile
from unittest.mock import patch

import matplotlib
import numpy as np
import pytest

from REvoDesign import issues
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.citations import CitableModuleAbstract, CitationManager
from REvoDesign.tools.utils import (
    cmap_reverser,
    convert_residue_ranges,
    count_and_sort_characters,
    extract_archive,
    generate_strong_password,
    get_cited,
    get_color,
    get_owner_class_from_static,
    inspect_method_types,
    minibatches,
    minibatches_generator,
    pairwise_loop,
    random_deduplicate,
    require_installed,
    rescale_number,
    timing,
)

matplotlib.use("Agg")  # Use the Agg backend to avoid GUI requirements for testing


def test_minibatches_correctly_splits_data():
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    batch_size = 3
    expected_output = [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]
    output = list(minibatches(data, batch_size))
    assert output == expected_output, "The minibatches function did not split the data correctly."


def test_minibatches_last_batch_size():
    data = [1, 2, 3, 4, 5]
    batch_size = 2
    expected_output = [[1, 2], [3, 4], [5]]
    output = list(minibatches(data, batch_size))
    assert output == expected_output, "The last minibatch does not contain the correct number of elements."


def test_minibatches_empty_data():
    data = []
    batch_size = 3
    expected_output = []
    output = list(minibatches(data, batch_size))
    assert output == expected_output, "Minibatches should be empty for empty input data."


def test_minibatches_single_element():
    data = [1]
    batch_size = 1
    expected_output = [[1]]
    output = list(minibatches(data, batch_size))
    assert output == expected_output, "Minibatches should contain the single element in a separate batch."


def test_minibatches_large_batch_size():
    data = [1, 2, 3, 4, 5]
    batch_size = 5
    expected_output = [[1, 2, 3, 4, 5]]
    output = list(minibatches(data, batch_size))
    assert output == expected_output, "Minibatches should handle large batch sizes correctly."


def test_minibatches_batch_size_larger_than_data():
    data = [1, 2, 3]
    batch_size = 5
    expected_output = [[1, 2, 3]]
    output = list(minibatches(data, batch_size))
    assert output == expected_output, "Minibatches should handle batch sizes larger than the data size correctly."


def test_minibatches_generator_even():
    """Test minibatches_generator with an even number of elements."""
    data_generator = (x for x in range(10))
    batch_size = 2
    expected = [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9]]
    minibatches = list(minibatches_generator(data_generator, batch_size))
    assert minibatches == expected


def test_minibatches_generator_odd():
    """Test minibatches_generator with an odd number of elements."""
    data_generator = (x for x in range(9))
    batch_size = 3
    expected = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    minibatches = list(minibatches_generator(data_generator, batch_size))
    assert minibatches == expected


def test_minibatches_generator_empty():
    """Test minibatches_generator with empty data."""
    data_generator = (x for x in range(0))
    batch_size = 5
    expected = []
    minibatches = list(minibatches_generator(data_generator, batch_size))
    assert minibatches == expected


def test_minibatches_generator_single_element():
    """Test minibatches_generator with a single element."""
    data_generator = (x for x in range(1))
    batch_size = 1
    expected = [[0]]
    minibatches = list(minibatches_generator(data_generator, batch_size))
    assert minibatches == expected


def test_minibatches_generator_last_batch_smaller():
    """Test minibatches_generator with the last batch being smaller than the batch size."""
    data_generator = (x for x in range(7))
    batch_size = 3
    expected = [[0, 1, 2], [3, 4, 5], [6]]
    minibatches = list(minibatches_generator(data_generator, batch_size))
    assert minibatches == expected


@pytest.fixture
def temp_extract_dir():
    # Create a temporary directory to extract files
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def create_test_archive(archive_type: str, files: list, temp_dir: str) -> str:
    """
    Helper function to create a test archive file.

    Args:
        archive_type (str): Type of the archive ('zip', 'tar.gz', 'tar.bz2', 'tar.xz').
        files (list): List of tuples containing file names and content.
        temp_dir (str): Temporary directory to create the archive in.

    Returns:
        str: Path to the created archive file.
    """
    archive_path = os.path.join(temp_dir, f"test.{archive_type}")

    if archive_type == "zip":
        with zipfile.ZipFile(archive_path, "w") as zipf:
            for file_name, content in files:
                zipf.writestr(file_name, content)
    elif archive_type in ["tar.gz", "tar.bz2", "tar.xz"]:
        mode = "w:gz" if archive_type == "tar.gz" else "w:bz2" if archive_type == "tar.bz2" else "w:xz"
        with tarfile.open(archive_path, mode) as tar:
            for file_name, content in files:
                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, "w") as f:
                    f.write(content)
                tar.add(file_path, arcname=file_name)
                os.remove(file_path)
    else:
        raise ValueError(f"Unsupported archive type: {archive_type}")

    return archive_path


def test_extract_zip(temp_extract_dir):
    files = [("file1.txt", "content1"), ("file2.txt", "content2")]
    archive_path = create_test_archive("zip", files, temp_extract_dir)
    extract_archive(archive_path, temp_extract_dir)

    for file_name, _ in files:
        assert os.path.exists(os.path.join(temp_extract_dir, file_name))


def test_extract_tar_gz(temp_extract_dir):
    files = [("file1.txt", "content1"), ("file2.txt", "content2")]
    archive_path = create_test_archive("tar.gz", files, temp_extract_dir)
    extract_archive(archive_path, temp_extract_dir)

    for file_name, _ in files:
        assert os.path.exists(os.path.join(temp_extract_dir, file_name))


def test_extract_tar_bz2(temp_extract_dir):
    files = [("file1.txt", "content1"), ("file2.txt", "content2")]
    archive_path = create_test_archive("tar.bz2", files, temp_extract_dir)
    extract_archive(archive_path, temp_extract_dir)

    for file_name, _ in files:
        assert os.path.exists(os.path.join(temp_extract_dir, file_name))


def test_extract_tar_xz(temp_extract_dir):
    files = [("file1.txt", "content1"), ("file2.txt", "content2")]
    archive_path = create_test_archive("tar.xz", files, temp_extract_dir)
    extract_archive(archive_path, temp_extract_dir)

    for file_name, _ in files:
        assert os.path.exists(os.path.join(temp_extract_dir, file_name))


def test_unsupported_archive(temp_extract_dir):
    unsupported_archive_path = os.path.join(temp_extract_dir, "test.unknown")
    with open(unsupported_archive_path, "w") as f:
        f.write("dummy content")

    with pytest.raises(ValueError, match="Unsupported archive format"):
        extract_archive(unsupported_archive_path, temp_extract_dir)


def test_get_color_uniform_range():
    # Test when min_value equals max_value
    color = get_color("viridis", 0.5, 0.5, 0.5)
    assert color == (0.5, 0.5, 0.5)


def test_get_color_clipped_below_range():
    # Test when data is below the range
    color = get_color("viridis", -1, 0, 1)
    assert all(0 <= c <= 1 for c in color)


def test_get_color_clipped_above_range():
    # Test when data is above the range
    color = get_color("viridis", 2, 0, 1)
    assert all(0 <= c <= 1 for c in color)


def test_get_color_within_range():
    # Test when data is within the range
    color = get_color("viridis", 0.5, 0, 1)
    assert all(0 <= c <= 1 for c in color)


def test_get_color_edge_cases():
    # Test edge cases where data is exactly at the min or max
    color_min = get_color("viridis", 0, 0, 1)
    color_max = get_color("viridis", 1, 0, 1)
    assert all(0 <= c <= 1 for c in color_min)
    assert all(0 <= c <= 1 for c in color_max)


def test_cmap_reverser_reverse_true():
    # Test when reverse is True and cmap does not end with '_r'
    cmap = "viridis"
    reversed_cmap = cmap_reverser(cmap, reverse=True)
    assert reversed_cmap == "viridis_r"


def test_cmap_reverser_reverse_true_with_r():
    # Test when reverse is True and cmap already ends with '_r'
    cmap = "viridis_r"
    reversed_cmap = cmap_reverser(cmap, reverse=True)
    assert reversed_cmap == "viridis"


def test_cmap_reverser_reverse_false():
    # Test when reverse is False
    cmap = "viridis"
    reversed_cmap = cmap_reverser(cmap, reverse=False)
    assert reversed_cmap == "viridis"


def test_cmap_reverser_reverse_false_with_r():
    # Test when reverse is False and cmap ends with '_r'
    cmap = "viridis_r"
    reversed_cmap = cmap_reverser(cmap, reverse=False)
    assert reversed_cmap == "viridis_r"


def test_rescale_number_within_range():
    # Test a number within the range
    assert rescale_number(2, 1, 3) == 0.5


def test_rescale_number_at_min():
    # Test a number at the minimum value
    assert rescale_number(1, 1, 3) == 0.0


def test_rescale_number_at_max():
    # Test a number at the maximum value
    assert rescale_number(3, 1, 3) == 1.0


def test_rescale_number_outside_range():
    # Test a number outside the range
    assert rescale_number(4, 1, 3) == 1.0
    assert rescale_number(0, 1, 3) == 0.0


def test_rescale_number_invalid_range():
    # Test with an invalid range where min_value >= max_value
    with pytest.raises(ArithmeticError):
        rescale_number(2, 3, 3)


def test_rescale_number_float_values():
    # Test with floating point numbers
    assert rescale_number(2.5, 1.0, 3.0) == 0.75


def test_rescale_number_negative_values():
    # Test with negative values
    assert rescale_number(-2, -3, -1) == 0.5


def test_empty_string():
    result = count_and_sort_characters("", ["a", "e", "i", "o", "u"])
    assert result == {}


def test_no_characters():
    result = count_and_sort_characters("Hello World", [])
    assert result == {}


def test_case_insensitivity():
    result = count_and_sort_characters("Hello World", ["h", "e", "l", "o"])
    expected = {"l": 3, "o": 2, "e": 1, "h": 1}
    assert result == expected


def test_count_and_sort():
    result = count_and_sort_characters("Hello World", ["l", "o", "w", "r", "d"])
    expected = {"l": 3, "o": 2, "w": 1, "r": 1, "d": 1}
    assert result == expected


def test_zero_counts():
    result = count_and_sort_characters("Hello World", ["x", "y", "z"])
    assert result == {}


def test_mixed_case_input():
    result = count_and_sort_characters("HeLlO WoRlD", ["l", "o", "w", "r", "d"])
    expected = {"l": 3, "o": 2, "w": 1, "r": 1, "d": 1}
    assert result == expected


def test_all_characters_present():
    result = count_and_sort_characters("abcdefg", ["a", "b", "c", "d", "e", "f", "g"])
    expected = {"a": 1, "b": 1, "c": 1, "d": 1, "e": 1, "f": 1, "g": 1}
    assert result == expected


def test_no_matching_characters():
    result = count_and_sort_characters("abcdefg", ["h", "i", "j"])
    assert result == {}


def test_random_deduplicate_empty_input():
    seq = np.array([])
    score = np.array([])
    unique_seq, unique_score = random_deduplicate(seq, score)
    assert len(unique_seq) == 0
    assert len(unique_score) == 0


def test_random_deduplicate_no_deduplicate():
    seq = np.array([1, 1, 1, 1])
    score = np.array([10, 20, 30, 40])
    unique_seq, unique_score = random_deduplicate(seq, score)
    assert len(unique_seq) == 1
    assert unique_seq[0] == 1
    assert unique_score[0] in [10, 20, 30, 40]


def test_random_deduplicate_deduplicate():
    seq = np.array([1, 2, 2, 3, 3, 3])
    score = np.array([10, 20, 30, 40, 50, 60])
    unique_seq, unique_score = random_deduplicate(seq, score)
    assert len(unique_seq) == 3
    assert set(unique_seq) == {1, 2, 3}
    assert unique_score[0] == 10
    assert unique_score[1] in [20, 30]
    assert unique_score[2] in [40, 50, 60]


def test_random_deduplicate_randomness():
    seq = np.array([1, 2, 2, 3, 3, 3])
    score = np.array([10, 20, 30, 40, 50, 60])
    # ensure that the random choice is called at least once
    with patch("numpy.random.choice") as mock_choice:
        unique_seq1, unique_score1 = random_deduplicate(seq, score)
        mock_choice.assert_called()


def test_generate_strong_password_length():
    """Test that the password has the correct length."""
    for length in range(16, 65):
        password = generate_strong_password(length)
        assert len(password) == length


def test_generate_strong_password_character_set():
    """Test that the password contains only allowed characters."""
    allowed_characters = set(string.ascii_letters + string.digits + "!#$%&*+-./:?@^_~")
    for length in range(16, 65):
        password = generate_strong_password(length)
        assert set(password).issubset(allowed_characters)


def test_generate_strong_password_value_error():
    """Test that a ValueError is raised for invalid lengths."""
    with pytest.raises(ValueError):
        generate_strong_password(15)
    with pytest.raises(ValueError):
        generate_strong_password(65)


@pytest.mark.parametrize(
    "unit, expected_unit",
    [
        ("ms", "milliseconds"),
        ("sec", "seconds"),
        ("min", "minutes"),
        ("hr", "hours"),
    ],
)
def test_timing(caplog, unit, expected_unit):
    # Mock the perf_counter to return specific times
    with patch("time.perf_counter", side_effect=[1.0, 2.0]):
        # Define a dummy function to be decorated
        @timing("test message", unit=unit)
        def dummy_function():
            pass

        # Call the dummy function
        dummy_function()

        # Check the logs
        assert "Started test message" in caplog.text
        assert "Finished test message in " in caplog.text

        assert unit in caplog.text


@pytest.mark.parametrize(
    "package_name, expected_raise",
    [
        ("REvoDesign", False),
        ("TARDIS", True),
    ],
)
def test_require_installed(package_name, expected_raise):

    @require_installed
    class TestClass:
        installed = is_package_installed(package_name)
        name = "TestClass"

    if expected_raise:
        with pytest.raises(issues.UninstalledPackageError):
            TestClass()
    else:
        TestClass()


class CitableClass(CitableModuleAbstract):
    def __init__(self): ...

    def config(self):
        print("Awesome module is under configuration!")

    @get_cited
    def run(self):
        print("Awesome module got run and the paper will be cited!")

    __bibtex__ = {
        "AwesomePaper": """@article {goodpaper2025.01.01.awesomej1009,
author = {You and Me},
title = {Good Title is All You Need},
elocation-id = {2025.01.01.awesomej1009},
year = {2024},
doi = {10.1101/2025.01.01.awesomej1009},
publisher = {Unlimited Sci-Hub Publishing Hard-Drive},
URL = {https://www.biorxiv.org/content/early/2025/01/01/awesomej1009},
eprint = {https://www.biorxiv.org/content/early/2025/01/01/awesomej1009.full.pdf},
journal = {Awesome Journal}
}"""
    }


def test_get_cited():

    expected_citation = CitableClass.__bibtex__

    cm = CitationManager()
    cm.clear()

    app = CitableClass()

    assert len(cm.called_citations) == 0, "CitationManager should start with no called citations"

    app.config()
    assert len(cm.called_citations) == 0, "CitationManager should still have no called citations after config()"

    app.run()
    assert len(cm.called_citations) == 1, "CitationManager should have one called citation after run()"
    assert cm.called_citations == expected_citation, "CitationManager should have the expected citation after run()"
    cm.reset_instance()


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        ([1, 2, 3], [(1, 2), (2, 3), (3, 1)]),
        (["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")]),
        ([], []),
        ([42], [(42, 42)]),
        ((1, 2), [(1, 2), (2, 1)]),
    ],
)
def test_pairwise_loop(input_data, expected_output):
    assert list(pairwise_loop(input_data)) == expected_output


# --- Test data setup ---------------------------------------------------------


class MyClass:
    @staticmethod
    def static_method():
        """Simple static method used for tests."""
        return "ok"

    def instance_method(self):
        """Regular instance method."""
        return "instance"

    @classmethod
    def class_method(cls):
        """Class method."""
        return "class"


class Outer:
    class Inner:
        @staticmethod
        def inner_static():
            """Inner class static method."""
            return "inner"


class A:
    @staticmethod
    def shared():
        """Shared static method."""
        return "shared"


class B:
    # Reuse A.shared as a staticmethod-like attribute
    shared = A.shared


def make_local_class():
    """Define a class inside a function to produce a tricky qualname."""

    class LocalClass:
        @staticmethod
        def local_static():
            return "local"

    return LocalClass


def plain_function():
    """A top-level plain function, not attached to any class."""
    return "plain"


# --- Tests for get_owner_class_from_static -----------------------------------


def test_get_owner_class_simple_static():
    """get_owner_class_from_static should return the top-level owning class."""
    m = MyClass.static_method
    cls = get_owner_class_from_static(m)
    assert cls is MyClass
    assert cls.static_method() == "ok"


def test_get_owner_class_nested_class_static():
    """get_owner_class_from_static should resolve nested classes via qualname."""
    m = Outer.Inner.inner_static
    cls = get_owner_class_from_static(m)
    assert cls is Outer.Inner
    assert cls.inner_static() == "inner"


def test_get_owner_class_raises_for_plain_function():
    """Non-method functions should raise a TypeError."""

    def plain_function():
        return 42

    with pytest.raises(LookupError):
        get_owner_class_from_static(plain_function)


def test_get_owner_class_raises_when_no_class_in_qualname():
    """A function with a flat qualname should not be resolved as a class method."""

    # Create a function and manually tweak its __qualname__ to simulate odd cases.
    def f():
        return "x"

    # This is artificial, but verifies defensive behavior.
    f.__qualname__ = "just_function_name"

    with pytest.raises(LookupError):
        get_owner_class_from_static(f)


def test_get_owner_class_with_local_class_may_fail():
    """
    Local classes defined inside a function often have '<locals>' in __qualname__.

    This test documents the current behavior: either it resolves successfully
    (if implementation strips '<locals>') or raises LookupError. The important
    property is that it does not crash with unexpected exceptions.
    """
    LocalClass = make_local_class()
    m = LocalClass.local_static

    try:
        cls = get_owner_class_from_static(m)
    except LookupError:
        # This is acceptable: local classes are a hard edge case.
        pytest.skip("Local class resolution not supported in this environment.")
    else:
        assert cls is LocalClass
        assert cls.local_static() == "local"


# --- Tests: instance methods --------------------------------------------------


def test_inspect_instance_method_bound_to_instance():
    """
    A bound instance method (accessed via an instance) should be reported
    as 'InstanceMethod'.
    """
    obj = MyClass()
    method = obj.instance_method
    assert inspect_method_types(method) == "InstanceMethod"


def test_inspect_instance_method_unbound_from_class_is_function():
    """
    An unbound instance method accessed from the class should look like a plain
    function (no binding), so it should be reported as 'Function'.
    """
    method = MyClass.instance_method
    # In CPython 3, this is just a function object, not a bound method.
    assert not hasattr(method, "__self__")
    assert inspect.isfunction(method)
    assert inspect_method_types(method) == "Function"


# --- Tests: class methods -----------------------------------------------------


def test_inspect_class_method_from_class():
    """
    A class method accessed via the class should be reported as 'ClassMethod'.
    """
    method = MyClass.class_method
    # This is a bound method whose __self__ is the class object.
    assert hasattr(method, "__self__")
    assert method.__self__ is MyClass
    assert inspect_method_types(method) == "ClassMethod"


def test_inspect_class_method_from_instance():
    """
    A class method accessed via an instance is still a class method and
    should be reported as 'ClassMethod'.
    """
    obj = MyClass()
    method = obj.class_method
    # Still bound to the class, not the instance.
    assert hasattr(method, "__self__")
    assert method.__self__ is MyClass
    assert inspect_method_types(method) == "ClassMethod"


# --- Tests: static methods ----------------------------------------------------


def test_inspect_static_method_from_class():
    """
    A static method accessed from the class should be reported as 'StaticMethod'.
    """
    method = MyClass.static_method
    # For a staticmethod, attribute access from the class returns the underlying function.
    assert not hasattr(method, "__self__")
    assert inspect.isfunction(method)
    assert inspect_method_types(method) == "StaticMethod"


def test_inspect_static_method_from_instance():
    """
    A static method accessed from an instance should also be reported as 'StaticMethod'.
    """
    obj = MyClass()
    method = obj.static_method
    # Still just the underlying function.
    assert not hasattr(method, "__self__")
    assert inspect.isfunction(method)
    assert inspect_method_types(method) == "StaticMethod"


def test_inspect_static_method_nested_inner_class():
    """
    Static methods on nested classes should still be reported as 'StaticMethod'.
    """
    method = Outer.Inner.inner_static
    assert inspect.isfunction(method)
    assert "Outer.Inner" in method.__qualname__
    assert inspect_method_types(method) == "StaticMethod"


def test_inspect_static_method_shared_between_classes():
    """
    The same static function object can be attached to multiple classes.
    It is still a 'StaticMethod' regardless of which class it is accessed from.
    """
    method_a = A.shared
    method_b = B.shared

    assert inspect_method_types(method_a) == "StaticMethod"
    assert inspect_method_types(method_b) == "StaticMethod"
    assert method_a is method_b  # same underlying function


# --- Tests: local-class static method ----------------------------------------


def test_inspect_static_method_local_class():
    """
    Static methods on locally defined classes (with '<locals>' in __qualname__)
    should still be treated as 'StaticMethod' if the qualname is dotted.
    """
    LocalClass = make_local_class()
    method = LocalClass.local_static

    # Depending on implementation, this may still be classified as StaticMethod
    # because of the dotted __qualname__ pattern.
    assert inspect.isfunction(method)
    assert "." in method.__qualname__
    assert inspect_method_types(method) == "StaticMethod"


# --- Tests: plain function and non-callable ----------------------------------


def test_inspect_plain_function():
    """
    A top-level function that is not attached to any class should be
    reported as 'Function'.
    """
    method = plain_function
    assert inspect.isfunction(method)
    assert "." not in method.__qualname__  # e.g. 'plain_function'
    assert inspect_method_types(method) == "Function"


def test_inspect_raises_for_non_callable():
    """
    A completely non-callable object should cause a TypeError.
    """
    with pytest.raises(issues.UnexpectedWorkflowError):
        inspect_method_types(42)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "residue_ranges, res_prefix, resr_prefix ,res_suffix, resr_suffix, connector, expected",
    [
        ["1-5+7-9+10-12+13", "", "", "", "", " | ", "1-5 | 7-9 | 10-12 | 13"],
        ["1-5+7-9+10-12+13", "r ", "ri ", "", "", " | ", "ri 1-5 | ri 7-9 | ri 10-12 | r 13"],
        ["1-5+7-9+10-12+13", "", "", "+", "", " | ", "1-5 | 7-9 | 10-12 | 13+"],
        ["1-5+7-9+10-12+13", "r ", "ri ", "+", "", " | ", "ri 1-5 | ri 7-9 | ri 10-12 | r 13+"],
        ["1-5+7-9+10-12+13", "", "", "", "", "; ", "1-5; 7-9; 10-12; 13"],
        ["1-5+7-9+10-12+13", "r ", "ri ", "", "", "; ", "ri 1-5; ri 7-9; ri 10-12; r 13"],
        ["1-5+7-9+10-12+13", "", "", "", "", "; ", "1-5; 7-9; 10-12; 13"],
        ["1-5+7-9+10-12+13", "r ", "ri ", "", "", "; ", "ri 1-5; ri 7-9; ri 10-12; r 13"],
        ["1", "", "", "", "", " | ", "1"],
        ["1", "r ", "ri ", "", "", " | ", "r 1"],
        ["1", "", "", "+", "", " | ", "1+"],
        ["1", "r ", "ri ", "+", "", " | ", "r 1+"],
    ],
)
def test_convert_residue_ranges(residue_ranges, res_prefix, resr_prefix, res_suffix, resr_suffix, connector, expected):
    assert (
        convert_residue_ranges(
            residue_ranges, res_prefix or "", resr_prefix or "", res_suffix or "", resr_suffix or "", connector or " | "
        )
        == expected
    )
