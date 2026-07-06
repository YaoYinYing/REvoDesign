# This file is generated from src/REvoDesign/UI/REvoDesign.ui.
# It is used only for static typing and IDE completion.
# It must not construct the UI at runtime.
# Do not edit by hand. Run: python dev/tools/generate_ui_typing.py

from __future__ import annotations

from typing import Protocol

from REvoDesign.Qt import QtCore, QtGui, QtWidgets


class REvoDesignUiProtocol(Protocol):
    """Static typing contract for the runtime-loaded REvoDesign main UI."""

    trans: QtCore.QTranslator
    """Legacy translator kept for backward compatibility with the generated-UI i18n path."""

    def retranslateUi(self, window: QtWidgets.QMainWindow) -> None:
        """Retranslate UI strings after a language change."""
        ...

    REvoDesignPyMOL_UI: QtWidgets.QMainWindow

    actionAll: QtGui.QAction

    actionAll_Group: QtGui.QAction

    actionAlter_Box: QtGui.QAction

    actionChange_Box: QtGui.QAction

    actionCheck_PyMOL_session: QtGui.QAction

    actionCheck_for_updates: QtGui.QAction

    actionClose: QtGui.QAction

    actionColor_by_Mutations: QtGui.QAction

    actionColor_by_pLDDT: QtGui.QAction

    actionContact: QtGui.QAction

    actionDebug: QtGui.QAction

    actionDocumentation: QtGui.QAction

    actionDraw_All_Sidechains: QtGui.QAction

    actionDraw_Selected_Sidechain: QtGui.QAction

    actionDropEnvironVar: QtGui.QAction

    actionDump_Sequence: QtGui.QAction

    actionESM_1v: QtGui.QAction

    actionFastRelax: QtGui.QAction

    actionFont: QtGui.QAction

    actionGet_Box: QtGui.QAction

    actionGet_PCA_Box: QtGui.QAction

    actionInfo: QtGui.QAction

    actionLoad_Demo: QtGui.QAction

    actionLogToCurrentDirectory: QtGui.QAction

    actionMake_Residue_Range: QtGui.QAction

    actionOpenLogFile: QtGui.QAction

    actionPROSS: QtGui.QAction

    actionPSSM_to_CSV: QtGui.QAction

    actionProfile_Design: QtGui.QAction

    actionPublicattion: QtGui.QAction

    actionRFdiffusion_General_Task: QtGui.QAction

    actionRMSF_to_b_factor: QtGui.QAction

    actionRecentEnvVar: QtGui.QAction

    actionReconfigure: QtGui.QAction

    actionRefreshEnvironVar: QtGui.QAction

    actionReinitialize: QtGui.QAction

    actionRelax_w_Ca_Constraints: QtGui.QAction

    actionRemove_Het_Atoms: QtGui.QAction

    actionRenderAllSidechains: QtGui.QAction

    actionRenderPickedSidechainGroup: QtGui.QAction

    actionRenderPickedSidechainObject: QtGui.QAction

    actionRender_to_Clipboard: QtGui.QAction

    actionRender_to_File: QtGui.QAction

    actionRenumber_Residue_Index: QtGui.QAction

    actionRosettaLigand: QtGui.QAction

    actionRosetta_Score_Analyser: QtGui.QAction

    actionRun_GREMLIN: QtGui.QAction

    actionSDF_to_Rosetta_Parameters: QtGui.QAction

    actionSMILES_Conformers: QtGui.QAction

    actionSMILES_Conformers_Batch: QtGui.QAction

    actionSave_Configuration_as: QtGui.QAction

    actionSave_Configurations: QtGui.QAction

    actionSetLogLevel: QtGui.QAction

    actionSet_Working_Directory: QtGui.QAction

    actionShorten_Range: QtGui.QAction

    actionShow_Real_Sidechain: QtGui.QAction

    actionSource_Code: QtGui.QAction

    actionStart: QtGui.QAction

    actionStartEditor: QtGui.QAction

    actionStart_SetupOpenMM: QtGui.QAction

    actionStopEditor: QtGui.QAction

    actionStop_SetupOpenMM: QtGui.QAction

    actionStyle_Presets: QtGui.QAction

    actionSubstrate_Potential: QtGui.QAction

    actionThermoMPNN: QtGui.QAction

    actionUtils: QtGui.QAction

    actionVersion: QtGui.QAction

    actionVina: QtGui.QAction

    actionVina_3: QtGui.QAction

    actionVina_Export_Results: QtGui.QAction

    actionVina_Prepare_Ligand: QtGui.QAction

    actionVina_Prepare_Receptor: QtGui.QAction

    actionWarning: QtGui.QAction

    action_LoadExperiment: QtGui.QAction

    action_Save_to_Experiment: QtGui.QAction

    centralwidget: QtWidgets.QWidget

    checkBox_cluster_mutate_and_relax: QtWidgets.QCheckBox

    checkBox_cluster_rosetta_override_representatives: QtWidgets.QCheckBox

    checkBox_deduplicate_designs: QtWidgets.QCheckBox

    checkBox_designer_homooligomeric: QtWidgets.QCheckBox

    checkBox_global_score_policy: QtWidgets.QCheckBox

    checkBox_interact_bind_chain_mode: QtWidgets.QCheckBox

    checkBox_multi_design_bond_CA: QtWidgets.QCheckBox

    checkBox_multi_design_check_sidechain_orientations: QtWidgets.QCheckBox

    checkBox_multi_design_color_by_scores: QtWidgets.QCheckBox

    checkBox_multi_design_use_external_scorer: QtWidgets.QCheckBox

    checkBox_randomized_sampling: QtWidgets.QCheckBox

    checkBox_reverse_mutant_effect: QtWidgets.QCheckBox

    checkBox_show_wt: QtWidgets.QCheckBox

    checkBox_shuffle_clustering: QtWidgets.QCheckBox

    checkBox_ws_broadcast_mutagenesis: QtWidgets.QCheckBox

    checkBox_ws_broadcast_selection: QtWidgets.QCheckBox

    checkBox_ws_broadcast_view: QtWidgets.QCheckBox

    checkBox_ws_duplex_mode: QtWidgets.QCheckBox

    checkBox_ws_recieve_mutagenesis_broadcast: QtWidgets.QCheckBox

    checkBox_ws_recieve_mutagenesis_selection: QtWidgets.QCheckBox

    checkBox_ws_recieve_view_broadcast: QtWidgets.QCheckBox

    checkBox_ws_server_mode: QtWidgets.QCheckBox

    checkBox_ws_server_use_key: QtWidgets.QCheckBox

    comboBox_best_leaf: QtWidgets.QComboBox

    comboBox_chain_id: QtWidgets.QComboBox

    comboBox_cluster_matrix: QtWidgets.QComboBox

    comboBox_cluster_method: QtWidgets.QComboBox

    comboBox_cmap: QtWidgets.QComboBox

    comboBox_cofactor_sel: QtWidgets.QComboBox

    comboBox_design_molecule: QtWidgets.QComboBox

    comboBox_external_scorer: QtWidgets.QComboBox

    comboBox_group_ids: QtWidgets.QComboBox

    comboBox_group_name: QtWidgets.QComboBox

    comboBox_ligand_sel: QtWidgets.QComboBox

    comboBox_mutant_ids: QtWidgets.QComboBox

    comboBox_profile_type: QtWidgets.QComboBox

    comboBox_profile_type_2: QtWidgets.QComboBox

    comboBox_rosetta_node_hint: QtWidgets.QComboBox

    comboBox_sidechain_solver: QtWidgets.QComboBox

    comboBox_sidechain_solver_model: QtWidgets.QComboBox

    comboBox_surface_exclusion: QtWidgets.QComboBox

    comboBox_totalscore: QtWidgets.QComboBox

    doubleSpinBox_cluster_evo_weight_esm: QtWidgets.QDoubleSpinBox

    doubleSpinBox_cluster_evo_weight_physchem: QtWidgets.QDoubleSpinBox

    doubleSpinBox_cluster_evo_weight_pssm: QtWidgets.QDoubleSpinBox

    doubleSpinBox_cluster_evo_weight_seq: QtWidgets.QDoubleSpinBox

    doubleSpinBox_cluster_evo_weight_spatial: QtWidgets.QDoubleSpinBox

    doubleSpinBox_cofactor_radius: QtWidgets.QDoubleSpinBox

    doubleSpinBox_designer_temperature: QtWidgets.QDoubleSpinBox

    doubleSpinBox_interface_cutoff: QtWidgets.QDoubleSpinBox

    doubleSpinBox_ligand_radius: QtWidgets.QDoubleSpinBox

    doubleSpinBox_max_interact_dist: QtWidgets.QDoubleSpinBox

    doubleSpinBox_minmal_mutant_distance: QtWidgets.QDoubleSpinBox

    doubleSpinBox_sidechain_solver_radius: QtWidgets.QDoubleSpinBox

    doubleSpinBox_surface_cutoff: QtWidgets.QDoubleSpinBox

    doubleSpinBox_ws_view_broadcast_interval: QtWidgets.QDoubleSpinBox

    formLayout_cluster_agglomerative: QtWidgets.QFormLayout

    formLayout_cluster_kmeans: QtWidgets.QFormLayout

    gridLayout: QtWidgets.QGridLayout

    gridLayout_16: QtWidgets.QGridLayout

    gridLayout_2: QtWidgets.QGridLayout

    gridLayout_3: QtWidgets.QGridLayout

    gridLayout_5: QtWidgets.QGridLayout

    gridLayout_6: QtWidgets.QGridLayout

    gridLayout_IO: QtWidgets.QGridLayout

    gridLayout_cluster_evo: QtWidgets.QGridLayout

    gridLayout_cluster_general_numbers: QtWidgets.QGridLayout

    gridLayout_design_status: QtWidgets.QGridLayout

    gridLayout_interact_pairs: QtWidgets.QGridLayout

    groupBox: QtWidgets.QGroupBox

    groupBox_10: QtWidgets.QGroupBox

    groupBox_11: QtWidgets.QGroupBox

    groupBox_12: QtWidgets.QGroupBox

    groupBox_13: QtWidgets.QGroupBox

    groupBox_16: QtWidgets.QGroupBox

    groupBox_17: QtWidgets.QGroupBox

    groupBox_2: QtWidgets.QGroupBox

    groupBox_20: QtWidgets.QGroupBox

    groupBox_21: QtWidgets.QGroupBox

    groupBox_22: QtWidgets.QGroupBox

    groupBox_4: QtWidgets.QGroupBox

    groupBox_5: QtWidgets.QGroupBox

    groupBox_6: QtWidgets.QGroupBox

    groupBox_7: QtWidgets.QGroupBox

    groupBox_8: QtWidgets.QGroupBox

    groupBox_9: QtWidgets.QGroupBox

    groupBox_IO_2: QtWidgets.QGroupBox

    groupBox_choice: QtWidgets.QGroupBox

    groupBox_design_status: QtWidgets.QGroupBox

    groupBox_functional: QtWidgets.QGroupBox

    groupBox_reject_substitution: QtWidgets.QGroupBox

    groupBox_surface: QtWidgets.QGroupBox

    groupBox_ws_client_settings: QtWidgets.QGroupBox

    groupBox_ws_server_settings: QtWidgets.QGroupBox

    horizontalLayout: QtWidgets.QHBoxLayout

    horizontalLayout_10: QtWidgets.QHBoxLayout

    horizontalLayout_11: QtWidgets.QHBoxLayout

    horizontalLayout_12: QtWidgets.QHBoxLayout

    horizontalLayout_13: QtWidgets.QHBoxLayout

    horizontalLayout_14: QtWidgets.QHBoxLayout

    horizontalLayout_15: QtWidgets.QHBoxLayout

    horizontalLayout_16: QtWidgets.QHBoxLayout

    horizontalLayout_17: QtWidgets.QHBoxLayout

    horizontalLayout_18: QtWidgets.QHBoxLayout

    horizontalLayout_19: QtWidgets.QHBoxLayout

    horizontalLayout_2: QtWidgets.QHBoxLayout

    horizontalLayout_20: QtWidgets.QHBoxLayout

    horizontalLayout_21: QtWidgets.QHBoxLayout

    horizontalLayout_23: QtWidgets.QHBoxLayout

    horizontalLayout_24: QtWidgets.QHBoxLayout

    horizontalLayout_25: QtWidgets.QHBoxLayout

    horizontalLayout_26: QtWidgets.QHBoxLayout

    horizontalLayout_27: QtWidgets.QHBoxLayout

    horizontalLayout_28: QtWidgets.QHBoxLayout

    horizontalLayout_29: QtWidgets.QHBoxLayout

    horizontalLayout_3: QtWidgets.QHBoxLayout

    horizontalLayout_30: QtWidgets.QHBoxLayout

    horizontalLayout_31: QtWidgets.QHBoxLayout

    horizontalLayout_32: QtWidgets.QHBoxLayout

    horizontalLayout_33: QtWidgets.QHBoxLayout

    horizontalLayout_34: QtWidgets.QHBoxLayout

    horizontalLayout_35: QtWidgets.QHBoxLayout

    horizontalLayout_36: QtWidgets.QHBoxLayout

    horizontalLayout_37: QtWidgets.QHBoxLayout

    horizontalLayout_39: QtWidgets.QHBoxLayout

    horizontalLayout_4: QtWidgets.QHBoxLayout

    horizontalLayout_40: QtWidgets.QHBoxLayout

    horizontalLayout_42: QtWidgets.QHBoxLayout

    horizontalLayout_43: QtWidgets.QHBoxLayout

    horizontalLayout_44: QtWidgets.QHBoxLayout

    horizontalLayout_45: QtWidgets.QHBoxLayout

    horizontalLayout_46: QtWidgets.QHBoxLayout

    horizontalLayout_47: QtWidgets.QHBoxLayout

    horizontalLayout_48: QtWidgets.QHBoxLayout

    horizontalLayout_49: QtWidgets.QHBoxLayout

    horizontalLayout_5: QtWidgets.QHBoxLayout

    horizontalLayout_50: QtWidgets.QHBoxLayout

    horizontalLayout_51: QtWidgets.QHBoxLayout

    horizontalLayout_52: QtWidgets.QHBoxLayout

    horizontalLayout_53: QtWidgets.QHBoxLayout

    horizontalLayout_54: QtWidgets.QHBoxLayout

    horizontalLayout_55: QtWidgets.QHBoxLayout

    horizontalLayout_56: QtWidgets.QHBoxLayout

    horizontalLayout_57: QtWidgets.QHBoxLayout

    horizontalLayout_58: QtWidgets.QHBoxLayout

    horizontalLayout_59: QtWidgets.QHBoxLayout

    horizontalLayout_6: QtWidgets.QHBoxLayout

    horizontalLayout_60: QtWidgets.QHBoxLayout

    horizontalLayout_61: QtWidgets.QHBoxLayout

    horizontalLayout_62: QtWidgets.QHBoxLayout

    horizontalLayout_64: QtWidgets.QHBoxLayout

    horizontalLayout_7: QtWidgets.QHBoxLayout

    horizontalLayout_8: QtWidgets.QHBoxLayout

    horizontalLayout_9: QtWidgets.QHBoxLayout

    horizontalLayout_cluster_evo_esm: QtWidgets.QHBoxLayout

    horizontalLayout_cluster_evo_pssm: QtWidgets.QHBoxLayout

    horizontalLayout_cluster_evo_structure: QtWidgets.QHBoxLayout

    horizontalLayout_cluster_method: QtWidgets.QHBoxLayout

    horizontalLayout_design_case: QtWidgets.QHBoxLayout

    horizontalLayout_evaluate_row2: QtWidgets.QHBoxLayout

    horizontalLayout_interact: QtWidgets.QHBoxLayout

    horizontalLayout_mutate_row2: QtWidgets.QHBoxLayout

    horizontalLayout_socket_row2: QtWidgets.QHBoxLayout

    horizontalLayout_socket_row4: QtWidgets.QHBoxLayout

    horizontalLayout_tab_cluster: QtWidgets.QHBoxLayout

    horizontalLayout_topbar: QtWidgets.QHBoxLayout

    horizontalLayout_visualize_row2: QtWidgets.QHBoxLayout

    label: QtWidgets.QLabel

    label_2: QtWidgets.QLabel

    label_28: QtWidgets.QLabel

    label_3: QtWidgets.QLabel

    label_4: QtWidgets.QLabel

    label_40: QtWidgets.QLabel

    label_41: QtWidgets.QLabel

    label_42: QtWidgets.QLabel

    label_43: QtWidgets.QLabel

    label_44: QtWidgets.QLabel

    label_47: QtWidgets.QLabel

    label_48: QtWidgets.QLabel

    label_5: QtWidgets.QLabel

    label_53: QtWidgets.QLabel

    label_chainid: QtWidgets.QLabel

    label_chainid_10: QtWidgets.QLabel

    label_chainid_11: QtWidgets.QLabel

    label_chainid_12: QtWidgets.QLabel

    label_chainid_13: QtWidgets.QLabel

    label_chainid_14: QtWidgets.QLabel

    label_chainid_6: QtWidgets.QLabel

    label_chainid_7: QtWidgets.QLabel

    label_chainid_8: QtWidgets.QLabel

    label_chainid_9: QtWidgets.QLabel

    label_cluster_agglomerative_linkage: QtWidgets.QLabel

    label_cluster_agglomerative_linkage_value: QtWidgets.QLabel

    label_cluster_agglomerative_matrix: QtWidgets.QLabel

    label_cluster_agglomerative_metric: QtWidgets.QLabel

    label_cluster_agglomerative_metric_value: QtWidgets.QLabel

    label_cluster_agglomerative_representative: QtWidgets.QLabel

    label_cluster_agglomerative_representative_value: QtWidgets.QLabel

    label_cluster_evo_esm: QtWidgets.QLabel

    label_cluster_evo_mutation_col: QtWidgets.QLabel

    label_cluster_evo_pssm: QtWidgets.QLabel

    label_cluster_evo_structure: QtWidgets.QLabel

    label_cluster_evo_weight_esm: QtWidgets.QLabel

    label_cluster_evo_weight_physchem: QtWidgets.QLabel

    label_cluster_evo_weight_pssm: QtWidgets.QLabel

    label_cluster_evo_weight_seq: QtWidgets.QLabel

    label_cluster_evo_weight_spatial: QtWidgets.QLabel

    label_cluster_kmeans_feature_space: QtWidgets.QLabel

    label_cluster_kmeans_feature_space_value: QtWidgets.QLabel

    label_cluster_kmeans_representative: QtWidgets.QLabel

    label_cluster_kmeans_representative_value: QtWidgets.QLabel

    label_cluster_legacy_warning: QtWidgets.QLabel

    label_cluster_method: QtWidgets.QLabel

    label_cluster_random_seed: QtWidgets.QLabel

    label_cofactor_radius: QtWidgets.QLabel

    label_cofactor_sel: QtWidgets.QLabel

    label_input_mut_table: QtWidgets.QLabel

    label_input_mut_table_2: QtWidgets.QLabel

    label_input_pssm_csv: QtWidgets.QLabel

    label_input_pssm_csv_2: QtWidgets.QLabel

    label_input_pssm_csv_3: QtWidgets.QLabel

    label_ligand_radius: QtWidgets.QLabel

    label_ligand_radius_2: QtWidgets.QLabel

    label_ligand_sel: QtWidgets.QLabel

    label_molecule: QtWidgets.QLabel

    label_molecule_11: QtWidgets.QLabel

    label_molecule_13: QtWidgets.QLabel

    label_molecule_14: QtWidgets.QLabel

    label_molecule_2: QtWidgets.QLabel

    label_molecule_3: QtWidgets.QLabel

    label_molecule_4: QtWidgets.QLabel

    label_molecule_5: QtWidgets.QLabel

    label_molecule_8: QtWidgets.QLabel

    label_nproc: QtWidgets.QLabel

    label_output_pse: QtWidgets.QLabel

    label_output_pse_2: QtWidgets.QLabel

    label_output_pse_3: QtWidgets.QLabel

    label_output_pse_4: QtWidgets.QLabel

    label_selected_mutant: QtWidgets.QLabel

    label_surface_cutoff: QtWidgets.QLabel

    label_surface_cutoff_2: QtWidgets.QLabel

    label_surface_exclusion: QtWidgets.QLabel

    label_total_mutant: QtWidgets.QLabel

    # WARNING: Unknown widget class 'QLCDNumber'; using QtWidgets.QWidget.
    lcdNumber_selected_mutant: QtWidgets.QWidget

    # WARNING: Unknown widget class 'QLCDNumber'; using QtWidgets.QWidget.
    lcdNumber_total_mutant: QtWidgets.QWidget

    # WARNING: Unknown widget class 'Line'; using QtWidgets.QWidget.
    line: QtWidgets.QWidget

    lineEdit_cluster_evo_esm1v_table: QtWidgets.QLineEdit

    lineEdit_cluster_evo_esm_mutation_col: QtWidgets.QLineEdit

    lineEdit_cluster_evo_pssm_profile: QtWidgets.QLineEdit

    lineEdit_cluster_evo_structure_pdb: QtWidgets.QLineEdit

    lineEdit_current_pair: QtWidgets.QLineEdit

    lineEdit_current_pair_mut_score: QtWidgets.QLineEdit

    lineEdit_current_pair_score: QtWidgets.QLineEdit

    lineEdit_current_pair_wt_score: QtWidgets.QLineEdit

    lineEdit_design_case: QtWidgets.QLineEdit

    lineEdit_input_csv: QtWidgets.QLineEdit

    lineEdit_input_csv_2: QtWidgets.QLineEdit

    lineEdit_input_customized_indices: QtWidgets.QLineEdit

    lineEdit_input_gremlin_mtx: QtWidgets.QLineEdit

    lineEdit_input_mut_table: QtWidgets.QLineEdit

    lineEdit_input_mut_table_csv: QtWidgets.QLineEdit

    lineEdit_interact_chain_binding: QtWidgets.QLineEdit

    lineEdit_multi_design_mutant_table: QtWidgets.QLineEdit

    lineEdit_output_mut_table: QtWidgets.QLineEdit

    lineEdit_output_mutant_table: QtWidgets.QLineEdit

    lineEdit_output_pse_mutate: QtWidgets.QLineEdit

    lineEdit_output_pse_pocket: QtWidgets.QLineEdit

    lineEdit_output_pse_surface: QtWidgets.QLineEdit

    lineEdit_output_pse_visualize: QtWidgets.QLineEdit

    lineEdit_preffer_substitution: QtWidgets.QLineEdit

    lineEdit_reject_substitution: QtWidgets.QLineEdit

    lineEdit_score_maxima: QtWidgets.QLineEdit

    lineEdit_score_minima: QtWidgets.QLineEdit

    lineEdit_ws_server_key: QtWidgets.QLineEdit

    lineEdit_ws_server_url_to_connect: QtWidgets.QLineEdit

    menuAbout: QtWidgets.QMenu

    menuBackbone_Rebuild: QtWidgets.QMenu

    menuDesign_Tools: QtWidgets.QMenu

    menuEdit: QtWidgets.QMenu

    menuEdit_Configuration: QtWidgets.QMenu

    menuEditor_Backend: QtWidgets.QMenu

    menuEnvironment_Variables: QtWidgets.QMenu

    menuEvolution: QtWidgets.QMenu

    menuExperiment: QtWidgets.QMenu

    menuExport_Tools: QtWidgets.QMenu

    menuFile: QtWidgets.QMenu

    menuFormatters: QtWidgets.QMenu

    menuGromacs_Utils: QtWidgets.QMenu

    menuHelp: QtWidgets.QMenu

    menuLanguage: QtWidgets.QMenu

    menuLog_File: QtWidgets.QMenu

    menuMD_analysis: QtWidgets.QMenu

    menuModeling_Tools: QtWidgets.QMenu

    menuMolecular_Dynamics: QtWidgets.QMenu

    menuMutant_Effects: QtWidgets.QMenu

    menuOpenMM: QtWidgets.QMenu

    menuPredictor_Tools: QtWidgets.QMenu

    menuRFdiffusion: QtWidgets.QMenu

    menuRecent_Experiments: QtWidgets.QMenu

    menuRender_Sidechains: QtWidgets.QMenu

    menuRosetta_Tools: QtWidgets.QMenu

    menuRuntime: QtWidgets.QMenu

    menuSmall_Molecule: QtWidgets.QMenu

    menuStructure_Tools: QtWidgets.QMenu

    menuStyle: QtWidgets.QMenu

    menuTools: QtWidgets.QMenu

    menuUI_Preferences: QtWidgets.QMenu

    menuUtils: QtWidgets.QMenu

    menuVina_Tools: QtWidgets.QMenu

    menubar: QtWidgets.QMenuBar

    page: QtWidgets.QWidget

    page_2: QtWidgets.QWidget

    page_3: QtWidgets.QWidget

    page_4: QtWidgets.QWidget

    page_5: QtWidgets.QWidget

    page_cluster_agglomerative: QtWidgets.QWidget

    page_cluster_evo: QtWidgets.QWidget

    page_cluster_kmeans: QtWidgets.QWidget

    page_cluster_legacy: QtWidgets.QWidget

    progressBar: QtWidgets.QProgressBar

    pushButton_accept_this_mutant: QtWidgets.QPushButton

    pushButton_choose_lucky_mutant: QtWidgets.QPushButton

    pushButton_dump_interfaces: QtWidgets.QPushButton

    pushButton_export_mutant_pdbs: QtWidgets.QPushButton

    pushButton_goto_best_hit_in_group: QtWidgets.QPushButton

    pushButton_interact_accept: QtWidgets.QPushButton

    pushButton_interact_reject: QtWidgets.QPushButton

    pushButton_load_mutant_choice_checkpoint: QtWidgets.QPushButton

    pushButton_multi_design_end_this_design: QtWidgets.QPushButton

    pushButton_multi_design_export_mutants_from_table: QtWidgets.QPushButton

    pushButton_multi_design_initialize: QtWidgets.QPushButton

    pushButton_multi_design_left: QtWidgets.QPushButton

    pushButton_multi_design_right: QtWidgets.QPushButton

    pushButton_multi_design_start_new_design: QtWidgets.QPushButton

    pushButton_next: QtWidgets.QPushButton

    pushButton_next_mutant: QtWidgets.QPushButton

    pushButton_open_cluster_evo_esm1v_table: QtWidgets.QPushButton

    pushButton_open_cluster_evo_pssm_profile: QtWidgets.QPushButton

    pushButton_open_cluster_evo_structure_pdb: QtWidgets.QPushButton

    pushButton_open_customized_indices: QtWidgets.QPushButton

    pushButton_open_gremlin_mtx: QtWidgets.QPushButton

    pushButton_open_input_csv: QtWidgets.QPushButton

    pushButton_open_input_csv_2: QtWidgets.QPushButton

    pushButton_open_mut_table: QtWidgets.QPushButton

    pushButton_open_mut_table_2: QtWidgets.QPushButton

    pushButton_open_mut_table_csv: QtWidgets.QPushButton

    pushButton_open_mut_table_csv_2: QtWidgets.QPushButton

    pushButton_open_output_pse_mutate: QtWidgets.QPushButton

    pushButton_open_output_pse_pocket: QtWidgets.QPushButton

    pushButton_open_output_pse_surface: QtWidgets.QPushButton

    pushButton_open_output_pse_visualize: QtWidgets.QPushButton

    pushButton_open_save_mutant_table: QtWidgets.QPushButton

    pushButton_previous: QtWidgets.QPushButton

    pushButton_previous_mutant: QtWidgets.QPushButton

    pushButton_reduce_this_session: QtWidgets.QPushButton

    pushButton_reinitialize_interact: QtWidgets.QPushButton

    pushButton_reinitialize_mutant_choosing: QtWidgets.QPushButton

    pushButton_reject_this_mutant: QtWidgets.QPushButton

    pushButton_run_PSSM_to_pse: QtWidgets.QPushButton

    pushButton_run_cluster: QtWidgets.QPushButton

    pushButton_run_interact_scan: QtWidgets.QPushButton

    pushButton_run_multi_design: QtWidgets.QPushButton

    pushButton_run_pocket_detection: QtWidgets.QPushButton

    pushButton_run_surface_detection: QtWidgets.QPushButton

    pushButton_run_surface_refresh: QtWidgets.QPushButton

    pushButton_run_visualizing: QtWidgets.QPushButton

    pushButton_save_this_mutant_table: QtWidgets.QPushButton

    pushButton_ws_connect_to_server: QtWidgets.QPushButton

    pushButton_ws_disconnect_from_server: QtWidgets.QPushButton

    pushButton_ws_generate_randomized_key: QtWidgets.QPushButton

    spinBox_cluster_batchsize: QtWidgets.QSpinBox

    spinBox_cluster_random_seed: QtWidgets.QSpinBox

    spinBox_designer_batch: QtWidgets.QSpinBox

    spinBox_designer_num_samples: QtWidgets.QSpinBox

    spinBox_gremlin_topN: QtWidgets.QSpinBox

    spinBox_maximal_multi_design_variant_num: QtWidgets.QSpinBox

    spinBox_maximal_mutant_num: QtWidgets.QSpinBox

    spinBox_nproc: QtWidgets.QSpinBox

    spinBox_num_cluster: QtWidgets.QSpinBox

    spinBox_num_mut_maximum: QtWidgets.QSpinBox

    spinBox_num_mut_minimun: QtWidgets.QSpinBox

    spinBox_randomized_sampling: QtWidgets.QSpinBox

    spinBox_ws_server_port: QtWidgets.QSpinBox

    stackedWidget: QtWidgets.QStackedWidget

    stackedWidget_cluster_method_settings: QtWidgets.QStackedWidget

    statusbar: QtWidgets.QStatusBar

    tabWidget: QtWidgets.QTabWidget

    tab_cluster: QtWidgets.QWidget

    tab_config: QtWidgets.QWidget

    tab_evaluate: QtWidgets.QWidget

    tab_interact: QtWidgets.QWidget

    tab_mutate: QtWidgets.QWidget

    tab_prepare: QtWidgets.QWidget

    tab_socket: QtWidgets.QWidget

    tab_visualize: QtWidgets.QWidget

    # WARNING: Unknown widget class 'QToolBox'; using QtWidgets.QWidget.
    toolBox: QtWidgets.QWidget

    treeWidget_ws_peers: QtWidgets.QTreeWidget

    verticalLayout: QtWidgets.QVBoxLayout

    verticalLayout_10: QtWidgets.QVBoxLayout

    verticalLayout_11: QtWidgets.QVBoxLayout

    verticalLayout_12: QtWidgets.QVBoxLayout

    verticalLayout_13: QtWidgets.QVBoxLayout

    verticalLayout_14: QtWidgets.QVBoxLayout

    verticalLayout_15: QtWidgets.QVBoxLayout

    verticalLayout_16: QtWidgets.QVBoxLayout

    verticalLayout_17: QtWidgets.QVBoxLayout

    verticalLayout_18: QtWidgets.QVBoxLayout

    verticalLayout_19: QtWidgets.QVBoxLayout

    verticalLayout_2: QtWidgets.QVBoxLayout

    verticalLayout_20: QtWidgets.QVBoxLayout

    verticalLayout_3: QtWidgets.QVBoxLayout

    verticalLayout_4: QtWidgets.QVBoxLayout

    verticalLayout_5: QtWidgets.QVBoxLayout

    verticalLayout_6: QtWidgets.QVBoxLayout

    verticalLayout_7: QtWidgets.QVBoxLayout

    verticalLayout_8: QtWidgets.QVBoxLayout

    verticalLayout_9: QtWidgets.QVBoxLayout

    verticalLayout_central: QtWidgets.QVBoxLayout

    verticalLayout_cluster_general: QtWidgets.QVBoxLayout

    verticalLayout_cluster_legacy: QtWidgets.QVBoxLayout

    verticalLayout_cluster_post: QtWidgets.QVBoxLayout

    verticalLayout_cluster_right: QtWidgets.QVBoxLayout

    verticalLayout_interact_right: QtWidgets.QVBoxLayout

    verticalLayout_mutate_left: QtWidgets.QVBoxLayout

    verticalLayout_mutate_right: QtWidgets.QVBoxLayout

    verticalLayout_tab_config: QtWidgets.QVBoxLayout

    verticalLayout_tab_evaluate: QtWidgets.QVBoxLayout

    verticalLayout_tab_interact: QtWidgets.QVBoxLayout

    verticalLayout_tab_mutate: QtWidgets.QVBoxLayout

    verticalLayout_tab_prepare: QtWidgets.QVBoxLayout

    verticalLayout_tab_socket: QtWidgets.QVBoxLayout

    verticalLayout_tab_visualize: QtWidgets.QVBoxLayout
