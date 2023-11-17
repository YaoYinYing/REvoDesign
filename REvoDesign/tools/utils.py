import contextlib
import os
from absl import logging
import time

from REvoDesign.tools.customized_widgets import WorkerThread, refresh_window
from REvoDesign.tools.system_tools import is_package_installed


WITH_COLABDESIGN = is_package_installed('colabdesign')


def run_command(excutable='python', command_list=[]):
    import sys
    import subprocess
    from absl import logging

    if excutable == 'python':
        python_exe = os.path.realpath(sys.executable)
        command_list = [python_exe] + command_list

    while '' in command_list:
        command_list.remove('')

    if not command_list:
        return

    logging.debug(command_list)

    result = subprocess.run(
        command_list,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

    return result


def dirname_does_exist(fp):
    return os.path.exists(os.path.dirname(fp))


def filepath_does_exists(fp):
    return os.path.exists(fp)


def suppress_print(func):
    def wrapper(*args, **kwargs):
        with contextlib.redirect_stdout(open(os.devnull, 'w')):
            with contextlib.redirect_stderr(open(os.devnull, 'w')):
                result = func(*args, **kwargs)
        return result

    return wrapper


def minibatches(inputs_data, batch_size):
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


def run_worker_thread_with_progress(
    worker_function, progress_bar=None, *args, **kwargs
):
    if progress_bar:
        progress_bar.setRange(0, 0)

    work_thread = WorkerThread(worker_function, args=args, kwargs=kwargs)
    work_thread.start()

    while not work_thread.isFinished():
        refresh_window()
        time.sleep(0.001)

    if progress_bar:
        progress_bar.setRange(0, 1)

    result = work_thread.handle_result()
    return result[0] if result else None


def extract_archive(archive_file, extract_to):
    """
    Extracts the contents of an archive file (zip, tar.gz, tar.bz2, tar.xz, or rar) to a specified directory.

    Args:
        archive_file (str): Path to the archive file.
        extract_to (str): Directory where the contents will be extracted.
    """

    try:
        import tarfile

        if archive_file.endswith(".zip"):
            import zipfile

            with zipfile.ZipFile(archive_file, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_file, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith((".tar.bz2", ".tbz")):
            with tarfile.open(archive_file, 'r:bz2') as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith(".tar.xz"):
            with tarfile.open(archive_file, 'r:xz') as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        else:
            logging.warning(f"Unsupported archive format: {archive_file}")
    except Exception as e:
        logging.error(f"Error extracting {archive_file}: {str(e)}")


def get_color(cmap, data, min_value, max_value):
    import matplotlib

    if min_value == max_value:
        return [0.5, 0.5, 0.5]
    _cmap = matplotlib.colormaps[cmap]
    num_color = _cmap.N
    scaled_value = (data - min_value) / (max_value - min_value)
    color = _cmap(int(num_color * scaled_value))[:3]
    return color


def cmap_reverser(cmap, reverse=False):
    if reverse:
        if cmap.endswith('_r'):
            cmap = cmap.replace('_r', '')
        else:
            cmap += '_r'

    return cmap


def rescale_number(number, min_value, max_value):
    # Ensure that min_value and max_value are valid.
    if min_value >= max_value:
        raise ValueError("min_value must be less than max_value")

    # Calculate the rescaled value.
    rescaled_value = (number - min_value) / (max_value - min_value)

    # Ensure the result is within the [0, 1] range.
    return max(0, min(1, rescaled_value))


def count_and_sort_characters(input_string, characters):
    char_count = {char: input_string.lower().count(char) for char in characters}
    
    sorted_count = dict(sorted(char_count.items(), key=lambda item: item[1], reverse=True))
    sorted_count = {key: value for key, value in sorted_count.items() if value != 0}
    return sorted_count


def random_deduplicate(seq, score):
    import numpy as np
    unique_items = np.unique(seq)
    unique_scores = [np.random.choice(score[seq == item]) for item in unique_items]
    return np.array(unique_items), np.array(unique_scores)