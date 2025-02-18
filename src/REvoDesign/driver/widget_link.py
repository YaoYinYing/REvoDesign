'''
This module contains the definitions of the push button IDs and configuration-widget mapping used in the application.
'''

from dataclasses import dataclass
from typing import Tuple

from immutabledict import immutabledict

from REvoDesign.Qt import QtWidgets


@dataclass(frozen=True)
class PushButtons:
    """
    A class to define the IDs of push buttons used in the application.

    Attributes:
        button_ids (list[str]): A list of button IDs.
    """

    button_ids: Tuple = (
        "open_output_pse_pocket",
        "open_output_pse_surface",
        "run_surface_refresh",
        "dump_interfaces",
        "run_surface_detection",
        "run_pocket_detection",
        "open_output_pse_mutate",
        "open_customized_indices",
        "open_input_csv",
        "run_PSSM_to_pse",
        "open_mut_table",
        "reinitialize_mutant_choosing",
        "goto_best_hit_in_group",
        "load_mutant_choice_checkpoint",
        "choose_lucky_mutant",
        "previous_mutant",
        "next_mutant",
        "reject_this_mutant",
        "accept_this_mutant",
        "open_mut_table_2",
        "run_cluster",
        "save_this_mutant_table",
        "open_input_csv_2",
        "open_mut_table_csv",
        "open_output_pse_visualize",
        "run_visualizing",
        "reduce_this_session",
        "open_mut_table_csv_2",
        "multi_design_initialize",
        "multi_design_start_new_design",
        "multi_design_left",
        "multi_design_right",
        "multi_design_end_this_design",
        "multi_design_export_mutants_from_table",
        "run_multi_design",
        "open_gremlin_mtx",
        "reinitialize_interact",
        "run_interact_scan",
        "open_save_mutant_table",
        "interact_reject",
        "interact_accept",
        "ws_generate_randomized_key",
        "ws_connect_to_server",
        "ws_disconnect_from_server",
        "previous",
        "next",
    )


