import asyncio
import os
import time
import traceback
from typing import Iterable, Union
from immutabledict import immutabledict
from omegaconf import OmegaConf
from pymol import cmd
from pymol.Qt import QtCore, QtGui, QtWidgets


# using partial module to reduce duplicate code.
from functools import partial
from REvoDesign.clients.PSSM_GREMLIN_client import PSSMGremlinCalculator

from REvoDesign.tools.logger import logging
from REvoDesign.application.ui_driver import (
    Widget2Widget,
    ConfigBus,
)

from REvoDesign.tools.post_installed import (
    save_configuration,
)

from REvoDesign.common.Mutant import Mutant
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
    extract_archive,
    generate_strong_password,
    run_worker_thread_with_progress,
    get_color,
    cmap_reverser,
    rescale_number,
)

from REvoDesign.tools.customized_widgets import (
    get_widget_value,
    hold_trigger_button,
    getExistingDirectory,
    set_widget_value,
    QbuttonMatrix,
    proceed_with_comfirm_msg_box,
    getOpenFileNameWithExt,
    create_cmap_icon,
    refresh_widget_while_another_changed,
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
        self.widget_config_map = None

        self.designable_sequences = {}
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

        self.ui.actionSet_Working_Directory.triggered.connect(
            self.set_working_directory
        )

        self.ui.actionReconfigure.triggered.connect(self.reload_configurations)
        self.ui.actionSave_Configurations.triggered.connect(
            self.save_configuration_from_ui
        )

        self.ui.actionSource_Code.triggered.connect(
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
            self.ui.tabWidget.setTabVisible(7, False)

        # Set up general input
        self.ui.comboBox_chain_id.currentIndexChanged.connect(
            self.set_design_sequence,
        )

        # read session from PyMOL. If it is empty, load one.
        self.ui.actionCheck_PyMOL_session.triggered.connect(
            self.reload_molecule_info,
        )

        # Update chain id
        self.ui.comboBox_design_molecule.currentIndexChanged.connect(
            self.update_chain_id,
        )

        # set up nproc
        from REvoDesign.tools.system_tools import CLIENT_INFO

        max_proc = CLIENT_INFO().nproc
        self.bus.set_widget_value('ui.header_panel.nproc', (1, max_proc))
        self.bus.set_widget_value('ui.header_panel.nproc', max_proc)
        self.bus.set_value('ui.header_panel.nproc', max_proc)

        

        # color map
        import matplotlib

        cmap_group = {
            _cmap: QtGui.QIcon(create_cmap_icon(cmap=_cmap))
            for _cmap in matplotlib.colormaps()
        }

        self.bus.set_widget_value(
            'ui.header_panel.cmap.default',
            cmap_group,
        )
        
        #set_widget_value(self.ui.comboBox_cmap, 'bwr_r')
        # self.bus.set_widget_value(
        #     'ui.header_panel.cmap.default',
        #     'bwr_r',
        # )
        self.bus.restore_widget_value('ui.header_panel.cmap.default')

        # Tab Client
        self.ui.comboBox_chain_id.currentIndexChanged.connect(
            self.setup_pssm_gremlin_calculator,
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
        # Tab `Prepare`

        self.ui.pushButton_open_output_pse_pocket.clicked.connect(
            partial(self.save_as_a_session, 'ui.prepare.input.pocket.to_pse')
        )

        self.ui.pushButton_open_output_pse_surface.clicked.connect(
            partial(self.save_as_a_session, 'ui.prepare.input.surface.to_pse')
        )

        self.ui.pushButton_run_surface_refresh.clicked.connect(
            self.update_surface_exclusion
        )

        self.ui.lineEdit_output_pse_surface.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.prepare.input.surface.to_pse',
                self.ui.pushButton_run_surface_detection,
            )
        )

        self.ui.lineEdit_output_pse_pocket.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.prepare.input.pocket.to_pse',
                self.ui.pushButton_run_pocket_detection,
            )
        )

        self.ui.comboBox_design_molecule.currentIndexChanged.connect(
            self.reload_determine_tab_setup,
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
            partial(self.save_as_a_session, 'ui.mutate.input.to_pse')
        )

        self.ui.pushButton_open_customized_indices.clicked.connect(
            partial(
                self.open_input_filepath,
                'ui.mutate.input.residue_ids',
                [TXT_FileExt, AnyFileExt],
            )
        )

        self.ui.pushButton_open_input_csv.clicked.connect(
            partial(
                self.open_input_filepath,
                'ui.mutate.input.profile',
                [PSSM_FileExt, AnyFileExt, CompressedFileExt],
            )
        )

        self.ui.lineEdit_input_csv.textChanged.connect(
            partial(
                self.determine_profile_format,
                'ui.mutate.input.profile',
                'ui.mutate.input.profile_type',
            )
        )

        self.ui.lineEdit_output_pse_mutate.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.mutate.input.to_pse',
                self.ui.pushButton_run_PSSM_to_pse,
            )
        )

        self.ui.pushButton_run_PSSM_to_pse.clicked.connect(
            self.run_mutant_loading_from_profile
        )

        # Tab `Evaluate`
        self.ui.pushButton_open_mut_table.clicked.connect(
            partial(
                self.open_mutant_table, 'ui.evaluate.input.to_mutant_txt', 'w'
            )
        )

        self.ui.lineEdit_output_mut_table.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.evaluate.input.to_mutant_txt',
                [
                    self.ui.pushButton_previous_mutant,
                    self.ui.pushButton_reject_this_mutant,
                    self.ui.pushButton_next_mutant,
                    self.ui.pushButton_accept_this_mutant,
                ],
            )
        )

        self.ui.checkBox_rock_pymol.stateChanged.connect(
            self.set_pymol_session_rock
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
                self.ui.progressBar,
                self.ui.comboBox_group_ids,
            )
        )

        self.ui.pushButton_goto_best_hit_in_group.clicked.connect(
            self.jump_to_the_best_mutant,
        )

        self.ui.pushButton_load_mutant_choice_checkpoint.clicked.connect(
            self.recover_mutant_choices_from_checkpoint,
        )

        self.ui.comboBox_group_ids.currentTextChanged.connect(
            self.jump_to_branch,
        )

        self.ui.comboBox_mutant_ids.currentTextChanged.connect(
            self.jump_to_a_mutant,
        )

        self.ui.pushButton_choose_lucky_mutant.clicked.connect(
            self.find_all_best_mutants,
        )

        # Tab `Cluster`

        self.ui.pushButton_open_mut_table_2.clicked.connect(
            partial(
                self.open_mutant_table, 'ui.cluster.input.from_mutant_txt', 'r'
            )
        )

        from Bio.Align import substitution_matrices

        score_matrix = [
            mtx
            for mtx in os.listdir(
                os.path.join(substitution_matrices.__path__[0], 'data')
            )
        ]

        self.bus.set_value('ui.cluster.score_matrix.group', score_matrix)

        self.bus.set_widget_value(
            'ui.cluster.score_matrix.default', score_matrix
        )

        self.ui.lineEdit_input_mut_table.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.cluster.input.from_mutant_txt',
                self.ui.pushButton_run_cluster,
            )
        )

        self.ui.pushButton_run_cluster.clicked.connect(self.run_clustering)

        # Tab Visualize

        self.ui.lineEdit_output_pse_visualize.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.visualize.input.to_pse',
                self.ui.pushButton_run_visualizing,
            )
        )

        self.ui.lineEdit_input_mut_table_csv.textChanged.connect(
            partial(
                self.bus.fp_lock,
                'ui.visualize.input.from_mutant_txt',
                [
                    self.ui.pushButton_save_this_mutant_table,
                    self.ui.pushButton_reduce_this_session,
                ],
            )
        )

        self.ui.pushButton_save_this_mutant_table.clicked.connect(
            partial(
                self.save_visualizing_mutant_tree,
                'ui.visualize.input.from_mutant_txt',
                'ui.visualize.input.group_name',
            )
        )

        self.ui.lineEdit_input_csv_2.textChanged.connect(
            partial(
                self.determine_profile_format,
                'ui.visualize.input.profile',
                'ui.visualize.input.profile_type',
            )
        )

        self.ui.pushButton_open_input_csv_2.clicked.connect(
            partial(
                self.open_input_filepath,
                'ui.visualize.input.profile',
                [PSSM_FileExt, AnyFileExt, CompressedFileExt],
            )
        )

        self.ui.pushButton_open_mut_table_csv.clicked.connect(
            partial(
                self.open_mutant_table,
                'ui.visualize.input.from_mutant_txt',
                'r',
            )
        )

        self.ui.lineEdit_input_mut_table_csv.textChanged.connect(
            self.update_mutant_table_columns,
        )

        self.ui.pushButton_open_output_pse_visualize.clicked.connect(
            partial(
                self.save_as_a_session,
                'ui.visualize.input.to_pse',
            )
        )

        self.bus.set_widget_value('ui.visualize.input.best_leaf', 'best_leaf')
        self.bus.set_widget_value(
            'ui.visualize.input.totalscore', 'totalscore'
        )

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
                self.bus.fp_lock,
                'ui.visualize.input.multi_design.to_mutant_txt',
                [
                    self.ui.pushButton_multi_design_export_mutants_from_table,
                    self.ui.pushButton_run_multi_design,
                ],
            )
        )

        self.ui.pushButton_open_mut_table_csv_2.clicked.connect(
            partial(
                self.open_mutant_table,
                'ui.visualize.input.multi_design.to_mutant_txt',
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
                'ui.interact.input.gremlin_pkl',
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
                'ui.interact.input.to_mutant_txt',
                'w',
            )
        )

        self.ui.pushButton_interact_reject.clicked.connect(
            self.coevoled_mutant_decision, False
        )
        self.ui.pushButton_interact_accept.clicked.connect(
            self.coevoled_mutant_decision, True
        )

        # Tab socket
        self.generate_ws_server_key()

        self.ui.pushButton_ws_generate_randomized_key.clicked.connect(
            self.generate_ws_server_key
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

        # Tab Config
        self.bus.set_widget_value(
            'ui.config.sidechain_solver.default',
            list(self.bus.cfg.ui.config.sidechain_solver.group),
        )

        self.ui.comboBox_sidechain_solver.currentIndexChanged.connect(
            partial(
                refresh_widget_while_another_changed,
                self.bus.get_widget('ui.config.sidechain_solver.default'),
                self.bus.get_widget('ui.config.sidechain_solver.model'),
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
    def open_input_filepath(self, cfg_input: str, exts=[AnyFileExt]):
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
                mode='r', exts=[SessionFileExt, PDB_FileExt, AnyFileExt]
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
            mode='w', exts=[SessionFileExt, AnyFileExt]
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
            input_mut_txt_fn = self.open_input_filepath(
                cfg_mutant_table,
                [MutableFileExt, AnyFileExt, CompressedFileExt],
            )
            if input_mut_txt_fn:
                self.bus.set_widget_value(cfg_mutant_table, input_mut_txt_fn)
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
                self.bus.set_widget_value(cfg_mutant_table, output_mut_txt_fn)
            else:
                logging.warning(f"Invalid output path: {output_mut_txt_fn}.")
        else:
            logging.warning(f'Unknown mode {mode} ! Aborded.')

    def write_input_mutant_table(self, output_mut_txt_fn, mutant_list):
        open(output_mut_txt_fn, 'w').write(
            '\n'.join(mutant_list) if mutant_list else ''
        )

    def save_mutant_choices(
        self, cfg_output_mut_txt: str, mutant_tree: MutantTree
    ):
        if not mutant_tree:
            logging.error(f"No Mutant tree is given!")
            return

        if mutant_tree.empty:
            logging.warning(f'mutant tree is empty. save nothing.')
            return

        mutants_to_save = mutant_tree.all_mutant_ids
        logging.info(f"saving: {mutants_to_save}")

        # TODO mutant_choices function
        output_mut_txt_fn = self.bus.get_value(cfg_output_mut_txt)
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
                        pymol_object=mt, sequences=self.designable_sequences
                    ).full_mutant_id
                    for mt in mutants_to_save
                ],
            )

        else:
            logging.info(f'Mutant table is created at {output_mut_txt_fn}')
            self.write_input_mutant_table(
                output_mut_txt_fn,
                [
                    extract_mutant_from_pymol_object(
                        pymol_object=mt, sequences=self.designable_sequences
                    ).full_mutant_id
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

    def set_pymol_session_rock(self):
        cmd.set('rock', self.bus.get_value('ui.evaluate.rock'))

    def center_design_area(self, mutant_id):
        if self.mutant_tree_pssm and mutant_id:
            logging.debug(f'Centering design area: {mutant_id}')
            cmd.center(mutant_id)
        else:
            logging.debug(f'Giving up centering design area: {mutant_id}')

    def find_session_path(self) -> str:
        session_path: str = cmd.get('session_file')

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
            self.bus.get_widget(
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
        input_file = self.temperal_session
        output_file = self.bus.get_value('ui.prepare.input.surface.to_pse')

        exclusion = self.bus.get_value('ui.prepare.input.surface.exclusion')
        cutoff = self.bus.get_value('ui.prepare.surface_probe_radius', float)
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
        output_file = self.bus.get_value('ui.prepare.input.pocket.to_pse')
        ligand = self.bus.get_value('ui.prepare.input.pocket.substrate')
        cofactor = self.bus.get_value('ui.prepare.input.pocket.cofactor')
        ligand_radius = self.bus.get_value('ui.prepare.ligand_radius', float)
        cofactor_radius = self.bus.get_value(
            'ui.prepare.cofactor_radius', float
        )

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
    def determine_profile_format(
        self, cfg_input_profile: str, cfg_profile_format: str
    ):
        _fp = self.bus.get_value(cfg_input_profile)
        if _fp == 'None' or not _fp:
            return None

        profile_fp = os.path.abspath(_fp)

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
        else:
            return

        self.bus.set_widget_value(cfg_profile_format, profile_format)

    def run_mutant_loading_from_profile(self):
        trigger_button = self.ui.pushButton_run_PSSM_to_pse

        with hold_trigger_button(trigger_button):
            try:
                design_profile = self.bus.get_value('ui.mutate.input.profile')
                design_profile_format = self.bus.get_value(
                    'ui.mutate.input.profile_type'
                )
                preffered = self.bus.get_value('ui.mutate.accept')
                rejected = self.bus.get_value('ui.mutate.reject')

                temperature = self.bus.get_value(
                    'ui.mutate.designer.temperature', float
                )
                num_designs = self.bus.get_value(
                    'ui.mutate.designer.num_sample', int
                )
                batch = self.bus.get_value('ui.mutate.designer.batch', int)
                homooligomeric = self.bus.get_value(
                    'ui.mutate.designer.homooligomeric'
                )
                deduplicate_designs = self.bus.get_value(
                    'ui.mutate.designer.deduplicate_designs'
                )
                randomized_sample = self.bus.get_value(
                    'ui.mutate.designer.enable_randomized_sampling'
                )
                randomized_sample_num = self.bus.get_value(
                    'ui.mutate.designer.randomized_sampling', int
                )
                design_case = self.bus.get_value('ui.mutate.input.design_case')
                custom_indices_fp = self.bus.get_value(
                    'ui.mutate.input.residue_ids'
                )
                cutoff = [
                    (self.bus.get_value('ui.mutate.min_score', float)),
                    (self.bus.get_value('ui.mutate.max_score', float)),
                ]
                reversed_mutant_effect = self.bus.get_value(
                    'ui.mutate.reverse_score'
                )
                output_pse = self.bus.get_value('ui.mutate.input.to_pse')
                nproc = self.bus.get_value('ui.header_panel.nproc', int)

                cmap = cmap_reverser(
                    cmap=self.bus.get_value('ui.header_panel.cmap.default'),
                    reverse=reversed_mutant_effect,
                )

                sidechain_solver = self.bus.get_value(
                    'ui.config.sidechain_solver.default'
                )
                sidechain_solver_radius = self.bus.get_value(
                    'ui.config.sidechain_solver.repack_radius', float
                )
                sidechain_solver_model = self.bus.get_value(
                    'ui.config.sidechain_solver.model'
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

                design.sidechain_solver = sidechain_solver
                design.sidechain_solver_radius = sidechain_solver_radius
                design.sidechain_solver_model = sidechain_solver_model

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
    def activate_focused(self):
        molecule = self.design_molecule
        chain_id = self.design_chain_id

        logging.debug(
            f'Current Mutant ID: {self.mutant_tree_pssm.current_mutant_id}'
        )

        if molecule and chain_id:
            mut_obj = extract_mutant_from_pymol_object(
                pymol_object=self.mutant_tree_pssm.current_mutant_id,
                sequences=self.designable_sequences,
            )
            resi = mut_obj.mutant_info[0]['position']

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
            if self.bus.get_value('ui.evaluate.show_wt') and resi:
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
            'ui.evaluate.input.to_mutant_txt', self.mutant_tree_pssm_selected
        )

    def walk_mutant_groups(
        self,
        walk_to_next,
        progressBar_mutant_choosing,
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

        self.activate_focused()
        logging.info(
            f'Walked to the {"next" if walk_to_next else "previous"} mutant {current_mutant_id}.'
        )

    def jump_to_branch(
        self,
    ):
        comboBox_group_ids = self.ui.comboBox_group_ids
        comboBox_mutant_ids = self.ui.comboBox_mutant_ids
        progressBar_mutant_choosing = self.ui.progressBar

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
    ):
        comboBox_group_ids = self.ui.comboBox_group_ids
        comboBox_mutant_ids = self.ui.comboBox_mutant_ids
        progressBar_mutant_choosing = self.ui.progressBar

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

        self.activate_focused()

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
    ):
        comboBox_group_ids = self.ui.comboBox_group_ids
        comboBox_mutant_ids = self.ui.comboBox_mutant_ids
        if self.mutant_tree_pssm.empty:
            return

        branch_id = comboBox_group_ids.currentText()

        best_mutant_id = (
            self.mutant_tree_pssm._jump_to_the_best_mutant_in_branch(
                branch_id=branch_id,
                reversed=self.bus.get_value('ui.evaluate.reverse_score'),
            )
        )
        logging.info(f'Jump to the best hit of {branch_id}: {best_mutant_id}')

        set_widget_value(comboBox_mutant_ids, best_mutant_id)

    def find_all_best_mutants(
        self,
    ):
        comboBox_group_ids = self.ui.comboBox_group_ids
        comboBox_mutant_ids = self.ui.comboBox_mutant_ids
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
                    reversed=self.bus.get_value('ui.evaluate.reverse_score'),
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
            pymol_object=mutant, sequences=self.designable_sequences
        )
        return _mutant_obj is not None

    def recover_mutant_choices_from_checkpoint(
        self,
    ):
        lcdNumber_selected_mutant = self.ui.lcdNumber_selected_mutant
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
        progressBar_mutant_choosing,
        comboBox_group_ids,
    ):
        lineEdit_output_mut_txt = self.bus.get_widget(
            'ui.evaluate.input.to_mutant_txt'
        )
        self.mutant_tree_pssm = existed_mutant_tree(
            sequences=self.designable_sequences, enabled_only=0
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

        self.activate_focused()

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
            )
        )

        pushButton_previous_mutant.clicked.connect(
            partial(
                self.walk_mutant_groups,
                False,
                progressBar_mutant_choosing,
            )
        )

    # combination and clustering
    def run_clustering(self):
        trigger_button = self.ui.pushButton_run_cluster

        # lazy module loading to fasten plugin initializing
        from REvoDesign.clusters.combine_positions import Combinations
        from REvoDesign.clusters.cluster_sequence import Clustering

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

        with hold_trigger_button(trigger_button):
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
    ):
        mut_table_fp = self.bus.get_value('ui.visualize.input.from_mutant_txt')
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
                comboBox_best_leaf = self.bus.get_widget(
                    'ui.visualize.input.best_leaf'
                )
                comboBox_totalscore = self.bus.get_widget(
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

        self.save_mutant_choices(
            cfg_mutant_table_fp,
            self.visualizing_mutant_tree,
        )

    def visualize_mutants(self):
        trigger_button = self.ui.pushButton_run_visualizing
        input_mut_table_csv = self.bus.get_value(
            'ui.visualize.input.from_mutant_txt'
        )

        output_pse = self.bus.get_value('ui.visualize.input.to_pse')
        best_leaf = self.bus.get_value('ui.visualize.input.best_leaf')
        totalscore = self.bus.get_value('ui.visualize.input.totalscore')
        nproc = self.bus.get_value('ui.header_panel.nproc', int)
        group_name = self.bus.get_value('ui.visualize.input.group_name')

        sidechain_solver = self.bus.get_value(
            'ui.config.sidechain_solver.default'
        )
        sidechain_solver_radius = self.bus.get_value(
            'ui.config.sidechain_solver.repack_radius', int
        )
        sidechain_solver_model = self.bus.get_value(
            'ui.config.sidechain_solver.model'
        )

        use_global_scores = self.bus.get_value(
            'ui.visualize.global_score_policy'
        )

        with hold_trigger_button(trigger_button):
            try:
                reversed_mutant_effect = self.bus.get_value(
                    'ui.visualize.reverse_score'
                )
                cmap = cmap_reverser(
                    cmap=self.bus.get_value('ui.header_panel.cmap.default'),
                    reverse=reversed_mutant_effect,
                )

                design_profile = self.bus.get_value(
                    'ui.visualize.input.profile'
                )
                design_profile_format = self.bus.get_value(
                    'ui.visualize.input.profile_type'
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
                    wd=os.path.join(
                        os.path.dirname(output_pse), 'temperal_pdb'
                    ),
                    reload=False,
                )
                visualizer.nproc = nproc
                visualizer.parallel_run = nproc > 1
                visualizer.sequence = self.design_sequence

                visualizer.consider_global_score_from_profile = (
                    use_global_scores
                )

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

                visualizer.sidechain_solver = sidechain_solver
                visualizer.sidechain_solver_radius = sidechain_solver_radius
                visualizer.sidechain_solver_model = sidechain_solver_model
                visualizer.setup_side_chain_solver()

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

        self.multi_mutagenesis_designer.cmap = self.bus.get_value('ui.header_panel.cmap.default')

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
        trigger_button = self.ui.pushButton_reinitialize_interact
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

    def run_gremlin_tool(self):
        trigger_button = self.ui.pushButton_run_interact_scan

        progress_bar = self.ui.progressBar
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
        ignore_wt = self.bus.get_value('ui.interact.interact_ignore_wt')
        max_interact_dist = self.bus.get_value(
            'ui.interact.max_interact_dist', float
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
                ignore_wt.isChecked(),
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

        self.save_mutant_choices(
            'ui.interact.input.to_mutant_txt',
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

        external_scorer = self.bus.get_value('ui.interact.use_external_scorer')

        sidechain_solver = self.bus.get_value(
            'ui.config.sidechain_solver.default'
        )
        sidechain_solver_radius = self.bus.get_value(
            'ui.config.sidechain_solver.repack_radius', float
        )
        sidechain_solver_model = self.bus.get_value(
            'ui.config.sidechain_solver.model'
        )

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

        visualizer.sidechain_solver = sidechain_solver
        visualizer.sidechain_solver_radius = sidechain_solver_radius
        visualizer.sidechain_solver_model = sidechain_solver_model

        visualizer.setup_side_chain_solver()

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
            treeWidget_ws_peers=self.ui.treeWidget_ws_peers,
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
        self.ws_client.progress_bar = self.ui.progressBar

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
            treeWidget_ws_peers=self.ui.treeWidget_ws_peers,
        )

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

    def reload_configurations(self):
        if self.bus:
            logging.warning(f'Reconfiguring with changes...')
            reconfigure=True
        else:
            logging.warning(f'Configuration initialized.')
            reconfigure=False
        # create a bus btw cfg<---> ui
        self.bus = ConfigBus(ui=self.ui)
        if not reconfigure:
            self.bus.fill_widget_with_cfg_group()

        # mapping ui widgets <--> cfg.elements
        self.widget_config_map: immutabledict = self.bus.w2c.widget2config_dict
        self.refresh_ui_from_new_configuration()

    def refresh_ui_from_new_configuration(self):
        for widget, config_item in self.widget_config_map.items():
            set_widget_value(
                widget, OmegaConf.select(self.bus.cfg, config_item)
            )

    def save_configuration_from_ui(self):
        from REvoDesign.tools.customized_widgets import get_widget_value

        # print(self.widget_config_mapper.widget2config_dict)
        for (
            widget,
            config_item,
        ) in self.bus.w2c.widget2config_dict.items():
            value = get_widget_value(widget=widget)
            logging.debug(f'Save {config_item}: {value}')
            OmegaConf.update(self.bus.cfg, config_item, value)

        save_configuration(new_cfg=self.bus.cfg)
