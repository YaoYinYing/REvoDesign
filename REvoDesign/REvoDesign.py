import asyncio
import gc
import os
import traceback

# using partial module to reduce duplicate code.
from functools import partial
from typing import Literal
from omegaconf import OmegaConf
from pymol import cmd
from pymol.Qt import QtCore, QtGui, QtWidgets

from REvoDesign import root_logger
from REvoDesign import VERSION
from REvoDesign import (
    reload_config_file,
    save_configuration,
    Widget2Widget,
    ConfigBus,
    EXPERIMENTS_CONFIG_DIR,
    FileExtentions,
)
from REvoDesign.application.i18n import LanguageSwitch


from REvoDesign.tools.utils import (
    extract_archive,
    generate_strong_password,
    run_worker_thread_with_progress,
)

from REvoDesign.tools.customized_widgets import (
    hold_trigger_button,
    getExistingDirectory,
    set_widget_value,
    decide,
    notify_box,
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
)

from REvoDesign.tools.mutant_tools import (
    determine_profile_type,
    existed_mutant_tree,
    get_mutant_table_columns,
    save_mutant_choices,
)

from REvoDesign.common.MultiMutantDesigner import MultiMutantDesigner

import warnings
from REvoDesign import issues

REPO_URL = "https://github.com/YaoYinYing/REvoDesign"

logging = None

IO_MODE = Literal['r', 'w']


