import asyncio
import sys, os
import time
from pymol import cmd

from pymol.Qt import QtCore, QtGui, QtWidgets

# using partial module to reduce duplicate code.
from functools import partial
import absl.logging as logging
import traceback


logging.set_verbosity(logging.DEBUG)
logging.info(f'REvoDesign is installed in {os.path.dirname(__file__)}')

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
    dirname_does_exist,
    filepath_does_exists,
    extract_archive,
    generate_strong_password,
    run_worker_thread_with_progress,
    get_color,
    cmap_reverser,
    rescale_number,
)

from REvoDesign.tools.customized_widgets import (
    getExistingDirectory,
    set_widget_value,
    QbuttonMatrix,
    proceed_with_comfirm_msg_box,
    getOpenFileNameWithExt,
    create_cmap_icon,
)


from REvoDesign.tools.pymol_utils import (
    fetch_exclusion_expressions,
    is_empty_session,
    find_all_protein_chain_ids_in_protein,
    find_design_molecules,
    find_small_molecules_in_protein,
    get_molecule_sequence,
    make_temperal_input_pdb,
    is_a_REvoDesign_session,
    any_posision_has_been_selected,
    PYMOL_VERSION,
)

from REvoDesign.tools.mutant_tools import (
    existed_mutant_tree,
    extract_mutant_from_pymol_object,
    extract_mutants_from_mutant_id,
)

from REvoDesign.common.MultiMutantDesigner import MultiMutantDesigner


