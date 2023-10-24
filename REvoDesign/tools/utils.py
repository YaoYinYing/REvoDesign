import contextlib
import re

from pymol import cmd
import os
from pymol.Qt import *
from pymol.Qt import QtWidgets, QtGui, QtCore
from absl import logging

import time

def is_empty_session():
    return len(cmd.get_names(type='objects', enabled_only=0)) == 0


def determine_polymer_protein(sele='(all)'):
    # return a list of protein that contain at least 10 residues
    return (
        len(
            list(
                set(
                    [
                        atom.resi
                        for atom in cmd.get_model(
                            f'( {sele}) and polymer.protein'
                        ).atom
                    ]
                )
            )
        )
        > 10
    )


def determine_small_molecule(sele='(all)'):
    # return a list of small molecules
    return [''] + list(
        set(
            [
                atom.resn
                for atom in cmd.get_model(
                    f'( {sele} ) and (not polymer.protein)'
                ).atom
            ]
        )
    )


def determine_molecule_objects():
    objects = [
        object
        for object in cmd.get_names(
            'public_nongroup_objects', enabled_only=1, selection='all'
        )
        if determine_polymer_protein(object)
    ]
    return objects


def determine_chain_id(sele='(all)'):
    # return a list of chain IDs that assigned to a protein molecule
    return [
        chain_id
        for chain_id in cmd.get_chains(sele)
        if determine_polymer_protein(f'( {sele} and c. {chain_id} )')
    ]


def determine_nproc():
    return [x for x in range(1, os.cpu_count() + 1)]


def determine_exclusion():
    return [""] + [
        sel
        for sel in cmd.get_names(
            type='selections', enabled_only=0, selection='(all)'
        )
    ]


def determine_system():
    import platform

    return platform.system()


