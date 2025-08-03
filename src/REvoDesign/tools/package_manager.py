# pylint: disable=too-many-lines
# pylint: disable=import-outside-toplevel
# pylint: disable=unused-argument


import difflib
import importlib
import importlib.util
import io
import json
import math
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property, partial
from typing import (TYPE_CHECKING, Any, Callable, Dict, Iterable, List,
                    Mapping, NoReturn, Optional, Tuple, Type, TypeVar, Union,
                    overload)
from urllib.error import HTTPError, URLError

from pymol import cmd, get_version_message
from pymol.plugins import addmenuitemqt
from pymol.Qt.utils import loadUi

LOGGER_LEVEL = 0

if TYPE_CHECKING:
    # type checking branch
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    # runtime branch
    from pymol.Qt import QtCore, QtGui, QtWidgets


if not __file__.endswith('package_manager.py'):
    # PyMOL plugin branch, set docstring to describe the plugin
    __doc__ = """Described at GitHub:
https://github.com/YaoYinYing/REvoDesign

Authors : Yinying Yao
Program : REvoDesign
Date    : Sept 2023

REvoDesign -- Makes enzyme redesign tasks easier to all."""
    # use a mocked logger to handle logging from pymol's concole instead,
    # only if it runs as the role ofpackagemanager as a plugin from PyMOL

    class MockLogger:

        def debug(self, msg: str, *args, **kwargs):
            print(f'[DEBUG]: {msg}') if LOGGER_LEVEL < 10 else None

        def info(self, msg: str, *args, **kwargs):
            print(f'[INFO]: {msg}') if LOGGER_LEVEL < 20 else None

        def warning(self, msg: str, *args, **kwargs):
            print(f'[WARNING]: {msg}') if LOGGER_LEVEL < 30 else None

        def error(self, msg: str, *args, **kwargs):
            print(f'[ERROR]: {msg}') if LOGGER_LEVEL < 40 else None

        def critical(self, msg: str, *args, **kwargs):
            print(f'[CRITICAL]: {msg}') if LOGGER_LEVEL < 50 else None

    logging = MockLogger()
    logging.info(f'Package manager is running via PyMOL: {__file__}.')


else:
    # REvoDesign runtime branch, set docstring to describe the module
    __doc__ = '''
Module that contains key functions of constructing the REvoDesign Package Manager

This module also serves as standalone REvoDesign Package Manager,
meaning that any tools existed here is part of the manager.
To make any of them importable in certain modules, import them from here
and add to the `__all__` attributes so that they can be discoverable.
'''
    # enable logger from REvoDesign if it is a submodule not a script
    from REvoDesign.logger import ROOT_LOGGER

    logging = ROOT_LOGGER.getChild(__name__)
    logging.info('Package manager is running via REvoDesign.')


REPO_URL: str = "https://github.com/YaoYinYing/REvoDesign"

GIST_BASE_URL: str = 'https://gist.githubusercontent.com/YaoYinYing/c1e8bfe0fc0b9c60bf49ea04a550a044/raw'

# uploaded with `make upload-gists`
UI_FILE_URL = f'{GIST_BASE_URL}/REvoDesign-PyMOL-entry.ui'

# refer to THIS file, an installable package manager via pymol's plugin manager.
THIS_FILE_URL = f'{GIST_BASE_URL}/REvoDesign_PyMOL.py'
# Define the URL of the JSON file
RICH_TABLE_JSON = f'{GIST_BASE_URL}/REvoDesignExtrasTableRich.json'


# Define the proxy protocols allowed
ALLOWED_PROXY_PROTOCOLS = ["http", "https", 'socks5', 'socks5h']


@dataclass
class PlatformInfo:
    """
    A dataclass representing platform information.
    """

    HAS_CUDA = shutil.which('nvidia-smi') is not None
    HAS_MPS = platform.system() == 'Darwin' and platform.mac_ver()[-1] == 'arm64'


@dataclass
class ExtrasItem:
    '''
    A dataclass representing an extras item.

    Attributes:
    - name (str): The name of the extras item.
    - extras_id (str): The unique identifier for the extras item.
    - depts (list[str]): The departments associated with the extras item.
    '''
    name: str
    extras_id: str
    depts: list[str]
    description: Optional[str] = None
    platform: Optional[list[str]] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'ExtrasItem':
        """
        Create an ExtrasItem instance from a dictionary.

        Parameters:
        data (dict): The dictionary containing the extras item data.

        Returns:
        ExtrasItem: An instance of ExtrasItem created from the provided data.
        """
        return cls(
            name=data['name'],
            extras_id=data['extras_id'],
            depts=data['depts'],
            description=data.get('description', data['name']),
            platform=data.get('platform', None),
        )


@dataclass
class ExtrasGroup:
    '''
    A dataclass representing an extras group.

    Attributes:
    - name (str): The name of the extras group.
    - description (str): The description of the extras group.
    - extras (ExtrasItem): The extras item associated with this group.

    '''
    name: str
    description: str
    extras: list[ExtrasItem]

    @classmethod
    def from_dict(cls, data: dict) -> 'ExtrasGroup':
        """
        Create an ExtrasGroup instance from a dictionary.

        Parameters:
        data (dict): The dictionary containing the group data.

        Returns:
        ExtrasGroup: An instance of ExtrasGroup created from the provided data.
        """
        return cls(
            name=data['name'],
            description=data['description'],
            extras=[ExtrasItem.from_dict(item) for item in data['extras']]
        )

    @cached_property
    def extras_id_list(self) -> list[str]:
        return [item.extras_id for item in self.extras]


@dataclass
class ExtrasGroups:
    entities: tuple[ExtrasGroup, ...]

    @classmethod
    def from_dict(cls, d: dict) -> 'ExtrasGroups':
        """
        Create an ExtrasGroups object from a dictionary.

        Args:
        d (dict): A dictionary containing the group names and descriptions.

        Returns:
        ExtrasGroups: An ExtrasGroups object.
        """

        if d and 'entities' in d:
            return cls(
                tuple(
                    ExtrasGroup.from_dict(_d)
                    for _d in d['entities']
                )
            )

        return cls(tuple())

    @cached_property
    def all_extras(self) -> list[ExtrasItem]:
        """
        Returns:
        list[Extras]: A list of all Extras items in the ExtrasGroups instance.
        """
        return [item for group in self.entities for item in group.extras]

    def find_extras(self, name: str) -> list[ExtrasItem]:
        """
        Finds all Extras items with a given name in the ExtrasGroups instance.

        Args:
            name (str): The name of the Extras item to find.

        Returns:
            list[Extras]: A list of all Extras items with the given name.
        """
        return [item for item in self.all_extras if item.name == name]


def fetch_gist_file(ui_file_url: str, save_to_file: str) -> None:
    """
    Fetch the UI file from the given URL, save it to a temporary file, and yield its absolute path.

    Parameters:
    ui_file_url (str): The URL of the UI file to be fetched.
    save_to_file (str): The name of the temporary file to save the fetched UI file to.

    Returns:
    None
    """
    # Validate and sanitize the URL
    if not ui_file_url.startswith('https'):
        raise ValueError("URL must start with 'https'")

    try:
        # Fetch the file content and write it to the temporary file
        with urllib.request.urlopen(ui_file_url) as response, open(save_to_file, 'w') as ui_handle:
            ui_data = response.read().decode('utf-8')
            ui_handle.write(ui_data)

    except (URLError, HTTPError) as e:
        raise URLError(f"Failed to download file: {e}") from e
    except ValueError as e:
        raise ValueError(f"Invalid URL: {e}") from e

# Fetch and validate JSON data


