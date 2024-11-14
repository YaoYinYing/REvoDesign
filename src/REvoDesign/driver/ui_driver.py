import os
import warnings
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Dict, List, Tuple, Union

import matplotlib
from Bio.Align import substitution_matrices
from immutabledict import immutabledict
from omegaconf import DictConfig, OmegaConf
from pymol.Qt import QtGui, QtWidgets  # type: ignore
from RosettaPy.node import NodeHintT

from REvoDesign import SingletonAbstract, issues, reload_config_file
from REvoDesign.citations import CitableModules
from REvoDesign.logger import root_logger
from REvoDesign.tools.customized_widgets import (create_cmap_icon,
                                                 get_widget_value,
                                                 set_widget_value)
from REvoDesign.tools.utils import dirname_does_exist, filepath_does_exists

logging = root_logger.getChild(__name__)


class ConfigBus(SingletonAbstract, CitableModules):
    """
    This class is responsible for handling the configuration and interaction between the UI widgets
    and the application's configuration settings.

    Attributes:
        ui (QtWidgets.QWidget): The main UI widget of the application.
        cfg (OmegaConf): The application's configuration settings.
        w2c (Widget2ConfigMapper): A mapper object that maps UI widgets to configuration settings.
        push_buttons (dict): A dictionary of UI buttons.

    Methods:
        initialize_widget_with_cfg_group(): Initializes UI widgets with their corresponding configuration settings.
        update_cfg_item_from_widget(widget_id: str): Updates a configuration setting based on the value of a UI widget.
        register_widget_changes_to_cfg(): Registers UI widget changes to update the configuration settings.
        get_widget_from_id(widget_id: str): Retrieves a UI widget based on its ID.
        get_widget_from_cfg_item(cfg_item: str): Retrieves a UI widget based on its corresponding configuration item.
        get_widget_value(cfg_item: str): Retrieves the value of a UI widget based on its corresponding
            configuration item.
        set_widget_value(cfg_item: str, value): Sets the value of a UI widget based on its corresponding
            configuration item.
        restore_widget_value(cfg_item: str): Restores the value of a UI widget to its default configuration setting.
        get_cfg_item(widget_id: str): Retrieves the configuration item corresponding to a UI widget ID.
        get_value(cfg_item: str, typing=None): Retrieves the value of a configuration item, with optional type casting.
        set_value(cfg_item: str, value): Sets the value of a configuration item.
        toggle_buttons(buttons: Iterable, set_enabled: bool = False): Toggles the enabled state of a list of buttons.
        fp_lock(cfg_fps: Union[list, tuple, str], buttons_id_to_release: Union[list, tuple, str]): Locks or unlocks
            buttons based on the existence of file paths in the configuration.
        button(id: str): Retrieves a button widget based on its ID.
    """

    def __init__(self, ui=None):
        # Check if the instance has already been initialized
        if not hasattr(self, "initialized"):
            # If not, set the instance attributes

            self.cfg: DictConfig = reload_config_file()
            if ui:
                self.ui = ui
                self.w2c = Widget2ConfigMapper(ui=self.ui)
                self.push_buttons = self.w2c.push_buttons

            # Mark the instance as initialized to prevent reinitialization
            self.initialized = True
            self.cite()

    @classmethod
    def initialize(cls, ui):
        if not cls._instance:
            cls(ui=ui)
        else:
            cls._instance.ui = ui

    def initialize_widget_with_group(self):
        # Initializes UI widgets with their corresponding configuration settings.

        for widget_id, group_cfgs in self.w2c.group_register.items():
            group_values = []
            widget = self.get_widget_from_id(widget_id=widget_id)
            if isinstance(widget, str):
                raise TypeError("widget cannot be string")

            # digest the string to values
            for j, group_cfg in enumerate(group_cfgs):
                if callable(group_cfg):
                    values = group_cfg()
                else:
                    logging.debug(
                        f"Group {j} of widget {widget_id} does not return any values"
                    ) 
                    continue
                
                # exclude blank string, blank list, or blank tuple
                if not values:
                    logging.debug(f"Group {j} of widget {widget_id} is empty: {values}")
                    continue

                if isinstance(values, (list, tuple)):
                    group_values.extend(values)
                elif isinstance(values, dict):
                    if not group_values:
                        group_values = values.copy()
                    else:
                        if not isinstance(group_values, dict):
                            raise TypeError(
                                f"{group_cfg} returns a dict while group_values is"
                                f" a {type(group_cfg)=}, not a dict."
                            )
                        group_values.update(values)

            if not group_values:
                logging.debug(f"No values found for widget {widget_id}")
                continue

            set_widget_value(widget, group_values)

            default_cfg_item = self.w2c.find_config_item(widget_id=widget_id)
            if default_cfg_item:
                self.restore_widget_value(default_cfg_item)

    def update_cfg_item_from_widget(self, widget_id: str):
        # Updates a configuration setting based on the value of a UI widget.

        cfg_item = self.w2c.widget_id2config_dict.get(widget_id)
        widget = self.get_widget_from_id(widget_id=widget_id)
        if not cfg_item:
            return
        value = get_widget_value(widget=widget)
        OmegaConf.update(self.cfg, cfg_item, value)

    def _widget_link(self, widget_id: str):
        return partial(self.update_cfg_item_from_widget, widget_id)

    def register_widget_changes_to_cfg(self):
        # Registers UI widget changes to update the configuration settings.
        for widget_id in self.w2c.all_widget_ids:
            widget = self.get_widget_from_id(widget_id=widget_id)
            if isinstance(
                widget,
                (
                    QtWidgets.QDoubleSpinBox,
                    QtWidgets.QSpinBox,
                    QtWidgets.QProgressBar,
                ),
            ):
                widget.valueChanged.connect(self._widget_link(widget_id))
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentTextChanged.connect(self._widget_link(widget_id))
                widget.editTextChanged.connect(self._widget_link(widget_id))
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(self._widget_link(widget_id))
                widget.textEdited.connect(self._widget_link(widget_id))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(self._widget_link(widget_id))
            else:
                raise NotImplementedError(
                    f"{widget} {type(widget)} is not supported yet"
                )

    def get_widget_from_id(self, widget_id) -> QtWidgets.QWidget:  # type: ignore
        # Retrieves a UI widget based on its ID.

        return self.w2c.widget_id2widget_map.get(widget_id)

    def get_widget_from_cfg_item(self, cfg_item: str) -> QtWidgets.QWidget:  # type: ignore
        # Retrieves a UI widget based on its corresponding configuration item.
        return self.w2c.config2widget_map.get(cfg_item)

    @staticmethod
    def value_converter(value: Any, converter: Any):
        # Handle predefined converters
        predefined_conversions = {
            str: lambda v: str(v),
            float: lambda v: float(v),
            int: lambda v: int(v),
            bool: lambda v: bool(v),
            dict: lambda v: dict(v),
        }
        if converter in predefined_conversions:
            value = predefined_conversions[converter](value)

        # Handle custom callable converters
        elif callable(converter):
            value = converter(value)
        else:
            warnings.warn(
                issues.FallingBackWarning(
                    f"value_converter is asked but no convertion is performed from {type(value)=} to {converter}."
                )
            )
        return value

    def get_widget_value(self, cfg_item: str, converter=None):
        try:
            value = get_widget_value(
                widget=self.get_widget_from_cfg_item(cfg_item)
            )
        except ValueError as e:
            # record error then re-raise it
            logging.error(f'Error in the configuration item: {cfg_item}: {e}')
            raise ValueError(
                "Error in the configuration item: {}".format(cfg_item)
            ) from e

        if converter:
            value = self.value_converter(value, converter)

        # Retrieves the value of a UI widget based on its corresponding configuration item.
        return value

    def set_widget_value(self, cfg_item: str, value, hard=False):
        # Sets the value of a UI widget based on its corresponding configuration item.
        widget = self.get_widget_from_cfg_item(cfg_item)
        set_widget_value(widget=widget, value=value)
        if hard:
            self.set_value(cfg_item=cfg_item, value=value)

    def restore_widget_value(self, cfg_item: str):
        # Restores the value of a UI widget to its default configuration setting.
        widget = self.get_widget_from_cfg_item(cfg_item)
        value = self.get_value(cfg_item)
        set_widget_value(widget=widget, value=value)

    def get_cfg_item(self, widget_id: str) -> str:
        # Retrieves the configuration item corresponding to a UI widget ID.
        return self.w2c.widget_id2config_dict.get(widget_id)  # type: ignore

    def get_value(
        self,
        cfg_item: str,
        converter: Union[Callable, Any] = None,
        reject_none: bool = False,
        default_value: Any = None,
    ):
        # Retrieves the value of a configuration item, with optional type casting.
        value = OmegaConf.select(self.cfg, cfg_item)

        # Default conversions for None values
        default_conversions = {
            Union[str, None]: "",
            Union[int, float]: 0,
            dict: {},
        }

        if reject_none and not value and not default_value:
            raise issues.ConfigureOutofDateError(
                "This configure file might be out of date. Please remove it and restart PyMOL to fix this."
            )

        if value is None:
            if default_value:
                value = default_value
            elif converter in default_conversions:
                value = default_conversions[converter]

        if converter:
            value = self.value_converter(value, converter)

        # Handle list values for groups
        if cfg_item.endswith("group") and value:
            value = list(value)

        return value

    def set_value(self, cfg_item: str, value: Union[str, List, Dict]) -> None:
        # Sets the value of a configuration item.
        if value is not None:
            OmegaConf.update(self.cfg, cfg_item, value)

    def toggle_buttons(
        self,
        button_ids: Union[List[str], Tuple[str]],
        set_enabled: bool = False,
    ):
        # Toggles the enabled state of a list of buttons.
        buttons = self.buttons(button_ids=button_ids)

        for button in buttons:
            if not button:
                continue
            button.setEnabled(set_enabled)

    def fp_lock(
        self,
        cfg_fps: Union[list, tuple, str],
        buttons_id_to_release: Union[list, tuple, str],
    ):
        # Locks or unlocks buttons based on the existence of file paths in the configuration.
        if isinstance(cfg_fps, str):
            cfg_fps = tuple([cfg_fps])

        if not isinstance(buttons_id_to_release, (list, tuple)):
            buttons_id_to_release = [buttons_id_to_release]

        self.toggle_buttons(
            button_ids=buttons_id_to_release, set_enabled=False
        )

        for cfg_fp in cfg_fps:
            _fp = self.get_value(cfg_fp)
            logging.info(f"Checking file path: {_fp}")
            if not _fp or not dirname_does_exist(_fp):
                return

            if not filepath_does_exists(_fp):
                logging.warning(f"The file `{_fp}` is not valid.")
            else:
                logging.info(f"The file `{_fp}` is valid.")

        self.toggle_buttons(button_ids=buttons_id_to_release, set_enabled=True)

    def button(self, button_id: str) -> QtWidgets.QPushButton: # type: ignore
        """Retrieves a button widget based on its ID.

        Args:
            button_id (str): Button ID.

        Returns:
            QtWidgets.QPushButton: Button object
        """
        assert button_id in self.w2c.run_button_ids
        return self.w2c.push_buttons.get(button_id)

    def buttons(self, button_ids: tuple[str]) -> tuple[
        Union[
            QtWidgets.QPushButton,
            None,
        ],
        ...,
    ]:
        """Retrieves all button widgets based on its ID.

        Args:
            button_ids (tuple[str]): Button IDs.

        Returns:
            tuple[QtWidgets.QPushButton]: Button objects in the same order as
                the given IDs.
        """
        assert all(
            button_id in self.w2c.run_button_ids for button_id in button_ids
        )
        return tuple(
            self.w2c.push_buttons.get(button_id) for button_id in button_ids
        )

    __bibtex__ = {
        "hydra": """@Misc{Yadan2019Hydra,
author =       {Omry Yadan},
title =        {Hydra - A framework for elegantly configuring complex applications},
howpublished = {Github},
year =         {2019},
url =          {https://github.com/facebookresearch/hydra}
}"""
    }


