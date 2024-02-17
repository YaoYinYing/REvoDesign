from dataclasses import asdict, dataclass
import os
import platform

from REvoDesign.tools.logger import logging as logger

logging = logger.getChild(__name__)


def get_system_info(os_info: platform.uname_result):
    """
    Function: get_system_info
    Usage: os_name, os_info = get_system_info()

    This function retrieves system information using the platform module.

    Returns:
    - os_name (str): Name of the operating system
    """
    os_name = os_info.system

    if os_name == 'Darwin':
        is_arm_macos = "ARM64" in os_info.version
        is_recognized_as_x86 = os_info.machine == 'x86_64'

        logging.debug(f'Does it ARMed? {is_arm_macos}')
        logging.debug(f'Does it Rosetta-ed? {is_recognized_as_x86}')

        if is_arm_macos and is_recognized_as_x86:
            logging.warning(
                'Oops! You are in Rosetta-translated PyMOL bundle from official channel. '
                'This might limit the performance of joblib, causing MutantVisualizer slower.'
            )
            os_name += '_Rosetta'
    return os_name


@dataclass
class CLIENT_INFO:
    OS_INFO: platform.uname_result = platform.uname()
    node: str = None
    user: str = None
    os: str = None
    os_build: str = None
    machine_arch: str = None
    revodesign_version: str = None
    pymol_version: str = None
    pymol_build: str = None
    python_version: str = None
    ip: list = None
    qt_ver: str = None
    OS_TYPE: str = None
    is_translated_arm_mac: bool = None

    def __post_init__(self):
        import os
        import socket
        from REvoDesign.__version__ import __version__
        from REvoDesign.tools.pymol_utils import PYMOL_VERSION, PYMOL_BUILD
        from REvoDesign.tools.customized_widgets import PYQT_VERSION_STR

        self.node: str = self.OS_INFO.node
        try:
            user: str = os.getlogin()
        except OSError as e:
            logging.warning(
                f'Failed to fetch user, maybe in CI runners? \nError: {e}'
            )
            user: str = 'CI'
        self.user: str = user
        self.os: str = self.OS_INFO.system
        self.os_build: str = self.OS_INFO.version
        self.machine_arch: str = self.OS_INFO.machine
        self.revodesign_version: str = __version__
        self.pymol_version = PYMOL_VERSION
        self.pymol_build = PYMOL_BUILD
        self.python_version: str = platform.python_version()
        self.OS_TYPE: str = get_system_info(os_info=self.OS_INFO)
        self.is_translated_arm_mac: bool = 'Rosetta' in self.OS_TYPE

        try:
            self.ip = socket.gethostbyname_ex(socket.gethostname())[2]
            if '127.0.0.1' in self.ip:
                self.ip.remove('127.0.0.1')
        except Exception as e:
            logging.error(f'Failed to fetch client ip: {e}')
            self.ip = []
        self.qt_ver = PYQT_VERSION_STR


# if __name__ == '__main__':
#     client_info=CLIENT_INFO()
#     print(client_info.__dict__)
