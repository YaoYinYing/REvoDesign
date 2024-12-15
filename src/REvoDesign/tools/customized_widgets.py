"""
Custom widgets for REvoDesign.
"""

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pymol.Qt import QtCore, QtGui, QtWidgets  # type: ignore

from REvoDesign import issues
from REvoDesign.basic import FileExtensionCollection as FExCol
from REvoDesign.common import FileExtentions
from REvoDesign.logger import root_logger

from .package_manager import (WorkerThread, decide, hold_trigger_button,
                              notify_box, refresh_window)

logging = root_logger.getChild(__name__)

PYQT_VERSION_STR = QtCore.PYQT_VERSION_STR


# Custom widget for displaying images
class ImageWidget(QtWidgets.QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        image = QtGui.QImage(self.image_path)
        painter.drawImage(self.rect(), image)


@dataclass(frozen=True)
class ButtonCoords:
    """
    Immutable data class representing the coordinates and names of a button.

    Attributes:
        row (int): The row index of the button.
        row_name (str): The name of the row.
        col (int): The column index of the button.
        col_name (str): The name of the column.
    """
    row: int
    row_name: str
    col: int
    col_name: str


class QButtonBrick(QtWidgets.QPushButton):  # type: ignore
    """
    Custom QPushButton subclass representing a button in a matrix.

    Attributes:
        coords (ButtonCoords): Coordinates and names associated with the button.
        color (QtGui.QColor): The background color of the button.
        is_wt (bool): Flag indicating if the button represents a wild type (WT) pair.

    Methods:
        button_name: Constructs the unique object name for the button.
        style_sheet: Generates the CSS styling for the button.
    """

    def __init__(
        self,
        coords: ButtonCoords,
        color: QtGui.QColor,
        label: Optional[str] = None,
        tooltip_text: Optional[str] = None,
        is_wt: Optional[bool] = False,
        size_policy: Optional[QtWidgets.QSizePolicy] = None,  # type: ignore
        parent=None,
    ):
        """
        Initializes the QButtonBrick instance.

        Args:
            coords (ButtonCoords): Coordinates and metadata for the button.
            color (QtGui.QColor): Background color of the button.
            label (Optional[str]): Text to display on the button.
            tooltip_text (Optional[str]): Tooltip text for the button.
            is_wt (Optional[bool]): Whether the button is a wild type button.
            size_policy (Optional[QtWidgets.QSizePolicy]): Size policy for the button.
            parent: Parent widget for the button.
        """
        super().__init__(parent)
        self.coords = coords
        self.color = color
        self.is_wt = is_wt

        self.setStyleSheet(self.style_sheet)
        self.setObjectName(self.button_name)
        self.setText(label)
        self.setToolTip(tooltip_text)
        self.setSizePolicy(size_policy)
        # self.setContentsMargins(0, 0, 0, 0)

    @property
    def button_name(self) -> str:
        """
        Constructs the unique object name for the button based on its coordinates.

        Returns:
            str: The unique name of the button.
        """
        return f"matrixButton_{self.coords.row}_vs_{self.coords.col}"

    @property
    def style_sheet(self) -> str:
        """
        Generates the CSS style for the button, including background color and text color.

        Returns:
            str: The CSS style for the button.
        """
        return f"""
    QPushButton {{
        background-color: {self.color.name()};
        {'color: black;' if self.is_wt else ''};
    }}
    QToolTip {{
        background-color: black;
        color: white;
        border: 1px solid white;
    }}
"""


class QButtonMatrix(QtWidgets.QWidget):
    """
    A custom widget for displaying a matrix of buttons.

    Attributes:
        label_size (Optional[List[int]]): Fixed size of row/column labels.
        report_axes_signal (pyqtSignal): Signal emitted with row and column indices.

    Methods:
        _map_value_to_color: Maps a matrix value to a QColor.
        _set_label_size: Sets the fixed size of a label.
        is_wt_button: Determines if a button is a wild type button.
        _make_button_tip: Constructs a tooltip for a button.
        init_ui: Initializes the matrix UI with buttons and labels.
        signal_process: Handles button click events.

    Usage Example:
        ```python

        # Example DataFrame
        data = {
            'A': [1.0, 2.0, 3.0],
            'B': [4.0, 5.0, 6.0],
            'C': [7.0, 8.0, 9.0]
        }
        df_button_matrix = pd.DataFrame(data, index=['X', 'Y', 'Z'])

        # Sequence
        sequence = "XYZ"

        # Function to handle button actions
        def mutate_with_gridbuttons(row, col, matrix, ignore_wt):
            print(f"Mutation grid button action executed at row {row}, col {col}.")

        # PyQt Application Setup
        app = QApplication([])

        # Create QButtonMatrix instance
        button_matrix = QButtonMatrix(
            df_matrix=df_button_matrix,
            sequence=sequence,
            cmap='bwr',
            flip_cmap=False,
        )

        # Method 1: Using internal calls with active_func
        button_matrix.sequence = sequence
        button_matrix.init_ui()
        button_matrix.active_func = partial(
            mutate_with_gridbuttons,
            **kwargs,
        )

        # Method 2: Connecting the signal externally
        button_matrix.report_axes_signal.connect(
            lambda row, col: mutate_with_gridbuttons(
                row,
                col,
                *args,
                **kwargs,
            )
        )

        # Show the widget
        button_matrix.show()

        # Execute the application
        app.exec_()
        ```

    Notes:
    - Method 1 (internal calls with `active_func`): Aligns with Pythonic principles
        by encapsulating logic within the widget. It ensures centralized management
        of button actions and allows for features like holding or freezing the trigger
        button during execution.
    - Method 2 (external signal connection): Aligns with PyQt-idiomatic practices,
        leveraging the signal-slot mechanism to decouple button actions from widget
        logic. Ideal for integrating into larger PyQt applications where events are
        handled externally.

    """

    label_size: Optional[List[int]] = [18, 12]

    # Define a custom signal for reporting axes
    report_axes_signal = QtCore.pyqtSignal(int, int)

    def __init__(
        self,
        df_matrix: pd.DataFrame,
        sequence: str,
        func: Optional[Callable[[int, int], None]] = None,
        parent=None,
        cmap: str = 'bwr',
        flip_cmap: bool = False,
        button_size=12,
        zero_index_offset=0,
    ):
        """
        Initializes the QButtonMatrix widget.

        Args:
            df_matrix (pd.DataFrame): Dataframe representing the matrix.
            sequence (str): Full sequence of residues.
            func (Optional[Callable[[int, int], None]]): Function called on button click.
            parent: Parent widget.
            cmap (str): Colormap name for button colors.
            flip_cmap (bool): Whether to reverse the colormap.
            button_size (int): Size of the buttons.
            zero_index_offset (int): Offset for zero-based indexing. Default is 0.
        """
        from REvoDesign.tools.utils import cmap_reverser

        super().__init__(parent)

        self.button_size = button_size
        self.sequence = sequence
        self.active_func = func
        self.df_matrix = df_matrix.copy()
        self.zero_index_offset = zero_index_offset

        self.alphabet_row = self.df_matrix.index.tolist()
        self.alphabet_col = self.df_matrix.columns.tolist()

        max_abs = np.max((np.abs(self.df_matrix.values.min()), self.df_matrix.values.max()))
        self.min_value, self.max_value = -max_abs, max_abs

        cmap = cmap_reverser(
            cmap=cmap,
            reverse=flip_cmap,
        )
        self.colormap = plt.get_cmap(cmap)

    def _map_value_to_color(self, value):
        """
        Maps a value to a QColor based on the colormap.

        Args:
            value (float): Value to be mapped.

        Returns:
            QtGui.QColor: Color corresponding to the value.
        """
        normalized_value = 1 - (value - self.min_value) / (self.max_value - self.min_value)
        rgba_color = self.colormap(normalized_value)
        return QtGui.QColor.fromRgbF(rgba_color[0], rgba_color[1], rgba_color[2], rgba_color[3])

    def _set_label_size(self, label: Any):
        """
        Sets the fixed size for a label if the class attribute `label_size` is defined.

        Args:
            label (QtWidgets.QLabel): The label to resize.
        """
        if not (hasattr(self, 'label_size') and self.label_size):
            return
        if len(self.label_size) != 2:
            raise ValueError("label size must be a list of length 2")
        label.setFixedSize(*self.label_size)

    def is_wt_button(self, row_name: str, col_name: str, row: int, col: int):
        """
        Determines if a button corresponds to a wild type (WT) pair.

        Args:
            row_name (str): Name of the row.
            col_name (str): Name of the column.
            row (int): Row index.
            col (int): Column index.

        Returns:
            bool: True if the button represents a WT pair, False otherwise.
        """
        return row_name == self.sequence[int(col_name) - 1 + self.zero_index_offset]

    def get_WT_label(self, row_name: str, col_name: str, row: int, col: int) -> str:
        return row_name

    def _make_button_tip(
            self,
            row_name: str,
            col_name: str,
            value: float,
            row: Optional[int] = None,
            col: Optional[int] = None,
            is_wt_pair: bool = False):
        """
        Constructs a tooltip for a button.

        Args:
            row_name (str): Name of the row.
            col_name (str): Name of the column.
            value (float): Value associated with the button.
            row (Optional[int]): Row index.
            col (Optional[int]): Column index.
            is_wt_pair (bool): Whether the button is a WT pair.

        Returns:
            str: Tooltip text for the button.
        """
        return f"{self.sequence[int(col_name)-1+self.zero_index_offset]}{str(int(col_name) + self.zero_index_offset)}{row_name} ({value:.3f}){', WT' if is_wt_pair else ''}"

    def init_ui(self):
        """
        Initializes the user interface by creating buttons and labels based on the matrix and sequence.
        """
        layout = QtWidgets.QGridLayout()
        font = QtGui.QFont()
        font.setPointSizeF(self.button_size * 0.8)
        font.setBold(True)

        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)

        for row, row_name in enumerate(self.alphabet_row):
            label = QtWidgets.QLabel(row_name)
            label.setFont(font)
            if hasattr(self, '_set_label_size'):
                self._set_label_size(label)

            layout.addWidget(label, row, 0, QtCore.Qt.AlignRight)
            for col, col_name in enumerate(self.alphabet_col):
                value = self.df_matrix.iloc[row, col]

                is_wt_button = self.is_wt_button(row_name=row_name, col_name=col_name, row=row, col=col)
                button_tip = self._make_button_tip(
                    col_name=col_name,
                    row_name=row_name,
                    value=value,
                    is_wt_pair=is_wt_button)
                button = QButtonBrick(
                    coords=ButtonCoords(row, row_name, col, col_name),
                    color=self._map_value_to_color(value),
                    label=f"&{self.get_WT_label( row_name, col_name, row, col)}" if is_wt_button else None,
                    tooltip_text=button_tip,
                    is_wt=is_wt_button,
                    size_policy=size_policy,
                )

                bfont = QtGui.QFont()
                bfont.setPointSizeF(self.button_size * .9)
                bfont.setBold(True)

                button.setFont(bfont)

                button.clicked.connect(lambda checked, r=row, c=col: self.signal_process(r, c))
                layout.addWidget(button, row, col + 1)

        for col, col_name in enumerate(self.alphabet_col):
            if self.zero_index_offset:
                try:
                    col_name = str(int(col_name) - self.zero_index_offset)
                except ValueError as e:
                    raise issues.UnsupportedDataTypeError(
                        f'Zero-index offset is not supported for Column where {self.alphabet_col}.\n'
                        f'Expected type is int or digit string, not {type(col_name)}.') from e
            label = QtWidgets.QLabel(col_name)
            label.setFont(font)
            if hasattr(self, '_set_label_size'):
                self._set_label_size(label)
            layout.addWidget(label, len(self.alphabet_col), col + 1, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        self.setLayout(layout)
        logging.debug("Matrix button matrix initialized.")
        logging.debug(layout)

    def signal_process(self, row, col):
        """
        Handles button click events and processes signals.

        Args:
            row (int): Row index of the clicked button.
            col (int): Column index of the clicked button.
        """
        logging.debug(f"Button at ({row}, {col}) clicked.")

        if self.active_func is not None:
            trigger_button = self.findChild(QButtonBrick, f"matrixButton_{row}_vs_{col}")
            with hold_trigger_button(trigger_button):
                self.active_func(row, col)
                return
        else:
            self.report_axes_signal.emit(row, col)


class QButtonMatrixGremlin(QButtonMatrix):
    """
    A specialized variant of QButtonMatrix for Gremlin.

    Attributes:
        pair_i (int): Index of the first pair.
        pair_j (int): Index of the second pair.

    Methods:
        is_wt_button: Redefines wild type button criteria for Gremlin.
        _make_button_tip: Custom tooltip generation for Gremlin.
    """
    label_size: Optional[List[int]] = [12, 12]

    def __init__(
            self,
            df_matrix,
            sequence,
            pair_i: int,
            pair_j: int,
            parent=None,
            func: Optional[Callable] = None,
            cmap='bwr',
            button_size=12):
        """
        Initializes the QButtonMatrixGremlin widget.

        Args:
            df_matrix (pd.DataFrame): Dataframe representing the matrix.
            sequence (str): Full sequence of residues.
            pair_i (int): Index of the first pair.
            pair_j (int): Index of the second pair.
            parent: Parent widget.
            func (Optional[Callable]): Function called on button click.
            cmap (str): Colormap name for button colors.
            button_size (int): Size of the buttons.
        """
        super().__init__(df_matrix, sequence, func, parent, cmap, True, button_size)
        self.pair_i = pair_i
        self.pair_j = pair_j

    def get_WT_label(self, row_name: str, col_name: str, row: int, col: int) -> str:
        return 'WT'

    def is_wt_button(self, row_name: str, col_name: str, row: int, col: int):
        """
        Determines if a button corresponds to a wild type (WT) pair for Gremlin.

        Args:
            row_name (str): Name of the row.
            col_name (str): Name of the column.
            row (int): Row index.
            col (int): Column index.

        Returns:
            bool: True if the button represents a WT pair, False otherwise.
        """
        return row_name == self.sequence[self.pair_i] and self.alphabet_col[col] == self.sequence[self.pair_j]

    def _make_button_tip(
            self,
            row_name: str,
            col_name: str,
            value: float,
            row: Optional[int] = None,
            col: Optional[int] = None,
            is_wt_pair: bool = False):
        """
        Constructs a tooltip for a button in Gremlin.

        Args:
            row_name (str): Name of the row.
            col_name (str): Name of the column.
            value (float): Value associated with the button.
            row (Optional[int]): Row index.
            col (Optional[int]): Column index.
            is_wt_pair (bool): Whether the button is a WT pair.

        Returns:
            str: Tooltip text for the button.
        """
        button_tip_i = (
            f"{self.sequence[self.pair_i]}{str(self.pair_i + 1)}{row_name}"
            if self.sequence[self.pair_i] != row_name
            else ""
        )
        button_tip_j = (
            f"{self.sequence[self.pair_j]}{str(self.pair_j + 1)}{col_name}"
            if self.sequence[self.pair_j] != col_name
            else ""
        )
        button_tip = " - ".join(t for t in [button_tip_i, button_tip_j] if t)
        return button_tip if button_tip else 'WT'


def getExistingDirectory():
    return QtWidgets.QFileDialog.getExistingDirectory(
        None,
        "Open Directory",
        os.path.expanduser("~"),
        QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks,
    )


# an open file version of pymol.Qt.utils.getSaveFileNameWithExt ;-)
def getOpenFileNameWithExt(*args, **kwargs):
    """
    Return a file name, append extension from filter if no extension provided.
    """
    import re

    fname, filter = QtWidgets.QFileDialog.getOpenFileName(*args, **kwargs)

    if not fname:
        return ""

    if "." not in os.path.split(fname)[-1]:
        m = re.search(r"\*(\.[\w\.]+)", filter)
        if m:
            # append first extension from filter
            fname += m.group(1)

    return fname


def set_widget_value(widget, value):
    """
    Sets the value of a PyQt5 widget based on the provided value.

    Args:
    - widget: The PyQt5 widget whose value needs to be set.
    - value: The value to be set on the widget.

    Supported Widgets and Value Types:
    - QDoubleSpinBox: Supports int, float, list or tuple (for setting range).
    - QSpinBox: Supports int, float, list or tuple (for setting range).
    - QComboBox: Supports str, list, tuple, dict.
    - QLineEdit: Supports str.
    - QProgressBar: Supports int, list or tuple (for setting range).
    - QLCDNumber: Supports any value (converted to string for display).
    - QCheckBox: Supports bool.
    - QStackedWidget: Supports list of image paths (adds ImageWidget widgets).
    - QGridLayout: Supports a string (image path) to add an ImageWidget widget.
    """

    def set_value_error(widget, value):
        logging.warning(f"FIX ME: Value {value} is not currently supported on widget {type(widget).__name__}")

    # Preprocess values according to types
    if callable(value):
        value = value()  # Call the function to get the value if value is callable

    if isinstance(value, Iterable) and not isinstance(value, (str, list, tuple, dict)):
        value = list(value)  # Convert iterable (excluding strings, lists, tuples, dicts) to list

    # Setting values
    if isinstance(widget, QtWidgets.QDoubleSpinBox):
        if isinstance(value, (int, float)):
            widget.setValue(float(value))
        elif isinstance(value, (list, tuple)) and len(value) > 1:
            widget.setRange(float(value[0]), float(value[1]))
    elif isinstance(widget, QtWidgets.QSpinBox):
        if isinstance(value, (int, float)):
            widget.setValue(int(value))
        elif isinstance(value, (list, tuple)) and len(value) > 1:
            widget.setRange(int(value[0]), int(value[1]))
    elif isinstance(widget, QtWidgets.QComboBox):
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
    elif isinstance(widget, QtWidgets.QLCDNumber):
        widget.display(str(value))
    elif isinstance(widget, QtWidgets.QCheckBox):
        widget.setChecked(bool(value))
    elif isinstance(widget, QtWidgets.QStackedWidget):
        if isinstance(value, list):
            while widget.count() > 0:
                widget.removeWidget(widget.widget(0))
            for image_path in value:
                image_widget = ImageWidget(image_path)  # Assuming ImageWidget is defined elsewhere
                widget.addWidget(image_widget)
            if value:
                widget.setCurrentIndex(0)
    elif isinstance(widget, QtWidgets.QGridLayout):
        if isinstance(value, str) and os.path.exists(value):
            # Clear the existing widgets from gridLayout_interact_pairs
            for i in reversed(range(widget.count())):
                widget = widget.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()
            image_widget = ImageWidget(value)  # Assuming ImageWidget is defined elsewhere
            widget.addWidget(image_widget)
    else:
        set_value_error(widget, value)


def get_widget_value(widget):
    """
    Retrieves the value from a PyQt5 widget.

    Args:
    - widget: The PyQt5 widget from which the value needs to be retrieved.

    Returns:
    The current value of the widget.

    Supported Widgets:
    - QDoubleSpinBox, QSpinBox: Returns the current value as float or int.
    - QComboBox: Returns the current text or the userData of the current item if any.
    - QLineEdit: Returns the current text as str.
    - QProgressBar: Returns the current value as int.
    - QLCDNumber: Returns the current value as float.
    - QCheckBox: Returns the checked state as bool.

    Raises:
    - ValueError: If the widget type is not supported for value retrieval.
    """
    if isinstance(widget, QtWidgets.QDoubleSpinBox) or isinstance(widget, QtWidgets.QSpinBox):
        return widget.value()
    elif isinstance(widget, QtWidgets.QComboBox):
        return widget.currentText()
    elif isinstance(widget, QtWidgets.QLineEdit):
        return widget.text()
    elif isinstance(widget, QtWidgets.QProgressBar):
        return widget.value()
    elif isinstance(widget, QtWidgets.QLCDNumber):
        return float(widget.value())
    elif isinstance(widget, QtWidgets.QCheckBox):
        return widget.isChecked()
    else:
        raise ValueError(f"Widget type {type(widget).__name__} is not supported for value retrieval.")


def refresh_widget_while_another_changed(
    trigger_widget_id: str, target_widget_id: str, target_data_group: Dict[str, tuple]
):

    from REvoDesign import ConfigBus, reload_config_file

    trigger_widget = ConfigBus().get_widget_from_cfg_item(trigger_widget_id)
    target_widget = ConfigBus().get_widget_from_cfg_item(target_widget_id)

    reload_config_file()
    trigger_value = get_widget_value(widget=trigger_widget)

    if trigger_value in target_data_group:

        for _, target_data in enumerate(target_data_group.get(trigger_value, "")):
            set_widget_value(widget=target_widget, value=target_data)


class ParallelExecutor:
    def __init__(
        self,
        func: Callable,
        args: Iterable[Any],
        n_jobs: int,
        backend: str = "auto",
        verbose: bool = 0,
        kwargs: Union[tuple[dict], list[dict], None] = None,
    ):

        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.n_jobs = n_jobs

        # guessing backend according to OS
        if not backend == "auto":
            self.backend = backend
        else:
            self.backend = "loky"

        self.verbose = verbose
        logging.debug(f"Parallel Executor initialized with backend {backend}: {self.backend}")

    def run(self):
        from joblib import Parallel, delayed

        logging.info(f"Workload in this run: {len(self.args)}")
        if not self.kwargs:
            return Parallel(n_jobs=self.n_jobs, backend=self.backend, verbose=self.verbose)(
                delayed(self.func)(*arg) for arg in self.args
            )

        if len(self.kwargs) != len(self.args):
            raise ValueError(f"Workload kwargs mismatch: {len(self.kwargs)=} != {len(self.args)=}")

        return Parallel(n_jobs=self.n_jobs, backend=self.backend, verbose=self.verbose)(
            delayed(self.func)(*arg, **kwarg) for arg, kwarg in zip(self.args, self.kwargs)
        )


class QtParallelExecutor(QtCore.QThread):
    """
    USAGE:
        # 1. set a bouncing progressbar
        progress_bar.setRange(0, 0)

        # 2. instantialize a parallel executor that is bound with target function, task option list, and the most
        # importantly, number of processors you would use with.
        self.parallel_executor = ParallelExecutor(self.process_position, mutagenesis_tasks, n_jobs=nproc)

        # 3. create a single for the progressbar (is it broken?)
        self.parallel_executor.progress_signal.connect(progress_bar.setValue)

        # 4. start the new thread
        self.parallel_executor.start()

        # 4. wait for its end and refresh the window, then take a short sleep so that the window UI can still be
        # active
        while not self.parallel_executor.isFinished():
            #logging.info(f'Running ....')
            refresh_window()
            time.sleep(0.001)

        # 5. after it is done, reset the progress bar to the job done state
        progress_bar.setRange(0, len(mutagenesis_tasks))
        progress_bar.setValue(len(mutagenesis_tasks))

        # 6. recieve the results
        self.results=self.parallel_executor.handle_result()

        # 7. continue the following code
        self.merging_sessions()

    """

    progress_signal = QtCore.pyqtSignal(int)
    result_signal = QtCore.pyqtSignal(list)
    finished_signal = QtCore.pyqtSignal()

    def __init__(
        self,
        func,
        args,
        n_jobs,
        backend="auto",
        verbose=0,
    ):
        super().__init__()
        self.func = func
        self.args = args
        self.n_jobs = n_jobs
        self.executor = ParallelExecutor(func, args, n_jobs, backend, verbose)

    def run(self):
        self.results = self.executor.run()
        self.progress_signal.emit(len(self.args))
        self.result_signal.emit(self.results)

    def handle_result(self):
        logging.debug("Sending results ...")
        return self.results


def create_cmap_icon(cmap: str):
    """
    Creates a square pixmap representing the color pattern of a specified colormap.

    Args:
    - cmap (str): Name of the colormap.

    Returns:
    - QtGui.QPixmap: Pixmap representing the color gradient of the colormap.

    Note:
    This function uses Matplotlib's colormap to generate a color gradient and creates a square pixmap
    with the color gradient to represent the colormap visually.

    Example Usage:
    ```python
    from pymol.Qt import QtWidgets
    import matplotlib.pyplot as plt

    # Assuming 'my_colormap' is a valid colormap name
    icon = create_cmap_icon('my_colormap')
    label = QtWidgets.QLabel()
    label.setPixmap(icon)
    label.show()
    plt.show()
    ```
    """

    # Create a pixmap representing the color pattern of the colormap
    color_map = matplotlib.colormaps[cmap]
    pixmap = QtGui.QPixmap(100, 100)  # Changed to create a square pixmap
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))  # Fill with transparent background

    # Draw color gradient representing the colormap
    painter = QtGui.QPainter(pixmap)
    gradient = QtGui.QLinearGradient(0, 0, 100, 100)  # Changed to create a square gradient
    for i in range(100):
        color = QtGui.QColor.fromRgbF(*color_map(i / 100)[:3])
        gradient.setColorAt(i / 100, color)
    painter.setBrush(QtGui.QBrush(gradient))
    painter.drawRect(0, 0, 100, 100)  # Changed to draw a square
    painter.end()

    return pixmap


