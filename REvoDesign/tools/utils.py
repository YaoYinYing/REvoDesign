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


def is_polymer_protein(sele=''):
    if not sele:
        return None

    # return a bool of protein that contain at least 10 residues
    return (
        len(
            set(
                [
                    at.resi
                    for at in cmd.get_model(
                        f'({sele}) and polymer.protein'
                    ).atom
                ]
            )
        )
        > 10
    )


def find_small_molecules_in_protein(sele):
    if not sele:
        return
    # return a list of small molecules
    return [''] + list(
        set(
            [
                at.resn
                for at in cmd.get_model(
                    f'( {sele} ) and (not polymer.protein)'
                ).atom
            ]
        )
    )


def find_design_molecules():
    objects = [
        object
        for object in cmd.get_names(
            'public_nongroup_objects', enabled_only=1, selection='all'
        )
        if is_polymer_protein(object)
    ]
    return objects


def find_all_protein_chain_ids_in_protein(sele):
    if not sele:
        return
    # return a list of chain IDs that assigned to a protein molecule
    return [
        chain_id
        for chain_id in cmd.get_chains(sele)
        if is_polymer_protein(f'( {sele} and c. {chain_id} )')
    ]


def is_distal_residue_pair(
    molecule,
    chain_id,
    resi_1,
    resi_2,
    minimal_distance=20,
    use_sidechain_angle=False,
):
    """
    Check if a pair of amino acid residues are distal based on certain conditions.

    Parameters:
    - molecule (str): The name of the molecule.
    - chain_id (str): The chain identifier.
    - resi_1 (int): The residue number of the first amino acid.
    - resi_2 (int): The residue number of the second amino acid.
    - minimal_distance (float, optional): The minimum distance threshold for residues to be considered distal. Default is 20.
    - use_sidechain_angle (bool, optional): Whether to consider the orientation of side chains. Default is False.

    Returns:
    - distal (bool): True if the residues are distal, False otherwise.
    """

    # Step 1: Get the sequence of the molecule and chain
    sequence = get_molecule_sequence(molecule=molecule, chain_id=chain_id)

    # Convert residue numbers to integers
    resi_1 = int(resi_1)
    resi_2 = int(resi_2)

    # Retrieve one-letter amino acid codes for the two residues
    resn_1 = sequence[resi_1 - 1]
    resn_2 = sequence[resi_2 - 1]

    # Construct strings representing CA atoms of the two residues
    Ca_atom_1 = f'{molecule} and c. {chain_id} and i. {resi_1} and n. CA'
    Ca_atom_2 = f'{molecule} and c. {chain_id} and i. {resi_2} and n. CA'

    # Calculate the distance between the CA atoms
    Ca_distance = cmd.get_distance(atom1=Ca_atom_1, atom2=Ca_atom_2)

    # Check if either of the residues is glycine or not using sidechain angle
    if any([resn == 'G' for resn in [resn_1, resn_2]]) or (
        not use_sidechain_angle
    ):
        return Ca_distance > minimal_distance
    else:
        import numpy as np

        # Construct strings representing sidechain atoms of the two residues
        SC_atoms_1 = f'{molecule} and c. {chain_id} and i. {resi_1} and sidechain and not hydrogen'
        SC_atoms_2 = f'{molecule} and c. {chain_id} and i. {resi_2} and sidechain and not hydrogen'

        # Get coordinates of CA and Sidechain  atoms
        Ca_atom_1_coord = np.array(cmd.get_coords(Ca_atom_1)[0])
        Ca_atom_2_coord = np.array(cmd.get_coords(Ca_atom_2)[0])
        SC_COM_1 = np.array(cmd.centerofmass(SC_atoms_1))
        SC_COM_2 = np.array(cmd.centerofmass(SC_atoms_2))

        # Calculate the orientation of the side chains
        sidechain_orient = np.dot(
            SC_COM_1 - Ca_atom_1_coord, SC_COM_2 - Ca_atom_2_coord
        )
        sidechain_com_dist = abs(np.linalg.norm(SC_COM_1 - SC_COM_2))

        # Check if the side chains are oriented in opposite directions
        if sidechain_orient < 0:
            logging.warning(
                f'Sidechains of {resi_1}{resn_1} and {resi_2}{resn_2} are oriented in opposite directions. Considered as a distal pair.'
            )

            if sidechain_com_dist >= Ca_distance:
                # /-------------\
                # *---Ca   Ca---*
                return True
            else:
                #       /--\
                # Ca---*    *---Ca
                return sidechain_com_dist > minimal_distance
        else:
            logging.warning(
                f'Sidechains of {resi_1}{resn_1} and {resi_2}{resn_2} are oriented in same directions.'
            )
            # Ca---*
            #        \
            #         \
            #          \
            #      Ca---*
            # Check if sidechain distance is greater than the minimal distance
            return sidechain_com_dist > minimal_distance


