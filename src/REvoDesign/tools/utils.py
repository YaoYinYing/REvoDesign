'''
Orphaneous functions for REvoDesign
'''
from __future__ import annotations

import contextlib
import importlib
import inspect
import itertools
import random
import string
import sys
import tarfile
import time
import zipfile
from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any, Literal, cast

from typing_extensions import ParamSpec, TypeVar


import matplotlib
import numpy as np
import pandas as pd

from REvoDesign import issues
from REvoDesign.logger import ROOT_LOGGER

from ..bootstrap.set_config import is_package_installed
from .package_manager import run_command, run_worker_thread_with_progress

from itertools import pairwise

logging = ROOT_LOGGER.getChild(__name__)


def resolve_dotted_function(dotted_str: str) -> Callable:
    """
    Resolves a dotted string into a callable Python object (function or method).

    The input string must follow one of these formats:

    - `<module_path>:<function_name>` (for module-level functions)
      Example: `"my_module.submodule:my_function"`

    - `<module_path>:<class_name>.<method_name>` (for class methods)
      Example: `"my_module.submodule:MyClass.my_method"`

    Args:
        dotted_str (str): A string representing the fully qualified path to a callable.

    Returns:
        Callable: The resolved callable function or method.

    Raises:
        issues.InvalidInputError: If the string does not contain a colon (`:`) or does not follow the expected format.
        AttributeError: If the specified module, class, or function does not exist.
    """
    if ":" not in dotted_str:
        raise issues.InvalidInputError(
            'dotted function expect an input string in pattern <import-path>:(<class>.)<function>',
            f'not `{dotted_str}`'
        )
    module_path, func_name = dotted_str.rsplit(":", 1)
    module = importlib.import_module(module_path)
    if "." not in func_name:
        logging.debug(f'Dotted function resolving `{func_name}` from {module}')
        return getattr(module, func_name)
    # maybe a class method?

    _class_name, _func_name = func_name.rsplit(".")
    logging.debug(f'Dotted function resolving `{_class_name}.{_func_name}` from {module}')
    _class = getattr(module, _class_name)
    return getattr(_class, _func_name)


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
    fallback_setup: Callable[[], Any] | str | None = None,
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
                    fallback_setup_: Callable[[], Any] | None = getattr(self, fallback_setup)
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


MethodKind = Literal["InstanceMethod", "ClassMethod", "StaticMethod", "Function"]


