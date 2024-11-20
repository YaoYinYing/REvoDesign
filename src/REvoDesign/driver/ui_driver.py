import warnings
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Union

from immutabledict import immutabledict
from omegaconf import DictConfig, OmegaConf
from pymol.Qt import QtWidgets

from REvoDesign import SingletonAbstract, issues, reload_config_file
from REvoDesign.citations import CitableModules
from REvoDesign.logger import root_logger
from REvoDesign.tools.customized_widgets import (get_widget_value,
                                                 set_widget_value)
from REvoDesign.tools.utils import dirname_does_exist, filepath_does_exists

from .group_register import GroupRegistryCollection
from .widget_link import Config2WidgetIds, PushButtons

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

        for i, gr in enumerate(GroupRegistryCollection):
            group_values = []
            widget = self.get_widget_from_id(widget_id=gr.cfg_item)
            if isinstance(widget, str):
                raise TypeError(f"widget cannot be string: {gr.cfg_item}")

            # digest the string to values
            for j, group_cfg in enumerate(gr.group_generators):
                if callable(group_cfg):
                    values = group_cfg()
                else:
                    logging.debug(
                        f"Group {j} of widget {gr.cfg_item} does not return any values"
                    )
                    continue

                # exclude blank string, blank list, or blank tuple
                if not values:
                    logging.debug(f"Group {j} of widget {gr.cfg_item} is empty: {values}")
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
                logging.debug(f"No values found for widget {gr.cfg_item}")
                continue

            set_widget_value(widget, group_values)

            default_cfg_item = self.w2c.find_config_item(widget_id=gr.cfg_item)
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

    def get_widget_from_id(self, widget_id: str) -> QtWidgets.QWidget:  # type: ignore
        # Retrieves a UI widget based on its ID.
        if widget_id not in self.w2c.widget_id2widget_map:
            raise KeyError(f"{widget_id} is not in the widget map")

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
                f"Error in the configuration item: {cfg_item}"
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
    ) -> Optional[Any]:
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
        button_ids: tuple[str, ...],
        set_enabled: bool = False,
    ):
        # Toggles the enabled state of a list of buttons.
        buttons = self.buttons(button_ids=button_ids)

        for button in buttons:
            if not button:
                continue
            # Check for 'held' property, defaulting to False if the property doesn't exist
            if button.property("held"):
                continue
            button.setEnabled(set_enabled)

    def fp_lock(
        self,
        cfg_fps: tuple[str, ...],
        buttons_id_to_release: tuple[str, ...],
    ):
        # Locks or unlocks buttons based on the existence of file paths in the configuration.
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

    def button(self, button_id: str) -> QtWidgets.QPushButton:  # type: ignore
        """Retrieves a button widget based on its ID.

        Args:
            button_id (str): Button ID.

        Returns:
            QtWidgets.QPushButton: Button object
        """
        assert button_id in self.w2c.run_button_ids
        return self.w2c.push_buttons.get(button_id)

    def buttons(self, button_ids: tuple[str, ...]) -> tuple[QtWidgets.QPushButton, ...]:  # type: ignore
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


class Widget2ConfigMapper:
    """
    This class maps UI widgets to configuration settings and provides methods to interact with these mappings.

    Attributes:
        ui (QtWidgets.QWidget): The main UI widget of the application.
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
                isinstance(found_widget:=getattr(self.ui, attr), widget_type)
                and attr == name
            ):
                logging.debug(f"Found widget by name: {attr=}")
                return found_widget

        layouts = [
            layout_widget
            for layout_widget in dir(self.ui)
            if "Layout" in layout_widget
        ]

        for layout_name in layouts:
            layout = getattr(self.ui, layout_name)
            
            if not hasattr(layout, "findChild"):
                continue

            logging.debug(f"Searching {layout_name=}: {dir(layout)=}")
            if found_widget := layout.findChild(widget_type, name):
                # https://stackoverflow.com/questions/27225529/get-widgets-by-name-from-layout
                logging.debug(
                    f"Found child with {name=} {found_widget=} in {layout}: {layout_name=}"
                )
                return found_widget
            
            for attr in dir(layout):
                if (
                    isinstance((found_widget:=getattr(layout, attr)), widget_type)
                    and attr == name
                ):
                    logging.debug(
                        f"Found widget with by name in {layout}: {attr=}: {layout_name=}"
                    )
                    return found_widget

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
