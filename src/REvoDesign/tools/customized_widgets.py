import gc
import json
import os
import warnings
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import (Any, Callable, Dict, List, Literal, Optional, Tuple,
                    TypedDict, Union, overload)
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from REvoDesign import issues
from REvoDesign.basic import FileExtensionCollection as FExCol
from REvoDesign.common import file_extensions as Fext
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.Qt import QtCore, QtGui, QtWidgets
from .package_manager import (WorkerThread, decide, hold_trigger_button,
                              notify_box, refresh_window,
                              run_worker_thread_with_progress)
logging = ROOT_LOGGER.getChild(__name__)
PYQT_VERSION_STR = QtCore.PYQT_VERSION_STR
class ImageWidget(QtWidgets.QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        image = QtGui.QImage(self.image_path)
        painter.drawImage(self.rect(), image)
class REvoDesignWidget(QtWidgets.QWidget):
    def __init__(self, object_name: Optional[str] = None, allow_repeat: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name or 'AnonymousWidget')
        self.allow_repeat = allow_repeat
        self.destroyed.connect(self.detach)
        if self.allow_repeat:
            return
        try:
            self.check_repeat()
        except RuntimeError as e:
            warnings.warn(issues.REvoDesignWidgetWarning(e))
            self.destroy()
            raise RuntimeError(f"a window named {self.objectName()} is already open.") from e
    def closeEvent(self, a0):
        try:
            self.detach()
        except Exception as e:
            logging.warning(e)
        return super().closeEvent(a0)
    def show(self):
        super().show()
        self.attach()
    def close(self):
        self.detach()
        return super().close()
    def check_repeat(self):
        from REvoDesign.driver.ui_driver import ConfigBus
        bus = ConfigBus()
        if bus.headless:
            return
        if not hasattr(bus.ui, 'open_windows'):
            return
        the_windows = [
            w for w in bus.ui.open_windows if hasattr(
                w, 'objectName') and getattr(
                w, 'objectName')() == self.objectName()]
        if any(the_windows):
            this_window: REvoDesignWidget = the_windows[0]
            this_window.raise_()
            raise RuntimeError(f"a window named {self.objectName()} is already open.")
    def attach(self):
        from REvoDesign.driver.ui_driver import ConfigBus
        bus = ConfigBus()
        if bus.headless:
            return
        logging.debug(f"Window {self.objectName()} attaching...")
        if not hasattr(bus.ui, 'open_windows'):
            bus.ui.open_windows = []
        bus.ui.open_windows.append(self)
        logging.debug(f'Window {self.objectName()} attached.')
    def detach(self):
        from REvoDesign.driver.ui_driver import ConfigBus
        bus = ConfigBus()
        if bus.headless:
            return
        logging.debug(f"Window {self.objectName()} detaching...")
        if hasattr(bus.ui, 'open_windows') and self in bus.ui.open_windows:
            bus.ui.open_windows.remove(self)
        logging.debug(f"Window {self.objectName()} destroyed and cleaned up.")
@dataclass(frozen=True)
class ButtonCoords:
    row: int
    row_name: str
    col: int
    col_name: str
class QButtonBrick(QtWidgets.QPushButton):  
    hover_signal = QtCore.pyqtSignal(int, int)
    leave_signal = QtCore.pyqtSignal()
    def __init__(
        self,
        coords: ButtonCoords,
        color: QtGui.QColor,
        label: Optional[str] = None,
        tooltip_text: Optional[str] = None,
        is_wt: Optional[bool] = False,
        size_policy: Optional[QtWidgets.QSizePolicy] = None,  
        parent=None,
    ):
        super().__init__(parent)
        self.coords = coords
        self.color = color
        self.is_wt = is_wt
        self.setStyleSheet(self.style_sheet)
        self.setObjectName(self.button_name)
        self.setText(label)
        self.setToolTip(tooltip_text)
        self.setSizePolicy(size_policy)
        self.setMouseTracking(True)  
    def enterEvent(self, event):
        self.hover_signal.emit(self.coords.row, self.coords.col)
        super().enterEvent(event)
    def leaveEvent(self, event):
        self.leave_signal.emit()
        super().leaveEvent(event)
    @property
    def button_name(self) -> str:
        return f"matrixButton_{self.coords.row}_vs_{self.coords.col}"
    @property
    def style_sheet(self) -> str:
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
    Floating hover cross widget that visually appears over the buttons as empty rectangular boxes.
        Initializes the hover cross.
        Args:
            button_size (int): Size of the button (width and height).
            parent: Parent widget.
        Updates the hover rectangles' position based on the hovered button.
        Args:
            button_rect (QRect): Geometry of the hovered button.
        self.hover_position = None
        self.update()
        self.hide()
    def paintEvent(self, event):
        if not self.hover_position:
            return  
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor("red"), self.edge_width)  
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)  
        button_width = self.button_size
        button_height = self.button_size
        center_x = self.hover_position.center().x()
        center_y = self.hover_position.center().y()
        horizontal_rect = QtCore.QRect(
            0, center_y - button_height // 2, self.width(), button_height
        )
        vertical_rect = QtCore.QRect(
            center_x - button_width // 2, 0, button_width, self.height()
        )
        painter.drawRect(horizontal_rect)
        painter.drawRect(vertical_rect)