def inspect_method_types(method: Callable) -> MethodKind:
    """
    Inspect the type of a callable: instance method, class method,
    static method, or plain function.

    Args:
        method (Callable): The callable to inspect.

    Returns:
        Literal['InstanceMethod', 'ClassMethod', 'StaticMethod', 'Function']:
        The inferred kind of method.

    Raises:
        TypeError: If the method type cannot be determined or the object
        is not callable.
    """
    if not callable(method):
        raise issues.UnexpectedWorkflowError(f"Cannot inspect method type for non-callable {method!r}")

    # --- 1. Bound methods: have a non-None __self__ -------------------------
    #   obj.method      -> bound instance method ( __self__ is instance )
    #   cls.method      -> bound class method    ( __self__ is class )
    if hasattr(method, "__self__") and getattr(method, "__self__", None) is not None:
        self_obj = method.__self__  # type: ignore[attr-defined]
        # Bound to a class -> classmethod
        if isinstance(self_obj, type):
            logging.debug(f'{method!r} is a classmethod bound to {self_obj!r}')
            return "ClassMethod"
        logging.debug(f'{method!r} is an instancemethod bound to {self_obj!r}')
        # Bound to an instance -> instance method
        return "InstanceMethod"

    # --- 2. Unbound functions (no binding) -----------------------------------
    # At this point, typical Python methods accessed from the class are plain
    # function objects (unbound). We must check how they are stored on the class.
    if inspect.isfunction(method):
        qualname = getattr(method, "__qualname__", "")
        logging.debug(f"Checking unbound function {method}: {getattr(method, '__module__', '')!r}")

        # Try to resolve the owning class from qualname: "MyClass.method"
        if "." in qualname:
            owner_path, func_name = qualname.rsplit(".", 1)

            owner_cls = None
            module = inspect.getmodule(method)
            if module is not None:
                obj = module
                # Walk the dotted path "Outer.Inner" etc.
                for part in owner_path.split("."):
                    if not hasattr(obj, part):
                        obj = None
                        break
                    obj = getattr(obj, part)
                if isinstance(obj, type):
                    owner_cls = obj

            if owner_cls is not None:
                # Look at the raw attribute on the class dict
                attr = owner_cls.__dict__.get(func_name)
                # Static method is stored as a staticmethod descriptor
                if isinstance(attr, staticmethod):
                    logging.debug(f'{method!r} is a staticmethod on {owner_cls!r}')
                    return "StaticMethod"
                # A normal "def" on the class body: unbound instance method
                if inspect.isfunction(attr):
                    logging.debug(f'{method!r} is a function on {owner_cls!r}')
                    return "Function"

            # Fallback: dotted qualname but class not resolvable
            # (e.g. local classes with '<locals>' in qualname).
            # In your semantics we still treat this as a static-style method.
            logging.debug(f'{method!r} is a dotted qualname but class is not resolvable')
            return "StaticMethod"

        # No dot in qualname: a plain top-level function
        logging.debug(f'{method!r} is a plain top-level function')
        return "Function"

    # --- 3. Rare cases: method-like objects not covered above ---------------
    if inspect.ismethod(method):
        # This branch is mostly for odd cases / builtins.
        self_obj = method.__self__
        if isinstance(self_obj, type):
            logging.debug(f'{method!r} is a method-like classmethod object')
            return "ClassMethod"
        logging.debug(f'{method!r} is a method-like instancemethod object')
        return "InstanceMethod"

    # --- 4. Give up ----------------------------------------------------------
    logging.error(f"Giving up for inpection on method type! {method!r}")
    raise TypeError(f"Cannot inspect method type for {method!r}")


def get_owner_class_from_static(func):
    """
    Best-effort: get the class that owns a staticmethod given `MyClass.static`.

    This works for normal top-level classes, but is not guaranteed for all cases.
    """
    logging.debug(f"Getting owner class from static method {func!r}")
    if not inspect.isfunction(func):
        raise TypeError("Expected a function object (e.g. MyClass.static).")

    # Example: "MyClass.static" or "Outer.Inner.static"
    qualname = func.__qualname__

    # Strip any '<locals>' part for nested definitions.
    qualname = qualname.split('.<locals>.', 1)[0]

    # Drop the last component (the function name itself).
    # e.g. "MyClass.static" -> "MyClass"
    #      "Outer.Inner.static" -> "Outer.Inner"
    parts = qualname.split('.')
    if len(parts) < 2:
        raise LookupError(f"Cannot infer an owning class from qualname {qualname!r} ({func.__qualname__!r})")

    class_path = parts[:-1]  # everything except the function name
    module = sys.modules.get(func.__module__)
    if module is None:
        raise LookupError(f"Module {func.__module__!r} not found in sys.modules")

    # Walk down the dotted path in the module namespace.
    obj = module
    for name in class_path:
        try:
            obj = getattr(obj, name)
        except AttributeError as exc:
            raise LookupError(f"Failed to resolve {'.'.join(class_path)!r} in module {module.__name__}") from exc

    if not isinstance(obj, type):
        raise LookupError(f"Resolved {obj!r} is not a class")

    return obj

# parameter specification for the original method
P = ParamSpec("P")

# return type for the original method
R = TypeVar("R")