def renumber_chain_ids(target_protein):
    chain_ids = cmd.get_chains(target_protein)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for chain_id, _alphabet in zip(chain_ids, alphabet):
        logging.info(f'rechain: {chain_id} - {_alphabet}')
        cmd.alter(
            f'{target_protein} and c. {chain_id}', f'chain=\'{_alphabet}\''
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


def getExistingDirectory():
    return QtWidgets.QFileDialog.getExistingDirectory(
        None,
        "Open Directory",
        os.path.expanduser('~'),
        QtWidgets.QFileDialog.ShowDirsOnly
        | QtWidgets.QFileDialog.DontResolveSymlinks,
    )


def check_dirname_exists(fp):
    return os.path.exists(os.path.dirname(fp))


def check_file_exists(fp):
    return os.path.exists(fp)


def get_molecule_sequence(molecule, chain_id):
    from Bio.Data import IUPACData

    protein_letters_3to1_upper = {
        key.upper(): val.upper()
        for key, val in IUPACData.protein_letters_3to1.items()
    }
    logging.debug(f'( {molecule} and c. {chain_id} and n. CA )')
    return ''.join(
        [
            protein_letters_3to1_upper[atom.resn]
            for atom in cmd.get_model(
                f'( {molecule} and c. {chain_id} and n. CA )'
            ).atom
        ]
    )


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
            print(
                "Send final data in length: %s" % len(inputs_data[start_idx:])
            )
            yield inputs_data[start_idx:]


def minibatches_generator(inputs_data_generator, batch_size):
    current_batch = []
    for data_point in inputs_data_generator:
        # print(f"Send data {data_point}")
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


def run_worker_thread_with_progress(
    worker_function, progress_bar=None, *args, **kwargs
):
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
        # guessing backend according to OS
        if not backend == 'auto':
            self.backend = backend
        else:
            if determine_system() == 'Windows':
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


def extract_archive(archive_file, extract_to):
    """
    Extracts the contents of an archive file (zip, tar.gz, tar.bz2, tar.xz, or rar) to a specified directory.

    Args:
        archive_file (str): Path to the archive file.
        extract_to (str): Directory where the contents will be extracted.
    """

    try:
        import tarfile
        if archive_file.endswith(".zip"):
            import zipfile
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
        else:
            logging.warning(f"Unsupported archive format: {archive_file}")
    except Exception as e:
        logging.error(f"Error extracting {archive_file}: {str(e)}")


class QbuttonMatrix(QtWidgets.QWidget):
    # Define a custom signal for reporting axes
    report_axes_signal = QtCore.pyqtSignal(int, int)

    def __init__(self, csv_file, parent=None, button_size=12):
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
        logging.debug(f"Button at ({row}, {col}) clicked.")
        self.report_axes_signal.emit(row, col)


def get_color(cmap, data, min_value, max_value):
    import matplotlib

    if min_value == max_value:
        return [0.5, 0.5, 0.5]
    _cmap = matplotlib.colormaps[cmap]
    num_color = _cmap.N
    scaled_value = (data - min_value) / (max_value - min_value)
    color = _cmap(int(num_color * scaled_value))[:3]
    return color


def cmap_reverser(cmap, reverse=False):
    if reverse:
        if cmap.endswith('_r'):
            cmap = cmap.replace('_r', '')
        else:
            cmap += '_r'

    return cmap


def rescale_number(number, min_value, max_value):
    # Ensure that min_value and max_value are valid.
    if min_value >= max_value:
        raise ValueError("min_value must be less than max_value")

    # Calculate the rescaled value.
    rescaled_value = (number - min_value) / (max_value - min_value)

    # Ensure the result is within the [0, 1] range.
    return max(0, min(1, rescaled_value))


def extract_mutants(mutant_string, chain_id=None, sequence=None):
    logging.debug(f'Parsing {mutant_string}')

    from common.Mutant import Mutant

    # Use regular expression to find all mutants in the string
    mutants = re.findall(r'([A-Z]{0,2}\d+[A-Z]{1})', mutant_string)

    mutant_info = []
    for mut in mutants:
        # full description of mutation, <chain_id><wt_res><pos><mut>
        if re.match(r'[A-Z]{2}\d+[A-Z]{1}', mut):
            logging.debug(f'full description: {mut}')
            _mut = re.match(r'([A-Z]{1})([A-Z]{1})(\d+)([A-Z]{1})', mut)
            _chain_id = (
                _mut.group(1)
                if chain_id is None or chain_id == ''
                else chain_id
            )
            _position = _mut.group(3)
            _wt_res = _mut.group(2)
            _mut_res = _mut.group(4)

        # reduced description of mutation, <wt_res><pos><mut>, missing <chain_id>
        elif re.match(r'[A-Z]{1}\d+[A-Z]{1}', mut):
            logging.debug(f'reduced description: {mut}')
            if not (mutant_info or chain_id):
                logging.error(
                    f'Error while processing mutant id {mut}: Invalid chain id: {chain_id}'
                )
                continue
            _mut = re.match(r'([A-Z]{1})(\d+)([A-Z]{1})', mut)

            _chain_id = chain_id
            _position = int(_mut.group(2))
            _wt_res = _mut.group(1)
            _mut_res = _mut.group(3)

        # fuzzy description of mutation, <pos><mut>, missing <chain_id> and <wt_res>
        elif re.match(r'\d+[A-Z]{1}', mut):
            logging.debug(f'fuzzy description: {mut}')
            # silent error report while mismatching the score term
            if not (mutant_info or chain_id):
                logging.error(
                    f'Error while processing mutant id {mut}: Invalid chain id: {chain_id}'
                )
                continue
            if not (sequence or mutant_info):
                logging.error(
                    f'Error while processing mutant id {mut}: Invalid sequence: {sequence}'
                )
                continue

            _mut = re.match(r'(\d+)([A-Z]{1})', mut)

            _chain_id = chain_id
            _position = int(_mut.group(1))
            _wt_res = sequence[_position - 1]
            _mut_res = _mut.group(2)

        else:
            logging.error(f'Error while processing mutant id {mut}. ')
            continue

        mutant_info.append(
            {
                'chain_id': _chain_id,
                'position': _position,
                'wt_res': _wt_res,
                'mut_res': _mut_res,
            }
        )

    if not mutant_info:
        # early return if the input string failes to be parsed
        return None, None

    # if the mutation has a position of score, we need to extract it.
    if re.match(r'[\d+\w]+_[-\d\.]+', mutant_string):
        matched_mutant_id = re.match(
            r'[\w\d\-]+_(\-?\d+\.?\d*)$', mutant_string
        )
        mutant_score = matched_mutant_id.group(1)
        mutant_score = float(mutant_score)
    else:
        # set mutant_score to None if not found.
        mutant_score = None

    # Instantializing a Mutant obj
    mutant_obj = Mutant(mutant_info, mutant_score)

    logging.debug(mutant_obj)

    # Join the mutants into a single string separated by underscores and instantialized Mutant obj
    return '_'.join(mutants), mutant_obj


def extract_mutant_info(mutant_sequence, wt_sequence, chain_id='A'):
    if len(mutant_sequence) != len(wt_sequence):
        logging.error(
            f'Lengths of WT and mutant are not equal to each other: {len(wt_sequence)}: {len(mutant_sequence)}'
        )
        return None

    if mutant_sequence == wt_sequence:
        logging.warning(f'WT and mutant sequences are identical.')
        return None

    mut_info = [
        f'{chain_id}{res}{i+1}{mutant_sequence[i]}'
        for i, res in enumerate(wt_sequence)
        if res != mutant_sequence[i]
    ]
    return '_'.join(mut_info)


def get_atom_pair_cst(selection='sele'):
    _sele = cmd.get_model(selection=selection).atom
    if len(_sele) != 2:
        logging.error(
            f'Atom pair selection {selection} must contain exactly 2 atoms!'
        )
        return
    else:
        cst = f'AtomPair {_sele[0].name} {_sele[0].resi}{_sele[0].chain} {_sele[1].name} {_sele[1].resi}{_sele[1].chain} HARMONIC 3 0.5'
        return cst
