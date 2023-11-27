import os
from typing import Union
from pymol.Qt import QtWidgets, QtGui, QtCore
from absl import logging

from REvoDesign.tools.system_tools import OS_INFO, OS_TYPE


# Custom widget for displaying images
class ImageWidget(QtWidgets.QWidget):
    def __init__(self, image_path, parent=None):
        super(ImageWidget, self).__init__(parent)
        self.image_path = image_path

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        image = QtGui.QImage(self.image_path)
        painter.drawImage(self.rect(), image)


class QbuttonMatrix(QtWidgets.QWidget):
    """
    QbuttonMatrix - Custom widget for displaying a matrix of buttons.

    Usage:
        qbm = QbuttonMatrix(csv_file, parent=None, button_size=12)
        qbm.init_ui()  # Initialize the user interface

    Attributes:
        report_axes_signal (QtCore.pyqtSignal): Signal for reporting axes.
        alphabet (str): String containing amino acid symbols.
        button_size (int): Size of the buttons.
        _alphabet (list): List containing amino acid symbols as individual characters.
        matrix (list): 2D list representing the matrix loaded from the CSV file.
        min_value (float): Minimum value in the loaded matrix.
        max_value (float): Maximum value in the loaded matrix.
        sequence (str): String representing a sequence of amino acids.
        pos_i (int): Position index for sequence.
        pos_j (int): Position index for sequence.
    """
    # Define a custom signal for reporting axes
    report_axes_signal = QtCore.pyqtSignal(int, int)

    def __init__(self, csv_file, parent=None, button_size=12):
        """
        Initialize QbuttonMatrix.

        Args:
            csv_file (str): Path to the CSV file.
            parent (QWidget): Parent widget. Defaults to None.
            button_size (int): Size of the buttons. Defaults to 12.
        """
        super().__init__(parent)
        self.button_size = button_size
        self.alphabet = "ARNDCQEGHILKMFPSTWYV-"

        self._alphabet = list(self.alphabet)
        (
            self.matrix,
            self.min_value,
            self.max_value,
        ) = self.load_matrix_from_csv(csv_file)

        self.sequence = ''
        self.pos_i = 0
        self.pos_j = 0

    def load_matrix_from_csv(self, csv_file):
        """
        Load matrix data from a CSV file.

        Args:
            csv_file (str): Path to the CSV file.

        Returns:
            tuple: Tuple containing matrix (2D list), min_value (float), max_value (float).
        """
        import numpy as np

        try:
            import pandas as pd  # Import pandas here

            df = pd.read_csv(csv_file, index_col=0)

            # Remove rows and columns not in the alphabet
            df = df.loc[
                df.index.isin(self._alphabet), df.columns.isin(self._alphabet)
            ]

            # Convert the DataFrame to a 2D list
            matrix = df.values.tolist()

            return (
                matrix,
                -np.max((np.abs(df.values.min()), df.values.max())),
                np.max((np.abs(df.values.min()), df.values.max())),
            )
        except Exception as e:
            logging.error(f"Error loading CSV file: {str(e)}")
            return [], 0, 1  # Default to 0-1 range if there's an error

    def map_value_to_color(self, value):
        """
        Map a value to a QColor based on a colormap.

        Args:
            value (float): Value to be mapped.

        Returns:
            QColor: Color based on the mapped value.
        """
        import matplotlib.pyplot as plt

        # Map a value to a color using the 'bwr' colormap with reversed colors
        normalized_value = 1 - (value - self.min_value) / (
            self.max_value - self.min_value
        )
        colormap = plt.get_cmap('bwr')
        rgba_color = colormap(normalized_value)
        color = QtGui.QColor.fromRgbF(
            rgba_color[0], rgba_color[1], rgba_color[2], rgba_color[3]
        )
        return color

    def init_ui(self):
        """
        Initialize the user interface by creating buttons and labels based on the matrix and sequence.
        """
        layout = QtWidgets.QGridLayout()
        font = QtGui.QFont()
        font.setPointSize(self.button_size)
        font.setBold(True)

        size_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum
        )

        # logging.debug(f"Sequence: {self.sequence}")
        logging.debug(
            f"WT pair: {self.sequence[self.pos_i]}{self.pos_i+1}_{self.sequence[self.pos_j]}{self.pos_j+1}"
        )

        # Add row names as labels to the left of buttons
        for row, row_name in enumerate(self._alphabet):
            label = QtWidgets.QLabel(row_name)
            # Set the font size to 9
            label.setFont(font)
            label.setFixedSize(self.button_size, self.button_size)

            layout.addWidget(label, row, 0, QtCore.Qt.AlignLeft)
            for col in range(len(self._alphabet)):
                if row < len(self.matrix) and col < len(self.matrix[0]):
                    value = self.matrix[row][col]
                else:
                    value = 0  # Default value for elements outside the matrix
                color = self.map_value_to_color(value)
                is_wt_pair = (
                    row_name == self.sequence[self.pos_i]
                    and self._alphabet[col] == self.sequence[self.pos_j]
                )

                button = QtWidgets.QPushButton("&WT" if is_wt_pair else None)

                button.setSizePolicy(size_policy)
                button.setStyleSheet(
                    f"background-color: {color.name()};{'color: black;' if is_wt_pair else ''}"
                )
                button.clicked.connect(
                    lambda checked, r=row, c=col: self.report_axises(r, c)
                )
                layout.addWidget(
                    button, row, col + 1
                )  # +1 to account for row labels

        # Add a row of column labels as labels after buttons
        for col, col_name in enumerate(self._alphabet):
            label = QtWidgets.QLabel(col_name)

            label.setFont(font)
            label.setFixedSize(
                self.button_size, self.button_size
            )  # Set fixed size for column labels

            layout.addWidget(
                label, len(self._alphabet), col + 1, QtCore.Qt.AlignTop
            )

        self.setLayout(layout)

    def report_axises(self, row, col):
        """
        Report the axes when a button is clicked.

        Args:
            row (int): Row index of the clicked button.
            col (int): Column index of the clicked button.
        """
        logging.debug(f"Button at ({row}, {col}) clicked.")
        self.report_axes_signal.emit(row, col)