def refresh_tree_widget(user_tree: Dict[str, Dict], treeWidget_ws_peers):
    """
    Refreshes a given tree widget with user data.

    Args:
    - user_tree (dict): Dictionary containing user information.
    - treeWidget_ws_peers (QtWidgets.QTreeWidget): Tree widget to be refreshed.

    Returns:
    - None
    """
    # Clear the existing table
    treeWidget_ws_peers.clear()
    if not user_tree:
        return

    host_info = user_tree.pop("Host")
    host_node = QtWidgets.QTreeWidgetItem(treeWidget_ws_peers)
    host_node.setText(0, f"Host: {host_info['user']}@{host_info['node']}")

    for key, value in host_info.items():
        child = QtWidgets.QTreeWidgetItem(host_node)
        child.setText(0, f"{key}: {value}")

    if not user_tree:
        return

    # Sort the user data by joined_time_stamp including UUIDs
    sorted_users = sorted(
        user_tree.items(),
        key=lambda x: x[1]["joined_time_stamp"],
        reverse=True,
    )

    # Refresh the tree view
    for uuid, user_info in sorted_users:
        user_node = QtWidgets.QTreeWidgetItem(treeWidget_ws_peers)
        user_node.setText(0, f"{user_info['user']}@{user_info['node']}")

        for key, value in user_info.items():
            child = QtWidgets.QTreeWidgetItem(user_node)
            child.setText(0, f"{key}: {value}")

        child = QtWidgets.QTreeWidgetItem(user_node)
        child.setText(0, f"uuid: {uuid}")

    return


