
from collections import defaultdict
import contextlib
import multiprocessing
import threading

from pymol import cmd
import os
from pymol.Qt import *
from pymol.Qt import QtWidgets,QtGui, QtCore

from threading import  Thread

import time

def determine_polymer_protein(sele='(all)'):
    # return a list of protein that contain at least 10 residues
    return len(list(set([atom.resi for atom in cmd.get_model(f'( {sele}) and polymer.protein').atom]))) > 10

def determine_small_molecule(sele='(all)'):
    # return a list of small molecules
    return [''] + list(set([atom.resn for atom in cmd.get_model(f'( {sele} ) and (not polymer.protein)').atom]))

def determine_molecule_objects():
    objects=[object for object in cmd.get_names('public_nongroup_objects',enabled_only=1,selection='all') if determine_polymer_protein(object)]
    return objects

def determine_chain_id(sele='(all)'):
    # return a list of chain IDs that assigned to a protein molecule
    return [chain_id for chain_id in cmd.get_chains(sele) if determine_polymer_protein(f'( {sele} and c. {chain_id} )')]

def determine_nproc():
    return [x for x in range(1, os.cpu_count()+1)]

def determine_exclusion():
    return [""]+ [sel for sel in cmd.get_names(type='selections',enabled_only=0,selection='(all)')]

def determine_system():
    import platform
    return platform.system()


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

def getExistingDirectory():
    return QtWidgets.QFileDialog.getExistingDirectory("Open Directory", 
                                                os.path.expanduser('~'), 
                                                QtWidgets.QFileDialog.ShowDirsOnly | 
                                                QtWidgets.QFileDialog.DontResolveSymlinks)

def check_dirname_exists(fp):
    return os.path.exists(os.path.dirname(fp))

def check_file_exists(fp):
    return os.path.exists(fp)


def get_molecule_sequence(molecule,chain_id):
    from absl import logging
    from Bio.Data import IUPACData
    protein_letters_3to1_upper={key.upper():val.upper() for key,val in IUPACData.protein_letters_3to1.items()}
    logging.debug(f'( {molecule} and c. {chain_id} and n. CA )')
    return ''.join([protein_letters_3to1_upper[atom.resn] for atom in cmd.get_model(f'( {molecule} and c. {chain_id} and n. CA )').atom])


def run_command(command_list, excutable='python', ):

    import sys
    import subprocess
    from absl import logging
    if excutable == 'python':
        python_exe = os.path.realpath(sys.executable)
        command_list=[python_exe] + command_list
    # TODO: enable shell executables

    while '' in command_list:
        command_list.remove('')
    
    logging.debug(command_list)

    result = subprocess.run(command_list, stderr=subprocess.PIPE,)

    return result

def refresh_window():
    QtWidgets.QApplication.processEvents()


def suppress_print(func):
    def wrapper(*args, **kwargs):
        with contextlib.redirect_stdout(open(os.devnull, 'w')):
            with contextlib.redirect_stderr(open(os.devnull, 'w')):
                result = func(*args, **kwargs)
        return result
    return wrapper

def minibatches(inputs_data, batch_size):
    for start_idx in range(0, len(inputs_data), batch_size):
        if len(inputs_data[start_idx:]) > batch_size:
            excerpt = slice(start_idx, start_idx + batch_size)
            print("Send data in length: %s" % len(inputs_data[excerpt]))
            yield inputs_data[excerpt]
        else:
            print("Send final data in length: %s" % len(inputs_data[start_idx:]))
            yield inputs_data[start_idx:]


def minibatches_generator(inputs_data_generator, batch_size):
    current_batch = []
    for data_point in inputs_data_generator:
        #print(f"Send data {data_point}")
        current_batch.append(data_point)
        if len(current_batch) == batch_size:
            yield current_batch
            current_batch = []

    # Yield any remaining data as a final batch
    if current_batch:
        yield current_batch



