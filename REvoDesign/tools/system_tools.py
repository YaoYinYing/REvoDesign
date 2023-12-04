from absl import logging
import importlib
import platform


def get_system_info():
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


OS_TYPE, OS_INFO = get_system_info()
PY_VERSION=platform.python_version()


def is_package_installed(package):
    package_loader = importlib.find_loader(package)
    return package_loader is not None

def get_client_info():

    import os
    import socket
    from REvoDesign.tools.pymol_utils import PYMOL_VERSION, PYMOL_BUILD
    from REvoDesign.tools.customized_widgets import PYQT_VERSION_STR

    try:
        client_ip=socket.gethostbyname_ex(socket.gethostname())[2]
        # pop the loop
        client_ip.remove('127.0.0.1')
    except Exception as e:
        logging.error(f'Failed to fetch client ip: {e}')
        client_ip=[]

    client_info = {
            # node and login
            'node': OS_INFO.node,
            'user': os.getlogin(),

            # os and march
            'os': OS_INFO.system,
            'os_build':OS_INFO.version,
            'machine_arch':OS_INFO.machine,

            # python and pymol
            'pymol_version': PYMOL_VERSION,
            'pymol_build': PYMOL_BUILD,
            'python_version': PY_VERSION,

            # network
            'ip': client_ip,

            # qt
            'qt_ver': PYQT_VERSION_STR
        }
    return client_info