@dataclass
class AskedValue:
    """
    Represents a single input field in the ValueDialog.

    Attributes:
        key (str): The unique identifier or label for the input field.
        val (Optional[Any]): The default or current value of the field.
        typing (type): The expected data type for the field's value.
        reason (Optional[str]): Additional description or reason for the field.
        required (bool): Indicates whether the field is mandatory.
        choices (Optional[Union[List, Tuple, Callable[[], Union[List, Tuple]]]]):
            Specifies available choices for the field. Can be:
            - List[Any]: A predefined list of options.
            - Tuple[Any]: A predefined tuple of options.
            - range: A range of values.
            - Callable[[], Union[List, Tuple, range]]: A function to dynamically generate options.
        source (Literal['None', 'File', 'Directory', 'JsonInput']):
            Specifies the source of the input field. Can be:
            - 'None': No specific source.
            - 'File': Input is expected to be a file path.
            - 'Directory': Input is expected to be a directory path.
            - 'JsonInput': Input is expected to be a JSON file input.
        ext (Optional[FExCol]): File extension filters for file and directory inputs.
    """

    key: str
    val: Optional[Any] = None
    typing: type = str
    reason: Optional[str] = None
    required: bool = False
    choices: Optional[Union[List, Tuple, range, Callable[[], Union[List, Tuple, range]]]] = None
    source: Literal["None", "File", "Directory", "JsonInput"] = "None"
    ext: Optional[FExCol] = None