class REvoDesignPlugin(QtWidgets.QWidget):
    def __init__(
        self,
    ):
        super(REvoDesignPlugin, self).__init__()
        # global reference to avoid garbage collection of our dialog
        self.window = None

        self.RUN_DIR = os.path.abspath(os.path.dirname(__file__))
        self.PWD = os.getcwd()

        self.ui_file = os.path.join(self.RUN_DIR, 'UI', 'REvoDesign.ui')
        self.widget2widget = Widget2Widget()
        self.bus = None

        self.designable_sequences = {}
        self.design_molecule = ''
        self.design_chain_id = ''
        self.design_sequence = ''

        self.gremlin_worker = None
        self.evaluator = None
        global logging
        logging = root_logger.getChild(self.__class__.__name__)

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
            warnings.warn(
                issues.DisabledFunctionWarning(
                    f'Teamwork is disabled. Please install the related requirements.'
                )
            )
            traceback.print_exc()
            self.teamwork_enabled = False

    def fix_wd(self):
        pwd_0 = os.getcwd()
        pwd_2 = (
            os.path.dirname(cmd.get('session_file'))
            if not is_empty_session()
            else None
        )

        # set session file's path if the rest is HOME, usually when a pse or pdb is opened to call PyMOL
        if pwd_2 and all(
            [
                os.path.abspath(pwd)
                == os.path.abspath(os.path.expanduser('~'))
                for pwd in [pwd_0]
            ]
        ):
            self.set_working_directory(pwd_2)
            return

        # otherwise, use the wd from PyMOL lauching, usually when PyMOL is called from command line with
        # an emtpy session or pdb/pse loading
        for pwd in [pwd_0]:
            if pwd and os.path.exists(pwd):
                self.set_working_directory(pwd)
                return

    def set_working_directory(self, dir=None):
        # if dir is specified yet same as the PWD, return silently.
        if dir and os.path.abspath(dir) == os.path.abspath(self.PWD):
            return

        if dir and os.path.exists(dir):
            self.PWD = dir
        else:
            self.PWD = getExistingDirectory()
        os.chdir(self.PWD)

    def run_plugin_gui(self):
        if self.window is None:
            self.window = self.make_window()
        self.window.show()
        self.fix_wd()

    def reinitialize(self, delete=False):
        self.gremlin_worker = None
        self.evaluator = None
        gc.collect()

        if delete:
            from REvoDesign import set_REvoDesign_config_file

            set_REvoDesign_config_file(delete_user_config_tree=True)
            warnings.warn(
                issues.ConflictWarning(
                    'Reinitialized with default configuration. Restart REvoDesign to take effort.'
                )
            )

    def __del__(self):
        # self.reinitialize()
        logging.warning('REvoDesign is shutting down.')
        if self.window:
            self.window = None

    # main function that makes the plugin window
    def make_window(self):
        installed_dir = os.path.dirname(__file__)
        logging.debug(f'REvoDesign is installed in {installed_dir}')

        main_window = QtWidgets.QMainWindow()

        from REvoDesign.UI import Ui_REvoDesignPyMOL_UI

        self.ui = Ui_REvoDesignPyMOL_UI()
        self.ui.setupUi(main_window)

        from REvoDesign.application.icon import IconSetter

        IconSetter(main_window=main_window)

        # create a bus btw cfg<---> ui
        self.reload_configurations()

        from REvoDesign.application.font import FontSetter

        FontSetter(main_window=main_window)

        # language switch for ui
        self.bus.ui.trans = QtCore.QTranslator(self)
        LanguageSwitch(window=main_window)

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

        self.bus.ui.actionReinitialize.triggered.connect(
            partial(self.reinitialize, delete=True)
        )

        self.bus.ui.actionSource_Code.triggered.connect(
            partial(
                QtGui.QDesktopServices.openUrl,
                QtCore.QUrl(REPO_URL),
            )
        )
        self.bus.ui.actionVersion.triggered.connect(
            partial(
                notify_box,
                message=f'REvoDesign v.{VERSION}\nSrc: {REPO_URL}',
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
        self.bus.set_widget_value('ui.header_panel.nproc', max_proc, hard=True)

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
            partial(self.coevoled_mutant_decision, False)
        )
        self.bus.button('interact_accept').clicked.connect(
            partial(self.coevoled_mutant_decision, True)
        )

        # Tab socket
        self.generate_ws_server_key()

        self.bus.button('ws_generate_randomized_key').clicked.connect(
            self.generate_ws_server_key
        )
        self.bus.get_widget_from_cfg_item(
            'ui.socket.use_key'
        ).stateChanged.connect(self.generate_ws_server_key)

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

    # class public function that can be shared with each tab
    # callback for the "Browse" button
    def browse_filename(
        self, mode: IO_MODE = 'r', exts=[FileExtentions.AnyFileExt]
    ):
        from pymol.Qt.utils import getSaveFileNameWithExt

        filter_strings = ';;'.join(
            [
                f'{ext_discrition} ( *.{ext_} )'
                for ext in exts
                for ext_, ext_discrition in ext.items()
            ]
        )

        if mode == 'w':
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
                confirmed = decide(
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
            warnings.warn(
                issues.EmptySessionWarning(
                    f'Current session is empty! Please load one PDB/PSE/PZE!'
                )
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
                warnings.warn(
                    issues.NoInputWarning(
                        'Abored recognizing sessions from input.'
                    )
                )
                return
            elif not os.path.exists(new_session_file):
                warnings.warn(
                    issues.NoInputWarning(
                        f'File does not exist: {new_session_file}.'
                    )
                )
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
            warnings.warn(
                issues.NoInputWarning(f"Invalid output path: {output_pse_fn}.")
            )

    def update_chain_id(self):
        molecule = self.bus.get_widget_value(
            'ui.header_panel.input.molecule', str
        )
        if not molecule:
            warnings.warn(
                issues.NoInputWarning('No available designable molecule!')
            )
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

            # TODO:
            '''
            omegaconf.errors.ConfigKeyError if trying to override a loaded designable sequences dict with another molecule
            '''
            self.bus.set_value(
                'designable_sequences', self.designable_sequences
            )

        self.setup_pssm_gremlin_calculator()

    def open_mutant_table(self, cfg_mutant_table: str, mode: IO_MODE = 'r'):
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
        else:
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

    def find_session_path(self) -> str:
        session_path: str = cmd.get('session_file')

        if not session_path:
            warnings.warn(
                issues.EmptySessionWarning(
                    'Session not found, please use a new session path to save.'
                )
            )
            return self.browse_filename(
                mode='w', exts=[FileExtentions.SessionFileExt]
            )

        if not os.path.exists(session_path):
            warnings.warn(
                issues.NoInputWarning(
                    'Invalid session file path, please use a new session path to save.'
                )
            )
            return self.browse_filename(
                mode='w', exts=[FileExtentions.SessionFileExt]
            )

        if os.path.basename(session_path).startswith(
            'tmp'
        ) and session_path.endswith('.pse'):
            warnings.warn(
                issues.InvalidSessionWarning(
                    f'Found temperal session path: {session_path}, please use a new session path to save.'
                )
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
        from REvoDesign.clients.PSSM_GREMLIN_client import (
            PSSMGremlinCalculator,
        )

        molecule = self.bus.get_widget_value(
            'ui.header_panel.input.molecule', str
        )
        chain_id = self.bus.get_widget_value(
            'ui.header_panel.input.chain_id', str
        )
        designable_sequences = self.bus.get_value('designable_sequences', dict)
        if not designable_sequences:
            return

        sequence = designable_sequences.get(chain_id)

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
        self.pssm_gremlin_calculator.url = self.bus.get_widget_value(
            'ui.client.pssm_gremlin_url', str
        )
        self.pssm_gremlin_calculator.user = self.bus.get_widget_value(
            'ui.client.pssm_gremlin_user', str
        )
        self.pssm_gremlin_calculator.password = self.bus.get_widget_value(
            'ui.client.pssm_gremlin_passwd', str
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

        small_molecules = ['']
        if more_hetatm := find_small_molecules_in_protein(
            self.design_molecule
        ):
            small_molecules.extend(more_hetatm)
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
        from REvoDesign.structure.SurfaceFinder import SurfaceFinder

        surfacefinder = SurfaceFinder(input_pse=self.temperal_session)

        surfacefinder.process_surface_residues()
        surfacefinder = None

    def run_pocket_detection(self):
        from REvoDesign.structure import PocketSearcher

        pocketsearcher = PocketSearcher(
            input_pse=self.temperal_session,
            save_dir=f'{self.PWD}/pockets/',
        )

        pocketsearcher.search_pockets()
        pocketsearcher = None

    # Tab `Mutate`
    def determine_profile_format(
        self, cfg_input_profile: str, cfg_profile_format: str
    ):
        _fp = self.bus.get_widget_value(cfg_input_profile, str)
        if _fp == 'None' or not _fp:
            return None

        profile_fp = os.path.abspath(_fp)

        if not os.path.exists(profile_fp):
            return None

        profile_format = determine_profile_type(profile_fp=profile_fp)
        if not profile_format:
            return

        self.bus.set_widget_value(cfg_profile_format, profile_format)

    def run_mutant_loading_from_profile(self):
        from REvoDesign.phylogenetics import MutateWorker

        trigger_button = self.bus.button('run_PSSM_to_pse')

        with hold_trigger_button(trigger_button):
            worker = MutateWorker(
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
        del worker

    # Tab `Evaluate`
    def set_pymol_session_rock(self):
        if not self.evaluator:
            return
        self.evaluator.set_pymol_session_rock()

    def initialize_design_candidates(
        self,
    ):
        from REvoDesign.evaluate import Evalutator

        self.evaluator = Evalutator()

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

        worker = ClusterRunner(
            bus=self.bus,
            PWD=self.PWD,
        )

        with hold_trigger_button(trigger_button):
            worker.run_clustering()

        del worker

    # Tab Visualize

    def update_mutant_table_columns(
        self,
    ):
        mut_table_fp = self.bus.get_widget_value(
            'ui.visualize.input.from_mutant_txt'
        )
        if not os.path.exists(mut_table_fp):
            warnings.warn(
                issues.NoInputWarning(
                    f'Mutant Table path is not valid: {mut_table_fp}'
                )
            )
            return

        mut_table_cols = get_mutant_table_columns(mutfile=mut_table_fp)

        if not mut_table_cols:
            warnings.warn(
                issues.BadDataWarning(
                    f'Mutant Table column names is not valid: {mut_table_cols}'
                )
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
            worker = VisualizingWorker(
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

        del worker

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
                confirmed = decide(
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
        with hold_trigger_button(self.bus.button('multi_design_initialize')):
            self.multi_mutagenesis_designer = MultiMutantDesigner()

    def multi_mutagenesis_design_start(self):
        if not self.multi_mutagenesis_designer:
            raise issues.UnexpectedWorkflowError(
                'Multi design is not initialized.'
            )

        with hold_trigger_button(
            self.bus.button('multi_design_start_new_design')
        ):
            self.multi_mutagenesis_designer.refresh_options()

            if (
                not self.multi_mutagenesis_designer.in_design_multi_design_case.empty
            ):
                logging.warning(
                    f'Your current mutant multi-mutagenesis will be discarded!'
                )

                # Ask whether to overide
                confirmed = decide(
                    title="Discard in-design mutant choice?",
                    description=f"You currently have uncompleted mutant choice, which shall be discarded. \n \
                        Are you really sure? ",
                )

                if not confirmed:
                    logging.warning(f'Cancelled.')
                    return
            self.multi_mutagenesis_designer.start_new_design()

    def multi_mutagenesis_design_pick_next_mut(self):
        if not self.multi_mutagenesis_designer:
            raise issues.UnexpectedWorkflowError(
                'Multi design is not initialized.'
            )

        with hold_trigger_button(self.bus.button('multi_design_right')):
            self.multi_mutagenesis_designer.refresh_options()
            self.multi_mutagenesis_designer.pick_next_mutant()

    def multi_mutagenesis_design_undo_picking(self):
        if not self.multi_mutagenesis_designer:
            raise issues.UnexpectedWorkflowError(
                'Multi design is not initialized.'
            )

        with hold_trigger_button(self.bus.button('multi_design_left')):
            self.multi_mutagenesis_designer.refresh_options()
            self.multi_mutagenesis_designer.undo_previous_mutant()

    def multi_mutagenesis_design_stop_design(self):
        if not self.multi_mutagenesis_designer:
            raise issues.UnexpectedWorkflowError(
                'Multi design is not initialized.'
            )

        with hold_trigger_button(
            self.bus.button('multi_design_end_this_design')
        ):
            self.multi_mutagenesis_designer.refresh_options()
            if self.multi_mutagenesis_designer.in_design_multi_design_case:
                self.multi_mutagenesis_designer.terminate_picking(
                    continue_design=False
                )

    def multi_mutagenesis_design_save_design(self):
        if not self.multi_mutagenesis_designer:
            raise issues.UnexpectedWorkflowError(
                'Multi design is not initialized.'
            )

        with hold_trigger_button(
            self.bus.button('multi_design_export_mutants_from_table')
        ):
            self.multi_mutagenesis_designer.export_designed_variant()

    def multi_mutagenesis_design_auto(self):
        trigger_button = self.bus.button('run_multi_design')

        # initialize
        self.multi_mutagenesis_design_initialize()
        if not self.multi_mutagenesis_designer:
            raise issues.UnexpectedWorkflowError(
                'Multi design failed in initializing.'
            )

        maximal_multi_design_variant_num = (
            self.multi_mutagenesis_designer.total_design_cases
        )

        maximal_mutant_num = self.multi_mutagenesis_designer.maximal_mutant_num
        self.multi_mutagenesis_designer.refresh_options()

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

        with hold_trigger_button(trigger_button):
            from REvoDesign.phylogenetics import GREMLIN_Analyser

            self.gremlin_worker = GREMLIN_Analyser(
                PWD=self.PWD,
            )
            self.gremlin_worker.load_gremlin_mrf()

    def run_gremlin_tool(self):
        if not self.gremlin_worker:
            return

        trigger_button = self.bus.button('run_interact_scan')

        with hold_trigger_button(trigger_button):
            self.gremlin_worker.run_gremlin_tool()

    def coevoled_mutant_decision(self, decision_to_accept):
        if not self.gremlin_worker:
            return
        self.gremlin_worker.coevoled_mutant_decision(accept=decision_to_accept)

    def generate_ws_server_key(self):
        use_key = self.bus.get_widget_value('ui.socket.use_key', str)
        if not use_key:
            return

        self.bus.set_widget_value(
            'ui.socket.input.key', generate_strong_password(length=32)
        )

    def setup_ws_server(self):
        self.generate_ws_server_key()
        self.ws_server.setup_ws_server()

    def update_ws_server_view_update_options(self):
        # not instantialized or not running
        if not self.ws_server or not self.ws_server.is_running:
            logging.warning(f'Server is not in service.')
            return

        # do changes
        self.ws_server.view_broadcast_enabled = self.bus.get_widget_value(
            'ui.socket.broadcast.view', bool
        )
        self.ws_server.view_broadcast_interval = self.bus.get_widget_value(
            'ui.socket.broadcast.interval', float
        )

        # disabled
        if not self.ws_server.view_broadcast_enabled:
            if self.ws_server.view_broadcast_on_air:
                self.ws_server.view_broadcast_worker.interrupt()
                self.ws_server.view_broadcast_on_air = False
                logging.warning('Stop broadcasting view.')
                return
            logging.warning(
                'Server is not broadcasting view changes. Do nothing.'
            )
            return

        # no clients
        if not self.ws_server.meetingroom:
            logging.warning(
                'Server has no client, ignore view updating. Do nothing.'
            )
            self.ws_server.view_broadcast_on_air = False
            return

        # already on air
        if self.ws_server.view_broadcast_on_air:
            logging.warning('Server is broadcasting view changes! Do nothing.')
            return

        # start broadcaster
        from REvoDesign.tools.customized_widgets import WorkerThread

        if not self.ws_server.view_broadcast_on_air:
            self.ws_server.view_broadcast_worker = WorkerThread(
                func=self.ws_server.broadcast_view
            )

        self.ws_server.view_broadcast_on_air = True
        self.ws_server.view_broadcast_worker.run()

        logging.warning('Start broadcasting view.')
        return

    # Assuming toggle_ws_server_mode gets triggered on checkBox_ws_server_mode state change
    def toggle_ws_server_mode(self):
        toggled = self.bus.get_widget_value('ui.socket.server_mode', bool)

        try:
            if not self.ws_server.initialized:
                from REvoDesign.clients.QtSocketConnector import (
                    REvoDesignWebSocketServer,
                )

                self.ws_server = REvoDesignWebSocketServer()

            if toggled:
                if self.ws_server.is_running:
                    logging.warning(
                        'Server is already in running state. Do nothing.'
                    )
                    return

                else:
                    logging.info('Server is launching...')
                    self.setup_ws_server()

            else:
                if not self.ws_server.is_running:
                    logging.warning('Server is already stopped. Do nothing.')
                    return
                self.ws_server.stop_server()
        except Exception as e:
            logging.warning(e)
            traceback.print_exc()

        logging.warning(
            f'Server status: {"ON" if self.ws_server.is_running else "OFF"}'
        )

    async def ws_broadcast_from_server(self, data, data_type: str):
        await self.ws_server.broadcast_object(data, data_type)

    def setup_ws_client(self):
        self.ws_client.setup_ws_client()

    def update_ws_client_view_update_options(self):
        if not self.ws_client or not self.ws_client.connected:
            logging.warning(f'Client is not connected')
            return

        self.ws_client.receive_view_broadcast = self.bus.get_widget_value(
            'ui.socket.receive.view', bool
        )

    def toggle_ws_client_connection(self, connect=True):
        try:
            if connect:
                self.ws_client_connect_to_server()
            else:
                self.ws_client_disconnect_from_server()
        except Exception as e:
            logging.warning(e)
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
        if not self.ws_client.initialized:
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
            ConfigBus.initialize(ui=self.ui)
            self.bus = ConfigBus()
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

    def load_and_save_experiment(self, mode: IO_MODE = 'r'):
        import shutil

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
