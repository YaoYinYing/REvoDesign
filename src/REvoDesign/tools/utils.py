'''
Orphaneous functions for REvoDesign
'''

import contextlib
import os
import random
import string

import tarfile
import time
import zipfile
from typing import Union

import matplotlib
import numpy as np

from REvoDesign.logger import root_logger


from .package_manager import run_worker_thread_with_progress,run_command

logging = root_logger.getChild(__name__)


def dirname_does_exist(fp):
    return os.path.exists(os.path.dirname(fp))


def filepath_does_exists(fp):
    return os.path.exists(fp)


def minibatches(inputs_data, batch_size):
    """
    Generates minibatches from input data with a specified batch size.

    Args:
    - inputs_data (list or iterable): Input data to be divided into minibatches.
    - batch_size (int): Size of each minibatch.

    Yields:
    - list: Minibatches of data based on the specified batch size.

    Note:
    If the length of the inputs_data is not perfectly divisible by the batch_size,
    the last batch may have fewer elements.

    Example Usage:
    ```python
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    batch_size = 3
    for batch in minibatches(data, batch_size):
        print(batch)
    ```
    """
    for start_idx in range(0, len(inputs_data), batch_size):
        if len(inputs_data[start_idx:]) > batch_size:
            excerpt = slice(start_idx, start_idx + batch_size)
            print("Send data in length: %s" % len(inputs_data[excerpt]))
            yield inputs_data[excerpt]
        else:
            print(
                "Send final data in length: %s" % len(inputs_data[start_idx:])
            )
            yield inputs_data[start_idx:]


def minibatches_generator(inputs_data_generator, batch_size):
    """
    Generates minibatches from a generator of input data with a specified batch size.

    Args:
    - inputs_data_generator (generator): Generator yielding input data.
    - batch_size (int): Size of each minibatch.

    Yields:
    - list: Minibatches of data based on the specified batch size.

    Note:
    If the length of the inputs_data is not perfectly divisible by the batch_size,
    the last batch may have fewer elements.

    Example Usage:
    ```python
    def data_generator():
        for i in range(10):
            yield i

    batch_size = 3
    for batch in minibatches_generator(data_generator(), batch_size):
        print(batch)
    ```
    """
    current_batch = []
    for data_point in inputs_data_generator:
        # print(f"Send data {data_point}")
        current_batch.append(data_point)
        if len(current_batch) == batch_size:
            yield current_batch
            current_batch = []

    # Yield any remaining data as a final batch
    if current_batch:
        yield current_batch



def extract_archive(archive_file, extract_to):
    """
    Extracts the contents of an archive file (zip, tar.gz, tar.bz2, tar.xz, or rar) to a specified directory.

    Args:
        archive_file (str): Path to the archive file.
        extract_to (str): Directory where the contents will be extracted.
    """

    try:
        if archive_file.endswith(".zip"):
            with zipfile.ZipFile(archive_file, "r") as zip_ref:
                zip_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_file, "r:*") as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith((".tar.bz2", ".tbz")):
            with tarfile.open(archive_file, "r:bz2") as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith(".tar.xz"):
            with tarfile.open(archive_file, "r:xz") as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        else:
            logging.warning(f"Unsupported archive format: {archive_file}")
    except Exception as e:
        logging.error(f"Error extracting {archive_file}: {str(e)}")


def get_color(
    cmap: str,
    data: Union[int, float],
    min_value: Union[int, float],
    max_value: Union[int, float],
) -> tuple[float, float, float]:
    """
    Get color value from a colormap based on given data.

    Args:
    - cmap: Colormap name or object.
    - data: Value to map to a color.
    - min_value: Minimum value of the data range.
    - max_value: Maximum value of the data range.

    Returns:
    - list: RGB color value based on the colormap and data.

    Notes:
    - Uses a specified colormap to map data values to color.
    - Returns a RGB color value in the range [0, 1].
    """
    if min_value == max_value:
        return (0.5, 0.5, 0.5)
    _cmap = matplotlib.colormaps[cmap]
    num_color = _cmap.N
    scaled_value = (data - min_value) / (max_value - min_value)
    color = _cmap(int(num_color * scaled_value))[:3]
    return color


