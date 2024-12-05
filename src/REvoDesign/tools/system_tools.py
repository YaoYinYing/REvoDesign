'''
System info collector
'''

import platform
import warnings

from immutabledict import immutabledict

from REvoDesign import issues
import platform

from .package_manager import issue_collection


def check_mac_rosetta2():
    """
    Check if the current environment is running on an Apple Silicon Mac with Rosetta 2.

    This function first checks if the current operating system is macOS. If not, it returns immediately.
    It then determines if the machine is an ARM-based Mac and whether it is recognized as an x86_64 architecture.
    If both conditions are met, a warning is issued indicating that the environment is using Rosetta 2, which may impact performance.

    Returns:
        None
    """

    if not platform.system() == "Darwin":
        return
    
    # Determine if the current machine is an ARM-based Mac
    is_arm_macos = "ARM64" in platform.uname().version
    # Determine if the current machine is recognized as x86_64
    is_recognized_as_x86 = platform.machine() == "x86_64"

    print(f"Does it ARMed? {is_arm_macos}")
    print(f"Does it Rosetta-ed? {is_recognized_as_x86}")

    if not (is_arm_macos and is_recognized_as_x86):
        return

    # Issue a warning if the machine is running under Rosetta 2
    warnings.warn(
        issues.AppleSiliconRosetta2Warning(
            "Oops! You are in Rosetta-translated PyMOL bundle from official channel. "
            "This might limit the performance of joblib, causing MutantVisualizer slower."
        )
    )


class CLIENT_INFO:
    '''
    A reduced client information class.
    '''
    
    def __init__(self):
        SYSTEM_INFO_DICT=immutabledict(issue_collection())

        self.node: str = SYSTEM_INFO_DICT['Platform::Hostname']
        self.user: str = SYSTEM_INFO_DICT['User::Username']
        self.os: str = SYSTEM_INFO_DICT['Platform::OS']
        self.os_build: str = SYSTEM_INFO_DICT['Platform::Version']
        self.machine_arch: str = SYSTEM_INFO_DICT['Platform::Machine']
        self.revodesign_version: str = SYSTEM_INFO_DICT['REvoDesign::Version']
        self.pymol_version: str = SYSTEM_INFO_DICT['PyMOL::Version']
        self.pymol_build: str = SYSTEM_INFO_DICT['PyMOL::Build']
        self.python_version: str = SYSTEM_INFO_DICT['Python::Version']
        self.ip: list = SYSTEM_INFO_DICT['Network::IP']
        self.qt_ver: str = SYSTEM_INFO_DICT['PyQt::Version']
        self.OS_TYPE: str = f"{SYSTEM_INFO_DICT['Platform::OS']}_{SYSTEM_INFO_DICT['Platform::Machine']}"
        self.is_translated_arm_mac: bool = SYSTEM_INFO_DICT['Platform::IsRosettaTranlated']
        self.nproc: int = SYSTEM_INFO_DICT['Platform::CPU::Num']