@dataclass(frozen=True)
class Config2WidgetIds:
    """
    This class defines the mappings between configuration items and widget IDs, as well as the widget types.

    Attributes:
        wi_types (immutabledict): A mapping of widget type names to their corresponding Qt widget classes.
        c2wi (immutabledict[str, str]): A mapping of configuration item keys to widget IDs.

    Methods:
        get_widget_typing(widget_id: str): Returns the Qt widget class corresponding to the given widget ID.
    """

    wi_types: immutabledict[str, QtWidgets.QWidget] = immutabledict(
        {
            "pushButton": QtWidgets.QPushButton,
            "lineEdit": QtWidgets.QLineEdit,
            "comboBox": QtWidgets.QComboBox,
            "spinBox": QtWidgets.QSpinBox,
            "doubleSpinBox": QtWidgets.QDoubleSpinBox,
            "checkBox": QtWidgets.QCheckBox,
        }
    )

    c2wi: immutabledict[str, str] = immutabledict(
        {
            "ui.header_panel.cmap.default": "comboBox_cmap",
            "ui.prepare.cofactor_radius": "doubleSpinBox_cofactor_radius",
            "ui.prepare.ligand_radius": "doubleSpinBox_ligand_radius",
            "ui.prepare.chain_dist": "doubleSpinBox_interface_cutoff",
            "ui.prepare.surface_probe_radius": "doubleSpinBox_surface_cutoff",
            "ui.header_panel.cmap.reverse_score": "checkBox_reverse_mutant_effect",
            "ui.mutate.max_score": "lineEdit_score_maxima",
            "ui.mutate.min_score": "lineEdit_score_minima",
            "ui.mutate.reject": "lineEdit_reject_substitution",
            "ui.mutate.accept": "lineEdit_preffer_substitution",
            "ui.mutate.designer.randomized_sampling": "spinBox_randomized_sampling",
            "ui.mutate.designer.enable_randomized_sampling": "checkBox_randomized_sampling",
            "ui.mutate.designer.deduplicate_designs": "checkBox_deduplicate_designs",
            "ui.mutate.designer.homooligomeric": "checkBox_designer_homooligomeric",
            "ui.mutate.designer.batch": "spinBox_designer_batch",
            "ui.mutate.designer.num_sample": "spinBox_designer_num_samples",
            "ui.mutate.designer.temperature": "doubleSpinBox_designer_temperature",
            "ui.cluster.score_matrix.default": "comboBox_cluster_matrix",
            "ui.cluster.shuffle": "checkBox_shuffle_clustering",
            "ui.cluster.mut_num_max": "spinBox_num_mut_maximum",
            "ui.cluster.mut_num_min": "spinBox_num_mut_minimun",
            "ui.cluster.num_cluster": "spinBox_num_cluster",
            "ui.cluster.batch_size": "spinBox_cluster_batchsize",
            "ui.cluster.mutate_relax": "checkBox_cluster_mutate_and_relax",
            "ui.visualize.global_score_policy": "checkBox_global_score_policy",
            "ui.interact.chain_binding.enabled": "checkBox_interact_bind_chain_mode",
            "ui.interact.chain_binding.chains_to_bind": "lineEdit_interact_chain_binding",
            "ui.interact.topN_pairs": "spinBox_gremlin_topN",
            "ui.interact.max_interact_dist": "doubleSpinBox_max_interact_dist",
            "ui.interact.use_external_scorer": "comboBox_external_scorer",
            "ui.socket.server_url": "lineEdit_ws_server_url_to_connect",
            "ui.socket.server_mode": "checkBox_ws_server_mode",
            "ui.socket.server_port": "spinBox_ws_server_port",
            "ui.socket.use_key": "checkBox_ws_server_use_key",
            "ui.socket.broadcast.interval": "doubleSpinBox_ws_view_broadcast_interval",
            "ui.socket.broadcast.view": "checkBox_ws_broadcast_view",
            "ui.socket.receive.mutagenesis": "checkBox_ws_recieve_mutagenesis_broadcast",
            "ui.socket.receive.view": "checkBox_ws_recieve_view_broadcast",
            "ui.config.sidechain_solver.use": "comboBox_sidechain_solver",
            "ui.config.sidechain_solver.repack_radius": "doubleSpinBox_sidechain_solver_radius",
            "ui.config.sidechain_solver.model": "comboBox_sidechain_solver_model",
            "ui.header_panel.input.molecule": "comboBox_design_molecule",
            "ui.header_panel.input.chain_id": "comboBox_chain_id",
            "ui.header_panel.nproc": "spinBox_nproc",
            "ui.prepare.input.pocket.to_pse": "lineEdit_output_pse_pocket",
            "ui.prepare.input.pocket.substrate": "comboBox_ligand_sel",
            "ui.prepare.input.pocket.cofactor": "comboBox_cofactor_sel",
            "ui.prepare.input.surface.to_pse": "lineEdit_output_pse_surface",
            "ui.prepare.input.surface.exclusion": "comboBox_surface_exclusion",
            "ui.mutate.input.to_pse": "lineEdit_output_pse_mutate",
            "ui.mutate.input.profile": "lineEdit_input_csv",
            "ui.mutate.input.profile_type": "comboBox_profile_type",
            "ui.mutate.input.design_case": "lineEdit_design_case",
            "ui.mutate.input.residue_ids": "lineEdit_input_customized_indices",
            "ui.evaluate.input.to_mutant_txt": "lineEdit_output_mut_table",
            "ui.evaluate.show_wt": "checkBox_show_wt",
            "ui.cluster.input.from_mutant_txt": "lineEdit_input_mut_table",
            "ui.visualize.input.to_pse": "lineEdit_output_pse_visualize",
            "ui.visualize.input.from_mutant_txt": "lineEdit_input_mut_table_csv",
            "ui.visualize.input.profile": "lineEdit_input_csv_2",
            "ui.visualize.input.profile_type": "comboBox_profile_type_2",
            "ui.visualize.input.group_name": "comboBox_group_name",
            "ui.visualize.input.best_leaf": "comboBox_best_leaf",
            "ui.visualize.input.totalscore": "comboBox_totalscore",
            "ui.visualize.input.multi_design.to_mutant_txt": "lineEdit_multi_design_mutant_table",
            "ui.visualize.multi_design.num_mut_max": "spinBox_maximal_mutant_num",
            "ui.visualize.multi_design.num_variant_max": "spinBox_maximal_multi_design_variant_num",
            "ui.visualize.multi_design.spatial_dist": "doubleSpinBox_minmal_mutant_distance",
            "ui.visualize.multi_design.use_bond_CA": "checkBox_multi_design_bond_CA",
            "ui.visualize.multi_design.use_sidechain_orientation": "checkBox_multi_design_check_sidechain_orientations",
            "ui.visualize.multi_design.use_external_scorer": "checkBox_multi_design_use_external_scorer",
            "ui.visualize.multi_design.color_by_scores": "checkBox_multi_design_color_by_scores",
            "ui.interact.input.gremlin_pkl": "lineEdit_input_gremlin_mtx",
            "ui.interact.input.to_mutant_txt": "lineEdit_output_mutant_table",
            "ui.socket.input.key": "lineEdit_ws_server_key",
            "rosetta.node_hint": "comboBox_rosetta_node_hint",
        }
    )

    def get_widget_typing(self, widget_id: str):
        """
        Returns the Qt widget class corresponding to the given widget ID.

        Args:
            widget_id (str): The ID of the widget.

        Returns:
            QtWidgets.QWidget: The corresponding Qt widget class.
        """
        widget_type = widget_id.split("_")[0]
        if widget_type not in self.wi_types:
            raise NotImplementedError(
                f"widget {widget_id} is not supported yet."
            )
        return self.wi_types.get(widget_type)