def num_processors():
    return sorted([x for x in range(1, os.cpu_count() + 1)], reverse=True)


def fetch_exclusion_expressions():
    return [""] + [sel for sel in refresh_all_selections()]


def refresh_all_selections():
    selections = [
        sel
        for sel in cmd.get_names(type='selections')
        if sel != 'sele' and (not sel.startswith('_align'))
    ]

    for sel in selections:
        _resi = sorted(list(set([at.resi for at in cmd.get_model(sel).atom])))
        logging.info(f'{sel}: i. {shorter_range([int(x) for x in _resi])}')
    return selections


def is_a_REvoDesign_session():
    return bool(cmd.get_names(type='public_group_objects'))

def make_temperal_input_pdb(molecule,format='pdb',wd=os.getcwd()):
    os.makedirs(wd, exist_ok=True)

    input_file = os.path.join(wd, f'{molecule}.{format}')
    cmd.save(input_file, f'{molecule}', -1)
    cmd.reinitialize()
    cmd.load(input_file)
    logging.warning(
        'To avoid error, a temperal session is created based on your molecule selection: \n'
        f'{molecule} --> {input_file}'
    )
    return input_file


def determine_system():
    import platform

    os_info = platform.uname()
    os_name = os_info.system

    if os_name == 'Darwin':
        is_arm_macos = "ARM64" in os_info.version
        is_recognized_as_x86 = os_info.machine == 'x86_64'

        logging.warning(f'Does it ARMed? {is_arm_macos}')
        logging.warning(f'Does it Rosetta-ed? {is_recognized_as_x86}')

        if is_arm_macos and is_recognized_as_x86:
            logging.warning(
                'Oops! You are in Rosetta-translated PyMOL bundle from official channel. '
                'This might limit the performance of joblib, causing MutantVisualizer slower.'
            )
            os_name += '_Rosetta'
    return os_name, os_info


OS_TYPE, OS_INFO = determine_system()

PYMOL_VERSION = cmd.get_version()[0]


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


