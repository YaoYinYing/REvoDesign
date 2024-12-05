'''
Module to register parameter changes in the UI.
'''
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Dict, Protocol, Tuple

from pymol.Qt import QtWidgets

from .. import issues


class QtEventSignal(Protocol):
    def connect(self): ...


@dataclass(frozen=True)
class ParamChangeRegistryItem:
    """
    A class that registers a mapping between two config items.

    This class is used to define how a change in one configuration item (source_cfg_item) should be mapped and registered
    to another configuration item (target_cfg_item) through a UI widget signal. It uses a dictionary to map parameter values.

    Attributes:
        widget_name (str): The name of the UI widget.
        widget_signal_name (str): The name of the signal on the widget.
        source_cfg_item (str): The name of the source configuration item.
        target_cfg_item (str): The name of the target configuration item.
        param_mapping (Dict[Any, Tuple]): A dictionary mapping parameter values from the source to the target.
    """

    widget_name: str
    widget_signal_name: str
    source_cfg_item: str
    target_cfg_item: str

    param_mapping: Dict[Any, Tuple]

    def widget_signal(self, ui) -> QtEventSignal:
        """
        Retrieves the specified signal from the specified widget on the UI.

        Args:
            ui (Any): The UI instance containing the widgets.

        Returns:
            QtEventSignal: The signal associated with the widget.

        Raises:
            issues.InternalError: If the widget does not have the specified signal.
        """
        try:
            widget: QtWidgets = getattr(ui, self.widget_name)  # type: ignore
            event = getattr(widget, self.widget_signal_name)  # type: ignore
            return event
        except AttributeError as e:
            raise issues.InternalError(
                f"Widget {self.widget_name} does not have signal {self.widget_signal_name}") from e

    def register(self, register_func: Callable[[str, str, Dict[str, Tuple]], None], ui: Any):
        """
        Registers the mapping between two configuration items by connecting the widget signal to the registration function.

        Args:
            register_func (Callable[[str, str, Dict[str, Tuple]], None]): The function to be called when the signal is emitted.
            ui (Any): The UI instance containing the widgets.
        """
        event = self.widget_signal(ui=ui)
        event.connect(
            partial(
                register_func,
                self.source_cfg_item,
                self.target_cfg_item,
                self.param_mapping
            )  # type: ignore
        )


@dataclass(frozen=True)
class ParamChangeRegister:
    """
    A data class to register parameter change functions.

    Attributes:
    - register_func: Callable[[str, str, Dict[str, Tuple]], None]
        A function that registers a parameter change handler.
    - registry: tuple[ParamChangeRegistryItem, ...]
        A tuple of items to be registered.
    """
    register_func: Callable[[str, str, Dict[str, Tuple]], None]
    registry: tuple[ParamChangeRegistryItem, ...]

    def register_all(self, ui):
        """
        Registers all items in the registry using the provided register function and UI.

        Parameters:
        - ui: The user interface object used for registration.
        """

        for registry_item in self.registry:
            registry_item.register(self.register_func, ui=ui)