class MultiCheckableComboBox(QtWidgets.QComboBox):
    def __init__(self, choices: List[str], parent=None):
        super().__init__(parent)
        self.choices = choices
        self.checked_items = set()

        # Use a custom model for multi-check items
        self.setModel(QtGui.QStandardItemModel(self))
        for choice in self.choices:
            self._add_checkable_item(choice)

    def _add_checkable_item(self, text):
        """Add a checkable item to the combo box."""
        item = QtGui.QStandardItem(text)
        item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
        item.setData(QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)
        self.model().appendRow(item)

    def get_checked_items(self) -> List[str]:
        """Retrieve all checked items."""
        checked = []
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if item.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                checked.append(item.text())
        return checked

    def set_checked_items(self, items: List[str]):
        """Set initial checked items."""
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if item.text() in items:
                item.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)

    def hidePopup(self):
        """Override to update selected items on close."""
        self.checked_items = set(self.get_checked_items())
        super().hidePopup()

    def currentText(self) -> str:
        """Override to show a comma-separated list of selected items."""
        return ", ".join(self.checked_items)


def real_bool(val: Any):
    """
    Convert the given value to its most likely boolean equivalent.

    Args:
        val: The value to be converted. Can be a string or an integer.

    Returns:
        bool: True if the value matches one of the predefined true values.
             False if the value matches one of the predefined false values.
    """
    # Check if the value matches any of the predefined true values
    if any(
        val == ans
        for ans in (
            "True",
            "true",
            "1",
            "yes",
            "Yes",
            "Y",
            1,
            True,
        )
    ):
        return True

    # Check if the value matches any of the predefined false values
    if any(
        val == ans
        for ans in (
            "False",
            "false",
            "0",
            "no",
            "No",
            "N",
            0,
            False,
        )
    ):
        return False


