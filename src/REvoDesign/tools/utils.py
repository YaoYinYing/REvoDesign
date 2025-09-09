'''
Orphaneous functions for REvoDesign
'''

import contextlib
import itertools
import random
import string
import tarfile
import time
import zipfile
from functools import wraps
from typing import (Any, Callable, Iterable, List, Literal, Optional, Tuple,
                    Union)

import matplotlib
import numpy as np

from REvoDesign import issues
from REvoDesign.logger import ROOT_LOGGER

from ..bootstrap.set_config import is_package_installed
from .package_manager import run_command, run_worker_thread_with_progress

try:
    from itertools import pairwise as _pairwise  # type: ignore
except ImportError:

    def _pairwise(iterable: Iterable):
        """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
        a, b = itertools.tee(iterable)
        next(b, None)
        return zip(a, b)


pairwise: Callable[[Iterable], Iterable[Tuple]] = _pairwise

logging = ROOT_LOGGER.getChild(__name__)


def pairwise_loop(iterable: Iterable):
    """
    Generate a looped pairwise iterable from the input iterable.

    This function takes an iterable as input and returns a list of tuples,
    where each tuple contains a pair of consecutive elements from the iterable.
    The last element is paired with the first element to form a loop structure.

    Parameters:
    iterable: Iterable - The input iterable used to generate the looped pairwise iterable.

    Returns:
    list - A list of tuples, each containing a pair of consecutive elements.
            The last element is paired with the first element.
    """
    # Convert iterable to a list to support indexing and concatenation
    seq = list(iterable)
    # Handle empty iterable case
    if not seq:
        return []
    # Add the first element to the end of the list to form a loop structure and generate pairwise combinations
    return pairwise(seq + [seq[0]])


# a slice of arguments to be passed to a class
CLASS_ARGSLICE = slice(1, None)


def require_not_none(
    attribute_name: str,
    fallback_setup: Optional[Union[Callable[[], Any], str]] = None,
    error_type: type[Exception] = issues.UnexpectedWorkflowError
):
    """
    Decorator factory to ensure a specific attribute of the instance is not None before the method is called.

    Args:
        attribute_name (str): Name of the attribute to check.
        fallback_setup (callable): Function to call if the attribute is None. Defaults to None.
        error_type (type): Exception type to raise if the attribute is None and no fallback.
            Defaults to issues.UnexpectedWorkflowError.
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            # Check if the attribute exists and is not None
            if not hasattr(self, attribute_name) or getattr(self, attribute_name) is None:
                # no fallback setup, raise error
                if callable(fallback_setup):
                    logging.warning(
                        f"Method called {method.__name__}' with None attribute, "
                        f"falling back to setup by {fallback_setup.__name__}")
                    fallback_setup()
                # fallback setup is a string, try call the method with the same name
                elif isinstance(fallback_setup, str):
                    if not hasattr(self, fallback_setup):
                        raise AttributeError(f"Attribute '{fallback_setup}' not found in {self}")
                    fallback_setup_: Optional[Callable[[], Any]] = getattr(self, fallback_setup)
                    # not a callable, raise error
                    if not callable(fallback_setup_):
                        raise AttributeError(f"Attribute '{fallback_setup}' is not callable in {self}")
                    logging.warning(f"Method called {method.__name__}' with None attribute, "
                                    f"falling back to setup by {fallback_setup}")
                    fallback_setup_()
                else:
                    # no fallback setup, raise error
                    raise error_type(
                        f"The method '{method.__name__}' cannot be called because '{attribute_name}' is None."
                    )

            # Call the original method
            return method(self, *args, **kwargs)

        return wrapper

    return decorator


def require_installed(cls):
    """
    Decorator to enforce that the `installed` attribute of a class is True.
    Raises an error if an instance is created with `installed` set to False.
    """
    orig_init = cls.__init__

    def __init__(self, *args, **kwargs):

        if not getattr(cls, 'installed', False):
            raise issues.UninstalledPackageError(f"Module '{self.name}' is not installed.")

        orig_init(self, *args, **kwargs)

    cls.__init__ = __init__
    return cls