class QButtonMatrix(QtWidgets.QWidget):
    label_size: Optional[List[int]] = [18, 12]
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
        scroll_x: bool = False,
    ):
        from REvoDesign.tools.utils import cmap_reverser
        super().__init__(parent)
        self.main_layout = QtWidgets.QStackedLayout(self)
        self.main_layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        self.matrix_widget = QtWidgets.QWidget()
        self.button_layout = QtWidgets.QGridLayout()
        self.matrix_widget.setLayout(self.button_layout)
        self.hover_cross = QHoverCross(button_size, self)
        self.main_layout.addWidget(self.matrix_widget)  
        self.main_layout.addWidget(self.hover_cross)    
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
    def on_hover(self, row: int, col: int):
        button = self.findChild(QButtonBrick, f"matrixButton_{row}_vs_{col}")
        if button:
            self.hover_cross.update_position(button.geometry())
    def on_leave(self):
        self.hover_cross.hide_hover()
    def _map_value_to_color(self, value):
        normalized_value = 1 - (value - self.min_value) / (self.max_value - self.min_value)
        rgba_color = self.colormap(normalized_value)
        return QtGui.QColor.fromRgbF(rgba_color[0], rgba_color[1], rgba_color[2], rgba_color[3])
    def _set_label_size(self, label: Any):
        if not (hasattr(self, 'label_size') and self.label_size):
            return
        if len(self.label_size) != 2:
            raise ValueError("label size must be a list of length 2")
        label.setFixedSize(*self.label_size)
    def is_wt_button(self, row_name: str, col_name: str, row: int, col: int):
        return row_name == self.sequence[int(col_name) - 1 + self.zero_index_offset]
    def get_WT_label(self, row_name: str, col_name: str, row: int, col: int) -> str:
        return row_name
    @property
    def shape(self) -> Tuple[int, int]:
        return (len(self.alphabet_row), len(self.alphabet_col))
    def _make_button_tip(
            self,
            row_name: str,
            col_name: str,
            value: float,
            row: Optional[int] = None,
            col: Optional[int] = None,
            is_wt_pair: bool = False):
        _WT = self.sequence[int(col_name) - 1 + self.zero_index_offset]
        _IDX = str(int(col_name) + self.zero_index_offset)
        _SUB = row_name
        _IS_WT_NOTE = ', WT' if is_wt_pair else ''
        return f"{_WT}{_IDX}{_SUB} ({value:.3f}){_IS_WT_NOTE}"
    def init_ui(self):
        font = QtGui.QFont()
        font.setPointSizeF(self.button_size * 0.8)
        font.setBold(True)
        logging.debug(
            f'Initialized button matrix with shape {self.shape}: {self.shape[0]} rows, {self.shape[1]} columns')
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        for row, row_name in enumerate(self.alphabet_row):
            label = QtWidgets.QLabel(row_name)
            label.setFont(font)
            if hasattr(self, '_set_label_size'):
                self._set_label_size(label)
            self.button_layout.addWidget(label, row, 0, QtCore.Qt.AlignRight)
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
                    label=f"&{self.get_WT_label(row_name, col_name, row, col)}" if is_wt_button else None,
                    tooltip_text=button_tip,
                    is_wt=is_wt_button,
                    size_policy=size_policy,
                )
                bfont = QtGui.QFont()
                bfont.setPointSizeF(self.button_size * .9)
                bfont.setBold(True)
                button.setFont(bfont)
                button.hover_signal.connect(self.on_hover)
                button.leave_signal.connect(self.on_leave)
                button.clicked.connect(lambda checked, r=row, c=col: self.signal_process(r, c))
                self.button_layout.addWidget(button, row, col + 1)
        for col, col_name in enumerate(self.alphabet_col):
            if self.zero_index_offset:
                try:
                    col_name = str(int(col_name) - self.zero_index_offset)
                except ValueError as e:
                    raise issues.UnsupportedDataTypeError(
                        f'Zero-index offset is not supported for Column where {self.alphabet_col}.\n'
                        f'Expected type is int or digit string, not {type(col_name)}.') from e
            label = QtWidgets.QLabel(str(col_name))
            label.setFont(font)
            if hasattr(self, '_set_label_size'):
                self._set_label_size(label)
            self.button_layout.addWidget(label, len(self.alphabet_col), col + 1,
                                         QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
    def signal_process(self, row, col):
        logging.debug(f"Button at ({row}, {col}) clicked.")
        if self.active_func is not None:
            trigger_button = self.findChild(QButtonBrick, f"matrixButton_{row}_vs_{col}")
            with hold_trigger_button(trigger_button):
                self.active_func(row, col)
                return
        else:
            self.report_axes_signal.emit(row, col)
class QButtonMatrixGremlin(QButtonMatrix):
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
        super().__init__(df_matrix, sequence, func, parent, cmap, True, button_size)
        self.pair_i = pair_i
        self.pair_j = pair_j
    def get_WT_label(self, row_name: str, col_name: str, row: int, col: int) -> str:
        return 'WT'
    def is_wt_button(self, row_name: str, col_name: str, row: int, col: int):
        return row_name == self.sequence[self.pair_i] and self.alphabet_col[col] == self.sequence[self.pair_j]
    def _make_button_tip(
            self,
            row_name: str,
            col_name: str,
            value: float,
            row: Optional[int] = None,
            col: Optional[int] = None,
            is_wt_pair: bool = False):
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
class MultiCheckableComboBox(QtWidgets.QComboBox):
    def __init__(self, choices: List[str], parent=None):
        super().__init__(parent)
        self.choices = choices
        self.checked_items = set()
        self.setModel(QtGui.QStandardItemModel(self))
        for choice in self.choices:
            self._add_checkable_item(choice)
    def _add_checkable_item(self, text):
        item = QtGui.QStandardItem(text)
        item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
        item.setData(QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)
        self.model().appendRow(item)
    def select_all(self):
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            item.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
    def unselect_all(self):
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            item.setData(QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)
    def invert_selection(self):
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            current_state = item.data(QtCore.Qt.CheckStateRole)
            item.setData(QtCore.Qt.Checked if current_state ==
                         QtCore.Qt.Unchecked else QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)
    def get_checked_items(self) -> List[str]:
        checked = []
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if item.data(QtCore.Qt.CheckStateRole) == QtCore.Qt.Checked:
                checked.append(item.text())
        return checked
    def set_checked_items(self, items: List[str]):
        for row in range(self.model().rowCount()):
            item = self.model().item(row)
            if item.text() in items:
                item.setData(QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)
    def hidePopup(self):
        self.checked_items = set(self.get_checked_items())
        super().hidePopup()
    def currentText(self) -> str:
        return ", ".join(sorted(self.checked_items))
def getExistingDirectory():
    return QtWidgets.QFileDialog.getExistingDirectory(  
        None,
        "Open Directory",
        os.path.expanduser("~"),
        QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks,  
    )
def getMultipleFiles(parent=None, exts: Optional[tuple[FExCol, ...]] = None):
    dialog = QtWidgets.QFileDialog(parent, "Select file(s)")  
    dialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFiles)  
    if exts:
        ext = FExCol.squeeze(exts)
        dialog.setNameFilter(ext.filter_string)
    if dialog.exec() == QtWidgets.QDialog.Accepted:  
        return dialog.selectedFiles()
    return []
