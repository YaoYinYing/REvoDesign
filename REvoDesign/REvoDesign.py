import asyncio
import os
import time
import traceback
from immutabledict import immutabledict
from omegaconf import OmegaConf
from pymol import cmd
from pymol.Qt import QtCore, QtGui, QtWidgets


# using partial module to reduce duplicate code.
from functools import partial
from REvoDesign.clients.PSSM_GREMLIN_client import PSSMGremlinCalculator
from REvoDesign.evaluate import Evalutator

from REvoDesign.sidechain_solver import (
    SidechainSolver,
)
from REvoDesign.tools.logger import logging
from REvoDesign.application.ui_driver import (
    Widget2Widget,
    ConfigBus,
)

from REvoDesign.tools.post_installed import (
    EXPERIMENTS_CONFIG_DIR,
    reload_config_file,
    save_configuration,
)

from REvoDesign.common.Mutant import Mutant
from REvoDesign.common.MutantTree import MutantTree
from REvoDesign.common.FileExtentions import (
    REvoDesignFileExtentions as FileExtentions,
)


from REvoDesign.tools.utils import (
    extract_archive,
    generate_strong_password,
    run_worker_thread_with_progress,
    get_color,
    rescale_number,
)

from REvoDesign.tools.customized_widgets import (
    hold_trigger_button,
    getExistingDirectory,
    set_widget_value,
    QbuttonMatrix,
    proceed_with_comfirm_msg_box,
    getOpenFileNameWithExt,
    refresh_widget_while_another_changed,
)


from REvoDesign.tools.pymol_utils import (
    fetch_exclusion_expressions,
    is_empty_session,
    find_all_protein_chain_ids_in_protein,
    find_design_molecules,
    find_small_molecules_in_protein,
    get_molecule_sequence,
    any_posision_has_been_selected,
)

from REvoDesign.tools.mutant_tools import (
    determine_profile_type,
    existed_mutant_tree,
    extract_mutant_from_pymol_object,
    extract_mutants_from_mutant_id,
    get_mutant_table_columns,
    save_mutant_choices,
)

from REvoDesign.common.MultiMutantDesigner import MultiMutantDesigner

REPO_URL = "https://github.com/YaoYinYing/REvoDesign"


