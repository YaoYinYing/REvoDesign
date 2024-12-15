'''
Main Module for REvoDesign
'''

import asyncio
import gc
import os
import shutil
import tempfile
import traceback
import warnings
# using partial module to reduce duplicate code.
from functools import partial
from typing import Any, Mapping, Optional

from omegaconf import OmegaConf
from pymol import cmd
from pymol.Qt import QtCore, QtGui, QtWidgets  # type: ignore
# from pymol.Qt.utils import loadUi
from requests.auth import HTTPBasicAuth
from RosettaPy.common.mutation import RosettaPyProteinSequence

import REvoDesign
from REvoDesign import (ConfigBus, FileExtentions, issues, reload_config_file,
                        save_configuration, set_REvoDesign_config_file)
from REvoDesign.application.font import FontSetter
from REvoDesign.application.i18n import LanguageSwitch
from REvoDesign.application.icon import IconSetter
from REvoDesign.basic import MenuActionServerMonitor, MenuCollection, MenuItem
from REvoDesign.bootstrap import EXPERIMENTS_CONFIG_DIR, REVODESIGN_CONFIG_FILE
from REvoDesign.clients.PSSM_GREMLIN_client import PSSMGremlinCalculator
from REvoDesign.clients.QtSocketConnector import (REvoDesignWebSocketClient,
                                                  REvoDesignWebSocketServer)
from REvoDesign.clusters import ClusterRunner
from REvoDesign.common.MultiMutantDesigner import MultiMutantDesigner
from REvoDesign.driver.environ_register import (add_new_environment_variables,
                                                drop_environment_variables,
                                                register_environment_variables)
from REvoDesign.driver.file_dialog import IO_MODE, FileDialog
from REvoDesign.driver.param_toggle_register import ParamChangeCollections
from REvoDesign.editor import menu_edit_file
from REvoDesign.editor.monaco.server import ServerControl
from REvoDesign.evaluate import Evalutator
from REvoDesign.logger import LoggerT, root_logger
from REvoDesign.phylogenetics import (GREMLIN_Analyser, MutateWorker,
                                      VisualizingWorker)
from REvoDesign.shortcuts.shortcut_tools import (menu_color_by_plddt,
                                                 menu_dump_sidechains,
                                                 menu_pssm2csv,
                                                 menu_pssm_design,
                                                 menu_real_sc,
                                                 menu_smiles_conformer_batch,
                                                 menu_smiles_conformer_single)
from REvoDesign.structure import PocketSearcher, SurfaceFinder
from REvoDesign.tools.customized_widgets import (WorkerThread, decide,
                                                 getExistingDirectory,
                                                 hold_trigger_button,
                                                 notify_box, set_widget_value)
from REvoDesign.tools.mutant_tools import (determine_profile_type,
                                           existed_mutant_tree,
                                           get_mutant_table_columns,
                                           save_mutant_choices)
from REvoDesign.tools.pymol_utils import (
    fetch_exclusion_expressions, find_all_protein_chain_ids_in_protein,
    find_design_molecules, find_small_molecules_in_protein,
    get_molecule_sequence, is_empty_session)
from REvoDesign.tools.system_tools import check_mac_rosetta2
from REvoDesign.tools.utils import (generate_strong_password,
                                    run_worker_thread_with_progress, timing)
from REvoDesign.UI import Ui_REvoDesignPyMOL_UI

REPO_URL = "https://github.com/YaoYinYing/REvoDesign"

# only when the window is activated by user can this logger be initialized.
logging: LoggerT = None  # type: ignore