def getOpenFileNameWithExt(*args, **kwargs):
    import re
    fname, filter = QtWidgets.QFileDialog.getOpenFileName(*args, **kwargs)  
    if not fname:
        return ""
    if "." not in os.path.split(fname)[-1]:
        m = re.search(r"\*(\.[\w\.]+)", filter)
        if m:
            fname += m.group(1)
    return fname
@overload
def set_widget_value(widget: QtWidgets.QStackedWidget, value: list): ...
@overload
def set_widget_value(widget: QtWidgets.QProgressBar, value: Union[int, List[int], tuple[int, int]]): ...
@overload
def set_widget_value(widget: Union[
    QtWidgets.QDoubleSpinBox,
    QtWidgets.QSpinBox],
    value: Union[int, float, list[str], tuple[str, str]]): ...
@overload
def set_widget_value(widget: MultiCheckableComboBox, value: Union[list, tuple, str, int, float]): ...
@overload
def set_widget_value(widget: QtWidgets.QComboBox, value: Union[list, tuple, dict, str, int, float, bool]): ...
@overload
def set_widget_value(widget: QtWidgets.QGridLayout, value: str): ...
@overload
def set_widget_value(widget: Union[
    QtWidgets.QLineEdit,
    QtWidgets.QLCDNumber,
    QtWidgets.QCheckBox
], value: Any): ...
def set_widget_value(widget, value):
    def set_value_error(widget: QtWidgets.QWidget, value: Any):
        logging.warning(f"FIX ME: Value {value} is not currently supported on widget {type(widget).__name__}")
    if callable(value):
        value = value()  
    if isinstance(value, Iterable) and not isinstance(value, (str, list, tuple, dict)):
        value = list(value)  
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
    elif isinstance(widget, MultiCheckableComboBox):
        if not isinstance(value, (list, tuple)):
            value = [value]
        widget.unselect_all()
        widget.set_checked_items([str(x) for x in value])
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
                image_widget = ImageWidget(image_path)  
                widget.addWidget(image_widget)
            if value:
                widget.setCurrentIndex(0)
    elif isinstance(widget, QtWidgets.QGridLayout):
        if isinstance(value, str) and os.path.exists(value):
            for i in reversed(range(widget.count())):
                widget = widget.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()
            image_widget = ImageWidget(value)  
            widget.addWidget(image_widget)
    else:
        set_value_error(widget, value)
