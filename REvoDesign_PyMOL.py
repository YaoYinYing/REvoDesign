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
from typing import (Callable, Dict, Iterable, List, Mapping, Optional,
                    Protocol, Tuple, TypeVar, Union)
from urllib.error import HTTPError, URLError

import pip
from pymol.plugins import addmenuitemqt
from pymol.Qt import QtCore, QtGui, QtWidgets  # type: ignore

print(f"REvoDesign entrypoint is located at {os.path.dirname(__file__)}")


REPO_URL: str = "https://github.com/YaoYinYing/REvoDesign"


# Define the URL of the JSON file
EXTRAS_TABLE_JSON = "https://gist.githubusercontent.com/YaoYinYing/37e0e8e73951fab3a12b2d8b81791f6a/raw"

# Fetch and validate JSON data


def fetch_extras(url: str) -> Dict[str, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # Set a timeout for safety
            data = response.read().decode('utf-8')
            json_data = json.loads(data)
            print(f'Extras table is fetched and parsed: \n'
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


# copied translated UI Dialog class from UI file
# ui: src/REvoDesign/UI/REvoDesign-PyMOL-entry.ui
# translated: src/REvoDesign/UI/Ui_REvoDesign-PyMOL-entry.py

class Ui_Dialog:
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(490, 534)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Dialog.sizePolicy().hasHeightForWidth())
        Dialog.setSizePolicy(sizePolicy)
        Dialog.setMinimumSize(QtCore.QSize(490, 534))
        Dialog.setMaximumSize(QtCore.QSize(652, 547))
        Dialog.setToolTipDuration(2)
        self.groupBox = QtWidgets.QGroupBox(Dialog)
        self.groupBox.setGeometry(QtCore.QRect(10, 70, 471, 101))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setObjectName("groupBox")
        self.horizontalLayoutWidget_2 = QtWidgets.QWidget(self.groupBox)
        self.horizontalLayoutWidget_2.setGeometry(QtCore.QRect(10, 30, 451, 64))
        self.horizontalLayoutWidget_2.setObjectName("horizontalLayoutWidget_2")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget_2)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.radioButton_from_repo = QtWidgets.QRadioButton(self.horizontalLayoutWidget_2)
        self.radioButton_from_repo.setWhatsThis("")
        self.radioButton_from_repo.setChecked(True)
        self.radioButton_from_repo.setObjectName("radioButton_from_repo")
        self.horizontalLayout_3.addWidget(self.radioButton_from_repo)
        self.radioButton_from_local_clone = QtWidgets.QRadioButton(self.horizontalLayoutWidget_2)
        self.radioButton_from_local_clone.setWhatsThis("")
        self.radioButton_from_local_clone.setObjectName("radioButton_from_local_clone")
        self.horizontalLayout_3.addWidget(self.radioButton_from_local_clone)
        self.radioButton_from_local_file = QtWidgets.QRadioButton(self.horizontalLayoutWidget_2)
        self.radioButton_from_local_file.setWhatsThis("")
        self.radioButton_from_local_file.setObjectName("radioButton_from_local_file")
        self.horizontalLayout_3.addWidget(self.radioButton_from_local_file)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.lineEdit_local = QtWidgets.QLineEdit(self.horizontalLayoutWidget_2)
        self.lineEdit_local.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_local.sizePolicy().hasHeightForWidth())
        self.lineEdit_local.setSizePolicy(sizePolicy)
        self.lineEdit_local.setWhatsThis("")
        self.lineEdit_local.setObjectName("lineEdit_local")
        self.horizontalLayout.addWidget(self.lineEdit_local)
        self.pushButton_open = QtWidgets.QPushButton(self.horizontalLayoutWidget_2)
        self.pushButton_open.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_open.sizePolicy().hasHeightForWidth())
        self.pushButton_open.setSizePolicy(sizePolicy)
        self.pushButton_open.setObjectName("pushButton_open")
        self.horizontalLayout.addWidget(self.pushButton_open)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_2.addLayout(self.verticalLayout)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.pushButton_install = QtWidgets.QPushButton(self.horizontalLayoutWidget_2)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_install.sizePolicy().hasHeightForWidth())
        self.pushButton_install.setSizePolicy(sizePolicy)
        self.pushButton_install.setObjectName("pushButton_install")
        self.verticalLayout_2.addWidget(self.pushButton_install)
        self.pushButton_remove = QtWidgets.QPushButton(self.horizontalLayoutWidget_2)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_remove.sizePolicy().hasHeightForWidth())
        self.pushButton_remove.setSizePolicy(sizePolicy)
        self.pushButton_remove.setObjectName("pushButton_remove")
        self.verticalLayout_2.addWidget(self.pushButton_remove)
        self.horizontalLayout_2.addLayout(self.verticalLayout_2)
        self.groupBox_2 = QtWidgets.QGroupBox(Dialog)
        self.groupBox_2.setGeometry(QtCore.QRect(10, 170, 471, 101))
        self.groupBox_2.setObjectName("groupBox_2")
        self.horizontalLayoutWidget_8 = QtWidgets.QWidget(self.groupBox_2)
        self.horizontalLayoutWidget_8.setGeometry(QtCore.QRect(10, 29, 451, 65))
        self.horizontalLayoutWidget_8.setObjectName("horizontalLayoutWidget_8")
        self.horizontalLayout_8 = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget_8)
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.checkBox_upgrade = QtWidgets.QCheckBox(self.horizontalLayoutWidget_8)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.checkBox_upgrade.sizePolicy().hasHeightForWidth())
        self.checkBox_upgrade.setSizePolicy(sizePolicy)
        self.checkBox_upgrade.setStatusTip("")
        self.checkBox_upgrade.setChecked(True)
        self.checkBox_upgrade.setObjectName("checkBox_upgrade")
        self.horizontalLayout_4.addWidget(self.checkBox_upgrade)
        self.verticalLayout_3.addLayout(self.horizontalLayout_4)
        self.horizontalLayout_7 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.checkBox_verbose = QtWidgets.QCheckBox(self.horizontalLayoutWidget_8)
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
        self.checkBox_specified_version = QtWidgets.QCheckBox(self.horizontalLayoutWidget_8)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.checkBox_specified_version.sizePolicy().hasHeightForWidth())
        self.checkBox_specified_version.setSizePolicy(sizePolicy)
        self.checkBox_specified_version.setWhatsThis("")
        self.checkBox_specified_version.setObjectName("checkBox_specified_version")
        self.horizontalLayout_5.addWidget(self.checkBox_specified_version)
        self.comboBox_version = QtWidgets.QComboBox(self.horizontalLayoutWidget_8)
        self.comboBox_version.setEnabled(False)
        self.comboBox_version.setObjectName("comboBox_version")
        self.horizontalLayout_5.addWidget(self.comboBox_version)
        self.verticalLayout_4.addLayout(self.horizontalLayout_5)
        self.horizontalLayout_6 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.checkBox_specified_commit = QtWidgets.QCheckBox(self.horizontalLayoutWidget_8)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.checkBox_specified_commit.sizePolicy().hasHeightForWidth())
        self.checkBox_specified_commit.setSizePolicy(sizePolicy)
        self.checkBox_specified_commit.setObjectName("checkBox_specified_commit")
        self.horizontalLayout_6.addWidget(self.checkBox_specified_commit)
        self.lineEdit_commit = QtWidgets.QLineEdit(self.horizontalLayoutWidget_8)
        self.lineEdit_commit.setEnabled(False)
        self.lineEdit_commit.setObjectName("lineEdit_commit")
        self.horizontalLayout_6.addWidget(self.lineEdit_commit)
        self.verticalLayout_4.addLayout(self.horizontalLayout_6)
        self.horizontalLayout_8.addLayout(self.verticalLayout_4)
        self.label_2 = QtWidgets.QLabel(Dialog)
        self.label_2.setGeometry(QtCore.QRect(20, 20, 451, 41))
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
        self.groupBox_3.setGeometry(QtCore.QRect(10, 270, 471, 101))
        self.groupBox_3.setObjectName("groupBox_3")
        self.verticalLayoutWidget = QtWidgets.QWidget(self.groupBox_3)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 30, 451, 61))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout_5 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_5.setSpacing(0)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.horizontalLayout_9 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_9.setObjectName("horizontalLayout_9")
        self.checkBox_use_proxy = QtWidgets.QCheckBox(self.verticalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.checkBox_use_proxy.sizePolicy().hasHeightForWidth())
        self.checkBox_use_proxy.setSizePolicy(sizePolicy)
        self.checkBox_use_proxy.setObjectName("checkBox_use_proxy")
        self.horizontalLayout_9.addWidget(self.checkBox_use_proxy)
        self.lineEdit_proxy_url = QtWidgets.QLineEdit(self.verticalLayoutWidget)
        self.lineEdit_proxy_url.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_proxy_url.sizePolicy().hasHeightForWidth())
        self.lineEdit_proxy_url.setSizePolicy(sizePolicy)
        self.lineEdit_proxy_url.setObjectName("lineEdit_proxy_url")
        self.horizontalLayout_9.addWidget(self.lineEdit_proxy_url)
        self.verticalLayout_5.addLayout(self.horizontalLayout_9)
        self.horizontalLayout_10 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_10.setObjectName("horizontalLayout_10")
        self.checkBox_use_mirror = QtWidgets.QCheckBox(self.verticalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.checkBox_use_mirror.sizePolicy().hasHeightForWidth())
        self.checkBox_use_mirror.setSizePolicy(sizePolicy)
        self.checkBox_use_mirror.setObjectName("checkBox_use_mirror")
        self.horizontalLayout_10.addWidget(self.checkBox_use_mirror)
        self.lineEdit_mirror_url = QtWidgets.QLineEdit(self.verticalLayoutWidget)
        self.lineEdit_mirror_url.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEdit_mirror_url.sizePolicy().hasHeightForWidth())
        self.lineEdit_mirror_url.setSizePolicy(sizePolicy)
        self.lineEdit_mirror_url.setObjectName("lineEdit_mirror_url")
        self.horizontalLayout_10.addWidget(self.lineEdit_mirror_url)
        self.verticalLayout_5.addLayout(self.horizontalLayout_10)
        self.groupBox_4 = QtWidgets.QGroupBox(Dialog)
        self.groupBox_4.setGeometry(QtCore.QRect(10, 430, 471, 71))
        self.groupBox_4.setObjectName("groupBox_4")
        self.horizontalLayoutWidget = QtWidgets.QWidget(self.groupBox_4)
        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(10, 30, 451, 33))
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayout_11 = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout_11.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_11.setObjectName("horizontalLayout_11")
        self.checkBox_user_cache_dir = QtWidgets.QCheckBox(self.horizontalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.checkBox_user_cache_dir.sizePolicy().hasHeightForWidth())
        self.checkBox_user_cache_dir.setSizePolicy(sizePolicy)
        self.checkBox_user_cache_dir.setWhatsThis("")
        self.checkBox_user_cache_dir.setObjectName("checkBox_user_cache_dir")
        self.horizontalLayout_11.addWidget(self.checkBox_user_cache_dir)
        self.lineEdit_customized_cache_dir = QtWidgets.QLineEdit(self.horizontalLayoutWidget)
        self.lineEdit_customized_cache_dir.setEnabled(False)
        self.lineEdit_customized_cache_dir.setObjectName("lineEdit_customized_cache_dir")
        self.horizontalLayout_11.addWidget(self.lineEdit_customized_cache_dir)
        self.pushButton_open_cache_dir = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        self.pushButton_open_cache_dir.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_open_cache_dir.sizePolicy().hasHeightForWidth())
        self.pushButton_open_cache_dir.setSizePolicy(sizePolicy)
        self.pushButton_open_cache_dir.setObjectName("pushButton_open_cache_dir")
        self.horizontalLayout_11.addWidget(self.pushButton_open_cache_dir)
        self.pushButton_set_cache_dir = QtWidgets.QPushButton(self.horizontalLayoutWidget)
        self.pushButton_set_cache_dir.setEnabled(False)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.pushButton_set_cache_dir.sizePolicy().hasHeightForWidth())
        self.pushButton_set_cache_dir.setSizePolicy(sizePolicy)
        self.pushButton_set_cache_dir.setObjectName("pushButton_set_cache_dir")
        self.horizontalLayout_11.addWidget(self.pushButton_set_cache_dir)
        self.groupBox_5 = QtWidgets.QGroupBox(Dialog)
        self.groupBox_5.setGeometry(QtCore.QRect(10, 370, 471, 61))
        self.groupBox_5.setObjectName("groupBox_5")
        self.layoutWidget = QtWidgets.QWidget(self.groupBox_5)
        self.layoutWidget.setGeometry(QtCore.QRect(10, 30, 451, 21))
        self.layoutWidget.setObjectName("layoutWidget")
        self.horizontalLayout_12 = QtWidgets.QHBoxLayout(self.layoutWidget)
        self.horizontalLayout_12.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_12.setObjectName("horizontalLayout_12")
        self.radioButton_extra_none = QtWidgets.QRadioButton(self.layoutWidget)
        self.radioButton_extra_none.setWhatsThis("")
        self.radioButton_extra_none.setChecked(True)
        self.radioButton_extra_none.setObjectName("radioButton_extra_none")
        self.horizontalLayout_12.addWidget(self.radioButton_extra_none)
        self.radioButton_extra_customized = QtWidgets.QRadioButton(self.layoutWidget)
        self.radioButton_extra_customized.setWhatsThis("")
        self.radioButton_extra_customized.setObjectName("radioButton_extra_customized")
        self.horizontalLayout_12.addWidget(self.radioButton_extra_customized)
        self.radioButton_extra_everything = QtWidgets.QRadioButton(self.layoutWidget)
        self.radioButton_extra_everything.setWhatsThis("")
        self.radioButton_extra_everything.setChecked(False)
        self.radioButton_extra_everything.setObjectName("radioButton_extra_everything")
        self.horizontalLayout_12.addWidget(self.radioButton_extra_everything)
        self.progressBar = QtWidgets.QProgressBar(Dialog)
        self.progressBar.setGeometry(QtCore.QRect(10, 510, 471, 16))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.progressBar.sizePolicy().hasHeightForWidth())
        self.progressBar.setSizePolicy(sizePolicy)
        self.progressBar.setMinimumSize(QtCore.QSize(0, 0))
        self.progressBar.setSizeIncrement(QtCore.QSize(0, 0))
        self.progressBar.setBaseSize(QtCore.QSize(0, 0))
        font = QtGui.QFont()
        font.setPointSize(3)
        self.progressBar.setFont(font)
        self.progressBar.setProperty("value", 0)
        self.progressBar.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self.progressBar.setOrientation(QtCore.Qt.Horizontal)
        self.progressBar.setTextDirection(QtWidgets.QProgressBar.TopToBottom)
        self.progressBar.setObjectName("progressBar")
        self.listView_extras = QtWidgets.QListView(Dialog)
        self.listView_extras.setGeometry(QtCore.QRect(490, 90, 151, 431))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.listView_extras.sizePolicy().hasHeightForWidth())
        self.listView_extras.setSizePolicy(sizePolicy)
        self.listView_extras.setObjectName("listView_extras")

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
        self.radioButton_from_local_file.toggled['bool'].connect(
            self.checkBox_specified_version.setDisabled)  # type: ignore
        self.radioButton_from_local_file.toggled['bool'].connect(
            self.checkBox_specified_commit.setDisabled)  # type: ignore
        self.radioButton_from_local_file.toggled['bool'].connect(self.lineEdit_commit.setDisabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(self.comboBox_version.setDisabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(
            self.checkBox_specified_version.setDisabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(
            self.checkBox_specified_commit.setDisabled)  # type: ignore
        self.radioButton_from_local_clone.toggled['bool'].connect(self.lineEdit_commit.setDisabled)  # type: ignore
        self.checkBox_user_cache_dir.toggled['bool'].connect(
            self.lineEdit_customized_cache_dir.setEnabled)  # type: ignore
        self.checkBox_user_cache_dir.toggled['bool'].connect(self.pushButton_open_cache_dir.setEnabled)  # type: ignore
        self.checkBox_user_cache_dir.toggled['bool'].connect(self.pushButton_set_cache_dir.setEnabled)  # type: ignore
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "REvoDesign Installer"))
        self.groupBox.setTitle(_translate("Dialog", "Source:"))
        self.radioButton_from_repo.setToolTip(_translate("Dialog", "From GitHub repository"))
        self.radioButton_from_repo.setText(_translate("Dialog", "Repository"))
        self.radioButton_from_local_clone.setToolTip(_translate(
            "Dialog", "From project directory containing `pyproject.toml`"))
        self.radioButton_from_local_clone.setText(_translate("Dialog", "Local clone"))
        self.radioButton_from_local_file.setToolTip(_translate("Dialog", "From released zip/tarball file"))
        self.radioButton_from_local_file.setText(_translate("Dialog", "Local file"))
        self.lineEdit_local.setToolTip(_translate("Dialog", "File/directory path to read"))
        self.lineEdit_local.setText(_translate("Dialog", "/Users/yyy/Documents/protein_design/REvoDesign"))
        self.pushButton_open.setText(_translate("Dialog", "..."))
        self.pushButton_install.setToolTip(_translate("Dialog", "Install REvoDesign"))
        self.pushButton_install.setText(_translate("Dialog", "Install"))
        self.pushButton_remove.setToolTip(_translate("Dialog", "Remove REvoDesign"))
        self.pushButton_remove.setText(_translate("Dialog", "Remove"))
        self.groupBox_2.setTitle(_translate("Dialog", "Options:"))
        self.checkBox_upgrade.setToolTip(_translate("Dialog", "Upgrade to the latest"))
        self.checkBox_upgrade.setText(_translate("Dialog", "Upgrade"))
        self.checkBox_verbose.setText(_translate("Dialog", "Verbose"))
        self.checkBox_specified_version.setToolTip(_translate("Dialog", "Install from a specific version"))
        self.checkBox_specified_version.setText(_translate("Dialog", "Version:"))
        self.comboBox_version.setToolTip(_translate("Dialog", "Install from a specific version number"))
        self.checkBox_specified_commit.setToolTip(_translate("Dialog", "Install from a specific commit/branch"))
        self.checkBox_specified_commit.setText(_translate("Dialog", "commit:"))
        self.lineEdit_commit.setToolTip(_translate("Dialog", "Install from a specific commit/branch"))
        self.label_2.setText(_translate("Dialog", "Makes enzyme redesign tasks easier to all."))
        self.groupBox_3.setTitle(_translate("Dialog", "Network:"))
        self.checkBox_use_proxy.setToolTip(_translate("Dialog", "Enable http/socks proxy"))
        self.checkBox_use_proxy.setText(_translate("Dialog", "proxy:"))
        self.lineEdit_proxy_url.setToolTip(_translate("Dialog", "HTTP/Socks proxy"))
        self.lineEdit_proxy_url.setText(_translate("Dialog", "http://localhost:7890"))
        self.checkBox_use_mirror.setToolTip(_translate("Dialog", "Enable PyPi mirror"))
        self.checkBox_use_mirror.setText(_translate("Dialog", "Mirror:"))
        self.lineEdit_mirror_url.setToolTip(_translate("Dialog", "Set PyPi mirror URL"))
        self.lineEdit_mirror_url.setText(_translate("Dialog", "https://mirrors.bfsu.edu.cn/pypi/web/simple"))
        self.groupBox_4.setTitle(_translate("Dialog", "Cache:"))
        self.checkBox_user_cache_dir.setToolTip(_translate("Dialog",
                                                           "Use customized cache dir. Uncheck this to let REvoDesign choose one."))
        self.checkBox_user_cache_dir.setText(_translate("Dialog", "Use:"))
        self.lineEdit_customized_cache_dir.setToolTip(_translate("Dialog", "Cache file on this dir"))
        self.pushButton_open_cache_dir.setToolTip(_translate("Dialog", "Open a dir as cache directory."))
        self.pushButton_open_cache_dir.setText(_translate("Dialog", "..."))
        self.pushButton_set_cache_dir.setToolTip(_translate("Dialog", "Apply this directory for cache."))
        self.pushButton_set_cache_dir.setText(_translate("Dialog", "Apply"))
        self.groupBox_5.setToolTip(_translate("Dialog", "Extra definitions of dependencies."))
        self.groupBox_5.setTitle(_translate("Dialog", "Extras:"))
        self.radioButton_extra_none.setToolTip(_translate("Dialog", "Default setting with no extra dependencies."))
        self.radioButton_extra_none.setText(_translate("Dialog", "None"))
        self.radioButton_extra_customized.setToolTip(_translate("Dialog", "Customized extras picked from right panel."))
        self.radioButton_extra_customized.setText(_translate("Dialog", "Customized"))
        self.radioButton_extra_everything.setToolTip(_translate("Dialog", "Install with all extras except unit tests"))
        self.radioButton_extra_everything.setText(_translate("Dialog", "Everything"))

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

    def get_checked_items(self):
        """
        Returns a list of all checked items' text.

        Returns:
            A list of strings representing the texts of all checked items.
        """
        checked_items = []
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item.isCheckable() and item.checkState() == QtCore.Qt.Checked:
                checked_items.append(self.items[item.text()])
        return checked_items

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

    def __post_init__(self):
        """
        Initializes instance attributes to check if git, conda, and winget are installed.

        This method is automatically called after the object initialization.
        It sets the object's properties based on whether these tools are available in the system path.
        This ensures that the object can determine if it can perform related operations before doing so.
        """
        for cmd_tool in ["git", "conda", "winget"]:
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
        elif self.has_conda:
            cmd = ["conda", "install", "-y", "git"]

        else:
            # If neither Conda nor Winget is present, prompt the user to install Git manually
            notify_box(
                message="Git is required to install REvoDesign. Please install Git first.\n"
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
class REvoDesignInstaller:
    """
    Class to manage the installation of the REvoDesign plugin.

    Attributes:
        dialog (QWidget): The main dialog window for the plugin GUI.
        extra_checkbox (CheckableListView): A checkbox list for selecting extra components.
    """

    dialog = None

    installer_ui: Ui_Dialog = None  # type: ignore
    extra_checkbox: CheckableListView = None  # type: ignore

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

        # Run a worker thread to fetch extras with a progress bar
        AVAILABLE_EXTRAS = run_worker_thread_with_progress(
            worker_function=fetch_extras,
            url=EXTRAS_TABLE_JSON,
            progress_bar=self.installer_ui.progressBar)

        if not AVAILABLE_EXTRAS:
            AVAILABLE_EXTRAS = {"No Extras is Fetched": ''}
            notify_box("Error fetching or validating the JSON data. \n"
                       "Please reconfigure your network and restart PyMOL to try again "
                       "if you wish to continue installation with extra packages")

        if self.extra_checkbox is None:
            # Create and position the extra components checkbox list
            self.extra_checkbox = CheckableListView(
                self.installer_ui.listView_extras, AVAILABLE_EXTRAS
            )

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

        # Run a worker thread to fetch tags with a progress bar
        self.fetch_tags()

    def proxy_in_env(self, proxy: Optional[str] = None) -> Dict[str, str]:
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

        if proxy.startswith('socks'):

            if not proxy.startswith('socks5'):
                notify_box(f'Unsupported proxy type: {proxy}\nPlease use socks5://... or socks5h://...')
                return {}

            print('Ensuring pysocks is installed...')
            run_worker_thread_with_progress(
                worker_function=ensure_package,
                package_string='pysocks',
                progress_bar=self.installer_ui.progressBar)

        print(f"using proxy: {proxy}")
        proxy_env = {
            "http_proxy": proxy,
            "https_proxy": proxy,
            "all_proxy": proxy,
        }
        return proxy_env

    def make_window(self) -> QtWidgets.QDialog:  # type: ignore
        """
        Creates and configures the application window.

        This method initializes a QDialog object and sets up its UI elements using the `Ui_Dialog` class.
        It also connects various buttons to their respective methods for handling user interactions.

        Returns:
            QtWidgets.QDialog: The configured dialog window.
        """

        self.installer_ui = Ui_Dialog()

        # Create a new dialog window
        dialog = QtWidgets.QDialog()

        # Set up the UI for the dialog
        self.installer_ui.setupUi(Dialog=dialog)

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

        This function animates the resizing of `self.dialog` and `self.ui.label_2` to the specified dimensions.
        """
        if expand:
            # Expand the dialog and label to larger sizes
            self.animate_to_size(self.dialog, (652, 534))
            self.animate_to_size(self.installer_ui.label_2, (611, 41))
        else:
            # Shrink the dialog and label to smaller sizes
            self.animate_to_size(self.dialog, (490, 534))
            self.animate_to_size(self.installer_ui.label_2, (451, 41))

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
                worker_function=install_via_pip,
                uninstall=True,
                progress_bar=self.installer_ui.progressBar,
            )

            if ret is None or ret.returncode:
                # If the uninstallation fails, notify the user of the failure and raise an error
                return notify_box(message="Failed to remove REvoDesign.", error_type=RuntimeError)

            # If the uninstallation is successful, notify the user
            return notify_box(
                message="REvoDesign is removed successfully. Bye-bye.",
            )

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
        env.update(self.proxy_in_env(proxy=proxy_url if (use_proxy and proxy_url) else None))

        # Perform the installation process
        with hold_trigger_button(self.installer_ui.pushButton_install):
            ensure_lower_pip(env=env)
            git_solver = GitSolver()
            has_git = run_worker_thread_with_progress(
                worker_function=git_solver.fetch_git,
                env=env,
                progress_bar=self.installer_ui.progressBar,
            )

            if not has_git:
                return

            installed: Union[subprocess.CompletedProcess, None] = run_worker_thread_with_progress(
                worker_function=install_via_pip,
                progress_bar=self.installer_ui.progressBar,
                source=install_source,
                upgrade=upgrade,
                verbose=verbose,
                extras=extras,
                env=env,
                mirror=mirror_url if (use_mirror and mirror_url) else "",
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


class QtProgressBarHint(Protocol):
    """
    Defines a protocol class to specify the behavior of a progress bar.
    This class outlines the methods that a progress bar should have, allowing static typing checker to analyse.
    """

    def minimum(self) -> int: ...

    def maximum(self) -> int: ...

    def value(self) -> int: ...

    def setRange(self, min: int, max: int): ...

    def setValue(self, value: int): ...


# a copy from `REvoDesign/tools/utils.py`
def run_worker_thread_with_progress(
    worker_function: Callable[..., R], *args, progress_bar: Optional[QtProgressBarHint] = None, **kwargs
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
        time.sleep(0.001)

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
def proceed_with_comfirm_msg_box(title="", description=""):
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


def solve_installation_config(source: str, git_url: str, git_tag: str, extras: Optional[str]):
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
    package_string = f"REvoDesign{extra_string}"
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

    notify_box(f"Unknown installation source {source}!", ValueError)


def ensure_package(package_string: str, env: Optional[Mapping[str, str]] = None):
    """
    Function: ensure_package
    Usage: ensure_package(package_string, env)
    This function ensures that a specified package is installed in the current Python environment.
    Args:
    - package_string (str): Name of the package to ensure
    - env (Optional[Mapping[str, str]]): Environment variables to use for the installation
    """

    # Get the absolute path of the current Python executable
    python_exe = os.path.realpath(sys.executable)
    # Construct the command to install a specific version of pip
    pip_cmd = [python_exe, "-m", "pip", "install", "-U", package_string, "-q"]

    # Execute the pip installation command
    result = run_command(pip_cmd, verbose=True, env=env)
    # If the pip downgrade command fails, notify the user to manually execute the command
    if result.returncode:
        print(
            f"Failed to ensure {package_string}. Please upgrade/downgrade manually.\n"
            f'Run this command in your shell - `{" ".join(pip_cmd)}`'
        )


def ensure_lower_pip(env: Optional[Mapping[str, str]]):
    """
    Ensure the pip version is lower than 24.0, as REvoDesign installation requires pip<24.0.

    Parameters:
    - env: Optional[Mapping[str, str]] - The environment variables for the pip installation command, optional.

    Returns:
    None
    """

    # Get the current pip version number
    pip_ver: float = float(pip.__version__.split(".", maxsplit=1)[0])
    # If the pip version is already lower than 24.0, no action is needed
    if pip_ver < 24.0:
        return

    # Warn the user that pip>=24.0 will be required for future REvoDesign installations
    warnings.warn(FutureWarning("pip>=24.0 will be required for REvoDesign installation."))
    ensure_package('pip<24.0', env=env)


def install_via_pip(
    source: str = REPO_URL,
    upgrade: bool = False,
    verbose: bool = True,
    extras: Optional[str] = None,
    mirror: Optional[str] = "",
    uninstall: bool = False,
    env: Optional[Mapping[str, str]] = None,
) -> Optional[subprocess.CompletedProcess]:
    """
    Install a package via pip.

    Args:
        source: The source URL of the package, default is the URL defined in REPO_URL.
        upgrade: Whether to upgrade the package, default is False.
        verbose: Whether to output detailed information, default is True.
        extras: Additional requirements, default is None.
        mirror: The mirror source for installation, default is empty.
        uninstall: Whether to uninstall before installation, default is False.
        env: Environment variables for the installation process, default is None.

    Returns:
        Returns the result of the installation process as a subprocess.CompletedProcess object.
    """

    def get_source_and_tag(source: str):
        """
        Parse the source URL and tag.

        Args:
            source: The source URL of the package.

        Returns:
            Returns a tuple containing the git directory and git tag.
        """
        git_dir = source.split("@")[0]
        if "@" in source:
            git_tag = source.split("@")[1]
        else:
            git_tag = ""
        return git_dir, git_tag

    print("Installation is started. This may take a while and the window will freeze until it is done.")

    python_exe = os.path.realpath(sys.executable)

    # run installation via pip
    ensurepip = run_command([python_exe, "-m", "ensurepip"], verbose=verbose, env=env)
    if ensurepip.returncode:
        notify_box("ensurepip failed.", RuntimeError)
        return

    if uninstall:
        pip_cmd = [
            python_exe,
            "-m",
            "pip",
            "uninstall",
            "-y",
            "REvoDesign",
        ]
    else:
        # use default source
        if not source:
            source = REPO_URL

        git_url, git_tag = get_source_and_tag(source=source)

        package_string = solve_installation_config(source=source, git_url=git_url, git_tag=git_tag, extras=extras)
        pip_cmd = [
            python_exe,
            "-m",
            "pip",
            "install",
            f"{package_string}",
        ]

        if upgrade:
            pip_cmd.append("--upgrade")

        if mirror:
            print(f"using mirror from {mirror}")
            pip_cmd.extend(["-i", mirror])

    result: subprocess.CompletedProcess = run_command(pip_cmd, verbose=verbose, env=env)

    return result


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
