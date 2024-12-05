'''
System info collector
'''

import platform
import warnings
from dataclasses import dataclass

from immutabledict import immutabledict

from REvoDesign import issues

from .package_manager import issue_collection

SYSTEM_INFO_DICT=immutabledict(issue_collection())


def check_mac_rosetta2():

    if SYSTEM_INFO_DICT['Platform::OS'] == "Darwin":
        is_arm_macos = "ARM64" in SYSTEM_INFO_DICT['Platform::Version']
        is_recognized_as_x86 = SYSTEM_INFO_DICT['Platform::Machine'] == "x86_64"

        print(f"Does it ARMed? {is_arm_macos}")
        print(f"Does it Rosetta-ed? {is_recognized_as_x86}")

        if SYSTEM_INFO_DICT['Platform::IsRosettaTranlated']:
            warnings.warn(
                issues.AppleSiliconRosetta2Warning(
                    "Oops! You are in Rosetta-translated PyMOL bundle from official channel. "
                    "This might limit the performance of joblib, causing MutantVisualizer slower."
                )
            )
    return


@dataclass
class CLIENT_INFO:
    node: str = SYSTEM_INFO_DICT['Platform::Hostname']
    user: str = SYSTEM_INFO_DICT['User::Username']
    os: str = SYSTEM_INFO_DICT['Platform::OS']
    os_build: str = SYSTEM_INFO_DICT['Platform::Version']
    machine_arch: str = SYSTEM_INFO_DICT['Platform::Machine']
    revodesign_version: str = SYSTEM_INFO_DICT['REvoDesign::Version']
    pymol_version: str = SYSTEM_INFO_DICT['PyMOL::Version']
    pymol_build: str = SYSTEM_INFO_DICT['PyMOL::Build']
    python_version: str = SYSTEM_INFO_DICT['Python::Version']
    ip: list = SYSTEM_INFO_DICT['Network::IP']
    qt_ver: str = SYSTEM_INFO_DICT['PyQt::Version']
    OS_TYPE: str = f"{SYSTEM_INFO_DICT['Platform::OS']}_{SYSTEM_INFO_DICT['Platform::Machine']}"
    is_translated_arm_mac: bool = SYSTEM_INFO_DICT['Platform::IsRosettaTranlated']
    nproc: int = SYSTEM_INFO_DICT['Platform::CPU::Num']