@overload
def get_widget_value(widget: QtWidgets.QCheckBox) -> bool: ...  
@overload
def get_widget_value(widget: Union[  
    QtWidgets.QComboBox,
    QtWidgets.QLineEdit]) -> str: ...
@overload
def get_widget_value(widget: Union[  
    QtWidgets.QDoubleSpinBox,
    QtWidgets.QLCDNumber
]) -> float: ...
@overload
def get_widget_value(widget: Union[  
    QtWidgets.QSpinBox,
    QtWidgets.QProgressBar]) -> int: ...
@overload
def get_widget_value(widget: MultiCheckableComboBox) -> list[str]: ...  
def get_widget_value(widget: QtWidgets.QWidget) -> Any:
    if isinstance(widget, (QtWidgets.QDoubleSpinBox, QtWidgets.QSpinBox)):
        return widget.value()
    if isinstance(widget, MultiCheckableComboBox):
        return widget.get_checked_items()
    if isinstance(widget, QtWidgets.QComboBox):
        return widget.currentText()
    if isinstance(widget, QtWidgets.QLineEdit):
        return widget.text()
    if isinstance(widget, QtWidgets.QProgressBar):
        return widget.value()
    if isinstance(widget, QtWidgets.QLCDNumber):
        return float(widget.value())
    if isinstance(widget, QtWidgets.QCheckBox):
        return widget.isChecked()
    raise ValueError(f"Widget type {type(widget).__name__} is not supported for value retrieval.")
def widget_signal_tape(widget: QtWidgets.QWidget, event):
    if isinstance(
        widget,
        (
            QtWidgets.QDoubleSpinBox,
            QtWidgets.QSpinBox,
            QtWidgets.QProgressBar,
        ),
    ):
        widget.valueChanged.connect(event)
    elif isinstance(widget, QtWidgets.QComboBox):
        widget.currentTextChanged.connect(event)
        widget.editTextChanged.connect(event)
    elif isinstance(widget, QtWidgets.QLineEdit):
        widget.textChanged.connect(event)
        widget.textEdited.connect(event)
    elif isinstance(widget, QtWidgets.QCheckBox):
        widget.stateChanged.connect(event)
    else:
        raise NotImplementedError(
            f"{widget} {type(widget)} is not supported yet"
        )
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
    color_map = matplotlib.colormaps[cmap]
    pixmap = QtGui.QPixmap(100, 100)  
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))  
    painter = QtGui.QPainter(pixmap)
    gradient = QtGui.QLinearGradient(0, 0, 100, 100)  
    for i in range(100):
        color = QtGui.QColor.fromRgbF(*color_map(i / 100)[:3])
        gradient.setColorAt(i / 100, color)
    painter.setBrush(QtGui.QBrush(gradient))
    painter.drawRect(0, 0, 100, 100)  
    painter.end()
    return pixmap
