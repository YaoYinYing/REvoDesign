'''
The heart of REvoDesign. A UI-Configuration Bus
'''
import os
from functools import partial, wraps
from typing import (Any, Callable, Dict, Optional, Protocol, Type, TypeVar,
                    Union, overload)
import omegaconf.errors
from immutabledict import immutabledict
from omegaconf import DictConfig, OmegaConf
from REvoDesign import SingletonAbstract, issues, reload_config_file
from REvoDesign.basic import MenuActionServerMonitor
from REvoDesign.citations import CitableModuleAbstract
from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.Qt import QtWidgets
from REvoDesign.tools.customized_widgets import (get_widget_value, notify_box,
                                                 set_widget_value,
                                                 widget_signal_tape)
from REvoDesign.tools.utils import CLASS_ARGSLICE
from .group_register import GroupRegistryCollection
from .widget_link import Config2WidgetIds, PushButtons
logging = ROOT_LOGGER.getChild(__name__)
ValueFromConfigT = TypeVar("ValueFromConfigT")
class StoresWidget(SingletonAbstract):
    def singleton_init(self):
        self.server_switches: Dict[str, MenuActionServerMonitor] = {}
    @classmethod
    def reset_instance(cls):
        '''
        Reset the instance of the class and clear all server switches dictionaries.
        '''
        myinstance = cls()
        for attr in myinstance.__dict__:
            if attr.startswith('_'):
                continue
            attr_dict: Union[Dict, Any] = getattr(myinstance, attr)
            if not isinstance(attr_dict, dict):
                continue
            for k, s in attr_dict.items():
                if hasattr(s, 'controller'):
                    controller = getattr(s, 'controller')
                    try:
                        if issubclass(s.controller.__class__, SingletonAbstract):
                            print(f'Resetting {k}: {controller.__class__.__name__}', end=' ')
                            s.controller.__class__.reset_instance()
                        print('done.')
                    except Exception as e:
                        print(f'failed: ({e}).')
            del attr_dict
        super().reset_instance()
class HeadlessProtocol(Protocol):
    """
    Defines a protocol for objects that can run in headless mode.
    This class inherits from Protocol and is primarily used for type annotations and type checking.
    It includes an attribute `headless` of type bool, which indicates whether the object runs in headless mode.
    Attributes:
    headless: bool -- A boolean attribute indicating whether the object runs in headless mode.
    """
    headless: bool
ConfigBusT = TypeVar("ConfigBusT", bound=HeadlessProtocol)
def require_non_headless(method):
    """
    A decorator to ensure that certain methods are only called when the application is not running in headless mode.
    It also prevents the method from being used with `partial`.
    Parameters:
    - method (Callable[..., Any]): The method to be decorated.
    Returns:
    - Callable[..., Any]: The wrapped method.
    """
    @wraps(method)
    def wrapper(*args, **kwargs):
        
        self: HeadlessProtocol = args[0]
        
        if self.headless:
            raise RuntimeError(
                f"The method '{method.__name__}' cannot be called when the application is running in headless mode."
            )
        
        return method(self, *args[CLASS_ARGSLICE], **kwargs)
    return wrapper
