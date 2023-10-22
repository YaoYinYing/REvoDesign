import sys, os
import time
import re
from pymol import cmd
from pymol.Qt import QtWidgets

# using partial module to reduce duplicate code.
from functools import partial
import absl.logging as logging

logging.set_verbosity(logging.DEBUG)
logging.info(f'REvoDesign Core is installed in {os.path.dirname(__file__)}')

sys.path.append(os.path.dirname(__file__))

from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.common.file_extensions import (
    SessionFileExt,
    PDB_FileExt,
    PSSM_FileExt,
    MutableFileExt,
    TXT_FileExt,
    AnyFileExt,
    CompressedFileExt,
    PickleObjectFileExt,
)

from REvoDesign.tools.utils import (
    is_empty_session,
    determine_chain_id,
    determine_exclusion,
    determine_molecule_objects,
    determine_nproc,
    determine_small_molecule,
    getOpenFileNameWithExt,
    check_dirname_exists,
    check_file_exists,
    get_molecule_sequence,
    getExistingDirectory,
    extract_archive,
    determine_system,
    ImageWidget,
    QbuttonMatrix,
    run_worker_thread_with_progress,
    get_color,
    cmap_reverser,
    rescale_number,
    extract_mutants,
)


class REvoDesignPlugin:
    def __init__(
        self,
    ):
        # global reference to avoid garbage collection of our dialog
        self.window = None

        self.RUN_DIR = os.path.abspath(os.path.dirname(__file__))
        self.PWD = os.getcwd()

        self.ui_file = os.path.join(self.RUN_DIR, 'UI', 'REvoDesign-PyMOL.ui')

        self.total_mutant_in_this_session = 0
        self.mutant_tree_pssm = None
        self.mutant_tree_pssm_selected = None
        self.mutant_tree_coevolved = None
        self.gremlin_tool = None

        from REvoDesign.phylogenetics.PSSM_GREMLIN_client import (
            PSSMGremlinCalculator,
        )

        self.pssm_gremlin_calculator = PSSMGremlinCalculator()

    def set_working_directory(self):
        self.PWD = getExistingDirectory()
        os.chdir(self.PWD)

    def load_test_data(self):
        # menu actions
        if determine_system() == 'Darwin':
            self.PWD = '/Users/yyy/Documents/RosettaWorkshop/2._Working/0._IntergatedProtocol/REvoDesign/tests/test_results'
        else:
            self.PWD = 'D:\repo\RosettaWorkshop/2._Working/0._IntergatedProtocol/REvoDesign\REvoDesign\tests/test_results'

    def run_plugin_gui(self):
        if self.window is None:
            self.window = self.make_window()
        self.window.show()

    # main function that makes the plugin window
    def make_window(self):
        main_window = QtWidgets.QMainWindow()

        from pymol.Qt.utils import loadUi

        self.ui = loadUi(
            self.ui_file, main_window
        )  # Store the UI form for later access

        from REvoDesign.common.magic_numbers import (
            DEFAULT_INTERCHAIN_RADIUS,
            DEFAULT_CLUSTER_NUM,
            DEFAULT_CLUSTER_RANGE,
            DEFAULT_CLUSTER_MIN_MUT,
            DEFAULT_CLUSTER_MAX_MUT,
            DEFAULT_CLUSTER_BATCH_SIZE,
            DEFAULT_CLUSTER_SCORE_MTX,
            DEFAULT_GREMLIN_TOPN_NUM,
            DEFAULT_GREMLIN_SPATIAL_MAX_DIST,
            DEFAULT_PROFILE_TYPE,
            DEFAULT_PROFILE_TYPE_GROUP,
        )

        # self.setup_nproc(self.ui.comboBox_nproc)

        self.setup_nproc(self.ui.comboBox_nproc_2)
        self.setup_nproc(self.ui.comboBox_nproc_3)
        self.setup_nproc(self.ui.comboBox_nproc_4)

        # Set up Menu
        self.ui.actionLoad_Tests.triggered.connect(self.load_test_data)
        self.ui.actionSet_Working_Directory.triggered.connect(
            self.set_working_directory
        )

        # Set up general arguments
        # Tab `Determine`

        self.ui.checkBox_use_this_session_2.stateChanged.connect(
            partial(
                self.reload_molecule_info,
                self.ui.checkBox_use_this_session_2,
                self.ui.lineEdit_input_pse,
                self.ui.comboBox_design_molecule,
            )
        )

        self.ui.lineEdit_input_pse.textChanged.connect(
            partial(
                self.reload_molecule_info,
                self.ui.checkBox_use_this_session_2,
                self.ui.lineEdit_input_pse,
                self.ui.comboBox_design_molecule,
            )
        )

        self.ui.pushButton_open_input_pse.clicked.connect(
            partial(
                self.open_structure_or_session, self.ui.lineEdit_input_pse, 'r'
            )
        )
        self.ui.pushButton_open_output_pse.clicked.connect(
            partial(
                self.open_structure_or_session,
                self.ui.lineEdit_output_pse_4,
                'w',
            )
        )
        self.ui.comboBox_design_molecule.currentIndexChanged.connect(
            partial(
                self.update_chain_id,
                self.ui.comboBox_design_molecule,
                self.ui.comboBox_chainid,
            )
        )

        self.ui.comboBox_design_molecule.currentIndexChanged.connect(
            partial(
                self.setup_pssm_gremlin_calculator,
                self.ui.comboBox_design_molecule,
                self.ui.comboBox_chainid,
            )
        )

        self.ui.comboBox_chainid.currentIndexChanged.connect(
            partial(
                self.setup_pssm_gremlin_calculator,
                self.ui.comboBox_design_molecule,
                self.ui.comboBox_chainid,
            )
        )

        self.pssm_gremlin_calculator.setup_url(
            self.ui.lineEdit_pssm_gremlin_url
        )

        self.ui.lineEdit_pssm_gremlin_url.textChanged.connect(
            partial(
                self.pssm_gremlin_calculator.setup_url,
                self.ui.lineEdit_pssm_gremlin_url,
            )
        )

        self.ui.pushButton_submit_pssm_gremlin_job.clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='submit',
                progress_bar=self.ui.progressBar_download,
            )
        )

        self.ui.pushButton_cancel_pssm_gremlin_job.clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='cancel',
                progress_bar=self.ui.progressBar_download,
            )
        )

        self.ui.pushButton_download_pssm_gremlin_job.clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='download',
                progress_bar=self.ui.progressBar_download,
            )
        )

        self.ui.pushButton_run_surface_refresh.clicked.connect(
            self.update_surface_exclusion
        )

        self.ui.lineEdit_output_pse_4.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [self.ui.lineEdit_output_pse_4],
                [
                    self.ui.pushButton_run_surface_detection,
                    self.ui.pushButton_run_pocket_detection,
                ],
            )
        )
        self.ui.comboBox_design_molecule.currentIndexChanged.connect(
            partial(
                self.update_chain_id,
                self.ui.comboBox_design_molecule,
                self.ui.comboBox_chainid,
            )
        )

        self.ui.comboBox_design_molecule.currentIndexChanged.connect(
            partial(
                self.reload_determine_tab_setup,
                self.ui.comboBox_design_molecule,
                self.ui.comboBox_ligand_sel,
                self.ui.comboBox_cofactor_sel,
            )
        )

        self.set_widget_value(
            self.ui.comboBox_interface_cutoff, DEFAULT_INTERCHAIN_RADIUS
        )

        # Connect run buttons
        self.ui.pushButton_dump_interfaces.clicked.connect(
            self.run_chain_interface_detection
        )
        self.ui.pushButton_run_surface_detection.clicked.connect(
            self.run_surface_detection
        )
        self.ui.pushButton_run_pocket_detection.clicked.connect(
            self.run_pocket_detection
        )

        # Tab `Load Mutants`
        import matplotlib

        self.set_widget_value(self.ui.comboBox_cmap_2, matplotlib.colormaps())
        self.set_widget_value(self.ui.comboBox_cmap_2, 'bwr_r')

        self.ui.lineEdit_input_pse_2.textChanged.connect(
            partial(
                self.reload_molecule_info,
                self.ui.checkBox_use_this_session,
                self.ui.lineEdit_input_pse_2,
                self.ui.comboBox_molecule,
            )
        )

        self.ui.checkBox_use_this_session.stateChanged.connect(
            partial(
                self.reload_molecule_info,
                self.ui.checkBox_use_this_session,
                self.ui.lineEdit_input_pse_2,
                self.ui.comboBox_molecule,
            )
        )

        self.ui.pushButton_open_input_pse_2.clicked.connect(
            partial(
                self.open_structure_or_session,
                self.ui.lineEdit_input_pse_2,
                'r',
            )
        )

        self.ui.pushButton_open_output_pse_2.clicked.connect(
            partial(
                self.open_structure_or_session,
                self.ui.lineEdit_output_pse,
                'w',
            )
        )
        self.ui.pushButton_open_customized_indices.clicked.connect(
            partial(
                self.open_input_filepath,
                self.ui.lineEdit_input_customized_indices,
                [TXT_FileExt, AnyFileExt],
            )
        )
        self.ui.comboBox_molecule.currentIndexChanged.connect(
            partial(
                self.update_chain_id,
                self.ui.comboBox_molecule,
                self.ui.comboBox_chainid_2,
            )
        )
        self.ui.pushButton_open_input_csv.clicked.connect(
            partial(
                self.open_input_filepath,
                self.ui.lineEdit_input_csv,
                [PSSM_FileExt, AnyFileExt, CompressedFileExt],
            )
        )

        self.set_widget_value(
            self.ui.comboBox_profile_type, DEFAULT_PROFILE_TYPE_GROUP
        )
        self.set_widget_value(
            self.ui.comboBox_profile_type, DEFAULT_PROFILE_TYPE
        )

        self.ui.lineEdit_input_csv.textChanged.connect(
            partial(
                self.determine_profile_format,
                self.ui.lineEdit_input_csv,
                self.ui.comboBox_profile_type,
            )
        )

        self.ui.lineEdit_output_pse.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_output_pse,
                    self.ui.lineEdit_input_csv,
                    self.ui.lineEdit_input_customized_indices,
                ],
                [
                    self.ui.pushButton_run_PSSM_to_pse,
                ],
            )
        )

        self.ui.lineEdit_input_csv.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_output_pse,
                    self.ui.lineEdit_input_csv,
                    self.ui.lineEdit_input_customized_indices,
                ],
                [
                    self.ui.pushButton_run_PSSM_to_pse,
                ],
            )
        )

        self.ui.lineEdit_input_customized_indices.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_output_pse,
                    self.ui.lineEdit_input_csv,
                    self.ui.lineEdit_input_customized_indices,
                ],
                [
                    self.ui.pushButton_run_PSSM_to_pse,
                ],
            )
        )

        self.ui.pushButton_run_PSSM_to_pse.clicked.connect(
            self.run_mutant_loading_from_profile
        )

        # Tab `Choose Mutants`
        self.ui.pushButton_open_mut_table.clicked.connect(
            partial(
                self.open_mutant_table, self.ui.lineEdit_output_mut_table, 'w'
            )
        )

        self.ui.lineEdit_output_mut_table.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_output_mut_table,
                ],
                [
                    self.ui.pushButton_previous_mutant,
                    self.ui.pushButton_reject_this_mutant,
                    self.ui.pushButton_next_mutant,
                    self.ui.pushButton_accept_this_mutant,
                ],
            )
        )

        self.ui.checkBox_rock_pymol.stateChanged.connect(
            partial(self.set_pymol_session_rock, self.ui.checkBox_rock_pymol)
        )

        self.ui.pushButton_reinitialize_mutant_choosing.clicked.connect(
            partial(
                self.initialize_design_candidates,
                self.ui.comboBox_molecule_7,
                self.ui.comboBox_chainid_7,
                self.ui.pushButton_previous_mutant,
                self.ui.pushButton_next_mutant,
                self.ui.pushButton_reject_this_mutant,
                self.ui.pushButton_accept_this_mutant,
                self.ui.lcdNumber_total_mutant,
                self.ui.lcdNumber_selected_mutant,
                self.ui.lineEdit_output_mut_table,
                self.ui.progressBar_mutant_choosing,
                self.ui.comboBox_group_ids,
                self.ui.checkBox_show_wt,
            )
        )

        self.ui.pushButton_goto_best_hit_in_group.clicked.connect(
            partial(
                self.jump_to_the_best_mutant,
                self.ui.checkBox_show_wt,
                self.ui.comboBox_molecule_7,
                self.ui.comboBox_chainid_7,
                self.ui.progressBar_mutant_choosing,
                self.ui.checkBox_reverse_mutant_effect_2,
            )
        )

        self.ui.pushButton_load_mutant_choice_checkpoint.clicked.connect(
            partial(
                self.recover_mutant_choices_from_checkpoint,
                self.ui.lcdNumber_selected_mutant,
            )
        )

        self.ui.pushButton_save_this_session.clicked.connect(
            self.save_sessionfile
        )

        self.ui.pushButton_goto_group.clicked.connect(
            partial(
                self.jump_to_branch,
                self.ui.comboBox_group_ids,
                self.ui.checkBox_show_wt,
                self.ui.comboBox_molecule_7,
                self.ui.comboBox_chainid_7,
                self.ui.progressBar_mutant_choosing,
            )
        )

        # Tab `Cluster`
        self.ui.pushButton_open_input_pse_3.clicked.connect(
            partial(
                self.open_structure_or_session,
                self.ui.lineEdit_input_pse_3,
                'r',
            )
        )

        self.ui.pushButton_open_mut_table_2.clicked.connect(
            partial(
                self.open_mutant_table, self.ui.lineEdit_input_mut_table, 'r'
            )
        )

        self.ui.checkBox_use_this_session_5.stateChanged.connect(
            partial(
                self.reload_molecule_info,
                self.ui.checkBox_use_this_session_5,
                self.ui.lineEdit_input_pse_3,
                self.ui.comboBox_molecule_4,
            )
        )

        self.ui.lineEdit_input_pse_3.textChanged.connect(
            partial(
                self.reload_molecule_info,
                self.ui.checkBox_use_this_session_5,
                self.ui.lineEdit_input_pse_3,
                self.ui.comboBox_molecule_4,
            )
        )

        self.ui.comboBox_molecule_4.currentIndexChanged.connect(
            partial(
                self.update_chain_id,
                self.ui.comboBox_molecule_4,
                self.ui.comboBox_chainid_3,
            )
        )

        self.set_widget_value(
            self.ui.comboBox_cluster_batchsize, DEFAULT_CLUSTER_BATCH_SIZE
        )
        self.set_widget_value(
            self.ui.comboBox_num_cluster, DEFAULT_CLUSTER_RANGE
        )
        self.set_widget_value(
            self.ui.comboBox_num_cluster, DEFAULT_CLUSTER_NUM
        )
        self.set_widget_value(
            self.ui.comboBox_num_mut_minimun, DEFAULT_CLUSTER_MIN_MUT
        )
        self.set_widget_value(
            self.ui.comboBox_num_mut_maximum, DEFAULT_CLUSTER_MAX_MUT
        )

        from Bio.Align import substitution_matrices

        self.set_widget_value(
            self.ui.comboBox_cluster_matrix,
            [
                mtx
                for mtx in os.listdir(
                    os.path.join(substitution_matrices.__path__[0], 'data')
                )
            ],
        )
        self.set_widget_value(
            self.ui.comboBox_cluster_matrix, DEFAULT_CLUSTER_SCORE_MTX
        )

        self.ui.lineEdit_input_mut_table.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_input_mut_table,
                ],
                [
                    self.ui.pushButton_run_cluster,
                ],
            )
        )

        self.ui.pushButton_run_cluster.clicked.connect(self.run_clustering)

        # Tab Visualize
        self.ui.checkBox_use_this_session_3.stateChanged.connect(
            partial(
                self.reload_molecule_info,
                self.ui.checkBox_use_this_session_3,
                self.ui.lineEdit_input_pse_4,
                self.ui.comboBox_molecule_2,
            )
        )

        self.ui.lineEdit_input_pse_4.textChanged.connect(
            partial(
                self.reload_molecule_info,
                self.ui.checkBox_use_this_session_3,
                self.ui.lineEdit_input_pse_4,
                self.ui.comboBox_molecule_2,
            )
        )

        self.ui.lineEdit_output_pse_2.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_output_pse_2,
                ],
                [
                    self.ui.pushButton_run_visualizing,
                ],
            )
        )

        self.ui.lineEdit_input_mut_table_csv.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_input_mut_table_csv,
                ],
                [
                    self.ui.pushButton_save_this_mutant_table,
                ],
            )
        )

        self.ui.pushButton_save_this_mutant_table.clicked.connect(
            partial(
                self.save_visualizing_mutant_tree,
                self.ui.lineEdit_input_mut_table_csv,
                self.ui.lineEdit_group_name,
            )
        )

        self.ui.comboBox_molecule_2.currentIndexChanged.connect(
            partial(
                self.update_chain_id,
                self.ui.comboBox_molecule_2,
                self.ui.comboBox_chainid_4,
            )
        )

        self.set_widget_value(
            self.ui.comboBox_profile_type_2, DEFAULT_PROFILE_TYPE_GROUP
        )
        self.set_widget_value(
            self.ui.comboBox_profile_type_2, DEFAULT_PROFILE_TYPE
        )

        self.ui.lineEdit_input_csv_2.textChanged.connect(
            partial(
                self.determine_profile_format,
                self.ui.lineEdit_input_csv_2,
                self.ui.comboBox_profile_type_2,
            )
        )

        self.ui.pushButton_open_input_csv_2.clicked.connect(
            partial(
                self.open_input_filepath,
                self.ui.lineEdit_input_csv_2,
                [PSSM_FileExt, AnyFileExt, CompressedFileExt],
            )
        )

        self.ui.pushButton_open_input_pse_4.clicked.connect(
            partial(
                self.open_structure_or_session,
                self.ui.lineEdit_input_pse_4,
                'r',
            )
        )

        self.ui.pushButton_open_mut_table_csv.clicked.connect(
            partial(
                self.open_mutant_table,
                self.ui.lineEdit_input_mut_table_csv,
                'r',
            )
        )

        self.ui.lineEdit_input_mut_table_csv.textChanged.connect(
            partial(
                self.update_mutant_table_columns,
                self.ui.lineEdit_input_mut_table_csv,
                self.ui.comboBox_best_leaf,
                self.ui.comboBox_totalscore,
            )
        )

        self.ui.pushButton_open_output_pse_3.clicked.connect(
            partial(
                self.open_structure_or_session,
                self.ui.lineEdit_output_pse_2,
                'w',
            )
        )

        self.set_widget_value(self.ui.comboBox_best_leaf, 'best_leaf')
        self.set_widget_value(self.ui.comboBox_totalscore, 'totalscore')

        self.set_widget_value(self.ui.comboBox_cmap, matplotlib.colormaps())
        self.set_widget_value(self.ui.comboBox_cmap, 'bwr_r')

        self.ui.pushButton_run_visualizing.clicked.connect(
            self.visualize_mutants
        )

        # Tab Interact
        self.ui.pushButton_open_gremlin_mtx.clicked.connect(
            partial(
                self.open_input_filepath,
                self.ui.lineEdit_input_gremlin_mtx,
                [PickleObjectFileExt, AnyFileExt],
            )
        )

        self.ui.checkBox_use_this_session_4.stateChanged.connect(
            partial(
                self.set_widget_value,
                self.ui.comboBox_molecule_3,
                determine_molecule_objects(),
            )
        )

        self.ui.comboBox_molecule_3.currentIndexChanged.connect(
            partial(
                self.update_chain_id,
                self.ui.comboBox_molecule_3,
                self.ui.comboBox_chainid_9,
            )
        )

        self.set_widget_value(
            self.ui.comboBox_gremlin_topN, DEFAULT_GREMLIN_TOPN_NUM
        )

        self.ui.pushButton_reinitialize_interact.clicked.connect(
            self.load_gremlin_mrf
        )
        self.ui.pushButton_run_interact_scan.clicked.connect(
            self.run_gremlin_tool
        )

        self.set_widget_value(
            self.ui.comboBox_max_interact_dist,
            DEFAULT_GREMLIN_SPATIAL_MAX_DIST,
        )

        self.ui.pushButton_open_save_mutant_table.clicked.connect(
            partial(
                self.open_mutant_table,
                self.ui.lineEdit_output_mutant_table,
                'w',
            )
        )

        self.ui.pushButton_interact_reject.clicked.connect(
            self.reject_coevoled_mutant
        )
        self.ui.pushButton_interact_accept.clicked.connect(
            self.accept_coevoled_mutant
        )

        return main_window

    # class public function that can be shared with each tab
    # callback for the "Browse" button
    def browse_filename(self, mode='r', exts=[AnyFileExt]):
        from pymol.Qt.utils import getSaveFileNameWithExt

        filter_strings = ';;'.join(
            [
                f'{ext_discrition} ( *.{ext_} )'
                for ext in exts
                for ext_, ext_discrition in ext.items()
            ]
        )

        if mode == 'w' or mode == 'a':
            browse_title = 'Save As...'
            filename = getSaveFileNameWithExt(
                self.window, browse_title, filter=filter_strings
            )
        else:
            browse_title = "Open ..."
            filename = getOpenFileNameWithExt(
                self.window, browse_title, filter=filter_strings
            )

            # Check if the selected file is a compressed archive
            is_compressed = [
                True
                for ext_, _ in CompressedFileExt.items()
                if filename.endswith(ext_)
            ]
            if any(is_compressed):
                # Ask whether to extract the file
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Question)
                msg.setWindowTitle("Extract Archive")
                msg.setText(
                    f"The selected file '{os.path.basename(filename)}' is a compressed archive. Do you want to extract it?"
                )
                msg.setStandardButtons(
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                result = msg.exec_()

                if result == QtWidgets.QMessageBox.Yes:
                    # Extract the archive and browse the extracted file
                    extracted_path = self.flatten_compressed_files(filename)
                    os.chdir(extracted_path)
                    return self.browse_filename(mode, exts=exts)
                else:
                    # Keep the previously selected filename and return it
                    return filename

        if filename:
            return filename

    # A universal and fussy function for value setting. ;-)
    def set_widget_value(self, widget, value):
        type_widget = type(widget)
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

        elif type_widget == QtWidgets.QLineEdit:
            widget.setText(str(value))

        elif type_widget == QtWidgets.QProgressBar:
            if type_value == list or type_value == tuple:
                widget.setRange(int(value[0]), int(value[1]))
            elif type_value == int:
                widget.setValue(int(value))
            else:
                logging.warning(
                    f'FIX ME: Value {value} ({type_value}) is not currently supported on widget {widget} ({type_widget})'
                )

        elif type_widget == QtWidgets.QLCDNumber:
            widget.display(str(value))

        elif type_widget == QtWidgets.QCheckBox:
            widget.setChecked(bool(value))
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

        else:
            logging.warning(
                f'FIX ME: Widget {widget} is not currently supported. '
            )

    # A universal and fussy function for input file path browsing.
    def open_input_filepath(self, lineEdit_input, exts=[AnyFileExt]):
        input_fn = self.browse_filename(mode='r', exts=exts)
        if input_fn:
            self.set_widget_value(lineEdit_input, input_fn)
            return input_fn

    def reload_molecule_info(
        self, trigger_checkBox, lineEdit_input_session, output_comboBox
    ):
        import tempfile

        self.temperal_session = tempfile.mktemp(suffix=".pse")

        self.new_session = (
            str(lineEdit_input_session.text()).strip().replace(' ', '')
        )

        if trigger_checkBox.isChecked():
            if not is_empty_session():
                logging.info(
                    f"Using current session: {trigger_checkBox.isChecked()}!"
                )
                cmd.save(self.temperal_session)
                cmd.reinitialize()
                cmd.load(self.temperal_session)
            else:
                logging.warning(
                    f'Current session is empty! \n \
                                Please load one PDB/PSE/PZE, otherwise uncheck `use_this_session`!'
                )
                return
        else:
            if self.new_session and os.path.exists(
                os.path.abspath(self.new_session)
            ):
                logging.info(f'Loading {self.new_session} ...')
                cmd.reinitialize()
                cmd.load(self.new_session)
                cmd.save(self.temperal_session)
            else:
                logging.warning(
                    f'Abored recognizing sessions from input: {self.new_session} .'
                )
                return

        molecule_objects = determine_molecule_objects()

        self.set_widget_value(output_comboBox, molecule_objects)

    def setup_nproc(self, comboBox_nproc):
        nprocs = determine_nproc()
        self.set_widget_value(comboBox_nproc, nprocs)
        self.set_widget_value(comboBox_nproc, max(nprocs))

    def open_structure_or_session(self, lineEdit_structure_session, mode='r'):
        if mode == 'r':
            input_pse_fn = self.open_input_filepath(
                lineEdit_structure_session,
                [SessionFileExt, PDB_FileExt, AnyFileExt],
            )
            if input_pse_fn:
                self.set_widget_value(lineEdit_structure_session, input_pse_fn)
            else:
                logging.warning(
                    f'Could not open file for reading: {input_pse_fn}'
                )
        elif mode == 'w':
            output_pse_fn = self.browse_filename(
                mode=mode, exts=[SessionFileExt, AnyFileExt]
            )
            if output_pse_fn and os.path.exists(
                os.path.dirname(output_pse_fn)
            ):
                logging.info(f"Output file is set as {output_pse_fn}")
                self.set_widget_value(
                    lineEdit_structure_session, output_pse_fn
                )
            else:
                logging.warning(f"Invalid output path: {output_pse_fn}.")
        else:
            logging.warning(f'Unknown mode {mode} ! Aborded.')

    def save_sessionfile(self, sessionfile):
        if not sessionfile:
            sessionfile = self.find_session_path()

        if sessionfile.endswith('.pze') or sessionfile.endswith('.pse'):
            cmd.save(sessionfile)
        else:
            logging.warning(f"Session file is not set properly: {sessionfile}")

    def release_run_button_if_lineEdit_fp_is_valid(
        self, lineEdits_fp, buttons_to_release
    ):
        button_unlocked = True

        for fp in lineEdits_fp:
            _fp = fp.text()
            logging.info(f'Checking file path: {_fp}')
            if not check_dirname_exists(_fp):
                logging.warning(
                    f'The parent dirname of `{_fp}` is not valid. Keep design buttoms locked!'
                )
                button_unlocked = False
                return
            else:
                if not check_file_exists(_fp):
                    logging.warning(f'The file `{_fp}` is not valid.')
                else:
                    logging.info(f'The file `{_fp}` is valid.')

        if button_unlocked:
            for button in buttons_to_release:
                button.setEnabled(True)
        else:
            for button in buttons_to_release:
                button.setEnabled(False)

    def update_chain_id(self, comboBox_molecule, comboBox_chainid):
        molecule = comboBox_molecule.currentText()
        if not molecule:
            logging.warning(f'No available designable molecule!')
            return
        chain_ids = determine_chain_id(molecule)
        self.set_widget_value(comboBox_chainid, chain_ids)
        self.set_widget_value(
            comboBox_chainid, chain_ids[0] if chain_ids else 0
        )

    def open_mutant_table(self, lineEdit_mutant_table, mode='r'):
        if mode == 'r':
            input_mut_txt_fn = self.open_input_filepath(
                lineEdit_mutant_table,
                [MutableFileExt, AnyFileExt, CompressedFileExt],
            )
            if input_mut_txt_fn:
                self.set_widget_value(lineEdit_mutant_table, input_mut_txt_fn)
            else:
                logging.warning(
                    f'Could not open file for reading: {input_mut_txt_fn}'
                )
        elif mode == 'w':
            output_mut_txt_fn = self.browse_filename(
                mode=mode, exts=[MutableFileExt, AnyFileExt]
            )
            if output_mut_txt_fn and os.path.exists(
                os.path.dirname(output_mut_txt_fn)
            ):
                logging.info(f"Output file is set as {output_mut_txt_fn}")
                self.set_widget_value(lineEdit_mutant_table, output_mut_txt_fn)
            else:
                logging.warning(f"Invalid output path: {output_mut_txt_fn}.")
        else:
            logging.warning(f'Unknown mode {mode} ! Aborded.')

    def write_input_mutant_table(self, output_mut_txt_fn, mutant_list):
        open(output_mut_txt_fn, 'w').write(
            '\n'.join(mutant_list) if mutant_list else ''
        )

    def determine_profile_format(
        self, lineEdit_input_profile, comboBox_profile_format
    ):
        profile_fp = os.path.abspath(lineEdit_input_profile.text())
        if not os.path.exists(profile_fp):
            return None

        profile_bn = os.path.basename(profile_fp)
        if profile_bn.endswith('.csv'):
            profile_format = 'CSV'
        elif profile_bn.endswith('.txt'):
            profile_format = 'TSV'
        elif profile_bn.endswith('.pssm') or profile_bn.endswith(
            'ascii_mtx_file'
        ):
            profile_format = 'PSSM'

        self.set_widget_value(comboBox_profile_format, profile_format)

    def save_mutant_choices(self, lineEdit_output_mut_txt, mutants_to_save):
        if not mutants_to_save:
            logging.warning(f"Mutant list is empty or None!")
            return None

        if type(mutants_to_save) == MutantTree:
            mutants_to_save = mutants_to_save.all_mutant_ids

        # TODO mutant_choices function
        output_mut_txt_fn = lineEdit_output_mut_txt.text()
        output_mut_txt_dir = os.path.dirname(output_mut_txt_fn)
        if not os.path.exists(output_mut_txt_dir):
            logging.warning(
                f'Parent dir for mutant table does NOT exist! {output_mut_txt_dir}'
            )
            # os.makedirs(output_mut_txt_dir,exist_ok=True)
            logging.warning(f'Skip saving mutant file.')
            return

        if os.path.exists(output_mut_txt_fn):
            logging.warning(
                f'Mutant table exists and will be overriden! {output_mut_txt_fn}'
            )
            self.write_input_mutant_table(
                output_mut_txt_fn,
                [extract_mutants(mt)[0] for mt in mutants_to_save],
            )

        else:
            logging.info(f'Mutant table is created at {output_mut_txt_fn}')
            self.write_input_mutant_table(
                output_mut_txt_fn,
                [extract_mutants(mt)[0] for mt in mutants_to_save],
            )

        output_mut_txt_dir_ckp = os.path.join(
            output_mut_txt_dir, f'{self.PWD}/checkpoints/'
        )
        os.makedirs(output_mut_txt_dir_ckp, exist_ok=True)

        output_mut_txt_bn_ckp = f'ckp_{time.strftime("%Y%m%d_%H%M%S", time.localtime())}.{os.path.basename(output_mut_txt_fn)}'
        output_mut_txt_ckp = os.path.join(
            output_mut_txt_dir_ckp, output_mut_txt_bn_ckp
        )

        logging.info(f'Saving checkpoint: {output_mut_txt_ckp}')
        self.write_input_mutant_table(
            output_mut_txt_ckp, [mt for mt in mutants_to_save]
        )

    def set_pymol_session_rock(self, checkBox_rock_pymol):
        cmd.rock(mode=checkBox_rock_pymol.isChecked())

    def center_design_area(self, mutant_id):
        if self.mutant_tree_pssm and mutant_id:
            logging.debug(f'Centering design area: {mutant_id}')
            cmd.center(mutant_id)
        else:
            logging.debug(f'Giving up centering design area: {mutant_id}')

    def find_session_path(self):
        session_path = cmd.get('session_file')
        if session_path and (
            session_path.endswith('.pze') or session_path.endswith('.pse')
        ):
            logging.info(f'Found session path: {session_path}')
            return session_path
        else:
            logging.info(
                'Session not found, please use a new session path to save.'
            )
            return self.browse_filename(mode='w', exts=[SessionFileExt])

    def flatten_compressed_files(self, compressed_file):
        flatten_path = os.path.join(
            self.PWD,
            'expanded_compressed_files',
            os.path.basename(compressed_file),
        )
        os.makedirs(flatten_path, exist_ok=True)
        extract_archive(archive_file=compressed_file, extract_to=flatten_path)
        return flatten_path

    '''
    Private functions used only in a specific tab.
    '''
    # Tab `Determine`

    def setup_pssm_gremlin_calculator(
        self, comboBox_design_molecule, comboBox_chainid
    ):
        molecule = str(comboBox_design_molecule.currentText())
        chain_id = str(comboBox_chainid.currentText())
        sequence = get_molecule_sequence(molecule=molecule, chain_id=chain_id)

        logging.debug(
            f'Molecule: {molecule}\nchain_id: {chain_id}\nsequence: {sequence}'
        )

        if molecule and chain_id and sequence:
            self.pssm_gremlin_calculator.setup_calculator(
                working_directory=self.PWD,
                molecule=molecule,
                chain_id=chain_id,
                sequence=sequence,
            )

    def reload_determine_tab_setup(
        self,
        comboBox_design_molecule,
        comboBox_ligand_sel,
        comboBox_cofactor_sel,
    ):
        from REvoDesign.common.magic_numbers import (
            DEFAULT_SURFACE_PROBE_RADIUS,
            DEFAULT_SUBSTRATE_POCKET_RADIUS,
            DEFAULT_COFACTOR_POCKET_RADIUS,
        )

        # Setup surface determination arguments
        self.ui.comboBox_surface_cutoff.clear()
        self.ui.comboBox_surface_cutoff.addItems(map(str, range(1, 36)))
        self.ui.comboBox_surface_cutoff.setCurrentIndex(
            self.ui.comboBox_surface_cutoff.findText(
                str(DEFAULT_SURFACE_PROBE_RADIUS)
            )
        )

        # Setup pocket determination arguments
        small_molecules = determine_small_molecule(
            comboBox_design_molecule.currentText()
        )
        comboBox_ligand_sel.clear()
        comboBox_ligand_sel.addItems(small_molecules)
        comboBox_ligand_sel.setCurrentIndex(len(small_molecules))

        comboBox_cofactor_sel.clear()
        comboBox_cofactor_sel.addItems(small_molecules)
        if len(small_molecules) >= 2:
            comboBox_cofactor_sel.setCurrentIndex(len(small_molecules) - 1)
        else:
            comboBox_cofactor_sel.setCurrentIndex(0)

        self.ui.comboBox_ligand_radius.clear()
        self.ui.comboBox_ligand_radius.addItems(map(str, range(1, 11)))
        self.ui.comboBox_ligand_radius.setCurrentIndex(
            self.ui.comboBox_ligand_radius.findText(
                str(DEFAULT_SUBSTRATE_POCKET_RADIUS)
            )
        )

        self.ui.comboBox_cofactor_radius.clear()
        self.ui.comboBox_cofactor_radius.addItems(map(str, range(0, 11)))
        self.ui.comboBox_cofactor_radius.setCurrentIndex(
            self.ui.comboBox_cofactor_radius.findText(
                str(DEFAULT_COFACTOR_POCKET_RADIUS)
            )
        )

    def update_surface_exclusion(self):
        exclusion_list = determine_exclusion()
        self.ui.comboBox_surface_exclusion.clear()
        self.ui.comboBox_surface_exclusion.addItems(exclusion_list)
        self.ui.comboBox_surface_exclusion.setCurrentIndex(
            0
        ) if exclusion_list else 0

    def run_chain_interface_detection(self):
        molecule = self.ui.comboBox_design_molecule.currentText()
        radius = int(self.ui.comboBox_interface_cutoff.currentText())
        for chain_id in determine_chain_id():
            cmd.select(
                f'if_{chain_id}',
                f'({molecule} and c. {chain_id} ) and byres ({molecule} and polymer.protein and (not c. {chain_id})) around {radius} and polymer.protein',
            )

    def run_surface_detection(self):
        input_file = self.temperal_session
        output_file = self.ui.lineEdit_output_pse_4.text()
        molecule = self.ui.comboBox_design_molecule.currentText()
        chain_id = self.ui.comboBox_chainid.currentText()
        exclusion = self.ui.comboBox_surface_exclusion.currentText()
        cutoff = int(self.ui.comboBox_surface_cutoff.currentText())
        do_show_surf_CA = True

        from REvoDesign.structure.Surface.findSurfaceResidues import (
            determine_surface_residue,
        )

        determine_surface_residue(
            input_file=input_file,
            output_file=output_file,
            molecule=molecule,
            chain_id=chain_id,
            exclude_residue_selection=exclusion,
            cutoff=cutoff,
            do_show_surf_CA=do_show_surf_CA,
        )

    def run_pocket_detection(self):
        input_file = self.temperal_session
        output_file = self.ui.lineEdit_output_pse_4.text()
        molecule = self.ui.comboBox_design_molecule.currentText()
        ligand = self.ui.comboBox_ligand_sel.currentText()
        cofactor = self.ui.comboBox_cofactor_sel.currentText()
        ligand_radius = int(self.ui.comboBox_ligand_radius.currentText())
        cofactor_radius = int(self.ui.comboBox_cofactor_radius.currentText())

        from REvoDesign.structure.pocket.read_enzyme_pockets import (
            read_enzyme_pockets,
        )

        read_enzyme_pockets(
            input_file=input_file,
            output_file=output_file,
            molecule=molecule,
            ligand=ligand,
            cofactor=cofactor,
            save_dir=f'{self.PWD}/pockets/',
            ligand_radius=ligand_radius,
            cofactor_radius=cofactor_radius,
        )

    # Tab `Load Mutants`

    def run_mutant_loading_from_profile(self):
        self.ui.pushButton_run_PSSM_to_pse.setEnabled(False)

        input_file = self.temperal_session
        molecule = self.ui.comboBox_molecule.currentText()
        chain_id = self.ui.comboBox_chainid_2.currentText()
        design_profile = self.ui.lineEdit_input_csv.text()
        design_profile_format = self.ui.comboBox_profile_type.currentText()
        preffered = self.ui.lineEdit_preffer_substitution.text().upper()
        rejected = self.ui.lineEdit_reject_substitution.text().upper()
        design_case = self.ui.lineEdit_design_case.text()
        custom_indices_fp = self.ui.lineEdit_input_customized_indices.text()
        cutoff = [
            float(self.ui.lineEdit_score_minima.text()),
            float(self.ui.lineEdit_score_maxima.text()),
        ]
        reversed_mutant_effect = (
            self.ui.checkBox_reverse_mutant_effect.isChecked()
        )
        output_pse = self.ui.lineEdit_output_pse.text()
        nproc = int(self.ui.comboBox_nproc_2.currentText())

        cmap = cmap_reverser(
            cmap=self.ui.comboBox_cmap_2.currentText(),
            reverse=reversed_mutant_effect,
        )

        progressbar = self.ui.progressBar_load_mutants
        sequence = get_molecule_sequence(molecule, chain_id)
        parallel_run = self.ui.checkBox_parallel.isChecked()

        # progressbarton=self.ui.pushButton_run_PSSM_to_pse

        logging.info(f"Sequence of `{molecule}`: \n {sequence}")

        from REvoDesign.phylogenetics.PSSM_profile import PssmAnalyzer

        design = PssmAnalyzer(design_profile)
        design.input_profile_format = design_profile_format
        design.molecule = molecule
        design.chain_id = chain_id
        design.pwd = self.PWD
        design.parallel_run = parallel_run
        design.cmap = cmap

        (
            mutation_json_fp,
            mutant_table_fp,
            mutation_png_fp,
        ) = design.design_protein_using_pssm(
            sequence,
            alias=molecule,
            preffered=preffered,
            design_case=design_case,
            custom_indices_fp=custom_indices_fp,
            cutoff=cutoff,
        )

        design.load_mutants_to_pymol_session(
            input_pse=input_file,
            output_pse=output_pse,
            molecule=molecule,
            chain_id=chain_id,
            mutant_json=mutation_json_fp,
            reject=rejected,
            create_full_pdb=False,
            progress_bar=progressbar,
            nproc=nproc,
        )

        cmd.reinitialize()
        cmd.load(output_pse)

        cmd.center(molecule)
        cmd.set('surface_color', 'gray70')
        cmd.set('cartoon_color', 'gray70')
        cmd.set('surface_cavity_mode', 4)
        cmd.set('transparency', 0.6)
        cmd.set(
            'cartoon_cylindrical_helices',
        )
        cmd.set('cartoon_transparency', 0.3)
        cmd.save(output_pse)

        self.ui.pushButton_run_PSSM_to_pse.setEnabled(True)

    # Tab `Choose Mutants`
    def activate_focused(
        self, checkBox_show_wt, comboBox_molecule, comboBox_chainid
    ):
        molecule = comboBox_molecule.currentText()
        chain_id = comboBox_chainid.currentText()

        if molecule and chain_id:
            _, mut_obj = extract_mutants(
                mutant_string=self.mutant_tree_pssm.current_mutant_id,
                chain_id=chain_id,
            )
            resi = mut_obj.get_mutant_info()[0]['position']

        if self.mutant_tree_pssm.current_mutant_id:
            cmd.enable(self.mutant_tree_pssm.current_mutant_id)
            cmd.show(
                'mesh',
                f'{self.mutant_tree_pssm.current_mutant_id} and (sidechain or n. CA)',
            )
            cmd.show(
                'sticks',
                f'{self.mutant_tree_pssm.current_mutant_id} and (sidechain or n. CA) and not hydrogen',
            )
            cmd.hide('cartoon', f'{self.mutant_tree_pssm.current_mutant_id}')
            if checkBox_show_wt.isChecked() and resi:
                cmd.show(
                    'lines',
                    f'{molecule} and c. {chain_id} and i. {resi} and (sidechain or n. CA) and not hydrogens',
                )
            elif resi:
                cmd.hide(
                    'lines',
                    f'{molecule} and c. {chain_id} and i. {resi} and (sidechain or n. CA) and not hydrogens',
                )

        if (
            self.mutant_tree_pssm.last_mutant_id
            and self.mutant_tree_pssm.last_mutant_id
            != self.mutant_tree_pssm.current_mutant_id
        ):
            cmd.disable(self.mutant_tree_pssm.last_mutant_id)
            cmd.hide(
                'mesh',
                f'{self.mutant_tree_pssm.last_mutant_id} and (sidechain or n. CA)',
            )
            cmd.hide(
                'sticks',
                f'{self.mutant_tree_pssm.last_mutant_id} and (sidechain or n. CA)',
            )

        # close group object if deactivated
        if (
            self.mutant_tree_pssm.last_branch_id != ''
            and self.mutant_tree_pssm.current_branch_id
            != self.mutant_tree_pssm.last_branch_id
        ):
            cmd.disable(self.mutant_tree_pssm.last_branch_id)
            cmd.group(self.mutant_tree_pssm.last_branch_id, action='close')

        # expand group object if activated
        if (
            self.mutant_tree_pssm.current_branch_id
            and self.mutant_tree_pssm.current_branch_id
            != self.mutant_tree_pssm.last_branch_id
        ):
            cmd.enable(self.mutant_tree_pssm.current_branch_id)
            cmd.group(self.mutant_tree_pssm.current_branch_id, action='open')

        self.center_design_area(self.mutant_tree_pssm.current_mutant_id)

    def accept_mutant(self, lcdNumber_selected_mutant):
        if self.is_this_pymol_object_a_mutant(
            self.mutant_tree_pssm.current_mutant_id
        ):
            logging.debug(
                f'Accepting mutant {self.mutant_tree_pssm.current_mutant_id}'
            )
            self.mutant_tree_pssm_selected.add_mutant_to_branch(
                branch=self.mutant_tree_pssm.current_branch_id,
                mutant=self.mutant_tree_pssm.current_mutant_id,
                mutant_info=extract_mutants(
                    self.mutant_tree_pssm.current_mutant_id
                )[1],
            )
        else:
            logging.warning(
                f'Ingoring non mutant {self.mutant_tree_pssm.current_mutant_id}'
            )

        self.set_widget_value(
            lcdNumber_selected_mutant,
            len(self.mutant_tree_pssm_selected.all_mutant_ids),
        )

        self.save_mutant_choices(
            self.ui.lineEdit_output_mut_table, self.mutant_tree_pssm_selected
        )

    def reject_mutant(self, lcdNumber_selected_mutant):
        if self.is_this_pymol_object_a_mutant(
            self.mutant_tree_pssm.current_mutant_id
        ):
            logging.debug(
                f'Rejecting mutant {self.mutant_tree_pssm.current_mutant_id}'
            )

            self.mutant_tree_pssm_selected.remove_mutant_from_branch(
                branch=self.mutant_tree_pssm.current_branch_id,
                mutant=self.mutant_tree_pssm.current_mutant_id,
            )

        else:
            logging.warning(
                f'Ingoring non mutant {self.mutant_tree_pssm.current_mutant_id}'
            )

        self.set_widget_value(
            lcdNumber_selected_mutant,
            len(self.mutant_tree_pssm_selected.all_mutant_ids),
        )

        self.save_mutant_choices(
            self.ui.lineEdit_output_mut_table,
            self.mutant_tree_pssm_selected,
        )

    def walk_mutant_groups(
        self,
        walk_to_next,
        progressBar_mutant_choosing,
        checkBox_show_wt,
        comboBox_molecule,
        comboBox_chainid,
    ):
        self.mutant_tree_pssm.walk_the_mutants(walk_to_next_one=walk_to_next)

        self.set_widget_value(
            progressBar_mutant_choosing,
            self.mutant_tree_pssm.get_mutant_index_in_all_mutants(
                self.mutant_tree_pssm.current_mutant_id
            ),
        )

        self.activate_focused(
            checkBox_show_wt, comboBox_molecule, comboBox_chainid
        )
        logging.info(
            f'Walked to the {"next" if walk_to_next else "previous"} mutant {self.mutant_tree_pssm.current_mutant_id}.'
        )

    def jump_to_branch(
        self,
        comboBox_group_ids,
        checkBox_show_wt,
        comboBox_molecule,
        comboBox_chainid,
        progressBar_mutant_choosing,
    ):
        branch = comboBox_group_ids.currentText()
        if not branch:
            logging.warning(f'Branch id is empty or null, skipped.')
            return
        elif not self.mutant_tree_pssm:
            logging.error(f'Mutant tree is invalid.')
            return
        else:
            logging.info(f'Jump to {branch} as required.')
            self.mutant_tree_pssm.jump_to_branch(branch_id=branch)

            progress = self.mutant_tree_pssm.get_mutant_index_in_all_mutants(
                self.mutant_tree_pssm.current_mutant_id
            )
            logging.info(
                f'Progressbar set to {progress}: {self.mutant_tree_pssm.current_mutant_id}'
            )
            self.set_widget_value(progressBar_mutant_choosing, progress)

            self.activate_focused(
                checkBox_show_wt, comboBox_molecule, comboBox_chainid
            )
            return

    def jump_to_the_best_mutant(
        self,
        checkBox_show_wt,
        comboBox_molecule,
        comboBox_chainid,
        progressBar_mutant_choosing,
        checkBox_reverse_mutant_effect,
    ):
        self.mutant_tree_pssm.jump_to_the_best_mutant_in_branch(
            branch_id=self.mutant_tree_pssm.current_branch_id,
            reversed=checkBox_reverse_mutant_effect.isChecked(),
        )
        logging.info(
            f'Jump to the best hit of {self.mutant_tree_pssm.current_branch_id}: {self.mutant_tree_pssm.current_mutant_id}'
        )
        self.activate_focused(
            checkBox_show_wt, comboBox_molecule, comboBox_chainid
        )

        progress = self.mutant_tree_pssm.get_mutant_index_in_all_mutants(
            self.mutant_tree_pssm.current_mutant_id
        )
        logging.info(
            f'Progressbar set to {progress}: {self.mutant_tree_pssm.current_mutant_id}'
        )
        self.set_widget_value(progressBar_mutant_choosing, progress)

    # basic function that works for mutant_tree instantiation
    def is_this_pymol_object_a_mutant(self, mutant):
        _mutant, _mutant_obj = extract_mutants(mutant_string=mutant)
        return _mutant is not None

    # basic function that works for mutant_tree instantiation
    def fetch_all_mutant_branch_ids(self, enabled_only=0):
        self.all_mutant_branch_ids = [
            group_id
            for group_id in cmd.get_names(
                type='group_objects', enabled_only=enabled_only
            )
        ]

    # basic function that works for mutant_tree instantiation
    def fetch_all_mutant_in_one_branch(self, group_id, enabled_only=0):
        all_nongroup_objects = cmd.get_names('nongroup_objects', enabled_only)

        # cmd.get_object_list:
        # https://sourceforge.net/p/pymol/mailman/message/34797180/
        mutants_in_current_group = [
            mutant
            for mutant in cmd.get_object_list(f'({group_id})')
            if self.is_this_pymol_object_a_mutant(mutant)
            and mutant in all_nongroup_objects
        ]

        all_mutants_in_current_branch = {}
        for mutant_id in mutants_in_current_group:
            mutant_, mutant_obj = extract_mutants(mutant_id)
            all_mutants_in_current_branch.update({mutant_id: mutant_obj})

        return all_mutants_in_current_branch

    # basic function that works for mutant_tree instantiation
    def fetch_mutant_tree(self, reinitialize=False):
        if reinitialize:
            # self.all_mutant_groups
            self.fetch_all_mutant_branch_ids()
            if not self.all_mutant_branch_ids:
                logging.error(f'This sesion may not contain an mutant tree.')
                return None
            mutant_tree = {}

            # self.all_mutants_in_all_groups
            for group_id in self.all_mutant_branch_ids:
                mutant_branch = self.fetch_all_mutant_in_one_branch(group_id)
                mutant_tree.update({group_id: mutant_branch})
                logging.info(
                    f'update {group_id} with {len(mutant_branch.keys())} mutants.'
                )

            # instantialize a mutant tree from current session.
            self.mutant_tree_pssm = MutantTree(mutant_tree)
        else:
            logging.warning(
                f'This sesion already has a valid mutant tree. To regenerate it, smash the `Reinitialize` button.'
            )

    def read_design_wt_info_from_group_id(self, group_id):
        logging.debug(f'Parsing group id {group_id}')
        matched_group_id = re.match(r'mt_(\w)(\d+)_([\-\d\.]+)', group_id)
        wild_type, design_resi, wild_type_score = (
            matched_group_id.group(1),
            matched_group_id.group(2),
            matched_group_id.group(3),
        )
        return int(design_resi), wild_type, float(wild_type_score)

    def recover_mutant_choices_from_checkpoint(
        self, lcdNumber_selected_mutant
    ):
        mutant_choice_checkpoint_fn = self.browse_filename(
            mode='r', exts=[MutableFileExt, AnyFileExt]
        )
        if os.path.exists(mutant_choice_checkpoint_fn):
            mutants_from_checkpoint = (
                open(mutant_choice_checkpoint_fn, 'r')
                .read()
                .strip()
                .split('\n')
            )

            self.mutant_tree_pssm_selected = (
                self.mutant_tree_pssm.create_mutant_tree_from_list(
                    mutants_from_checkpoint
                )
            )
            logging.info(
                f'Recover mutants from checkpoint: {mutant_choice_checkpoint_fn}'
            )
            logging.info(mutants_from_checkpoint)

            self.set_widget_value(
                lcdNumber_selected_mutant,
                len(self.mutant_tree_pssm_selected.all_mutant_ids),
            )

    def initialize_design_candidates(
        self,
        comboBox_molecule,
        comboBox_chainid,
        pushButton_previous_mutant,
        pushButton_next_mutant,
        pushButton_reject_this_mutant,
        pushButton_accept_this_mutant,
        lcdNumber_total_mutant,
        lcdNumber_selected_mutant,
        lineEdit_output_mut_txt,
        progressBar_mutant_choosing,
        comboBox_group_ids,
        checkBox_show_wt,
    ):
        self.fetch_mutant_tree(reinitialize=True)
        if not self.all_mutant_branch_ids:
            logging.error(f'This sesion may not contain an mutant tree.')
            return None

        self.mutant_tree_pssm_selected = MutantTree({})

        # if mutant tree is available, disable the input box for saving.

        lineEdit_output_mut_txt.setEnabled(not ((self.mutant_tree_pssm)))

        if not self.mutant_tree_pssm:
            logging.warning(
                'Could not initialize mutant tree! This session may not be a REvoDesign session!'
            )
            return

        # clean the view
        cmd.disable(' or '.join(self.mutant_tree_pssm.all_mutant_branch_ids))
        cmd.hide('sticks', ' or '.join(self.mutant_tree_pssm.all_mutant_ids))
        cmd.disable(' or '.join(self.mutant_tree_pssm.all_mutant_ids))

        comboBox_molecule.currentIndexChanged.connect(
            partial(
                self.update_chain_id,
                comboBox_molecule,
                comboBox_chainid,
            )
        )

        self.set_widget_value(comboBox_molecule, determine_molecule_objects())

        self.set_widget_value(
            progressBar_mutant_choosing,
            [0, len(self.mutant_tree_pssm.all_mutant_ids)],
        )

        self.set_widget_value(
            comboBox_group_ids, self.mutant_tree_pssm.all_mutant_branch_ids
        )
        self.set_widget_value(
            comboBox_group_ids, self.mutant_tree_pssm.all_mutant_branch_ids[0]
        )

        self.activate_focused(
            checkBox_show_wt, comboBox_molecule, comboBox_chainid
        )

        # show the current branch and mutant
        cmd.enable(self.mutant_tree_pssm.current_mutant_id)
        cmd.enable(self.mutant_tree_pssm.current_branch_id)

        self.set_widget_value(
            lcdNumber_total_mutant, len(self.mutant_tree_pssm.all_mutant_ids)
        )
        self.set_widget_value(
            lcdNumber_selected_mutant,
            len(self.mutant_tree_pssm_selected.all_mutant_ids),
        )

        # initialize mutant walking

        # set state changes to pushbuttons accroding to the mutant tree
        for pushButton in [
            pushButton_previous_mutant,
            pushButton_next_mutant,
            pushButton_reject_this_mutant,
            pushButton_accept_this_mutant,
        ]:
            try:
                pushButton.clicked.disconnect()
            except:
                pass
            pushButton.setEnabled(bool(self.mutant_tree_pssm))

        pushButton_accept_this_mutant.clicked.connect(
            partial(self.accept_mutant, lcdNumber_selected_mutant)
        )
        pushButton_reject_this_mutant.clicked.connect(
            partial(self.reject_mutant, lcdNumber_selected_mutant)
        )

        pushButton_next_mutant.clicked.connect(
            partial(
                self.walk_mutant_groups,
                True,
                progressBar_mutant_choosing,
                checkBox_show_wt,
                comboBox_molecule,
                comboBox_chainid,
            )
        )

        pushButton_previous_mutant.clicked.connect(
            partial(
                self.walk_mutant_groups,
                False,
                progressBar_mutant_choosing,
                checkBox_show_wt,
                comboBox_molecule,
                comboBox_chainid,
            )
        )

    # combination and clustering
    def run_clustering(self):
        # lazy module loading to fasten plugin initializing
        from REvoDesign.clusters.combine_positions import Combinations
        from REvoDesign.clusters.cluster_sequence import Clustering

        input_molecule = self.ui.comboBox_molecule_4.currentText()
        input_chain_id = self.ui.comboBox_chainid_3.currentText()
        input_mutant_table = self.ui.lineEdit_input_mut_table.text()

        cluster_batch_size = int(
            self.ui.comboBox_cluster_batchsize.currentText()
        )
        cluster_number = int(self.ui.comboBox_num_cluster.currentText())
        min_mut_num = int(self.ui.comboBox_num_mut_minimun.currentText())
        max_mut_num = int(self.ui.comboBox_num_mut_maximum.currentText())
        cluster_substitution_matrix = (
            self.ui.comboBox_cluster_matrix.currentText()
        )

        shuffle_variant = self.ui.checkBox_shuffle_clustering.isChecked()

        nproc = int(self.ui.comboBox_nproc_3.currentText())

        # output space
        plot_space = self.ui.stackedWidget
        progressbar = self.ui.progressBar_clustering

        input_sequence = get_molecule_sequence(
            molecule=input_molecule, chain_id=input_chain_id
        )
        logging.info(
            f'Sequence for {input_molecule}, chain id: {input_chain_id}: \n {input_sequence}'
        )
        input_fasta_file = (
            f'{self.PWD}/{input_molecule}_{input_chain_id}.fasta'
        )
        open(input_fasta_file, 'w').write(
            f'>{input_molecule}_{input_chain_id}\n{input_sequence}'
        )
        logging.info(f'Sequence file is saved as {input_fasta_file}')

        # output files
        cluster_outputs = {}

        for num_mut in range(min_mut_num, max_mut_num + 1):
            # combination
            combinations = Combinations()
            combinations.fastasequence = input_sequence
            combinations.chain_id = input_chain_id
            combinations.fastafile = input_fasta_file
            combinations.inputfile = input_mutant_table
            combinations.combi = num_mut
            combinations.path = self.PWD
            combinations.processors = nproc

            # expected design combination file

            combinations.run_combinations()
            expected_design_combinations = combinations.expected_output_fasta

            # clustering

            clustering = Clustering(fastafile=expected_design_combinations)
            clustering.batch_size = cluster_batch_size
            clustering.num_proc = nproc
            clustering.num_clusters = cluster_number
            clustering.shuffle_variant = shuffle_variant
            clustering.substitution_matrix = cluster_substitution_matrix
            clustering._save_dir = self.PWD

            clustering.initialize_aligner()

            clustering.run_clustering(progressbar=progressbar)
            cluster_outputs.update({num_mut: clustering.cluster_output_fp})

        cluster_imgs = [
            _cluster['score'] for _, _cluster in cluster_outputs.items()
        ]
        self.set_widget_value(plot_space, cluster_imgs)

    # Tab Visualize

    def get_mutant_table_columns(self, mutfile):
        import pandas as pd

        table_extensions = [f'.{ext}' for ext, _ in MutableFileExt.items()]

        if not any(
            [True for ext in table_extensions if mutfile.lower().endswith(ext)]
        ):
            return None

        elif mutfile.lower().endswith('.txt'):
            return None

        elif mutfile.lower().endswith('.csv'):
            mutation_data = pd.read_csv(mutfile)

        elif mutfile.lower().endswith('.tsv'):
            mutation_data = pd.read_fwf(mutfile)

        elif mutfile.lower().endswith('.xlsx') or mutfile.lower().endswith(
            '.xls'
        ):
            mutation_data = pd.read_excel(mutfile)

        return list(mutation_data.columns)

    def update_mutant_table_columns(
        self,
        lineEdit_input_mut_table_csv,
        comboBox_best_leaf,
        comboBox_totalscore,
    ):
        mut_table_fp = lineEdit_input_mut_table_csv.text()
        if not os.path.exists(mut_table_fp):
            logging.warning(f'Mutant Table path is not valid: {mut_table_fp}')
            return
        else:
            mut_table_cols = self.get_mutant_table_columns(
                mutfile=mut_table_fp
            )

            if not mut_table_cols:
                logging.warning(
                    f'Mutant Table column names is not valid: {mut_table_cols}'
                )
                return
            else:
                # set cols to combo boxes
                for comboBox in [comboBox_best_leaf, comboBox_totalscore]:
                    self.set_widget_value(comboBox, mut_table_cols)

                # set default col value
                if len(mut_table_cols) > 1:
                    self.set_widget_value(
                        comboBox_best_leaf, mut_table_cols[0]
                    )
                    self.set_widget_value(
                        comboBox_totalscore, mut_table_cols[-1]
                    )

    def save_visualizing_mutant_tree(
        self, lineEdit_mutant_table_fp, lineEdit_group_name
    ):
        lineEdit_mutant_table_fp = lineEdit_mutant_table_fp
        group_name = lineEdit_group_name.text()

        mutant_table_fp = lineEdit_mutant_table_fp.text()

        if not os.path.exists(mutant_table_fp):
            logging.warning(
                f'Mutant table path is not available. Now we will create one.'
            )

        all_available_groups = cmd.get_names(
            type='group_objects', enabled_only=0
        )
        if group_name not in all_available_groups:
            logging.error(
                f'Group {group_name} is not correct. Available group: {all_available_groups}'
            )
            return

        logging.info('Instantializing MutantTree for current selection ... ')
        self.visualizing_mutant_tree = MutantTree(
            {
                group_name: self.fetch_all_mutant_in_one_branch(
                    group_id=group_name, enabled_only=1
                )
            }
        )

        logging.info(f'Saving mutant table to {mutant_table_fp} ...')

        self.save_mutant_choices(
            lineEdit_mutant_table_fp,
            self.visualizing_mutant_tree.all_mutant_ids,
        )

    def visualize_mutants(self):
        input_pse = self.temperal_session
        input_mut_table_csv = self.ui.lineEdit_input_mut_table_csv.text()
        molecule = self.ui.comboBox_molecule_2.currentText()
        chainid = self.ui.comboBox_chainid_4.currentText()
        output_pse = self.ui.lineEdit_output_pse_2.text()
        best_leaf = self.ui.comboBox_best_leaf.currentText()
        totalscore = self.ui.comboBox_totalscore.currentText()
        nproc = int(self.ui.comboBox_nproc_4.currentText())
        group_name = self.ui.lineEdit_group_name.text()

        reversed_mutant_effect = (
            self.ui.checkBox_reverse_mutant_effect_3.isChecked()
        )
        cmap = cmap_reverser(
            cmap=self.ui.comboBox_cmap.currentText(),
            reverse=reversed_mutant_effect,
        )

        design_profile = self.ui.lineEdit_input_csv_2.text()
        design_profile_format = self.ui.comboBox_profile_type_2.currentText()

        progressBar_visualize_mutants = self.ui.progressBar_visualize_mutants

        from REvoDesign.common.MutantVisualizer import MutantVisualizer

        visualizer = MutantVisualizer(
            molecule=molecule,
            chain_id=chainid,
        )
        visualizer.mutfile = input_mut_table_csv
        visualizer.input_session = input_pse
        visualizer.nproc = nproc

        if os.path.exists(design_profile):
            visualizer.profile_scoring_df = visualizer.parse_profile(
                profile_fp=design_profile, profile_format=design_profile_format
            )
            logging.debug(visualizer.profile_scoring_df.head())
        else:
            logging.warning(
                "Profile data is not available. Trying to read scores from the mutant table ..."
            )
            visualizer.profile_scoring_df = None

        if best_leaf:
            visualizer.key_col = best_leaf
        if totalscore:
            visualizer.score_col = totalscore

        visualizer.save_session = output_pse
        visualizer.full = False
        visualizer.group_name = group_name
        visualizer.cmap = cmap

        visualizer.run_with_progressbar(
            progress_bar=progressBar_visualize_mutants
        )

        cmd.reinitialize()
        cmd.load(output_pse)
        cmd.center(molecule)
        cmd.set('surface_color', 'gray70')
        cmd.set('cartoon_color', 'gray70')
        cmd.set('surface_cavity_mode', 4)
        cmd.set('transparency', 0.6)
        cmd.set(
            'cartoon_cylindrical_helices',
        )
        cmd.set('cartoon_transparency', 0.3)
        cmd.save(output_pse)

    # Tab Interact via GREMLIN
    def load_gremlin_mrf(
        self,
    ):
        from REvoDesign.phylogenetics.GREMLIN_Tools import GREMLIN_Tools

        self.ui.pushButton_reinitialize_interact.setEnabled(False)

        try:
            gremlin_mrf_fp = self.ui.lineEdit_input_gremlin_mtx.text()

            topN_gremlin_candidates = int(
                self.ui.comboBox_gremlin_topN.currentText()
            )
            molecule = self.ui.comboBox_molecule_3.currentText()
            chain_id = self.ui.comboBox_chainid_9.currentText()
            pushButton_run_interact_scan = self.ui.pushButton_run_interact_scan
            gridLayout_interact_pairs = self.ui.gridLayout_interact_pairs

            progress_bar = self.ui.progressBar_gremlin_visualizing

            # Reinitialize Gremlin mutant tree
            self.mutant_tree_coevolved = MutantTree({})

            self.gremlin_tool = GREMLIN_Tools(molecule=molecule)

            if self.ui.checkBox_use_this_session_4.isChecked():
                self.gremlin_tool.sequence = get_molecule_sequence(
                    molecule=molecule, chain_id=chain_id
                )

            if (
                not molecule
                or not chain_id
                or not os.path.exists(gremlin_mrf_fp)
            ):
                logging.error(
                    "Could not run GREMLIN tools. Please check your configuration"
                )
                return

            run_worker_thread_with_progress(
                self.gremlin_tool.load_msa_and_mrf,
                progress_bar=progress_bar,
                mrf_path=gremlin_mrf_fp,
            )

            pushButton_run_interact_scan.setEnabled(bool(self.gremlin_tool))

            if not self.gremlin_tool:
                logging.error(
                    f'Failed to create gremlin tool object. Please check the inputs.'
                )

                return

            self.gremlin_tool.pwd = self.PWD
            self.gremlin_tool.topN = topN_gremlin_candidates

            self.gremlin_tool.get_to_coevolving_pairs()
            plot_mtx_fp = self.gremlin_tool.plot_mtx()

            self.set_widget_value(gridLayout_interact_pairs, plot_mtx_fp)

        finally:
            self.ui.pushButton_reinitialize_interact.setEnabled(True)

    def run_gremlin_tool(self):
        molecule = self.ui.comboBox_molecule_3.currentText()
        chain_id = self.ui.comboBox_chainid_9.currentText()

        progress_bar = self.ui.progressBar_gremlin_visualizing
        max_interact_dist = int(
            self.ui.comboBox_max_interact_dist.currentText()
        )

        self.plot_w_fps = {}

        if self.any_posision_has_been_selected():
            logging.info(f'One vs All mode.')
            self.gremlin_tool_a2a_mode = False
            resi = int(cmd.get_model('sele and n. CA').atom[0].resi)
            logging.info(f'{resi} is selected.')

            self.plot_w_fps = run_worker_thread_with_progress(
                self.gremlin_tool.analyze_coevolving_pairs_for_i,
                progress_bar=progress_bar,
                i=resi - 1,
            )

            if not self.plot_w_fps:
                logging.warning(
                    f'No Available co-evolutionary signal against {resi}'
                )
                # early return if no data.
                return

            logging.info(
                f'Found {len(self.plot_w_fps.keys())} pairs against {resi}.'
            )

            self.renumber_plot_w_fps()

        else:
            logging.info(
                f'No selection `sele` is picked, use All vs All mode.'
            )
            self.gremlin_tool_a2a_mode = True
            self.plot_w_fps = run_worker_thread_with_progress(
                self.gremlin_tool.plot_w_in_batch, progress_bar=progress_bar
            )

            if not self.plot_w_fps:
                logging.warning(
                    f'No Available co-evolutionary signal in global'
                )
                # early return if no data.
                return

            logging.info(
                f'Found {len(self.plot_w_fps.keys())} pairs in global'
            )

        logging.debug(self.plot_w_fps)

        # visualize co-evolved pair in pymol UI
        min_gremlin_score = min(
            [
                min(
                    [self.plot_w_fps[i][0][-1] for i in self.plot_w_fps.keys()]
                ),
                0,
            ]
        )
        max_gremlin_score = max(
            [self.plot_w_fps[i][0][-1] for i in self.plot_w_fps.keys()]
        )

        ce_object_name = cmd.get_unused_name(f"ce_pairs_{molecule}_{chain_id}")

        cmd.create(ce_object_name, f'{molecule} and c. {chain_id} and n. CA')
        cmd.hide('cartoon', ce_object_name)
        cmd.hide('surface', ce_object_name)
        for i, pair_resi in self.plot_w_fps.items():
            logging.debug(pair_resi)
            spatial_distance = cmd.get_distance(
                atom1=f'{molecule} and c. {chain_id} and i. {pair_resi[0][0]+1} and n. CA',
                atom2=f'{molecule} and c. {chain_id} and i. {pair_resi[0][1]+1} and n. CA',
            )
            if spatial_distance > max_interact_dist:
                logging.info(
                    f'Resi {pair_resi[0][0]+1} is {spatial_distance:.2f} Å away from {pair_resi[0][1]+1}, out of distance {max_interact_dist}'
                )

            cmd.bond(
                f'{ce_object_name} and c. {chain_id} and resi {pair_resi[0][0]+1} and n. CA',
                f'{ce_object_name} and c. {chain_id} and resi {pair_resi[0][1]+1} and n. CA',
            )
            cmd.set(
                'stick_radius',
                rescale_number(
                    pair_resi[0][-1],
                    min_value=min_gremlin_score,
                    max_value=max_gremlin_score,
                ),
                f'({ce_object_name}  and c. {chain_id} and resi {pair_resi[0][0]+1}+{pair_resi[0][1]+1} and n. CA)',
            )

        cmd.show('sticks', ce_object_name)
        cmd.set('stick_use_shader', 0)
        cmd.set('stick_round_nub', 0)
        cmd.set('stick_color', 'gray70', ce_object_name)

        try:
            self.ui.pushButton_previous.clicked.disconnect()
            self.ui.pushButton_next.clicked.disconnect()
        except:
            pass

        self.ui.pushButton_previous.clicked.connect(
            partial(self.load_co_evolving_pairs, progress_bar, False)
        )

        self.ui.pushButton_next.clicked.connect(
            partial(self.load_co_evolving_pairs, progress_bar, True)
        )

        # intitialize
        self.set_widget_value(progress_bar, [0, len(self.plot_w_fps.keys())])
        self.current_gremlin_co_evoving_pair_index = -1

        self.current_gremlin_co_evoving_pair_mutant_id = ''
        self.last_gremlin_co_evoving_pair_mutant_id = ''

        self.current_gremlin_co_evoving_pair_group_id = ''
        self.last_gremlin_co_evoving_pair_group_id = ''

        self.load_co_evolving_pairs(progress_bar)

    def any_posision_has_been_selected(self):
        return bool(
            [
                x
                for x in cmd.get_names(type='selections', enabled_only=1)
                if x == 'sele'
            ]
        )

    def renumber_plot_w_fps(self):
        logging.info('Renumbering anaysis results.')
        new_plot_w_fps = {}
        for new_idx, data in enumerate(self.plot_w_fps.values()):
            new_plot_w_fps[new_idx] = data
        self.plot_w_fps = new_plot_w_fps

    def load_co_evolving_pairs(
        self,
        progress_bar,
        walk_to_next=True,
    ):
        molecule = self.ui.comboBox_molecule_3.currentText()
        chain_id = self.ui.comboBox_chainid_9.currentText()
        ignore_wt = self.ui.checkBox_interact_ignore_wt.isChecked()
        max_interact_dist = int(
            self.ui.comboBox_max_interact_dist.currentText()
        )

        lineEdit_current_design = self.ui.lineEdit_current_design

        if not chain_id or not molecule:
            logging.error(f'No available molecule or chain id.')
            return

        if walk_to_next:
            if self.current_gremlin_co_evoving_pair_index == -1:
                logging.info('Initialized.')
                self.current_gremlin_co_evoving_pair_index = 0
            elif (
                self.current_gremlin_co_evoving_pair_index
                == len(self.plot_w_fps.keys()) - 1
            ):
                logging.info(
                    "Co-vary pairs are already reach the last one, returning to the first."
                )
                self.current_gremlin_co_evoving_pair_index = 0
            else:
                self.current_gremlin_co_evoving_pair_index += 1
        else:
            if self.current_gremlin_co_evoving_pair_index == -1:
                logging.info('Initialized.')
                self.current_gremlin_co_evoving_pair_index = (
                    len(self.plot_w_fps.keys()) - 1
                )
            elif self.current_gremlin_co_evoving_pair_index == 0:
                logging.info(
                    "Co-vary pairs are already reach the first one, returning to the last."
                )
                self.current_gremlin_co_evoving_pair_index = (
                    len(self.plot_w_fps.keys()) - 1
                )
            else:
                self.current_gremlin_co_evoving_pair_index -= 1

        self.set_widget_value(
            progress_bar, self.current_gremlin_co_evoving_pair_index
        )

        (wt_info, csv_fp, plot_fp) = self.plot_w_fps[
            self.current_gremlin_co_evoving_pair_index
        ]

        # Clear the existing widgets from gridLayout_interact_pairs
        for i in reversed(range(self.ui.gridLayout_interact_pairs.count())):
            widget = self.ui.gridLayout_interact_pairs.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        button_matrix = QbuttonMatrix(csv_fp)
        button_matrix.sequence = self.gremlin_tool.sequence
        button_matrix.pos_i, button_matrix.pos_j, _, __, ___ = wt_info

        button_matrix.init_ui()

        button_matrix.report_axes_signal.connect(
            lambda row, col: self.mutate_with_gridbuttons(
                row,
                col,
                molecule,
                chain_id,
                button_matrix.matrix,
                button_matrix.min_value,
                button_matrix.max_value,
                wt_info,
                ignore_wt,
            )
        )
        self.ui.gridLayout_interact_pairs.addWidget(button_matrix)

        spatial_distance = cmd.get_distance(
            atom1=f'{molecule} and c. {chain_id} and i. {button_matrix.pos_i+1} and n. CA',
            atom2=f'{molecule} and c. {chain_id} and i. {button_matrix.pos_j+1} and n. CA',
        )

        self.set_widget_value(
            lineEdit_current_design,
            ' vs '.join(wt_info[-3:-1]) + f' in dist {spatial_distance:.2f} Å',
        )

        if max_interact_dist and spatial_distance > max_interact_dist:
            logging.warning(
                f'Resi {button_matrix.pos_i+1} is {spatial_distance:.2f} Å away from {button_matrix.pos_j+1}, out of distance {max_interact_dist}'
            )
            self.set_widget_value(
                lineEdit_current_design, 'Residues are out of distance.'
            )
            # To disable the QbuttonMatrix:
            button_matrix.setEnabled(False)
        else:
            # To enable the QbuttonMatrix:
            button_matrix.setEnabled(True)

    def accept_coevoled_mutant(self):
        logging.debug(
            f'Accepting co-evolved mutant {self.current_gremlin_co_evoving_pair_mutant_id}'
        )
        cmd.enable(self.current_gremlin_co_evoving_pair_mutant_id)

        self.mutant_tree_coevolved.add_mutant_to_branch(
            self.current_gremlin_co_evoving_pair_group_id,
            self.current_gremlin_co_evoving_pair_mutant_id,
            extract_mutants(
                mutant_string=self.current_gremlin_co_evoving_pair_mutant_id
            )[1],
        )

        self.save_mutant_choices(
            self.ui.lineEdit_output_mutant_table,
            self.mutant_tree_coevolved,
        )

    def reject_coevoled_mutant(self):
        logging.debug(
            f'Rejecting co-evolved mutant {self.current_gremlin_co_evoving_pair_mutant_id}'
        )
        cmd.disable(self.current_gremlin_co_evoving_pair_mutant_id)
        self.mutant_tree_coevolved.remove_mutant_from_branch(
            self.current_gremlin_co_evoving_pair_group_id,
            self.current_gremlin_co_evoving_pair_mutant_id,
        )

        self.save_mutant_choices(
            self.ui.lineEdit_output_mutant_table, self.mutant_tree_coevolved
        )

    def activate_focused_interaction(self):
        if (
            self.current_gremlin_co_evoving_pair_mutant_id
            == self.last_gremlin_co_evoving_pair_mutant_id
        ):
            return

        if self.current_gremlin_co_evoving_pair_mutant_id:
            cmd.enable(self.current_gremlin_co_evoving_pair_mutant_id)
            cmd.show(
                'sticks',
                f'{self.current_gremlin_co_evoving_pair_mutant_id} and (sidechain or n. CA) and not hydrogen',
            )
            cmd.show(
                'mesh',
                f'{self.current_gremlin_co_evoving_pair_mutant_id} and (sidechain or n. CA)',
            )
            cmd.hide(
                'cartoon', f'{self.current_gremlin_co_evoving_pair_mutant_id}'
            )
        if self.last_gremlin_co_evoving_pair_mutant_id:
            cmd.disable(self.last_gremlin_co_evoving_pair_mutant_id)
            cmd.hide(
                'mesh',
                f'{self.last_gremlin_co_evoving_pair_mutant_id} and (sidechain or n. CA)',
            )
            cmd.hide(
                'sticks',
                f'{self.last_gremlin_co_evoving_pair_mutant_id} and (sidechain or n. CA) and not hydrogen',
            )
            cmd.hide(
                'cartoon', f'{self.current_gremlin_co_evoving_pair_mutant_id}'
            )

    def mutate_with_gridbuttons(
        self,
        col,
        row,
        molecule,
        chain_id,
        matrix,
        min_score,
        max_score,
        wt_info,
        ignore_wt=False,
    ):
        import matplotlib

        matplotlib.use('Agg')

        from REvoDesign.common.MutantVisualizer import MutantVisualizer

        visualizer = MutantVisualizer(molecule, chain_id)
        alphabet = self.gremlin_tool.alphabet
        visualizer.group_name = '_vs_'.join(
            [wt.replace('_', '') for wt in wt_info[-3:-1]]
        )
        if self.current_gremlin_co_evoving_pair_group_id:
            self.last_gremlin_co_evoving_pair_group_id = (
                self.current_gremlin_co_evoving_pair_group_id
            )

        self.current_gremlin_co_evoving_pair_group_id = visualizer.group_name

        logging.debug(f'Received col {col} and row {row}')

        # aa from clicked button, mutant
        WT_A = alphabet[col]
        WT_B = alphabet[row]

        score = matrix[col][row]
        [i, j, i_aa, j_aa, zscore] = wt_info

        # aa from wt
        res_I = i_aa.split('_')[0]  # in column
        res_J = j_aa.split('_')[0]  # in row

        _mutant = []

        if self.current_gremlin_co_evoving_pair_mutant_id:
            self.last_gremlin_co_evoving_pair_mutant_id = (
                self.current_gremlin_co_evoving_pair_mutant_id
            )

        for mut, idx, wt in zip([WT_A, WT_B], [j + 1, i + 1], [res_I, res_J]):
            _ = f'{chain_id}{wt}{idx}{mut}'
            if wt == mut and ignore_wt:
                logging.debug(f'Ignore WT to WT mutagenese {_}')

            elif mut == '-':
                logging.info(f'Igore deletion {_}')
            else:
                logging.debug(f'Adding mutagenesis {_}')
                _mutant.append(_)

        _mutant.append(f'{score:.3f}')

        mutant = '_'.join(_mutant)

        if not _mutant:
            logging.info(
                'No mutagenesis will be performed since the picked pair is a wt-wt pair'
            )
            return

        elif mutant in cmd.get_names(
            type='nongroup_objects',
            enabled_only=0,
        ):
            logging.info(
                f'Picked mutant: {mutant} ( {score} ) already exists. Do nothing.'
            )
        else:
            logging.info(f'Picked mutant: {mutant} ( {score} )')

            color = get_color('bwr_r', score, min_score, max_score)

            logging.info(f" Visualizing {mutant} {score}: {color}")
            visualizer.create_mutagenesis_objects(mutant, color)
            cmd.hide('everything', 'hydrogens and polymer.protein')
            cmd.hide('cartoon', mutant)

        self.current_gremlin_co_evoving_pair_mutant_id = mutant
        self.activate_focused_interaction()