def refresh_tree_widget(user_tree: Dict[str, Dict], treeWidget_ws_peers):
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
    sorted_users = sorted(
        user_tree.items(),
        key=lambda x: x[1]["joined_time_stamp"],
        reverse=True,
    )
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
    key: str
    val: Optional[Any] = None
    typing: type = str
    reason: Optional[str] = None
    required: bool = False
    choices: Optional[Union[Iterable, Callable[[], Optional[Iterable]]]] = None
    source: Literal["None", "File", "FileO", "Files", "Directory", "JsonInput"] = "None"
    ext: Optional[FExCol] = None
    multiple_choices: bool = False
def real_bool(val: Any):
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
    asked_values: List[AskedValue] = field(default_factory=list)
    banner: Optional[str] = None  
    @property
    def need_action(self) -> bool:
        return any(asked.source != "None" for asked in self.asked_values) or any(
            asked.typing is list for asked in self.asked_values)
    @property
    def typing_fixed(self) -> 'AskedValueCollection':
        self_mirror = deepcopy(self)
        for asked in self_mirror.asked_values:
            if not asked.multiple_choices:
                asked.val = asked.typing(asked.val) if asked.typing is not bool else real_bool(asked.val)
            elif not isinstance(asked.val, Iterable):
                raise ValueError(f"Multiple choices are enabled, yet value is not iterable: {asked.val}")
            else:
                asked.val = [asked.typing(val) if asked.typing is not bool else real_bool(val) for val in asked.val]
        return self_mirror
    @property
    def asdict(self) -> Dict[str, Any]:
        return {asked.key: asked.val for asked in self.asked_values}
    def __bool__(self):
        return bool(self.asked_values)
    @classmethod
    def from_list(cls, list_of_asked_value: List[AskedValue]):
        return cls(asked_values=list_of_asked_value)