class REvoDesignPlugin:
    def __init__(
        self,
    ):
        # global reference to avoid garbage collection of our dialog
        self.window = None

        self.RUN_DIR = os.path.abspath(os.path.dirname(__file__))
        self.PWD = os.getcwd()

        self.ui_file = os.path.join(self.RUN_DIR, 'UI', 'REvoDesign-PyMOL.ui')
        self.design_molecule = ''
        self.design_chain_id = ''
        self.design_sequence = ''

        self.mutant_tree_pssm = MutantTree({})
        self.mutant_tree_pssm_selected = MutantTree({})
        self.mutant_tree_coevolved = MutantTree({})

        self.gremlin_tool = None
        self.gremlin_external_scorer = None

        from REvoDesign.clients.PSSM_GREMLIN_client import (
            PSSMGremlinCalculator,
        )

        self.pssm_gremlin_calculator = PSSMGremlinCalculator()

        self.multi_mutagenesis_designer = None

        try:
            # if QtWebsockets is available, teamwork is activated.
            from PyQt5 import QtWebSockets

            self.teamwork_enabled = True
        except ImportError:
            logging.warning(
                f'Teamwork is disabled. Please install the related requirements.'
            )
            traceback.print_exc()
            self.teamwork_enabled = False

    def set_working_directory(self):
        self.PWD = getExistingDirectory()
        os.chdir(self.PWD)

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

        from REvoDesign.tools.customized_widgets import set_window_font

        set_window_font(main_window)

        from REvoDesign.common.magic_numbers import (
            DEFAULT_CLUSTER_SCORE_MTX,
            DEFAULT_PROFILE_TYPE,
            DEFAULT_PROFILE_TYPE_GROUP,
        )

        from REvoDesign.external_designer import EXTERNAL_DESIGNERS

        # Set up Menu

        self.ui.actionSet_Working_Directory.triggered.connect(
            self.set_working_directory
        )

        self.ui.actionDebug.triggered.connect(
            partial(logging.set_verbosity, logging.DEBUG)
        )

        self.ui.actionWarning.triggered.connect(
            partial(logging.set_verbosity, logging.WARNING)
        )

        self.ui.actionInfo.triggered.connect(
            partial(logging.set_verbosity, logging.INFO)
        )

        if self.teamwork_enabled:
            from REvoDesign.clients.QtSocketConnector import (
                REvoDesignWebSocketServer,
                REvoDesignWebSocketClient,
            )

            self.ws_server = REvoDesignWebSocketServer()
            self.ws_client = REvoDesignWebSocketClient()
        else:
            self.ws_server = None
            self.ws_client = None
            # hide tab_socket if websockets is not available.
            self.ui.tabWidget.setTabVisible(7, False)

        # Set up general input
        self.ui.comboBox_chain_id.currentIndexChanged.connect(
            partial(
                self.set_design_sequence,
                self.ui.comboBox_design_molecule,
                self.ui.comboBox_chain_id,
            )
        )

        # read session from PyMOL. If it is empty, load one.
        self.ui.actionCheck_PyMOL_session.triggered.connect(
            partial(
                self.reload_molecule_info,
                self.ui.comboBox_design_molecule,
            )
        )

        # Update chain id
        self.ui.comboBox_design_molecule.currentIndexChanged.connect(
            partial(
                self.update_chain_id,
                self.ui.comboBox_design_molecule,
                self.ui.comboBox_chain_id,
            )
        )

        # set up nproc
        set_widget_value(self.ui.spinBox_nproc, (1, os.cpu_count()))
        set_widget_value(self.ui.spinBox_nproc, os.cpu_count())

        # color map
        import matplotlib

        set_widget_value(
            self.ui.comboBox_cmap,
            {
                _cmap: QtGui.QIcon(create_cmap_icon(cmap=_cmap))
                for _cmap in matplotlib.colormaps()
            },
        )
        set_widget_value(self.ui.comboBox_cmap, 'bwr_r')

        # Tab Client
        self.ui.comboBox_chain_id.currentIndexChanged.connect(
            partial(
                self.setup_pssm_gremlin_calculator,
            )
        )

        self.pssm_gremlin_calculator.setup_url(
            self.ui.lineEdit_pssm_gremlin_url,
            self.ui.lineEdit_pssm_gremlin_user,
            self.ui.lineEdit_pssm_gremlin_passwd,
        )

        self.ui.lineEdit_pssm_gremlin_url.textChanged.connect(
            partial(
                self.pssm_gremlin_calculator.setup_url,
                self.ui.lineEdit_pssm_gremlin_url,
                self.ui.lineEdit_pssm_gremlin_user,
                self.ui.lineEdit_pssm_gremlin_passwd,
            )
        )
        self.ui.lineEdit_pssm_gremlin_user.textChanged.connect(
            partial(
                self.pssm_gremlin_calculator.setup_url,
                self.ui.lineEdit_pssm_gremlin_url,
                self.ui.lineEdit_pssm_gremlin_user,
                self.ui.lineEdit_pssm_gremlin_passwd,
            )
        )

        self.ui.lineEdit_pssm_gremlin_passwd.textChanged.connect(
            partial(
                self.pssm_gremlin_calculator.setup_url,
                self.ui.lineEdit_pssm_gremlin_url,
                self.ui.lineEdit_pssm_gremlin_user,
                self.ui.lineEdit_pssm_gremlin_passwd,
            )
        )

        self.ui.pushButton_submit_pssm_gremlin_job.clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='submit',
                progress_bar=self.ui.progressBar,
            )
        )

        self.ui.pushButton_cancel_pssm_gremlin_job.clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='cancel',
                progress_bar=self.ui.progressBar,
            )
        )

        self.ui.pushButton_download_pssm_gremlin_job.clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='download',
                progress_bar=self.ui.progressBar,
            )
        )

        # Set up general arguments
        # Tab `Determine`
        self.ui.pushButton_open_output_pse_pocket.clicked.connect(
            partial(
                self.save_as_a_session,
                self.ui.lineEdit_output_pse_pocket,
            )
        )

        self.ui.pushButton_open_output_pse_surface.clicked.connect(
            partial(
                self.save_as_a_session,
                self.ui.lineEdit_output_pse_surface,
            )
        )

        self.ui.pushButton_run_surface_refresh.clicked.connect(
            self.update_surface_exclusion
        )

        self.ui.lineEdit_output_pse_surface.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [self.ui.lineEdit_output_pse_surface],
                [
                    self.ui.pushButton_run_surface_detection,
                ],
            )
        )

        self.ui.lineEdit_output_pse_pocket.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [self.ui.lineEdit_output_pse_pocket],
                [
                    self.ui.pushButton_run_pocket_detection,
                ],
            )
        )

        self.ui.comboBox_design_molecule.currentIndexChanged.connect(
            partial(
                self.reload_determine_tab_setup,
                self.ui.comboBox_ligand_sel,
                self.ui.comboBox_cofactor_sel,
            )
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

        # Tab `Mutate`
        self.ui.pushButton_open_output_pse_mutate.clicked.connect(
            partial(
                self.save_as_a_session,
                self.ui.lineEdit_output_pse_mutate,
            )
        )

        self.ui.pushButton_open_customized_indices.clicked.connect(
            partial(
                self.open_input_filepath,
                self.ui.lineEdit_input_customized_indices,
                [TXT_FileExt, AnyFileExt],
            )
        )

        self.ui.pushButton_open_input_csv.clicked.connect(
            partial(
                self.open_input_filepath,
                self.ui.lineEdit_input_csv,
                [PSSM_FileExt, AnyFileExt, CompressedFileExt],
            )
        )

        set_widget_value(
            self.ui.comboBox_profile_type,
            DEFAULT_PROFILE_TYPE_GROUP + list(EXTERNAL_DESIGNERS.keys()),
        )
        set_widget_value(self.ui.comboBox_profile_type, DEFAULT_PROFILE_TYPE)

        self.ui.lineEdit_input_csv.textChanged.connect(
            partial(
                self.determine_profile_format,
                self.ui.lineEdit_input_csv,
                self.ui.comboBox_profile_type,
            )
        )

        self.ui.lineEdit_output_pse_mutate.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_output_pse_mutate,
                ],
                [
                    self.ui.pushButton_run_PSSM_to_pse,
                ],
            )
        )

        self.ui.pushButton_run_PSSM_to_pse.clicked.connect(
            self.run_mutant_loading_from_profile
        )

        # Tab `Evaluate`
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
                self.ui.pushButton_previous_mutant,
                self.ui.pushButton_next_mutant,
                self.ui.pushButton_reject_this_mutant,
                self.ui.pushButton_accept_this_mutant,
                self.ui.lcdNumber_total_mutant,
                self.ui.lcdNumber_selected_mutant,
                self.ui.lineEdit_output_mut_table,
                self.ui.progressBar,
                self.ui.comboBox_group_ids,
                self.ui.checkBox_show_wt,
            )
        )

        self.ui.pushButton_goto_best_hit_in_group.clicked.connect(
            partial(
                self.jump_to_the_best_mutant,
                self.ui.comboBox_group_ids,
                self.ui.comboBox_mutant_ids,
                self.ui.checkBox_reverse_mutant_effect_2,
            )
        )

        self.ui.pushButton_load_mutant_choice_checkpoint.clicked.connect(
            partial(
                self.recover_mutant_choices_from_checkpoint,
                self.ui.lcdNumber_selected_mutant,
            )
        )

        self.ui.comboBox_group_ids.currentTextChanged.connect(
            partial(
                self.jump_to_branch,
                self.ui.comboBox_group_ids,
                self.ui.comboBox_mutant_ids,
                self.ui.progressBar,
            )
        )

        self.ui.comboBox_mutant_ids.currentTextChanged.connect(
            partial(
                self.jump_to_a_mutant,
                self.ui.comboBox_group_ids,
                self.ui.comboBox_mutant_ids,
                self.ui.checkBox_show_wt,
                self.ui.progressBar,
            )
        )

        self.ui.pushButton_choose_lucky_mutant.clicked.connect(
            partial(
                self.find_all_best_mutants,
                self.ui.comboBox_group_ids,
                self.ui.comboBox_mutant_ids,
                self.ui.checkBox_reverse_mutant_effect_2,
                self.ui.lcdNumber_selected_mutant,
            )
        )

        # Tab `Cluster`

        self.ui.pushButton_open_mut_table_2.clicked.connect(
            partial(
                self.open_mutant_table, self.ui.lineEdit_input_mut_table, 'r'
            )
        )

        from Bio.Align import substitution_matrices

        set_widget_value(
            self.ui.comboBox_cluster_matrix,
            [
                mtx
                for mtx in os.listdir(
                    os.path.join(substitution_matrices.__path__[0], 'data')
                )
            ],
        )
        set_widget_value(
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
        self.ui.lineEdit_output_pse_visualize.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_output_pse_visualize,
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
                    self.ui.pushButton_reduce_this_session,
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

        set_widget_value(
            self.ui.comboBox_profile_type_2,
            DEFAULT_PROFILE_TYPE_GROUP + list(EXTERNAL_DESIGNERS.keys()),
        )
        set_widget_value(self.ui.comboBox_profile_type_2, DEFAULT_PROFILE_TYPE)

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

        self.ui.pushButton_open_output_pse_visualize.clicked.connect(
            partial(
                self.save_as_a_session,
                self.ui.lineEdit_output_pse_visualize,
            )
        )

        set_widget_value(self.ui.comboBox_best_leaf, 'best_leaf')
        set_widget_value(self.ui.comboBox_totalscore, 'totalscore')

        self.ui.pushButton_run_visualizing.clicked.connect(
            self.visualize_mutants
        )

        self.ui.pushButton_reduce_this_session.clicked.connect(
            partial(
                self.reduce_current_session,
                session=None,
                reduce_disabled=True,
                overwrite=False,
            )
        )

        # Multi-Design
        self.ui.lineEdit_multi_design_mutant_table.textChanged.connect(
            partial(
                self.release_run_button_if_lineEdit_fp_is_valid,
                [
                    self.ui.lineEdit_multi_design_mutant_table,
                ],
                [
                    self.ui.pushButton_multi_design_export_mutants_from_table,
                    self.ui.pushButton_run_multi_design,
                ],
            )
        )

        self.ui.pushButton_open_mut_table_csv_2.clicked.connect(
            partial(
                self.open_mutant_table,
                self.ui.lineEdit_multi_design_mutant_table,
                'w',
            )
        )

        self.ui.pushButton_multi_design_initialize.clicked.connect(
            self.multi_mutagenesis_design_initialize
        )

        self.ui.pushButton_multi_design_start_new_design.clicked.connect(
            self.multi_mutagenesis_design_start
        )

        self.ui.pushButton_multi_design_left.clicked.connect(
            self.multi_mutagenesis_design_undo_picking
        )

        self.ui.pushButton_multi_design_right.clicked.connect(
            self.multi_mutagenesis_design_pick_next_mut
        )

        self.ui.pushButton_multi_design_end_this_design.clicked.connect(
            self.multi_mutagenesis_design_stop_design
        )

        self.ui.pushButton_multi_design_export_mutants_from_table.clicked.connect(
            self.multi_mutagenesis_design_save_design
        )

        self.ui.pushButton_run_multi_design.clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_auto,
                progress_bar=self.ui.progressBar,
            )
        )

        # Tab Interact
        self.ui.pushButton_open_gremlin_mtx.clicked.connect(
            partial(
                self.open_input_filepath,
                self.ui.lineEdit_input_gremlin_mtx,
                [PickleObjectFileExt, AnyFileExt],
            )
        )

        self.ui.pushButton_reinitialize_interact.clicked.connect(
            self.load_gremlin_mrf
        )
        self.ui.pushButton_run_interact_scan.clicked.connect(
            self.run_gremlin_tool
        )

        self.ui.pushButton_open_save_mutant_table.clicked.connect(
            partial(
                self.open_mutant_table,
                self.ui.lineEdit_output_mutant_table,
                'w',
            )
        )

        self.ui.pushButton_interact_reject.clicked.connect(
            self.coevoled_mutant_decision, False
        )
        self.ui.pushButton_interact_accept.clicked.connect(
            self.coevoled_mutant_decision, True
        )
        from REvoDesign.external_designer import EXTERNAL_DESIGNERS

        set_widget_value(
            self.ui.comboBox_external_scorer,
            [''] + list(EXTERNAL_DESIGNERS.keys()),
        )

        self.generate_ws_server_key(self.ui.lineEdit_ws_server_key)

        self.ui.pushButton_ws_generate_randomized_key.clicked.connect(
            partial(
                self.generate_ws_server_key, self.ui.lineEdit_ws_server_key
            )
        )

        # Connect the partial function to the stateChanged signal
        self.ui.checkBox_ws_server_mode.stateChanged.connect(
            self.toggle_ws_server_mode
        )

        self.ui.pushButton_ws_connect_to_server.clicked.connect(
            partial(self.toggle_ws_client_connection, True)
        )

        self.ui.pushButton_ws_disconnect_from_server.clicked.connect(
            partial(self.toggle_ws_client_connection, False)
        )

        self.ui.checkBox_ws_broadcast_view.stateChanged.connect(
            self.update_ws_server_view_update_options
        )
        self.ui.doubleSpinBox_ws_view_broadcast_interval.valueChanged.connect(
            self.update_ws_server_view_update_options
        )

        self.ui.checkBox_ws_recieve_view_broadcast.stateChanged.connect(
            self.update_ws_client_view_update_options
        )

        return main_window

    def set_design_sequence(
        self,
        comboBox_design_molecule: QtWidgets.QComboBox,
        comboBox_chain_id: QtWidgets.QComboBox,
    ):
        design_molecule = comboBox_design_molecule.currentText()
        design_chain = comboBox_chain_id.currentText()

        if design_molecule and design_chain:
            self.design_molecule = design_molecule
            self.design_chain_id = design_chain
            self.design_sequence = get_molecule_sequence(
                molecule=self.design_molecule,
                chain_id=self.design_chain_id,
                keep_missing=True,
            )

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
                # Ask whether to overide
                confirmed = proceed_with_comfirm_msg_box(
                    title="Extract Archive",
                    description=f"The selected file '{os.path.basename(filename)}' is a compressed archive. Do you want to extract it?",
                )

                if confirmed:
                    # Extract the archive and browse the extracted file
                    extracted_path = self.flatten_compressed_files(filename)
                    return self.browse_filename(mode, exts=exts)
                else:
                    # Keep the previously selected filename and return it
                    return filename

        if filename:
            return filename

    # A universal and versatile function for input file path browsing.
    def open_input_filepath(self, lineEdit_input, exts=[AnyFileExt]):
        input_fn = self.browse_filename(mode='r', exts=exts)
        if input_fn:
            set_widget_value(lineEdit_input, input_fn)
            return input_fn

    def reload_molecule_info(self, comboBox_molecule):
        import tempfile

        self.temperal_session = tempfile.mktemp(suffix=".pse")

        if not is_empty_session():
            cmd.save(self.temperal_session)
            cmd.reinitialize()
            cmd.load(self.temperal_session)
        else:
            logging.warning(
                f'Current session is empty! \n \
                            Please load one PDB/PSE/PZE!'
            )
            new_session_file = self.browse_filename(
                mode='r', exts=[SessionFileExt, PDB_FileExt, AnyFileExt]
            )
            if not new_session_file:
                logging.error(
                    f'Abored recognizing sessions from input {new_session_file}.'
                )
                return
            elif not os.path.exists(new_session_file):
                logging.error(f'File not exist: {new_session_file}.')
                return
            else:
                cmd.reinitialize()
                cmd.load(new_session_file)
                cmd.save(self.temperal_session)

        set_widget_value(comboBox_molecule, find_design_molecules)

    def save_as_a_session(self, lineEdit_structure_session):
        output_pse_fn = self.browse_filename(
            mode='w', exts=[SessionFileExt, AnyFileExt]
        )

        if output_pse_fn and os.path.exists(os.path.dirname(output_pse_fn)):
            logging.info(f"Output file is set as {output_pse_fn}")
            set_widget_value(lineEdit_structure_session, output_pse_fn)
        else:
            logging.warning(f"Invalid output path: {output_pse_fn}.")

    def release_run_button_if_lineEdit_fp_is_valid(
        self, lineEdits_fp, buttons_to_release
    ):
        button_unlocked = True

        for fp in lineEdits_fp:
            _fp = fp.text()
            logging.info(f'Checking file path: {_fp}')
            if not dirname_does_exist(_fp):
                logging.warning(
                    f'The parent dirname of `{_fp}` is not valid. Keep design buttoms locked!'
                )
                button_unlocked = False
                return
            else:
                if not filepath_does_exists(_fp):
                    logging.warning(f'The file `{_fp}` is not valid.')
                else:
                    logging.info(f'The file `{_fp}` is valid.')

        if button_unlocked:
            for button in buttons_to_release:
                button.setEnabled(True)
        else:
            for button in buttons_to_release:
                button.setEnabled(False)

    def update_chain_id(self, comboBox_molecule, comboBox_chain_id):
        molecule = comboBox_molecule.currentText()
        if not molecule:
            logging.warning(f'No available designable molecule!')
            return
        chain_ids = find_all_protein_chain_ids_in_protein(molecule)
        if chain_ids:
            set_widget_value(comboBox_chain_id, chain_ids)
            set_widget_value(comboBox_chain_id, chain_ids[0])

    def open_mutant_table(self, lineEdit_mutant_table, mode='r'):
        if mode == 'r':
            input_mut_txt_fn = self.open_input_filepath(
                lineEdit_mutant_table,
                [MutableFileExt, AnyFileExt, CompressedFileExt],
            )
            if input_mut_txt_fn:
                set_widget_value(lineEdit_mutant_table, input_mut_txt_fn)
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
                set_widget_value(lineEdit_mutant_table, output_mut_txt_fn)
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

        set_widget_value(comboBox_profile_format, profile_format)

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
                [
                    extract_mutant_from_pymol_object(
                        pymol_object=mt, sequence=self.design_sequence
                    ).get_mutant_id()
                    for mt in mutants_to_save
                ],
            )

        else:
            logging.info(f'Mutant table is created at {output_mut_txt_fn}')
            self.write_input_mutant_table(
                output_mut_txt_fn,
                [
                    extract_mutant_from_pymol_object(
                        pymol_object=mt, sequence=self.design_sequence
                    ).get_mutant_id()
                    for mt in mutants_to_save
                ],
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
        # rocked_view=(cmd.get('rock')=='on')
        cmd.set('rock', checkBox_rock_pymol.isChecked())

    def center_design_area(self, mutant_id):
        if self.mutant_tree_pssm and mutant_id:
            logging.debug(f'Centering design area: {mutant_id}')
            cmd.center(mutant_id)
        else:
            logging.debug(f'Giving up centering design area: {mutant_id}')

    def find_session_path(self):
        session_path = cmd.get('session_file')

        if not session_path:
            logging.warning(
                'Session not found, please use a new session path to save.'
            )
            return self.browse_filename(mode='w', exts=[SessionFileExt])

        if not os.path.exists(session_path):
            logging.warning(
                'Invalid session file path, please use a new session path to save.'
            )
            return self.browse_filename(mode='w', exts=[SessionFileExt])

        if os.path.basename(session_path).startswith(
            'tmp'
        ) and session_path.endswith('.pse'):
            logging.warning(
                f'Found temperal session path: {session_path}, please use a new session path to save.'
            )
            return self.browse_filename(mode='w', exts=[SessionFileExt])

        return session_path

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

    # Tab Client
    def setup_pssm_gremlin_calculator(self):
        molecule = self.design_molecule
        chain_id = self.design_chain_id
        sequence = self.design_sequence

        if (not molecule) or (not chain_id) or (not sequence):
            return

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

    # Tab `Determine`

    def reload_determine_tab_setup(
        self,
        comboBox_ligand_sel,
        comboBox_cofactor_sel,
    ):
        # Setup pocket determination arguments
        small_molecules = find_small_molecules_in_protein(self.design_molecule)
        if small_molecules:
            set_widget_value(comboBox_ligand_sel, small_molecules)
            comboBox_ligand_sel.setCurrentIndex(len(small_molecules))

            set_widget_value(comboBox_cofactor_sel, small_molecules)

            if len(small_molecules) >= 2:
                comboBox_cofactor_sel.setCurrentIndex(len(small_molecules) - 1)
            else:
                comboBox_cofactor_sel.setCurrentIndex(0)

    def update_surface_exclusion(self):
        exclusion_list = fetch_exclusion_expressions()

        set_widget_value(self.ui.comboBox_surface_exclusion, exclusion_list)
        self.ui.comboBox_surface_exclusion.setCurrentIndex(
            0
        ) if exclusion_list else 0

    def run_chain_interface_detection(self):
        molecule = self.design_molecule
        radius = self.ui.doubleSpinBox_interface_cutoff.value()
        chain_ids = find_all_protein_chain_ids_in_protein(molecule)
        if not chain_ids or len(chain_ids) <= 1:
            return

        for chain_id in chain_ids:
            cmd.select(
                f'if_{chain_id}',
                f'({molecule} and c. {chain_id} ) and byres ({molecule} and polymer.protein and (not c. {chain_id})) around {radius} and polymer.protein',
            )

    def run_surface_detection(self):
        input_file = self.temperal_session
        output_file = self.ui.lineEdit_output_pse_surface.text()

        exclusion = self.ui.comboBox_surface_exclusion.currentText()
        cutoff = float(self.ui.doubleSpinBox_surface_cutoff.value())
        do_show_surf_CA = True

        from REvoDesign.structure.SurfaceFinder import SurfaceFinder

        surfacefinder = SurfaceFinder(
            input_file=input_file,
            output_file=output_file,
            molecule=self.design_molecule,
            chain_id=self.design_chain_id,
        )

        surfacefinder.cutoff = cutoff
        surfacefinder.exclude_residue_selection = exclusion
        surfacefinder.do_show_surf_CA = do_show_surf_CA

        surfacefinder.process_surface_residues()

    def run_pocket_detection(self):
        input_file = self.temperal_session
        output_file = self.ui.lineEdit_output_pse_pocket.text()
        ligand = self.ui.comboBox_ligand_sel.currentText()
        cofactor = self.ui.comboBox_cofactor_sel.currentText()
        ligand_radius = self.ui.doubleSpinBox_ligand_radius.value()
        cofactor_radius = self.ui.doubleSpinBox_cofactor_radius.value()

        from REvoDesign.structure.PocketSearcher import PocketSearcher

        pocketsearcher = PocketSearcher(
            input_file=input_file,
            output_file=output_file,
            molecule=self.design_molecule,
            ligand=ligand,
        )

        pocketsearcher.chain_id = self.design_chain_id

        pocketsearcher.ligand_radius = ligand_radius
        pocketsearcher.cofactor = cofactor
        pocketsearcher.cofactor_radius = cofactor_radius

        pocketsearcher.save_dir = f'{self.PWD}/pockets/'
        pocketsearcher.search_pockets()

    # Tab `Mutate`

    def run_mutant_loading_from_profile(self):
        self.ui.pushButton_run_PSSM_to_pse.setEnabled(False)

        try:
            design_profile = self.ui.lineEdit_input_csv.text()
            design_profile_format = self.ui.comboBox_profile_type.currentText()
            preffered = self.ui.lineEdit_preffer_substitution.text().upper()
            rejected = self.ui.lineEdit_reject_substitution.text().upper()

            temperature = self.ui.doubleSpinBox_designer_temperature.value()
            num_designs = self.ui.spinBox_designer_num_samples.value()
            batch = self.ui.spinBox_designer_batch.value()
            homooligomeric = (
                self.ui.checkBox_designer_homooligomeric.isChecked()
            )
            deduplicate_designs = (
                self.ui.checkBox_deduplicate_designs.isChecked()
            )
            randomized_sample = (
                self.ui.checkBox_randomized_sampling.isChecked()
            )
            randomized_sample_num = self.ui.spinBox_randomized_sampling.value()

            design_case = self.ui.lineEdit_design_case.text()
            custom_indices_fp = (
                self.ui.lineEdit_input_customized_indices.text()
            )
            cutoff = [
                float(self.ui.lineEdit_score_minima.text()),
                float(self.ui.lineEdit_score_maxima.text()),
            ]
            reversed_mutant_effect = (
                self.ui.checkBox_reverse_mutant_effect.isChecked()
            )
            output_pse = self.ui.lineEdit_output_pse_mutate.text()
            nproc = self.ui.spinBox_nproc.value()

            cmap = cmap_reverser(
                cmap=self.ui.comboBox_cmap.currentText(),
                reverse=reversed_mutant_effect,
            )

            progressbar = self.ui.progressBar

            if is_a_REvoDesign_session():
                logging.warning(
                    'Loading mutants into a REvoDesign session may trigger unexpected segmentation fault.\n'
                    'In order to keep the session\'s feature, you should always create seperate sessions according to '
                    'your dataset and merge them manually in PyMOL window.'
                )

            input_file = make_temperal_input_pdb(
                molecule=self.design_molecule,
                format='pdb',
                wd=os.path.join(self.PWD, 'temperal_pdb'),
                reload=False,
            )

            from REvoDesign.phylogenetics.REvoDesigner import REvoDesigner

            design = REvoDesigner(design_profile)
            design.input_pse = input_file
            design.output_pse = output_pse
            design.input_profile_format = design_profile_format

            design.molecule = self.design_molecule
            design.chain_id = self.design_chain_id
            design.sequence = self.design_sequence
            design.pwd = self.PWD
            design.design_case = design_case

            design.external_designer_temperature = temperature
            design.external_designer_num_samples = num_designs
            design.batch = batch
            design.homooligomeric = homooligomeric
            design.deduplicate_designs = deduplicate_designs
            design.randomized_sample = randomized_sample
            design.randomized_sample_num = randomized_sample_num

            design.preffered_substitutions = preffered
            design.reject_aa = rejected
            design.nproc = nproc
            design.cmap = cmap
            design.create_full_pdb = False

            from REvoDesign.external_designer import EXTERNAL_DESIGNERS

            if design_profile_format in EXTERNAL_DESIGNERS.keys():
                design.design_protein_using_external_designer(
                    custom_indices_fp=custom_indices_fp,
                    progress_bar=progressbar,
                )
            else:
                (
                    mutation_json_fp,
                    mutation_png_fp,
                ) = design.setup_profile_design(
                    custom_indices_fp=custom_indices_fp,
                    cutoff=cutoff,
                )

                design.load_mutants_to_pymol_session(
                    mutant_json=mutation_json_fp,
                    progress_bar=progressbar,
                )

            assert design.output_pse and dirname_does_exist(
                design.output_pse
            ), f'No output PyMOL session is created.'

            cmd.load(design.output_pse, partial=2)

            cmd.center(self.design_molecule)
            cmd.set('surface_color', 'gray70')
            cmd.set('cartoon_color', 'gray70')
            cmd.set('surface_cavity_mode', 4)
            cmd.set('transparency', 0.6)
            cmd.set(
                'cartoon_cylindrical_helices',
            )
            cmd.set('cartoon_transparency', 0.3)
            cmd.save(output_pse)

        except Exception:
            traceback.print_exc()
        finally:
            self.ui.pushButton_run_PSSM_to_pse.setEnabled(True)

        if (
            self.ws_server
            and self.ws_server.is_running
            and design.mutant_tree
            and not design.mutant_tree.empty
        ):
            asyncio.run(
                self.ws_broadcast_from_server(
                    data=design.mutant_tree,
                    data_type='MutantTree',
                )
            )

    # Tab `Evaluate`
    def activate_focused(self, checkBox_show_wt):
        molecule = self.design_molecule
        chain_id = self.design_chain_id

        logging.debug(
            f'Current Mutant ID: {self.mutant_tree_pssm.current_mutant_id}'
        )

        if molecule and chain_id:
            mut_obj = extract_mutant_from_pymol_object(
                pymol_object=self.mutant_tree_pssm.current_mutant_id,
                sequence=self.design_sequence,
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

        all_enabled_mutant_ids = cmd.get_names('nongroup_objects', 1)

        all_enabled_mutants_in_current_group = [
            mutant
            for mutant in cmd.get_object_list(
                f'({self.mutant_tree_pssm.current_branch_id})'
            )
            if mutant != self.mutant_tree_pssm.current_mutant_id
            and mutant in all_enabled_mutant_ids
        ]

        for mutant in all_enabled_mutants_in_current_group:
            cmd.disable(mutant)

        other_opened_group = [
            group
            for group in cmd.get_names('group_objects', 1)
            if group != self.mutant_tree_pssm.current_branch_id
        ]

        for group_id in other_opened_group:
            cmd.disable(group_id)
            cmd.group(group_id, action='close')

        # expand group object if activated
        if self.mutant_tree_pssm.current_branch_id:
            cmd.enable(self.mutant_tree_pssm.current_branch_id)
            cmd.group(self.mutant_tree_pssm.current_branch_id, action='open')

        self.center_design_area(self.mutant_tree_pssm.current_mutant_id)

    def mutant_decision(self, decision_to_accept: bool):
        lcdNumber_selected_mutant = self.ui.lcdNumber_selected_mutant
        if not self.is_this_pymol_object_a_mutant(
            self.mutant_tree_pssm.current_mutant_id
        ):
            logging.warning(
                f'Ingoring non mutant {self.mutant_tree_pssm.current_mutant_id}'
            )
            return

        logging.debug(
            f'{"Accepting" if decision_to_accept else "Rejecting"} mutant {self.mutant_tree_pssm.current_mutant_id}'
        )

        if decision_to_accept:
            self.mutant_tree_pssm_selected.add_mutant_to_branch(
                branch=self.mutant_tree_pssm.current_branch_id,
                mutant=self.mutant_tree_pssm.current_mutant_id,
                mutant_info=self.mutant_tree_pssm.mutant_tree[
                    self.mutant_tree_pssm.current_branch_id
                ][self.mutant_tree_pssm.current_mutant_id],
            )

        else:
            if (
                self.mutant_tree_pssm.current_branch_id
                not in self.mutant_tree_pssm_selected.all_mutant_branch_ids
            ):
                logging.warning(
                    f'{self.mutant_tree_pssm.current_branch_id} does not exist. skipped'
                )
                return

            self.mutant_tree_pssm_selected.remove_mutant_from_branch(
                branch=self.mutant_tree_pssm.current_branch_id,
                mutant=self.mutant_tree_pssm.current_mutant_id,
            )

        set_widget_value(
            lcdNumber_selected_mutant,
            len(self.mutant_tree_pssm_selected.all_mutant_ids),
        )

        self.save_mutant_choices(
            self.ui.lineEdit_output_mut_table, self.mutant_tree_pssm_selected
        )

    def walk_mutant_groups(
        self,
        walk_to_next,
        progressBar_mutant_choosing,
        checkBox_show_wt,
    ):
        comboBox_group_ids = self.ui.comboBox_group_ids
        comboBox_mutant_ids = self.ui.comboBox_mutant_ids

        # self.mutant_tree_pssm.walk_the_mutants(walk_to_next_one=walk_to_next)

        (
            current_branch_id,
            current_mutant_id,
        ) = self.mutant_tree_pssm._walk_the_mutants(
            walk_to_next_one=walk_to_next
        )

        set_widget_value(
            progressBar_mutant_choosing,
            self.mutant_tree_pssm.get_mutant_index_in_all_mutants(
                current_mutant_id
            ),
        )

        # feedback on two comboboxes
        if comboBox_group_ids.currentText() != current_branch_id:
            set_widget_value(comboBox_group_ids, current_branch_id)
            set_widget_value(
                comboBox_mutant_ids,
                list(
                    self.mutant_tree_pssm.get_a_branch(
                        branch_id=self.mutant_tree_pssm.current_branch_id
                    ).keys()
                ),
            )

        if comboBox_mutant_ids.currentText() != current_mutant_id:
            set_widget_value(comboBox_mutant_ids, current_mutant_id)

        self.activate_focused(checkBox_show_wt)
        logging.info(
            f'Walked to the {"next" if walk_to_next else "previous"} mutant {current_mutant_id}.'
        )

    def jump_to_branch(
        self,
        comboBox_group_ids,
        comboBox_mutant_ids,
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
            set_widget_value(progressBar_mutant_choosing, progress)

            # Setting mutant ids to candidates box
            set_widget_value(
                comboBox_mutant_ids,
                list(
                    self.mutant_tree_pssm.get_a_branch(branch_id=branch).keys()
                ),
            )
            set_widget_value(
                comboBox_mutant_ids, self.mutant_tree_pssm.current_mutant_id
            )
            return

    # end of mutant switching machanism. This step will do focusing, centering, progress bar updating.
    def jump_to_a_mutant(
        self,
        comboBox_group_ids,
        comboBox_mutant_ids,
        checkBox_show_wt,
        progressBar_mutant_choosing,
    ):
        branch_id = comboBox_group_ids.currentText()
        mutant_id = comboBox_mutant_ids.currentText()

        if self.mutant_tree_pssm.empty:
            return

        if (not branch_id) or (not mutant_id):
            return

        if branch_id not in self.mutant_tree_pssm.all_mutant_branch_ids:
            return

        if mutant_id not in self.mutant_tree_pssm.get_a_branch(
            branch_id=branch_id
        ):
            logging.error(
                f'Mutant ID {branch_id} is not belong to this branch {self.mutant_tree_pssm.current_branch_id}.'
            )
            return

        if branch_id != self.mutant_tree_pssm.current_branch_id:
            self.mutant_tree_pssm.current_branch_id = branch_id

        logging.info(f'Jump to {mutant_id} as required.')
        self.mutant_tree_pssm.current_mutant_id = mutant_id

        self.activate_focused(checkBox_show_wt)

        # update progress bar
        progress = self.mutant_tree_pssm.get_mutant_index_in_all_mutants(
            self.mutant_tree_pssm.current_mutant_id
        )
        logging.info(
            f'Progressbar set to {progress}: {self.mutant_tree_pssm.current_mutant_id}'
        )
        set_widget_value(progressBar_mutant_choosing, progress)

    def jump_to_the_best_mutant(
        self,
        comboBox_group_ids,
        comboBox_mutant_ids,
        checkBox_reverse_mutant_effect,
    ):
        if self.mutant_tree_pssm.empty:
            return

        branch_id = comboBox_group_ids.currentText()

        best_mutant_id = (
            self.mutant_tree_pssm._jump_to_the_best_mutant_in_branch(
                branch_id=branch_id,
                reversed=checkBox_reverse_mutant_effect.isChecked(),
            )
        )
        logging.info(f'Jump to the best hit of {branch_id}: {best_mutant_id}')

        set_widget_value(comboBox_mutant_ids, best_mutant_id)

    def find_all_best_mutants(
        self,
        comboBox_group_ids,
        comboBox_mutant_ids,
        checkBox_reverse_mutant_effect,
        lcdNumber_selected_mutant,
    ):
        if self.mutant_tree_pssm.empty:
            logging.error(
                f'No available mutant tree. Please reinitialize it before picking mutants.'
            )
            return

        if not self.mutant_tree_pssm_selected.empty:
            logging.warning(
                f'Your current mutant selection will be overrided!'
            )

            # Ask whether to overide
            confirmed = proceed_with_comfirm_msg_box(
                title="Override existed mutant table choices?",
                description=f"You currently have existed mutant table choices, which shall be overriden by using `I'm lucky`. \n \
                    Are you really sure? ",
            )

            if not confirmed:
                logging.warning(f'Cancelled.')
                return

        original_branch_id = comboBox_group_ids.currentText()
        original_mutant_id = comboBox_mutant_ids.currentText()

        self.mutant_tree_pssm_selected = MutantTree({})

        for branch_id in self.mutant_tree_pssm.all_mutant_branch_ids:
            logging.info(f'Jump to {branch_id} as required.')

            set_widget_value(comboBox_group_ids, branch_id)

            best_mutant_id = (
                self.mutant_tree_pssm._jump_to_the_best_mutant_in_branch(
                    branch_id=branch_id,
                    reversed=checkBox_reverse_mutant_effect.isChecked(),
                )
            )
            logging.info(
                f'Jump to the best hit of {branch_id}: {best_mutant_id}'
            )
            set_widget_value(comboBox_mutant_ids, best_mutant_id)

            self.mutant_decision(decision_to_accept=True)
            logging.info(
                f'Best hit of {self.mutant_tree_pssm.current_mutant_id} accepted.'
            )
        # set back orignal values befor clicking this button
        set_widget_value(comboBox_group_ids, original_branch_id)
        set_widget_value(comboBox_mutant_ids, original_mutant_id)

        logging.info('Done.')

    # basic function that works for mutant_tree instantiation
    def is_this_pymol_object_a_mutant(self, mutant):
        _mutant_obj = extract_mutant_from_pymol_object(
            pymol_object=mutant, sequence=self.design_sequence
        )
        return _mutant_obj is not None

    def recover_mutant_choices_from_checkpoint(
        self, lcdNumber_selected_mutant
    ):
        mutant_choice_checkpoint_fn = self.browse_filename(
            mode='r', exts=[MutableFileExt, AnyFileExt]
        )

        if not mutant_choice_checkpoint_fn:
            logging.warning("Cancelled.")
            return

        if not os.path.exists(mutant_choice_checkpoint_fn):
            logging.warning(
                f"Invalid checkpoint file: {mutant_choice_checkpoint_fn}."
            )
            return

        mutants_from_checkpoint = (
            open(mutant_choice_checkpoint_fn, 'r').read().strip().split('\n')
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

        set_widget_value(
            lcdNumber_selected_mutant,
            len(self.mutant_tree_pssm_selected.all_mutant_ids),
        )

    def initialize_design_candidates(
        self,
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
        self.mutant_tree_pssm = existed_mutant_tree(
            sequence=self.design_sequence, enabled_only=0
        )
        if self.mutant_tree_pssm.empty:
            logging.error(f'This sesion may not contain an mutant tree.')
            return None

        self.mutant_tree_pssm_selected = MutantTree({})

        # if mutant tree is available, disable the input box for saving.

        lineEdit_output_mut_txt.setEnabled(not self.mutant_tree_pssm.empty)

        if not self.mutant_tree_pssm:
            logging.warning(
                'Could not initialize mutant tree! This session may not be a REvoDesign session!'
            )
            return

        # clean the view
        cmd.disable(' or '.join(self.mutant_tree_pssm.all_mutant_branch_ids))
        cmd.hide('sticks', ' or '.join(self.mutant_tree_pssm.all_mutant_ids))
        cmd.disable(' or '.join(self.mutant_tree_pssm.all_mutant_ids))

        set_widget_value(
            progressBar_mutant_choosing,
            [0, len(self.mutant_tree_pssm.all_mutant_ids)],
        )

        set_widget_value(
            comboBox_group_ids, self.mutant_tree_pssm.all_mutant_branch_ids
        )
        set_widget_value(
            comboBox_group_ids, self.mutant_tree_pssm.all_mutant_branch_ids[0]
        )

        self.activate_focused(checkBox_show_wt)

        # show the current branch and mutant
        cmd.enable(self.mutant_tree_pssm.current_mutant_id)
        cmd.enable(self.mutant_tree_pssm.current_branch_id)

        set_widget_value(
            lcdNumber_total_mutant, len(self.mutant_tree_pssm.all_mutant_ids)
        )
        set_widget_value(
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
            pushButton.setEnabled(bool(not self.mutant_tree_pssm.empty))

        pushButton_accept_this_mutant.clicked.connect(
            partial(self.mutant_decision, True)
        )
        pushButton_reject_this_mutant.clicked.connect(
            partial(self.mutant_decision, False)
        )

        pushButton_next_mutant.clicked.connect(
            partial(
                self.walk_mutant_groups,
                True,
                progressBar_mutant_choosing,
                checkBox_show_wt,
            )
        )

        pushButton_previous_mutant.clicked.connect(
            partial(
                self.walk_mutant_groups,
                False,
                progressBar_mutant_choosing,
                checkBox_show_wt,
            )
        )

    # combination and clustering
    def run_clustering(self):
        trigger_button = self.ui.pushButton_run_cluster

        # lazy module loading to fasten plugin initializing
        from REvoDesign.clusters.combine_positions import Combinations
        from REvoDesign.clusters.cluster_sequence import Clustering

        input_mutant_table = self.ui.lineEdit_input_mut_table.text()

        cluster_batch_size = self.ui.spinBox_cluster_batchsize.value()
        cluster_number = self.ui.spinBox_num_cluster.value()
        min_mut_num = self.ui.spinBox_num_mut_minimun.value()
        max_mut_num = self.ui.spinBox_num_mut_maximum.value()
        cluster_substitution_matrix = (
            self.ui.comboBox_cluster_matrix.currentText()
        )

        shuffle_variant = self.ui.checkBox_shuffle_clustering.isChecked()

        nproc = self.ui.spinBox_nproc.value()

        # output space
        plot_space = self.ui.stackedWidget
        progressbar = self.ui.progressBar

        input_fasta_file = (
            f'{self.PWD}/{self.design_molecule}_{self.design_chain_id}.fasta'
        )
        open(input_fasta_file, 'w').write(
            f'>{self.design_molecule}_{self.design_chain_id}\n{self.design_sequence}'
        )
        logging.info(f'Sequence file is saved as {input_fasta_file}')

        # output files
        cluster_outputs = {}
        trigger_button.setEnabled(False)

        try:
            for num_mut in range(min_mut_num, max_mut_num + 1):
                # combination
                combinations = Combinations()
                combinations.fastasequence = self.design_sequence
                combinations.chain_id = self.design_chain_id
                combinations.fastafile = input_fasta_file
                combinations.inputfile = input_mutant_table
                combinations.combi = num_mut
                combinations.path = self.PWD
                combinations.processors = nproc

                # expected design combination file

                combinations.run_combinations()
                expected_design_combinations = (
                    combinations.expected_output_fasta
                )

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
            set_widget_value(plot_space, cluster_imgs)

        finally:
            trigger_button.setEnabled(True)

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
                    set_widget_value(comboBox, mut_table_cols)

                # set default col value
                if len(mut_table_cols) > 1:
                    set_widget_value(comboBox_best_leaf, mut_table_cols[0])
                    set_widget_value(comboBox_totalscore, mut_table_cols[-1])

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
        self.visualizing_mutant_tree = existed_mutant_tree(
            sequence=self.design_sequence, enabled_only=1
        )

        logging.info(f'Saving mutant table to {mutant_table_fp} ...')

        self.save_mutant_choices(
            lineEdit_mutant_table_fp,
            self.visualizing_mutant_tree.all_mutant_ids,
        )

    def visualize_mutants(self):
        trigger_button = self.ui.pushButton_run_visualizing
        input_mut_table_csv = self.ui.lineEdit_input_mut_table_csv.text()

        output_pse = self.ui.lineEdit_output_pse_visualize.text()
        best_leaf = self.ui.comboBox_best_leaf.currentText()
        totalscore = self.ui.comboBox_totalscore.currentText()
        nproc = self.ui.spinBox_nproc.value()
        group_name = self.ui.lineEdit_group_name.text()

        use_global_scores = self.ui.checkBox_global_score_policy.isChecked()

        trigger_button.setEnabled(False)

        try:
            reversed_mutant_effect = (
                self.ui.checkBox_reverse_mutant_effect_3.isChecked()
            )
            cmap = cmap_reverser(
                cmap=self.ui.comboBox_cmap.currentText(),
                reverse=reversed_mutant_effect,
            )

            design_profile = self.ui.lineEdit_input_csv_2.text()
            design_profile_format = (
                self.ui.comboBox_profile_type_2.currentText()
            )

            progressBar_visualize_mutants = self.ui.progressBar

            from REvoDesign.common.MutantVisualizer import MutantVisualizer

            visualizer = MutantVisualizer(
                molecule=self.design_molecule,
                chain_id=self.design_chain_id,
            )
            visualizer.mutfile = input_mut_table_csv
            visualizer.input_session = make_temperal_input_pdb(
                molecule=self.design_molecule,
                wd=os.path.join(os.path.dirname(output_pse), 'temperal_pdb'),
                reload=False,
            )
            visualizer.nproc = nproc
            visualizer.parallel_run = nproc > 1
            visualizer.sequence = self.design_sequence

            visualizer.consider_global_score_from_profile = use_global_scores

            visualizer.profile_scoring_df = None
            visualizer.consider_global_score_from_profile = False

            visualizer.profile_scoring_df = visualizer.parse_profile(
                profile_fp=design_profile,
                profile_format=design_profile_format,
            )

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

            cmd.load(visualizer.save_session, partial=2)
            cmd.center(self.design_molecule)
            cmd.set('surface_color', 'gray70')
            cmd.set('cartoon_color', 'gray70')
            cmd.set('surface_cavity_mode', 4)
            cmd.set('transparency', 0.6)
            cmd.set(
                'cartoon_cylindrical_helices',
            )
            cmd.set('cartoon_transparency', 0.3)
            cmd.save(output_pse)

        except Exception:
            logging.error('Error while running the visualization: ')
            traceback.print_exc()

        finally:
            trigger_button.setEnabled(True)

        if (
            self.ws_server
            and self.ws_server.is_running
            and visualizer.mutant_tree
            and not visualizer.mutant_tree.empty
        ):
            asyncio.run(
                self.ws_broadcast_from_server(
                    data=visualizer.mutant_tree,
                    data_type='MutantTree',
                )
            )

    def reduce_current_session(
        self, session=None, reduce_disabled=False, overwrite=False
    ):
        if not session:
            session = self.find_session_path()

        if reduce_disabled:
            enabled_items = cmd.get_names('nongroup_objects', enabled_only=1)
            all_items = cmd.get_names('nongroup_objects', enabled_only=0)
            for item in all_items:
                if item not in enabled_items:
                    logging.warning(
                        f'Reducing item {item} from current session ...'
                    )
                    cmd.delete(item)
                    cmd.refresh()

        if os.path.exists(session):
            if not overwrite:
                # Ask whether to overide
                confirmed = proceed_with_comfirm_msg_box(
                    title="Override current session?",
                    description=f"Your current session will be overriden. \n \
                        Are you really sure? ",
                )

                if not confirmed:
                    session = self.browse_filename(
                        mode='w', exts=[SessionFileExt]
                    )

                if not session:
                    return

        cmd.save(filename=session)

    def multi_mutagenesis_design_initialize(self):
        self.multi_mutagenesis_designer = MultiMutantDesigner(
            molecule=self.design_molecule,
            chain_id=self.design_chain_id,
            sequence=self.design_sequence,
        )
        self.refresh_multi_mutagenesis_designer_parameters()

    def refresh_multi_mutagenesis_designer_parameters(self):
        if not self.multi_mutagenesis_designer:
            return
        spinBox_maximal_mutant_num = self.ui.spinBox_maximal_mutant_num
        doubleSpinBox_minmal_mutant_distance = (
            self.ui.doubleSpinBox_minmal_mutant_distance
        )
        checkBox_multi_design_bond_CA = self.ui.checkBox_multi_design_bond_CA
        checkBox_multi_design_check_sidechain_orientations = (
            self.ui.checkBox_multi_design_check_sidechain_orientations
        )
        comboBox_profile_type_2 = self.ui.comboBox_profile_type_2
        spinBox_maximal_multi_design_variant_num = (
            self.ui.spinBox_maximal_multi_design_variant_num
        )
        checkBox_multi_design_use_external_scorer = (
            self.ui.checkBox_multi_design_use_external_scorer
        )
        checkBox_multi_design_color_by_scores = (
            self.ui.checkBox_multi_design_color_by_scores
        )
        checkBox_reverse_mutant_effect_3 = (
            self.ui.checkBox_reverse_mutant_effect_3
        )

        self.multi_mutagenesis_designer.scorer = (
            comboBox_profile_type_2.currentText()
        )
        self.multi_mutagenesis_designer.total_design_cases = (
            spinBox_maximal_multi_design_variant_num.value()
        )

        self.multi_mutagenesis_designer.cmap = (
            self.ui.comboBox_cmap.currentText()
        )

        self.multi_mutagenesis_designer.maximal_mutant_num = (
            spinBox_maximal_mutant_num.value()
        )
        self.multi_mutagenesis_designer.minimal_distance = (
            doubleSpinBox_minmal_mutant_distance.value()
        )
        self.multi_mutagenesis_designer.bond_CA = (
            checkBox_multi_design_bond_CA.isChecked()
        )
        self.multi_mutagenesis_designer.use_sidechain_angle = (
            checkBox_multi_design_check_sidechain_orientations.isChecked()
        )
        self.multi_mutagenesis_designer.use_external_scorer = (
            checkBox_multi_design_use_external_scorer.isChecked()
        )
        self.multi_mutagenesis_designer.color_by_scores = (
            checkBox_multi_design_color_by_scores.isChecked()
        )
        self.multi_mutagenesis_designer.external_scorer_reversed_score = (
            checkBox_reverse_mutant_effect_3.isChecked()
        )

    def multi_mutagenesis_design_start(self):
        if not self.multi_mutagenesis_designer:
            logging.error('Multi design is not initialized.')
            return

        if self.multi_mutagenesis_designer.in_design_multi_design_case:
            logging.warning(
                f'Your current mutant multi-mutagenesis will be discarded!'
            )

            # Ask whether to overide
            confirmed = proceed_with_comfirm_msg_box(
                title="Discard in-design mutant choice?",
                description=f"You currently have uncompleted mutant choice, which shall be discarded. \n \
                    Are you really sure? ",
            )

            if not confirmed:
                logging.warning(f'Cancelled.')
                return
        self.refresh_multi_mutagenesis_designer_parameters()
        self.multi_mutagenesis_designer.start_new_design()

    def multi_mutagenesis_design_pick_next_mut(self):
        if not self.multi_mutagenesis_designer:
            logging.error('Multi design is not initialized.')
            return
        self.refresh_multi_mutagenesis_designer_parameters()
        self.multi_mutagenesis_designer.pick_next_mutant()

    def multi_mutagenesis_design_undo_picking(self):
        if not self.multi_mutagenesis_designer:
            logging.error('Multi design is not initialized.')
            return

        self.refresh_multi_mutagenesis_designer_parameters()
        self.multi_mutagenesis_designer.undo_previous_mutant()

    def multi_mutagenesis_design_stop_design(self):
        if not self.multi_mutagenesis_designer:
            logging.error('Multi design is not initialized.')
            return
        self.refresh_multi_mutagenesis_designer_parameters()
        if self.multi_mutagenesis_designer.in_design_multi_design_case:
            self.multi_mutagenesis_designer.new_design(continue_design=False)

    def multi_mutagenesis_design_save_design(self):
        if not self.multi_mutagenesis_designer:
            logging.error('Multi design is not initialized.')
            return
        self.refresh_multi_mutagenesis_designer_parameters()

        mut_table_csv = self.ui.lineEdit_multi_design_mutant_table.text()
        self.multi_mutagenesis_designer.export_designed_variant(
            save_mutant_table=mut_table_csv
        )

    def multi_mutagenesis_design_auto(self):
        trigger_button = self.ui.pushButton_run_multi_design
        self.refresh_multi_mutagenesis_designer_parameters()

        maximal_multi_design_variant_num = (
            self.multi_mutagenesis_designer.total_design_cases
        )
        maximal_mutant_num = self.multi_mutagenesis_designer.maximal_mutant_num

        # initialize
        self.multi_mutagenesis_design_initialize()
        if not self.multi_mutagenesis_designer:
            logging.error('Multi design failed in initializing.')
            return

        trigger_button.setEnabled(False)
        try:
            for i in range(maximal_multi_design_variant_num):
                self.multi_mutagenesis_design_start()
                # pick mutant until it reaches the required number
                for j in range(maximal_mutant_num):
                    self.multi_mutagenesis_design_pick_next_mut()
                self.multi_mutagenesis_design_stop_design()
            self.multi_mutagenesis_design_save_design()
        except Exception:
            traceback.print_exc()
        finally:
            trigger_button.setEnabled(True)

    # Tab Interact via GREMLIN
    def load_gremlin_mrf(
        self,
    ):
        trigger_button = self.ui.pushButton_reinitialize_interact
        from REvoDesign.phylogenetics.GREMLIN_Tools import GREMLIN_Tools

        trigger_button.setEnabled(False)

        try:
            gremlin_mrf_fp = self.ui.lineEdit_input_gremlin_mtx.text()

            topN_gremlin_candidates = self.ui.spinBox_gremlin_topN.value()

            if (not self.design_molecule) or (not self.design_chain_id):
                logging.error(
                    f'Molecule Info not complete. \n\tmolecule: {self.design_molecule}\n\tchain: {self.design_chain_id}.'
                )
                return

            if not os.path.exists(gremlin_mrf_fp):
                logging.error(
                    "Could not run GREMLIN tools. Please check your configuration"
                )
                return

            pushButton_run_interact_scan = self.ui.pushButton_run_interact_scan
            gridLayout_interact_pairs = self.ui.gridLayout_interact_pairs

            # reset design info
            lineEdit_current_pair_wt_score = (
                self.ui.lineEdit_current_pair_wt_score
            )
            lineEdit_current_pair_mut_score = (
                self.ui.lineEdit_current_pair_mut_score
            )
            lineEdit_current_pair = self.ui.lineEdit_current_pair
            lineEdit_current_pair_score = self.ui.lineEdit_current_pair_score

            for lineEdit in [
                lineEdit_current_pair,
                lineEdit_current_pair_score,
                lineEdit_current_pair_wt_score,
                lineEdit_current_pair_mut_score,
            ]:
                set_widget_value(lineEdit, '')

            progress_bar = self.ui.progressBar

            # Reinitialize Gremlin mutant tree
            self.mutant_tree_coevolved = MutantTree({})

            self.gremlin_tool = GREMLIN_Tools(molecule=self.design_molecule)

            self.gremlin_tool.sequence = self.design_sequence

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

            try:
                set_widget_value(gridLayout_interact_pairs, plot_mtx_fp)
            except AttributeError:
                logging.info(
                    f'Work Space is cleaned. Click once again to reinitialize. '
                )

        finally:
            trigger_button.setEnabled(True)

    def run_gremlin_tool(self):
        progress_bar = self.ui.progressBar
        max_interact_dist = self.ui.doubleSpinBox_max_interact_dist.value()

        self.plot_w_fps = {}

        if any_posision_has_been_selected():
            logging.info(f'One vs All mode.')
            self.gremlin_tool_a2a_mode = False
            resi = int(cmd.get_model('sele and n. CA').atom[0].resi)
            logging.info(f'{resi} is selected.')

            self.gremlin_workpath = os.path.join(
                self.PWD, 'gremlin_co_evolved_pairs', f'resi_{resi}'
            )
            os.makedirs(self.gremlin_workpath, exist_ok=True)
            self.gremlin_tool.pwd = self.gremlin_workpath

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

            self.gremlin_workpath = os.path.join(
                self.PWD, 'gremlin_co_evolved_pairs', 'all_vs_all'
            )
            os.makedirs(self.gremlin_workpath, exist_ok=True)
            self.gremlin_tool.pwd = self.gremlin_workpath

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

        ce_object_name = cmd.get_unused_name(
            f"ce_pairs_{self.design_molecule}_{self.design_chain_id}"
        )

        cmd.create(
            ce_object_name,
            f'{self.design_molecule} and c. {self.design_chain_id} and n. CA',
        )
        cmd.hide('cartoon', ce_object_name)
        cmd.hide('surface', ce_object_name)
        i_out_of_range = []
        for i, pair_resi in self.plot_w_fps.items():
            logging.debug(pair_resi)

            spatial_distance = cmd.get_distance(
                atom1=f'{self.design_molecule} and c. {self.design_chain_id} and i. {pair_resi[0][0]+1} and n. CA',
                atom2=f'{self.design_molecule} and c. {self.design_chain_id} and i. {pair_resi[0][1]+1} and n. CA',
            )
            cmd.bond(
                f'{ce_object_name} and c. {self.design_chain_id} and resi {pair_resi[0][0]+1} and n. CA',
                f'{ce_object_name} and c. {self.design_chain_id} and resi {pair_resi[0][1]+1} and n. CA',
            )
            cmd.set(
                'stick_radius',
                rescale_number(
                    pair_resi[0][-1],
                    min_value=min_gremlin_score,
                    max_value=max_gremlin_score,
                ),
                f'({ce_object_name}  and c. {self.design_chain_id} and resi {pair_resi[0][0]+1}+{pair_resi[0][1]+1} and n. CA)',
            )
            if spatial_distance > max_interact_dist:
                logging.info(
                    f'Resi {pair_resi[0][0]+1} is {spatial_distance:.2f} Å away from {pair_resi[0][1]+1}, out of distance {max_interact_dist}'
                )
                i_out_of_range.append(i)
                cmd.set(
                    'stick_color',
                    'salmon',
                    f'({ce_object_name}  and c. {self.design_chain_id} and resi {pair_resi[0][0]+1}+{pair_resi[0][1]+1} and n. CA)',
                )
            else:
                cmd.set(
                    'stick_color',
                    'marine',
                    f'({ce_object_name}  and c. {self.design_chain_id} and resi {pair_resi[0][0]+1}+{pair_resi[0][1]+1} and n. CA)',
                )

        cmd.show('sticks', ce_object_name)
        cmd.set('stick_use_shader', 0)
        cmd.set('stick_round_nub', 0)
        cmd.set('stick_color', 'gray70', ce_object_name)

        # remove pairs that distal
        for i in i_out_of_range:
            logging.info(
                f'Pair {self.plot_w_fps[i][0][2]}-{self.plot_w_fps[i][0][3]} will be removed:  out of range.'
            )
            self.plot_w_fps.pop(i)

        if i_out_of_range:
            self.renumber_plot_w_fps()

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
        set_widget_value(progress_bar, [0, len(self.plot_w_fps.keys())])
        self.current_gremlin_co_evoving_pair_index = -1

        self.current_gremlin_co_evoving_pair_mutant_id = ''
        self.last_gremlin_co_evoving_pair_mutant_id = ''

        self.current_gremlin_co_evoving_pair_group_id = ''
        self.last_gremlin_co_evoving_pair_group_id = ''

        self.load_co_evolving_pairs(progress_bar)

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
        checkBox_ignore_wt = self.ui.checkBox_interact_ignore_wt
        doubleSpinBox_max_interact_dist = (
            self.ui.doubleSpinBox_max_interact_dist
        )

        lineEdit_current_pair = self.ui.lineEdit_current_pair
        lineEdit_current_pair_score = self.ui.lineEdit_current_pair_score

        if not self.design_chain_id or not self.design_molecule:
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

        set_widget_value(
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

        [i, j, i_aa, j_aa, zscore] = wt_info

        if i < j:
            button_matrix.pos_i, button_matrix.pos_j = i, j
        else:
            button_matrix.pos_i, button_matrix.pos_j = j, i

        button_matrix.pos_i, button_matrix.pos_j, i_aa, j_aa, zscore = wt_info

        button_matrix.init_ui()

        button_matrix.report_axes_signal.connect(
            lambda row, col: self.mutate_with_gridbuttons(
                row,
                col,
                button_matrix.matrix,
                button_matrix.min_value,
                button_matrix.max_value,
                wt_info,
                checkBox_ignore_wt.isChecked(),
            )
        )
        self.ui.gridLayout_interact_pairs.addWidget(button_matrix)

        spatial_distance = cmd.get_distance(
            atom1=f'{self.design_molecule} and c. {self.design_chain_id} and i. {button_matrix.pos_i+1} and n. CA',
            atom2=f'{self.design_molecule} and c. {self.design_chain_id} and i. {button_matrix.pos_j+1} and n. CA',
        )

        set_widget_value(
            lineEdit_current_pair,
            f'{i_aa.replace("_","")}-{j_aa.replace("_","")}, {spatial_distance:.1f} Å',
        )

        set_widget_value(lineEdit_current_pair_score, f'{zscore:.2f}')

        if (
            doubleSpinBox_max_interact_dist.value()
            and spatial_distance > doubleSpinBox_max_interact_dist.value()
        ):
            logging.warning(
                f'Resi {button_matrix.pos_i+1} is {spatial_distance:.2f} Å away from {button_matrix.pos_j+1}, out of distance {doubleSpinBox_max_interact_dist.value()}'
            )
            set_widget_value(lineEdit_current_pair, 'Out of range.')
            # To disable the QbuttonMatrix:
            button_matrix.setEnabled(False)
        else:
            # To enable the QbuttonMatrix:
            button_matrix.setEnabled(True)

    def coevoled_mutant_decision(self, decision_to_accept):
        logging.debug(
            f'{"Accepting" if decision_to_accept else "Rejecting"}  co-evolved mutant {self.current_gremlin_co_evoving_pair_mutant_id}'
        )

        if decision_to_accept:
            cmd.enable(self.current_gremlin_co_evoving_pair_mutant_id)

            self.mutant_tree_coevolved.add_mutant_to_branch(
                self.current_gremlin_co_evoving_pair_group_id,
                self.current_gremlin_co_evoving_pair_mutant_id,
                extract_mutant_from_pymol_object(
                    pymol_object=self.current_gremlin_co_evoving_pair_mutant_id,
                    sequence=self.design_sequence,
                ),
            )
        else:
            cmd.disable(self.current_gremlin_co_evoving_pair_mutant_id)
            if (
                self.current_gremlin_co_evoving_pair_mutant_id
                not in self.mutant_tree_coevolved.all_mutant_ids
            ):
                logging.warning(
                    f'{self.current_gremlin_co_evoving_pair_mutant_id} has not been accepted yet. Skipped.'
                )
                return
            else:
                self.mutant_tree_coevolved.remove_mutant_from_branch(
                    self.current_gremlin_co_evoving_pair_group_id,
                    self.current_gremlin_co_evoving_pair_mutant_id,
                )

        self.save_mutant_choices(
            self.ui.lineEdit_output_mutant_table,
            self.mutant_tree_coevolved,
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

        # close group object if deactivated
        if (
            self.last_gremlin_co_evoving_pair_group_id != ''
            and self.current_gremlin_co_evoving_pair_group_id
            != self.last_gremlin_co_evoving_pair_group_id
        ):
            cmd.disable(self.last_gremlin_co_evoving_pair_group_id)
            cmd.group(
                self.last_gremlin_co_evoving_pair_group_id, action='close'
            )

        # expand group object if activated
        if (
            self.current_gremlin_co_evoving_pair_group_id
            and self.last_gremlin_co_evoving_pair_group_id
            != self.current_gremlin_co_evoving_pair_group_id
        ):
            cmd.enable(self.current_gremlin_co_evoving_pair_group_id)
            cmd.group(
                self.current_gremlin_co_evoving_pair_group_id, action='open'
            )

        cmd.center(self.current_gremlin_co_evoving_pair_mutant_id)

    def mutate_with_gridbuttons(
        self,
        col,
        row,
        matrix,
        min_score,
        max_score,
        wt_info,
        ignore_wt=False,
    ):
        import matplotlib

        matplotlib.use('Agg')

        from REvoDesign.common.MutantVisualizer import MutantVisualizer

        lineEdit_current_pair_wt_score = self.ui.lineEdit_current_pair_wt_score
        lineEdit_current_pair_mut_score = (
            self.ui.lineEdit_current_pair_mut_score
        )

        comboBox_external_scorer = self.ui.comboBox_external_scorer
        external_scorer = comboBox_external_scorer.currentText()
        from REvoDesign.external_designer import EXTERNAL_DESIGNERS

        if external_scorer and external_scorer in EXTERNAL_DESIGNERS:
            magician = EXTERNAL_DESIGNERS[external_scorer]
            if (
                not self.gremlin_external_scorer  # non-scorer is set
                or magician.__name__  # scorer is switched to another
                != self.gremlin_external_scorer.__class__.__name__
            ):
                logging.info(
                    f'Pre-heating {external_scorer} ... This could take a while ...'
                )
                self.gremlin_external_scorer = magician(
                    molecule=self.design_molecule
                )
                run_worker_thread_with_progress(
                    worker_function=self.gremlin_external_scorer.initialize,
                    ignore_missing=bool('X' in self.design_sequence),
                    progress_bar=self.ui.progressBar,
                )

        else:
            if self.gremlin_external_scorer:
                logging.info(
                    f'Cooling down {self.gremlin_external_scorer.__class__.__name__} ...'
                )
            self.gremlin_external_scorer = None

        visualizer = MutantVisualizer(
            molecule=self.design_molecule, chain_id=self.design_chain_id
        )
        visualizer.sequence = self.design_sequence
        alphabet = self.gremlin_tool.alphabet

        visualizer.group_name = '_vs_'.join(
            [wt.replace('_', '') for wt in wt_info[-3:-1]]
        )
        if self.current_gremlin_co_evoving_pair_group_id:
            self.last_gremlin_co_evoving_pair_group_id = (
                self.current_gremlin_co_evoving_pair_group_id
            )

        self.current_gremlin_co_evoving_pair_group_id = visualizer.group_name

        [i, j, i_aa, j_aa, zscore] = wt_info

        # aa from wt
        wt_A = i_aa.split('_')[0]  # in column
        wt_B = j_aa.split('_')[0]  # in row

        wt_score = (
            matrix[alphabet.index(wt_A)][alphabet.index(wt_B)]
            if not self.gremlin_external_scorer
            else self.gremlin_external_scorer.scorer(
                sequence=self.design_sequence
            )
        )

        if i > j:
            j, i = i, j
            j_aa, i_aa = i_aa, j_aa
            col, row = row, col

        # aa from clicked button, mutant
        mut_A = alphabet[col]
        mut_B = alphabet[row]

        _mutant = []

        if self.current_gremlin_co_evoving_pair_mutant_id:
            self.last_gremlin_co_evoving_pair_mutant_id = (
                self.current_gremlin_co_evoving_pair_mutant_id
            )

        for mut, idx, wt in zip([mut_A, mut_B], [i + 1, j + 1], [wt_A, wt_B]):
            _ = f'{self.design_chain_id}{wt}{idx}{mut}'
            if wt == mut and ignore_wt:
                logging.debug(f'Ignore WT to WT mutagenese {_}')

            elif mut == '-':
                logging.info(f'Igore deletion {_}')
            else:
                logging.debug(f'Adding mutagenesis {_}')
                _mutant.append(_)

        if not _mutant:
            logging.info(
                'No mutagenesis will be performed since the picked pair is a wt-wt pair'
            )
            return

        mutant = '_'.join(_mutant)

        _, mutant_obj = extract_mutants_from_mutant_id(
            mutant_string=mutant,
            chain_id=self.design_chain_id,
            sequence=self.design_sequence,
        )

        mutant_obj.wt_sequence = self.design_sequence

        mut_score = (
            matrix[col][row]
            if not self.gremlin_external_scorer
            else self.gremlin_external_scorer.scorer(
                sequence=mutant_obj.get_mutant_sequence()
            )
        )
        mutant_obj.set_mutant_score(mut_score)

        set_widget_value(lineEdit_current_pair_wt_score, f'{wt_score:.3f}')
        set_widget_value(lineEdit_current_pair_mut_score, f'{mut_score:.3f}')

        # update mutant id from Mutant object.
        mutant = mutant_obj.get_short_mutant_id()

        if mutant in cmd.get_names(
            type='nongroup_objects',
            enabled_only=0,
        ):
            logging.info(
                f'Picked mutant: {mutant} already exists. Do nothing.'
            )
        else:
            logging.info(f'Picked mutant: {mutant} ')

            color = get_color(
                self.ui.comboBox_cmap.currentText(),
                mut_score,
                min_score,
                max_score,
            )

            logging.info(f" Visualizing {mutant}: {color}")

            visualizer.create_mutagenesis_objects(mutant_obj, color)
            cmd.hide('everything', 'hydrogens and polymer.protein')
            cmd.hide('cartoon', mutant)

        self.current_gremlin_co_evoving_pair_mutant_id = mutant
        self.activate_focused_interaction()

        if self.ws_server and self.ws_server.is_running and mutant_obj:
            mutant_tree = {
                visualizer.group_name: {
                    mutant_obj.get_short_mutant_id(): mutant_obj
                }
            }

            asyncio.run(
                self.ws_broadcast_from_server(
                    data=MutantTree(mutant_tree=mutant_tree),
                    data_type='MutantTree',
                )
            )

    def generate_ws_server_key(self, lineEdit_ws_server_key):
        key = generate_strong_password(length=32)
        if key:
            set_widget_value(lineEdit_ws_server_key, key)

    def setup_ws_server(self):
        self.ws_server.setup_ws_server(
            checkBox_ws_broadcast_view=self.ui.checkBox_ws_broadcast_view,
            checkBox_ws_duplex_mode=self.ui.checkBox_ws_duplex_mode,
            checkBox_ws_server_use_key=self.ui.checkBox_ws_server_use_key,
            lineEdit_ws_server_key=self.ui.lineEdit_ws_server_key,
            spinBox_ws_server_port=self.ui.spinBox_ws_server_port,
            doubleSpinBox_ws_view_broadcast_interval=self.ui.doubleSpinBox_ws_view_broadcast_interval,
            treeWidget_ws_peers=self.ui.treeWidget_ws_peers,
        )

    def update_ws_server_view_update_options(self):
        if not self.ws_server or not self.ws_server.is_running:
            logging.warning(f'Server is not in service.')
            return

        self.ws_server.view_broadcast_enabled = (
            self.ui.checkBox_ws_broadcast_view.isChecked()
        )
        self.ws_server.view_broadcast_interval = (
            self.ui.doubleSpinBox_ws_view_broadcast_interval.value()
        )
        if self.ui.checkBox_ws_broadcast_view.isChecked():
            if not self.ws_server.clients:
                logging.warning(
                    'Server has no client, ignore view updating. Do nothing.'
                )
                return
            if self.ws_server.view_broadcast_on_air:
                logging.warning(
                    'Server is broadcasting view changes! Do nothing.'
                )
                return

            from REvoDesign.tools.customized_widgets import WorkerThread

            if not self.ws_server.view_broadcast_on_air:
                self.ws_server.view_broadcast_worker = WorkerThread(
                    func=self.ws_server.broadcast_view
                )

            self.ws_server.view_broadcast_on_air = True
            self.ws_server.view_broadcast_worker.run()

            logging.warning('Start broadcasting view.')
            return

        if not self.ui.checkBox_ws_broadcast_view.isChecked():
            if not self.ws_server.view_broadcast_on_air:
                logging.warning(
                    'Server is not broadcasting view changes. Do nothing.'
                )
                return

            self.ws_server.view_broadcast_worker.interrupt()
            self.ws_server.view_broadcast_on_air = False
            logging.warning('Stop broadcasting view.')
            return

    # Assuming toggle_ws_server_mode gets triggered on checkBox_ws_server_mode state change
    def toggle_ws_server_mode(self):
        try:
            if not self.ws_server:
                from REvoDesign.clients.QtSocketConnector import (
                    REvoDesignWebSocketServer,
                )

                self.ws_server = REvoDesignWebSocketServer()

            if self.ui.checkBox_ws_server_mode.isChecked():
                if not self.ws_server or not self.ws_server.is_running:
                    self.setup_ws_server()
                else:
                    logging.warning(
                        f'Server is already in running state. Do nothing.'
                    )
                    return
            else:
                if not self.ws_server.is_running:
                    logging.warning(f'Server is already stopped. Do nothing.')
                    return
                self.ws_server.stop_server()
        except:
            traceback.print_exc()

        logging.warning(
            f'Server status: {"ON" if self.ws_server.is_running else "OFF"}'
        )

    async def ws_broadcast_from_server(self, data, data_type: str):
        await self.ws_server.broadcast_object(data, data_type)

    def setup_ws_client(self):
        if (
            not self.design_molecule
            or not self.design_chain_id
            or not self.design_sequence
        ):
            self.reload_molecule_info(self.ui.comboBox_design_molecule)

        self.ws_client.design_molecule = self.design_molecule
        self.ws_client.design_chain_id = self.design_chain_id
        self.ws_client.design_sequence = self.design_sequence
        self.ws_client.cmap = self.ui.comboBox_cmap.currentText()
        self.ws_client.nproc = self.ui.spinBox_nproc.value()
        self.ws_client.progress_bar = self.ui.progressBar

        self.ws_client.setup_ws_client(
            lineEdit_ws_server_url_to_connect=self.ui.lineEdit_ws_server_url_to_connect,
            spinBox_ws_server_port_to_connect=self.ui.spinBox_ws_server_port,
            lineEdit_ws_server_key_to_connect=self.ui.lineEdit_ws_server_key,
            checkBox_ws_receive_view_broadcast=self.ui.checkBox_ws_recieve_view_broadcast,
            checkBox_ws_receive_mutagenesis_broadcast=self.ui.checkBox_ws_recieve_mutagenesis_broadcast,
            treeWidget_ws_peers=self.ui.treeWidget_ws_peers,
        )

    def update_ws_client_view_update_options(self):
        if not self.ws_client or not self.ws_client.connected:
            logging.warning(f'Client is not connected')
            return

        self.ws_client.receive_view_broadcast = (
            self.ui.checkBox_ws_recieve_view_broadcast.isChecked()
        )

    def toggle_ws_client_connection(self, connect=True):
        if not self.ws_client:
            from REvoDesign.clients.QtSocketConnector import (
                REvoDesignWebSocketClient,
            )

            self.ws_client = REvoDesignWebSocketClient()

        try:
            if connect:
                self.ws_client_connect_to_server()
            else:
                self.ws_client_disconnect_from_server()
        except:
            traceback.print_exc()

        logging.warning(
            f'Client status: {"ON" if self.ws_client.connected else "OFF"}'
        )

    def ws_client_connect_to_server(self):
        self.setup_ws_client()
        if self.ws_client.connected:
            logging.warning(f'Client has already connected. Do noting.')
            return
        self.ws_client.connect_to_server()

    def ws_client_disconnect_from_server(self):
        if not self.ws_client:
            logging.warning(f'Client is not initialized. Do noting.')
            return
        if not self.ws_client.connected:
            logging.warning(f'Client has already disconneced. Do noting.')
            return
        self.ws_client.close_connection()