# Custom widget for displaying images
class ImageWidget(QtWidgets.QWidget):
    def __init__(self, image_path, parent=None):
        super(ImageWidget, self).__init__(parent)
        self.image_path = image_path

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        image = QtGui.QImage(self.image_path)
        painter.drawImage(self.rect(), image)

class WorkerThread(QtCore.QThread):
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


def run_worker_thread_with_progress(worker_function, progress_bar=None, *args, **kwargs):
    if progress_bar:
        progress_bar.setRange(0, 0)

    work_thread = WorkerThread(worker_function, args=args, kwargs=kwargs)
    work_thread.start()

    while not work_thread.isFinished():
        refresh_window()
        time.sleep(0.001)

    if progress_bar:
        progress_bar.setRange(0, 1)

    result = work_thread.handle_result()
    return result[0] if result else None

    
def parallel_run(func, input_args: list, num_proc: int):
    p = multiprocessing.Pool(num_proc)
    return p.map(func, input_args)



class CallBack(object):
    completed = defaultdict(int)
    
    def __init__(self, time, index, parallel):
        self.index = index
        self.parallel = parallel

    def __call__(self, index):
        CallBack.completed[self.parallel] += 1
        mycount = CallBack.completed[self.parallel]
        progress = (mycount / len(self.parallel._original_iterator)) * 100
        self.parallel.progress_signal.emit(progress)
        if self.parallel._original_iterator is not None: 
            self.parallel.dispatch_next()

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
    
    

    def __init__(self, func, args, n_jobs, backend='auto',verbose=0):
        from absl import logging
        super().__init__()
        self.func = func
        self.args = args
        self.n_jobs = n_jobs
        # guessing backend according to OS
        if not backend=='auto':
            self.backend=backend
        else:
            if determine_system() == 'Windows':
                self.backend='multiprocessing'
            else:
                self.backend='loky'

        self.verbose =verbose
        logging.debug(f"Parallel Executor initialized with backend {backend}: {self.backend}")

    def run(self):
        from absl import logging
        from joblib import Parallel, delayed
        logging.info(f'Workload in this run: {len(self.args)} ')
        self.results = Parallel(n_jobs=self.n_jobs,backend=self.backend,verbose=self.verbose)(delayed(self.func)(*arg) for arg in self.args)
        
        self.progress_signal.emit(len(self.args))
        self.result_signal.emit(self.results)
        
        
    def handle_result(self):
        from absl import logging
        logging.debug(f'Sending results ...')
        return self.results
    
    
        



class NestedWorkerThread(QtCore.QThread):
    progress_signal = QtCore.pyqtSignal(int)
    result_signal = QtCore.pyqtSignal(list)
    finished_signal = QtCore.pyqtSignal()

    def __init__(self, func, input_args, num_proc):
        super().__init__()
        self.func = func
        self.input_args = input_args
        self.num_proc = num_proc

    def run(self):
        self.results = self.parallel_run(self.func, self.input_args, self.num_proc)
        self.progress_signal.emit(len(self.input_args))
        self.result_signal.emit(self.results)
        self.finished_signal.emit()

    def parallel_run(self, func, input_args, num_proc):
        from joblib import Parallel, delayed
        self.results = Parallel(n_jobs=num_proc)(delayed(func)(*arg) for arg in input_args)
        
        return self.results

    def handle_result(self):
        return self.results
    