class ValueDialog(REvoDesignWidget):
    ok_signal = QtCore.pyqtSignal(list)
    cancel_signal = QtCore.pyqtSignal()
    def __init__(self, title: str, key_dict: AskedValueCollection, parent=None):
        super().__init__(f"ValueDialog - {title}", allow_repeat=False, parent=parent)
        self.setWindowTitle(title)
        self.key_dict = key_dict.asked_values
        self.updated_values = []
        self.setAcceptDrops(True)
        self.need_action = key_dict.need_action
        self.layout = QtWidgets.QVBoxLayout()
        if key_dict.banner:
            banner_label = QtWidgets.QLabel(key_dict.banner)
            banner_label.setWordWrap(True)
            banner_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
            banner_label.setStyleSheet(
            )
            self.layout.addWidget(banner_label)
        if self.need_action:
            self.table = QtWidgets.QTableWidget(len(self.key_dict), 4)
            self.table.setHorizontalHeaderLabels(["Field", "Type", "Input", "Action"])
        else:
            self.table = QtWidgets.QTableWidget(len(self.key_dict), 3)
            self.table.setHorizontalHeaderLabels(["Field", "Type", "Input"])
        self.table.horizontalHeader().setStretchLastSection(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)  
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  
        if self.need_action:
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  
        self.table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,  
            QtWidgets.QSizePolicy.Policy.Expanding,  
        )
        self.table.verticalHeader().setVisible(False)  
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)  
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)  
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
        for row, item in enumerate(key_dict.asked_values):
            self._add_field_to_table(row, item)
        self.layout.addWidget(self.table)
        load_save_layout = QtWidgets.QHBoxLayout()
        load_button = QtWidgets.QPushButton("Load")
        load_button.clicked.connect(self._on_load_clicked)
        load_button.setObjectName("Load")
        load_button.setToolTip(
            'Load the previous saved recipe to replicate the same settings. '
            'Also, you can drag and drop the recipe file (json) into this window here.')
        save_button = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self._on_save_clicked)
        save_button.setObjectName("Save")
        save_button.setToolTip("Save the current values as a new recipe.")
        load_save_layout.addWidget(load_button)
        load_save_layout.addWidget(save_button)
        self.layout.addLayout(load_save_layout)
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK")
        ok_button.setObjectName("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setObjectName("Cancel")
        ok_button.clicked.connect(self._on_ok_clicked)
        cancel_button.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)
    def _add_field_to_table(self, row: int, asked_value: AskedValue):
        required_star = '<span style=" font-weight:600; color:
        key_label = QtWidgets.QLabel(f"{required_star if asked_value.required else ''}{asked_value.key}")
        key_label.setToolTip(f"{'[REQUIRED] ' if asked_value.required else ''}{asked_value.reason}" or "")
        self.table.setCellWidget(row, 0, key_label)
        type_label = QtWidgets.QLabel(asked_value.typing.__name__)
        type_label.setToolTip(f"Expected type: {asked_value.typing.__name__}")
        self.table.setCellWidget(row, 1, type_label)
        choices = asked_value.choices
        if callable(choices):
            try:
                choices = choices()
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to fetch dynamic choices for '{asked_value.key}': {str(e)}"
                )
                choices = None
        if asked_value.multiple_choices:
            if not choices:
                raise issues.InternalError(f"Multi-choice field must have a valid choices, not {choices}")
            widget = MultiCheckableComboBox(choices=list(choices))
            if asked_value.val:
                widget.set_checked_items(asked_value.val if isinstance(asked_value.val, list) else [asked_value.val])
        elif asked_value.typing == bool:
            widget = QtWidgets.QCheckBox()
            widget.setChecked(bool(asked_value.val))
        elif isinstance(choices, range):
            if asked_value.typing == float:
                widget = QtWidgets.QDoubleSpinBox()
                widget.setRange(choices.start, choices.stop)
                widget.setSingleStep(0.1)  
            else:
                widget = QtWidgets.QSpinBox()
                widget.setRange(choices.start, choices.stop)
            if asked_value.val is not None:
                widget.setValue(asked_value.typing(asked_value.val))
            else:
                widget.setValue(choices.start)
        elif isinstance(choices, (tuple, list, filter)):
            choices = tuple(choices) if not isinstance(choices, filter) else tuple(deepcopy(choices))
            if not choices:
                raise issues.InternalError(f"Drop-down field must have a valid choices, not {choices}")
            widget = QtWidgets.QComboBox()
            widget.addItems(map(str, choices))
            widget.setCurrentText(str(asked_value.val) or str(choices[0]))
        else:
            widget = QtWidgets.QLineEdit()
            widget.setText(str(asked_value.val) or "")
            if asked_value.required:
                widget.setPlaceholderText("Required")
        widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        widget.setToolTip(asked_value.reason or "")
        self.input_fields[asked_value.key] = widget
        self.input_fields_data_pair[asked_value.key] = asked_value
        self.table.setCellWidget(row, 2, widget)
        action_button_size_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Fixed)
        if asked_value.source in ("File", 'FileO'):
            action_button = QtWidgets.QPushButton("Browse")
            action_button.setToolTip("Browse for a file")
            action_button.clicked.connect(
                lambda: self._browse_file(
                    widget,
                    asked_value.ext,
                    mode='r' if asked_value.source == "File" else 'w'))
            self.table.setCellWidget(row, 3, action_button)
        elif asked_value.source == "Files":
            action_button = QtWidgets.QPushButton("Browse")
            action_button.setToolTip("Browse for multiple files")
            action_button.clicked.connect(lambda: self._browse_file(widget, multiple=True))
            self.table.setCellWidget(row, 3, action_button)
        elif asked_value.source == "Directory":
            action_button = QtWidgets.QPushButton("Browse")
            action_button.setToolTip("Browse for a directory")
            action_button.clicked.connect(lambda: widget.setText(getExistingDirectory()))
            self.table.setCellWidget(row, 3, action_button)
        elif asked_value.source == "JsonInput":
            container_widget = QtWidgets.QWidget()
            button_layout = QtWidgets.QHBoxLayout(container_widget)
            button_layout.setContentsMargins(0, 0, 0, 0)  
            input_action_button = QtWidgets.QPushButton("Input")
            input_action_button.setToolTip("Browse for an input JSON file")
            input_action_button.clicked.connect(lambda: widget.setText(ask_for_multiple_values_as_json()))
            input_action_button.setSizePolicy(action_button_size_policy)
            button_layout.addWidget(input_action_button)
            load_action_button = QtWidgets.QPushButton("Load")
            load_action_button.setToolTip("Load a auto-savedJSON file($PWD/json_multi_input/***.json)")
            load_action_button.clicked.connect(lambda: self._browse_file(widget, Fext.JSON))
            load_action_button.setSizePolicy(action_button_size_policy)
            button_layout.addWidget(load_action_button)
            self.table.setCellWidget(row, 3, container_widget)
        elif asked_value.multiple_choices:
            container_widget = QtWidgets.QWidget()
            button_layout = QtWidgets.QHBoxLayout(container_widget)
            button_layout.setContentsMargins(0, 0, 0, 0)  
            select_all_button = QtWidgets.QPushButton("All")
            select_all_button.setToolTip("Select all")
            select_all_button.clicked.connect(widget.select_all)
            select_all_button.setSizePolicy(action_button_size_policy)
            button_layout.addWidget(select_all_button)
            select_none_button = QtWidgets.QPushButton("None")
            select_none_button.setToolTip("Unselect all")
            select_none_button.clicked.connect(widget.unselect_all)
            select_none_button.setSizePolicy(action_button_size_policy)
            button_layout.addWidget(select_none_button)
            select_invert_button = QtWidgets.QPushButton("Invert")
            select_invert_button.setToolTip("Invert selection")
            select_invert_button.clicked.connect(widget.invert_selection)
            select_invert_button.setSizePolicy(action_button_size_policy)
            button_layout.addWidget(select_invert_button)
            self.table.setCellWidget(row, 3, container_widget)
    def _browse_file(self, widget, exts: Optional[FExCol] = None,
                     multiple: bool = False, mode: Literal['r', 'w'] = 'r'):
        from REvoDesign.driver.file_dialog import FileDialog
        ext = (exts, Fext.Any,) if exts else (Fext.Any,)
        file_dialog = FileDialog(None, os.getcwd())
        if multiple:
            selected_file = file_dialog.browse_multiple_files(ext)
            if selected_file:
                widget.setText('|'.join(selected_file))
            return
        selected_file = file_dialog.browse_filename(
            mode=mode, exts=ext
        )
        if selected_file:
            widget.setText(selected_file)
    def _on_ok_clicked(self):
        self.updated_values: List[AskedValue] = []
        for key, widget in self.input_fields.items():
            try:
                value = get_widget_value(widget)
            except Exception as e:
                logging.error(f"Error getting value from widget {widget}: {e}")
                raise ValueError(f"Error getting value from widget {widget}: {e}") from e
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
                        multiple_choices=original.multiple_choices,
                    )
                )
        self.ok_signal.emit(self.updated_values)
    def _on_cancel_clicked(self):
        self.cancel_signal.emit()
        self.close()
        gc.collect()
    def _on_save_clicked(self):
        from REvoDesign import __version__
        from REvoDesign.driver.file_dialog import FileDialog
        file_dialog = FileDialog(None, os.getcwd())
        selected_file = file_dialog.browse_filename(
            mode='w', exts=(Fext.JSON, Fext.Any)
        )
        if not selected_file:
            return
        contents_to_save = {
            'metadata': {
                '__window__': self.windowTitle(),
                '__version__': __version__,
                '__date__': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            '__asked_values__': {a.key: get_widget_value(self.input_fields[a.key]) for a in self.key_dict}
        }
        try:
            with open(selected_file, 'w') as f:
                json.dump(contents_to_save, f, indent=4)
                logging.info(f"Saved recipe: {selected_file}")
        except Exception as e:
            logging.error(f"Error loading json file {selected_file}: {e}")
            raise ValueError(f"Error loading json file {selected_file}: {e}") from e
    def _load_json_file(self, selected_file):
        from REvoDesign import __version__
        contents_to_load: Dict[str, Dict[str, Any]] = json.load(open(selected_file))
        if contents_to_load['metadata']['__window__'] != self.windowTitle():
            logging.error(f"The recipe is made for Dialog `{contents_to_load['metadata']['__window__']}`, "
                          f"which is not compatible with the current window `{self.windowTitle()}`")
            return
        if contents_to_load['metadata']['__version__'] != __version__:
            logging.warning(
                f"The recipe is made with version {contents_to_load['metadata']['__version__']}, "
                f"which may not be compatible from the current version {__version__}")
        logging.info(f'Recipe created at: {contents_to_load["metadata"]["__date__"]}')
        for key, val in contents_to_load['__asked_values__'].items():
            widget = self.input_fields[key]
            set_widget_value(widget, val)
        logging.info(f"Loaded recipe: {selected_file}")
    def _on_load_clicked(self):
        from REvoDesign.driver.file_dialog import FileDialog
        file_dialog = FileDialog(None, os.getcwd())
        selected_file = file_dialog.browse_filename(
            mode='r', exts=(Fext.JSON, Fext.Any)
        )
        if not selected_file:
            return
        self._load_json_file(selected_file)
    def dragEnterEvent(self, a0):
        if a0.mimeData().hasUrls:
            a0.accept()
        else:
            a0.ignore()
        return super().dragEnterEvent(a0)
    def dragMoveEvent(self, a0):
        if a0.mimeData().hasUrls:
            a0.accept()
        else:
            a0.ignore()
        return super().dragMoveEvent(a0)
    def dropEvent(self, a0):
        if a0.mimeData().hasUrls:
            a0.setDropAction(QtCore.Qt.CopyAction)
            file_path = a0.mimeData().urls()[0].toString()
            file_path = file_path.replace('file://', '')
            if not file_path.endswith('.json'):
                raise ValueError('Only json files are allowed')
            self._load_json_file(file_path)
            a0.accept()
        else:
            a0.ignore()
        return super().dropEvent(a0)
class AppendableValueDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dynamic Key-Value Pairs")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        self.layout = QtWidgets.QVBoxLayout()
        self.row_widgets = []  
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout()
        self.scroll_layout.setContentsMargins(5, 5, 5, 5)  
        self.scroll_layout.setSpacing(5)  
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.layout.addWidget(self.scroll_area)
        self._add_row()
        add_button = QtWidgets.QPushButton("+ Add Row")
        add_button.clicked.connect(self._add_row)
        self.layout.addWidget(add_button)
        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK")
        ok_button.setObjectName("OK")
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setObjectName("Cancel")
        ok_button.clicked.connect(self._on_ok_clicked)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)
    def _add_row(self, key: str = "", val: str = ""):
        row_layout = QtWidgets.QHBoxLayout()
        key_edit = QtWidgets.QLineEdit()
        key_edit.setPlaceholderText("Key")
        key_edit.setText(key or "")
        val_edit = QtWidgets.QLineEdit()
        val_edit.setPlaceholderText("Value")
        val_edit.setText(val or "")
        remove_button = QtWidgets.QPushButton("-")
        remove_button.clicked.connect(lambda: self._remove_row(row_layout))
        row_layout.addWidget(key_edit)
        row_layout.addWidget(val_edit)
        row_layout.addWidget(remove_button)
        self.scroll_layout.addLayout(row_layout)
        self.row_widgets.append((row_layout, key_edit, val_edit))
        self._adjust_dialog_height()
    def _remove_row(self, row_layout):
        for i, (layout, key_edit, val_edit) in enumerate(self.row_widgets):
            if layout == row_layout:
                for j in reversed(range(layout.count())):
                    widget = layout.itemAt(j).widget()
                    if widget:
                        widget.deleteLater()
                self.scroll_layout.removeItem(layout)
                del self.row_widgets[i]
                break
        self._adjust_dialog_height()
    def _adjust_dialog_height(self):
        row_height = 30  
        max_height = 600  
        new_height = min(max_height, 150 + len(self.row_widgets) * row_height)
        self.resize(self.width(), new_height)
    def _on_ok_clicked(self):
        self.updated_values = []
        for _, key_edit, val_edit in self.row_widgets:
            key = key_edit.text().strip()
            val = val_edit.text().strip()
            if key:  
                self.updated_values.append(AskedValue(key=key, val=val))
        self.accept()
    def get_values(self) -> AskedValueCollection:
        return AskedValueCollection(getattr(self, "updated_values", []))