class REvoDesignPlugin:
    def __init__(
        self,
    ):
        # global reference to avoid garbage collection of our dialog
        self.window = None

        self.RUN_DIR = os.path.abspath(os.path.dirname(__file__))
        self.PWD = os.getcwd()

        self.ui_file = os.path.join(self.RUN_DIR, 'UI', 'REvoDesign-PyMOL.ui')

        self.widget2widget = Widget2Widget()
        self.bus = None

        self.designable_sequences = {}
        self.design_molecule = ''
        self.design_chain_id = ''
        self.design_sequence = ''

        self.mutant_tree_coevolved = MutantTree({})

        self.gremlin_tool = None
        self.gremlin_external_scorer = None
        self.sidechain_solver = None
        self.evaluator: Evalutator = None

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
        logging.debug(
            f'REvoDesign is installed in {os.path.dirname(__file__)}'
        )
        main_window = QtWidgets.QMainWindow()

        from pymol.Qt.utils import loadUi

        # load ui elements
        self.ui = loadUi(
            self.ui_file, main_window
        )  # Store the UI form for later access

        # create a bus btw cfg<---> ui
        self.reload_configurations()

        from REvoDesign.tools.customized_widgets import set_window_font

        set_window_font(main_window)

        # Set up Menu

        self.bus.ui.actionSet_Working_Directory.triggered.connect(
            self.set_working_directory
        )

        self.bus.ui.actionReconfigure.triggered.connect(
            self.reload_configurations
        )
        self.bus.ui.actionSave_Configurations.triggered.connect(
            self.save_configuration_from_ui
        )

        self.bus.ui.action_LoadExperiment.triggered.connect(
            partial(self.load_and_save_experiment, mode='r')
        )

        self.bus.ui.action_Save_to_Experiment.triggered.connect(
            partial(self.load_and_save_experiment, mode='w')
        )

        self.bus.ui.actionSource_Code.triggered.connect(
            partial(
                QtGui.QDesktopServices.openUrl,
                QtCore.QUrl(REPO_URL),
            )
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
            self.bus.ui.tabWidget.setTabVisible(7, False)

        # Set up general input
        self.bus.ui.comboBox_chain_id.currentIndexChanged.connect(
            self.set_design_sequence,
        )

        # read session from PyMOL. If it is empty, load one.
        self.bus.ui.actionCheck_PyMOL_session.triggered.connect(
            self.reload_molecule_info,
        )

        # Update chain id
        self.bus.ui.comboBox_design_molecule.currentIndexChanged.connect(
            self.update_chain_id,
        )

        # set up nproc
        from REvoDesign.tools.system_tools import CLIENT_INFO

        max_proc = CLIENT_INFO().nproc
        self.bus.set_widget_value('ui.header_panel.nproc', (1, max_proc))
        self.bus.set_widget_value('ui.header_panel.nproc', max_proc)
        self.bus.set_value('ui.header_panel.nproc', max_proc)

        # Tab Client
        self.bus.ui.comboBox_chain_id.currentIndexChanged.connect(
            self.setup_pssm_gremlin_calculator,
        )

        self.bus.button('submit_pssm_gremlin_job').clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='submit',
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button('cancel_pssm_gremlin_job').clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='cancel',
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button('download_pssm_gremlin_job').clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_remote_pssm_gremlin_calc,
                opt='download',
                progress_bar=self.bus.ui.progressBar,
            )
        )

        # Set up general arguments
        # Tab `Prepare`

        self.bus.button('open_output_pse_pocket').clicked.connect(
            partial(self.save_as_a_session, 'ui.prepare.input.pocket.to_pse')
        )

        self.bus.button('open_output_pse_surface').clicked.connect(
            partial(self.save_as_a_session, 'ui.prepare.input.surface.to_pse')
        )

        self.bus.button('run_surface_refresh').clicked.connect(
            self.update_surface_exclusion
        )

        self.bus.ui.lineEdit_output_pse_surface.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.prepare.input.surface.to_pse',
                'run_surface_detection',
            )
        )

        self.bus.ui.lineEdit_output_pse_pocket.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.prepare.input.pocket.to_pse',
                'run_pocket_detection',
            )
        )

        self.bus.ui.comboBox_design_molecule.currentIndexChanged.connect(
            self.reload_determine_tab_setup,
        )

        # Connect run buttons
        self.bus.button('dump_interfaces').clicked.connect(
            self.run_chain_interface_detection
        )
        self.bus.button('run_surface_detection').clicked.connect(
            self.run_surface_detection
        )
        self.bus.button('run_pocket_detection').clicked.connect(
            self.run_pocket_detection
        )

        # Tab `Mutate`

        self.bus.button('open_output_pse_mutate').clicked.connect(
            partial(self.save_as_a_session, 'ui.mutate.input.to_pse')
        )

        self.bus.button('open_customized_indices').clicked.connect(
            partial(
                self.open_input_psepath,
                'ui.mutate.input.residue_ids',
                [FileExtentions.TXT_FileExt, FileExtentions.AnyFileExt],
            )
        )

        self.bus.button('open_input_csv').clicked.connect(
            partial(
                self.open_input_psepath,
                'ui.mutate.input.profile',
                [
                    FileExtentions.PSSM_FileExt,
                    FileExtentions.AnyFileExt,
                    FileExtentions.CompressedFileExt,
                ],
            )
        )

        self.bus.ui.lineEdit_input_csv.textChanged.connect(
            partial(
                self.determine_profile_format,
                'ui.mutate.input.profile',
                'ui.mutate.input.profile_type',
            )
        )

        self.bus.ui.lineEdit_output_pse_mutate.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.mutate.input.to_pse',
                'run_PSSM_to_pse',
            )
        )

        self.bus.button('run_PSSM_to_pse').clicked.connect(
            self.run_mutant_loading_from_profile
        )

        # Tab `Evaluate`
        self.bus.button('open_mut_table').clicked.connect(
            partial(
                self.open_mutant_table, 'ui.evaluate.input.to_mutant_txt', 'w'
            )
        )

        self.bus.ui.lineEdit_output_mut_table.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.evaluate.input.to_mutant_txt',
                [
                    'previous_mutant',
                    'reject_this_mutant',
                    'next_mutant',
                    'accept_this_mutant',
                ],
            )
        )

        self.bus.ui.checkBox_rock_pymol.stateChanged.connect(
            self.set_pymol_session_rock
        )

        self.bus.button('reinitialize_mutant_choosing').clicked.connect(
            self.initialize_design_candidates,
        )

        self.bus.button('goto_best_hit_in_group').clicked.connect(
            self.jump_to_the_best_mutant,
        )

        self.bus.button('load_mutant_choice_checkpoint').clicked.connect(
            self.recover_mutant_choices_from_checkpoint,
        )

        self.bus.ui.comboBox_group_ids.currentTextChanged.connect(
            self.jump_to_branch,
        )

        self.bus.ui.comboBox_mutant_ids.currentTextChanged.connect(
            self.jump_to_a_mutant,
        )

        self.bus.button('choose_lucky_mutant').clicked.connect(
            self.find_all_best_mutants,
        )

        # Tab `Cluster`

        self.bus.button('open_mut_table_2').clicked.connect(
            partial(
                self.open_mutant_table, 'ui.cluster.input.from_mutant_txt', 'r'
            )
        )

        self.bus.ui.lineEdit_input_mut_table.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.cluster.input.from_mutant_txt',
                'run_cluster',
            )
        )

        self.bus.button('run_cluster').clicked.connect(self.run_clustering)

        # Tab Visualize

        self.bus.ui.lineEdit_output_pse_visualize.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.visualize.input.to_pse',
                'run_visualizing',
            )
        )

        self.bus.ui.lineEdit_input_mut_table_csv.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.visualize.input.from_mutant_txt',
                [
                    'save_this_mutant_table',
                    'reduce_this_session',
                ],
            )
        )

        self.bus.button('save_this_mutant_table').clicked.connect(
            partial(
                self.save_visualizing_mutant_tree,
                'ui.visualize.input.from_mutant_txt',
                'ui.visualize.input.group_name',
            )
        )

        self.bus.ui.lineEdit_input_csv_2.textChanged.connect(
            partial(
                self.determine_profile_format,
                'ui.visualize.input.profile',
                'ui.visualize.input.profile_type',
            )
        )

        self.bus.button('open_input_csv_2').clicked.connect(
            partial(
                self.open_input_psepath,
                'ui.visualize.input.profile',
                [
                    FileExtentions.PSSM_FileExt,
                    FileExtentions.AnyFileExt,
                    FileExtentions.CompressedFileExt,
                ],
            )
        )

        self.bus.button('open_mut_table_csv').clicked.connect(
            partial(
                self.open_mutant_table,
                'ui.visualize.input.from_mutant_txt',
                'r',
            )
        )

        self.bus.ui.lineEdit_input_mut_table_csv.textChanged.connect(
            self.update_mutant_table_columns,
        )

        self.bus.button('open_output_pse_visualize').clicked.connect(
            partial(
                self.save_as_a_session,
                'ui.visualize.input.to_pse',
            )
        )

        self.bus.set_widget_value('ui.visualize.input.best_leaf', 'best_leaf')
        self.bus.set_widget_value(
            'ui.visualize.input.totalscore', 'totalscore'
        )

        self.bus.button('run_visualizing').clicked.connect(
            self.visualize_mutants
        )

        self.bus.button('reduce_this_session').clicked.connect(
            partial(
                self.reduce_current_session,
                session=None,
                reduce_disabled=True,
                overwrite=False,
            )
        )

        # Multi-Design
        self.bus.ui.lineEdit_multi_design_mutant_table.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.visualize.input.multi_design.to_mutant_txt',
                [
                    'multi_design_export_mutants_from_table',
                    'run_multi_design',
                ],
            )
        )

        self.bus.button('open_mut_table_csv_2').clicked.connect(
            partial(
                self.open_mutant_table,
                'ui.visualize.input.multi_design.to_mutant_txt',
                'w',
            )
        )

        self.bus.button('multi_design_initialize').clicked.connect(
            self.multi_mutagenesis_design_initialize
        )

        self.bus.button('multi_design_start_new_design').clicked.connect(
            self.multi_mutagenesis_design_start
        )

        self.bus.button('multi_design_left').clicked.connect(
            self.multi_mutagenesis_design_undo_picking
        )

        self.bus.button('multi_design_right').clicked.connect(
            self.multi_mutagenesis_design_pick_next_mut
        )

        self.bus.button('multi_design_end_this_design').clicked.connect(
            self.multi_mutagenesis_design_stop_design
        )

        self.bus.button(
            'multi_design_export_mutants_from_table'
        ).clicked.connect(self.multi_mutagenesis_design_save_design)

        self.bus.button('run_multi_design').clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_auto,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        # Tab Interact

        self.bus.button('open_gremlin_mtx').clicked.connect(
            partial(
                self.open_input_psepath,
                'ui.interact.input.gremlin_pkl',
                [
                    FileExtentions.PickleObjectFileExt,
                    FileExtentions.AnyFileExt,
                ],
            )
        )

        self.bus.button('reinitialize_interact').clicked.connect(
            self.load_gremlin_mrf
        )
        self.bus.button('run_interact_scan').clicked.connect(
            self.run_gremlin_tool
        )

        self.bus.button('open_save_mutant_table').clicked.connect(
            partial(
                self.open_mutant_table,
                'ui.interact.input.to_mutant_txt',
                'w',
            )
        )

        self.bus.button('interact_reject').clicked.connect(
            self.coevoled_mutant_decision, False
        )
        self.bus.button('interact_accept').clicked.connect(
            self.coevoled_mutant_decision, True
        )

        # Tab socket
        self.generate_ws_server_key()

        self.bus.button('ws_generate_randomized_key').clicked.connect(
            self.generate_ws_server_key
        )

        # Connect the partial function to the stateChanged signal
        self.bus.ui.checkBox_ws_server_mode.stateChanged.connect(
            self.toggle_ws_server_mode
        )

        self.bus.button('ws_connect_to_server').clicked.connect(
            partial(self.toggle_ws_client_connection, True)
        )

        self.bus.button('ws_disconnect_from_server').clicked.connect(
            partial(self.toggle_ws_client_connection, False)
        )

        self.bus.ui.checkBox_ws_broadcast_view.stateChanged.connect(
            self.update_ws_server_view_update_options
        )
        self.bus.ui.doubleSpinBox_ws_view_broadcast_interval.valueChanged.connect(
            self.update_ws_server_view_update_options
        )

        self.bus.ui.checkBox_ws_recieve_view_broadcast.stateChanged.connect(
            self.update_ws_client_view_update_options
        )

        # Tab Config

        self.bus.ui.comboBox_sidechain_solver.currentIndexChanged.connect(
            partial(
                refresh_widget_while_another_changed,
                self.bus.get_widget_from_cfg_item(
                    'ui.config.sidechain_solver.default'
                ),
                self.bus.get_widget_from_cfg_item(
                    'ui.config.sidechain_solver.model'
                ),
                self.widget2widget.sidechain_solver2model,
            )
        )

        # register widget change events to update cfg items
        self.bus.register_widget_changes_to_cfg()

        return main_window

    def set_design_sequence(
        self,
    ):
        design_molecule = self.bus.get_widget_value(
            'ui.header_panel.input.molecule'
        )
        design_chain = self.bus.get_widget_value(
            'ui.header_panel.input.chain_id'
        )

        if design_molecule and design_chain:
            self.design_molecule = design_molecule
            self.design_chain_id = design_chain
            self.design_sequence = self.designable_sequences[
                self.design_chain_id
            ]

    # class public function that can be shared with each tab
    # callback for the "Browse" button
    def browse_filename(self, mode='r', exts=[FileExtentions.AnyFileExt]):
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
                for ext_, _ in FileExtentions.CompressedFileExt.items()
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
    def open_input_psepath(
        self, cfg_input: str, exts=[FileExtentions.AnyFileExt]
    ):
        input_fn = self.browse_filename(mode='r', exts=exts)
        if input_fn:
            self.bus.set_widget_value(cfg_input, input_fn)
            return input_fn

    def reload_molecule_info(self):
        import tempfile

        self.temperal_session = tempfile.mktemp(suffix=".pse")

        if not is_empty_session():
            # remove alternative comformations
            cmd.remove('not alt ""+A')
            cmd.alter('all', 'alt=""')
            cmd.save(self.temperal_session)
            cmd.reinitialize()
            cmd.load(self.temperal_session)
        else:
            logging.warning(
                f'Current session is empty! \n \
                            Please load one PDB/PSE/PZE!'
            )
            new_session_file = self.browse_filename(
                mode='r',
                exts=[
                    FileExtentions.SessionFileExt,
                    FileExtentions.PDB_FileExt,
                    FileExtentions.AnyFileExt,
                ],
            )
            if not new_session_file:
                logging.error(f'Abored recognizing sessions from input.')
                return
            elif not os.path.exists(new_session_file):
                logging.error(f'File does not exist: {new_session_file}.')
                return
            else:
                cmd.reinitialize()
                cmd.load(new_session_file)
                # remove alternative comformations
                cmd.remove('not alt ""+A')
                cmd.alter('all', 'alt=""')
                cmd.save(self.temperal_session)

        self.bus.set_widget_value(
            'ui.header_panel.input.molecule', find_design_molecules
        )

    def save_as_a_session(self, cfg_to_pse: str):
        output_pse_fn = self.browse_filename(
            mode='w',
            exts=[FileExtentions.SessionFileExt, FileExtentions.AnyFileExt],
        )

        if output_pse_fn and os.path.exists(os.path.dirname(output_pse_fn)):
            logging.info(f"Output file is set as {output_pse_fn}")
            self.bus.set_widget_value(cfg_to_pse, output_pse_fn)
        else:
            logging.warning(f"Invalid output path: {output_pse_fn}.")

    def update_chain_id(self):
        molecule = self.bus.get_widget_value('ui.header_panel.input.molecule')
        if not molecule:
            logging.warning(f'No available designable molecule!')
            return
        chain_ids = find_all_protein_chain_ids_in_protein(molecule)
        self.designable_sequences = {
            chain_id: get_molecule_sequence(
                molecule=molecule,
                chain_id=chain_id,
                keep_missing=True,
            )
            for chain_id in chain_ids
        }
        if chain_ids:
            self.bus.set_widget_value(
                'ui.header_panel.input.chain_id', chain_ids
            )
            self.bus.set_widget_value(
                'ui.header_panel.input.chain_id', chain_ids[0]
            )

    def open_mutant_table(self, cfg_mutant_table: str, mode='r'):
        if mode == 'r':
            input_mut_txt_fn = self.open_input_psepath(
                cfg_mutant_table,
                [
                    FileExtentions.MutableFileExt,
                    FileExtentions.AnyFileExt,
                    FileExtentions.CompressedFileExt,
                ],
            )
            if input_mut_txt_fn:
                self.bus.set_widget_value(cfg_mutant_table, input_mut_txt_fn)
            else:
                logging.warning(
                    f'Could not open file for reading: {input_mut_txt_fn}'
                )
        elif mode == 'w':
            output_mut_txt_fn = self.browse_filename(
                mode=mode,
                exts=[
                    FileExtentions.MutableFileExt,
                    FileExtentions.AnyFileExt,
                ],
            )
            if output_mut_txt_fn and os.path.exists(
                os.path.dirname(output_mut_txt_fn)
            ):
                logging.info(f"Output file is set as {output_mut_txt_fn}")
                self.bus.set_widget_value(cfg_mutant_table, output_mut_txt_fn)
            else:
                logging.warning(f"Invalid output path: {output_mut_txt_fn}.")
        else:
            logging.warning(f'Unknown mode {mode} ! Aborded.')

    def find_session_path(self) -> str:
        session_path: str = cmd.get('session_file')

        if not session_path:
            logging.warning(
                'Session not found, please use a new session path to save.'
            )
            return self.browse_filename(
                mode='w', exts=[FileExtentions.SessionFileExt]
            )

        if not os.path.exists(session_path):
            logging.warning(
                'Invalid session file path, please use a new session path to save.'
            )
            return self.browse_filename(
                mode='w', exts=[FileExtentions.SessionFileExt]
            )

        if os.path.basename(session_path).startswith(
            'tmp'
        ) and session_path.endswith('.pse'):
            logging.warning(
                f'Found temperal session path: {session_path}, please use a new session path to save.'
            )
            return self.browse_filename(
                mode='w', exts=[FileExtentions.SessionFileExt]
            )

        return session_path

    def flatten_compressed_files(self, compressed_file: str) -> str:
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
        molecule = self.bus.get_value('ui.header_panel.input.molecule')
        chain_id = self.bus.get_value('ui.header_panel.input.chain_id')
        sequence = self.designable_sequences[self.design_chain_id]

        if (not molecule) or (not chain_id) or (not sequence):
            return

        logging.debug(
            f'Molecule: {molecule}\nchain_id: {chain_id}\nsequence: {sequence}'
        )
        if not isinstance(self.pssm_gremlin_calculator, PSSMGremlinCalculator):
            self.pssm_gremlin_calculator = PSSMGremlinCalculator()

        if molecule and chain_id and sequence:
            self.pssm_gremlin_calculator.setup_calculator(
                working_directory=self.PWD,
                molecule=molecule,
                chain_id=chain_id,
                sequence=sequence,
            )
        self.pssm_gremlin_calculator.url = self.bus.get_value(
            'ui.client.pssm_gremlin_url'
        )
        self.pssm_gremlin_calculator.user = self.bus.get_value(
            'ui.client.pssm_gremlin_user'
        )
        self.pssm_gremlin_calculator.password = self.bus.get_value(
            'ui.client.pssm_gremlin_passwd'
        )
        if (
            self.pssm_gremlin_calculator.user
            and self.pssm_gremlin_calculator.password
        ):
            from requests.auth import HTTPBasicAuth

            self.pssm_gremlin_calculator.auth = HTTPBasicAuth(
                self.pssm_gremlin_calculator.user,
                self.pssm_gremlin_calculator.password,
            )
        else:
            self.pssm_gremlin_calculator.auth = None

    # Tab `Determine`
    def reload_determine_tab_setup(
        self,
    ):
        # Setup pocket determination arguments
        small_molecules = find_small_molecules_in_protein(self.design_molecule)
        if small_molecules:
            self.bus.set_widget_value(
                'ui.prepare.input.pocket.substrate', small_molecules
            )
            self.bus.set_widget_value(
                'ui.prepare.input.pocket.cofactor', small_molecules
            )

    def update_surface_exclusion(self):
        exclusion_list = fetch_exclusion_expressions()

        self.bus.set_widget_value(
            'ui.prepare.input.surface.exclusion', exclusion_list
        )
        if exclusion_list:
            self.bus.get_widget_from_cfg_item(
                'ui.prepare.input.surface.exclusion'
            ).setCurrentIndex(0)

    def run_chain_interface_detection(self):
        molecule = self.bus.get_value('ui.header_panel.input.molecule')
        radius = self.bus.get_value('ui.prepare.chain_dist', float)
        chain_ids = find_all_protein_chain_ids_in_protein(molecule)
        if not chain_ids or len(chain_ids) <= 1:
            return

        for chain_id in chain_ids:
            cmd.select(
                f'if_{chain_id}',
                f'({molecule} and c. {chain_id} ) and byres ({molecule} and polymer.protein and (not c. {chain_id})) around {radius} and polymer.protein',
            )

    def run_surface_detection(self):
        input_pse = self.temperal_session
        output_pse = self.bus.get_value('ui.prepare.input.surface.to_pse')

        exclusion = self.bus.get_value('ui.prepare.input.surface.exclusion')
        cutoff = self.bus.get_value('ui.prepare.surface_probe_radius', float)
        do_show_surf_CA = True

        from REvoDesign.structure.SurfaceFinder import SurfaceFinder

        surfacefinder = SurfaceFinder(
            input_pse=input_pse,
            output_pse=output_pse,
            molecule=self.design_molecule,
            chain_id=self.design_chain_id,
            cutoff=cutoff,
            exclude_residue_selection=exclusion,
            do_show_surf_CA=do_show_surf_CA,
        )

        surfacefinder.process_surface_residues()

    def run_pocket_detection(self):
        input_pse = self.temperal_session
        output_pse = self.bus.get_value('ui.prepare.input.pocket.to_pse')
        ligand = self.bus.get_value('ui.prepare.input.pocket.substrate')
        cofactor = self.bus.get_value('ui.prepare.input.pocket.cofactor')
        ligand_radius = self.bus.get_value('ui.prepare.ligand_radius', float)
        cofactor_radius = self.bus.get_value(
            'ui.prepare.cofactor_radius', float
        )

        from REvoDesign.structure import PocketSearcher

        pocketsearcher = PocketSearcher(
            input_pse=input_pse,
            output_pse=output_pse,
            molecule=self.design_molecule,
            chain_id=self.design_chain_id,
            ligand=ligand,
            ligand_radius=ligand_radius,
            cofactor=cofactor,
            cofactor_radius=cofactor_radius,
            save_dir=f'{self.PWD}/pockets/',
        )

        pocketsearcher.search_pockets()

    # Tab `Mutate`
    def refresh_sidechainsolver(self):
        sidechain_solver_name = self.bus.get_value(
            'ui.config.sidechain_solver.default'
        )
        sidechain_solver_radius = self.bus.get_value(
            'ui.config.sidechain_solver.repack_radius', float
        )
        sidechain_solver_model = self.bus.get_value(
            'ui.config.sidechain_solver.model'
        )
        available_sidechain_solvers = list(
            self.bus.get_value('ui.config.sidechain_solver.group')
        )
        if not self.sidechain_solver:
            self.sidechain_solver = SidechainSolver(
                molecule=self.design_molecule,
                chain_id=self.design_chain_id,
                sidechain_solver_name=sidechain_solver_name,
                sidechain_solver_radius=sidechain_solver_radius,
                sidechain_solver_model=sidechain_solver_model,
                available_sidechain_solvers=available_sidechain_solvers,
            )
            self.sidechain_solver.setup()
            return

        if not (
            self.sidechain_solver.molecule == self.design_molecule
            and self.sidechain_solver.chain_id == self.design_chain_id
            and self.sidechain_solver.sidechain_solver_name
            == sidechain_solver_name
            and self.sidechain_solver.sidechain_solver_radius
            == sidechain_solver_radius
            and self.sidechain_solver.sidechain_solver_model
            == sidechain_solver_model
        ):
            self.sidechain_solver.refresh(
                molecule=self.design_molecule,
                chain_id=self.design_chain_id,
                sidechain_solver_name=sidechain_solver_name,
                sidechain_solver_radius=sidechain_solver_radius,
                sidechain_solver_model=sidechain_solver_model,
            )

    def determine_profile_format(
        self, cfg_input_profile: str, cfg_profile_format: str
    ):
        _fp = self.bus.get_value(cfg_input_profile)
        if _fp == 'None' or not _fp:
            return None

        profile_fp = os.path.abspath(_fp)

        if not os.path.exists(profile_fp):
            return None

        profile_format= determine_profile_type(profile_fp=profile_fp)
        if not profile_format:
            return

        self.bus.set_widget_value(cfg_profile_format, profile_format)

    def run_mutant_loading_from_profile(self):
        from REvoDesign.phylogenetics import MutateWorker

        trigger_button = self.bus.button('run_PSSM_to_pse')

        with hold_trigger_button(trigger_button):
            run_worker_thread_with_progress(self.refresh_sidechainsolver)
            assert self.sidechain_solver and isinstance(
                self.sidechain_solver, SidechainSolver
            ), f'MutateWorker requires a valid sidechain_solver! {self.sidechain_solver}'

            worker = MutateWorker(
                bus=self.bus,
                design_molecule=self.design_molecule,
                design_chain_id=self.design_chain_id,
                design_sequence=self.design_sequence,
                designable_sequences=self.designable_sequences,
                sidechain_solver=self.sidechain_solver,
                PWD=self.PWD,
            )

            worker.run_mutant_loading_from_profile()

        if (
            self.ws_server
            and self.ws_server.is_running
            and worker.design.mutant_tree
            and not worker.design.mutant_tree.empty
        ):
            asyncio.run(
                self.ws_broadcast_from_server(
                    data=worker.design.mutant_tree,
                    data_type='MutantTree',
                )
            )

    # Tab `Evaluate`
    def set_pymol_session_rock(self):
        if not self.evaluator:
            return
        self.evaluator.set_pymol_session_rock()

    def initialize_design_candidates(
        self,
    ):
        self.evaluator = Evalutator(
            bus=self.bus,
            design_molecule=self.design_molecule,
            design_chain_id=self.design_chain_id,
            design_sequence=self.design_sequence,
            designable_sequences=self.designable_sequences,
        )

        self.evaluator.initialize_design_candidates()

    def recover_mutant_choices_from_checkpoint(self):
        if not self.evaluator:
            return
        mutant_choice_checkpoint_fn = self.browse_filename(
            mode='r',
            exts=[FileExtentions.MutableFileExt, FileExtentions.AnyFileExt],
        )

        self.evaluator.recover_mutant_choices_from_checkpoint(
            mutant_choice_checkpoint_fn
        )

    def jump_to_the_best_mutant(self):
        if not self.evaluator:
            return
        self.evaluator.jump_to_the_best_mutant()

    def jump_to_branch(self):
        if not self.evaluator:
            return
        self.evaluator.jump_to_branch()

    def jump_to_a_mutant(self):
        if not self.evaluator:
            return
        self.evaluator.jump_to_a_mutant()

    def find_all_best_mutants(self):
        if not self.evaluator:
            return
        self.evaluator.find_all_best_mutants()

    # combination and clustering
    def run_clustering(self):
        trigger_button = self.bus.button('run_cluster')

        # lazy module loading to fasten plugin initializing
        from REvoDesign.clusters import ClusterRunner

        input_mutant_table = self.bus.get_value(
            'ui.cluster.input.from_mutant_txt'
        )

        cluster_batch_size = self.bus.get_value('ui.cluster.batch_size', int)
        cluster_number = self.bus.get_value('ui.cluster.num_cluster', int)
        min_mut_num = self.bus.get_value('ui.cluster.mut_num_min', int)
        max_mut_num = self.bus.get_value('ui.cluster.mut_num_max', int)
        cluster_substitution_matrix = self.bus.get_value(
            'ui.cluster.score_matrix.default'
        )

        shuffle_variant = self.bus.get_value('ui.cluster.shuffle')

        nproc = self.bus.get_value('ui.header_panel.nproc', int)

        worker = ClusterRunner(
            bus=self.bus,
            design_molecule=self.design_molecule,
            design_chain_id=self.design_chain_id,
            design_sequence=self.design_sequence,
            PWD=self.PWD,
            cluster_batch_size=cluster_batch_size,
            cluster_number=cluster_number,
            min_mut_num=min_mut_num,
            max_mut_num=max_mut_num,
            cluster_substitution_matrix=cluster_substitution_matrix,
            shuffle_variant=shuffle_variant,
            nproc=nproc,
            input_mutant_table=input_mutant_table,
        )

        with hold_trigger_button(trigger_button):
            worker.run_clustering()

    # Tab Visualize

    def update_mutant_table_columns(
        self,
    ):
        mut_table_fp = self.bus.get_value('ui.visualize.input.from_mutant_txt')
        if not os.path.exists(mut_table_fp):
            logging.warning(f'Mutant Table path is not valid: {mut_table_fp}')
            return
    
        mut_table_cols = get_mutant_table_columns(
            mutfile=mut_table_fp
        )

        if not mut_table_cols:
            logging.warning(
                f'Mutant Table column names is not valid: {mut_table_cols}'
            )
            return
        
        comboBox_best_leaf = self.bus.get_widget_from_cfg_item(
            'ui.visualize.input.best_leaf'
        )
        comboBox_totalscore = self.bus.get_widget_from_cfg_item(
            'ui.visualize.input.totalscore'
        )

        # set cols to combo boxes
        for comboBox in [comboBox_best_leaf, comboBox_totalscore]:
            set_widget_value(comboBox, mut_table_cols)

        # set default col value
        if len(mut_table_cols) > 1:
            set_widget_value(comboBox_best_leaf, mut_table_cols[0])
            set_widget_value(comboBox_totalscore, mut_table_cols[-1])

    def save_visualizing_mutant_tree(
        self, cfg_mutant_table_fp, cfg_group_name
    ):
        
        group_name = self.bus.get_value(cfg_group_name)

        mutant_table_fp = self.bus.get_value(cfg_mutant_table_fp)

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
            sequences=self.designable_sequences, enabled_only=1
        )

        logging.info(f'Saving mutant table to {mutant_table_fp} ...')

        save_mutant_choices(
            self.bus.get_value(cfg_mutant_table_fp),
            self.visualizing_mutant_tree,
        )

    def visualize_mutants(self):
        trigger_button = self.bus.button('run_visualizing')
        from REvoDesign.phylogenetics import VisualizingWorker

        with hold_trigger_button(trigger_button):
            # reinstiatate sidechain solver if required
            run_worker_thread_with_progress(self.refresh_sidechainsolver)
            assert self.sidechain_solver and isinstance(
                self.sidechain_solver, SidechainSolver
            ), f'MutateWorker requires a valid sidechain_solver! {self.sidechain_solver}'

            worker = VisualizingWorker(
                bus=self.bus,
                design_molecule=self.design_molecule,
                design_chain_id=self.design_chain_id,
                design_sequence=self.design_sequence,
                designable_sequences=self.designable_sequences,
                sidechain_solver=self.sidechain_solver,
                PWD=self.PWD,
            )
            worker.visualize_mutants()

        if (
            self.ws_server
            and self.ws_server.is_running
            and worker.visualizer.mutant_tree
            and not worker.visualizer.mutant_tree.empty
        ):
            asyncio.run(
                self.ws_broadcast_from_server(
                    data=worker.visualizer.mutant_tree,
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
                        mode='w', exts=[FileExtentions.SessionFileExt]
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
        spinBox_maximal_mutant_num = self.bus.ui.spinBox_maximal_mutant_num
        doubleSpinBox_minmal_mutant_distance = (
            self.bus.ui.doubleSpinBox_minmal_mutant_distance
        )
        checkBox_multi_design_bond_CA = (
            self.bus.ui.checkBox_multi_design_bond_CA
        )
        checkBox_multi_design_check_sidechain_orientations = (
            self.bus.ui.checkBox_multi_design_check_sidechain_orientations
        )
        comboBox_profile_type_2 = self.bus.ui.comboBox_profile_type_2
        spinBox_maximal_multi_design_variant_num = (
            self.bus.ui.spinBox_maximal_multi_design_variant_num
        )
        checkBox_multi_design_use_external_scorer = (
            self.bus.ui.checkBox_multi_design_use_external_scorer
        )
        checkBox_multi_design_color_by_scores = (
            self.bus.ui.checkBox_multi_design_color_by_scores
        )
        checkBox_reverse_mutant_effect_3 = (
            self.bus.ui.checkBox_reverse_mutant_effect_3
        )

        self.multi_mutagenesis_designer.scorer = (
            comboBox_profile_type_2.currentText()
        )
        self.multi_mutagenesis_designer.total_design_cases = (
            spinBox_maximal_multi_design_variant_num.value()
        )

        self.multi_mutagenesis_designer.cmap = self.bus.get_value(
            'ui.header_panel.cmap.default'
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

        mut_table_csv = self.bus.ui.lineEdit_multi_design_mutant_table.text()
        self.multi_mutagenesis_designer.export_designed_variant(
            save_mutant_table=mut_table_csv
        )

    def multi_mutagenesis_design_auto(self):
        trigger_button = self.bus.button('run_multi_design')
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

        with hold_trigger_button(trigger_button):
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

    # Tab Interact via GREMLIN
    def load_gremlin_mrf(
        self,
    ):
        trigger_button = self.bus.button('reinitialize_interact')
        from REvoDesign.phylogenetics.GREMLIN_Tools import GREMLIN_Tools

        with hold_trigger_button(trigger_button):
            gremlin_mrf_fp = self.bus.get_value(
                'ui.interact.input.gremlin_pkl'
            )

            topN_gremlin_candidates = self.bus.get_value(
                'ui.interact.topN_pairs', int
            )
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

            pushButton_run_interact_scan = self.bus.button('run_interact_scan')
            gridLayout_interact_pairs = self.bus.ui.gridLayout_interact_pairs

            # reset design info
            lineEdit_current_pair_wt_score = (
                self.bus.ui.lineEdit_current_pair_wt_score
            )
            lineEdit_current_pair_mut_score = (
                self.bus.ui.lineEdit_current_pair_mut_score
            )
            lineEdit_current_pair = self.bus.ui.lineEdit_current_pair
            lineEdit_current_pair_score = (
                self.bus.ui.lineEdit_current_pair_score
            )

            for lineEdit in [
                lineEdit_current_pair,
                lineEdit_current_pair_score,
                lineEdit_current_pair_wt_score,
                lineEdit_current_pair_mut_score,
            ]:
                set_widget_value(lineEdit, '')

            progress_bar = self.bus.ui.progressBar

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

    def run_gremlin_tool(self):
        trigger_button = self.bus.button('run_interact_scan')

        progress_bar = self.bus.ui.progressBar
        max_interact_dist = self.bus.get_value(
            'ui.interact.max_interact_dist', float
        )

        self.plot_w_fps = {}
        with hold_trigger_button(trigger_button):
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
                    self.gremlin_tool.plot_w_in_batch,
                    progress_bar=progress_bar,
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
                        [
                            self.plot_w_fps[i][0][-1]
                            for i in self.plot_w_fps.keys()
                        ]
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
                self.bus.button('previous').clicked.disconnect()
                self.bus.button('next').clicked.disconnect()
            except:
                pass

            self.bus.button('previous').clicked.connect(
                partial(self.load_co_evolving_pairs, progress_bar, False)
            )

            self.bus.button('next').clicked.connect(
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
        ignore_wt = self.bus.get_value('ui.interact.interact_ignore_wt')
        max_interact_dist = self.bus.get_value(
            'ui.interact.max_interact_dist', float
        )

        lineEdit_current_pair = self.bus.ui.lineEdit_current_pair
        lineEdit_current_pair_score = self.bus.ui.lineEdit_current_pair_score

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
        for i in reversed(
            range(self.bus.ui.gridLayout_interact_pairs.count())
        ):
            widget = self.bus.ui.gridLayout_interact_pairs.itemAt(i).widget()
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
                ignore_wt.isChecked(),
            )
        )
        self.bus.ui.gridLayout_interact_pairs.addWidget(button_matrix)

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
            max_interact_dist.value()
            and spatial_distance > max_interact_dist.value()
        ):
            logging.warning(
                f'Resi {button_matrix.pos_i+1} is {spatial_distance:.2f} Å away from {button_matrix.pos_j+1}, out of distance {max_interact_dist.value()}'
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
                    sequences=self.designable_sequences,
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

        save_mutant_choices(
            self.bus.get_value('ui.interact.input.to_mutant_txt'),
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

        lineEdit_current_pair_wt_score = (
            self.bus.ui.lineEdit_current_pair_wt_score
        )
        lineEdit_current_pair_mut_score = (
            self.bus.ui.lineEdit_current_pair_mut_score
        )

        external_scorer = self.bus.get_value('ui.interact.use_external_scorer')

        run_worker_thread_with_progress(self.refresh_sidechainsolver)

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
                    progress_bar=self.bus.ui.progressBar,
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

        visualizer.mutate_runner = self.sidechain_solver.mutate_runner

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

        mutant_obj: Mutant = extract_mutants_from_mutant_id(
            mutant_string=mutant,
            sequences=self.designable_sequences,
        )

        mutant_obj.wt_sequences = self.designable_sequences

        mut_score = (
            matrix[col][row]
            if not self.gremlin_external_scorer
            else self.gremlin_external_scorer.scorer(
                sequence=mutant_obj.get_mutant_sequence_single_chain(
                    chain_id=self.design_chain_id
                )
            )
        )
        mutant_obj.mutant_score = mut_score

        set_widget_value(lineEdit_current_pair_wt_score, f'{wt_score:.3f}')
        set_widget_value(lineEdit_current_pair_mut_score, f'{mut_score:.3f}')

        # update mutant id from Mutant object.
        mutant = mutant_obj.short_mutant_id

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
                self.bus.get_value('ui.header_panel.cmap.default'),
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
                visualizer.group_name: {mutant_obj.short_mutant_id: mutant_obj}
            }

            asyncio.run(
                self.ws_broadcast_from_server(
                    data=MutantTree(mutant_tree=mutant_tree),
                    data_type='MutantTree',
                )
            )

    def generate_ws_server_key(self):
        key = generate_strong_password(length=32)
        if key:
            self.bus.set_widget_value('ui.socket.input.key', key)

    def setup_ws_server(self):
        self.ws_server.setup_ws_server(
            ws_broadcast_view=self.bus.get_value('ui.socket.broadcast.view'),
            ws_server_use_key=self.bus.get_value('ui.socket.use_key'),
            ws_server_key=self.bus.get_value('ui.socket.input.key'),
            ws_server_port=(self.bus.get_value('ui.socket.server_port', int)),
            ws_view_broadcast_interval=(
                self.bus.get_value('ui.socket.broadcast.interval', float)
            ),
            treeWidget_ws_peers=self.bus.ui.treeWidget_ws_peers,
        )

    def update_ws_server_view_update_options(self):
        if not self.ws_server or not self.ws_server.is_running:
            logging.warning(f'Server is not in service.')
            return

        self.ws_server.view_broadcast_enabled = self.bus.get_value(
            'ui.socket.broadcast.view'
        )
        self.ws_server.view_broadcast_interval = self.bus.get_value(
            'ui.socket.broadcast.interval', float
        )

        if self.ws_server.view_broadcast_interval:
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

        if not self.ws_server.view_broadcast_interval:
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

            if self.bus.get_value('ui.socket.server_mode'):
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
            self.reload_molecule_info()

        self.ws_client.design_molecule = self.design_molecule
        self.ws_client.design_chain_id = self.design_chain_id
        self.ws_client.design_sequence = self.design_sequence
        self.ws_client.cmap = self.bus.get_value(
            'ui.header_panel.cmap.default'
        )
        self.ws_client.nproc = self.bus.get_value('ui.header_panel.nproc')
        self.ws_client.progress_bar = self.bus.ui.progressBar

        self.ws_client.setup_ws_client(
            lineEdit_ws_server_url_to_connect=self.bus.get_value(
                'ui.socket.input.hostname'
            ),
            spinBox_ws_server_port_to_connect=(
                self.bus.get_value('ui.socket.server_port', int)
            ),
            lineEdit_ws_server_key_to_connect=self.bus.get_value(
                'ui.socket.input.key'
            ),
            checkBox_ws_receive_view_broadcast=self.bus.get_value(
                'ui.socket.receive.view'
            ),
            checkBox_ws_receive_mutagenesis_broadcast=self.bus.get_value(
                'ui.socket.receive.mutagenesis'
            ),
            treeWidget_ws_peers=self.bus.ui.treeWidget_ws_peers,
        )
        run_worker_thread_with_progress(self.refresh_sidechainsolver)
        self.ws_client.sidechain_solver = self.sidechain_solver

    def update_ws_client_view_update_options(self):
        if not self.ws_client or not self.ws_client.connected:
            logging.warning(f'Client is not connected')
            return

        self.ws_client.receive_view_broadcast = self.bus.get_value(
            'ui.socket.receive.view'
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

    def reload_configurations(self, experiment: str = None):
        if self.bus:
            logging.warning(f'Reconfiguring with changes...')
            reconfigure = True
        else:
            logging.warning(f'Configuration initialized.')
            reconfigure = False

        if not reconfigure:
            # while booting
            # create a bus btw cfg<---> ui
            self.bus = ConfigBus(ui=self.ui)
            self.bus.initialize_widget_with_cfg_group()

        elif experiment:
            # while loading experiment
            expected_experiment_config = f'{experiment}.yaml'

            if os.path.exists(
                os.path.join(
                    EXPERIMENTS_CONFIG_DIR, expected_experiment_config
                )
            ):
                self.bus.cfg = reload_config_file(
                    config_name=f'experiments/{experiment}'
                )['experiments']
        else:
            # simply reload from default config, discard unsaved.
            self.bus.cfg = reload_config_file()

        self.refresh_ui_from_new_configuration()

    def refresh_ui_from_new_configuration(self):
        for (
            widget_id,
            config_item,
        ) in self.bus.w2c.widget_id2config_dict.items():
            widget = self.bus.get_widget_from_id(widget_id=widget_id)
            # print(f'Updating from cfg: {config_item} -> {widget_id} ->{widget}')
            set_widget_value(
                widget, OmegaConf.select(self.bus.cfg, config_item)
            )

    def save_configuration_from_ui(self, experiment: str = None):
        save_configuration(new_cfg=self.bus.cfg, config_name=experiment)

    def load_and_save_experiment(self, mode='r'):
        import shutil

        if not (mode == 'r' or mode == 'w'):
            return
        new_cfg_file = self.browse_filename(
            mode=mode,
            exts=[FileExtentions.ConfigFileExt, FileExtentions.AnyFileExt],
        )
        if not new_cfg_file:
            return
        new_cfg_base_name: str = os.path.basename(new_cfg_file)
        new_cfg_prefix = new_cfg_base_name.replace('.yaml', '')
        experiment_file = os.path.join(
            EXPERIMENTS_CONFIG_DIR, new_cfg_base_name
        )
        if mode == 'r':
            # copy cfg to experiment dir so that hydra can access it
            shutil.copy(new_cfg_file, experiment_file)
            self.reload_configurations(experiment=new_cfg_prefix)
            logging.warning(
                f'Load config from {new_cfg_file}, backup at {experiment_file}'
            )
        else:
            self.save_configuration_from_ui(
                experiment=f'experiments/{new_cfg_prefix}'
            )
            # hydra has already saved config into EXPERIMENTS_CONFIG_DIR, copy to user defined config file path
            shutil.copy(experiment_file, new_cfg_file)
            logging.warning(
                f'saved config at {new_cfg_file}, backup at {experiment_file}'
            )