class ConfigBus(SingletonAbstract, CitableModuleAbstract):
    """
    This class is responsible for handling the configuration and interaction between the UI widgets
    and the application's configuration settings.
    Attributes:
        headless (bool): Indicates whether the application is running in headless mode.
        ui (QtWidgets.QWidget): The main UI widget of the application.
        cfg (OmegaConf): The application's configuration settings.
        w2c (Widget2ConfigMapper): A mapper object that maps UI widgets to configuration settings.
        push_buttons (dict): A dictionary of UI buttons.
    Methods:
        Non-headless Methods:
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
            button(id: str): Retrieves a button widget based on its ID.
            toggle_buttons(buttons: Iterable, set_enabled: bool = False): Toggles the enabled state of a list of buttons.
        Headless Only Methods:
            get_value(cfg_item: str, typing=None): Retrieves the value of a configuration item, with optional type casting.
            set_value(cfg_item: str, value): Sets the value of a configuration item.
        fp_lock(cfg_fps: Union[list, tuple, str], buttons_id_to_release: Union[list, tuple, str]): Locks or unlocks
            buttons based on the existence of file paths in the configuration.
    """
    headless: bool = True
    def singleton_init(self, ui=None):
        self.cfg: DictConfig = reload_config_file()
        if ui:
            self.headless = False
            self.ui = ui
            self.w2c = Widget2ConfigMapper(ui=self.ui)
            self.push_buttons = self.w2c.push_buttons
        self.cite()
    
    @require_non_headless
    def initialize_widget_with_group(self):
        
        for i, gr in enumerate(GroupRegistryCollection):
            group_values = []
            widget = self.get_widget_from_id(widget_id=gr.cfg_item)
            if isinstance(widget, str):
                raise TypeError(f"widget cannot be string: {gr.cfg_item}")
            
            for j, group_cfg in enumerate(gr.group_generators):
                if callable(group_cfg):
                    values = group_cfg()
                else:
                    logging.debug(
                        f"Group {j} of widget {gr.cfg_item} does not return any values"
                    )
                    continue
                
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
        
        cfg_item = self.w2c.widget_id2config_dict.get(widget_id)
        widget = self.get_widget_from_id(widget_id=widget_id)
        if not cfg_item:
            return
        value = get_widget_value(widget=widget)
        OmegaConf.update(self.cfg, cfg_item, value)
    def _widget_link(self, widget_id: str):
        return partial(self.update_cfg_item_from_widget, widget_id)
    @require_non_headless
    def register_widget_changes_to_cfg(self):
        
        for widget_id in self.w2c.all_widget_ids:
            widget = self.get_widget_from_id(widget_id=widget_id)
            try:
                widget_signal_tape(widget, self._widget_link(widget_id))
            except Exception as e:
                raise issues.UnknownWidgetError(f'Expect link of {widget_id} with {widget.__name__} is broken.') from e
    @require_non_headless
    def get_widget_from_id(self, widget_id: str) -> QtWidgets.QWidget:
        
        if widget_id not in self.w2c.widget_id2widget_map:
            raise KeyError(f"{widget_id} is not in the widget map")
        return self.w2c.widget_id2widget_map.get(widget_id)
    @require_non_headless
    def get_widget_from_cfg_item(self, cfg_item: str) -> QtWidgets.QWidget:
        
        return self.w2c.config2widget_map.get(cfg_item)
    @require_non_headless
    def get_widget_value(self, cfg_item: str, converter: Callable[[Any], ValueFromConfigT]) -> ValueFromConfigT:
        try:
            value = get_widget_value(
                widget=self.get_widget_from_cfg_item(cfg_item)
            )
        except ValueError as e:
            
            logging.error(f'Error in the configuration item: {cfg_item}: {e}')
            raise ValueError(
                f"Error in the configuration item: {cfg_item}"
            ) from e
        
        return converter(value)
    @require_non_headless
    def set_widget_value(self, cfg_item: str, value, hard=False):
        
        widget = self.get_widget_from_cfg_item(cfg_item)
        set_widget_value(widget=widget, value=value)
        if hard:
            self.set_value(cfg_item=cfg_item, value=value)
    @require_non_headless
    def restore_widget_value(self, cfg_item: str):
        
        widget = self.get_widget_from_cfg_item(cfg_item)
        value = self.get_value(cfg_item)
        set_widget_value(widget=widget, value=value)
    def get_cfg_item(self, widget_id: str) -> str:
        
        cfg_item = self.w2c.widget_id2config_dict.get(widget_id)
        if cfg_item is None:
            raise ValueError(f"{widget_id} is not a valid widget ID.")
        return cfg_item
    @overload
    def get_value(self, cfg_item: str, converter: Callable[[Any], ValueFromConfigT],
                  reject_none: bool, default_value: None = ...) -> ValueFromConfigT: ...
    @overload
    def get_value(self, cfg_item: str, converter: Type[bool], reject_none: bool, default_value: bool = ...) -> bool: ...
    @overload
    def get_value(self,
                  cfg_item: str,
                  converter: Callable[[Any],
                                      ValueFromConfigT],
                  reject_none: bool = True,
                  default_value: Optional[ValueFromConfigT] = ...) -> ValueFromConfigT: ...
    @overload
    def get_value(self, cfg_item: str, converter=None) -> Any: ...
    def get_value(
        self,
        cfg_item: str,
        converter: Optional[Callable[[Any], ValueFromConfigT]] = None,
        reject_none: bool = False,
        default_value: Optional[ValueFromConfigT] = None,
    ) -> Optional[ValueFromConfigT]:
        """
        Retrieves the value of a configuration item with optional type casting.
        Args:
            cfg_item: Name of the configuration item.
            converter: Callable to convert the value from the configuration item to a desired type.
            reject_none: If True, raises an exception if the value is None.
            default_value: Default value to return if the value is None.
        Returns:
            The converted value, the default value if provided, or None if allowed.
        Raises:
            ValueError: If `reject_none` is True and the resolved value is None.
        """
        
        value = OmegaConf.select(self.cfg, cfg_item)
        
        if value is None:
            
            if default_value is not None:
                value = default_value
            
            elif reject_none:
                
                if not self.get_value('ui.header_panel.input.molecule', None):
                    notify_box(
                        "No molecule is loaded in PyMOL. Please load a molecule first.", issues.UnexpectedWorkflowError
                    )
                
                notify_box(
                    "This configure file might be out of date. "
                    "Please reinitialize REvoDesign (menu->Edit->Reinitialize) and restart PyMOL to fix this.",
                    issues.ConfigureOutofDateError
                )
            else:
                return None  
        
        if converter:
            value = converter(value)
        
        
        if reject_none and value is None:
            raise ValueError("The configuration value is None and reject_none is True.")
        return value
    def set_value(self, cfg_item: str, value: Any, force_add: bool = False) -> None:
        
        if value is not None:
            try:
                OmegaConf.update(self.cfg, cfg_item, value, force_add=force_add)
            except omegaconf.errors.ConfigKeyError as e:
                raise issues.ConfigureOutofDateError(
                    "This configure file might be out of date. Please remove it and restart PyMOL to fix this."
                ) from e
    @require_non_headless
    def toggle_buttons(
        self,
        button_ids: tuple[str, ...],
        set_enabled: bool = False,
    ):
        
        buttons = self.buttons(button_ids=button_ids)
        for button in buttons:
            if not button:
                continue
            
            if button.property("held"):
                continue
            button.setEnabled(set_enabled)
    def fp_lock(
        self,
        cfg_fps: tuple[str, ...],
        buttons_id_to_release: tuple[str, ...],
    ):
        
        self.toggle_buttons(
            button_ids=buttons_id_to_release, set_enabled=False
        )
        for cfg_fp in cfg_fps:
            _fp = self.get_value(cfg_fp)
            logging.info(f"Checking file path: {_fp}")
            if not _fp or not os.path.isdir(os.path.dirname(_fp)):
                return
            if not os.path.isfile(_fp):
                logging.warning(f"The file `{_fp}` is not valid.")
            else:
                logging.info(f"The file `{_fp}` is valid.")
        self.toggle_buttons(button_ids=buttons_id_to_release, set_enabled=True)
    @require_non_headless
    def button(self, button_id: str) -> QtWidgets.QPushButton:
        """Retrieves a button widget based on its ID.
        Args:
            button_id (str): Button ID.
        Returns:
            QtWidgets.QPushButton: Button object
        """
        assert button_id in self.w2c.run_button_ids
        return self.w2c.push_buttons.get(button_id)
    @require_non_headless
    def buttons(self, button_ids: tuple[str, ...]) -> tuple[QtWidgets.QPushButton, ...]:
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
        self.push_buttons: immutabledict[str, QtWidgets.QPushButton] = immutabledict(
            {
                button_id: self.get_button_from_id(button_id=button_id)
                for button_id in self.run_button_ids
            }
        )
        self.c2wi = Config2WidgetIds()
        self.config_widget_id_map: immutabledict[str, str] = immutabledict(
            self.c2wi.c2wi
        )
        self.config2widget_map: immutabledict[str, QtWidgets.QWidget] = immutabledict(
            {
                c: self.get_widget_from_id(wi)
                for c, wi in self.config_widget_id_map.items()
            }
        )
        self.widget_id2widget_map: immutabledict[str, QtWidgets.QWidget] = immutabledict(
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
                isinstance(found_widget := getattr(self.ui, attr), widget_type)
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
                
                logging.debug(
                    f"Found child with {name=} {found_widget=} in {layout}: {layout_name=}"
                )
                return found_widget
            for attr in dir(layout):
                if (
                    isinstance((found_widget := getattr(layout, attr)), widget_type)
                    and attr == name
                ):
                    logging.debug(
                        f"Found widget with by name in {layout}: {attr=}: {layout_name=}"
                    )
                    return found_widget
        raise issues.UnknownWidgetError(
            f"Could not find {widget_type=} and {name=} in {dir(self.ui)=} or {self.run_button_ids=} or {layouts=}"
        )
    def get_button_from_id(self, button_id: str, prefix="pushButton", button_type: Any = QtWidgets.QPushButton):
        return self.find_child(button_type, f"{prefix}_{button_id}")
    @property
    def all_widget_ids(self) -> tuple[str, ...]:
        return tuple(self.config_widget_id_map.values())
    @property
    def all_cfg_items(self) -> tuple[str, ...]:
        return tuple(self.config_widget_id_map.keys())
    @property
    def widget_id2config_dict(self) -> immutabledict[str, str]:
        return immutabledict(
            {v: k for k, v in self.config_widget_id_map.items()}
        )
    def find_config_item(self, widget_id):
        config_item = self.widget_id2config_dict.get(widget_id)
        return config_item
    def _find_widget_id(self, config_item: str) -> str:
        widget_id = self.config_widget_id_map.get(config_item)
        if widget_id is None:
            raise issues.InternalError(f"{config_item} is not a valid config item.")
        return widget_id
    def get_widget_from_id(self, widget_id: str) -> QtWidgets.QWidget:
        widget = self.find_child(
            self.c2wi.get_widget_typing(widget_id=widget_id), widget_id
        )
        return widget