def ask_for_appendable_values() -> Optional[AskedValueCollection]:
    dialog = AppendableValueDialog()
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        return dialog.get_values()
def ask_for_multiple_values_as_json() -> str:
    data = ask_for_appendable_values()
    if not data:  
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
class AskedValueDynamic(TypedDict):
    value: AskedValue
    index: int
def dialog_wrapper(
    title: str,
    banner: str,
    options: Tuple[AskedValue, ...],
) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            dynamic_values_with_index: List[AskedValueDynamic] = kwargs.pop("dynamic_values", [])
            dynamic_values_with_index = sorted(dynamic_values_with_index, key=lambda x: x.get("index", len(options)))
            all_options = list(options)
            for dynamic_value in dynamic_values_with_index:
                index = dynamic_value.get("index", len(all_options))
                all_options.insert(index, dynamic_value["value"])
            values: Optional[AskedValueCollection] = None
            dialog = ValueDialog(title, AskedValueCollection(all_options, banner=banner))
            def set_values(x: List[AskedValue]):
                nonlocal values
                values = AskedValueCollection.from_list(x)
                dialog.close()
                func(**values.typing_fixed.asdict)
            dialog.ok_signal.connect(set_values)
            dialog.show()
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
    "AppendableValueDialog",
    "ask_for_appendable_values",
]