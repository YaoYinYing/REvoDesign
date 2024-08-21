'''
Described at GitHub:
https://github.com/YaoYinYing/REvoDesign

Authors : Yinying Yao
Program : REvoDesign
Date    : Sept 2023

REvoDesign -- Makes enzyme redesign tasks easier to all.
'''

import subprocess
import time

import warnings
import traceback
import json
import os
import shutil

from typing import Iterable, Mapping, Optional, Union, Protocol

from dataclasses import dataclass
from contextlib import contextmanager


from pymol.Qt import QtCore, QtGui, QtWidgets

print(f'REvoDesign entrypoint is located at {os.path.dirname(__file__)}')


REPO_URL: str = 'https://github.com/YaoYinYing/REvoDesign'
AVAILABLE_EXTRAS: list = ['', 'tf', 'torch', 'jax', 'full', 'unittest']


def run_command(
    cmd: Union[tuple[str], str],
    verbose: bool = False,
    env: Mapping[str, str] = {},
) -> subprocess.CompletedProcess:
    """
    Execute a specified command in the shell.

    Parameters:
    - cmd: A tuple or string representing the command to be executed. If it's a tuple, it represents the command and its parameters.
    - verbose: A boolean indicating whether to print detailed execution information.
    - env: A mapping object containing environment variables for the command.

    Returns:
    - The CompletedProcess object returned by subprocess.run(), containing the command execution information.

    Raises:
    - When the command execution fails (return code is not 0) and verbose is True, a RuntimeError is raised.
    """
    # Optionally print the command for debugging
    if verbose:
        print(cmd)

    # Execute the command using subprocess.run()
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        env=env if env else None,
        universal_newlines=True,
    )

    # Optionally print the command output for debugging
    if verbose and (res_text := result.stdout):
        print(res_text)

    # If the command execution fails and verbose is True, raise an exception
    if result.returncode != 0 and verbose:
        raise RuntimeError(
            f"--> Command failed: \n{'-'*79}\n{result.stderr}\n{'-'*79}"
        )

    # Return the execution result
    return result


