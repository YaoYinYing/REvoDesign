'''
Described at GitHub:
https://github.com/YaoYinYing/REvoDesign

Authors : Yinying Yao
Program : REvoDesign
Date    : Sept 2023

REvoDesign -- Makes enzyme redesign tasks easier to all.
'''

import time
from typing import Iterable, Union
from pymol.Qt import QtCore, QtGui, QtWidgets
import traceback
import urllib.request
import json
import os

print(f'REvoDesign entrypoint is located at {os.path.dirname(__file__)}')

install_msg = '''
You can still use the following in PyMOL command prompt to install REvoDesign manually:\n
`install_REvoDesign_via_pip` or \n
`install_REvoDesign_via_pip file:///local/path/to/repository/of/REvoDesign`\n
After it is done, you should restart PyMOL.
'''

REPO_URL: str = 'https://github.com/YaoYinYing/REvoDesign'
AVAILABLE_EXTRAS: list = ['', 'tf', 'torch', 'jax', 'full', 'unittest']


# translated UI Dialog from UI file
class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(544, 325)
        self.groupBox = QtWidgets.QGroupBox(Dialog)
        self.groupBox.setGeometry(QtCore.QRect(10, 70, 521, 121))
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
            QtCore.QRect(10, 30, 501, 81)
        )
        self.horizontalLayoutWidget_2.setObjectName("horizontalLayoutWidget_2")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(
            self.horizontalLayoutWidget_2
        )
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.radioButton_from_repo = QtWidgets.QRadioButton(
            self.horizontalLayoutWidget_2
        )
        self.radioButton_from_repo.setObjectName("radioButton_from_repo")
        self.horizontalLayout_3.addWidget(self.radioButton_from_repo)
        self.radioButton_from_local_clone = QtWidgets.QRadioButton(
            self.horizontalLayoutWidget_2
        )
        self.radioButton_from_local_clone.setObjectName(
            "radioButton_from_local_clone"
        )
        self.horizontalLayout_3.addWidget(self.radioButton_from_local_clone)
        self.radioButton_from_local_file = QtWidgets.QRadioButton(
            self.horizontalLayoutWidget_2
        )
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
        self.progressBar = QtWidgets.QProgressBar(
            self.horizontalLayoutWidget_2
        )
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
        self.verticalLayout_2.addWidget(self.progressBar)
        self.horizontalLayout_2.addLayout(self.verticalLayout_2)
        self.groupBox_2 = QtWidgets.QGroupBox(Dialog)
        self.groupBox_2.setGeometry(QtCore.QRect(10, 200, 521, 111))
        self.groupBox_2.setObjectName("groupBox_2")
        self.horizontalLayoutWidget_8 = QtWidgets.QWidget(self.groupBox_2)
        self.horizontalLayoutWidget_8.setGeometry(
            QtCore.QRect(10, 29, 501, 75)
        )
        self.horizontalLayoutWidget_8.setObjectName("horizontalLayoutWidget_8")
        self.horizontalLayout_8 = QtWidgets.QHBoxLayout(
            self.horizontalLayoutWidget_8
        )
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
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
        self.comboBox_extras.setObjectName("comboBox_extras")
        self.horizontalLayout_4.addWidget(self.comboBox_extras)
        self.verticalLayout_3.addLayout(self.horizontalLayout_4)
        self.horizontalLayout_7 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.checkBox_verbose = QtWidgets.QCheckBox(
            self.horizontalLayoutWidget_8
        )
        self.checkBox_verbose.setObjectName("checkBox_verbose")
        self.horizontalLayout_7.addWidget(self.checkBox_verbose)
        self.verticalLayout_3.addLayout(self.horizontalLayout_7)
        self.horizontalLayout_8.addLayout(self.verticalLayout_3)
        self.verticalLayout_4 = QtWidgets.QVBoxLayout()
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

        self.retranslateUi(Dialog)
        self.radioButton_from_repo.toggled['bool'].connect(self.lineEdit_local.setDisabled)  # type: ignore
        self.radioButton_from_repo.toggled['bool'].connect(self.pushButton_open.setDisabled)  # type: ignore
        self.checkBox_specified_version.toggled['bool'].connect(self.comboBox_version.setEnabled)  # type: ignore
        self.checkBox_specified_commit.toggled['bool'].connect(self.lineEdit_commit.setEnabled)  # type: ignore
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(
            _translate("Dialog", "Install REvoDesign to PyMOL")
        )
        self.groupBox.setTitle(_translate("Dialog", "Source:"))
        self.radioButton_from_repo.setText(_translate("Dialog", "Repository"))
        self.radioButton_from_local_clone.setText(
            _translate("Dialog", "Local clone")
        )
        self.radioButton_from_local_file.setText(
            _translate("Dialog", "Local file")
        )
        self.pushButton_open.setText(_translate("Dialog", "..."))
        self.pushButton_install.setText(_translate("Dialog", "Install"))
        self.groupBox_2.setTitle(_translate("Dialog", "Options:"))
        self.label.setText(_translate("Dialog", "Extras:"))
        self.checkBox_verbose.setText(_translate("Dialog", "Verbose"))
        self.checkBox_specified_version.setText(
            _translate("Dialog", "Version:")
        )
        self.checkBox_upgrade.setText(_translate("Dialog", "Upgrade"))
        self.checkBox_specified_commit.setText(_translate("Dialog", "commit:"))
        self.label_2.setText(
            _translate(
                "Dialog",
                "This tool helps you with installation of REvoDesign to PyMOL.",
            )
        )


