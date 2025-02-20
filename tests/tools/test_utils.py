import os
import string
import tarfile
import tempfile
import zipfile
from unittest.mock import MagicMock, patch

import matplotlib
import numpy as np
import pytest

from REvoDesign import issues
from REvoDesign.citations import CitableModuleAbstract,CitationManager
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.tools.utils import (cmap_reverser, count_and_sort_characters,
                                    extract_archive, generate_strong_password,
                                    get_color, minibatches,
                                    minibatches_generator, random_deduplicate,
                                    rescale_number, timing,require_installed,get_cited)

matplotlib.use('Agg')  # Use the Agg backend to avoid GUI requirements for testing


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
    archive_path = os.path.join(temp_dir, f'test.{archive_type}')

    if archive_type == 'zip':
        with zipfile.ZipFile(archive_path, 'w') as zipf:
            for file_name, content in files:
                zipf.writestr(file_name, content)
    elif archive_type in ['tar.gz', 'tar.bz2', 'tar.xz']:
        mode = 'w:gz' if archive_type == 'tar.gz' else 'w:bz2' if archive_type == 'tar.bz2' else 'w:xz'
        with tarfile.open(archive_path, mode) as tar:
            for file_name, content in files:
                file_path = os.path.join(temp_dir, file_name)
                with open(file_path, 'w') as f:
                    f.write(content)
                tar.add(file_path, arcname=file_name)
                os.remove(file_path)
    else:
        raise ValueError(f"Unsupported archive type: {archive_type}")

    return archive_path


def test_extract_zip(temp_extract_dir):
    files = [('file1.txt', 'content1'), ('file2.txt', 'content2')]
    archive_path = create_test_archive('zip', files, temp_extract_dir)
    extract_archive(archive_path, temp_extract_dir)

    for file_name, _ in files:
        assert os.path.exists(os.path.join(temp_extract_dir, file_name))


def test_extract_tar_gz(temp_extract_dir):
    files = [('file1.txt', 'content1'), ('file2.txt', 'content2')]
    archive_path = create_test_archive('tar.gz', files, temp_extract_dir)
    extract_archive(archive_path, temp_extract_dir)

    for file_name, _ in files:
        assert os.path.exists(os.path.join(temp_extract_dir, file_name))


def test_extract_tar_bz2(temp_extract_dir):
    files = [('file1.txt', 'content1'), ('file2.txt', 'content2')]
    archive_path = create_test_archive('tar.bz2', files, temp_extract_dir)
    extract_archive(archive_path, temp_extract_dir)

    for file_name, _ in files:
        assert os.path.exists(os.path.join(temp_extract_dir, file_name))


def test_extract_tar_xz(temp_extract_dir):
    files = [('file1.txt', 'content1'), ('file2.txt', 'content2')]
    archive_path = create_test_archive('tar.xz', files, temp_extract_dir)
    extract_archive(archive_path, temp_extract_dir)

    for file_name, _ in files:
        assert os.path.exists(os.path.join(temp_extract_dir, file_name))


def test_unsupported_archive(temp_extract_dir):
    unsupported_archive_path = os.path.join(temp_extract_dir, 'test.unknown')
    with open(unsupported_archive_path, 'w') as f:
        f.write('dummy content')

    with pytest.raises(ValueError, match='Unsupported archive format'):
        extract_archive(unsupported_archive_path, temp_extract_dir)


def test_get_color_uniform_range():
    # Test when min_value equals max_value
    color = get_color('viridis', 0.5, 0.5, 0.5)
    assert color == (0.5, 0.5, 0.5)


def test_get_color_clipped_below_range():
    # Test when data is below the range
    color = get_color('viridis', -1, 0, 1)
    assert all(0 <= c <= 1 for c in color)


def test_get_color_clipped_above_range():
    # Test when data is above the range
    color = get_color('viridis', 2, 0, 1)
    assert all(0 <= c <= 1 for c in color)


def test_get_color_within_range():
    # Test when data is within the range
    color = get_color('viridis', 0.5, 0, 1)
    assert all(0 <= c <= 1 for c in color)


def test_get_color_edge_cases():
    # Test edge cases where data is exactly at the min or max
    color_min = get_color('viridis', 0, 0, 1)
    color_max = get_color('viridis', 1, 0, 1)
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
    result = count_and_sort_characters("", ['a', 'e', 'i', 'o', 'u'])
    assert result == {}


