"""
Described at GitHub:
https://github.com/YaoYinYing/REvoDesign

Authors : Yinying Yao
Program : REvoDesign
Date    : Sept 2023

REvoDesign -- Makes enzyme redesign tasks easier to all.
"""

# pylint: disable=too-many-lines
# pylint: disable=import-outside-toplevel
# pylint: disable=unused-argument

import difflib
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from typing import (Any, Callable, Dict, Iterable, List, Mapping, Optional,
                    Tuple, TypeVar, Union)
from urllib.error import HTTPError, URLError

from pymol.plugins import addmenuitemqt
from pymol.Qt import QtCore, QtGui, QtWidgets  # type: ignore
from pymol.Qt.utils import loadUi

print(f"REvoDesign entrypoint is located at {os.path.dirname(__file__)}")


REPO_URL: str = "https://github.com/YaoYinYing/REvoDesign"

# UI file online
# uploaded with `make upload-manager-ui`
UI_FILE_URL = 'https://gist.githubusercontent.com/YaoYinYing/2e378bbe038774e6f819f731701b32cb/raw'

# THIS file
# uploaded with `make upload-manager`
THIS_FILE_URL = 'https://gist.githubusercontent.com/YaoYinYing/c1e8bfe0fc0b9c60bf49ea04a550a044/raw'

# Define the URL of the JSON file
EXTRAS_TABLE_JSON = "https://gist.githubusercontent.com/YaoYinYing/37e0e8e73951fab3a12b2d8b81791f6a/raw"
DEPTS_TABLE_JSON = 'https://gist.githubusercontent.com/YaoYinYing/312c55b22c23069d478956bb85697bee/raw'


# Define the proxy protocols allowed
ALLOWED_PROXY_PROTOCOLS = ["http", "https", 'socks5', 'socks5h']


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


def fetch_gist_json(url: str) -> Dict[str, str]:
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
            print(f'[DEBUG]: Extras table is fetched and parsed: \n'
                  f'{json_data}')

            # Validate the structure of the fetched data
            if not isinstance(json_data, dict):
                raise ValueError("Fetched data is not a dictionary.")
            for key, value in json_data.items():
                if not isinstance(key, str) or not (isinstance(value, str) or value is None):
                    raise ValueError("Invalid key-value format in JSON data.")
            return json_data
    except Exception as e:
        print(f"Error fetching or validating the JSON data: {e}: ")
        return {}


# Define a generic type variable for the return type of worker_function
R = TypeVar("R")


class UnsupportedWidgetValueTypeError(TypeError):
    """
    Exception raised when an unsupported value type is assigned to a Widget.

    This exception class inherits from TypeError and is used to indicate that the value type
    assigned to a Widget instance is not supported.
    """


def run_command(
    cmd: Union[Tuple[str], List[str]],
    verbose: bool = False,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess:
    """
    Execute a specified command in the shell.

    Parameters:
    - cmd: A tuple or string representing the command to be executed. If it's a tuple, it represents the command
    and its parameters.
    - verbose: A boolean indicating whether to print detailed execution information.
    - env: A mapping object containing environment variables for the command.

    Returns:
    - The CompletedProcess object returned by subprocess.run(), containing the command execution information.

    Raises:
    - When the command execution fails (return code is not 0) and verbose is True, a RuntimeError is raised.
    """
    # Optionally print the command for debugging
    if verbose:
        print(f'launching command: {" ".join(cmd)}')

    # Execute the command using subprocess.run()
    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        env=env if env else None,
        text=True,
        check=False,
    )

    # Optionally print the command output for debugging
    if verbose and (res_text := result.stdout):
        print(res_text)

    # If the command execution fails and verbose is True, raise an exception
    if result.returncode != 0 and verbose:
        raise RuntimeError(f"--> Command failed: \n{'-'*79}\n{result.stderr}\n{'-'*79}")

    # Return the execution result
    return result

# Additional widget for extra selection