def extract_archive(archive_file, extract_to):
    """
    Extracts the contents of an archive file (zip, tar.gz, tar.bz2, tar.xz, or rar) to a specified directory.

    Args:
        archive_file (str): Path to the archive file.
        extract_to (str): Directory where the contents will be extracted.
    """
    try:
        if archive_file.endswith(".zip"):
            import zipfile
            import tarfile
            from absl import logging

            with zipfile.ZipFile(archive_file, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith((".tar.gz", ".tgz")):
            with tarfile.open(archive_file, 'r:*') as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith((".tar.bz2", ".tbz")):
            with tarfile.open(archive_file, 'r:bz2') as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith(".tar.xz"):
            with tarfile.open(archive_file, 'r:xz') as tar_ref:
                tar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        elif archive_file.endswith(".rar"):
            try:
                from unrar import rarfile
            except:
                cmd.system('pip install unrar')
                from unrar import rarfile
            with rarfile.RarFile(archive_file, 'r') as rar_ref:
                rar_ref.extractall(extract_to)
            logging.info(f"Extracted {archive_file} to {extract_to}")
        else:
            logging.warning(f"Unsupported archive format: {archive_file}")
    except Exception as e:
        logging.error(f"Error extracting {archive_file}: {str(e)}")




class QProgressBarton(QtWidgets.QPushButton):
    def __init__(self, existing_button=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet('''
            QPushButton {
                background-color: #ccc;
                border: 1px solid #000;
                border-radius: 5px;
                min-height: 20px;
            }
        ''')
        self.progress = 0
        self.min_value = 0
        self.max_value = 100  # Default maximum value
        self.bounce_timer = QtCore.QTimer(self)
        self.bounce_direction = 1

        if existing_button:
            self.replacePushButton(existing_button)

    def setRange(self, min_val, max_val):
        self.min_value = min_val
        self.max_value = max(max_val, min_val + 1)  # Ensure max_value is at least min_value + 1
        self.updateStyle()

    def setValue(self, value):
        # Ensure the value is within the specified range
        value = max(self.min_value, min(value, self.max_value))
        self.progress = value
        self.updateStyle()

    def value(self):
        return self.progress

    def updateStyle(self):
        # Constrain the progress value within the specified range
        self.progress = max(self.min_value, min(self.progress, self.max_value))

        # Calculate the progress as a percentage within the range
        scaling_factor = 4  # Adjust this factor to control the speed of progress
        percentage = (self.progress - self.min_value) / (self.max_value - self.min_value) * 100 * scaling_factor

        # Ensure that the percentage is within the [0, 100] range
        percentage = max(0, min(percentage, 100))

        # Calculate the text color transition from green to gray
        text_color = f'rgb({255 - int(percentage * 2.55)}, 255, {255 - int(percentage * 2.55)})'

        # Adjust the gradient stops for a narrower transition
        green_stop = min(percentage / 200, 1.0) 
        gray_stop = min((percentage / 200) + 0.01, 1.0)

        style = f'''
            QPushButton {{
                background: qlineargradient(x1:0 y1:0, x2:{green_stop} y2:0, stop:0 #00FF00, stop:{green_stop} #00FF00, stop:{gray_stop} #ccc, stop: #ccc);
                border: 1px solid #000;
                border-radius: 5px;
                min-height: 20px;
            }}
            QPushButton::disabled {{
                color: {text_color};
            }}
        '''
        print(style)

        self.setStyleSheet(style)

        # Check if minimum and maximum values are equal
        if self.min_value == self.max_value:
            # Start a bouncing animation
            self.bounce_timer.timeout.connect(self.bounceAnimation)
            self.bounce_timer.start(100)  # Adjust the bounce speed as needed





    def bounceAnimation(self):
        # Bounce the progress indicator
        if self.bounce_direction == 1:
            self.bounce_direction = -1
        else:
            self.bounce_direction = 1

        # Calculate the new value
        new_value = self.progress + (self.bounce_direction * 5)  # Adjust the bounce step as needed
        self.setValue(new_value)

    def replacePushButton(self, existing_button):
        # Copy properties and settings from the existing button
        self.setObjectName(existing_button.objectName())
        self.setGeometry(existing_button.geometry())
        self.setText(existing_button.text())
        self.setEnabled(existing_button.isEnabled())
        self.clicked.connect(existing_button.clicked)

        # Hide the existing button and replace it with the QProgressBarton
        existing_button.hide()
        if existing_button.parentWidget() and existing_button.parentWidget().layout():
            layout = existing_button.parentWidget().layout()
            layout.replaceWidget(existing_button, self)

class QbuttonMatrix(QtWidgets.QWidget):
    # Define a custom signal for reporting axes
    report_axes_signal = QtCore.pyqtSignal(int, int)
    def __init__(self, csv_file, parent=None, button_size=12):
        super().__init__(parent)
        self.button_size = button_size
        self.alphabet = "ARNDCQEGHILKMFPSTWYV-"

        self._alphabet = list(self.alphabet)
        self.matrix, self.min_value, self.max_value = self.load_matrix_from_csv(csv_file)

        self.sequence=''
        self.pos_i = 0
        self.pos_j = 0
        


    def load_matrix_from_csv(self, csv_file):
        import numpy as np
        from absl import logging
        try:
            import pandas as pd  # Import pandas here
            df = pd.read_csv(csv_file, index_col=0)
            
            # Remove rows and columns not in the alphabet
            df = df.loc[df.index.isin(self._alphabet), df.columns.isin(self._alphabet)]
            
            # Convert the DataFrame to a 2D list
            matrix = df.values.tolist()
            
            return matrix, -np.max((np.abs(df.values.min()), df.values.max())), np.max((np.abs(df.values.min()), df.values.max()))
        except Exception as e:
            logging.error(f"Error loading CSV file: {str(e)}")
            return [], 0, 1  # Default to 0-1 range if there's an error

    def map_value_to_color(self, value):
        import matplotlib.pyplot as plt
        # Map a value to a color using the 'bwr' colormap with reversed colors
        normalized_value = 1 - (value - self.min_value) / (self.max_value - self.min_value)
        colormap = plt.get_cmap('bwr')
        rgba_color = colormap(normalized_value)
        color = QtGui.QColor.fromRgbF(rgba_color[0], rgba_color[1], rgba_color[2], rgba_color[3])
        return color

    def init_ui(self):
        from absl import logging
        layout = QtWidgets.QGridLayout()
        font = QtGui.QFont()
        font.setPointSize(self.button_size) 
        font.setBold(True)


        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)

        #logging.debug(f"Sequence: {self.sequence}")
        logging.debug(f"WT pair: {self.sequence[self.pos_i]}{self.pos_i+1}_{self.sequence[self.pos_j]}{self.pos_j+1}")

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
                is_wt_pair=(row_name==self.sequence[self.pos_i] and self._alphabet[col]==self.sequence[self.pos_j])

                button = QtWidgets.QPushButton("&WT" if is_wt_pair else None)
                
                button.setSizePolicy(size_policy)
                button.setStyleSheet(f"background-color: {color.name()};{'color: black;' if is_wt_pair else ''}")
                button.clicked.connect(lambda checked, r=row, c=col: self.report_axises(r, c))
                layout.addWidget(button, row, col + 1)  # +1 to account for row labels

        # Add a row of column labels as labels after buttons
        for col, col_name in enumerate(self._alphabet):
            label = QtWidgets.QLabel(col_name)
            
            label.setFont(font)
            label.setFixedSize(self.button_size, self.button_size)  # Set fixed size for column labels
            
            
            layout.addWidget(label, len(self._alphabet), col + 1, QtCore.Qt.AlignTop)

        self.setLayout(layout)



    def report_axises(self, row, col):
        from absl import logging
        logging.debug(f"Button at ({row}, {col}) clicked.")
        self.report_axes_signal.emit(row, col)


def get_color(cmap, data, min_value, max_value):
    import matplotlib
    if min_value == max_value:
        return [0.5,0.5,0.5]
    _cmap=matplotlib.colormaps[cmap]
    num_color = _cmap.N
    scaled_value = (data - min_value) / (max_value - min_value)
    color = _cmap(int(num_color * scaled_value))[:3]
    return color

def rescale_number(number, min_value, max_value):
    # Ensure that min_value and max_value are valid.
    if min_value >= max_value:
        raise ValueError("min_value must be less than max_value")
    
    # Calculate the rescaled value.
    rescaled_value = (number - min_value) / (max_value - min_value)
    
    # Ensure the result is within the [0, 1] range.
    return max(0, min(1, rescaled_value))