def fetch_gist_json(url: str) -> dict[str, Any]:
    """
    Fetches JSON data from the specified URL and validates its structure.

    Parameters:
    url (str): The URL from which to fetch the JSON data.

    Returns:
    Dict[str, str]: The fetched and validated JSON data, or an empty dictionary if an error occurs.
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # Set a timeout for safety
            data = response.read().decode('utf-8')
            json_data = json.loads(data)
            logging.debug('Extras table is fetched and parsed: \n'
                          f'{json_data}')

            # Validate the structure of the fetched data
            if not isinstance(json_data, dict):
                raise ValueError("Fetched data is not a dictionary.")
            return json_data
    except Exception as e:
        logging.error(f"Error fetching or validating the JSON data: {e}: ")
        return {}


# Define a generic type variable for the return type of worker_function
R = TypeVar("R")


class UnsupportedWidgetValueTypeError(TypeError):
    """
    Exception raised when an unsupported value type is assigned to a Widget.

    This exception class inherits from TypeError and is used to indicate that the value type
    assigned to a Widget instance is not supported.
    """


class LiveProcessResult(subprocess.CompletedProcess):
    """
    A CompletedProcess-compatible result object with real-time captured output.
    """

    def __init__(self, args, returncode, stdout: str, stderr: str):
        super().__init__(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def run_command(
    cmd: Union[Tuple[str], List[str]],
    verbose: bool = False,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    """
    Execute a command with real-time output streaming, while capturing stdout and stderr.

    Parameters:
    - cmd: List or tuple of command and arguments.
    - verbose: If True, prints output in real time and logs errors.
    - env: Optional environment variables to pass to the subprocess.

    Returns:
    - A subprocess.CompletedProcess-compatible object with .args, .returncode, .stdout, .stderr.

    Raises:
    - RuntimeError: if the command fails and verbose is True.
    """
    if verbose:
        logging.info(f"Launching command: {' '.join(cmd)}")

    # Clone and patch environment for macOS if needed
    patched_env = os.environ.copy()
    if env:
        patched_env.update(env)

    stdout_lines: List[str] = []
    stderr_lines: List[str] = []

    def stream_reader(pipe: io.IOBase, collector: List[str], label: str):
        for line in iter(pipe.readline, ''):
            if verbose:
                logging.info(f"[{label}] {line.rstrip()}")
            collector.append(line)
        pipe.close()

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=patched_env,
    )

    t1 = threading.Thread(target=stream_reader, args=(process.stdout, stdout_lines, "STDOUT"))
    t2 = threading.Thread(target=stream_reader, args=(process.stderr, stderr_lines, "STDERR"))
    t1.start()
    t2.start()

    process.wait()
    t1.join()
    t2.join()

    stdout_text = ''.join(stdout_lines)
    stderr_text = ''.join(stderr_lines)

    if process.returncode != 0 and verbose:
        raise RuntimeError(
            f"--> Command failed:\n{'-' * 79}\n{stderr_text.strip()}\n{'-' * 79}"
        )

    return LiveProcessResult(
        args=cmd,
        returncode=process.returncode,
        stdout=stdout_text,
        stderr=stderr_text,
    )

# Additional widget for extra selection


class CheckableListView(QtWidgets.QWidget):
    """
    Checkable list view widget, allowing users to check items in the list.

    Attributes:
        list_view: The QListView instance this widget operates on.
        model: The data model instance used by the list view.
    """

    def __init__(self, list_view, items: ExtrasGroups, filter: PlatformInfo, parent=None):
        """
        Initializes the CheckableListView instance.

        Parameters:
            listView: The QListView instance to use.
            items: Optional list of item texts to add to the list.
            separators: Optional list of separator texts, used to categorize items.
            parent: The parent widget, defaults to None.
        """
        super().__init__(parent)

        # Use the existing list view
        self.list_view = list_view

        # Set up the model (use existing one if set, otherwise create a new one)
        if self.list_view.model() is None:
            self.model = QtGui.QStandardItemModel(self.list_view)
            self.list_view.setModel(self.model)
        else:
            self.model = self.list_view.model()

        # Clear the model before adding new items
        self.model.clear()

        self.items = items
        self.filter = filter

        for e in self.items.entities:
            # Add as a separator
            separator_item = QtGui.QStandardItem(e.name)
            separator_item.setEnabled(False)  # Non-interactive
            separator_item.setSelectable(False)  # Non-selectable
            separator_item.setCheckable(False)  # Non-checkable
            separator_item.setForeground(QtGui.QBrush(QtCore.Qt.yellow))
            separator_item.setBackground(QtGui.QBrush(QtCore.Qt.blue))   # Different background
            separator_item.setFont(QtGui.QFont("Arial", weight=QtGui.QFont.Bold))  # Bold text
            separator_item.setToolTip(e.description or e.name)
            self.model.appendRow(separator_item)

            for _e in e.extras:
                if _e.platform:
                    if any(not getattr(filter, f'HAS_{p}') for p in _e.platform):
                        logging.debug(f"Skipping {_e.name} for {_e.platform}")
                        continue

                # Add as a regular checkable item
                item = QtGui.QStandardItem(_e.name)
                item.setCheckable(True)
                item.setCheckState(QtCore.Qt.Unchecked)   # Default unchecked
                item.setToolTip(_e.description or _e.name)
                self.model.appendRow(item)

    def _get_items_by_check_state(self, check_state) -> ExtrasGroup:
        """
        Helper function to get items based on their check state.

        Args:
            check_state (int): The check state to filter items by (e.g., QtCore.Qt.Checked).

        Returns:
            A list of strings representing the texts of items with the specified check state.
        """
        items = ExtrasGroup(f'{"" if check_state else "un" }checked', '', [])
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item.isCheckable() and item.checkState() == check_state:
                items.extras.extend(self.items.find_extras(item.text()))
        return items

    @property
    def checked_items(self) -> list[str]:
        """
        Returns a list of all checked items' text.

        Returns:
            A list of strings representing the texts of all checked items.
        """
        checked_items = self._get_items_by_check_state(QtCore.Qt.Checked)
        logging.debug(f'Checked: {checked_items}')
        return checked_items.extras_id_list

    def check_all(self):
        """
        Check all items in the list, excluding separators.
        """
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item.isCheckable() and item.text() != 'Test':
                item.setCheckState(QtCore.Qt.Checked)

    def uncheck_all(self):
        """
        Uncheck all items in the list, excluding separators.
        """
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item.isCheckable():
                item.setCheckState(QtCore.Qt.Unchecked)


@dataclass
class GitSolver:
    """
    A class that checks for the presence of Git, Conda, and Winget on the system and can install Git if necessary.
    """

    has_git: Optional[str] = None
    has_conda: Optional[str] = None
    has_mamba: Optional[str] = None
    has_winget: Optional[str] = None
    has_brew: Optional[str] = None
    has_choco: Optional[str] = None

    def __post_init__(self):
        """
        Initializes instance attributes to check if git, conda, and winget are installed.

        This method is automatically called after the object initialization.
        It sets the object's properties based on whether these tools are available in the system path.
        This ensures that the object can determine if it can perform related operations before doing so.
        """
        # subprocess.run on Windows treat conda as a excutable file and will check its existence
        # however conda is AKA a alias in shell and does not exist as a file.
        # shutil.which will return the real path of conda script
        for cmd_tool in ["git", "conda", "mamba", "winget", "brew", 'choco']:
            setattr(self, f"has_{cmd_tool}", shutil.which(cmd_tool))
            logging.debug(f"Command tool check: {cmd_tool}: {getattr(self, f'has_{cmd_tool}')}")

    @property
    def where_to_install(self) -> Optional[List[str]]:
        if self.has_winget:
            return [
                self.has_winget,
                "install",
                "--id",
                "Git.Git",
                "-e",
                "--source",
                "winget",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]

        # Determine the installation command based on Conda's presence or the system type (Windows with Winget)
        if self.has_mamba:
            return [self.has_mamba, "install", "-y", "git"]
        if self.has_conda:
            return [self.has_conda, "install", "-y", "git"]

        if self.has_brew:
            return [self.has_brew, "install", "git"]
        if self.has_choco:
            return [self.has_choco, "install", "git"]

        return None

    def fetch_git(self, git_fetch_command: List[str], env: Optional[Mapping[str, str]] = None) -> Tuple[bool, str]:
        """
        Installs Git if it is not present on the system.

        This method attempts to install Git based on the available installers (Conda, Winget) or the system type.
        If the installation is successful, it returns True. Otherwise, it provides error information and returns False.

        Parameters:
            env (Optional[Mapping[str, str]]): Environment variables for the installation process.
        """

        # Check if Git is already installed
        if self.has_git:
            return True, ''

        # Execute the Git installation command in a worker thread and monitor progress
        git_install_std = run_command(
            cmd=git_fetch_command,
            verbose=True,
            env=env,
        )

        # Check if the Git installation was successful
        if (git_install_std and git_install_std.returncode == 0) or shutil.which('git'):
            self.has_git = shutil.which('git')
            return True, ''

        # If installation failed, show error information and return False

        with open((file_path := os.path.abspath("error.log")), "w", encoding="utf-8") as f:
            f.write(f"STDOUT:\n{git_install_std.stdout}\n\n\n\nSTDERR:\n{git_install_std.stderr}")

        return False, file_path


@dataclass
class PIPInstaller:
    """
    A class for installing, uninstalling, and ensuring the installation of packages using pip.

    Attributes:
        python_exe (str): The path to the Python executable.
        env (Optional[Mapping[str, str]]): Optional environment variables for running commands.
        verbose_level (int): The verbosity level for running commands.
            -3~-1: Maximum - Minimum silent
            0:  Default
            1~3:  Minimum - Maximum noisy
    """

    python_exe: str = ''
    # run_command args
    env: Optional[Mapping[str, str]] = None
    verbose_level: int = 0

    def ensurepip(self):
        """
        Run the ensurepip command to ensure pip is installed in the current Python environment.
        If ensurepip fails, raise a RuntimeError with the command output.
        """
        # run installation via pip
        ensurepip = run_command([self.python_exe, "-m", "ensurepip"], verbose=self.verbose_level > -1, env=self.env)
        if ensurepip.returncode:
            notify_box(
                f"ensurepip failed.",
                RuntimeError,
                details=f'\nSTDOUT:\n{ensurepip.stdout}\n\nSTDERR:\n{ensurepip.stderr}')

    def __post_init__(self):
        """
        Post-initialization method to set the real path of the Python executable and run ensurepip.
        """
        self.python_exe = os.path.realpath(sys.executable)
        self.ensurepip()

    def install(self,
                package_name: str = 'REvoDesign',
                source: Optional[str] = None,
                upgrade: bool = False,
                extras: Optional[str] = None,
                mirror: Optional[str] = "",
                verbose_level: int = 0,
                env: Optional[Mapping[str, str]] = None,
                ):
        """
        Install a package in the current Python environment.

        Args:
            package_name (str): The name of the package to install. Defaults to 'REvoDesign'.
            source (Optional[str]): The source URL for the package. Required if package_name is 'REvoDesign'.
            upgrade (bool): If True, upgrade the package if it is already installed. Defaults to False.
            extras (Optional[str]): Additional requirements to install. Defaults to None.
            mirror (Optional[str]): The URL of the package mirror to use. Defaults to None.
            verbose_level (int): The verbosity level for the installation. Defaults to 1.
            env (Optional[Mapping[str, str]]): Optional environment variables for running the pip command.

        Returns:
            The result of running the pip install command.
        """
        logging.info("Installation is started. This may take a while.")

        if package_name != 'pip':
            logging.info('Upgrading pip to the latest version...')
            self.install('pip', upgrade=True, verbose_level=verbose_level, env=self.env)

        def get_source_and_tag(source: str):
            """
            Parse the source URL and tag.

            Args:
                source (str): The source URL of the REvoDesign, or name of a package.

            Returns:
                Returns a tuple containing the git directory and git tag.
            """
            git_dir = source.split("@")[0]
            if "@" in source:
                git_tag = source.split("@")[1]
            else:
                git_tag = ""
            return git_dir, git_tag

        if package_name != 'REvoDesign':
            # use package_name as package_string for other packages then 'REvoDesign'
            package_string = package_name
        else:
            if source is None or source == '':
                raise ValueError("Source must be specified for REvoDesign")

            git_url, git_tag = get_source_and_tag(source=source)
            package_string = solve_installation_config(
                source=source,
                git_url=git_url,
                git_tag=git_tag,
                extras=extras,
                package_name=package_name
            )

        pip_cmd = [
            self.python_exe,
            "-m",
            "pip",
            "install",
            f"{package_string}",
        ]

        if upgrade:
            pip_cmd.append("-U")

        if mirror:
            logging.info(f"using mirror from {mirror}")
            pip_cmd.extend(["-i", mirror])
        if verbose_level < 0:
            pip_cmd.append(f"-{'q' * -verbose_level}")
        elif verbose_level > 0:
            pip_cmd.append(f"-{'v' * verbose_level}")

        logging.debug(f'Using verbose level {verbose_level}')

        result = run_command(
            pip_cmd, verbose=self.verbose_level > -1, env=env or self.env)
        return result

    def uninstall(self, package_name: str = 'REvoDesign'):
        """
        Uninstall a package from the current Python environment.

        Args:
            package_name (str): The name of the package to uninstall. Defaults to 'REvoDesign'.

        Returns:
            The result of running the pip uninstall command.
        """
        pip_cmd = [
            self.python_exe,
            "-m",
            "pip",
            "uninstall",
            "-y",
            package_name,
        ]
        result = run_command(pip_cmd, verbose=self.verbose_level > -1, env=self.env)
        return result

    def ensure_package(self, package_string: str,
                       env: Optional[Mapping[str, str]] = None, mirror: Optional[str] = None):
        """
        Ensure a package is installed in the current Python environment.
        If the package is not installed or needs to be upgraded, run the pip install command.

        Args:
            package_string (str): The name of the package to ensure.
            env (Optional[Mapping[str, str]]): Optional environment variables for running the pip command.
            mirror (Optional[str]): The URL of the package mirror to use. Defaults to None.
        """
        # Execute the pip installation command
        result = self.install(package_string, upgrade=True, env=env, mirror=mirror)
        # If the pip downgrade command fails, notify the user to manually execute the command
        if result.returncode:
            notify_box(
                f"Failed to ensure {package_string}. Please upgrade/downgrade manually.\n"
                f'Run this command in your shell - `{" ".join(result.args)}`',
                details=f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"

            )


@dataclass(frozen=True)
class MenuItem:
    """
    A data class representing a menu item.

    This class is used to define the properties of a menu item, including its name, associated function, and optional arguments.
    The use of the @dataclass decorator automatically generates special methods such as __init__(), __repr__(), and __eq__().
    The frozen parameter ensures that instances of the class are immutable, enhancing thread safety and consistency.

    Attributes:
        name (str): The name of the menu item, used for display and identification.
        func (Callable): The function associated with the menu item, which is executed when the item is selected.
        kwargs (Optional[Mapping]): Optional arguments passed to the associated function when it is executed. Defaults to None.
    """
    name: str
    func: Optional[Callable] = None
    kwargs: Optional[Mapping] = None


@dataclass
class REvoDesignPackageManager:
    """
    Class to manage the installation of the REvoDesign plugin.
    This class firstly performs a self-bootstrap including the following:
        1. fetch UI file and load it
        2. fetch extras table
        3. fetch repo release tags if possible
        4. add menu items
    Then it register widget signals and get all things ready.


    Attributes:
        dialog (QWidget): The main dialog window for the plugin GUI.
        extra_checkbox (CheckableListView): A checkbox list for selecting extra components.
    """

    dialog: Any = None
    installer_ui: Any = None
    extra_checkbox: CheckableListView = None  # type: ignore
    pip_installer: PIPInstaller = None  # type: ignore
    remote_extra_group_data: ExtrasGroups = None  # type: ignore

    platform_info = PlatformInfo()

    def ensure_ui_file(self, upgrade: bool = False):
        ui_file = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'REvoDesign-manager',
                'UI',
                'REvoDesign_installer.ui'))
        os.makedirs(os.path.dirname(ui_file), exist_ok=True)

        # if not exists,  preform the first fetch
        if not os.path.isfile(ui_file):
            fetch_gist_file(ui_file_url=UI_FILE_URL, save_to_file=ui_file)
            logging.info(f"Fetched UI file for manager: {ui_file}")
            return ui_file

        # otherwise, if the user not requires an upgrade, return
        if not upgrade:
            logging.debug(f'pre-downloaded UI file found: {ui_file}')
            return ui_file

        # otherwise, preform the upgrade
        new_ui_file = f'{ui_file}.swp'

        fetch_gist_file(ui_file_url=UI_FILE_URL, save_to_file=new_ui_file)
        self.upgrade_check(
            original_file=ui_file,
            new_file=new_ui_file,
            title='REvoDesign Manager UI file'
        )
        return ui_file

    @staticmethod
    def upgrade_check(original_file: str, new_file: str, title: str):
        """
        Check and apply an upgrade if necessary.

        This function compares the original file with a new fetched file, generates a diff file if there are differences,
        and prompts the user to confirm whether to apply the upgrade. If the user confirms, the new file replaces the original file.

        Parameters:
        - original_file (str): The path to the original file.
        - new_file (str): The path to the new fetched file.
        - title (str): The title used in notifications.

        Returns:
        - None
        """
        diff_file = f'{original_file}.diff'

        # Open the original, new fetched, and diff files
        with open(original_file) as original, open(new_file) as new_fetched:
            diffs = tuple(
                difflib.context_diff(
                    original.readlines(),
                    new_fetched.readlines(),
                    fromfile=original_file,
                    tofile=new_file
                )
            )
            if not diffs:
                return notify_box(f'{title} is already up to date.')

            num_added_lines = len([l for l in diffs if l.startswith('+ ')])
            num_chged_lines = len([l for l in diffs if l.startswith('! ')])
            num_deled_lines = len([l for l in diffs if l.startswith('- ')])

            with open(diff_file, 'w') as diff:
                diff.writelines(diffs)

        # Prompt the user to confirm the upgrade
        accept_upgraded = decide(
            title='Upgrade', description='Do you REALLY want to apply the upgrade?<p><p>'
            '<a style="background-color:yellow;color:blue;">:::::Upgrade Summary:::::</a><p>'
            '<table>'
            '<tr><th><b>Event</b></th><th>-</th><th><b>Affected Lines<b></th></tr>'
            f'<tr><td><a style="background-color:green;color:white">Added  </a></td><td>:</td><td><a style="background-color:white;color:green;">{num_added_lines}</a></td></tr>'
            f'<tr><td><a style="background-color:blue; color:white">Changed</a></td><td>:</td><td><a style="background-color:white;color:blue ;">{num_chged_lines}</a></td></tr>'
            f'<tr><td><a style="background-color:red;  color:white">Deleted</a></td><td>:</td><td><a style="background-color:white;color:red  ;">{num_deled_lines}</a></td></tr>'
            '</table>'
            'You must check out these changes carefully.<p>'
            f"See all changes in this <a href=file://{diff_file}>diff file of {title}</a>.", rich=True, details='\n'.join(diffs))

        # Clean up the diff file
        if os.path.isfile(diff_file):
            os.remove(diff_file)

        # Handle user response
        if not accept_upgraded:
            os.remove(new_file)
            return notify_box('Upgrade cancelled.')

        shutil.move(new_file, original_file)

        return notify_box(
            f'{title} has been upgraded successfully, please restart PyMOL to take effects.'
        )

    def self_upgrade(self):
        confirmed = decide(
            title='Upgrade REvoDesign',
            description='[WARNING]\n'
            'Do you want to upgrade REvoDesign Manager to the latest version?'
        )

        if not confirmed:
            return notify_box('Upgrade cancelled.')

        new_py_file = f'{__file__}.swp'

        fetch_gist_file(THIS_FILE_URL, new_py_file)

        self.upgrade_check(
            original_file=__file__,
            new_file=new_py_file,
            title='REvoDesign Manager'
        )

        self.ensure_ui_file(upgrade=True)

    @contextmanager
    def freeze_manager(self):
        """
        Freezes the dialog while the plugin is running.
        """
        self.dialog.setEnabled(False)
        logging.debug("Dialog locked.")
        try:
            yield
        except Exception as e:
            logging.error(f"Error occurred: {e}")
        self.dialog.setEnabled(True)
        logging.debug("Dialog unlocked.")

    def run_plugin_gui(self):
        """
        Runs the plugin GUI.

        This method initializes and displays the plugin's graphical user interface. It also sets up
        the extra components checkbox list and connects the radio button signals to the appropriate
        methods for checking or unchecking all items.

        Steps:
        - Initialize the dialog window if it hasn't been created yet.
        - Display the dialog window.
        - Create and position the extra components checkbox list.
        - Connect the 'None' radio button to uncheck all items in the checkbox list.
        - Connect the 'Everything' radio button to check all items in the checkbox list.
        - Run a worker thread to fetch tags with a progress bar.
        """
        logging.debug('Initializing dialog window...')
        if self.dialog is None:
            self.dialog = self.make_window()

        self.dialog.show()
        logging.debug('Dialog window initialized.')

        with self.freeze_manager():
            self.initialize_manager()

    def initialize_manager(self):

        logging.debug('Run pre-fetching tasks... ')

        self.refresh_remote_json()

        self.pip_installer = run_worker_thread_with_progress(PIPInstaller)

        self.extra_checkbox.setGeometry(QtCore.QRect(540, 90, 141, 431))

        # Connect the 'None' radio button to uncheck all items
        self.installer_ui.radioButton_extra_none.toggled["bool"].connect(
            self.extra_checkbox.uncheck_all,
        )

        # Connect the 'Everything' radio button to check all items
        self.installer_ui.radioButton_extra_everything.toggled["bool"].connect(
            self.extra_checkbox.check_all,
        )

        self.installer_ui.pushButton_refresh_extras.clicked.connect(self.refresh_remote_json)

        # Run a worker thread to fetch tags with a progress bar
        self.fetch_tags()
        logging.debug("Package manager initialized.")

    def proxy_in_env(self, proxy: Optional[str] = None, mirror: Optional[str] = None) -> Dict[str, str]:
        """
        Generates an environment mapping based on the provided proxy string.

        Args:
            proxy (str): The proxy string to use for creating the environment variables.

        Returns:
            Dict[str, str]: A dictionary containing the proxy settings for environment variables.
                            If `proxy` is empty, returns an empty dictionary.
        """

        if not proxy:
            return {}

        if not any(proxy.startswith(prefix) for prefix in ALLOWED_PROXY_PROTOCOLS):
            notify_box(f'Unsupported proxy type: {proxy}\nPlease use one of the following protocols: \n'
                       + "\n".join(f"{p}://..." for p in ALLOWED_PROXY_PROTOCOLS), ValueError)

        if proxy.startswith('socks5'):
            logging.info('Ensuring pysocks is installed...')
            run_worker_thread_with_progress(
                worker_function=self.pip_installer.ensure_package,
                package_string='pysocks',
                mirror=mirror,
                env={},
                progress_bar=self.installer_ui.progressBar)

        logging.info(f"using proxy: {proxy}")
        proxy_env = {
            "http_proxy": proxy,
            "https_proxy": proxy,
            "all_proxy": proxy,
        }
        return proxy_env

    def refresh_remote_json(self):
        """
        Refreshes the list of available extras by fetching data from a JSON source.

        This method uses a worker thread to fetch extras data with a progress bar indication.
        If fetching fails, it shows an error notification and sets up an empty extras list.
        """
        d_placeholder = {'entities': [{
            "name": "No Extras is Fetched",
            "description": "No Extras is Fetched, please check the internet connection",
            "extras": []
        }], }
        remote_data = run_worker_thread_with_progress(
            worker_function=fetch_gist_json,
            url=RICH_TABLE_JSON,
            progress_bar=self.installer_ui.progressBar)

        self.notification_channel(remote_data)

        if not remote_data:
            notify_box("Error fetching or validating the JSON data. \n"
                       "Please reconfigure your network and press <Refresh> to try again "
                       "if you wish to continue installation with extra packages")

        if 'entities' not in remote_data:
            notify_box('Fetched data is not valid. The data is expected to have an `entities` key.')

        self.remote_extra_group_data = ExtrasGroups.from_dict(remote_data or d_placeholder)

        # Create and position the extra components checkbox list
        self.extra_checkbox = CheckableListView(
            self.installer_ui.listView_extras, self.remote_extra_group_data, filter=self.platform_info
        )

    def notification_channel(self, d: dict):
        """
        Process notification messages and send them to the notification box

        Args:
            d (dict): A dictionary containing notification information, should include 'notification' key

        Returns:
            None
        """
        # Check if input dictionary is valid and contains notification key
        if not d or 'notification' not in d:
            return

        # Iterate through all notification messages and send to notification box
        for n in d['notification']:
            notify_box(message=f'[{n.get("level", "unknown")}]: {n.get("message")}')

    def collect_diagnostic_data(self, collect_dummy: bool = False, drop_sensitives=True):
        """
        Collects diagnostic data and copies it to the clipboard.

        This function clears the clipboard, collects diagnostic data by starting a worker thread,
        and then copies the collected data in JSON format to the clipboard. It finally notifies the user
        to paste the diagnostic information when creating a new issue on GitHub.

        Parameters:
        collect_dummy (bool): A flag indicating whether to collect dummy data. Default is False.
        drop_sensitives (bool): A flag indicating whether to drop sensitive data. Default is True.

        Returns:
        None
        """
        if not drop_sensitives:
            confirmed = decide(
                title='Agree to collect SENSITIVE data?',
                description='[!!!CAUSION!!!]Do you REALLY want to collect diagnostic information INCLUDING ALL SENSITIVE data?\n'
                'Please DO NOT share this information with anyone else or post it to public channels.',
            )
            if not confirmed:
                return notify_box('Diagnostic information collection cancelled.')

        # Clear the clipboard to ensure no old data is mixed in
        cb = QtWidgets.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)

        # Collect diagnostic data using a worker thread
        diagnostic_data = run_worker_thread_with_progress(
            worker_function=issue_collection,
            collect_dummy=collect_dummy,
            drop_sensitives=drop_sensitives,
            progress_bar=self.installer_ui.progressBar
        )
        diagnostic_data_json = json.dumps(diagnostic_data, indent=2)
        # Copy the collected diagnostic data to the clipboard in JSON format
        cb.setText(diagnostic_data_json, mode=cb.Clipboard)

        # Notify the user that the diagnostic data has been copied and instruct them on what to do next
        notify_box(
            "Issue collection copied to clipboard. "
            "Please paste it in a new issue in the REvoDesign repository on GitHub.",
            details=diagnostic_data_json,
        )

    def add_right_click_menu(self, items: List[MenuItem]):
        """
        Adds a right-click context menu to the installer UI.

        Args:
            items (List[MenuItem]): A list of menu items to be added to the right-click menu.

        This method creates a right-click menu with actions defined by the `items` parameter.
        Each item in the list is converted into a QAction, which is then added to the menu.
        """
        # Create the right-click menu
        self.menu = QtWidgets.QMenu(self.installer_ui)

        for item in items:
            if item.func is not None:  # active item
                # Add the item as active
                upgrade_action = QtWidgets.QAction(item.name, self.installer_ui)
                upgrade_action.triggered.connect(partial(item.func, **item.kwargs if item.kwargs else {}))
                upgrade_action.setEnabled(True)
                self.menu.addAction(upgrade_action)
            else:  # menu section
                self.menu.addSection(item.name)

        # Set the context menu policy to show the menu on right-click
        self.installer_ui.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.installer_ui.customContextMenuRequested.connect(self.show_menu)

    def show_menu(self, pos):
        """
        Shows the context menu at the position of the mouse cursor.

        Args:
            pos (QPoint): The position where the menu should be shown, in widget coordinates.
        """
        # Show the menu at the position of the mouse cursor
        global_pos = self.installer_ui.mapToGlobal(pos)
        self.menu.exec_(global_pos)

    def make_window(self) -> QtWidgets.QDialog:
        """
        Creates and configures the application window.

        This method initializes a QDialog object and sets up its UI elements using the `Ui_Dialog` class.
        It also connects various buttons to their respective methods for handling user interactions.

        Returns:
            QtWidgets.QDialog: The configured dialog window.
        """
        # Create a new dialog window
        dialog = QtWidgets.QDialog()

        ui_file = run_worker_thread_with_progress(
            worker_function=self.ensure_ui_file
        )
        # Set up the UI for the dialog
        try:
            self.installer_ui = loadUi(ui_file, dialog)
        except Exception as e:
            decided = decide(
                'UI Error',
                f'Error Occurs while loading UI file, this UI may out-of-dated.\nCleanup and fetch the latest?',
                details=str(e),)
            if decided:
                os.remove(ui_file)
                return self.make_window()
            else:
                raise RuntimeError(f"Error occurs while loading UI file: {e}.")

        # add right-click menu on `self.installer_ui.label_header`,
        # add a item `Upgrade UI` and connect `partial(self.ensure_ui_file, upgrade=True)`
        menuitems = [
            MenuItem('Upgrades'),
            MenuItem("Upgrade this manager", self.self_upgrade),

            MenuItem('Fetch remote data'),
            MenuItem('Refresh GitHub Release tags', self.fetch_tags),

            MenuItem('Diagnostics'),
            MenuItem(
                'Collect diagnostic data (reduced)',
                self.collect_diagnostic_data,
                kwargs={'collect_dummy': False}
            ),
            MenuItem(
                'Collect diagnostic data (full, non-sensitive)',
                self.collect_diagnostic_data,
                kwargs={'collect_dummy': True}
            ),
            MenuItem(
                'Collect diagnostic data (full, with sensitive)',
                self.collect_diagnostic_data,
                kwargs={'collect_dummy': True, 'drop_sensitives': False}
            ),

            MenuItem('Configuration Force Reset'),
            MenuItem(
                'Reset REvoDesign\'s Configuration',
                self.reinitialize_config,
            )
        ]
        self.add_right_click_menu(menuitems)

        # Connect the open files button to the open_files method
        self.installer_ui.pushButton_open.clicked.connect(self.open_files)

        # Connect the open cache directory button to the open_cache_dir method
        self.installer_ui.pushButton_open_cache_dir.clicked.connect(self.open_cache_dir)

        # Connect the set cache directory button to the setup_cache_dir method
        self.installer_ui.pushButton_set_cache_dir.clicked.connect(self.setup_cache_dir)

        # Connect the install button to the install method
        self.installer_ui.pushButton_install.clicked.connect(self.install)

        # Connect the remove button to the uninstall method
        self.installer_ui.pushButton_remove.clicked.connect(self.uninstall)

        # Connect the radio button for customized extra options to the resize_extra_widget method with expand=True
        self.installer_ui.radioButton_extra_customized.toggled["bool"].connect(
            partial(
                self.resize_extra_widget,
                expand=True,
            )
        )

        # Connect the radio button for no extra options to the resize_extra_widget method with expand=False
        self.installer_ui.radioButton_extra_none.toggled["bool"].connect(
            partial(
                self.resize_extra_widget,
                expand=False,
            )
        )

        # Connect the radio button for all extra options to the resize_extra_widget method with expand=False
        self.installer_ui.radioButton_extra_everything.toggled["bool"].connect(
            partial(
                self.resize_extra_widget,
                expand=False,
            )
        )

        # Return the configured dialog window
        return dialog

    @staticmethod
    def animate_to_size(widget, target_size, duration=300):
        """
        Animates the given widget to the target size over a specified duration.

        :param widget: The widget to animate.
        :param target_size: A tuple (width, height) representing the target size.
        :param duration: The duration of the animation in milliseconds.
        """
        animation = QtCore.QPropertyAnimation(widget, b"size")
        animation.setDuration(duration)
        animation.setStartValue(widget.size())
        animation.setEndValue(QtCore.QSize(*target_size))
        animation.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        animation.start()

        # Prevent animation from being garbage collected
        widget.anim = animation

    def resize_extra_widget(self, expand: bool = False):
        """
        Resize the extra widget based on the expand parameter.

        Parameters:
        - expand (bool): If True, expands the widget to a larger size; if False, shrinks it to a smaller size.

        This function animates the resizing of `self.dialog` and `self.ui.label_header` to the specified dimensions.
        """
        if expand:
            # Expand the dialog and label to larger sizes
            self.animate_to_size(self.dialog, (652, 534))
            self.animate_to_size(self.installer_ui.label_header, (611, 41))
        else:
            # Shrink the dialog and label to smaller sizes
            self.animate_to_size(self.dialog, (490, 534))
            self.animate_to_size(self.installer_ui.label_header, (451, 41))

    def fetch_tags(self):
        """
        Retrieves the tags of a GitHub repository and sets them as the value of the version combo box.

        This method calls the `get_github_repo_tags` function to obtain the tags information of the
        specified GitHub repository,
        and then sets the result as the value of the `comboBox_version` combo box in the UI.
        """
        # Run a worker thread to fetch tags with a progress bar
        tags = run_worker_thread_with_progress(
            worker_function=get_github_repo_tags,
            repo_url=REPO_URL,
            progress_bar=self.installer_ui.progressBar)
        if tags and isinstance(tags, list):
            return set_widget_value(self.installer_ui.comboBox_version, tags)

        return notify_box(f'Failed to fetch version tags from GitHub repo: \n{REPO_URL}')

    # a copy from `REvoDesign/tools/customized_widgets.py`

    def get_existing_directory(self):
        """
        Opens a dialog for the user to select an existing directory.

        Parameters:
        - self: The instance of the class this method is called on.

        Returns:
        - str: The path of the selected directory.
        """
        return QtWidgets.QFileDialog.getExistingDirectory(
            None,
            "Open Directory",
            os.path.expanduser("~"),
            QtWidgets.QFileDialog.DontResolveSymlinks,
        )

    # a copy from `REvoDesign/tools/customized_widgets.py`
    # an open file version of pymol.Qt.utils.getSaveFileNameWithExt ;-)
    def get_open_file_name_with_ext(self, *args, **kwargs):
        """
        Return a file name, append extension from filter if no extension provided.
        """

        fname, ext_filter = QtWidgets.QFileDialog.getOpenFileName(*args, **kwargs)

        if not fname:
            return ""

        if "." not in os.path.split(fname)[-1]:
            ext_match = re.search(r"\*(\.[\w\.]+)", ext_filter)
            if ext_match:
                # append first extension from filter
                fname += ext_match.group(1)

        return fname

    def open_cache_dir(self):
        """
        Opens the cache directory.

        This method retrieves an existing directory path and sets it as the value of a line edit widget.
        If the directory exists, it updates the UI with the directory path.

        Returns:
            The method returns the result of `set_widget_value` function, which is typically None or a
            status indicating success.
        """
        # Retrieve the existing directory path
        cache_dir = self.get_existing_directory()

        # Check if the directory exists and update the UI
        if cache_dir and os.path.exists(cache_dir):
            return set_widget_value(self.installer_ui.lineEdit_customized_cache_dir, cache_dir)

    def open_files(self):
        """
        Opens files or directories based on user selection from the UI.

        This function checks which radio button is selected (local clone or local file) and then opens
        the corresponding directory or file.

        Returns:
            None: The function updates the UI with the selected directory or file path.
        """

        # Check if the 'from local clone' radio button is selected
        from_local_clone = self.installer_ui.radioButton_from_local_clone.isChecked()

        # Check if the 'from local file' radio button is selected
        from_local_file = self.installer_ui.radioButton_from_local_file.isChecked()

        if from_local_clone:
            # Get the existing directory path from the user
            opened_dir = self.get_existing_directory()

            # If a valid directory is selected, update the UI with the directory path
            if opened_dir and os.path.exists(opened_dir):
                return set_widget_value(self.installer_ui.lineEdit_local, opened_dir)

        if from_local_file:
            # Define supported file extensions and their descriptions
            ext = {"zip": "ZIP archive", "tar.gz": "Tarball (TAR.GZ)"}

            # Open a file dialog to select a file with the specified extensions
            file = self.get_open_file_name_with_ext(
                self.dialog,
                "Open",
                filter=";;".join([f"{ext_description} ( *.{ext_} )" for ext_, ext_description in ext.items()]),
            )

            # If a valid file is selected, update the UI with the file path
            if file and os.path.exists(file):
                return set_widget_value(self.installer_ui.lineEdit_local, file)

    def uninstall(self):
        """
        Uninstall the REvoDesign package.

        This function checks if REvoDesign is installed. If it is installed, it initiates the uninstallation process
        through a separate thread, displaying the progress on the UI progress bar. After uninstallation is complete,
        it provides feedback on the operation's success or failure.
        """

        # Check if REvoDesign is installed
        installed = importlib.util.find_spec("REvoDesign") is not None

        # If REvoDesign is not installed, notify the user and exit the function
        if not installed:
            notify_box(message="REvoDesign is not installed.")
            return

        # During the uninstallation process, hold down the remove button on the UI to prevent multiple triggers
        with hold_trigger_button(self.installer_ui.pushButton_remove), self.freeze_manager():
            # Run the uninstallation process in a separate thread and monitor its progress
            ret = run_worker_thread_with_progress(
                worker_function=self.pip_installer.uninstall,
                package_name='REvoDesign',
                progress_bar=self.installer_ui.progressBar,
            )

            if ret is None or ret.returncode:
                # If the uninstallation fails, notify the user of the failure and raise an error
                return notify_box(message="Failed to remove REvoDesign.", error_type=RuntimeError, details=ret.stdout)

            remove_deps = decide(
                'Clean up warning', 'Do you want to remove all the dependencies?')
            if remove_deps:
                run_worker_thread_with_progress(
                    self.remove_depts,
                    progress_bar=self.installer_ui.progressBar
                )

            # If the uninstallation is successful, notify the user
            return notify_box(
                message="REvoDesign is removed successfully. Bye-bye.",
            )

    def remove_depts(self):
        """
        Removes selected dependencies.

        This function removes the packages corresponding to the dependencies checked by the user.
        It first fetches the dependency mapping table, filters out the dependencies that need to be removed,
        and then calls the uninstall method of pip_installer to remove each package.

        Parameters:
        - self: The instance of the class containing this method.

        Returns:
        - None
        """
        # Fetch the dependency package mapping table

        # Filter out dependencies whose package ID is empty

        # Get the list of dependencies checked by the user for uninstallation
        checked_depts_to_uninstall = self.extra_checkbox.checked_items
        # Iterate over the dependency table
        for e in self.remote_extra_group_data.all_extras:
            if e.extras_id not in checked_depts_to_uninstall:
                logging.debug(f'Skip unchecked item: {e.name}')
                continue
            # Uninstall each package associated with the checked dependency
            for _p in e.depts:
                logging.info(f"Removing {_p}...")
                self.pip_installer.uninstall(_p)

    def install(self):
        """
        Handles the installation process based on user-selected options.

        This function determines the installation source and method based on the user's choices,
        validates the input, and performs the installation process. It also manages network settings,
        such as proxies and mirrors, and provides feedback on the installation result.
        """
        # sources
        from_repo = self.installer_ui.radioButton_from_repo.isChecked()
        from_local_clone = self.installer_ui.radioButton_from_local_clone.isChecked()
        from_local_file = self.installer_ui.radioButton_from_local_file.isChecked()
        local_source: str = self.installer_ui.lineEdit_local.text()

        # Determine additional components to install
        extras = ",".join(self.extra_checkbox.checked_items)
        upgrade = self.installer_ui.checkBox_upgrade.isChecked()
        verbose_level = self.installer_ui.horizontalSlider_Verbose.value()

        # version tags
        use_version = self.installer_ui.checkBox_specified_version.isChecked()
        target_version = self.installer_ui.comboBox_version.currentText()

        # git commits
        use_commit = self.installer_ui.checkBox_specified_commit.isChecked()
        target_commit = self.installer_ui.lineEdit_commit.text()

        # networking
        use_proxy = self.installer_ui.checkBox_use_proxy.isChecked()
        proxy_url = self.installer_ui.lineEdit_proxy_url.text()

        use_mirror = self.installer_ui.checkBox_use_mirror.isChecked()
        mirror_url = self.installer_ui.lineEdit_mirror_url.text()

        # Determine the installation source based on user selection
        if from_repo:
            install_source = REPO_URL
            if use_version and target_version:
                install_source += f"@{target_version}"
            elif use_commit and target_commit:
                install_source += f"@{target_commit}"

        elif from_local_clone:
            install_source = local_source
            # Validate the local directory
            if not local_source:
                notify_box(f"Empty local dir: {local_source}", ValueError)
            if not os.path.exists(local_source):
                notify_box(f"dir not exists: {local_source}", ValueError)

            if not os.path.isdir(local_source):
                notify_box(f"{local_source} not a directory", FileNotFoundError)

            if use_version and target_version:
                install_source = f"file://{install_source}@{target_version}"
            elif use_commit and target_commit:
                install_source = f"file://{install_source}@{target_commit}"
        elif from_local_file:
            install_source = local_source
            # Validate the local file
            if not os.path.exists(local_source):
                notify_box(f"{local_source} is not found.", FileNotFoundError)
            if not os.path.isfile(local_source):
                notify_box(f"{local_source} is not a file.", ValueError)
            if not (local_source.endswith(".zip") or local_source.endswith(".tar.gz")):
                notify_box(
                    f"{local_source} must be a .zip or .tar.gz file!",
                    ValueError,
                )
            if use_version or use_commit or target_version or target_commit:
                logging.warning("installation from zip/tar file cannot use specified version/commit.")
            install_source = local_source

        else:
            notify_box("Installation configuration is failed. Aborded. ", ValueError)

        env: Dict[str, str] = {}

        # Update environment variables based on proxy settings
        env.update(self.proxy_in_env(
            proxy=proxy_url if (use_proxy and proxy_url) else None,
            mirror=mirror_url if (use_mirror and mirror_url) else None))

        # pass env to installer
        self.pip_installer.env = env

        # Perform the installation process
        with hold_trigger_button(self.installer_ui.pushButton_install), self.freeze_manager():
            git_solver = GitSolver()
            if not git_solver.has_git:
                git_fetch_command = git_solver.where_to_install
                if not git_fetch_command:
                    # If none of package managers is present, prompt the user to install Git manually
                    notify_box(
                        message="Failed on resolving Git with package managers [winget/conda/brew]. \n"
                        "Git is required to install REvoDesign. Please install Git first.\n"
                        "See https://git-scm.com/downloads",
                    )
                    return

                git_solver_res = run_worker_thread_with_progress(
                    worker_function=git_solver.fetch_git,
                    git_fetch_command=git_fetch_command,
                    env=env,
                    progress_bar=self.installer_ui.progressBar,
                )

                if not git_solver.has_git:
                    notify_box(
                        message=f"Git not installed. \n{git_solver_res[-1] if git_solver_res else ''}"
                    )
                    return
                # If successful, show a notification and return True
                notify_box(message="Git installed successfully.")

            installed = run_worker_thread_with_progress(
                worker_function=self.pip_installer.install,
                source=install_source,
                upgrade=upgrade,
                extras=extras,
                verbose_level=verbose_level,
                mirror=mirror_url if (use_mirror and mirror_url) else '',
                progress_bar=self.installer_ui.progressBar,
            )
            # Provide feedback on the installation result
            if isinstance(installed, subprocess.CompletedProcess) and installed.returncode == 0:
                notify_box(
                    message="Installation succeeded. \nIf this is an upgrade, "
                    "please restart PyMOL for it to take effect.",
                    details=f'STDOUT:\n{installed.stdout}\n\nSTDERR:\n{installed.stderr}' if installed else None)
                return

            notify_box(
                message=f"Installation failed from: {install_source} \n",
                error_type=RuntimeError,
                details=f'STDOUT: \n{installed.stderr}\n\nSTDERR: \n{installed.stderr}' if installed else None,
            )

    def setup_cache_dir(self):
        """
        Set up the custom cache directory.

        This function attempts to import `ConfigBus` and `save_configuration` from the REvoDesign library
        to update the cache directory settings.
        If the specified cache directory is valid, it updates the configuration and saves it.

        Returns:
            None
        """
        try:
            # Import necessary components from REvoDesign
            from REvoDesign import ConfigBus, save_configuration

            bus = ConfigBus()

            # Get the new cache directory from the UI input
            new_cache_dir = self.installer_ui.lineEdit_customized_cache_dir.text()

            # Check if the new cache directory is valid
            if new_cache_dir and os.path.isdir(new_cache_dir):
                # Update the cache directory settings
                bus.cfg.cache_dir.under_home_dir = False
                bus.cfg.cache_dir.customized = new_cache_dir

                # Save the updated configuration
                save_configuration(new_cfg=bus.cfg)

                # Notify the user that the cache directory has been updated
                notify_box(f"The customized cache directory has been updated: \n{new_cache_dir}")
            else:
                # Notify the user that the cache directory is invalid
                notify_box(f"The cache directory is not valid. Please check the path: \n{new_cache_dir}", UserWarning)

            # Reset the ConfigBus instance
            ConfigBus.reset_instance()

        except ImportError:
            # Notify the user that REvoDesign is not installed
            notify_box(
                message="REvoDesign is not installed. \nPlease install it first.",
                error_type=RuntimeError,
            )

    def reinitialize_config(self):
        comfirmed = decide(
            "Reinitialize REvoDesign configuration?",
            '[WARNING] This will delete your current configuration files.')

        if not comfirmed:
            return

        from REvoDesign.bootstrap.set_config import set_REvoDesign_config_file
        set_REvoDesign_config_file(delete_user_config_tree=True)


class WorkerThread(QtCore.QThread):
    """
    Custom worker thread for executing a function in a separate thread.

    Attributes:
    - result_signal (QtCore.pyqtSignal): Signal emitted when the result is available.
    - finished_signal (QtCore.pyqtSignal): Signal emitted when the thread finishes its execution.
    - interrupt_signal (QtCore.pyqtSignal): Signal to interrupt the thread.

    Methods:
    - __init__: Initializes the WorkerThread object.
    - run: Executes the specified function with arguments and emits the result through signals.
    - handle_result: Returns the result obtained after the thread execution.
    - interrupt: Interrupts the execution of the thread.

    Example Usage:
    ```python
    def some_function(x, y):
        return x + y

    worker = WorkerThread(func=some_function, args=(10, 20))
    worker.result_signal.connect(handle_result_function)
    worker.finished_signal.connect(handle_finished_function)
    worker.interrupt_signal.connect(handle_interrupt_function)
    worker.start()
    # To interrupt the execution:
    # worker.interrupt()
    ```
    """

    result_signal = QtCore.pyqtSignal(list)
    finished_signal = QtCore.pyqtSignal()
    interrupt_signal = QtCore.pyqtSignal()

    def __init__(self, func, args=None, kwargs=None):
        super().__init__()
        self.func = func
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.results = None  # Define the results attribute

    def run(self):
        """
        Executes the task and handles the results.

        This function checks if an interruption has been requested. If not, it runs the specified function with
        given arguments and keyword arguments.
        The result is then emitted through a signal if available, and a completion signal is emitted at the end.

        Parameters:
        - self: The instance of the class containing this method. It should have the following attributes:
            - func: The function to be executed.
            - args: A tuple of positional arguments for the function.
            - kwargs: A dictionary of keyword arguments for the function.
            - result_signal: A signal to emit the results.
            - finished_signal: A signal to indicate the task has finished.
            - isInterruptionRequested: A method that returns True if an interruption has been requested,
            otherwise False.
        """
        # Check if an interruption has been requested
        if not self.isInterruptionRequested():
            # Execute the function with provided arguments and store the result
            self.results = [self.func(*self.args, **self.kwargs)]

            # Emit the result if it exists
            if self.results:
                self.result_signal.emit(self.results)

            # Emit the finished signal
            self.finished_signal.emit()

    def handle_result(self):
        """
        Retrieves the results from the current instance.

        This method returns the 'results' attribute of the current instance.
        It is used to obtain the result data within other methods of the class.
        """
        return self.results

    def interrupt(self):
        """
        Emit an interrupt signal.

        This function triggers an interrupt signal.
        """
        self.interrupt_signal.emit()


@overload
def run_worker_thread_with_progress(
    worker_function: Callable[..., R], *args, progress_bar: Optional[Any] = None, **kwargs
) -> R: ...


def run_worker_thread_with_progress(
    worker_function: Callable[..., Optional[R]], *args, progress_bar: Optional[Any] = None, **kwargs
) -> Optional[R]:
    """
    Runs a worker function in a separate thread and optionally updates a progress bar.

    This function is designed to execute a given task (worker_function) in a separate thread,
    allowing the main thread to remain responsive, such as updating a progress bar.
    After the task is completed, it restores the progress bar's state and returns the result of the task.

    Parameters:
    - worker_function: The function to execute in a separate thread.
    - progress_bar: An optional progress bar object to update during the execution of the worker function.
    - *args, **kwargs: Additional arguments and keyword arguments to pass to the worker function.

    Returns:
    - The result of the worker function or None if no result is available.
    """
    # If a progress bar is provided, store its current state and set it to indeterminate progress
    if progress_bar:
        # store the progress bar state
        _min = progress_bar.minimum()
        _max = progress_bar.maximum()
        _val = progress_bar.value()

        progress_bar.setRange(0, 0)

    # Create and start a worker thread with the given function and parameters
    work_thread = WorkerThread(worker_function, args=args, kwargs=kwargs)
    work_thread.start()

    # Keep the main thread running until the worker thread finishes
    while not work_thread.isFinished():
        refresh_window()
        time.sleep(0.01)

    # If a progress bar was used, restore its state after the task is completed
    if progress_bar:
        # restore the progressbar state
        progress_bar.setRange(_min, _max)
        progress_bar.setValue(_val)

    # Obtain and return the result of the worker function
    result = work_thread.handle_result()

    return result[0] if result else None


def get_github_repo_tags(repo_url) -> list[str]:
    """
    Retrieve all released tags of a GitHub repository using urllib.

    Usage:
        tags = get_github_repo_tags("https://github.com/BradyAJohnston/MolecularNodes")
        print(tags)

    Args:
        repo_url (str): The URL of the GitHub repository.

    Returns:
        list: A list of tag names for the repository.
    """

    # Extract the owner and repo name from the URL
    parts = repo_url.split("/")
    owner = parts[-2]
    repo = parts[-1]

    # GitHub API URL for listing tags
    api_url = f"https://api.github.com/repos/{owner}/{repo}/tags"

    try:
        # Send a GET request to the GitHub API
        with urllib.request.urlopen(api_url) as response:
            # Read the response and decode from bytes to string
            response_data = response.read().decode()
            # Parse JSON response data
            tags = json.loads(response_data)
            # Extract the name of each tag
            tag_names = [tag["name"] for tag in tags]
            return tag_names
    except HTTPError as e:
        # Handle HTTP errors (e.g., repository not found, rate limit exceeded)
        logging.warning(f"GitHub API returned status code {e.code}")
        return []
    except URLError as e:
        # Handle URL errors (e.g., network issues)
        logging.error(f"Failed to reach the server. Reason: {e.reason}")
        return []


# a minimum copy from `REvoDesign/tools/customized_widgets.py`
def set_widget_value(widget, value):
    """
    Sets the value of a PyQt5 widget based on the provided value.
    ****************************************************************
    A minimum version for installer.
    ****************************************************************

    Args:
    - widget: The PyQt5 widget whose value needs to be set.
    - value: The value to be set on the widget.

    Supported Widgets and Value Types:
    - QComboBox: Supports str, list, tuple, dict.
    - QLineEdit: Supports str.
    - QProgressBar: Supports int, list or tuple (for setting range).
    - QCheckBox: Supports bool.
    """

    # Preprocess values according to types
    if callable(value):
        value = value()  # Call the function to get the value if value is callable

    if isinstance(value, Iterable) and not isinstance(value, (str, list, tuple, dict)):
        value = list(value)  # Convert iterable (excluding strings, lists, tuples, dicts) to list

    # Setting values
    if isinstance(widget, QtWidgets.QComboBox):
        if isinstance(value, (list, tuple)):
            widget.clear()
            widget.addItems(map(str, value))
            return
        if isinstance(value, dict):
            widget.clear()
            for k, v in value.items():
                widget.addItem(v, k)
            return

        widget.setCurrentText(str(value))
        return
    if isinstance(widget, QtWidgets.QLineEdit):
        widget.setText(str(value))
        return
    if isinstance(widget, QtWidgets.QProgressBar):
        if isinstance(value, int):
            widget.setValue(value)
            return
        if isinstance(value, (list, tuple)) and len(value) == 2:
            widget.setRange(*value)
            return
        raise ValueError(
            f"Invalid value {value} for QProgressBar. Value must be an integer or a list/tuple of two integers."
        )
    if isinstance(widget, QtWidgets.QCheckBox):
        widget.setChecked(bool(value))
        return

    raise UnsupportedWidgetValueTypeError(
        f"FIX ME: Value {value} is not currently supported on widget {type(widget).__name__}"
    )


def refresh_window():
    """
    Refresh the application window by processing all pending events.
    This function is copied from `REvoDesign/tools/customized_widgets.py`.

    No parameters are required for this function.

    Returns:
        None
    """
    QtWidgets.QApplication.processEvents()

# Overload #1: None or Warning => returns bool


@overload
def notify_box(
    message: str = "",
    error_type: Union[None, Type[Warning]] = None,
    details: Optional[str] = None
) -> None:
    ...

# Overload #2: Exception => NoReturn


@overload
def notify_box(
    message: str,
    error_type: Type[Exception],
    details: Optional[str] = None
) -> NoReturn:
    ...


def notify_box(
    message: str = "",
    error_type: Optional[Type[Exception]] = None,
    details: Optional[str] = None
) -> Union[None, NoReturn]:
    """
    Display a notification message box.

    Parameters:
    - message: str, the content of the message box.
    - error_type: Optional[Union[Exception, Warning]], the type of error or warning, can be None.

    If `error_type` is None or a Warning, returns bool.
    If `error_type` is an Exception (and not a Warning), raises => NoReturn.
    """
    refresh_window()
    # Create an information message box
    msg = QtWidgets.QMessageBox()

    if error_type is None:
        msg.setIcon(QtWidgets.QMessageBox.Information)
    elif issubclass(error_type, Warning):
        msg.setIcon(QtWidgets.QMessageBox.Warning)
    elif issubclass(error_type, Exception):
        msg.setIcon(QtWidgets.QMessageBox.Critical)

    msg.setText(message)
    if details is not None:
        msg.setDetailedText(details)

    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
    # Display the message box
    msg.exec_()
    # If error_type is None, end the function execution
    if error_type is None:
        return

    # error_type is a Warning => also bool
    if issubclass(error_type, Warning):
        warnings.warn(error_type(message))
        return

    # Otherwise, raise => NoReturn
    raise_error(error_type, message)


def raise_error(error_type: Type[Exception], message: str) -> NoReturn:
    """
    Raises an error of the specified type with the given message.

    Args:
    - error_type: Type[Exception], the type of error to raise.
    - message: str, the error message.
    """
    raise error_type(message)


def decide(title="", description="", rich: bool = False, details: Optional[str] = None):
    """
    Function: decide
    Usage: result = decide(title='', description='', rich=True)

    This function displays a confirmation message box with a title and description,
    allowing the user to proceed or cancel.

    Args:
    - title (str): Title of the confirmation box (default is empty)
    - description (str): Description displayed in the confirmation box (default is empty)
    - rich (bool): Whether to proceed with rich text or not (default is False)

    Returns:
    - bool: True if 'Yes' is selected, False otherwise
    """
    refresh_window()
    # A confirmation message.
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(description)
    if details is not None:
        msg.setDetailedText(details)
    if rich:
        msg.setTextFormat(QtCore.Qt.RichText)
    msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    result = msg.exec_()

    return result == QtWidgets.QMessageBox.Yes


def is_package_installed(package):
    """
    Function: is_package_installed
    Usage: is_installed = is_package_installed(package)

    This function checks if a specified package is installed in the current Python environment.

    Args:
    - package (str): Name of the package to check

    Returns:
    - bool: True if the package is installed, False otherwise
    """
    package_loader = importlib.util.find_spec(package)
    return package_loader is not None


def filter_sensitive_data(env):
    """
    Filters out sensitive data keys from the provided environment dictionary.

    Args:
        env (dict): The dictionary to filter.

    Returns:
        dict: A new dictionary with sensitive keys removed.
    """
    # Define the regex pattern to match sensitive keys
    sensitive_pattern = re.compile(
        r"(token|passwd|password|pass|session|_id|secret|access|auth|api_key|apikey|"
        r"access_key|accesskey|secret_key|secretkey|auth_token|authtoken|"
        r"session_id|session_token|private_key|ssh_key|key|login|cred|"
        r"credential|authenticator|certificate|cert|identity|oauth|jwt|bearer|csrf)",
        re.IGNORECASE
    )

    # Filter out sensitive keys
    filtered_env = {
        key: value for key, value in env.items() if not sensitive_pattern.search(key)
    }

    return filtered_env


def issue_collection(
        collect_dummy: bool = False,
        network: bool = True,
        drop_sensitives: bool = True,
) -> Dict[str, Any]:
    """
    Collects system and environment information and returns it as a dictionary.

    Parameters:
    - collect_dummy: A boolean indicating whether to collect additional 'dummy' information for debugging purposes.
    - network: A boolean indicating whether to collect network information.
    - drop_sensitives: A boolean indicating whether to drop sensitive information like passwords, tokens, etc.

    Returns:
    - A dictionary containing detailed information about the system, environment, and installed software.
    """
    issue_dict = {}

    # Collect platform information
    platform_info = platform.uname()

    # Platform
    issue_dict.update({'Platform::Platform': sys.platform})
    issue_dict.update({'Platform::Architecture': platform.architecture()[0]})
    issue_dict.update({'Platform::OS': platform_info.system})
    if platform_info.system == 'Darwin':
        issue_dict.update({'Platform::MacOS::Version': platform.mac_ver()[0]})
    elif platform_info.system == 'Windows':
        issue_dict.update({'Platform::Windows::Version': platform.win32_ver()})
        issue_dict.update({'Platform::Windows::Edition': platform.win32_edition()})
        issue_dict.update({'Platform::Windows::IsIotDevice': platform.win32_is_iot()})
    elif platform_info.system == 'Linux':
        issue_dict.update({'Platform::Linux::Version': platform.freedesktop_os_release()
                          if hasattr(platform, 'freedesktop_os_release') else None})
    issue_dict.update({'Platform::Release': platform_info.release})
    issue_dict.update({'Platform::Version': platform_info.version})

    if platform_info.system == 'Windows':
        issue_dict.update({'Platform::CPU': platform_info.processor})
    elif platform_info.system == 'Linux':
        cpuinfo = run_command(['cat', '/proc/cpuinfo']).stdout.strip()
        cpu_model = re.search(r'model name\s+:\s+(.+)', cpuinfo)
        issue_dict.update({'Platform::CPU': cpu_model.group(1) if cpu_model else 'Unknown'})
    elif platform_info.system == 'Darwin':
        issue_dict.update({'Platform::CPU': run_command(['sysctl', '-n', 'machdep.cpu.brand_string']).stdout.strip()})
    else:
        issue_dict.update({'Platform::CPU': 'Unknown'})

    issue_dict.update({'Platform::CPU::Num': os.cpu_count()})
    issue_dict.update({'Platform::Machine': platform_info.machine})
    issue_dict.update({'Platform::Hostname': platform_info.node})

    is_rosetta_mac = "ARM64" in platform_info.version and platform_info.machine == "x86_64" if platform_info.system == "Darwin" else False
    issue_dict.update({'Platform::IsRosettaTranlated': is_rosetta_mac})
    which_chcp = shutil.which("chcp")
    if which_chcp:
        try:
            issue_dict.update({'Platform::Windows::Chcp': run_command(['chcp']).stdout.strip()})
        except Exception as e:
            issue_dict.update({'Platform::Windows::Chcp': f"Error: {e}"})

    # Shell
    issue_dict.update({'Shell::Name': os.getenv('SHELL')})
    issue_dict.update({'Shell::Encoding': sys.stdout.encoding})
    issue_dict.update({'Shell::IsCygwin': 'CYGWIN' in os.environ.get('MSYSTEM', '')})

    # Python
    issue_dict.update({'Python::Version': sys.version})
    issue_dict.update({'Python::PythonPath': sys.executable})
    issue_dict.update({'Python::PIP': run_command([sys.executable, '-m', 'pip', '--version']).stdout.strip()})
    issue_dict.update({'Python::Compiler': platform.python_compiler()})
    issue_dict.update({'Python::Implementation': platform.python_implementation()})

    # PyQt
    issue_dict.update({'PyQt::Version': QtCore.PYQT_VERSION_STR})
    issue_dict.update({'PyQt::QtPath': QtCore.__file__})

    # Tools

    git_solver = GitSolver()

    try:
        conda_version = run_command([git_solver.has_conda, '--version']
                                    ).stdout.strip() if git_solver.has_conda else 'Not Found'
    except Exception:
        conda_version = 'Not Found'
    issue_dict.update({'Tools::Conda': conda_version})

    try:
        mamba_version = run_command([git_solver.has_mamba, '--version']
                                    ).stdout.strip() if git_solver.has_mamba else 'Not Found'
    except Exception:
        mamba_version = 'Not Found'

    issue_dict.update({'Tools::Mamba': mamba_version})
    issue_dict.update({'Tools::Git': git_solver.has_git})
    issue_dict.update({'Tools::Git::Version': run_command(
        [git_solver.has_git, '--version']).stdout.strip() if git_solver.has_git else 'Not Found'})
    issue_dict.update({'Tools::Homebrew': git_solver.has_brew})
    issue_dict.update({'Tools::Homebrew::Version': run_command(
        [git_solver.has_brew, '--version']).stdout.strip() if git_solver.has_brew else 'Not Found'})
    issue_dict.update({'Tools::Win-Get': git_solver.has_winget})
    issue_dict.update({'Tools::Win-Get::Version': run_command(
        [git_solver.has_winget, '--version']).stdout.strip() if git_solver.has_winget else 'Not Found'})

    # Env Vars
    issue_dict.update({'Env::CondaPath::0': os.getenv('CONDA_PREFIX')})
    issue_dict.update({'Env::CondaPath::1': os.getenv('CONDA_PREFIX_1')})
    issue_dict.update({'Env::CondaPath::2': os.getenv('CONDA_PREFIX_2')})
    issue_dict.update({'Env::CondaEnvName': os.getenv('CONDA_DEFAULT_ENV')})
    issue_dict.update({'Env::CondaPython': os.getenv('CONDA_PYTHON_EXE')})

    issue_dict.update({'User::HomeDir': os.getenv('HOME')})
    try:
        issue_dict.update({'User::Username': os.getlogin()})
    except OSError:
        issue_dict.update({'User::Username': 'Unknown'})

    # Network
    try:
        ip = socket.gethostbyname_ex(socket.gethostname())[2]
    except Exception as e:
        ip = f'Failed to fetch client ip: {e}'

    issue_dict.update({'Network::IP': ip})

    if network:
        ip_location = fetch_gist_json('https://ipinfo.io')
        if ip_location:
            issue_dict.update({'Network::Location': ip_location})
        else:
            issue_dict.update({'Network::Location': 'Failed to fetch client location'})

    # PyMOL
    issue_dict.update({'PyMOL::Version': cmd.get_version()[0]})
    issue_dict.update({'PyMOL::Build': get_version_message()})

    # REvoDesign
    issue_dict.update({'REvoDesign::Installer': __file__})

    if is_package_installed('REvoDesign'):
        import REvoDesign
        from REvoDesign.driver.ui_driver import ConfigBus
        from REvoDesign.magician import ALL_DESIGNER_CLASSES
        from REvoDesign.sidechain.sidechain_solver import ALL_RUNNER_CLASSES

        issue_dict.update({'REvoDesign::Version': REvoDesign.__version__})
        issue_dict.update({'REvoDesign::Config': REvoDesign.REVODESIGN_CONFIG_FILE})
        issue_dict.update({'REvoDesign::UI::Language': ConfigBus(
        ).cfg.language if ConfigBus._instance is not None else 'N/A'})

        logfile_in_cfg = ConfigBus().cfg.log.handlers.file.filename if ConfigBus._instance is not None else 'N/A'
        if logfile_in_cfg == 'AUTO':
            from platformdirs import user_log_path
            logdir = user_log_path("REvoDesign")
            logfile = os.path.join(logdir, "REvoDesign.runtime.log")
        else:
            logfile = logfile_in_cfg

        issue_dict.update({'REvoDesign::Logger::File': logfile})
        issue_dict.update({'REvoDesign::Extras::SidechainSolver': [
                          runner.name for runner in ALL_RUNNER_CLASSES if runner.installed]})
        issue_dict.update({'REvoDesign::Extras::Designers': [
                          designer.name for designer in ALL_DESIGNER_CLASSES if designer.installed]})
        issue_dict.update({'REvoDesign::Extras::TestSuite': is_package_installed('pytest')})
    else:
        issue_dict.update({'REvoDesign::Version': 'Not Installed'})

    # Dummy
    if collect_dummy:
        if drop_sensitives:
            env_dict = filter_sensitive_data(os.environ)
            logging.info('Sensitive data are removed.')
        else:
            env_dict = dict(os.environ)
            logging.warning('Sensitive data may be kept.')

        issue_dict.update({'Dummy::Environ': env_dict})

        pip_list_stdout: List[str] = run_command(['pip', 'list']).stdout.split('\n')
        pip_list_stdout_body: List[List[str]] = [l.split(' ') for l in pip_list_stdout[2:]]

        issue_dict.update({'Dummy::Pip::List': {
            line[0]: line[-1]
            for line in pip_list_stdout_body
            if line[0]
        }})
        if is_package_installed('REvoDesign'):
            import REvoDesign
            from REvoDesign.bootstrap.set_config import ConfigConverter
            from REvoDesign.driver.ui_driver import ConfigBus

            issue_dict.update({'Dummy::REvoDesign::Configurations': ConfigConverter().convert(
                ConfigBus().cfg) if ConfigBus._instance is not None else 'N/A'})
    return issue_dict


# TODO:
# add abort button
'''
self.abortbutton = QtWidgets.QPushButton('Abort')
self.abortbutton.setStyleSheet("background: #FF0000; color: #FFFFFF")
self.abortbutton.released.connect(cmd.interrupt)
'''


@contextmanager
def hold_trigger_button(
    buttons: Union[tuple[QtWidgets.QPushButton, ...], QtWidgets.QPushButton],
    animation_duration: int = 1000  # Duration of the breathing cycle (in milliseconds)
):
    """
    A context manager for holding and releasing trigger buttons with a breathing effect
    using the system's accent color.

    Args:
        buttons: One or more QPushButton objects.
        animation_duration: Duration of the breathing animation cycle (in milliseconds).
    """
    if not isinstance(buttons, (tuple, list, set)):
        buttons = (buttons,)

    timers = []

    def get_accent_color():
        color = QtGui.QColor(76, 217, 100)
        return color

    def start_breathing_animation(button: QtWidgets.QPushButton):
        accent_color = get_accent_color()
        base_color = accent_color.lighter(150)  # Start with a lighter shade
        darker_color = accent_color.darker(150)  # Use a darker shade for the trough

        timer = QtCore.QTimer(button)
        timer.setInterval(30)  # Update every 30 milliseconds
        elapsed = 0

        def update_stylesheet():
            nonlocal elapsed
            elapsed += timer.interval()
            t = (elapsed % animation_duration) / animation_duration  # Normalized time [0, 1]
            # Calculate intermediate intensity using sine wave
            factor = (1 + math.sin(2 * math.pi * t)) / 2  # Normalized to [0, 1]
            r = int(base_color.red() * factor + darker_color.red() * (1 - factor))
            g = int(base_color.green() * factor + darker_color.green() * (1 - factor))
            b = int(base_color.blue() * factor + darker_color.blue() * (1 - factor))
            button.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")

        timer.timeout.connect(update_stylesheet)
        timer.start()
        timers.append(timer)

    def stop_breathing_animation(button: QtWidgets.QPushButton):
        # Stop all timers associated with this button
        for timer in timers:
            if timer.parent() == button:
                timer.stop()
                timers.remove(timer)
        button.setStyleSheet("")  # Reset the button's style

    try:
        for b in buttons:
            b.setEnabled(False)
            b.setProperty("held", True)  # Mark the button as held
            b.setProperty("original_style", b.styleSheet() if b.styleSheet() else "")
            start_breathing_animation(b)
            logging.debug(f"Held button: {b.text()}: ({b.objectName()})")
        yield
    finally:
        for b in buttons:
            b.setProperty("held", False)  # Remove the held mark
            stop_breathing_animation(b)
            b.setStyleSheet(b.property("original_style") if b.property("original_style") else "")
            b.setEnabled(True)  # Re-enable the button
            logging.debug(f"Released button: {b.text()}: ({b.objectName()})")


def solve_installation_config(
    source: str,
    git_url: str,
    git_tag: str,
    extras: Optional[str],
    package_name: str = 'REvoDesign',
):
    """
    Solves the installation configuration based on the provided parameters.

    Parameters:
    - source (str): The source of the package to install. Can be a URL, a file path, or a directory.
    - git_url (str): The Git URL of the repository.
    - git_tag (str): The Git tag or branch to use for installation.
    - extras (str): Additional extras to include in the installation.

    Returns:
    - str: The formatted package string for installation.
    """
    extra_string = f'[{extras}]' if extras else ''
    package_string = f"{package_name}{extra_string}"
    logging.info(f"Installing as {package_string}...")

    # Handle installation from a GitHub URL with a tag
    if source and source.startswith("https://"):
        package_string += f' @ git+{git_url}{f"@{git_tag}" if git_tag else ""}'
        return package_string

    # Handle installation from a local directory
    if os.path.isdir(source):
        # preprocess
        if source.endswith("/"):
            source = source[:-1]
        # # a local Git repository? # TODO: not fully implemented yet
        # if os.path.isdir(os.path.join(source, ".git")):
        #     package_string += f' @ git+file://{source}{f"@{git_tag}" if git_tag else ""}'
        #     return package_string

        # or just an unzipped code directory?
        if os.path.exists(os.path.join(source, "pyproject.toml")):
            if git_tag:
                notify_box("Ignore unzipped code directory tag!")

            package_string = f"{source}{extra_string}"
            return package_string
        notify_box(f"{source} should atleast be a Git repository or a code directory!", ValueError)

    # Handle installation from a zipped code file
    if os.path.isfile(source):
        if git_tag:
            notify_box("Ignore zipped file tag!")

        if source.endswith(".zip") or source.endswith(".tar.gz"):
            package_string = f"{source}{extra_string}"
            return package_string

        notify_box(
            f"{source} is neither a zipped file nor a tar.gz file!",
            FileNotFoundError,
        )

    notify_box(f"Unknown installation source {source}({package_name})!", ValueError)

# entrypoint of PyMOL plugin


def __init_plugin__(app=None):
    """
    Add an entry to the PyMOL "Plugin" menu
    """
    logging.info(f"REvoDesign entrypoint is located at {os.path.dirname(__file__)}")

    plugin = REvoDesignPackageManager()
    addmenuitemqt("REvoDesign Package Manager", plugin.run_plugin_gui)

    if is_package_installed('REvoDesign'):
        try:
            from REvoDesign import REvoDesignPlugin

            plugin = REvoDesignPlugin()
            addmenuitemqt("REvoDesign", plugin.run_plugin_gui)
        except Exception as e:
            logging.error(str(e))
    else:
        logging.critical("REvoDesign is not available.")
