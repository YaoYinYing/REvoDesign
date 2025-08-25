'''
System info collector
'''
import platform
import warnings
from dataclasses import dataclass, field
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
    
    is_arm_macos = "ARM64" in platform.uname().version
    
    is_recognized_as_x86 = platform.machine() == "x86_64"
    print(f"Does it ARMed? {is_arm_macos}")
    print(f"Does it Rosetta-ed? {is_recognized_as_x86}")
    if not (is_arm_macos and is_recognized_as_x86):
        return
    
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
@dataclass
class CLIENT_INFO:
    '''
    A reduced client information class.
    '''
    node: str = ''
    user: str = ''
    os: str = ''
    os_build: str = ''
    machine_arch: str = ''
    revodesign_version: str = ''
    pymol_version: str = ''
    pymol_build: str = ''
    python_version: str = ''
    ip: list = field(default_factory=list)
    qt_ver: str = ''
    OS_TYPE: str = ''
    is_translated_arm_mac: bool = False
    nproc: int = 4
    def __post_init__(self):
        self.SYSTEM_INFO_DICT = SystemInfoReduced().info
        self.node: str = self.SYSTEM_INFO_DICT['Platform::Hostname']
        self.user: str = self.SYSTEM_INFO_DICT['User::Username']
        self.os: str = self.SYSTEM_INFO_DICT['Platform::OS']
        self.os_build: str = self.SYSTEM_INFO_DICT['Platform::Version']
        self.machine_arch: str = self.SYSTEM_INFO_DICT['Platform::Machine']
        self.revodesign_version: str = self.SYSTEM_INFO_DICT['REvoDesign::Version']
        self.pymol_version: str = self.SYSTEM_INFO_DICT['PyMOL::Version']
        self.pymol_build: str = self.SYSTEM_INFO_DICT['PyMOL::Build']
        self.python_version: str = self.SYSTEM_INFO_DICT['Python::Version']
        self.ip: list = self.SYSTEM_INFO_DICT['Network::IP']
        self.qt_ver: str = self.SYSTEM_INFO_DICT['PyQt::Version']
        self.OS_TYPE: str = f"{self.SYSTEM_INFO_DICT['Platform::OS']}_{self.SYSTEM_INFO_DICT['Platform::Machine']}"
        self.is_translated_arm_mac: bool = self.SYSTEM_INFO_DICT['Platform::IsRosettaTranlated']
        self.nproc: int = self.SYSTEM_INFO_DICT['Platform::CPU::Num']