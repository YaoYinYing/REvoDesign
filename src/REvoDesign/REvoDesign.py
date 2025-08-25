import asyncio
import gc
import os
import shutil
import tempfile
import traceback
import warnings
from functools import partial
from typing import Any, Optional
from omegaconf import OmegaConf
from pymol import cmd
from RosettaPy.common.mutation import RosettaPyProteinSequence
import REvoDesign
from REvoDesign import (ConfigBus, file_extensions, issues, reload_config_file,
                        save_configuration, set_REvoDesign_config_file)
from REvoDesign.application.font import FontSetter
from REvoDesign.application.i18n import LanguageSwitch
from REvoDesign.application.icon import IconSetter
from REvoDesign.basic import MenuActionServerMonitor, MenuCollection, MenuItem
from REvoDesign.bootstrap import EXPERIMENTS_CONFIG_DIR, REVODESIGN_CONFIG_FILE
from REvoDesign.clients.QtSocketConnector import (REvoDesignWebSocketClient,
                                                  REvoDesignWebSocketServer)
from REvoDesign.clusters import ClusterRunner
from REvoDesign.common.multi_mutant_designer import MultiMutantDesigner
from REvoDesign.driver.environ_register import (add_new_environment_variables,
                                                drop_environment_variables,
                                                register_environment_variables)
from REvoDesign.driver.file_dialog import IO_MODE, FileDialog
from REvoDesign.driver.param_toggle_register import ParamChangeCollections
from REvoDesign.driver.ui_driver import StoresWidget
from REvoDesign.editor import menu_edit_file
from REvoDesign.editor.monaco.server import ServerControl
from REvoDesign.evaluate import Evalutator
from REvoDesign.logger import ROOT_LOGGER, LoggerT
from REvoDesign.phylogenetics import (GremlinAnalyser, MutateWorker,
                                      VisualizingWorker)
from REvoDesign.Qt import QtCore, QtGui, QtWidgets
from REvoDesign.shortcuts.shortcuts_on_menu import (
    menu_alterbox, menu_color_by_mutation, menu_color_by_plddt,
    menu_dump_fasta_from_struct, menu_dump_sidechains, menu_esm1v,
    menu_fast_relax, menu_general_rfdiffusion_task, menu_get_pca_box,
    menu_getbox, menu_logger_level_setter, menu_profile_pick_design,
    menu_pross, menu_pssm2csv, menu_real_sc, menu_relax_w_ca_constraints,
    menu_resi_renumber, menu_rmhet, menu_rosettaligand,
    menu_sdf2rosetta_params, menu_smiles_conformer_batch,
    menu_smiles_conformer_single, menu_thermompnn,
    menu_visualize_substrate_potentials)
from REvoDesign.shortcuts.tools.openmm_utils import OpenmmSetupServerControl
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
from REvoDesign.tools.utils import (generate_strong_password, require_not_none,
                                    run_worker_thread_with_progress, timing)