def getExistingDirectory():
    return QtWidgets.QFileDialog.getExistingDirectory(
        None,
        "Open Directory",
        os.path.expanduser('~'),
        QtWidgets.QFileDialog.ShowDirsOnly
        | QtWidgets.QFileDialog.DontResolveSymlinks,
    )


# an open file version of pymol.Qt.utils.getSaveFileNameWithExt ;-)
def getOpenFileNameWithExt(*args, **kwargs):
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


# A universal and versatile function for value setting. ;-)
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

    Example Usage:
    ```python
    # Set value for QDoubleSpinBox
    set_widget_value(double_spinbox, 25.5)

    # Set value for QComboBox using list
    set_widget_value(combo_box, ['Option 1', 'Option 2', 'Option 3'])

    # Set value for QProgressBar with range
    set_widget_value(progress_bar, [0, 100])

    # Set value for QCheckBox
    set_widget_value(checkbox, True)

    # Set value for QStackedWidget with a list of image paths
    set_widget_value(stacked_widget, ['path/to/image1.png', 'path/to/image2.png'])

    # Set value for QGridLayout with an image path
    set_widget_value(grid_layout, 'path/to/image.png')
    ```
    """

    def set_value_error(value,widget,type_value,type_widget):
        logging.warning(
                f'FIX ME: Value {value} ({type_value}) is not currently supported on widget {widget} ({type_widget})'
            )


    type_widget = type(widget)
    type_value = type(value)

    # preprocess values according to types
    if type_value == type(lambda: None):  # Check if value is a function
        value = value()  # If it's a function, call it to get the value
        type_value = type(value)
    
    if type_value == range or type_value == type(
        (x for x in range(0, 1))
    ):  # Check if value is a range or generator
        value = [
            x for x in value
        ]  # If it's a range or generator, expand it as a list
        type_value = type(value)

    # Setting values    
    if type_widget == QtWidgets.QDoubleSpinBox:
        if type_value == int or type_value==float:
            widget.setValue(float(value))
        elif (type_value == list or type_value == tuple) and len(value) >1 :
            widget.setRange(float(value[0]), float(value[1]))
        return
    
    if type_widget == QtWidgets.QSpinBox:
        if type_value == int or type_value==float:
            widget.setValue(int(value))
        elif (type_value == list or type_value == tuple) and len(value) >1:
            widget.setRange(int(value[0]), int(value[1]))
        return

    if type_widget == QtWidgets.QComboBox:
        if type_value != list and type_value != tuple and type_value != dict:
            widget.setCurrentText(str(value))
        elif type_value == list or type_value == tuple:
            widget.clear()
            widget.addItems(map(str, value))
        elif type_value == dict:
            widget.clear()
            for k,v in value.items():
                widget.addItem(v,k)
        else:
            set_value_error(value,widget,type_value,type_widget)
        return
    
    if type_widget == QtWidgets.QLineEdit:
        widget.setText(str(value))
        return
    
    if type_widget == QtWidgets.QProgressBar:
        if type_value == list or type_value == tuple:
            widget.setRange(int(value[0]), int(value[1]))
        elif type_value == int:
            widget.setValue(int(value))
        else:
            set_value_error(value,widget,type_value,type_widget)
        return
    
    if type_widget == QtWidgets.QLCDNumber:
        widget.display(str(value))
        return
    
    if type_widget == QtWidgets.QCheckBox:
        widget.setChecked(bool(value))
        return
    
    if type_widget == QtWidgets.QStackedWidget:
        # Check if the value is a list of image paths
        if type_value == list:
            # Remove all existing widgets from the stacked widget
            while widget.count() > 0:
                widget.removeWidget(widget.widget(0))
            # Add image widgets to the stacked widget
            for image_path in value:
                image_widget = ImageWidget(image_path)
                widget.addWidget(image_widget)
            # Show the first image by default
            if len(value) > 0:
                widget.setCurrentIndex(0)
        else:
            set_value_error(value,widget,type_value,type_widget)
        return
    
    if type_widget == QtWidgets.QGridLayout:
        if type_value == str and os.path.exists(value):
            # Clear the existing widgets from gridLayout_interact_pairs
            for i in reversed(range(widget.count())):
                widget = widget.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()
            image_widget = ImageWidget(value)
            widget.addWidget(image_widget)
        else:
            set_value_error(value,widget,type_value,type_widget)
        return
    



    logging.warning(
        f'FIX ME: Widget {widget} is not currently supported. '
    )
    return


class ParallelExecutor(QtCore.QThread):

    '''
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

    '''

    progress_signal = QtCore.pyqtSignal(int)
    result_signal = QtCore.pyqtSignal(list)
    finished_signal = QtCore.pyqtSignal()

    def __init__(
        self,
        func,
        args,
        n_jobs,
        backend='auto',
        verbose=0,
    ):
        super().__init__()
        self.func = func
        self.args = args
        self.n_jobs = n_jobs

        os_type = OS_TYPE
        # guessing backend according to OS
        if not backend == 'auto':
            self.backend = backend
        else:
            if os_type == 'Windows' or os_type == 'Darwin_Rosetta':
                self.backend = 'multiprocessing'
            else:
                self.backend = 'loky'

        self.verbose = verbose
        logging.debug(
            f"Parallel Executor initialized with backend {backend}: {self.backend}"
        )

    def run(self):
        from joblib import Parallel, delayed

        logging.info(f'Workload in this run: {len(self.args)}')
        self.results = Parallel(
            n_jobs=self.n_jobs, backend=self.backend, verbose=self.verbose
        )(delayed(self.func)(*arg) for arg in self.args)

        self.progress_signal.emit(len(self.args))
        self.result_signal.emit(self.results)

    def handle_result(self):
        logging.debug(f'Sending results ...')
        return self.results


def refresh_window():
    QtWidgets.QApplication.processEvents()


class WorkerThread(QtCore.QThread):
    """
    Custom worker thread for executing a function in a separate thread.

    Attributes:
    - result_signal (QtCore.pyqtSignal): Signal emitted when the result is available.
    - finished_signal (QtCore.pyqtSignal): Signal emitted when the thread finishes its execution.

    Methods:
    - __init__: Initializes the WorkerThread object.
    - run: Executes the specified function with arguments and emits the result through signals.
    - handle_result: Returns the result obtained after the thread execution.

    Example Usage:
    ```python
    def some_function(x, y):
        return x + y

    worker = WorkerThread(func=some_function, args=(10, 20))
    worker.result_signal.connect(handle_result_function)
    worker.finished_signal.connect(handle_finished_function)
    worker.start()
    ```
    """
    result_signal = QtCore.pyqtSignal(list)
    finished_signal = QtCore.pyqtSignal()

    def __init__(self, func, args=None, kwargs=None):
        super().__init__()
        self.func = func
        self.args = args if args is not None else ()
        self.kwargs = kwargs if kwargs is not None else {}
        self.results = None  # Define the results attribute

    def run(self):
        self.results = [self.func(*self.args, **self.kwargs)]
        if self.results:
            self.result_signal.emit(self.results)

    def handle_result(self):
        return self.results


def proceed_with_comfirm_msg_box(title='', description=''):
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


def set_window_font(main_window):
    font_families = QtGui.QFontDatabase().families()

    OS_TYPE_FONT_TABLE = {
        'Windows': ['Microsoft YaHei', 'Century Gothic'],
        'Linux': ['Nimbus Sans', 'DejaVu Sans'],
        #'Darwin': ['Chalkboard']
    }

    _OS_TYPE = OS_INFO.system
    if _OS_TYPE not in OS_TYPE_FONT_TABLE:
        return

    for font_str in OS_TYPE_FONT_TABLE[_OS_TYPE]:
        if font_str in font_families:
            font = QtGui.QFont()
            font.setFamily(font_str)
            main_window.setFont(font)
            return


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
    import matplotlib
    from pymol.Qt import QtGui

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