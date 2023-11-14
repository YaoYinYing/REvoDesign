import os
from absl import logging
import importlib


def num_processors():
    return sorted([x for x in range(1, os.cpu_count() + 1)], reverse=True)


def determine_system():
    import platform

    os_info = platform.uname()
    os_name = os_info.system

    if os_name == 'Darwin':
        is_arm_macos = "ARM64" in os_info.version
        is_recognized_as_x86 = os_info.machine == 'x86_64'

        logging.warning(f'Does it ARMed? {is_arm_macos}')
        logging.warning(f'Does it Rosetta-ed? {is_recognized_as_x86}')

        if is_arm_macos and is_recognized_as_x86:
            logging.warning(
                'Oops! You are in Rosetta-translated PyMOL bundle from official channel. '
                'This might limit the performance of joblib, causing MutantVisualizer slower.'
            )
            os_name += '_Rosetta'
    return os_name, os_info


OS_TYPE, OS_INFO = determine_system()


def is_package_installed(package):
    package_loader = importlib.find_loader(package)
    return package_loader is not None
