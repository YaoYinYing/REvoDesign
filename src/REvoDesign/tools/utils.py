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
    from itertools import pairwise as _pairwise  
except ImportError:
    def _pairwise(iterable: Iterable):
        a, b = itertools.tee(iterable)
        next(b, None)
        return zip(a, b)
pairwise: Callable[[Iterable], Iterable[Tuple]] = _pairwise
logging = ROOT_LOGGER.getChild(__name__)
def pairwise_loop(iterable: Iterable):
    seq = list(iterable)
    if not seq:
        return []
    return pairwise(seq + [seq[0]])
CLASS_ARGSLICE = slice(1, None)
def require_not_none(
    attribute_name: str,
    fallback_setup: Optional[Union[Callable[[], Any], str]] = None,
    error_type: type[Exception] = issues.UnexpectedWorkflowError
):
    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, attribute_name) or getattr(self, attribute_name) is None:
                if callable(fallback_setup):
                    logging.warning(
                        f"Method called {method.__name__}' with None attribute, "
                        f"falling back to setup by {fallback_setup.__name__}")
                    fallback_setup()
                elif isinstance(fallback_setup, str):
                    if not hasattr(self, fallback_setup):
                        raise AttributeError(f"Attribute '{fallback_setup}' not found in {self}")
                    fallback_setup_: Optional[Callable[[], Any]] = getattr(self, fallback_setup)
                    if not callable(fallback_setup_):
                        raise AttributeError(f"Attribute '{fallback_setup}' is not callable in {self}")
                    logging.warning(f"Method called {method.__name__}' with None attribute, "
                                    f"falling back to setup by {fallback_setup}")
                    fallback_setup_()
                else:
                    raise error_type(
                        f"The method '{method.__name__}' cannot be called because '{attribute_name}' is None."
                    )
            return method(self, *args, **kwargs)
        return wrapper
    return decorator
def require_installed(cls):
    orig_init = cls.__init__
    def __init__(self, *args, **kwargs):
        if not getattr(cls, 'installed', False):
            raise issues.UninstalledPackageError(f"Module '{self.name}' is not installed.")
        orig_init(self, *args, **kwargs)
    cls.__init__ = __init__
    return cls
def get_cited(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        if hasattr(self, 'cite') and callable(getattr(self, 'cite')):
            self.cite()
        return result
    return wrapper
def minibatches(inputs_data, batch_size):
    for start_idx in range(0, len(inputs_data), batch_size):
        if len(inputs_data[start_idx:]) > batch_size:
            excerpt = slice(start_idx, start_idx + batch_size)
            print(f"Send data in length: {len(inputs_data[excerpt])}")
            yield inputs_data[excerpt]
        else:
            print(f"Send final data in length: {len(inputs_data[start_idx:])}")
            yield inputs_data[start_idx:]
def minibatches_generator(inputs_data_generator, batch_size):
    current_batch = []
    for data_point in inputs_data_generator:
        current_batch.append(data_point)
        if len(current_batch) == batch_size:
            yield current_batch
            current_batch = []
    if current_batch:
        yield current_batch
def extract_archive(archive_file: str, extract_to: str):
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
    if min_value == max_value:
        return (0.5, 0.5, 0.5)
    _cmap = matplotlib.colormaps[cmap]
    num_color = _cmap.N
    scaled_value = (data - min_value) / (max_value - min_value)
    color = _cmap(int(num_color * scaled_value))[:3]
    return color
def cmap_reverser(cmap: str, reverse: bool = False) -> str:
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
    if min_value >= max_value:
        raise ArithmeticError("min_value must be less than max_value")
    rescaled_value = (number - min_value) / (max_value - min_value)
    return max(0, min(1, rescaled_value))
def count_and_sort_characters(input_string: str, characters):
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
    unique_items = np.unique(seq)
    unique_scores = [
        np.random.choice(score[seq == item]) for item in unique_items
    ]
    return np.array(unique_items), np.array(unique_scores)
def generate_strong_password(length=16):
    if length < 16 or length > 64:
        raise ValueError(
            "Password length should be between 16 and 64 characters."
        )
    password_characters = (
        string.ascii_letters + string.digits + '!
    )
    generated_password = "".join(
        random.choice(password_characters) for _ in range(length)
    )
    return generated_password
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
def device_picker() -> List[str]:
    device_list = ['cpu']
    if is_package_installed('torch'):
        import torch
        try:
            if torch.cuda.is_available():
                cuda_device_count = torch.cuda.device_count()
                if cuda_device_count >= 1:
                    device_list.extend([f'cuda:{i}' for i in range(cuda_device_count)])
            if torch.backends.mps.is_available() and torch.backends.mps.is_built():
                device_list.append('mps')
        except Exception as e:
            print(f"Error checking PyTorch devices: {e}")
    elif is_package_installed('tensorflow'):
        import tensorflow as tf
        try:
            if tf.config.list_physical_devices('GPU'):
                device_list.append('gpu')
        except Exception as e:
            print(f"Error checking TensorFlow devices: {e}")
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