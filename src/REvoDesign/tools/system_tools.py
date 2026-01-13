"""
System info collector
"""

import platform
import warnings
from typing import Any, TypedDict, cast

from immutabledict import immutabledict

from .. import issues
from ..basic import SingletonAbstract
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


class SystemInfoReduced(SingletonAbstract):
    """
    A singleton class that provides system information.
    """

    def singleton_init(self):
        self.info: immutabledict = immutabledict(issue_collection(network=False))
        self.initialized = True


CLIENT_INFO_FIELD_MAP = immutabledict(
    {
        "node": "Platform::Hostname",
        "user": "User::Username",
        "os": "Platform::OS",
        "os_build": "Platform::Version",
        "machine_arch": "Platform::Machine",
        "revodesign_version": "REvoDesign::Version",
        "pymol_version": "PyMOL::Version",
        "pymol_build": "PyMOL::Build",
        "python_version": "Python::Version",
        "ip": "Network::IP",
        "qt_ver": "PyQt::Version",
        "is_translated_arm_mac": "Platform::IsRosettaTranlated",
        "nproc": "Platform::CPU::Num",
    }
)


class CLIENT_INFO(TypedDict):
    node: str
    user: str
    os: str
    os_build: str
    machine_arch: str
    revodesign_version: str
    pymol_version: str
    pymol_build: str
    python_version: str
    ip: list[str]
    qt_ver: str
    OS_TYPE: str
    is_translated_arm_mac: bool
    nproc: int


def get_client_info() -> CLIENT_INFO:
    info = SystemInfoReduced().info
    client_info: dict[str, Any] = {}

    for attr, info_key in CLIENT_INFO_FIELD_MAP.items():
        value = info[info_key]
        if attr == "ip":
            value = list(value)
        client_info[attr] = value

    client_info["OS_TYPE"] = f"{client_info['os']}_{client_info['machine_arch']}"
    return cast(CLIENT_INFO, client_info)