class REvoDesignInstaller:
    def __init__(self):
        self.dialog = None

    def run_plugin_gui(self):
        if self.dialog is None:
            self.dialog = self.make_window()
        self.dialog.show()

    def make_window(self):
        self.ui = Ui_Dialog()

        dialog = QtWidgets.QDialog()
        self.ui.setupUi(Dialog=dialog)
        self.ui.pushButton_open.clicked.connect(self.open_files)
        self.ui.pushButton_install.clicked.connect(self.install)
        set_widget_value(self.ui.comboBox_version, self.fetch_tags)
        set_widget_value(self.ui.comboBox_extras, AVAILABLE_EXTRAS)
        return dialog

    def fetch_tags(self) -> Union[list, str]:
        try:
            tags = get_github_repo_tags(repo_url=REPO_URL)
            assert tags
            return tags
        except ValueError as e:
            traceback.print_exc()
            return ''

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

    def install(self):
        # sources
        from_repo = self.ui.radioButton_from_repo.isChecked()
        from_local_clone = self.ui.radioButton_from_local_clone.isChecked()
        from_local_file = self.ui.radioButton_from_local_file.isChecked()
        local_source: str = self.ui.lineEdit_local.text()

        extras = self.ui.comboBox_extras.currentText()
        upgrade = self.ui.checkBox_upgrade.isChecked()
        verbose = self.ui.checkBox_verbose.isChecked()

        use_version = self.ui.checkBox_specified_version.isChecked()
        target_version = self.ui.comboBox_version.currentText()

        use_commit = self.ui.checkBox_specified_commit.isChecked()
        target_commit = self.ui.lineEdit_commit.text()

        if from_repo:
            install_source = REPO_URL
            if use_version and target_version:
                install_source += f'@{target_version}'
            elif use_commit and target_commit:
                install_source += f'@{target_commit}'

        elif from_local_clone:
            install_source = local_source
            if not local_source:
                raise ValueError(f'Empty local dir: {local_source}')
            if not os.path.exists(local_source):
                raise ValueError(f'dir not exists: {local_source}')

            if not os.path.isdir(local_source):
                raise FileNotFoundError(f'{local_source} not a directory')

            if use_version and target_version:
                install_source = f'file://{install_source}@{target_version}'
            elif use_commit and target_commit:
                install_source = f'file://{install_source}@{target_commit}'
        elif from_local_file:
            install_source = local_source
            if not os.path.exists(local_source):
                raise FileNotFoundError(f'{local_source} is not found.')
            if not os.path.isfile(local_source):
                raise ValueError(f'{local_source} is not a file.')
            if not (
                local_source.endswith('.zip')
                or local_source.endswith('.tar.gz')
            ):
                raise ValueError(
                    f'{local_source} must be a .zip or .tar.gz file!'
                )
            if use_version or use_commit or target_version or target_commit:
                print(
                    f'WARNING: installation from zip/tar file cannot use specified version/commit.'
                )
            install_source = local_source

        if not install_source:
            raise ValueError('Installation configuration is failed. Aborded. ')

        run_worker_thread_with_progress(
            worker_function=install_via_pip,
            progress_bar=self.ui.progressBar,
            source=install_source,
            upgrade=upgrade,
            vebose=verbose,
            extras=extras,
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


# a copy from `REvoDesign/tools/utils.py`
def run_worker_thread_with_progress(
    worker_function, progress_bar=None, *args, **kwargs
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


def get_github_repo_tags(repo_url):
    """
    Retrieve all released tags of a GitHub repository using urllib.

    Usage:
        tags = get_github_repo_tags("https://github.com/BradyAJohnston/MolecularNodes")
        print(tags)

    Args:
        repo_url (str): The URL of the GitHub repository.

    Returns:
        list: A list of tag names for the repository, or an error message.
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
            tag_names = [tag['name'] for tag in tags]
            return tag_names
    except urllib.error.HTTPError as e:
        # Handle HTTP errors (e.g., repository not found, rate limit exceeded)
        return f"Error: GitHub API returned status code {e.code}"
    except urllib.error.URLError as e:
        # Handle URL errors (e.g., network issues)
        return f"Error: Failed to reach the server. Reason: {e.reason}"


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

    def set_value_error(widget, value):
        print(
            f'FIX ME: Value {value} is not currently supported on widget {type(widget).__name__}'
        )

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
        elif isinstance(value, dict):
            widget.clear()
            for k, v in value.items():
                widget.addItem(v, k)
        else:
            widget.setCurrentText(str(value))
    elif isinstance(widget, QtWidgets.QLineEdit):
        widget.setText(str(value))
    elif isinstance(widget, QtWidgets.QProgressBar):
        if isinstance(value, int):
            widget.setValue(value)
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            widget.setRange(*value)
    elif isinstance(widget, QtWidgets.QCheckBox):
        widget.setChecked(bool(value))
    else:
        set_value_error(widget, value)


# a copy from `REvoDesign/tools/customized_widgets.py`
def refresh_window():
    QtWidgets.QApplication.processEvents()


def install_via_pip(
    source=REPO_URL,
    upgrade=0,
    vebose=1,
    extras='',
):
    def get_source_and_tag(source):
        git_dir = source.split('@')[0]
        if '@' in source:
            git_tag = source.split('@')[1]
        else:
            git_tag = ''
        return git_dir, git_tag

    import sys, subprocess

    upgrade = int(upgrade)
    vebose = int(vebose)

    print(
        'Installation is started. This may take a while and the window will freeze until it is done.'
    )
    python_exe = os.path.realpath(sys.executable)

    # use default source
    if not source:
        source = REPO_URL

    git_url, git_tag = get_source_and_tag(source=source)
    package_string = f"REvoDesign{f'[{extras}]' if extras and extras in AVAILABLE_EXTRAS else ''}"

    # with github url and tag
    if source and source.startswith('https://'):
        package_string += f' @ git+{git_url}{f"@{git_tag}" if git_tag else ""}'

    # with git repo clone and tag
    elif source.startswith('file://'):
        if not os.path.exists(os.path.join(git_url, '.git')):
            raise FileNotFoundError(
                f'Git dir not found: {os.path.join(git_url, ".git")}'
            )
        package_string += f' @ git+{source}{f"@{git_tag}" if git_tag else ""}'

    # with unzipped code dir
    elif os.path.exists(source) and os.path.isdir(source):
        if not os.path.exists(os.path.join(source, 'pyproject.toml')):
            raise FileNotFoundError(
                f'{source} is not a directory containing pyproject.toml'
            )
        if git_tag:
            raise ValueError('unzipped code directory can not have a tag!')
        if source.endswith('/'):
            source = source[:-1]
        package_string = f"{source}{f'[{extras}]'if extras else ''}"

    # with zipped code archive
    elif os.path.exists(source) and os.path.isfile(source):
        if git_tag:
            raise ValueError('zipped file can not have a tag!')

        if source.endswith('.zip'):
            package_string = source
        elif source.endswith('.tar.gz'):
            package_string += f'@{source}'
        else:
            raise FileNotFoundError(
                f'{source} is neither a zipped file nor a tar.gz file!'
            )

    else:
        raise ValueError(f'Unknown installation source {source}!')

    # run installation via pip
    subprocess.run([python_exe, '-m', 'ensurepip'])

    pip_cmd = [
        python_exe,
        '-m',
        'pip',
        'install',
        f"{package_string}",
    ]

    if upgrade:
        pip_cmd.append('--upgrade')

    print(pip_cmd)

    result = subprocess.run(
        pip_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        print(f'Installation failed: {source}')
        if vebose:
            print(f'stdout: {result.stdout.decode()}')
            print(f'stderr: {result.stderr.decode()}')
    else:
        print(
            f'Installation succeeded: {source}',
        )
        if vebose:
            print(f'stdout: {result.stdout.decode()}')
        print(
            'If this is an upgrade, please restart PyMOL for it to take effect.'
        )



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
        
    finally:
        from pymol import cmd
        cmd.extend('install_REvoDesign_via_pip', install_via_pip)