# translated UI Dialog from UI file\
class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(543, 402)
        Dialog.setMinimumSize(QtCore.QSize(543, 0))
        Dialog.setMaximumSize(QtCore.QSize(543, 16777215))
        Dialog.setToolTipDuration(2)
        self.groupBox = QtWidgets.QGroupBox(Dialog)
        self.groupBox.setGeometry(QtCore.QRect(10, 70, 521, 101))
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.groupBox.sizePolicy().hasHeightForWidth()
        )
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setObjectName("groupBox")
        self.horizontalLayoutWidget_2 = QtWidgets.QWidget(self.groupBox)
        self.horizontalLayoutWidget_2.setGeometry(
            QtCore.QRect(10, 30, 501, 64)
        )
        self.horizontalLayoutWidget_2.setObjectName("horizontalLayoutWidget_2")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(
            self.horizontalLayoutWidget_2
        )
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.radioButton_from_repo = QtWidgets.QRadioButton(
            self.horizontalLayoutWidget_2
        )
        self.radioButton_from_repo.setWhatsThis("")
        self.radioButton_from_repo.setChecked(True)
        self.radioButton_from_repo.setObjectName("radioButton_from_repo")
        self.horizontalLayout_3.addWidget(self.radioButton_from_repo)
        self.radioButton_from_local_clone = QtWidgets.QRadioButton(
            self.horizontalLayoutWidget_2
        )
        self.radioButton_from_local_clone.setWhatsThis("")
        self.radioButton_from_local_clone.setObjectName(
            "radioButton_from_local_clone"
        )
        self.horizontalLayout_3.addWidget(self.radioButton_from_local_clone)
        self.radioButton_from_local_file = QtWidgets.QRadioButton(
            self.horizontalLayoutWidget_2
        )
        self.radioButton_from_local_file.setWhatsThis("")
        self.radioButton_from_local_file.setObjectName(
            "radioButton_from_local_file"
        )
        self.horizontalLayout_3.addWidget(self.radioButton_from_local_file)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.lineEdit_local = QtWidgets.QLineEdit(
            self.horizontalLayoutWidget_2
        )
        self.lineEdit_local.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.lineEdit_local.sizePolicy().hasHeightForWidth()
        )
        self.lineEdit_local.setSizePolicy(sizePolicy)
        self.lineEdit_local.setWhatsThis("")
        self.lineEdit_local.setObjectName("lineEdit_local")
        self.horizontalLayout.addWidget(self.lineEdit_local)
        self.pushButton_open = QtWidgets.QPushButton(
            self.horizontalLayoutWidget_2
        )
        self.pushButton_open.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.pushButton_open.sizePolicy().hasHeightForWidth()
        )
        self.pushButton_open.setSizePolicy(sizePolicy)
        self.pushButton_open.setObjectName("pushButton_open")
        self.horizontalLayout.addWidget(self.pushButton_open)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_2.addLayout(self.verticalLayout)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.pushButton_install = QtWidgets.QPushButton(
            self.horizontalLayoutWidget_2
        )
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.pushButton_install.sizePolicy().hasHeightForWidth()
        )
        self.pushButton_install.setSizePolicy(sizePolicy)
        self.pushButton_install.setObjectName("pushButton_install")
        self.verticalLayout_2.addWidget(self.pushButton_install)
        self.pushButton_remove = QtWidgets.QPushButton(
            self.horizontalLayoutWidget_2
        )
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.pushButton_remove.sizePolicy().hasHeightForWidth()
        )
        self.pushButton_remove.setSizePolicy(sizePolicy)
        self.pushButton_remove.setObjectName("pushButton_remove")
        self.verticalLayout_2.addWidget(self.pushButton_remove)
        self.horizontalLayout_2.addLayout(self.verticalLayout_2)
        self.groupBox_2 = QtWidgets.QGroupBox(Dialog)
        self.groupBox_2.setGeometry(QtCore.QRect(10, 170, 521, 101))
        self.groupBox_2.setObjectName("groupBox_2")
        self.horizontalLayoutWidget_8 = QtWidgets.QWidget(self.groupBox_2)
        self.horizontalLayoutWidget_8.setGeometry(
            QtCore.QRect(10, 29, 501, 65)
        )
        self.horizontalLayoutWidget_8.setObjectName("horizontalLayoutWidget_8")
        self.horizontalLayout_8 = QtWidgets.QHBoxLayout(
            self.horizontalLayoutWidget_8
        )
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.label = QtWidgets.QLabel(self.horizontalLayoutWidget_8)
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.label.sizePolicy().hasHeightForWidth()
        )
        self.label.setSizePolicy(sizePolicy)
        self.label.setObjectName("label")
        self.horizontalLayout_4.addWidget(self.label)
        self.comboBox_extras = QtWidgets.QComboBox(
            self.horizontalLayoutWidget_8
        )
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.comboBox_extras.sizePolicy().hasHeightForWidth()
        )
        self.comboBox_extras.setSizePolicy(sizePolicy)
        self.comboBox_extras.setMaximumSize(QtCore.QSize(75, 16777215))
        self.comboBox_extras.setWhatsThis("")
        self.comboBox_extras.setObjectName("comboBox_extras")
        self.horizontalLayout_4.addWidget(self.comboBox_extras)
        self.verticalLayout_3.addLayout(self.horizontalLayout_4)
        self.horizontalLayout_7 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.checkBox_verbose = QtWidgets.QCheckBox(
            self.horizontalLayoutWidget_8
        )
        self.checkBox_verbose.setChecked(True)
        self.checkBox_verbose.setObjectName("checkBox_verbose")
        self.horizontalLayout_7.addWidget(self.checkBox_verbose)
        self.verticalLayout_3.addLayout(self.horizontalLayout_7)
        self.horizontalLayout_8.addLayout(self.verticalLayout_3)
        self.verticalLayout_4 = QtWidgets.QVBoxLayout()
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.horizontalLayout_5 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.checkBox_specified_version = QtWidgets.QCheckBox(
            self.horizontalLayoutWidget_8
        )
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.checkBox_specified_version.sizePolicy().hasHeightForWidth()
        )
        self.checkBox_specified_version.setSizePolicy(sizePolicy)
        self.checkBox_specified_version.setWhatsThis("")
        self.checkBox_specified_version.setObjectName(
            "checkBox_specified_version"
        )
        self.horizontalLayout_5.addWidget(self.checkBox_specified_version)
        self.comboBox_version = QtWidgets.QComboBox(
            self.horizontalLayoutWidget_8
        )
        self.comboBox_version.setEnabled(False)
        self.comboBox_version.setObjectName("comboBox_version")
        self.horizontalLayout_5.addWidget(self.comboBox_version)
        self.checkBox_upgrade = QtWidgets.QCheckBox(
            self.horizontalLayoutWidget_8
        )
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.checkBox_upgrade.sizePolicy().hasHeightForWidth()
        )
        self.checkBox_upgrade.setSizePolicy(sizePolicy)
        self.checkBox_upgrade.setStatusTip("")
        self.checkBox_upgrade.setChecked(True)
        self.checkBox_upgrade.setObjectName("checkBox_upgrade")
        self.horizontalLayout_5.addWidget(self.checkBox_upgrade)
        self.verticalLayout_4.addLayout(self.horizontalLayout_5)
        self.horizontalLayout_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.checkBox_specified_commit = QtWidgets.QCheckBox(
            self.horizontalLayoutWidget_8
        )
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.checkBox_specified_commit.sizePolicy().hasHeightForWidth()
        )
        self.checkBox_specified_commit.setSizePolicy(sizePolicy)
        self.checkBox_specified_commit.setObjectName(
            "checkBox_specified_commit"
        )
        self.horizontalLayout_6.addWidget(self.checkBox_specified_commit)
        self.lineEdit_commit = QtWidgets.QLineEdit(
            self.horizontalLayoutWidget_8
        )
        self.lineEdit_commit.setEnabled(False)
        self.lineEdit_commit.setObjectName("lineEdit_commit")
        self.horizontalLayout_6.addWidget(self.lineEdit_commit)
        self.verticalLayout_4.addLayout(self.horizontalLayout_6)
        self.horizontalLayout_8.addLayout(self.verticalLayout_4)
        self.label_2 = QtWidgets.QLabel(Dialog)
        self.label_2.setGeometry(QtCore.QRect(20, 20, 501, 41))
        font = QtGui.QFont()
        font.setPointSize(14)
        font.setBold(True)
        font.setItalic(True)
        font.setUnderline(False)
        font.setWeight(75)
        font.setStrikeOut(False)
        self.label_2.setFont(font)
        self.label_2.setFrameShape(QtWidgets.QFrame.Panel)
        self.label_2.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.label_2.setLineWidth(2)
        self.label_2.setMidLineWidth(0)
        self.label_2.setTextFormat(QtCore.Qt.RichText)
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_2.setObjectName("label_2")
        self.groupBox_3 = QtWidgets.QGroupBox(Dialog)
        self.groupBox_3.setGeometry(QtCore.QRect(10, 270, 521, 101))
        self.groupBox_3.setObjectName("groupBox_3")
        self.verticalLayoutWidget = QtWidgets.QWidget(self.groupBox_3)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 30, 501, 61))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout(
            self.verticalLayoutWidget
        )
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_5.setSpacing(0)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.horizontalLayout_9 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_9.setObjectName("horizontalLayout_9")
        self.checkBox_use_proxy = QtWidgets.QCheckBox(
            self.verticalLayoutWidget
        )
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.checkBox_use_proxy.sizePolicy().hasHeightForWidth()
        )
        self.checkBox_use_proxy.setSizePolicy(sizePolicy)
        self.checkBox_use_proxy.setObjectName("checkBox_use_proxy")
        self.horizontalLayout_9.addWidget(self.checkBox_use_proxy)
        self.lineEdit_proxy_url = QtWidgets.QLineEdit(
            self.verticalLayoutWidget
        )
        self.lineEdit_proxy_url.setEnabled(False)
        self.lineEdit_proxy_url.setObjectName("lineEdit_proxy_url")
        self.horizontalLayout_9.addWidget(self.lineEdit_proxy_url)
        self.verticalLayout_5.addLayout(self.horizontalLayout_9)
        self.horizontalLayout_10 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_10.setObjectName("horizontalLayout_10")
        self.checkBox_use_mirror = QtWidgets.QCheckBox(
            self.verticalLayoutWidget
        )
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.checkBox_use_mirror.sizePolicy().hasHeightForWidth()
        )
        self.checkBox_use_mirror.setSizePolicy(sizePolicy)
        self.checkBox_use_mirror.setObjectName("checkBox_use_mirror")
        self.horizontalLayout_10.addWidget(self.checkBox_use_mirror)
        self.lineEdit_mirror_url = QtWidgets.QLineEdit(
            self.verticalLayoutWidget
        )
        self.lineEdit_mirror_url.setEnabled(False)
        self.lineEdit_mirror_url.setObjectName("lineEdit_mirror_url")
        self.horizontalLayout_10.addWidget(self.lineEdit_mirror_url)
        self.verticalLayout_5.addLayout(self.horizontalLayout_10)
        self.progressBar = QtWidgets.QProgressBar(Dialog)
        self.progressBar.setGeometry(QtCore.QRect(10, 370, 521, 20))
        sizePolicy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.progressBar.sizePolicy().hasHeightForWidth()
        )
        self.progressBar.setSizePolicy(sizePolicy)
        self.progressBar.setMinimumSize(QtCore.QSize(0, 0))
        self.progressBar.setSizeIncrement(QtCore.QSize(0, 0))
        self.progressBar.setBaseSize(QtCore.QSize(0, 0))
        font = QtGui.QFont()
        font.setPointSize(3)
        self.progressBar.setFont(font)
        self.progressBar.setProperty("value", 0)
        self.progressBar.setAlignment(
            QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop
        )
        self.progressBar.setOrientation(QtCore.Qt.Horizontal)
        self.progressBar.setTextDirection(QtWidgets.QProgressBar.TopToBottom)
        self.progressBar.setObjectName("progressBar")

        self.retranslateUi(Dialog)
        self.radioButton_from_repo.toggled['bool'].connect(self.lineEdit_local.setDisabled)  # type: ignore
        self.radioButton_from_repo.toggled['bool'].connect(self.pushButton_open.setDisabled)  # type: ignore
        self.checkBox_specified_version.toggled['bool'].connect(self.comboBox_version.setEnabled)  # type: ignore
        self.checkBox_specified_commit.toggled['bool'].connect(self.lineEdit_commit.setEnabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(self.lineEdit_local.setEnabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(self.pushButton_open.setEnabled)  # type: ignore
        self.radioButton_from_local_file.toggled['bool'].connect(self.lineEdit_local.setEnabled)  # type: ignore
        self.radioButton_from_local_file.toggled['bool'].connect(self.pushButton_open.setEnabled)  # type: ignore
        self.radioButton_from_local_file.toggled['bool'].connect(self.comboBox_version.setDisabled)  # type: ignore
        self.checkBox_use_proxy.toggled['bool'].connect(self.lineEdit_proxy_url.setEnabled)  # type: ignore
        self.checkBox_use_mirror.toggled['bool'].connect(self.lineEdit_mirror_url.setEnabled)  # type: ignore
        self.radioButton_from_local_file.toggled['bool'].connect(self.checkBox_specified_version.setDisabled)  # type: ignore
        self.radioButton_from_local_file.toggled['bool'].connect(self.checkBox_specified_commit.setDisabled)  # type: ignore
        self.radioButton_from_local_file.toggled['bool'].connect(self.lineEdit_commit.setDisabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(self.comboBox_version.setDisabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(self.checkBox_specified_version.setDisabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(self.checkBox_specified_commit.setDisabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(self.lineEdit_commit.setDisabled)  # type: ignore
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "REvoDesign Installer"))
        self.groupBox.setTitle(_translate("Dialog", "Source:"))
        self.radioButton_from_repo.setToolTip(
            _translate("Dialog", "From GitHub repository")
        )
        self.radioButton_from_repo.setText(_translate("Dialog", "Repository"))
        self.radioButton_from_local_clone.setToolTip(
            _translate(
                "Dialog", "From project directory containing `pyproject.toml`"
            )
        )
        self.radioButton_from_local_clone.setText(
            _translate("Dialog", "Local clone")
        )
        self.radioButton_from_local_file.setToolTip(
            _translate("Dialog", "From released zip/tarball file")
        )
        self.radioButton_from_local_file.setText(
            _translate("Dialog", "Local file")
        )
        self.lineEdit_local.setToolTip(
            _translate("Dialog", "File/directory path to read")
        )
        self.lineEdit_local.setText(
            _translate(
                "Dialog", "/Users/yyy/Documents/protein_design/REvoDesign"
            )
        )
        self.pushButton_open.setText(_translate("Dialog", "..."))
        self.pushButton_install.setToolTip(
            _translate("Dialog", "Install REvoDesign")
        )
        self.pushButton_install.setText(_translate("Dialog", "Install"))
        self.pushButton_remove.setToolTip(
            _translate("Dialog", "Remove REvoDesign")
        )
        self.pushButton_remove.setText(_translate("Dialog", "Remove"))
        self.groupBox_2.setTitle(_translate("Dialog", "Options:"))
        self.label.setText(_translate("Dialog", "Extras:"))
        self.comboBox_extras.setToolTip(
            _translate("Dialog", "Extra definitions of dependencies.")
        )
        self.checkBox_verbose.setText(_translate("Dialog", "Verbose"))
        self.checkBox_specified_version.setToolTip(
            _translate("Dialog", "Install from a specific version")
        )
        self.checkBox_specified_version.setText(
            _translate("Dialog", "Version:")
        )
        self.comboBox_version.setToolTip(
            _translate("Dialog", "Install from a specific version number")
        )
        self.checkBox_upgrade.setToolTip(
            _translate("Dialog", "Upgrade to the latest")
        )
        self.checkBox_upgrade.setText(_translate("Dialog", "Upgrade"))
        self.checkBox_specified_commit.setToolTip(
            _translate("Dialog", "Install from a specific commit/branch")
        )
        self.checkBox_specified_commit.setText(_translate("Dialog", "commit:"))
        self.lineEdit_commit.setToolTip(
            _translate("Dialog", "Install from a specific commit/branch")
        )
        self.label_2.setText(
            _translate("Dialog", "REvoDesign Installation/Upgradation Tool")
        )
        self.groupBox_3.setTitle(_translate("Dialog", "Network:"))
        self.checkBox_use_proxy.setToolTip(
            _translate("Dialog", "Enable http proxy")
        )
        self.checkBox_use_proxy.setText(_translate("Dialog", "proxy:"))
        self.lineEdit_proxy_url.setToolTip(_translate("Dialog", "HTTP proxy"))
        self.lineEdit_proxy_url.setText(
            _translate("Dialog", "http://localhost:7890")
        )
        self.checkBox_use_mirror.setToolTip(
            _translate("Dialog", "Enable PyPi mirror")
        )
        self.checkBox_use_mirror.setText(_translate("Dialog", "Mirror:"))
        self.lineEdit_mirror_url.setToolTip(
            _translate("Dialog", "Set PyPi mirror URL")
        )
        self.lineEdit_mirror_url.setText(
            _translate("Dialog", "https://mirrors.bfsu.edu.cn/pypi/web/simple")
        )


@dataclass
class GitSolver:
    """
    A class that checks for the presence of Git, Conda, and Winget on the system and can install Git if necessary.
    """

    __slots__ = ['has_git', 'has_conda', 'has_winget']

    def __post_init__(self):
        """
        Initializes instance attributes to check if git, conda, and winget are installed.

        This method is automatically called after the object initialization.
        It sets the object's properties based on whether these tools are available in the system path.
        This ensures that the object can determine if it can perform related operations before doing so.
        """
        for c in ['git', 'conda', 'winget']:
            setattr(self, f'has_{c}', shutil.which(c) is not None)

    def fetch_git(self, env: Optional[Mapping[str, str]]):
        """
        Installs Git if it is not present on the system.

        This method attempts to install Git based on the available installers (Conda, Winget) or the system type.
        If the installation is successful, it returns True. Otherwise, it provides error information and returns False.

        Parameters:
            env (Optional[Mapping[str, str]]): Environment variables for the installation process.
        """
        import platform

        # Check if Git is already installed
        if self.has_git:
            return True

        # Get system information for conditional logic
        uname_info = platform.uname()

        # Determine the installation command based on Conda's presence or the system type (Windows with Winget)
        if self.has_conda:
            cmd = ['conda', 'install', '-y', 'git']
        elif uname_info.system == "Windows" and self.has_winget:
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
        else:
            # If neither Conda nor Winget is present, prompt the user to install Git manually
            notify_box(
                message='Git is required to install REvoDesign. Please install Git first.\n'
                'See https://git-scm.com/downloads',
            )
            return False

        # Prompt the user for confirmation to install Git
        confirmed = proceed_with_comfirm_msg_box(
            title='Install Git?',
            description=f'Do you want to install git first?\n command:\n {" ".join(cmd)}',
        )
        if not confirmed:
            # If the user cancels the installation, notify and return
            notify_box(message='Git installation is cancelled.')
            return False

        # Execute the Git installation command in a worker thread and monitor progress
        git_install_std: subprocess.CompletedProcess = run_command(
            cmd=cmd,
            verbose=True,
            env=env,
        )

        # Check if the Git installation was successful
        if (
            git_install_std
            and git_install_std.returncode == 0
            and self.has_git
        ):
            # If successful, show a notification and return True
            notify_box(message=f'Git installed successfully.')
            return True
        else:
            # If installation failed, show error information and return False
            try:
                stdout, stderr = git_install_std.stdout, git_install_std.stderr
            except UnicodeDecodeError as e:
                with open((fp := os.path.abspath('error.log')), 'w') as f:
                    f.write(f'STDOUT:\n{stdout}\n\n\n\nSTDERR:\n{stderr}')

                notify_box(
                    message=f'Git not installed due to {e}.\n Error details saved to {fp}\n',
                    error_type=RuntimeError,
                )


@dataclass
class REvoDesignInstaller:

    dialog = None

    def run_plugin_gui(self):
        if self.dialog is None:
            self.dialog = self.make_window()
        self.dialog.show()
        run_worker_thread_with_progress(
            worker_function=self.fetch_tags, progress_bar=self.ui.progressBar
        )

    @staticmethod
    def proxy_in_env(proxy: str) -> Mapping[str, str]:
        """
        Generates an environment mapping based on the provided proxy string.

        Args:
            proxy (str): The proxy string to use for creating the environment variables.

        Returns:
            Mapping[str, str]: A dictionary containing the proxy settings for environment variables.
                            If `proxy` is empty, returns an empty dictionary.
        """

        if not proxy:
            return {}

        print(f'using proxy: {proxy}')
        proxy_env = {
            'http_proxy': proxy,
            'https_proxy': proxy,
            'all_proxy': proxy,
        }
        return proxy_env

    def make_window(self) -> QtWidgets.QDialog:  # type: ignore
        self.ui = Ui_Dialog()

        dialog = QtWidgets.QDialog()
        self.ui.setupUi(Dialog=dialog)
        self.ui.pushButton_open.clicked.connect(self.open_files)
        self.ui.pushButton_install.clicked.connect(self.install)
        self.ui.pushButton_remove.clicked.connect(self.uninstall)

        set_widget_value(self.ui.comboBox_extras, AVAILABLE_EXTRAS)
        return dialog

    def fetch_tags(self) -> list:
        set_widget_value(
            self.ui.comboBox_version, get_github_repo_tags(repo_url=REPO_URL)
        )

    # a copy from `REvoDesign/tools/customized_widgets.py`
    def getExistingDirectory(self):
        return QtWidgets.QFileDialog.getExistingDirectory(
            None,
            "Open Directory",
            os.path.expanduser('~'),
            QtWidgets.QFileDialog.DontResolveSymlinks,
        )

    # a copy from `REvoDesign/tools/customized_widgets.py`
    # an open file version of pymol.Qt.utils.getSaveFileNameWithExt ;-)
    def getOpenFileNameWithExt(self, *args, **kwargs):
        """
        Return a file name, append extension from filter if no extension provided.
        """
        import re

        fname, filter = QtWidgets.QFileDialog.getOpenFileName(*args, **kwargs)

        if not fname:
            return ''

        if '.' not in os.path.split(fname)[-1]:
            m = re.search(r'\*(\.[\w\.]+)', filter)
            if m:
                # append first extension from filter
                fname += m.group(1)

        return fname

    def open_files(self):
        from_local_clone = self.ui.radioButton_from_local_clone.isChecked()
        from_local_file = self.ui.radioButton_from_local_file.isChecked()

        if from_local_clone:
            dir = self.getExistingDirectory()
            if dir and os.path.exists(dir):
                set_widget_value(self.ui.lineEdit_local, dir)

        elif from_local_file:
            ext = {'zip': "ZIP archive", 'tar.gz': "Tarball (TAR.GZ)"}
            file = self.getOpenFileNameWithExt(
                self.dialog,
                'Open',
                filter=';;'.join(
                    [
                        f'{ext_discrition} ( *.{ext_} )'
                        for ext_, ext_discrition in ext.items()
                    ]
                ),
            )
            if file and os.path.exists(file):
                set_widget_value(self.ui.lineEdit_local, file)

    def uninstall(self):
        import importlib

        installed = importlib.util.find_spec('REvoDesign') is not None

        if not installed:
            notify_box(message='REvoDesign is not installed.')
            return

        with hold_trigger_button(self.ui.pushButton_remove):
            ret: subprocess.CompletedProcess = run_worker_thread_with_progress(
                worker_function=install_via_pip,
                uninstall=True,
                progress_bar=self.ui.progressBar,
            )

            if not ret.returncode:
                notify_box(
                    message='REvoDesign is removed successfully. Bye-bye.',
                )
                return
            notify_box(
                message='Failed to remove REvoDesign.', error_type=RuntimeError
            )

    def install(self):
        # sources
        from_repo = self.ui.radioButton_from_repo.isChecked()
        from_local_clone = self.ui.radioButton_from_local_clone.isChecked()
        from_local_file = self.ui.radioButton_from_local_file.isChecked()
        local_source: str = self.ui.lineEdit_local.text()

        extras = self.ui.comboBox_extras.currentText()
        upgrade = self.ui.checkBox_upgrade.isChecked()
        verbose = self.ui.checkBox_verbose.isChecked()

        # version tags
        use_version = self.ui.checkBox_specified_version.isChecked()
        target_version = self.ui.comboBox_version.currentText()

        # git commits
        use_commit = self.ui.checkBox_specified_commit.isChecked()
        target_commit = self.ui.lineEdit_commit.text()

        # networking
        use_proxy = self.ui.checkBox_use_proxy.isChecked()
        proxy_url = self.ui.lineEdit_proxy_url.text()

        use_mirror = self.ui.checkBox_use_mirror.isChecked()
        mirror_url = self.ui.lineEdit_mirror_url.text()

        if from_repo:
            install_source = REPO_URL
            if use_version and target_version:
                install_source += f'@{target_version}'
            elif use_commit and target_commit:
                install_source += f'@{target_commit}'

        elif from_local_clone:
            install_source = local_source
            if not local_source:
                notify_box(f'Empty local dir: {local_source}', ValueError)
            if not os.path.exists(local_source):
                notify_box(f'dir not exists: {local_source}', ValueError)

            if not os.path.isdir(local_source):
                notify_box(
                    f'{local_source} not a directory', FileNotFoundError
                )

            if use_version and target_version:
                install_source = f'file://{install_source}@{target_version}'
            elif use_commit and target_commit:
                install_source = f'file://{install_source}@{target_commit}'
        elif from_local_file:
            install_source = local_source
            if not os.path.exists(local_source):
                notify_box(f'{local_source} is not found.', FileNotFoundError)
            if not os.path.isfile(local_source):
                notify_box(f'{local_source} is not a file.', ValueError)
            if not (
                local_source.endswith('.zip')
                or local_source.endswith('.tar.gz')
            ):
                notify_box(
                    f'{local_source} must be a .zip or .tar.gz file!',
                    ValueError,
                )
            if use_version or use_commit or target_version or target_commit:
                print(
                    f'WARNING: installation from zip/tar file cannot use specified version/commit.'
                )
            install_source = local_source

        if not install_source:
            notify_box(
                'Installation configuration is failed. Aborded. ', ValueError
            )

        env = {}

        env.update(
            self.proxy_in_env(
                proxy=proxy_url if (use_proxy and proxy_url) else None
            )
        )

        with hold_trigger_button(self.ui.pushButton_install):
            ensure_lower_pip(env=env)
            git_solver = GitSolver()
            has_git = run_worker_thread_with_progress(
                worker_function=git_solver.fetch_git,
                env=env,
                progress_bar=self.ui.progressBar,
            )

            if not has_git:
                return

            installed: Union[subprocess.CompletedProcess, None] = (
                run_worker_thread_with_progress(
                    worker_function=install_via_pip,
                    progress_bar=self.ui.progressBar,
                    source=install_source,
                    upgrade=upgrade,
                    verbose=verbose,
                    extras=extras,
                    env=env,
                    mirror=mirror_url if (use_mirror and mirror_url) else '',
                )
            )
            if isinstance(installed,subprocess.CompletedProcess ) and installed.returncode == 0:
                notify_box(
                    message='Installation succeeded. \nIf this is an upgrade, please restart PyMOL for it to take effect.',
                )
                return

            notify_box(
                message=f'Installation failed from: {install_source} \n',
                error_type=RuntimeError,
            )


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
        if not self.isInterruptionRequested():
            self.results = [self.func(*self.args, **self.kwargs)]
            if self.results:
                self.result_signal.emit(self.results)
            self.finished_signal.emit()

    def handle_result(self):
        return self.results

    def interrupt(self):
        self.interrupt_signal.emit()


class QtProgressBarHint(Protocol):
    def minimum(self) -> int: ...
    def maximum(self) -> int: ...
    def value(self) -> int: ...
    def setRange(self, min: int, max: int): ...
    def setValue(self, value: int): ...


# a copy from `REvoDesign/tools/utils.py`
def run_worker_thread_with_progress(
    worker_function, progress_bar=Optional[QtProgressBarHint], *args, **kwargs
):
    if progress_bar:
        # store the progress bar state
        _min = progress_bar.minimum()
        _max = progress_bar.maximum()
        _val = progress_bar.value()

        progress_bar.setRange(0, 0)

    work_thread = WorkerThread(worker_function, args=args, kwargs=kwargs)
    work_thread.start()

    while not work_thread.isFinished():
        refresh_window()
        time.sleep(0.001)

    if progress_bar:
        # restore the progressbar state
        progress_bar.setRange(_min, _max)
        progress_bar.setValue(_val)

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
    import urllib.request

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
            tag_names = [tag['name'] for tag in tags]
            return tag_names
    except urllib.error.HTTPError as e:
        # Handle HTTP errors (e.g., repository not found, rate limit exceeded)
        print(f"Error: GitHub API returned status code {e.code}")
        return []
    except urllib.error.URLError as e:
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

    class UnsupportedWidgetValueTypeError(TypeError): ...

    # Preprocess values according to types
    if callable(value):
        value = (
            value()
        )  # Call the function to get the value if value is callable

    if isinstance(value, Iterable) and not isinstance(
        value, (str, list, tuple, dict)
    ):
        value = list(
            value
        )  # Convert iterable (excluding strings, lists, tuples, dicts) to list

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
            f'Invalid value {value} for QProgressBar. Value must be an integer or a list/tuple of two integers.'
        )
    if isinstance(widget, QtWidgets.QCheckBox):
        widget.setChecked(bool(value))
        return

    raise UnsupportedWidgetValueTypeError(
        f'FIX ME: Value {value} is not currently supported on widget {type(widget).__name__}'
    )


# a copy from `REvoDesign/tools/customized_widgets.py`
def refresh_window():
    QtWidgets.QApplication.processEvents()


# a copy from `REvoDesign/tools/customized_widgets.py`
def notify_box(
    message: str = '', error_type: Optional[Union[Exception, Warning]] = None
):
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
    if isinstance(error_type(), Warning):
        warnings.warn(error_type(message))
        return True

    # otherwise raise the exception
    if isinstance(error_type(), Exception):
        raise error_type(message)


# a copy from `REvoDesign/tools/customized_widgets.py`
def proceed_with_comfirm_msg_box(title='', description=''):
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
    msg.setStandardButtons(
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
    )
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
    source: str, git_url: str, git_tag: str, extras: str
):
    package_string = f"REvoDesign{f'[{extras}]' if extras and extras in AVAILABLE_EXTRAS else ''}"

    # with github url and tag
    if source and source.startswith('https://'):
        package_string += f' @ git+{git_url}{f"@{git_tag}" if git_tag else ""}'
        return package_string

    # with git repo clone and tag
    if source.startswith('file://'):
        dir = git_url.replace('file://', '')
        if not os.path.exists(os.path.join(dir, '.git')):
            notify_box(f'Git dir not found: {os.path.join(dir, ".git")}')
        package_string += f' @ git+{git_url}{f"@{git_tag}" if git_tag else ""}'
        return package_string

    # with unzipped code dir
    if os.path.exists(source) and os.path.isdir(source):
        if not os.path.exists(os.path.join(source, 'pyproject.toml')):
            notify_box(
                f'{source} is not a directory containing pyproject.toml',
                FileNotFoundError,
            )
        if git_tag:
            notify_box(
                'unzipped code directory can not have a tag!', ValueError
            )
        if source.endswith('/'):
            source = source[:-1]
        package_string = f"{source}{f'[{extras}]'if extras else ''}"
        return package_string

    # with zipped code archive
    if os.path.exists(source) and os.path.isfile(source):
        if git_tag:
            notify_box('zipped file can not have a tag!', ValueError)

        if source.endswith('.zip'):
            package_string = f"{source}{f'[{extras}]'if extras else ''}"
        elif source.endswith('.tar.gz'):
            package_string = f"{source}{f'[{extras}]'if extras else ''}"
        else:
            notify_box(
                f'{source} is neither a zipped file nor a tar.gz file!',
                FileNotFoundError,
            )

        return package_string

    notify_box(f'Unknown installation source {source}!', ValueError)


def ensure_lower_pip(env: Optional[Mapping[str, str]]):
    """
    Ensure the pip version is lower than 24.0, as REvoDesign installation requires pip<24.0.

    Parameters:
    - env: Optional[Mapping[str, str]] - The environment variables for the pip installation command, optional.

    Returns:
    None
    """
    # Import necessary modules
    import sys
    import warnings
    import pip

    # Get the current pip version number
    pip_ver: float = float(pip.__version__.split('.')[0])
    # If the pip version is already lower than 24.0, no action is needed
    if pip_ver < 24.0:
        return

    # Warn the user that pip>=24.0 will be required for future REvoDesign installations
    warnings.warn(
        FutureWarning(
            'pip>=24.0 will be required for REvoDesign installation.'
        )
    )

    # Get the absolute path of the current Python executable
    python_exe = os.path.realpath(sys.executable)
    # Construct the command to install a specific version of pip
    pip_cmd = [python_exe, '-m', 'pip', 'install', '-U', 'pip<24.0', '-q']

    # Execute the pip installation command
    result = run_command(pip_cmd, verbose=True, env=env)
    # If the pip downgrade command fails, notify the user to manually execute the command
    if result.returncode:
        notify_box(
            'Failed to downgrade pip. Please upgrade/downgrade pip<24.0 manually.\n'
            f'Run this command in your shell - `{" ".join(pip_cmd)}`'
        )


def install_via_pip(
    source=REPO_URL,
    upgrade=0,
    verbose=1,
    extras='',
    mirror='',
    uninstall=False,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess:
    def get_source_and_tag(source):
        git_dir = source.split('@')[0]
        if '@' in source:
            git_tag = source.split('@')[1]
        else:
            git_tag = ''
        return git_dir, git_tag

    import sys

    upgrade = int(upgrade)
    verbose = int(verbose)

    print(
        'Installation is started. This may take a while and the window will freeze until it is done.'
    )

    python_exe = os.path.realpath(sys.executable)

    # run installation via pip
    ensurepip = run_command(
        [python_exe, '-m', 'ensurepip'], verbose=verbose, env=env
    )
    if ensurepip.returncode:
        notify_box('ensurepip failed.')
        return None

    if uninstall:
        pip_cmd = [
            python_exe,
            '-m',
            'pip',
            'uninstall',
            '-y',
            'REvoDesign',
        ]
    else:
        # use default source
        if not source:
            source = REPO_URL

        git_url, git_tag = get_source_and_tag(source=source)

        package_string = solve_installation_config(
            source=source, git_url=git_url, git_tag=git_tag, extras=extras
        )
        pip_cmd = [
            python_exe,
            '-m',
            'pip',
            'install',
            f"{package_string}",
        ]

        if upgrade:
            pip_cmd.append('--upgrade')

        if mirror:
            print(f'using mirror from {mirror}')
            pip_cmd.extend(['-i', mirror])

    result: subprocess.CompletedProcess = run_command(
        pip_cmd, verbose=verbose, env=env
    )

    return result


# entrypoint of PyMOL plugin
def __init_plugin__(app=None):
    '''
    Add an entry to the PyMOL "Plugin" menu
    '''
    from pymol.plugins import addmenuitemqt

    plugin = REvoDesignInstaller()
    addmenuitemqt('REvoDesign Installer', plugin.run_plugin_gui)

    try:
        from REvoDesign import REvoDesignPlugin

        plugin = REvoDesignPlugin()
        addmenuitemqt('REvoDesign', plugin.run_plugin_gui)
    except ImportError:
        traceback.print_exc()

        print('REvoDesign is not available.')