from REvoDesign.UI import Ui_REvoDesignPyMOL_UI
REPO_URL = "https://github.com/YaoYinYing/REvoDesign"
logging: LoggerT = None  
class REvoDesignPlugin(QtWidgets.QWidget):
    def __init__(
        self,
    ):
        super().__init__()
        self.window = None
        self.RUN_DIR = os.path.abspath(os.path.dirname(__file__))
        self.PWD = os.getcwd()
        self.bus: ConfigBus = None  
        self.file_dialog: FileDialog = None  
        self.designable_sequences: RosettaPyProteinSequence = None  
        self.design_molecule = ""
        self.design_chain_id = ""
        self.design_sequence = ""
        self.gremlin_worker: GremlinAnalyser = None  
        self.evaluator: Evalutator = None  
        global logging
        logging = ROOT_LOGGER.getChild(self.__class__.__name__)
        self.multi_designer: MultiMutantDesigner = None  
        try:
            from PyQt5 import QtWebSockets  
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
        if pwd_2 and all(
            [
                os.path.abspath(pwd)
                == os.path.abspath(os.path.expanduser("~"))
                for pwd in [pwd_0]
            ]
        ):
            self.set_working_directory(pwd_2)
            return
        for pwd in [pwd_0]:
            if pwd and os.path.exists(pwd):
                self.set_working_directory(pwd)
                return
    def set_working_directory(self, new_dir: Optional[str] = None):
        if new_dir and os.path.abspath(new_dir) == os.path.abspath(self.PWD):
            self.bus.set_value("work_dir", os.path.abspath(self.PWD))
            return
        if new_dir and os.path.exists(new_dir):
            self.PWD = new_dir
        else:
            PWD = getExistingDirectory()
            if not PWD:
                return
            self.PWD = PWD
        os.chdir(self.PWD)
        self.bus.set_value("work_dir", os.path.abspath(self.PWD))
    def run_plugin_gui(self):
        if self.window is None:
            self.window = self.make_window()
        self.window.show()
        self.fix_wd()
        self.file_dialog = FileDialog(self.window, self.PWD)
    def reinitialize(self, delete: bool = False):
        self.multi_designer = None
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
        logging.warning("REvoDesign is shutting down.")
        if self.window:
            self.window = None
    def make_window(self):
        installed_dir = os.path.dirname(__file__)
        logging.debug(f"REvoDesign is installed in {installed_dir}")
        check_mac_rosetta2()
        main_window = QtWidgets.QMainWindow()  
        self.ui = Ui_REvoDesignPyMOL_UI()
        self.ui.setupUi(main_window)
        IconSetter(main_window=main_window)
        self.reload_configurations()
        FontSetter(main_window=main_window)
        self.bus.ui.trans = QtCore.QTranslator(self)
        LanguageSwitch(window=main_window)
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
                    kwargs={'file_path': REVODESIGN_CONFIG_FILE}
                ),
                MenuItem(
                    self.bus.ui.actionSave_Configurations,
                    self.save_configuration_from_ui,
                    kwargs={'experiment': "global_config"}
                ),
                MenuItem(
                    self.bus.ui.action_LoadExperiment,
                    self.load_and_save_experiment,
                    kwargs={'mode': "r"},
                ),
                MenuItem(
                    self.bus.ui.action_Save_to_Experiment,
                    self.load_and_save_experiment,
                    kwargs={'mode': "w"},
                ),
                MenuItem(
                    self.bus.ui.actionReinitialize,
                    self.reinitialize,
                    kwargs={'delete': True},
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
                    kwargs={'dump_all': False},
                ),
                MenuItem(
                    self.bus.ui.actionRenderAllSidechains,
                    menu_dump_sidechains,
                    kwargs={'dump_all': True},
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
                    self.bus.ui.actionColor_by_Mutations,
                    menu_color_by_mutation
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
                    self.bus.ui.actionSDF_to_Rosetta_Parameters,
                    menu_sdf2rosetta_params
                ),
                MenuItem(
                    self.bus.ui.actionRosettaLigand,
                    menu_rosettaligand
                ),
                MenuItem(
                    self.bus.ui.actionFastRelax,
                    menu_fast_relax
                ),
                MenuItem(
                    self.bus.ui.actionRelax_w_Ca_Constraints,
                    menu_relax_w_ca_constraints
                ),
                MenuItem(
                    self.bus.ui.actionThermoMPNN,
                    menu_thermompnn
                ),
                MenuItem(
                    self.bus.ui.actionESM_1v,
                    menu_esm1v
                ),
                MenuItem(
                    self.bus.ui.actionAlter_Box,
                    menu_alterbox
                ),
                MenuItem(
                    self.bus.ui.actionGet_PCA_Box,
                    menu_get_pca_box
                ),
                MenuItem(
                    self.bus.ui.actionGet_Box,
                    menu_getbox
                ),
                MenuItem(
                    self.bus.ui.actionRemove_Het_Atoms,
                    menu_rmhet
                ),
                MenuItem(
                    self.bus.ui.actionRFdiffusion_General_Task,
                    menu_general_rfdiffusion_task
                ),
                MenuItem(
                    self.bus.ui.actionSubstrate_Potential,
                    menu_visualize_substrate_potentials
                ),
                MenuItem(
                    self.bus.ui.actionPROSS,
                    menu_pross
                ),
                MenuItem(
                    self.bus.ui.actionProfile_Design,
                    menu_profile_pick_design
                ),
                MenuItem(
                    self.bus.ui.actionRenumber_Residue_Index,
                    menu_resi_renumber
                ),
                MenuItem(
                    self.bus.ui.actionDump_Sequence,
                    menu_dump_fasta_from_struct
                ),
                MenuItem(
                    self.bus.ui.actionSource_Code,
                    QtGui.QDesktopServices.openUrl,
                    (QtCore.QUrl(REPO_URL),)
                ),
                MenuItem(
                    self.bus.ui.actionVersion,
                    notify_box,
                    kwargs={'message': f"REvoDesign v.{REvoDesign.__version__}\nSrc: {REPO_URL}"}
                ),
                MenuItem(
                    self.bus.ui.actionSetLogLevel,
                    menu_logger_level_setter
                ),
            ),
        )
        stores = StoresWidget()
        stores.server_switches.update(
            {
                'Editor_Backend': MenuActionServerMonitor(
                    ServerControl,
                    self.bus.ui.actionStartEditor,
                    self.bus.ui.actionStopEditor,
                    self.bus.ui.menuEditor_Backend)})
        stores.server_switches.update(
            {
                'OpenMM': MenuActionServerMonitor(
                    OpenmmSetupServerControl,
                    self.bus.ui.actionStart_SetupOpenMM,
                    self.bus.ui.actionStop_SetupOpenMM,
                    self.bus.ui.menuOpenMM
                )})
        if self.teamwork_enabled:
            self.ws_server = REvoDesignWebSocketServer()
            self.ws_client = REvoDesignWebSocketClient()
        else:
            self.ws_server = None
            self.ws_client = None
            self.bus.ui.tabWidget.setTabVisible(7, False)
        self.bus.ui.actionCheck_PyMOL_session.triggered.connect(
            self.reload_molecule_info,
        )
        self.bus.ui.comboBox_design_molecule.currentIndexChanged.connect(
            self.update_chain_id,
        )
        max_proc = os.cpu_count()
        if max_proc is None:
            max_proc = 4  
        self.bus.set_widget_value("ui.header_panel.nproc", (1, max_proc))
        self.bus.set_widget_value("ui.header_panel.nproc", max_proc, hard=True)
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
        self.bus.button("dump_interfaces").clicked.connect(
            self.run_chain_interface_detection
        )
        self.bus.button("run_surface_detection").clicked.connect(
            self.run_surface_detection
        )
        self.bus.button("run_pocket_detection").clicked.connect(
            self.run_pocket_detection
        )
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
        self.bus.ui.lineEdit_input_mut_table.textChanged.connect(
            partial(
                self.bus.fp_lock,
                ("ui.cluster.input.from_mutant_txt",),
                ("run_cluster",)
            )
        )
        self.bus.button("run_cluster").clicked.connect(self.run_clustering)
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
        self.generate_ws_server_key()
        self.bus.button("ws_generate_randomized_key").clicked.connect(
            self.generate_ws_server_key
        )
        self.bus.get_widget_from_cfg_item(
            "ui.socket.use_key"
        ).stateChanged.connect(self.generate_ws_server_key)
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
        self.temperal_session = tempfile.mkstemp(suffix=".pse")[1]
        if not is_empty_session():
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
                    file_extensions.Session,
                    file_extensions.PDB,
                    file_extensions.Any,
                ),
            )
            if not new_session_file:
                warnings.warn(
                    issues.NoInputWarning(
                        "Abored recognizing sessions from input."
                    )
                )
                return
            if not os.path.exists(new_session_file):
                warnings.warn(
                    issues.NoInputWarning(
                        f"File does not exist: {new_session_file}."
                    )
                )
                return
            cmd.reinitialize()
            cmd.load(new_session_file)
            cmd.remove('not alt ""+A')
            cmd.alter("all", 'alt=""')
            cmd.save(self.temperal_session)
        self.bus.set_widget_value(
            "ui.header_panel.input.molecule", find_design_molecules
        )
    def save_as_a_session(self, cfg_to_pse: str):
        output_pse_fn = self.file_dialog.browse_filename(
            mode="w",
            exts=(file_extensions.Session, file_extensions.Any),
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
    def find_session_path(self) -> Optional[str]:
        session_path: str = cmd.get("session_file")
        if not session_path:
            warnings.warn(
                issues.EmptySessionWarning(
                    "Session not found, please use a new session path to save."
                )
            )
            return self.file_dialog.browse_filename(
                mode="w", exts=(file_extensions.Session,)
            )
        if not os.path.exists(session_path):
            warnings.warn(
                issues.NoInputWarning(
                    "Invalid session file path, please use a new session path to save."
                )
            )
            return self.file_dialog.browse_filename(
                mode="w", exts=(file_extensions.Session,)
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
                mode="w", exts=(file_extensions.Session,)
            )
        return session_path
    def reload_determine_tab_setup(self):
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
        exclusion_list = fetch_exclusion_expressions()
        self.bus.set_widget_value(
            "ui.prepare.input.surface.exclusion", exclusion_list
        )
        if exclusion_list:
            self.bus.get_widget_from_cfg_item(
                "ui.prepare.input.surface.exclusion"
            ).setCurrentIndex(0)
    def run_chain_interface_detection(self):
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
        SurfaceFinder(input_pse=self.temperal_session).process_surface_residues()
    def run_pocket_detection(self):
        PocketSearcher(
            input_pse=self.temperal_session,
            save_dir=f"{self.PWD}/pockets/",
        ).search_pockets()
    def determine_profile_format(
        self, cfg_input_profile: str, cfg_profile_format: str
    ):
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
    def initialize_design_candidates(self):
        self.evaluator = Evalutator()
        self.evaluator.initialize_design_candidates()
    @require_not_none("evaluator")
    def recover_mutant_choices_from_checkpoint(self, *args, **kwargs):
        mutant_choice_checkpoint_fn = self.file_dialog.browse_filename(
            mode="r",
            exts=(file_extensions.Mutable, file_extensions.Any),
        )
        self.evaluator.recover_mutant_choices_from_checkpoint(
            mutant_choice_checkpoint_fn
        )
    @require_not_none("evaluator")
    def jump_to_the_best_mutant(self, *args, **kwargs):
        self.evaluator.jump_to_the_best_mutant()
    @require_not_none("evaluator")
    def jump_to_branch(self, *args, **kwargs):
        self.evaluator.jump_to_branch()
    @require_not_none("evaluator")
    def jump_to_a_mutant(self, *args, **kwargs):
        self.evaluator.jump_to_a_mutant()
    @require_not_none("evaluator")
    def find_all_best_mutants(self, *args, **kwargs):
        self.evaluator.find_all_best_mutants()
    def run_clustering(self):
        trigger_button = self.bus.button("run_cluster")
        worker = ClusterRunner(
            PWD=self.PWD,
        )
        with hold_trigger_button(trigger_button), timing("Clustering"):
            worker.run_clustering()
        del worker
    def update_mutant_table_columns(self):
        mut_table_fp = self.bus.get_widget_value(
            "ui.visualize.input.from_mutant_txt", str
        )
        comboBox_best_leaf = self.bus.get_widget_from_cfg_item(
            "ui.visualize.input.best_leaf"
        )
        comboBox_totalscore = self.bus.get_widget_from_cfg_item(
            "ui.visualize.input.totalscore"
        )
        comboBox_group_name = self.bus.get_widget_from_cfg_item(
            "ui.visualize.input.group_name"
        )
        if not os.path.exists(mut_table_fp):
            warnings.warn(
                issues.NoInputWarning(
                    f"Mutant Table path is not valid: {mut_table_fp}"
                )
            )
            for comboBox in [comboBox_best_leaf, comboBox_totalscore]:
                set_widget_value(comboBox, [''])
            set_widget_value(comboBox_group_name, ['default'])
            return
        mut_table_cols = get_mutant_table_columns(mutfile=mut_table_fp)
        if not mut_table_cols:
            warnings.warn(
                issues.BadDataWarning(
                    f"Mutant Table column names is not valid: {mut_table_cols}"
                )
            )
            return
        for comboBox in [comboBox_best_leaf, comboBox_totalscore]:
            set_widget_value(comboBox, mut_table_cols)
        set_widget_value(comboBox_group_name, [""] + mut_table_cols)
        if len(mut_table_cols) > 1:
            set_widget_value(comboBox_best_leaf, mut_table_cols[0])
            set_widget_value(comboBox_totalscore, mut_table_cols[-1])
            set_widget_value(comboBox_group_name, "")
    def save_visualizing_mutant_tree(
        self, cfg_mutant_table_fp, cfg_group_name
    ):
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
                confirmed = decide(
                    title="Override current session?",
                    description="Your current session will be overriden. \n \
                        Are you really sure? ",
                )
                if not confirmed:
                    session = self.file_dialog.browse_filename(
                        mode="w", exts=(file_extensions.Session,)
                    )
                if not session:
                    return
        cmd.save(filename=session)
    def multi_mutagenesis_design_initialize(self):
        with hold_trigger_button(self.bus.button("multi_design_initialize")):
            self.multi_designer = MultiMutantDesigner()
    @require_not_none("multi_designer")
    def multi_mutagenesis_design_start(self, *args, **kwargs):
        with hold_trigger_button(
            self.bus.button("multi_design_start_new_design")
        ):
            self.multi_designer.refresh_options()
            if not self.multi_designer.in_design_multi_design_case.empty:
                logging.warning(
                    "Your current mutant multi-mutagenesis will be discarded!"
                )
                confirmed = decide(
                    title="Discard in-design mutant choice?",
                    description="You currently have uncompleted mutant choice, "
                    "which shall be discarded. \n  Are you really sure? ",
                )
                if not confirmed:
                    logging.warning("Cancelled.")
                    return
            self.multi_designer.start_new_design()
    @require_not_none("multi_designer")
    def multi_mutagenesis_design_pick_next_mut(self, *args, **kwargs):
        with hold_trigger_button(
            buttons=self.bus.buttons(
                button_ids=("multi_design_left", "multi_design_right")
            )
        ):
            self.multi_designer.refresh_options()
            self.multi_designer.pick_next_mutant()
    @require_not_none("multi_designer")
    def multi_mutagenesis_design_undo_picking(self, *args, **kwargs):
        with hold_trigger_button(
            buttons=self.bus.buttons(
                ("multi_design_left", "multi_design_right")
            )
        ):
            self.multi_designer.refresh_options()
            self.multi_designer.undo_previous_mutant()
    @require_not_none("multi_designer")
    def multi_mutagenesis_design_stop_design(self, *args, **kwargs):
        with hold_trigger_button(
            self.bus.button("multi_design_end_this_design")
        ):
            self.multi_designer.refresh_options()
            if self.multi_designer.in_design_multi_design_case:
                self.multi_designer.terminate_picking(continue_design=False)
    @require_not_none("multi_designer")
    def multi_mutagenesis_design_save_design(self, *args, **kwargs):
        with hold_trigger_button(
            self.bus.button("multi_design_export_mutants_from_table")
        ):
            self.multi_designer.export_designed_variant()
    def multi_mutagenesis_design_auto(self):
        trigger_button = self.bus.button("run_multi_design")
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
                    for j in range(maximal_mutant_num):
                        logging.info(f"Picking {j}-th mutagenesis")
                        self.multi_mutagenesis_design_pick_next_mut()
                    self.multi_mutagenesis_design_stop_design()
                self.multi_mutagenesis_design_save_design()
            except Exception:
                traceback.print_exc()
    def load_gremlin_mrf(self):
        trigger_button = self.bus.button("reinitialize_interact")
        with hold_trigger_button(trigger_button), timing("Load GREMLIN mrf"):
            self.gremlin_worker = GremlinAnalyser()
            self.gremlin_worker.load_gremlin_mrf()
    @require_not_none("gremlin_worker")
    def run_gremlin_tool(self, *args, **kwargs):
        trigger_button = self.bus.button("run_interact_scan")
        with (
            hold_trigger_button(trigger_button),
            timing("GREMLIN interaction scanning"),
        ):
            self.gremlin_worker.run_gremlin_tool()
    def coevoled_mutant_decision(self, decision_to_accept: bool):
        self.gremlin_worker.coevoled_mutant_decision(accept=decision_to_accept)
    def generate_ws_server_key(self):
        use_key = self.bus.get_widget_value("ui.socket.use_key", str)
        if not use_key:
            return
        self.bus.set_widget_value(
            "ui.socket.input.key", generate_strong_password(length=32)
        )
    def setup_ws_server(self):
        self.generate_ws_server_key()
        self.ws_server.setup_ws_server()
    def update_ws_server_view_update_options(self):
        if not self.ws_server or not self.ws_server.is_running:
            logging.warning("Server is not in service.")
            return
        self.ws_server.view_broadcast_enabled = self.bus.get_widget_value(
            "ui.socket.broadcast.view", bool
        )
        self.ws_server.view_broadcast_interval = self.bus.get_widget_value(
            "ui.socket.broadcast.interval", float
        )
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
        if not self.ws_server.meetingroom:
            logging.warning(
                "Server has no client, ignore view updating. Do nothing."
            )
            self.ws_server.view_broadcast_on_air = False
            return
        if self.ws_server.view_broadcast_on_air:
            logging.warning("Server is broadcasting view changes! Do nothing.")
            return
        if not self.ws_server.view_broadcast_on_air:
            self.ws_server.view_broadcast_worker = WorkerThread(
                func=self.ws_server.broadcast_view
            )
        self.ws_server.view_broadcast_on_air = True
        self.ws_server.view_broadcast_worker.run()
        logging.warning("Start broadcasting view.")
        return
    def toggle_ws_server_mode(self):
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
        await self.ws_server.broadcast_object(data, data_type)
    def setup_ws_client(self):
        self.ws_client.setup_ws_client()
    def update_ws_client_view_update_options(self):
        if not self.ws_client or not self.ws_client.connected:
            logging.warning("Client is not connected")
            return
        self.ws_client.receive_view_broadcast = self.bus.get_widget_value(
            "ui.socket.receive.view", bool
        )
    def toggle_ws_client_connection(self, connect: bool = True):
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
            logging.warning("Client has already connected. Do noting.")
            return
        self.ws_client.connect_to_server()
    def ws_client_disconnect_from_server(self):
        if not self.ws_client.initialized:
            logging.warning("Client is not initialized. Do noting.")
            return
        if not self.ws_client.connected:
            logging.warning("Client has already disconneced. Do noting.")
            return
        self.ws_client.close_connection()
    def reload_configurations(self, experiment: Optional[str] = None):
        if self.bus:
            logging.warning("Reconfiguring with changes...")
            reconfigure = True
        else:
            logging.warning("Configuration initialized.")
            reconfigure = False
        if not reconfigure:
            ConfigBus.initialize(ui=self.ui)
            self.bus = ConfigBus()
            register_environment_variables()
            ParamChangeCollections.register_all(ui=self.bus.ui)
            self.bus.initialize_widget_with_group()
            self.bus.register_widget_changes_to_cfg()
        elif experiment:
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
            self.bus.cfg = reload_config_file()
        self.refresh_ui_from_new_configuration()
    def refresh_ui_from_new_configuration(self):
        for (
            widget_id,
            config_item,
        ) in self.bus.w2c.widget_id2config_dict.items():
            widget = self.bus.get_widget_from_id(widget_id=widget_id)
            set_widget_value(
                widget, OmegaConf.select(self.bus.cfg, config_item)
            )
    def save_configuration_from_ui(self, experiment: str = "global_config"):
        logging.warning(f"Saving configuration as {experiment}")
        save_configuration(new_cfg=self.bus.cfg, config_name=experiment)
    def load_and_save_experiment(self, mode: IO_MODE = "r"):
        new_cfg_file = self.file_dialog.browse_filename(
            mode=mode,
            exts=(file_extensions.YAML, file_extensions.Any),
        )
        if not new_cfg_file:
            return
        new_cfg_base_name: str = os.path.basename(new_cfg_file)
        new_cfg_prefix = new_cfg_base_name[:-5]
        experiment_file = os.path.join(
            EXPERIMENTS_CONFIG_DIR, new_cfg_base_name
        )
        if mode == "r":
            shutil.copy(new_cfg_file, experiment_file)
            self.reload_configurations(experiment=new_cfg_prefix)
            logging.warning(
                f"Load config from {new_cfg_file}, backup at {experiment_file}"
            )
        else:
            self.save_configuration_from_ui(
                experiment=f"experiments/{new_cfg_prefix}"
            )
            shutil.copy(experiment_file, new_cfg_file)
            logging.warning(
                f"saved config at {new_cfg_file}, backup at {experiment_file}"
            )