def run_command(excutable='python', command_list=[]):
    import sys
    import subprocess
    from absl import logging

    if excutable == 'python':
        python_exe = os.path.realpath(sys.executable)
        command_list = [python_exe] + command_list

    while '' in command_list:
        command_list.remove('')

    if not command_list:
        return

    logging.debug(command_list)

    result = subprocess.run(
        command_list,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

    return result


# A universal and versatile function for value setting. ;-)
def set_widget_value(widget, value):
    type_widget = type(widget)
    type_value = type(value)

    # preprocess values according to types
    if type_value == type(lambda: None):  # Check if value is a function
        value = value()  # If it's a function, call it to get the value
        type_value = type(value)

    #
    if type_value == range or type_value == type(
        (x for x in range(0, 1))
    ):  # Check if value is a range or generator
        value = [
            x for x in value
        ]  # If it's a range or generator, expand it as a list
        type_value = type(value)

    if type_widget == QtWidgets.QComboBox:
        if type_value != list and type_value != tuple:
            widget.setCurrentText(str(value))
        elif type_value == list or type_value == tuple:
            widget.clear()
            widget.addItems(map(str, value))
        else:
            logging.warning(
                f'FIX ME: Value {value} ({type_value}) is not currently supported on widget {widget} ({type_widget})'
            )
        return

    elif type_widget == QtWidgets.QLineEdit:
        widget.setText(str(value))
        return

    elif type_widget == QtWidgets.QProgressBar:
        if type_value == list or type_value == tuple:
            widget.setRange(int(value[0]), int(value[1]))
        elif type_value == int:
            widget.setValue(int(value))
        else:
            logging.warning(
                f'FIX ME: Value {value} ({type_value}) is not currently supported on widget {widget} ({type_widget})'
            )
        return

    elif type_widget == QtWidgets.QLCDNumber:
        widget.display(str(value))
        return

    elif type_widget == QtWidgets.QCheckBox:
        widget.setChecked(bool(value))
        return

    elif type_widget == QtWidgets.QStackedWidget:
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
            logging.warning(
                f'FIX ME: Value {value} ({type_value}) is not currently supported on widget {widget} ({type_widget})'
            )
        return

    elif type_widget == QtWidgets.QGridLayout:
        if type_value == str and os.path.exists(value):
            # Clear the existing widgets from gridLayout_interact_pairs
            for i in reversed(range(widget.count())):
                widget = widget.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()
            image_widget = ImageWidget(value)
            widget.addWidget(image_widget)
        else:
            logging.warning(
                f'FIX ME: Value {value} ({type_value}) is not currently supported on widget {widget} ({type_widget})'
            )
        return

    else:
        logging.warning(
            f'FIX ME: Widget {widget} is not currently supported. '
        )
        return


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


def does_dirname_exist(fp):
    return os.path.exists(os.path.dirname(fp))


def check_file_exists(fp):
    return os.path.exists(fp)


def get_molecule_sequence(molecule, chain_id):
    from Bio.Data import IUPACData

    protein_letters_3to1_upper = {
        key.upper(): val.upper()
        for key, val in IUPACData.protein_letters_3to1.items()
    }
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
    if re.match(r'[\d+\w]+_[-\d\.e]+', mutant_string):
        matched_mutant_id = re.match(
            r'[\w\d\-]+_(\-?\d+\.?\d*e?\-?\d*)$', mutant_string
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


def shorter_range(input_list):
    """
    Shorten a list of integers by representing consecutive ranges with hyphens,
    and non-consecutive integers with plus signs.

    Parameters:
    input_list (list): A list of integers to be shortened.

    Returns:
    str: A string expression representing the shortened integer list.

    Example:
    >>> input_list = [395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409]
    >>> result = shorter_range(input_list)
    >>> print(result)
    "395-409"

    >>> input_list = [395, 396, 397, 398, 399, 400, 401, 403, 404, 405, 406, 407, 408, 409]
    >>> result = shorter_range(input_list)
    >>> print(result)
    "395-401+403-409"
    """

    # Filter out non-integer items and sort the list
    input_list = sorted([item for item in input_list if isinstance(item, int)])

    if not input_list:
        return

    range_pairs = []
    start, end = input_list[0], input_list[0]

    for item in input_list[1:]:
        if item == end + 1:
            end = item
        else:
            if start == end:
                range_pairs.append(str(start))
            else:
                range_pairs.append(f"{start}-{end}")
            start, end = item, item

    # Handle the last range or single number
    if start == end:
        range_pairs.append(str(start))
    else:
        range_pairs.append(f"{start}-{end}")

    return '+'.join(range_pairs)


def expand_range(shortened_str):
    """
    Expand a shortened string expression representing a list of integers to the original list.

    Parameters:
    shortened_str (str): A shortened string expression representing a list of integers.

    Returns:
    list: A list of integers corresponding to the original input.

    Example:
    >>> shortened_str = "395-401+403-409"
    >>> result = expand_range(shortened_str)
    >>> print(result)
    [395, 396, 397, 398, 399, 400, 401, 403, 404, 405, 406, 407, 408, 409]
    """
    expanded_list = []
    ranges = shortened_str.split('+')

    for rng in ranges:
        if '-' in rng:
            start, end = map(int, rng.split('-'))
            expanded_list.extend(range(start, end + 1))
        else:
            expanded_list.append(int(rng))

    return expanded_list


def proceed_with_comfirm_msg_box(title='', description='' ):
    # A confirmation message.
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(
        description )
    msg.setStandardButtons(
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
    )
    result = msg.exec_()

    return result == QtWidgets.QMessageBox.Yes