def cmap_reverser(cmap: str, reverse: bool = False) -> str:
    """
    Reverses a colormap name if the 'reverse' flag is set to True.

    Args:
    - cmap (str): Name of the colormap.
    - reverse (bool): Flag indicating whether to reverse the colormap (default is False).

    Returns:
    - str: Reversed colormap name if 'reverse' is True, otherwise returns the original colormap name.
    """
    if reverse:
        if cmap.endswith("_r"):
            cmap = cmap.replace("_r", "")
        else:
            cmap += "_r"

    return cmap


def rescale_number(
    number: Union[int, float],
    min_value: Union[int, float],
    max_value: Union[int, float],
) -> float:
    """
    Rescales a number within a specified range to a value between 0 and 1.

    Args:
    - number (float): The number to be rescaled.
    - min_value (float): The minimum value of the range.
    - max_value (float): The maximum value of the range.

    Returns:
    - float: The rescaled value between 0 and 1.

    Raises:
    - ValueError: If min_value is greater than or equal to max_value.
    """
    # Ensure that min_value and max_value are valid.
    if min_value >= max_value:
        raise ArithmeticError("min_value must be less than max_value")

    # Calculate the rescaled value.
    rescaled_value = (number - min_value) / (max_value - min_value)

    # Ensure the result is within the [0, 1] range.
    return max(0, min(1, rescaled_value))


def count_and_sort_characters(input_string: str, characters):
    """
    Counts occurrences of specified characters in a string and sorts them based on counts.

    Args:
    - input_string (str): The input string to count characters from.
    - characters (list): List of characters to count in the input string.

    Returns:
    - dict: Dictionary containing character counts sorted in descending order.
    """
    char_count = {
        char: input_string.lower().count(char) for char in characters
    }

    sorted_count = dict(
        sorted(char_count.items(), key=lambda item: item[1], reverse=True)
    )
    sorted_count = {
        key: value for key, value in sorted_count.items() if value != 0
    }
    return sorted_count


def random_deduplicate(seq, score):
    """
    Deduplicates a sequence while preserving random scores for unique items.

    Args:
    - seq (numpy.array): Sequence array to deduplicate.
    - score (numpy.array): Array of scores corresponding to items in seq.

    Returns:
    - numpy.array: Unique items from seq.
    - numpy.array: Randomly chosen scores corresponding to unique items.
    """
    unique_items = np.unique(seq)
    unique_scores = [
        np.random.choice(score[seq == item]) for item in unique_items
    ]
    return np.array(unique_items), np.array(unique_scores)


def generate_strong_password(length=16):
    """
    Generate a strong random password.

    Args:
    - length (int): Length of the password (default is 16).

    Returns:
    - str: Strong password of the specified length.

    Raises:
    - ValueError: If the password length is not within the range of 16 to 64 characters.

    Notes:
    - Generates a strong password using a mix of ASCII letters, digits, and punctuation.
    - The password length should be between 16 and 64 characters.
    """
    if length < 16 or length > 64:
        raise ValueError(
            "Password length should be between 16 and 64 characters."
        )

    # Define the characters to use for generating the password
    password_characters = (
        string.ascii_letters + string.digits + '!#$%&*+-./:?@^_~'
    )

    # Generate the password using random characters from the defined set
    generated_password = "".join(
        random.choice(password_characters) for _ in range(length)
    )

    return generated_password


# modified from AlphaFold
@contextlib.contextmanager
def timing(msg: str):
    logging.info(f"Started {msg}")
    tic = time.perf_counter()
    yield
    toc = time.perf_counter()
    logging.info(f"Finished {msg} in {toc - tic:.3f} seconds")


__all__=[
    "run_command",
    'run_worker_thread_with_progress',
    'timing',
    'generate_strong_password',
    'random_deduplicate',
    'dirname_does_exist',
    'filepath_does_exists',
    'minibatches',
    'minibatches_generator',
    'extract_archive',
    'get_color',
    'cmap_reverser',
    'rescale_number',
    'count_and_sort_characters'
]