class CheckableListView(QtWidgets.QWidget):
    """
    Checkable list view widget, allowing users to check items in the list.

    Attributes:
        list_view: The QListView instance this widget operates on.
        model: The data model instance used by the list view.
    """

    def __init__(self, list_view, items: Optional[Dict[str, str]] = None, parent=None):
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

        # Add items to the model with optional separators
        if not items:
            return

        self.items = items

        for k, v in items.items():
            if not v:
                # Add as a separator
                separator_item = QtGui.QStandardItem(k)
                separator_item.setEnabled(False)  # Non-interactive
                separator_item.setSelectable(False)  # Non-selectable
                separator_item.setCheckable(False)  # Non-checkable
                separator_item.setForeground(QtGui.QBrush(QtCore.Qt.yellow))
                separator_item.setBackground(QtGui.QBrush(QtCore.Qt.blue))  # Different background
                separator_item.setFont(QtGui.QFont("Arial", weight=QtGui.QFont.Bold))  # Bold text
                self.model.appendRow(separator_item)
            else:
                # Add as a regular checkable item
                item = QtGui.QStandardItem(k)
                item.setCheckable(True)
                item.setCheckState(QtCore.Qt.Unchecked)  # Default unchecked
                self.model.appendRow(item)

    def _get_items_by_check_state(self, check_state):
        """
        Helper function to get items based on their check state.

        Args:
            check_state (int): The check state to filter items by (e.g., QtCore.Qt.Checked).

        Returns:
            A list of strings representing the texts of items with the specified check state.
        """
        items = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item.isCheckable() and item.checkState() == check_state:
                items.append(self.items.get(item.text(), None))
        return items

    def get_checked_items(self):
        """
        Returns a list of all checked items' text.

        Returns:
            A list of strings representing the texts of all checked items.
        """
        checked_items = self._get_items_by_check_state(QtCore.Qt.Checked)
        print(f'[DEBUG]: Checked: {checked_items}')
        return checked_items

    def get_unchecked_items(self):
        """
        Returns a list of all unchecked items' text.

        Returns:
            A list of strings representing the texts of all unchecked items.
        """
        return self._get_items_by_check_state(QtCore.Qt.Unchecked)

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

    has_git: bool = False
    has_conda: bool = False
    has_winget: bool = False
    has_brew: bool = False

    def __post_init__(self):
        """
        Initializes instance attributes to check if git, conda, and winget are installed.

        This method is automatically called after the object initialization.
        It sets the object's properties based on whether these tools are available in the system path.
        This ensures that the object can determine if it can perform related operations before doing so.
        """
        for cmd_tool in ["git", "conda", "winget", "brew"]:
            setattr(self, f"has_{cmd_tool}", shutil.which(cmd_tool) is not None)

    def fetch_git(self, env: Optional[Mapping[str, str]] = None):
        """
        Installs Git if it is not present on the system.

        This method attempts to install Git based on the available installers (Conda, Winget) or the system type.
        If the installation is successful, it returns True. Otherwise, it provides error information and returns False.

        Parameters:
            env (Optional[Mapping[str, str]]): Environment variables for the installation process.
        """

        # Check if Git is already installed
        if self.has_git:
            return True

        # Determine the installation command based on Conda's presence or the system type (Windows with Winget)
        if self.has_winget:
            cmd = [
                "winget",
                "install",
                "--id",
                "Git.Git",
                "-e",
                "--source",
                "winget",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]

        elif self.has_brew:
            cmd = ["brew", "install", "git"]

        elif self.has_conda:
            cmd = ["conda", "install", "-y", "git"]

        else:
            # If none of package managers is present, prompt the user to install Git manually
            notify_box(
                message="Failed on resolving Git with package managers [winget/conda/brew]. \n"
                "Git is required to install REvoDesign. Please install Git first.\n"
                "See https://git-scm.com/downloads",
            )
            return False

        # Prompt the user for confirmation to install Git
        confirmed = proceed_with_comfirm_msg_box(
            title="Install Git?",
            description=f'Do you want to install git first?\n command:\n {" ".join(cmd)}',
        )
        if not confirmed:
            # If the user cancels the installation, notify and return
            notify_box(message="Git installation is cancelled.")
            return False

        # Execute the Git installation command in a worker thread and monitor progress
        git_install_std: subprocess.CompletedProcess = run_command(
            cmd=cmd,
            verbose=True,
            env=env,
        )

        # Check if the Git installation was successful
        if git_install_std and git_install_std.returncode == 0 and self.has_git:
            # If successful, show a notification and return True
            notify_box(message="Git installed successfully.")
            return True

        # If installation failed, show error information and return False

        with open((file_path := os.path.abspath("error.log")), "w", encoding="utf-8") as f:
            f.write(f"STDOUT:\n{git_install_std.stdout}\n\n\n\nSTDERR:\n{git_install_std.stderr}")

        notify_box(
            message=f"Git not installed.\n Error details saved to {file_path}\n",
            error_type=RuntimeError,
        )