@dataclass
class AskedValueCollection:
    """
    Represents a collection of AskedValue objects, along with a banner message.

    Attributes:
        asked_values (List[AskedValue]): List of input fields for the dialog.
        banner (Optional[str]): A message to be displayed at the top of the dialog.
    """

    asked_values: List[AskedValue] = field(default_factory=list)
    banner: Optional[str] = None  # a banner message

    @property
    def need_action(self) -> bool:
        return any(asked.source != "None" for asked in self.asked_values)

    @property
    def asdict(self) -> Dict[str, Any]:
        """
        Converts the collection into a dictionary where the keys are the field labels
        and the values are their corresponding inputs.

        Returns:
            Dict[str, Any]: A dictionary representation of the collection.
        """
        return {
            asked.key: asked.typing(asked.val) if asked.typing is not bool else real_bool(asked.val)
            for asked in self.asked_values
        }

    def __bool__(self):
        """
        Evaluates the truthiness of the collection.

        Returns:
            bool: True if the collection contains at least one AskedValue.
        """
        return bool(self.asked_values)


class ValueDialog(QtWidgets.QDialog):
    def __init__(self, title: str, key_dict: AskedValueCollection, parent=None):
        """
        Initializes the ValueDialog with specified size policies to ensure a compact and clear layout.

        Args:
            title (str): The title of the dialog box.
            key_dict (AskedValueCollection): The collection of fields to display in the dialog.
            parent (Optional[QWidget]): The parent widget of the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.key_dict = key_dict.asked_values
        self.updated_values = []

        # Check if any AskedValue has file=True
        self.has_file_action = key_dict.need_action

        # Main layout
        self.layout = QtWidgets.QVBoxLayout()

        # Add banner at the top
        if key_dict.banner:
            banner_label = QtWidgets.QLabel(key_dict.banner)
            banner_label.setWordWrap(True)
            banner_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
            banner_label.setStyleSheet(
                """
                font-size: 14px;
                font-weight: bold;
                color: #333;
                padding: 10px;
                background-color: #f9f9f9;
                border: 1px solid #ccc;
                border-radius: 5px;
            """
            )
            self.layout.addWidget(banner_label)

        # Create the table with four columns
        if self.has_file_action:
            self.table = QtWidgets.QTableWidget(len(self.key_dict), 4)
            self.table.setHorizontalHeaderLabels(["Field", "Type", "Input", "Source"])
        else:
            self.table = QtWidgets.QTableWidget(len(self.key_dict), 3)
            self.table.setHorizontalHeaderLabels(["Field", "Type", "Input"])
        self.table.horizontalHeader().setStretchLastSection(True)

        # Configure horizontal size policy for compact width
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)  # Field column
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Type column
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)  # Input column
        if self.has_file_action:
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # Action column

        self.table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,  # Compact width
            QtWidgets.QSizePolicy.Policy.Expanding,  # Expanding height
        )

        self.table.verticalHeader().setVisible(False)  # Hide row numbers
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)  # Disable row selection
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)  # Prevent label editing

        # Vertical behavior: Adjust for row count
        max_visible_rows = 8
        row_height = self.table.verticalHeader().defaultSectionSize()
        if len(self.key_dict) > max_visible_rows:
            self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.table.setMinimumHeight(max_visible_rows * row_height)
        else:
            self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.table.setMinimumHeight(len(self.key_dict) * row_height)

        self.input_fields: Dict[str, Any] = {}
        self.input_fields_data_pair: Dict[str, AskedValue] = {}

        # Add fields to the table
        for row, item in enumerate(key_dict.asked_values):
            self._add_field_to_table(row, item)

        self.layout.addWidget(self.table)

        # Add OK and Cancel buttons
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")
        ok_button.clicked.connect(self._on_ok_clicked)
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

    def _add_field_to_table(self, row: int, asked_value: AskedValue):
        """
        Adds a key-value pair to the table as a row.

        Args:
            row (int): The row number to add the field.
            asked_value (AskedValue): The field details.
        """
        # Column 0: Field label
        key_label = QtWidgets.QLabel(asked_value.key)
        key_label.setToolTip(asked_value.reason or "")
        self.table.setCellWidget(row, 0, key_label)

        # Column 1: Typing information
        type_label = QtWidgets.QLabel(asked_value.typing.__name__)
        type_label.setToolTip(f"Expected type: {asked_value.typing.__name__}")
        self.table.setCellWidget(row, 1, type_label)

        # Column 2: Input widget
        choices = asked_value.choices
        if callable(choices):
            try:
                choices = choices()
                if asked_value.typing != list:  # not a multi-choice
                    choices = tuple(choices)  # ensure the choices are tuple to prevent multiple choices
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to fetch dynamic choices for '{asked_value.key}': {str(e)}"
                )
                choices = []

        # Column 2: Input widget
        if isinstance(choices, list):
            # MultiCheckableComboBox for list of choices
            widget = MultiCheckableComboBox(choices=choices)
            if asked_value.val:
                widget.set_checked_items(asked_value.val if isinstance(asked_value.val, list) else [asked_value.val])
        elif isinstance(choices, range):
            # QSpinBox or QDoubleSpinBox for range of numbers
            if asked_value.typing == float:
                widget = QtWidgets.QDoubleSpinBox()
                widget.setRange(choices.start, choices.stop)
                widget.setSingleStep(0.1)  # Increment step for floating-point numbers
            else:
                widget = QtWidgets.QSpinBox()
                widget.setRange(choices.start, choices.stop)
            widget.setValue(asked_value.val if asked_value.val else choices.start)
        elif isinstance(choices, tuple):
            # QComboBox for tuple of any
            widget = QtWidgets.QComboBox()
            widget.addItems(map(str, choices))
            if asked_value.val:
                widget.setCurrentText(str(asked_value.val))
        elif asked_value.typing == bool:
            widget = QtWidgets.QComboBox()
            widget.addItems(["True", "False"])
            widget.setCurrentText(str(asked_value.val))
        else:
            # Default: QLineEdit
            widget = QtWidgets.QLineEdit()
            widget.setText(str(asked_value.val) if asked_value.val is not None else "")
            if asked_value.required:
                widget.setPlaceholderText("Required")

        widget.setToolTip(asked_value.reason or "")
        self.input_fields[asked_value.key] = widget
        self.input_fields_data_pair[asked_value.key] = asked_value
        self.table.setCellWidget(row, 2, widget)

        # Column 3: Action button if file=True
        if asked_value.source == "File":
            action_button = QtWidgets.QPushButton("Browse")
            action_button.setToolTip("Browse for a file")
            action_button.clicked.connect(lambda: self._browse_file(widget, asked_value.ext))
            self.table.setCellWidget(row, 3, action_button)
        elif asked_value.source == "Directory":
            action_button = QtWidgets.QPushButton("Browse")
            action_button.setToolTip("Browse for a directory")
            action_button.clicked.connect(lambda: widget.setText(getExistingDirectory()))
            self.table.setCellWidget(row, 3, action_button)
        elif asked_value.source == "JsonInput":
            # Create a container widget for the layout
            container_widget = QtWidgets.QWidget()
            button_layout = QtWidgets.QHBoxLayout(container_widget)
            button_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for proper cell fit

            # Create and configure the "Input JSON" button
            input_action_button = QtWidgets.QPushButton("Input")
            input_action_button.setToolTip("Browse for an input JSON file")
            input_action_button.clicked.connect(lambda: widget.setText(ask_for_multiple_values_as_json()))
            # Set size policy to ResizeToContents
            input_action_button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed)
            button_layout.addWidget(input_action_button)

            # Create and configure the "Load" button
            load_action_button = QtWidgets.QPushButton("Load")
            load_action_button.setToolTip(f"Load a auto-savedJSON file($PWD/json_multi_input/***.json)")
            load_action_button.clicked.connect(lambda: self._browse_file(widget, FileExtentions.JSON))
            # Set size policy to ResizeToContents
            load_action_button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Fixed)
            button_layout.addWidget(load_action_button)

            # Set the container widget as the cell widget
            self.table.setCellWidget(row, 3, container_widget)

    def _browse_file(self, widget, exts: Optional[FExCol] = None):
        """
        Opens a file dialog to select a file and updates the input field.

        Args:
            widget (QWidget): The input widget to update with the selected file path.
        """
        # prevent circular import
        from REvoDesign.driver.file_dialog import FileDialog

        file_dialog = FileDialog(None, os.getcwd())
        selected_file = file_dialog.browse_filename(
            mode="r", exts=(FileExtentions.Any, exts) if exts else (FileExtentions.Any,)
        )
        if selected_file:
            widget.setText(selected_file)

    def _on_ok_clicked(self):
        """
        Handles the OK button click. Collects user inputs and validates required fields.
        """
        self.updated_values = []
        for key, widget in self.input_fields.items():
            if isinstance(widget, MultiCheckableComboBox):
                # MultiCheckableComboBox returns a list of selected items
                value = widget.get_checked_items()
            elif isinstance(widget, QtWidgets.QSpinBox) or isinstance(widget, QtWidgets.QDoubleSpinBox):
                # SpinBox or DoubleSpinBox returns a single value
                value = widget.value()
            elif isinstance(widget, QtWidgets.QComboBox):
                # ComboBox returns the selected value
                if self.input_fields_data_pair[key].typing != bool:
                    value = widget.currentText()
                else:
                    value = widget.currentText() == "True"
            elif isinstance(widget, QtWidgets.QLineEdit):
                # LineEdit returns a single string
                value = widget.text().strip()
            else:
                value = None

            original = next((item for item in self.key_dict if item.key == key), None)
            if original and original.required and not value:
                QtWidgets.QMessageBox.warning(self, "Missing Input", f"Please provide a value for '{key}'")
                return
            if original:
                self.updated_values.append(
                    AskedValue(
                        key=key,
                        val=value,
                        typing=original.typing,
                        reason=original.reason,
                        required=original.required,
                        choices=original.choices,
                    )
                )
        self.accept()


def ask_for_values(title: str, key_dict: AskedValueCollection) -> Optional[AskedValueCollection]:

    dialog = ValueDialog(title, key_dict)
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        return AskedValueCollection(dialog.updated_values)


class AppendableValueDialog(QtWidgets.QDialog):
    """
    A dialog box that allows users to dynamically add, edit, and remove key-value pairs.

    This dialog supports appending new rows with key-value pairs, where users can
    manage their entries interactively. The interface is scrollable to handle large numbers of rows.

    Attributes:
        row_widgets (List[Tuple[QHBoxLayout, QLineEdit, QLineEdit]]): Keeps track of all rows in the dialog.
    """

    def __init__(self, parent=None):
        """
        Initializes the AppendableValueDialog.

        Args:
            parent (Optional[QWidget]): The parent widget of the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Dynamic Key-Value Pairs")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)

        # Initialize main layout
        self.layout = QtWidgets.QVBoxLayout()
        self.row_widgets = []  # Keep track of row widgets

        # Create scroll area for rows
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout()
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)  # Reduce margins
        self.scroll_layout.setSpacing(5)  # Reduce spacing between rows
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.layout.addWidget(self.scroll_area)

        # Add initial row
        self._add_row()

        # Add the "+" button for adding new rows
        add_button = QtWidgets.QPushButton("+ Add Row")
        add_button.clicked.connect(self._add_row)
        self.layout.addWidget(add_button)

        # Add OK and Cancel buttons
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")
        ok_button.clicked.connect(self._on_ok_clicked)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

    def _add_row(self, key: str = "", val: str = ""):
        """
        Adds a new row for entering a key-value pair.

        Args:
            key (str): The default text for the key field.
            val (str): The default text for the value field.
        """
        row_layout = QtWidgets.QHBoxLayout()

        # Key field
        key_edit = QtWidgets.QLineEdit()
        key_edit.setPlaceholderText("Key")
        key_edit.setText(key or "")

        # Value field
        val_edit = QtWidgets.QLineEdit()
        val_edit.setPlaceholderText("Value")
        val_edit.setText(val or "")

        # Remove button
        remove_button = QtWidgets.QPushButton("-")
        remove_button.clicked.connect(lambda: self._remove_row(row_layout))

        # Add widgets to row layout
        row_layout.addWidget(key_edit)
        row_layout.addWidget(val_edit)
        row_layout.addWidget(remove_button)

        # Add row layout to scroll area
        self.scroll_layout.addLayout(row_layout)
        self.row_widgets.append((row_layout, key_edit, val_edit))

        # Dynamically adjust dialog height
        self._adjust_dialog_height()

    def _remove_row(self, row_layout):
        """
        Removes a specific row from the dialog.

        Args:
            row_layout (QHBoxLayout): The row layout to be removed.
        """
        for i, (layout, key_edit, val_edit) in enumerate(self.row_widgets):
            if layout == row_layout:
                # Remove all widgets in the row
                for j in reversed(range(layout.count())):
                    widget = layout.itemAt(j).widget()
                    if widget:
                        widget.deleteLater()
                # Remove the row layout from the parent layout
                self.scroll_layout.removeItem(layout)
                # Remove the corresponding entry from row_widgets
                del self.row_widgets[i]
                break

        # Dynamically adjust dialog height
        self._adjust_dialog_height()

    def _adjust_dialog_height(self):
        """
        Dynamically adjusts the height of the dialog based on the number of rows.
        """
        row_height = 30  # Approximate height of a row
        max_height = 600  # Maximum height for the dialog
        new_height = min(max_height, 150 + len(self.row_widgets) * row_height)
        self.resize(self.width(), new_height)

    def _on_ok_clicked(self):
        """
        Handles the OK button click. Collects all key-value pairs and validates input.

        Discards rows with empty keys and processes valid rows.
        """
        self.updated_values = []
        for _, key_edit, val_edit in self.row_widgets:
            key = key_edit.text().strip()
            val = val_edit.text().strip()
            if key:  # Discard rows with empty keys
                self.updated_values.append(AskedValue(key=key, val=val))
        self.accept()

    def get_values(self) -> AskedValueCollection:
        """
        Retrieves the user-provided key-value pairs as an AskedValueCollection.

        Returns:
            AskedValueCollection: A collection of the key-value pairs entered by the user.
        """
        return AskedValueCollection(getattr(self, "updated_values", []))