def get_cited(method):
    """
    Decorator to call `self.cite()` after executing `self.process()`.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        if hasattr(self, 'cite') and callable(getattr(self, 'cite')):
            self.cite()
        return result

    return wrapper


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
            print(f"Send data in length: {len(inputs_data[excerpt])}")
            yield inputs_data[excerpt]
        else:
            print(f"Send final data in length: {len(inputs_data[start_idx:])}")
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


def extract_archive(archive_file: str, extract_to: str):
    """
    Extracts the contents of an archive file (zip, tar.gz, tar.bz2, tar.xz, or rar) to a specified directory.

    Args:
        archive_file (str): Path to the archive file.
        extract_to (str): Directory where the contents will be extracted.
    """

    try:
        with timing(f'extracting {archive_file} to {extract_to}'):
            if archive_file.endswith(".zip"):
                with zipfile.ZipFile(archive_file, "r") as zip_ref:
                    zip_ref.extractall(extract_to)

            elif archive_file.endswith(".tar"):
                with tarfile.open(archive_file, "r:") as tar_ref:
                    tar_ref.extractall(extract_to)

            elif archive_file.endswith((".tar.gz", ".tgz")):
                with tarfile.open(archive_file, "r:*") as tar_ref:
                    tar_ref.extractall(extract_to)

            elif archive_file.endswith((".tar.bz2", ".tbz")):
                with tarfile.open(archive_file, "r:bz2") as tar_ref:
                    tar_ref.extractall(extract_to)

            elif archive_file.endswith(".tar.xz"):
                with tarfile.open(archive_file, "r:xz") as tar_ref:
                    tar_ref.extractall(extract_to)

            else:
                raise ValueError(f"Unsupported archive format: {archive_file}")
    except Exception as e:
        logging.error(f"Error extracting {archive_file}: {str(e)}")
        raise ValueError(f"Failed to extract {archive_file}: {e}") from e


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
    if not reverse:
        return cmap

    return cmap.replace("_r", "") if cmap.endswith("_r") else cmap + "_r"


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
def timing(msg: str, unit: Literal['ms', 'sec', 'min', 'hr'] = 'sec'):
    logging.info(f"Started {msg}")
    tic = time.perf_counter()
    yield
    toc = time.perf_counter()
    tic_toc = toc - tic
    if unit == 'sec':
        logging.info(f"Finished {msg} in {tic_toc:.3f} seconds")
    elif unit == 'min':
        logging.info(f"Finished {msg} in {tic_toc / 60:.3f} minutes")
    elif unit == 'hr':
        logging.info(f"Finished {msg} in {tic_toc / 3600:.3f} hours")
    elif unit == 'ms':
        logging.info(f"Finished {msg} in {tic_toc * 1000:.3f} milliseconds")

# TODO: support JAX and TensorFlow; need refactor


def device_picker() -> List[str]:
    """
    Detects and returns a list of available devices for deep learning frameworks.

    This function checks for the availability of GPU or specialized hardware
    (like MPS on macOS) using PyTorch or TensorFlow. If no compatible devices are found,
    it defaults to 'cpu'.

    Returns:
        List[str]: A list of available device strings (e.g., ['cuda:0', 'mps', 'gpu', 'cpu']).
    """

    device_list = ['cpu']

    # Check if PyTorch is installed and configure devices accordingly
    if is_package_installed('torch'):
        import torch

        try:
            # Add CUDA devices if available
            if torch.cuda.is_available():
                cuda_device_count = torch.cuda.device_count()
                if cuda_device_count >= 1:
                    device_list.extend([f'cuda:{i}' for i in range(cuda_device_count)])

            # Add MPS device if available and built into PyTorch
            if torch.backends.mps.is_available() and torch.backends.mps.is_built():
                device_list.append('mps')
        except Exception as e:
            print(f"Error checking PyTorch devices: {e}")

    # Check if TensorFlow is installed and configure devices accordingly
    elif is_package_installed('tensorflow'):
        import tensorflow as tf

        try:
            # Add GPU device if available
            if tf.config.list_physical_devices('GPU'):
                device_list.append('gpu')
        except Exception as e:
            print(f"Error checking TensorFlow devices: {e}")

    # Default to CPU if no other devices are available
    if not device_list:
        device_list.append('cpu')

    return device_list


__all__ = [
    "run_command",
    'run_worker_thread_with_progress',
    'timing',
    'generate_strong_password',
    'random_deduplicate',
    'minibatches',
    'minibatches_generator',
    'extract_archive',
    'get_color',
    'cmap_reverser',
    'rescale_number',
    'count_and_sort_characters',
    'device_picker',
    'pairwise'
]