@dataclass
class PIPInstaller:
    """
    A class for installing, uninstalling, and ensuring the installation of packages using pip.

    Attributes:
        python_exe (str): The path to the Python executable.
        env (Optional[Mapping[str, str]]): Optional environment variables for running commands.
        verbose (bool): If True, print detailed information when running commands.
    """

    python_exe: str = ''
    # run_command args
    env: Optional[Mapping[str, str]] = None
    verbose: bool = True

    def ensurepip(self):
        """
        Run the ensurepip command to ensure pip is installed in the current Python environment.
        If ensurepip fails, raise a RuntimeError with the command output.
        """
        # run installation via pip
        ensurepip = run_command([self.python_exe, "-m", "ensurepip"], verbose=self.verbose, env=self.env)
        if ensurepip.returncode:
            notify_box(f"ensurepip failed: \nSTDOUT:\n{ensurepip.stdout}\n\nSTDERR:\n{ensurepip.stderr}.", RuntimeError)
            return

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
                quiet: bool = False,
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
            quiet (bool): If True, run pip in quiet mode. Defaults to False.
            env (Optional[Mapping[str, str]]): Optional environment variables for running the pip command.

        Returns:
            The result of running the pip install command.
        """
        print("Installation is started. This may take a while and the window will freeze until it is done.")

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
            print(f"using mirror from {mirror}")
            pip_cmd.extend(["-i", mirror])
        if quiet:
            pip_cmd.append("-q")

        result: subprocess.CompletedProcess = run_command(
            pip_cmd, verbose=self.verbose, env=env if env is not None else self.env)
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
        result: subprocess.CompletedProcess = run_command(pip_cmd, verbose=self.verbose, env=self.env)
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
            print(
                f"Failed to ensure {package_string}. Please upgrade/downgrade manually.\n"
                f'Run this command in your shell - `{" ".join(result.args)}`'
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
    func: Callable
    kwargs: Optional[Mapping] = None


@dataclass
class REvoDesignInstaller:
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

    def ensure_ui_file(self, upgrade: bool = False):
        ui_file = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                'REvoDesign-manager',
                'UI',
                'REvoDesign_installer.ui'))
        os.makedirs(os.path.dirname(ui_file), exist_ok=True)
        if os.path.isfile(ui_file) and not upgrade:
            print(f'[DEBUG]: pre-downloaded UI file found: {ui_file}')
            return ui_file

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
            num_deled_lines = len([l for l in diffs if l.startswith('- ')])

            with open(diff_file, 'w') as diff:
                diff.writelines(diffs)

        # Prompt the user to confirm the upgrade
        accept_upgraded = proceed_with_comfirm_msg_box(
            'Upgrade',
            'Do you REALLY want to apply the upgrade?<p><p>'
            f'Added  : {num_added_lines} <p>'
            f'Deleted: {num_deled_lines} <p>'
            'You must check out these changes carefully.<p>'
            f"See all changes in this <a href=file://{diff_file}>diff file of {title}.</a>", rich=True)

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
        confirmed = proceed_with_comfirm_msg_box(
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
        if self.dialog is None:
            self.dialog = self.make_window()
        self.dialog.show()

        self.refresh_extras_table()

        self.pip_installer = PIPInstaller()

        self.extra_checkbox.setGeometry(QtCore.QRect(540, 90, 141, 431))

        # Connect the 'None' radio button to uncheck all items
        self.installer_ui.radioButton_extra_none.toggled["bool"].connect(
            partial(
                self.extra_checkbox.uncheck_all,
            )
        )

        # Connect the 'Everything' radio button to check all items
        self.installer_ui.radioButton_extra_everything.toggled["bool"].connect(
            partial(
                self.extra_checkbox.check_all,
            )
        )

        self.installer_ui.pushButton_refresh_extras.clicked.connect(self.refresh_extras_table)

        # Run a worker thread to fetch tags with a progress bar
        self.fetch_tags()

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
            raise ValueError(f'Unsupported proxy type: {proxy}')

        if proxy.startswith('socks5'):
            print('Ensuring pysocks is installed...')
            run_worker_thread_with_progress(
                worker_function=self.pip_installer.ensure_package,
                package_string='pysocks',
                mirror=mirror,
                env={},
                progress_bar=self.installer_ui.progressBar)

        print(f"using proxy: {proxy}")
        proxy_env = {
            "http_proxy": proxy,
            "https_proxy": proxy,
            "all_proxy": proxy,
        }
        return proxy_env

    def refresh_extras_table(self):
        """
        Refreshes the list of available extras by fetching data from a JSON source.

        This method uses a worker thread to fetch extras data with a progress bar indication.
        If fetching fails, it shows an error notification and sets up an empty extras list.
        """
        # Run a worker thread to fetch extras with a progress bar
        AVAILABLE_EXTRAS = run_worker_thread_with_progress(
            worker_function=fetch_gist_json,
            url=EXTRAS_TABLE_JSON,
            progress_bar=self.installer_ui.progressBar)

        # Handle the case where no extras are fetched
        if not AVAILABLE_EXTRAS:
            AVAILABLE_EXTRAS = {"No Extras is Fetched": ''}
            notify_box("Error fetching or validating the JSON data. \n"
                       "Please reconfigure your network and press <Refresh> to try again "
                       "if you wish to continue installation with extra packages")

        # Create and position the extra components checkbox list
        self.extra_checkbox = CheckableListView(
            self.installer_ui.listView_extras, AVAILABLE_EXTRAS
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
            # Add the "Upgrade UI" item
            upgrade_action = QtWidgets.QAction(item.name, self.installer_ui)
            upgrade_action.triggered.connect(partial(item.func, **item.kwargs if item.kwargs else {}))

            # Add the action to the menu
            self.menu.addAction(upgrade_action)

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

    def make_window(self) -> QtWidgets.QDialog:  # type: ignore
        """
        Creates and configures the application window.

        This method initializes a QDialog object and sets up its UI elements using the `Ui_Dialog` class.
        It also connects various buttons to their respective methods for handling user interactions.

        Returns:
            QtWidgets.QDialog: The configured dialog window.
        """
        # Create a new dialog window
        dialog = QtWidgets.QDialog()

        ui_file = self.ensure_ui_file()
        # Set up the UI for the dialog
        self.installer_ui = loadUi(ui_file, dialog)

        # add right-click menu on `self.installer_ui.label_header`,
        # add a item `Upgrade UI` and connect `partial(self.ensure_ui_file, upgrade=True)`
        menuitems = [
            MenuItem("Upgrade UI", self.ensure_ui_file, kwargs={"upgrade": True}),
            MenuItem("Upgrade this manager", self.self_upgrade),
            MenuItem('Refresh GitHub Release tags', self.fetch_tags)
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
        with hold_trigger_button(self.installer_ui.pushButton_remove):
            # Run the uninstallation process in a separate thread and monitor its progress
            ret: Optional[subprocess.CompletedProcess] = run_worker_thread_with_progress(
                worker_function=self.pip_installer.uninstall,
                package_name='REvoDesign',
                progress_bar=self.installer_ui.progressBar,
            )

            if ret is None or ret.returncode:
                # If the uninstallation fails, notify the user of the failure and raise an error
                return notify_box(message="Failed to remove REvoDesign.", error_type=RuntimeError)

            remove_deps = proceed_with_comfirm_msg_box(
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
        deps_table: Dict[str, str] = fetch_gist_json(DEPTS_TABLE_JSON)
        # Filter out dependencies whose package ID is empty
        deps_table = {k: v for k, v in deps_table.items() if v != ''}
        # Get the list of dependencies checked by the user for uninstallation
        checked_depts_to_uninstall = self.extra_checkbox.get_checked_items()
        # Iterate over the dependency table
        for pkg_name, pkg_id in deps_table.items():
            if pkg_name not in checked_depts_to_uninstall:
                print(f'[DEBUG]: Skip unchecked item: {pkg_name}')
                continue
            # Uninstall each package associated with the checked dependency
            for _p in pkg_id.split(';'):
                print(f"Removing {_p}...")
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
        extras = ",".join(self.extra_checkbox.get_checked_items())
        upgrade = self.installer_ui.checkBox_upgrade.isChecked()
        verbose = self.installer_ui.checkBox_verbose.isChecked()

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
                print("WARNING: installation from zip/tar file cannot use specified version/commit.")
            install_source = local_source

        else:
            return notify_box("Installation configuration is failed. Aborded. ", ValueError)

        env: Dict[str, str] = {}

        # Update environment variables based on proxy settings
        env.update(self.proxy_in_env(
            proxy=proxy_url if (use_proxy and proxy_url) else None,
            mirror=mirror_url if (use_mirror and mirror_url) else None))

        # pass env to installer
        self.pip_installer.env = env

        # Perform the installation process
        with hold_trigger_button(self.installer_ui.pushButton_install):
            git_solver = GitSolver()
            has_git = run_worker_thread_with_progress(
                worker_function=git_solver.fetch_git,
                env=env,
                progress_bar=self.installer_ui.progressBar,
            )

            if not has_git:
                return

            installed: Union[subprocess.CompletedProcess, None] = run_worker_thread_with_progress(
                worker_function=self.pip_installer.install,
                source=install_source,
                upgrade=upgrade,
                extras=extras,
                quiet=not verbose,
                mirror=mirror_url if (use_mirror and mirror_url) else '',
                progress_bar=self.installer_ui.progressBar,
            )
            # Provide feedback on the installation result
            if isinstance(installed, subprocess.CompletedProcess) and installed.returncode == 0:
                notify_box(
                    message="Installation succeeded. \nIf this is an upgrade, "
                    "please restart PyMOL for it to take effect.", )
                return

            notify_box(
                message=f"Installation failed from: {install_source} \n",
                error_type=RuntimeError,
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
            return


# a copy from `REvoDesign/tools/customized_widgets.py`
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
        self.args = args if args is not None else ()
        self.kwargs = kwargs if kwargs is not None else {}
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

# a copy from `REvoDesign/tools/utils.py`


def run_worker_thread_with_progress(
    worker_function: Callable[..., R], *args, progress_bar: Optional[Any] = None, **kwargs
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
        progress_bar.setRange(_min, _max)  # type: ignore
        progress_bar.setValue(_val)  # type: ignore

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
        print(f"Error: GitHub API returned status code {e.code}")
        return []
    except URLError as e:
        # Handle URL errors (e.g., network issues)
        print(f"Error: Failed to reach the server. Reason: {e.reason}")
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


# a copy from `REvoDesign/tools/customized_widgets.py`
def refresh_window():
    """
    Refresh the application window by processing all pending events.
    This function is copied from `REvoDesign/tools/customized_widgets.py`.

    No parameters are required for this function.

    Returns:
        None
    """
    QtWidgets.QApplication.processEvents()


# a copy from `REvoDesign/tools/customized_widgets.py`
def notify_box(message: str = "", error_type: Optional[Union[type[Exception], type[Warning]]] = None) -> bool:
    """
    Display a notification message box.

    Parameters:
    - message: str, the content of the message box.
    - error_type: Optional[Union[Exception, Warning]], the type of error or warning, can be None.

    Returns:
    - None, but if error_type is not None, it either shows a warning or raises an exception.
    """
    # Create an information message box
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Information)
    msg.setText(message)
    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)

    # Display the message box
    msg.exec_()
    # If error_type is None, end the function execution
    if error_type is None:
        return True

    # if it is warning, show the warning message and return
    if isinstance(error_type, Warning):
        warnings.warn(error_type(message))  # type: ignore
        return True

    # otherwise raise the exception
    if isinstance(error_type, Exception):
        raise error_type(message)  # type: ignore

    return False


# a copy from `REvoDesign/tools/customized_widgets.py`
def proceed_with_comfirm_msg_box(title="", description="", rich: bool = False):
    """
    Function: proceed_with_confirm_msg_box
    Usage: result = proceed_with_confirm_msg_box(title='', description='')

    This function displays a confirmation message box with a title and description,
    allowing the user to proceed or cancel.

    Args:
    - title (str): Title of the confirmation box (default is empty)
    - description (str): Description displayed in the confirmation box (default is empty)

    Returns:
    - bool: True if 'Yes' is selected, False otherwise
    """
    # A confirmation message.
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(description)
    if rich:
        msg.setTextFormat(QtCore.Qt.RichText)
    msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    result = msg.exec_()

    return result == QtWidgets.QMessageBox.Yes


# a copy from `REvoDesign/tools/customized_widgets.py`
@contextmanager
def hold_trigger_button(button):
    """
    A context manager for holding and releasing a trigger button.

    Usage:
        with hold_trigger_button(button):
            # Code block where the button is held (disabled)
            # The button will be automatically released (enabled) at the end of the block
    """
    try:
        button.setEnabled(False)
        yield
    finally:
        button.setEnabled(True)


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
    print(f"Installing as {package_string}...")

    # Handle installation from a GitHub URL with a tag
    if source and source.startswith("https://"):
        package_string += f' @ git+{git_url}{f"@{git_tag}" if git_tag else ""}'
        return package_string

    # Handle installation from a local Git repository with a tag
    if source.startswith("file://"):
        repo_dir = git_url.replace("file://", "")
        if not os.path.exists(os.path.join(repo_dir, ".git")):
            notify_box(f'Git dir not found: {os.path.join(repo_dir, ".git")}')
        package_string += f' @ git+{git_url}{f"@{git_tag}" if git_tag else ""}'
        return package_string

    # Handle installation from an unzipped code directory
    if os.path.exists(source) and os.path.isdir(source):
        if not os.path.exists(os.path.join(source, "pyproject.toml")):
            notify_box(
                f"{source} is not a directory containing pyproject.toml",
                FileNotFoundError,
            )
        if git_tag:
            notify_box("unzipped code directory can not have a tag!", ValueError)
        if source.endswith("/"):
            source = source[:-1]
        package_string = f"{source}{extra_string}"
        return package_string

    # Handle installation from a zipped code archive
    if os.path.exists(source) and os.path.isfile(source):
        if git_tag:
            notify_box("zipped file can not have a tag!", ValueError)

        if source.endswith(".zip"):
            package_string = f"{source}{extra_string}"
        elif source.endswith(".tar.gz"):
            package_string = f"{source}{extra_string}"
        else:
            notify_box(
                f"{source} is neither a zipped file nor a tar.gz file!",
                FileNotFoundError,
            )

        return package_string

    notify_box(f"Unknown installation source {source}({package_name})!", ValueError)

# entrypoint of PyMOL plugin


def __init_plugin__(app=None):
    """
    Add an entry to the PyMOL "Plugin" menu
    """

    plugin = REvoDesignInstaller()
    addmenuitemqt("REvoDesign Installer", plugin.run_plugin_gui)

    try:
        from REvoDesign import REvoDesignPlugin

        plugin = REvoDesignPlugin()
        addmenuitemqt("REvoDesign", plugin.run_plugin_gui)
    except ImportError:
        traceback.print_exc()

        print("REvoDesign is not available.")