def test_no_characters():
    result = count_and_sort_characters("Hello World", [])
    assert result == {}


def test_case_insensitivity():
    result = count_and_sort_characters("Hello World", ['h', 'e', 'l', 'o'])
    expected = {'l': 3, 'o': 2, 'e': 1, 'h': 1}
    assert result == expected


def test_count_and_sort():
    result = count_and_sort_characters("Hello World", ['l', 'o', 'w', 'r', 'd'])
    expected = {'l': 3, 'o': 2, 'w': 1, 'r': 1, 'd': 1}
    assert result == expected


def test_zero_counts():
    result = count_and_sort_characters("Hello World", ['x', 'y', 'z'])
    assert result == {}


def test_mixed_case_input():
    result = count_and_sort_characters("HeLlO WoRlD", ['l', 'o', 'w', 'r', 'd'])
    expected = {'l': 3, 'o': 2, 'w': 1, 'r': 1, 'd': 1}
    assert result == expected


def test_all_characters_present():
    result = count_and_sort_characters("abcdefg", ['a', 'b', 'c', 'd', 'e', 'f', 'g'])
    expected = {'a': 1, 'b': 1, 'c': 1, 'd': 1, 'e': 1, 'f': 1, 'g': 1}
    assert result == expected


def test_no_matching_characters():
    result = count_and_sort_characters("abcdefg", ['h', 'i', 'j'])
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
    with patch('numpy.random.choice') as mock_choice:
        unique_seq1, unique_score1 = random_deduplicate(seq, score)
        mock_choice.assert_called()


def test_generate_strong_password_length():
    """Test that the password has the correct length."""
    for length in range(16, 65):
        password = generate_strong_password(length)
        assert len(password) == length


def test_generate_strong_password_character_set():
    """Test that the password contains only allowed characters."""
    allowed_characters = set(string.ascii_letters + string.digits + '!#$%&*+-./:?@^_~')
    for length in range(16, 65):
        password = generate_strong_password(length)
        assert set(password).issubset(allowed_characters)


def test_generate_strong_password_value_error():
    """Test that a ValueError is raised for invalid lengths."""
    with pytest.raises(ValueError):
        generate_strong_password(15)
    with pytest.raises(ValueError):
        generate_strong_password(65)


def test_timing(caplog):
    # Mock the perf_counter to return specific times
    with patch('time.perf_counter', side_effect=[1.0, 2.0]):
        # Define a dummy function to be decorated
        @timing("test message")
        def dummy_function():
            pass

        # Call the dummy function
        dummy_function()

        # Check the logs
        assert "Started test message" in caplog.text
        assert "Finished test message in " in caplog.text

@pytest.mark.parametrize(
        'package_name, expected_raise',
        [
            ('REvoDesign', False),
            ('TARDIS', True),
        ]
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
    

def test_get_cited():

    class CitableClass(CitableModuleAbstract):
        def __init__(self):
            ...

        def config(self):
            print('Awesome module is under configuration!')

        @get_cited
        def run(self):
            print('Awesome module got run and the paper will be cited!')
        
        __bibtex__ = {'AwesomePaper': """@article {goodpaper2025.01.01.awesomej1009,
    author = {You and Me},
    title = {Good Title is All You Need},
    elocation-id = {2025.01.01.awesomej1009},
    year = {2024},
    doi = {10.1101/2025.01.01.awesomej1009},
    publisher = {Unlimited Sci-Hub Publishing Hard-Drive},
    URL = {https://www.biorxiv.org/content/early/2025/01/01/awesomej1009},
    eprint = {https://www.biorxiv.org/content/early/2025/01/01/awesomej1009.full.pdf},
    journal = {Awesome Journal}
}"""}
        
    expected_citation=CitableClass.__bibtex__
        
    cm=CitationManager()
    cm.clear()

    app=CitableClass()

    assert len(cm.called_citations) == 0, "CitationManager should start with no called citations"

    app.config()
    assert len(cm.called_citations) == 0, "CitationManager should still have no called citations after config()"

    app.run()
    assert len(cm.called_citations) == 1, "CitationManager should have one called citation after run()"
    assert cm.called_citations == expected_citation, "CitationManager should have the expected citation after run()"
    cm.reset_instance()