@dataclass(frozen=True)
class PushButtons:
    """
    A class to define the IDs of push buttons used in the application.

    Attributes:
        button_ids (list[str]): A list of button IDs.
    """

    button_ids: Tuple = (
        "submit_pssm_gremlin_job",
        "cancel_pssm_gremlin_job",
        "download_pssm_gremlin_job",
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

    wi_types: immutabledict = immutabledict(
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
            "ui.client.pssm_gremlin_url": "lineEdit_pssm_gremlin_url",
            "ui.client.pssm_gremlin_user": "lineEdit_pssm_gremlin_user",
            "ui.client.pssm_gremlin_passwd": "lineEdit_pssm_gremlin_passwd",
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
            "ui.evaluate.rock": "checkBox_rock_pymol",
            "ui.evaluate.show_wt": "checkBox_show_wt",
            "ui.cluster.input.from_mutant_txt": "lineEdit_input_mut_table",
            "ui.visualize.input.to_pse": "lineEdit_output_pse_visualize",
            "ui.visualize.input.from_mutant_txt": "lineEdit_input_mut_table_csv",
            "ui.visualize.input.profile": "lineEdit_input_csv_2",
            "ui.visualize.input.profile_type": "comboBox_profile_type_2",
            "ui.visualize.input.group_name": "lineEdit_group_name",
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


class Widget2ConfigMapper:
    """
    This class maps UI widgets to configuration settings and provides methods to interact with these mappings.

    Attributes:
        ui (QtWidgets.QWidget): The main UI widget of the application.
        group_register (immutabledict[str, Tuple[Callable]]): A mapping of widget IDs to configuration items
            or callable functions.
        run_button_ids (tuple[str]): A tuple of IDs for buttons that trigger actions.
        push_buttons (immutabledict): A mapping of button IDs to button widgets.
        c2wi (Config2WidgetIds): An instance of the Config2WidgetIds class.
        config_widget_id_map (immutabledict): A mapping of configuration items to widget IDs.
        config2widget_map (immutabledict): A mapping of configuration items to widget widgets.
        widget_id2widget_map (immutabledict): A mapping of widget IDs to widget widgets.

    Methods:
        get_button_from_id(button_id): Retrieves a button widget based on its ID.
        get_widget_from_id(widget_id): Retrieves a widget based on its ID.
        _find_config_item(widget_id): Finds the configuration item corresponding to a widget ID.
        _find_widget_id(config_item): Finds the widget ID corresponding to a configuration item.
    """

    def __init__(self, ui):
        self.ui = ui

        self.group_register: immutabledict[str, Tuple[Callable]] = (
            immutabledict(
                {
                    # Header
                    "comboBox_cmap": (CallableGroupValues.list_color_map,),
                    # Tab Cluster
                    "comboBox_cluster_matrix": (
                        CallableGroupValues.list_score_matrix,
                    ),
                    # Tab Config
                    "comboBox_sidechain_solver": (
                        CallableGroupValues.list_installed_mutate_runners,
                    ),
                    # Tab Mutate
                    "comboBox_profile_type": (
                        CallableGroupValues.list_all_profile_parsers,
                        CallableGroupValues.list_all_designers,
                    ),
                    # Tab Visualize
                    "comboBox_profile_type_2": (
                        CallableGroupValues.list_all_profile_parsers,
                        CallableGroupValues.list_all_scorers,
                    ),
                    # Tab Interact
                    "comboBox_external_scorer": (
                        CallableGroupValues.list_some_blanks,
                        CallableGroupValues.list_all_scorers,
                    ),
                    "comboBox_rosetta_node_hint": (
                        CallableGroupValues.list_all_rosetta_node_hints,
                    ),
                }
            )
        )

        self.run_button_ids: tuple[str] = tuple(PushButtons().button_ids)
        self.push_buttons: immutabledict = immutabledict(
            {
                button_id: self.get_button_from_id(button_id=button_id)
                for button_id in self.run_button_ids
            }
        )
        self.c2wi = Config2WidgetIds()
        self.config_widget_id_map: immutabledict = immutabledict(
            self.c2wi.c2wi
        )
        self.config2widget_map: immutabledict = immutabledict(
            {
                c: self.get_widget_from_id(wi)
                for c, wi in self.config_widget_id_map.items()
            }
        )
        self.widget_id2widget_map: immutabledict = immutabledict(
            {
                self._find_widget_id(c): w
                for c, w in self.config2widget_map.items()
            }
        )

    def find_child(self, widget_type, name):
        """
        Find a child widget in a UI object.

        Args:
            widget_type: The type of the widget (e.g., QtWidgets.QLabel).
            name: The name of the widget.

        Returns:
            The found widget, or None if not found.
        """
        for attr in dir(self.ui):
            if (
                isinstance(getattr(self.ui, attr), widget_type)
                and attr == name
            ):
                logging.debug(f"Found widget with {name=}: {attr=}")
                return getattr(self.ui, attr)

        layouts = [
            layout_widget
            for layout_widget in dir(self.ui)
            if "Layout" in layout_widget
        ]

        for layout_name in layouts:
            layout = getattr(self.ui, layout_name)
            logging.debug(f"Searching {layout_name=}: {dir(layout)=}")
            if hasattr(layout, "findChild"):
                if widget := layout.findChild(widget_type, name):
                    # https://stackoverflow.com/questions/27225529/get-widgets-by-name-from-layout
                    logging.debug(
                        f"Found child with {name=} {widget=} in {layout}: {layout_name=}"
                    )
                    return widget
            for attr in dir(layout):
                if (
                    isinstance(getattr(layout, attr), widget_type)
                    and attr == name
                ):
                    logging.debug(
                        f"Found widget with {name=}: {attr=} in {layout}: {layout_name=}"
                    )
                    return getattr(layout, attr)

        raise issues.UnknownWidgetError(
            f"Could not find {widget_type=} and {name=} in {dir(self.ui)=} or {self.run_button_ids=} or {layouts=}"
        )

    def get_button_from_id(self, button_id, prefix="pushButton"):
        return self.find_child(QtWidgets.QPushButton, f"{prefix}_{button_id}")

    @property
    def all_widget_ids(self) -> tuple[str, ...]:
        return tuple(self.config_widget_id_map.values())

    @property
    def all_cfg_items(self) -> tuple[str, ...]:
        return tuple(self.config_widget_id_map.keys())

    @property
    def widget_id2config_dict(self) -> immutabledict:
        return immutabledict(
            {v: k for k, v in self.config_widget_id_map.items()}
        )

    def find_config_item(self, widget_id):
        config_item = self.widget_id2config_dict.get(widget_id)
        return config_item

    def _find_widget_id(self, config_item: str):
        widget_id = self.config_widget_id_map.get(config_item)
        return widget_id

    def get_widget_from_id(self, widget_id) -> QtWidgets.QWidget:  # type: ignore
        widget = self.find_child(
            self.c2wi.get_widget_typing(widget_id=widget_id), widget_id
        )
        assert isinstance(widget, QtWidgets.QWidget)
        return widget


class CallableGroupValues:
    """
    This class provides static methods to generate dynamic values for group configuration items.

    Methods:
        score_matrix(): Returns a list of available score matrices.
        ColorMap(): Returns a dictionary of available color maps.
    """

    @staticmethod
    def list_some_blanks(n=1) -> List[str]:
        return [''] * n

    @staticmethod
    def list_score_matrix() -> List:
        score_matrix = [
            mtx
            for mtx in os.listdir(
                os.path.join(substitution_matrices.__path__[0], "data")  # type: ignore
            )
        ]
        return score_matrix

    @staticmethod
    def list_color_map() -> Dict:
        cmap_group = {
            _cmap: QtGui.QIcon(create_cmap_icon(cmap=_cmap))
            for _cmap in matplotlib.colormaps()
        }
        return cmap_group

    @staticmethod
    def list_installed_mutate_runners() -> List[str]:
        from REvoDesign.sidechain_solver.SidechainSolver import all_runner_c

        return [c.name for c in all_runner_c if c.installed]

    @staticmethod
    def list_all_profile_parsers() -> List[str]:
        from REvoDesign.common.ProfileParsers import all_parser_classes

        return [p.name for p in all_parser_classes]

    @staticmethod
    def list_all_designers() -> List[str]:
        from REvoDesign.external_designer import all_designer_classes

        return [
            dc.name
            for dc in all_designer_classes
            if dc.installed and not dc.scorer_only
        ]

    @staticmethod
    def list_all_scorers() -> List[str]:
        from REvoDesign.external_designer import all_designer_classes

        return [dc.name for dc in all_designer_classes if dc.installed]

    @staticmethod
    def list_all_rosetta_node_hints() -> List[str]:

        from REvoDesign.external_designer.designers.cart_ddg import \
            is_run_node_available

        node_hints: List[NodeHintT] = [
            "native",
            "docker",
            "docker_mpi",
            "mpi",
            "wsl",
            "wsl_mpi",
        ]

        available_run_node_hints = [
            n for n in node_hints if is_run_node_available(n)
        ]

        return available_run_node_hints