def ask_for_appendable_values() -> Optional[AskedValueCollection]:
    dialog = AppendableValueDialog()
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        return dialog.get_values()


def ask_for_multiple_values_as_json() -> str:
    data = ask_for_appendable_values()
    if not data:  # none or empty collection
        return ""
    data_id = id(data)
    json_fp = os.path.join("json_multi_input", f"{data_id}.json")
    os.makedirs(os.path.dirname(json_fp), exist_ok=True)

    json.dump(
        obj=data.asdict,
        fp=open(json_fp, "w"),
        indent=4,
    )

    return json_fp


def dialog_wrapper(
    title: str,
    banner: str,
    options: Tuple[AskedValue, ...],
) -> Callable:
    """
    A decorator to wrap a function and generate a dialog for user input.

    Args:
        title (str): The title of the dialog.
        banner (str): A banner message to display at the top of the dialog.
        options (Tuple[AskedValue, ...]): The static list of AskedValue objects to include in the dialog.

    Returns:
        Callable: The wrapped function that collects input from a dialog before execution.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Prepare dynamic values with optional index
            dynamic_values_with_index = kwargs.pop("dynamic_values", [])
            dynamic_values_with_index = sorted(dynamic_values_with_index, key=lambda x: x.get("index", len(options)))

            # Merge static and dynamic options based on index
            all_options = list(options)
            for dynamic_value in dynamic_values_with_index:
                index = dynamic_value.get("index", len(all_options))
                all_options.insert(index, dynamic_value["value"])

            # Create the dialog
            values = ask_for_values(
                title,
                AskedValueCollection(all_options, banner=banner),
            )

            # Exit if dialog is canceled
            if not values:
                return

            # Extract values from the dialog and pass them to the wrapped function
            func(**values.asdict)

        return wrapper

    return decorator


__all__ = [
    "notify_box",
    "decide",
    "refresh_window",
    "set_widget_value",
    "ImageWidget",
    "hold_trigger_button",
    "getExistingDirectory",
    "WorkerThread",
    "ValueDialog",
    "AskedValueCollection",
    "ask_for_values",
    "AppendableValueDialog",
    "ask_for_appendable_values",
]