class REvoDesignPlugin(QtWidgets.QWidget):
    def __init__(
        self,
    ):
        super().__init__()
        # global reference to avoid garbage collection of our dialog
        self.window = None

        self.RUN_DIR = os.path.abspath(os.path.dirname(__file__))
        self.PWD = os.getcwd()

        self.bus: ConfigBus = None  # type: ignore
        self.file_dialog: FileDialog = None  # type: ignore

        self.designable_sequences: RosettaPyProteinSequence = None  # type: ignore
        self.design_molecule = ""
        self.design_chain_id = ""
        self.design_sequence = ""

        self.gremlin_worker = None
        self.evaluator = None
        global logging
        logging = root_logger.getChild(self.__class__.__name__)

        self.pssm_gremlin_calculator = PSSMGremlinCalculator()

        self.multi_designer = None

        try:
            # if QtWebsockets is available, teamwork is activated.
            from PyQt5 import QtWebSockets  # type: ignore

            logging.info(f"Find QtWebSockets in {QtWebSockets.__file__}")

            self.teamwork_enabled = True
        except ImportError:
            warnings.warn(
                issues.DisabledFunctionWarning(
                    "Teamwork is disabled. Please install PyQt5."
                )
            )
            traceback.print_exc()
            self.teamwork_enabled = False

    def fix_wd(self):
        pwd_0 = os.getcwd()
        pwd_2 = (
            os.path.dirname(cmd.get("session_file"))
            if not is_empty_session()
            else None
        )

        # set session file's path if the rest is HOME,
        # usually when a pse or pdb is opened to call PyMOL
        if pwd_2 and all(
            [
                os.path.abspath(pwd)
                == os.path.abspath(os.path.expanduser("~"))
                for pwd in [pwd_0]
            ]
        ):
            self.set_working_directory(pwd_2)
            return

        # otherwise, use the wd from PyMOL lauching,
        # usually when PyMOL is called from command line with
        # an emtpy session or pdb/pse loading
        for pwd in [pwd_0]:
            if pwd and os.path.exists(pwd):
                self.set_working_directory(pwd)
                return

    def set_working_directory(self, new_dir: Optional[str] = None):
        """Set working directory for the current REvoDesign Session

        Args:
            new_dir (str, optional): new directory to set as CWD.
                Defaults to None.
        """
        # if dir is specified yet same as the PWD, return silently.
        if new_dir and os.path.abspath(new_dir) == os.path.abspath(self.PWD):
            self.bus.set_value("work_dir", os.path.abspath(self.PWD))
            return

        if new_dir and os.path.exists(new_dir):
            self.PWD = new_dir
        else:
            PWD = getExistingDirectory()
            if not PWD:
                return
            self.PWD=PWD

        os.chdir(self.PWD)

        self.bus.set_value("work_dir", os.path.abspath(self.PWD))

    def run_plugin_gui(self):
        """PyMOL entry for running the plugin"""
        if self.window is None:
            self.window = self.make_window()
        self.window.show()
        self.fix_wd()

        self.file_dialog = FileDialog(self.window, self.PWD)

    def reinitialize(self, delete: bool = False):
        """_summary_

        Args:
            delete (bool, optional): Delete user configurations.
                Defaults to False.
        """
        self.multi_designer = None
        self.pssm_gremlin_calculator = None

        self.gremlin_worker = None
        self.evaluator = None
        self.ws_server = None
        self.ws_client = None

        self.window = None

        gc.collect()

        if delete:
            if decide(
                "DANGEROUS!!!",
                "You are reinitializing REvoDesign by DELETING the user configuration file.",
            ):
                set_REvoDesign_config_file(delete_user_config_tree=True)
                warnings.warn(
                    issues.ConflictWarning(
                        "Reinitialized with default configuration. "
                        "Restart REvoDesign to take effort."
                    )
                )

    def __del__(self):
        """Shutting down."""
        # self.reinitialize()
        logging.warning("REvoDesign is shutting down.")
        if self.window:
            self.window = None

    # main function that makes the plugin window
    def make_window(self):
        """make new window

        Returns:
            QtWidgets.QMainWindow: new main window object
        """
        installed_dir = os.path.dirname(__file__)
        logging.debug(f"REvoDesign is installed in {installed_dir}")
        check_mac_rosetta2()

        main_window = QtWidgets.QMainWindow()

        # loadUi fails on translations so we have to compile the form as `Ui_REvoDesignPyMOL_UI`
        # ui_file=os.path.join(installed_dir, 'UI','REvoDesign.ui')
        # self.ui=loadUi(ui_file, main_window)

        self.ui = Ui_REvoDesignPyMOL_UI()
        self.ui.setupUi(main_window)

        IconSetter(main_window=main_window)

        # create a bus btw cfg<---> ui
        self.reload_configurations()
        # all ConfigBus related method calls must follow this
        # since the bus is initialized here

        FontSetter(main_window=main_window)

        # language switch for ui
        self.bus.ui.trans = QtCore.QTranslator(self)
        LanguageSwitch(window=main_window)

        # Set up Menu
        MenuCollection(
            (
                MenuItem(
                    self.bus.ui.actionSet_Working_Directory,
                    self.set_working_directory,
                ),
                MenuItem(
                    self.bus.ui.actionReconfigure,
                    self.reload_configurations,
                ),
                MenuItem(
                    self.bus.ui.actionEdit_Configuration,
                    menu_edit_file,
                    {'file_path': REVODESIGN_CONFIG_FILE}
                ),
                MenuItem(
                    self.bus.ui.actionSave_Configurations,
                    self.save_configuration_from_ui,
                    {'experiment': "global_config"}
                ),
                MenuItem(
                    self.bus.ui.action_LoadExperiment,
                    self.load_and_save_experiment,
                    {'mode': "r"},
                ),
                MenuItem(
                    self.bus.ui.action_Save_to_Experiment,
                    self.load_and_save_experiment,
                    {'mode': "w"},
                ),
                MenuItem(
                    self.bus.ui.actionReinitialize,
                    self.reinitialize,
                    {'delete': True},
                ),
                MenuItem(
                    self.bus.ui.actionAddEnvironVar,
                    add_new_environment_variables,
                ),
                MenuItem(
                    self.bus.ui.actionDropEnvironVar,
                    drop_environment_variables,
                ),
                MenuItem(
                    self.bus.ui.actionRenderPickedSidechainGroup,
                    menu_dump_sidechains,
                    {'dump_all': False},
                ),
                MenuItem(
                    self.bus.ui.actionRenderAllSidechains,
                    menu_dump_sidechains,
                    {'dump_all': True},
                ),
                MenuItem(
                    self.bus.ui.actionColor_by_pLDDT,
                    menu_color_by_plddt
                ),
                MenuItem(
                    self.bus.ui.actionShow_Real_Sidechain,
                    menu_real_sc
                ),
                MenuItem(
                    self.bus.ui.actionPSSM_to_CSV,
                    menu_pssm2csv
                ),
                MenuItem(
                    self.bus.ui.actionSMILES_Conformers,
                    menu_smiles_conformer_single
                ),
                MenuItem(
                    self.bus.ui.actionSMILES_Conformers_Batch,
                    menu_smiles_conformer_batch
                ),
                MenuItem(
                    self.bus.ui.actionProfile_Design,
                    menu_pssm_design
                ),
                MenuItem(
                    self.bus.ui.actionSource_Code,
                    QtGui.QDesktopServices.openUrl,
                    {'url': QtCore.QUrl(REPO_URL)}
                ),
                MenuItem(
                    self.bus.ui.actionVersion,
                    notify_box,
                    {'message': f"REvoDesign v.{REvoDesign.__version__}\nSrc: {REPO_URL}"}
                )
            ),
        )

        MenuActionServerMonitor(ServerControl, self.bus.ui.actionStartEditor, self.bus.ui.actionStopEditor)

        if self.teamwork_enabled:
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

        max_proc = os.cpu_count()
        if max_proc is None:
            max_proc = 4  # fallback to use default nproc
        self.bus.set_widget_value("ui.header_panel.nproc", (1, max_proc))
        self.bus.set_widget_value("ui.header_panel.nproc", max_proc, hard=True)

        # Tab Client
        self.bus.ui.comboBox_chain_id.currentIndexChanged.connect(
            self.setup_pssm_gremlin_calculator,
        )

        self.bus.button("submit_pssm_gremlin_job").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_calc,
                opt="submit",
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button("cancel_pssm_gremlin_job").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_calc,
                opt="cancel",
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button("download_pssm_gremlin_job").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.pssm_gremlin_calculator.submit_calc,
                opt="download",
                progress_bar=self.bus.ui.progressBar,
            )
        )

        # Set up general arguments
        # Tab `Prepare`

        self.bus.button("open_output_pse_pocket").clicked.connect(
            partial(self.save_as_a_session, "ui.prepare.input.pocket.to_pse")
        )

        self.bus.button("open_output_pse_surface").clicked.connect(
            partial(self.save_as_a_session, "ui.prepare.input.surface.to_pse")
        )

        self.bus.button("run_surface_refresh").clicked.connect(
            self.update_surface_exclusion
        )

        self.bus.ui.lineEdit_output_pse_surface.textChanged.connect(
            partial(
                self.bus.fp_lock,
                ("ui.prepare.input.surface.to_pse",),
                ("run_surface_detection",)
            )
        )

        self.bus.ui.lineEdit_output_pse_pocket.textChanged.connect(
            partial(
                self.bus.fp_lock,
                ("ui.prepare.input.pocket.to_pse",),
                ("run_pocket_detection",)
            )
        )

        self.bus.ui.comboBox_design_molecule.currentIndexChanged.connect(
            self.reload_determine_tab_setup,
        )

        # Connect run buttons
        self.bus.button("dump_interfaces").clicked.connect(
            self.run_chain_interface_detection
        )
        self.bus.button("run_surface_detection").clicked.connect(
            self.run_surface_detection
        )
        self.bus.button("run_pocket_detection").clicked.connect(
            self.run_pocket_detection
        )

        # Tab `Mutate`

        self.bus.button("open_output_pse_mutate").clicked.connect(
            partial(self.save_as_a_session, "ui.mutate.input.to_pse")
        )

        self.bus.ui.lineEdit_input_csv.textChanged.connect(
            partial(
                self.determine_profile_format,
                "ui.mutate.input.profile",
                "ui.mutate.input.profile_type",
            )
        )

        self.bus.ui.lineEdit_output_pse_mutate.textChanged.connect(
            partial(
                self.bus.fp_lock,
                ("ui.mutate.input.to_pse",),
                ("run_PSSM_to_pse",)
            )
        )

        self.bus.button("run_PSSM_to_pse").clicked.connect(
            self.run_mutant_loading_from_profile
        )

        # Tab `Evaluate`

        self.bus.ui.lineEdit_output_mut_table.textChanged.connect(
            partial(
                self.bus.fp_lock,
                ("ui.evaluate.input.to_mutant_txt",),
                (
                    "previous_mutant",
                    "reject_this_mutant",
                    "next_mutant",
                    "accept_this_mutant",
                ),
            )
        )

        self.bus.ui.checkBox_rock_pymol.stateChanged.connect(
            self.set_pymol_session_rock
        )

        self.bus.button("reinitialize_mutant_choosing").clicked.connect(
            self.initialize_design_candidates,
        )

        self.bus.button("goto_best_hit_in_group").clicked.connect(
            self.jump_to_the_best_mutant,
        )

        self.bus.button("load_mutant_choice_checkpoint").clicked.connect(
            self.recover_mutant_choices_from_checkpoint,
        )

        self.bus.ui.comboBox_group_ids.currentTextChanged.connect(
            self.jump_to_branch,
        )

        self.bus.ui.comboBox_mutant_ids.currentTextChanged.connect(
            self.jump_to_a_mutant,
        )

        self.bus.button("choose_lucky_mutant").clicked.connect(
            self.find_all_best_mutants,
        )

        # Tab `Cluster`

        self.bus.ui.lineEdit_input_mut_table.textChanged.connect(
            partial(
                self.bus.fp_lock,
                ("ui.cluster.input.from_mutant_txt",),
                ("run_cluster",)
            )
        )

        self.bus.button("run_cluster").clicked.connect(self.run_clustering)

        # Tab Visualize

        self.bus.ui.lineEdit_output_pse_visualize.textChanged.connect(
            partial(
                self.bus.fp_lock,
                ("ui.visualize.input.to_pse",),
                ("run_visualizing",)
            )
        )

        self.bus.ui.lineEdit_input_mut_table_csv.textChanged.connect(
            partial(
                self.bus.fp_lock,
                ("ui.visualize.input.from_mutant_txt",),
                (
                    "save_this_mutant_table",
                    "reduce_this_session",
                ),
            )
        )

        self.bus.button("save_this_mutant_table").clicked.connect(
            partial(
                self.save_visualizing_mutant_tree,
                "ui.visualize.input.from_mutant_txt",
                "ui.visualize.input.group_name",
            )
        )

        self.bus.ui.lineEdit_input_csv_2.textChanged.connect(
            partial(
                self.determine_profile_format,
                "ui.visualize.input.profile",
                "ui.visualize.input.profile_type",
            )
        )

        self.bus.ui.lineEdit_input_mut_table_csv.textChanged.connect(
            self.update_mutant_table_columns,
        )

        self.bus.button("open_output_pse_visualize").clicked.connect(
            partial(
                self.save_as_a_session,
                "ui.visualize.input.to_pse",
            )
        )

        self.bus.set_widget_value("ui.visualize.input.best_leaf", "best_leaf")
        self.bus.set_widget_value(
            "ui.visualize.input.totalscore", "totalscore"
        )

        self.bus.button("run_visualizing").clicked.connect(
            self.visualize_mutants
        )

        self.bus.button("reduce_this_session").clicked.connect(
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
                ("ui.visualize.input.multi_design.to_mutant_txt",),
                (
                    "multi_design_export_mutants_from_table",
                    "run_multi_design",
                ),
            )
        )

        self.bus.button("multi_design_initialize").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_initialize,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button("multi_design_start_new_design").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_start,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button("multi_design_left").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_undo_picking,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button("multi_design_right").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_pick_next_mut,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button("multi_design_end_this_design").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_stop_design,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button(
            "multi_design_export_mutants_from_table"
        ).clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_save_design,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        self.bus.button("run_multi_design").clicked.connect(
            partial(
                run_worker_thread_with_progress,
                worker_function=self.multi_mutagenesis_design_auto,
                progress_bar=self.bus.ui.progressBar,
            )
        )

        # Tab Interact

        self.bus.button("reinitialize_interact").clicked.connect(
            self.load_gremlin_mrf
        )
        self.bus.button("run_interact_scan").clicked.connect(
            self.run_gremlin_tool
        )

        self.bus.button("interact_reject").clicked.connect(
            partial(self.coevoled_mutant_decision, False)
        )
        self.bus.button("interact_accept").clicked.connect(
            partial(self.coevoled_mutant_decision, True)
        )

        # Tab socket
        self.generate_ws_server_key()

        self.bus.button("ws_generate_randomized_key").clicked.connect(
            self.generate_ws_server_key
        )
        self.bus.get_widget_from_cfg_item(
            "ui.socket.use_key"
        ).stateChanged.connect(self.generate_ws_server_key)

        # Connect the partial function to the stateChanged signal
        self.bus.ui.checkBox_ws_server_mode.stateChanged.connect(
            self.toggle_ws_server_mode
        )

        self.bus.button("ws_connect_to_server").clicked.connect(
            partial(self.toggle_ws_client_connection, True)
        )

        self.bus.button("ws_disconnect_from_server").clicked.connect(
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

        return main_window

    def reload_molecule_info(self):
        """Reload the molecule in current session."""
        self.temperal_session = tempfile.mktemp(suffix=".pse")

        if not is_empty_session():
            # remove alternative comformations
            cmd.remove('not alt ""+A')
            cmd.alter("all", 'alt=""')
            cmd.save(self.temperal_session)
            cmd.reinitialize()
            cmd.load(self.temperal_session)
        else:
            warnings.warn(
                issues.EmptySessionWarning(
                    "Current session is empty! Please load one PDB/PSE/PZE!"
                )
            )
            new_session_file = self.file_dialog.browse_filename(
                mode="r",
                exts=(
                    FileExtentions.Session,
                    FileExtentions.PDB,
                    FileExtentions.Any,
                ),
            )
            if not new_session_file:
                warnings.warn(
                    issues.NoInputWarning(
                        "Abored recognizing sessions from input."
                    )
                )
                return
            elif not os.path.exists(new_session_file):
                warnings.warn(
                    issues.NoInputWarning(
                        f"File does not exist: {new_session_file}."
                    )
                )
                return
            else:
                cmd.reinitialize()
                cmd.load(new_session_file)
                # remove alternative comformations
                cmd.remove('not alt ""+A')
                cmd.alter("all", 'alt=""')
                cmd.save(self.temperal_session)

        self.bus.set_widget_value(
            "ui.header_panel.input.molecule", find_design_molecules
        )

    def save_as_a_session(self, cfg_to_pse: str):
        """Save current session to a file.

        Args:
            cfg_to_pse (str): Config item in ConfigBus
        """
        output_pse_fn = self.file_dialog.browse_filename(
            mode="w",
            exts=(FileExtentions.Session, FileExtentions.Any),
        )

        if output_pse_fn and os.path.exists(os.path.dirname(output_pse_fn)):
            logging.info(f"Output file is set as {output_pse_fn}")
            self.bus.set_widget_value(cfg_to_pse, output_pse_fn)
        else:
            warnings.warn(
                issues.NoInputWarning(f"Invalid output path: {output_pse_fn}.")
            )

    def update_chain_id(self):
        """Update chain ids for picked molecule."""
        molecule = self.bus.get_widget_value(
            "ui.header_panel.input.molecule", str
        )
        if not molecule:
            warnings.warn(
                issues.NoInputWarning("No available designable molecule!")
            )
            return
        chain_ids = find_all_protein_chain_ids_in_protein(molecule)
        self.designable_sequences = RosettaPyProteinSequence.from_dict(
            {
                chain_id: get_molecule_sequence(
                    molecule=molecule,
                    chain_id=chain_id,
                    keep_missing=True,
                )
                for chain_id in chain_ids
            }
        )
        if chain_ids:
            self.bus.set_widget_value(
                "ui.header_panel.input.chain_id", chain_ids
            )
            self.bus.set_widget_value(
                "ui.header_panel.input.chain_id", chain_ids[0]
            )

            self.bus.set_value(
                "designable_sequences", self.designable_sequences.as_dict, force_add=True
            )

        self.setup_pssm_gremlin_calculator()

    def find_session_path(self) -> Optional[str]:
        """Find and validate if current session is saved as a session file.

        Returns:
            str: session path.
        """
        session_path: str = cmd.get("session_file")

        if not session_path:
            warnings.warn(
                issues.EmptySessionWarning(
                    "Session not found, please use a new session path to save."
                )
            )
            return self.file_dialog.browse_filename(
                mode="w", exts=(FileExtentions.Session,)
            )

        if not os.path.exists(session_path):
            warnings.warn(
                issues.NoInputWarning(
                    "Invalid session file path, please use a new session path to save."
                )
            )
            return self.file_dialog.browse_filename(
                mode="w", exts=(FileExtentions.Session,)
            )

        if os.path.basename(session_path).startswith(
            "tmp"
        ) and session_path.endswith(".pse"):
            warnings.warn(
                issues.InvalidSessionWarning(
                    f"Found temperal session path: {session_path}, "
                    "please use a new session path to save."
                )
            )
            return self.file_dialog.browse_filename(
                mode="w", exts=(FileExtentions.Session,)
            )

        return session_path

    """
    Private functions used only in a specific tab.
    """

    # Tab Client
    def setup_pssm_gremlin_calculator(self):
        """Setup PSSM/GREMLIN calculation"""

        molecule = self.bus.get_widget_value(
            "ui.header_panel.input.molecule", str
        )
        chain_id = self.bus.get_widget_value(
            "ui.header_panel.input.chain_id", str
        )
        designable_sequences: Optional[Mapping] = self.bus.get_value("designable_sequences", dict)
        if not designable_sequences:
            return

        sequence = designable_sequences.get(chain_id)

        if (not molecule) or (not chain_id) or (not sequence):
            return

        logging.debug(
            f"Molecule: {molecule}\nchain_id: {chain_id}\nsequence: {sequence}"
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
            "ui.client.pssm_gremlin_url", str
        )
        self.pssm_gremlin_calculator.user = self.bus.get_widget_value(
            "ui.client.pssm_gremlin_user", str
        )
        self.pssm_gremlin_calculator.password = self.bus.get_widget_value(
            "ui.client.pssm_gremlin_passwd", str
        )
        if (
            self.pssm_gremlin_calculator.user
            and self.pssm_gremlin_calculator.password
        ):
            self.pssm_gremlin_calculator.auth = HTTPBasicAuth(
                self.pssm_gremlin_calculator.user,
                self.pssm_gremlin_calculator.password,
            )
        else:
            self.pssm_gremlin_calculator.auth = None

    # Tab `Determine`
    def reload_determine_tab_setup(self):
        """Setup pocket determination"""
        molecule = self.bus.get_widget_value(
            "ui.header_panel.input.molecule", str
        )
        if not molecule:
            warnings.warn(issues.NoResultsWarning("No design molecule found."))
            return

        small_molecules = [""]
        if more_hetatm := find_small_molecules_in_protein(molecule):
            small_molecules.extend(more_hetatm)
            logging.info(f"Small molecules found: {more_hetatm}")
        else:
            warnings.warn(issues.NoResultsWarning("No small molecule found."))

        self.bus.set_widget_value(
            "ui.prepare.input.pocket.substrate", small_molecules
        )
        self.bus.set_widget_value(
            "ui.prepare.input.pocket.cofactor", small_molecules
        )

    def update_surface_exclusion(self):
        """Setup surface determination"""
        exclusion_list = fetch_exclusion_expressions()

        self.bus.set_widget_value(
            "ui.prepare.input.surface.exclusion", exclusion_list
        )
        if exclusion_list:
            self.bus.get_widget_from_cfg_item(
                "ui.prepare.input.surface.exclusion"
            ).setCurrentIndex(0)

    def run_chain_interface_detection(self):
        """Setup chain-chain interface determination"""
        molecule = self.bus.get_value("ui.header_panel.input.molecule")
        radius = self.bus.get_value("ui.prepare.chain_dist", float)
        chain_ids = find_all_protein_chain_ids_in_protein(molecule)
        if not chain_ids or len(chain_ids) <= 1:
            return

        for chain_id in chain_ids:
            cmd.select(
                f"if_{chain_id}",
                f"({molecule} and c. {chain_id} ) and byres ({molecule} "
                f"and polymer.protein and (not c. {chain_id})) "
                f"around {radius} and polymer.protein",
            )

    def run_surface_detection(self):
        """Run surface determination"""
        SurfaceFinder(input_pse=self.temperal_session).process_surface_residues()

    def run_pocket_detection(self):
        """Run pocket determination"""
        PocketSearcher(
            input_pse=self.temperal_session,
            save_dir=f"{self.PWD}/pockets/",
        ).search_pockets()

    # Tab `Mutate`
    def determine_profile_format(
        self, cfg_input_profile: str, cfg_profile_format: str
    ):
        """Determine the format of input profile

        Args:
            cfg_input_profile (str): config item of input profile
            cfg_profile_format (str): config item of output profile format

        """
        _fp = self.bus.get_widget_value(cfg_input_profile, str)
        if _fp == "None" or not _fp:
            return

        profile_fp = os.path.abspath(str(_fp))

        if not os.path.exists(profile_fp):
            return

        profile_format = determine_profile_type(profile_fp=profile_fp)
        if not profile_format:
            return

        self.bus.set_widget_value(cfg_profile_format, profile_format)

    def run_mutant_loading_from_profile(self):
        """Run mutant loading from profile to session"""

        trigger_button = self.bus.button("run_PSSM_to_pse")

        with (
            hold_trigger_button(trigger_button),
            timing("Run Mutant Loading from Profile"),
        ):
            worker = MutateWorker()
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
                    data_type="MutantTree",
                )
            )
        del worker

    # Tab `Evaluate`
    def set_pymol_session_rock(self):
        """Rock PyMOl view"""
        if not self.evaluator:
            raise issues.UnexpectedWorkflowError(
                "Faild to call evaluator because it is not initialized."
            )
        self.evaluator.set_pymol_session_rock()

    def initialize_design_candidates(self):
        """Initialize Evaluator for human checks"""

        self.evaluator = Evalutator()

        self.evaluator.initialize_design_candidates()

    def recover_mutant_choices_from_checkpoint(self):
        """
        This function recovers mutant choices from a checkpoint file
        using an evaluator.
        """

        if not self.evaluator:
            raise issues.UnexpectedWorkflowError(
                "Faild to call evaluator because it is not initialized."
            )
        mutant_choice_checkpoint_fn = self.file_dialog.browse_filename(
            mode="r",
            exts=(FileExtentions.Mutable, FileExtentions.Any),
        )

        self.evaluator.recover_mutant_choices_from_checkpoint(
            mutant_choice_checkpoint_fn
        )

    def jump_to_the_best_mutant(self):
        """
        This function checks if the evaluator is initialized
        and then jumps to the best mutant.
        """
        if not self.evaluator:
            raise issues.UnexpectedWorkflowError(
                "Faild to call evaluator because it is not initialized."
            )
        self.evaluator.jump_to_the_best_mutant()

    def jump_to_branch(self):
        """
        This function checks if the evaluator is initialized
        and then jumps to a branch.
        """
        if not self.evaluator:
            raise issues.UnexpectedWorkflowError(
                "Faild to call evaluator because it is not initialized."
            )
        self.evaluator.jump_to_branch()

    def jump_to_a_mutant(self):
        """
        This function checks if the evaluator is initialized
        and then jumps to a mutant.
        """
        if not self.evaluator:
            raise issues.UnexpectedWorkflowError(
                "Faild to call evaluator because it is not initialized."
            )
        self.evaluator.jump_to_a_mutant()

    def find_all_best_mutants(self):
        """
        This function checks if the evaluator is initialized and
        then calls a method to find all the best mutants.
        """
        if not self.evaluator:
            raise issues.UnexpectedWorkflowError(
                "Faild to call evaluator because it is not initialized."
            )
        self.evaluator.find_all_best_mutants()

    # combination and clustering
    def run_clustering(self):
        """
        The function `run_clustering` initializes a `ClusterRunner`
        object and runs the clustering process upon triggering a button press.
        """
        trigger_button = self.bus.button("run_cluster")

        # lazy module loading to fasten plugin initializing

        worker = ClusterRunner(
            PWD=self.PWD,
        )

        with hold_trigger_button(trigger_button), timing("Clustering"):
            worker.run_clustering()

        del worker

    # Tab Visualize

    def update_mutant_table_columns(self):
        """Retrieves mutant table columns from a file, validates them,
        and sets them as values in combo boxes.
        """
        mut_table_fp = self.bus.get_widget_value(
            "ui.visualize.input.from_mutant_txt"
        )
        if not os.path.exists(mut_table_fp):
            warnings.warn(
                issues.NoInputWarning(
                    f"Mutant Table path is not valid: {mut_table_fp}"
                )
            )
            return

        mut_table_cols = get_mutant_table_columns(mutfile=mut_table_fp)

        if not mut_table_cols:
            warnings.warn(
                issues.BadDataWarning(
                    f"Mutant Table column names is not valid: {mut_table_cols}"
                )
            )
            return

        comboBox_best_leaf = self.bus.get_widget_from_cfg_item(
            "ui.visualize.input.best_leaf"
        )
        comboBox_totalscore = self.bus.get_widget_from_cfg_item(
            "ui.visualize.input.totalscore"
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
        """
        This function saves a mutant tree visualization based on specified
        configuration parameters.

        :param cfg_mutant_table_fp: `cfg_mutant_table_fp` is a configuration
            parameter that represents the file path where the mutant table
            will be saved
        :param cfg_group_name: The `cfg_group_name` parameter is a
            configuration key that specifies the name of a group.
            In the `save_visualizing_mutant_tree` method, this parameter
            is used to retrieve the group name from the configuration
            settings using
        `self.bus.get_value(cfg_group_name)`. This group name is then
        :return: nothing explicitly, as there is no return statement provided
            in the code snippet.
        """
        group_name = self.bus.get_value(cfg_group_name)

        mutant_table_fp = self.bus.get_value(cfg_mutant_table_fp)

        if not os.path.exists(mutant_table_fp):
            logging.warning(
                "Mutant table path is not available. Now we will create one."
            )

        all_available_groups = cmd.get_names(
            type="group_objects", enabled_only=0
        )
        if group_name not in all_available_groups:
            logging.error(
                f"Group {group_name} is not correct. Available group: {all_available_groups}"
            )
            return

        logging.info("Instantializing MutantTree for current selection ... ")
        self.visualizing_mutant_tree = existed_mutant_tree(
            sequences=self.designable_sequences, enabled_only=1
        )

        logging.info(f"Saving mutant table to {mutant_table_fp} ...")

        save_mutant_choices(
            self.bus.get_value(cfg_mutant_table_fp),
            self.visualizing_mutant_tree,
        )

    def visualize_mutants(self):
        """
        The `visualize_mutants` function triggers visualization of
        mutants and broadcasts the mutant tree data if conditions are met.
        """
        trigger_button = self.bus.button("run_visualizing")

        with hold_trigger_button(trigger_button), timing("Visualizng Mutants"):
            worker = VisualizingWorker()
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
                    data_type="MutantTree",
                )
            )

        del worker

    def reduce_current_session(
        self,
        session: Optional[str] = None,
        reduce_disabled: bool = False,
        overwrite: bool = False,
    ):
        """Reduce the current session by disabling certain items
        and potentially overwriting the session file.

        Args:
            session (str, optional): Path to given session. Defaults to None.
            reduce_disabled (bool, optional): Whether to reduce disabled object
                in current session. Defaults to False.
            overwrite (bool, optional): Whether to override existing file.
                Defaults to False.
        """
        if not session:
            session = self.find_session_path()

        if reduce_disabled:
            enabled_items = cmd.get_names("nongroup_objects", enabled_only=1)
            all_items = cmd.get_names("nongroup_objects", enabled_only=0)
            for item in all_items:
                if item not in enabled_items:
                    logging.warning(
                        f"Reducing item {item} from current session ..."
                    )
                    cmd.delete(item)
                    cmd.refresh()

        if session is not None and os.path.exists(session):
            if not overwrite:
                # Ask whether to overide
                confirmed = decide(
                    title="Override current session?",
                    description="Your current session will be overriden. \n \
                        Are you really sure? ",
                )

                if not confirmed:
                    session = self.file_dialog.browse_filename(
                        mode="w", exts=(FileExtentions.Session,)
                    )

                if not session:
                    return

        cmd.save(filename=session)

    def multi_mutagenesis_design_initialize(self):
        """
        The function initializes a MultiMutantDesigner object.
        """
        with hold_trigger_button(self.bus.button("multi_design_initialize")):
            self.multi_designer = MultiMutantDesigner()

    def multi_mutagenesis_design_start(self):
        """Start a new multi design."""

        if not self.multi_designer:
            raise issues.UnexpectedWorkflowError(
                "Multi design is not initialized."
            )

        with hold_trigger_button(
            self.bus.button("multi_design_start_new_design")
        ):
            self.multi_designer.refresh_options()

            if not self.multi_designer.in_design_multi_design_case.empty:
                logging.warning(
                    "Your current mutant multi-mutagenesis will be discarded!"
                )

                # Ask whether to overide
                confirmed = decide(
                    title="Discard in-design mutant choice?",
                    description="You currently have uncompleted mutant choice, "
                    "which shall be discarded. \n  Are you really sure? ",
                )

                if not confirmed:
                    logging.warning("Cancelled.")
                    return
            self.multi_designer.start_new_design()

    def multi_mutagenesis_design_pick_next_mut(self):
        """
        Picking the next mutant in a multi mutagenesis design process.
        """
        if not self.multi_designer:
            raise issues.UnexpectedWorkflowError(
                "Multi design is not initialized."
            )

        with hold_trigger_button(
            buttons=self.bus.buttons(
                button_ids=("multi_design_left", "multi_design_right")
            )
        ):
            self.multi_designer.refresh_options()
            self.multi_designer.pick_next_mutant()

    def multi_mutagenesis_design_undo_picking(self):
        """
        Undo a single step of operation in multi mutagenesis design.
        """
        if not self.multi_designer:
            raise issues.UnexpectedWorkflowError(
                "Multi design is not initialized."
            )

        with hold_trigger_button(
            buttons=self.bus.buttons(
                ("multi_design_left", "multi_design_right")
            )
        ):
            self.multi_designer.refresh_options()
            self.multi_designer.undo_previous_mutant()

    def multi_mutagenesis_design_stop_design(self):
        """
        Terminates the picking process if in a multi design case.
        """
        if not self.multi_designer:
            raise issues.UnexpectedWorkflowError(
                "Multi design is not initialized."
            )

        with hold_trigger_button(
            self.bus.button("multi_design_end_this_design")
        ):
            self.multi_designer.refresh_options()
            if self.multi_designer.in_design_multi_design_case:
                self.multi_designer.terminate_picking(continue_design=False)

    def multi_mutagenesis_design_save_design(self):
        """
        Exports designed variants.
        """
        if not self.multi_designer:
            raise issues.UnexpectedWorkflowError(
                "Multi design is not initialized."
            )

        with hold_trigger_button(
            self.bus.button("multi_design_export_mutants_from_table")
        ):
            self.multi_designer.export_designed_variant()

    def multi_mutagenesis_design_auto(self):
        """
        Automates the process of designing multiple mutagenesis variants.
        """
        trigger_button = self.bus.button("run_multi_design")

        # initialize
        self.multi_mutagenesis_design_initialize()
        if not self.multi_designer:
            raise issues.UnexpectedWorkflowError(
                "Multi design failed in initializing."
            )

        max_num_multi_design_cases = self.multi_designer.total_design_cases

        maximal_mutant_num = self.multi_designer.maximal_mutant_num
        self.multi_designer.refresh_options()

        with (
            hold_trigger_button(trigger_button),
            timing("Automatic multi-design"),
        ):
            try:
                for i in range(max_num_multi_design_cases):
                    logging.info(f"Starting {i}-th mutagenesis variant case")
                    self.multi_mutagenesis_design_start()
                    # pick mutant until it reaches the required number
                    for j in range(maximal_mutant_num):
                        logging.info(f"Picking {j}-th mutagenesis")
                        self.multi_mutagenesis_design_pick_next_mut()
                    self.multi_mutagenesis_design_stop_design()
                self.multi_mutagenesis_design_save_design()
            except Exception:
                traceback.print_exc()

    # Tab Interact via GREMLIN
    def load_gremlin_mrf(self):
        """
        Loads a GREMLIN MRF for interaction analysis.
        """
        trigger_button = self.bus.button("reinitialize_interact")

        with hold_trigger_button(trigger_button), timing("Load GREMLIN mrf"):
            self.gremlin_worker = GREMLIN_Analyser()
            self.gremlin_worker.load_gremlin_mrf()

    def run_gremlin_tool(self):
        """
        Runs Gremlin tool if a Gremlin worker is available.
        """
        if not self.gremlin_worker:
            raise issues.UnexpectedWorkflowError(
                "Gremlin tool is not started."
            )

        trigger_button = self.bus.button("run_interact_scan")

        with (
            hold_trigger_button(trigger_button),
            timing("GREMLIN interaction scanning"),
        ):
            self.gremlin_worker.run_gremlin_tool()

    def coevoled_mutant_decision(self, decision_to_accept: bool):
        """Makes a decision on accepting a mutant.

        Args:
            decision_to_accept (bool): whether to accept or
                reject a coevolved mutant.

        """
        if not self.gremlin_worker:
            raise issues.UnexpectedWorkflowError(
                "Gremlin tool is not started."
            )
        self.gremlin_worker.coevoled_mutant_decision(accept=decision_to_accept)

    def generate_ws_server_key(self):
        """
        Generates a strong password key for a WebSocket server.
        """
        use_key = self.bus.get_widget_value("ui.socket.use_key", str)
        if not use_key:
            return

        self.bus.set_widget_value(
            "ui.socket.input.key", generate_strong_password(length=32)
        )

    def setup_ws_server(self):
        """
        Generates a WebSocket server key and sets up the WebSocket
        server.
        """
        self.generate_ws_server_key()
        self.ws_server.setup_ws_server()

    def update_ws_server_view_update_options(self):
        """
        Updates the options for broadcasting view changes in a WebSocket server.
        """
        # not instantialized or not running
        if not self.ws_server or not self.ws_server.is_running:
            logging.warning("Server is not in service.")
            return

        # do changes
        self.ws_server.view_broadcast_enabled = self.bus.get_widget_value(
            "ui.socket.broadcast.view", bool
        )
        self.ws_server.view_broadcast_interval = self.bus.get_widget_value(
            "ui.socket.broadcast.interval", float
        )

        # disabled
        if not self.ws_server.view_broadcast_enabled:
            if self.ws_server.view_broadcast_on_air:
                self.ws_server.view_broadcast_worker.interrupt()
                self.ws_server.view_broadcast_on_air = False
                logging.warning("Stop broadcasting view.")
                return
            logging.warning(
                "Server is not broadcasting view changes. Do nothing."
            )
            return

        # no clients
        if not self.ws_server.meetingroom:
            logging.warning(
                "Server has no client, ignore view updating. Do nothing."
            )
            self.ws_server.view_broadcast_on_air = False
            return

        # already on air
        if self.ws_server.view_broadcast_on_air:
            logging.warning("Server is broadcasting view changes! Do nothing.")
            return

        # start broadcaster

        if not self.ws_server.view_broadcast_on_air:
            self.ws_server.view_broadcast_worker = WorkerThread(
                func=self.ws_server.broadcast_view
            )

        self.ws_server.view_broadcast_on_air = True
        self.ws_server.view_broadcast_worker.run()

        logging.warning("Start broadcasting view.")
        return

    # Assuming toggle_ws_server_mode gets triggered on
    # checkBox_ws_server_mode state change
    def toggle_ws_server_mode(self):
        """
        Toggles the WebSocket server mode based on the value of a widget
        and logs the server status.
        """
        toggled = self.bus.get_widget_value("ui.socket.server_mode", bool)

        try:
            if not self.ws_server.initialized:
                self.ws_server = REvoDesignWebSocketServer()

            if toggled:
                if self.ws_server.is_running:
                    logging.warning(
                        "Server is already in running state. Do nothing."
                    )
                    return

                else:
                    logging.info("Server is launching...")
                    self.setup_ws_server()

            else:
                if not self.ws_server.is_running:
                    logging.warning("Server is already stopped. Do nothing.")
                    return
                self.ws_server.stop_server()
        except Exception as e:
            logging.warning(e)
            traceback.print_exc()

        logging.warning(
            f'Server status: {"ON" if self.ws_server.is_running else "OFF"}'
        )

    async def ws_broadcast_from_server(self, data: Any, data_type: str):
        """Broadcasts data of a specified type from the server to connected
        WebSocket clients.

        Args:
            data (Any): data object
            data_type (str): data type lable
        """
        await self.ws_server.broadcast_object(data, data_type)

    def setup_ws_client(self):
        """
        Set up a WebSocket client.
        """
        self.ws_client.setup_ws_client()

    def update_ws_client_view_update_options(self):
        """
        Updates the view broadcast option for a WebSocket client if it is
        connected.
        """
        if not self.ws_client or not self.ws_client.connected:
            logging.warning("Client is not connected")
            return

        self.ws_client.receive_view_broadcast = self.bus.get_widget_value(
            "ui.socket.receive.view", bool
        )

    def toggle_ws_client_connection(self, connect: bool = True):
        """Connect or disconnect a WebSocket client from a
        server and logs the client status.

        Args:
            connect (bool, optional): whether to connect or disconnect
            the WebSocket client. Defaults to True.
        """
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
        """
        Set up a WebSocket client and connects it to the
        server if it is not already connected.
        """
        self.setup_ws_client()
        if self.ws_client.connected:
            logging.warning("Client has already connected. Do noting.")
            return
        self.ws_client.connect_to_server()

    def ws_client_disconnect_from_server(self):
        """
        Checks if the WebSocket client is initialized and connected before
        closing the connection.
        """
        if not self.ws_client.initialized:
            logging.warning("Client is not initialized. Do noting.")
            return
        if not self.ws_client.connected:
            logging.warning("Client has already disconneced. Do noting.")
            return
        self.ws_client.close_connection()

    def reload_configurations(self, experiment: Optional[str] = None):
        """Reloading configurations based on different scenarios such as
        reconfiguring with changes, initializing configurations, loading
        specific experiment configurations, or reloading from default
        configurations.

        Args:
            experiment (str, optional): the name of the experiment for which
            configurations need to be reloaded. Defaults to None.
        """
        if self.bus:
            logging.warning("Reconfiguring with changes...")
            reconfigure = True
        else:
            logging.warning("Configuration initialized.")
            reconfigure = False

        if not reconfigure:
            # while booting
            # create a bus btw cfg<---> ui
            ConfigBus.initialize(ui=self.ui)
            self.bus = ConfigBus()

            # Regster all environment variables from config file
            register_environment_variables()

            # Tab Config
            ParamChangeCollections.register_all(ui=self.bus.ui)

            self.bus.initialize_widget_with_group()

            # register widget change events to update cfg items
            self.bus.register_widget_changes_to_cfg()

        elif experiment:
            # while loading experiment
            expected_experiment_config = f"{experiment}.yaml"

            if os.path.exists(
                os.path.join(
                    EXPERIMENTS_CONFIG_DIR, expected_experiment_config
                )
            ):
                self.bus.cfg = reload_config_file(
                    config_name=f"experiments/{experiment}"
                )["experiments"]
        else:
            # simply reload from default config, discard unsaved.
            self.bus.cfg = reload_config_file()

        self.refresh_ui_from_new_configuration()

    def refresh_ui_from_new_configuration(self):
        """
        Updates the UI widgets based on a new configuration.
        """
        for (
            widget_id,
            config_item,
        ) in self.bus.w2c.widget_id2config_dict.items():
            widget = self.bus.get_widget_from_id(widget_id=widget_id)
            set_widget_value(
                widget, OmegaConf.select(self.bus.cfg, config_item)
            )

    def save_configuration_from_ui(self, experiment: str = "global_config"):
        """Saves a configuration from the user interface with an optional
        experiment name.

        Args:
            experiment (str, optional): the name of the configuration or
            experiment being saved. It is an optional parameter, meaning
            it can be None if not provided. Defaults to None.
        """
        logging.warning(f"Saving configuration as {experiment}")
        save_configuration(new_cfg=self.bus.cfg, config_name=experiment)

    def load_and_save_experiment(self, mode: IO_MODE = "r"):
        """Loads and saves experiment configurations, copying files
        between directories based on the specified mode.

        Args:
            mode (IO_MODE, optional): Specify the input/output mode
            for loading and saving the experiment configuration.
            Defaults to 'r'.
        """
        new_cfg_file = self.file_dialog.browse_filename(
            mode=mode,
            exts=(FileExtentions.YAML, FileExtentions.Any),
        )
        if not new_cfg_file:
            return
        new_cfg_base_name: str = os.path.basename(new_cfg_file)
        new_cfg_prefix = new_cfg_base_name.rstrip(".yaml")
        experiment_file = os.path.join(
            EXPERIMENTS_CONFIG_DIR, new_cfg_base_name
        )
        if mode == "r":
            # copy cfg to experiment dir so that hydra can access it
            shutil.copy(new_cfg_file, experiment_file)
            self.reload_configurations(experiment=new_cfg_prefix)
            logging.warning(
                f"Load config from {new_cfg_file}, backup at {experiment_file}"
            )
        else:
            self.save_configuration_from_ui(
                experiment=f"experiments/{new_cfg_prefix}"
            )
            # hydra has already saved config into EXPERIMENTS_CONFIG_DIR, copy to user defined config file path
            shutil.copy(experiment_file, new_cfg_file)
            logging.warning(
                f"saved config at {new_cfg_file}, backup at {experiment_file}"
            )