# Annotate the decorator with the original method's parameters and return type
def get_cited(method: Callable[P, R]) -> Callable[P, R]:
    """
    A decorator that adds citation functionality to a method, automatically calling the appropriate cite() method.
    
    This decorator determines which object's cite() method should be called based on the method type 
    (class method, instance method, static method, or function) and automatically records citation information.
    
    Args:
        method: The method to be decorated, can be a class method, instance method, static method, or regular function
        
    Returns:
        Returns a wrapped method that calls the appropriate cite() method after executing the original method
    """
    from ..citations import CitableModuleAbstract

    def _cite_for_cls(cls_or_obj: type[CitableModuleAbstract] | CitableModuleAbstract) -> None:
        """
        Calls the cite() method on the given class or object.
        
        Args:
            cls_or_obj: A class or instance object of type CitableModuleAbstract
        """
        try:
            if not (hasattr(cls_or_obj, "cite") and callable(getattr(cls_or_obj, "cite"))):
                name = getattr(cls_or_obj, "__name__", type(cls_or_obj).__name__)
                raise TypeError(f"{name} is not citable or missing cite()")
            cls_or_obj.cite()
        except Exception as e:
            logging.warning(f"Ignore cite() error: {e}")

    # Determine method type and log it
    guessed_method_type = inspect_method_types(method=cast(Callable[..., Any], method))
    logging.warning(f"Guessed method type: {method!r}: {guessed_method_type}")

    # broadcast typing from the original method to the wrapper
    def _impl(*args: P.args, **kwargs: P.kwargs) -> R:
        """
        Actual decorator implementation function.
        
        Executes the original method, then calls the appropriate cite() method based on the method type.
        """
        result = method(*args, **kwargs)

        try:
            # Determine how to call cite() based on method type
            if guessed_method_type in ("ClassMethod", "InstanceMethod"):
                if args:
                    _cite_for_cls(cast(type[CitableModuleAbstract] | CitableModuleAbstract, args[0]))

            elif guessed_method_type == "StaticMethod":
                cls = get_owner_class_from_static(cast(Callable[..., Any], method))
                _cite_for_cls(cls)

            elif guessed_method_type == "Function":
                anonymous = CitableModuleAbstract.get_citable_class(func=cast(Callable[..., Any], method))
                anonymous().cite()

            else:
                raise issues.InternalError(f"Cannot apply get_cited decorator to {method!r}")

        except Exception as e:
            logging.debug(f"Failed to cite {method!r} due to {e}")

        return result

    wrapped = wraps(method)(_impl)
    return cast(Callable[P, R], wrapped)

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
    data: int | float,
    min_value: int | float,
    max_value: int | float,
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
    number: int | float,
    min_value: int | float,
    max_value: int | float,
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


def convert_residue_ranges(
        residue_ranges: str,

        res_prefix: str = "",
        resr_prefix: str = "",

        res_suffix: str = "",
        resr_suffix: str = "",

        connector: str = ' | ',
) -> str:
    '''
    Converts a string of residue ranges into a string of residue segments.
    Example:
    >>> convert_residue_ranges('1-5+7-9+10-12+13', res_prefix='r ', resr_prefix='ri ', connector=' | ')
    ri 1-5 | r 7-9 | r 10-12 | r 13


    Args:
        residue_ranges: String of residue ranges.
        res_prefix: Prefix to add to each residue.
        resr_prefix: Prefix to add to each residue range.
        res_suffix: Suffix to add to each residue.
        resr_suffix: Suffix to add to each residue range.
        connector: Connector to use between each residue segment.
    Returns:
        String of residue segments.

    '''

    converted = []
    for residue_seg in residue_ranges.split('+'):
        if '-' in residue_seg:
            converted.append(resr_prefix + residue_seg + resr_suffix)
        else:
            converted.append(res_prefix + residue_seg + res_suffix)

    converted_str = connector.join(converted)
    logging.info(f"Converted residue ranges to segments: {converted_str}")

    return converted_str


# TODO: support JAX and TensorFlow; need refactor

def device_picker() -> list[str]:
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


def xvg2df(xvg_file: str) -> pd.DataFrame:
    """
    Converts an xvg file to a pandas dataframe.

    Args:
        xvg_file (str): Path to the xvg file.

    Returns:
        pd.DataFrame: DataFrame containing the data from the xvg file.
    """
    data = np.loadtxt(xvg_file, comments=['#', '@'])
    df = pd.DataFrame(data=data)
    return df


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
