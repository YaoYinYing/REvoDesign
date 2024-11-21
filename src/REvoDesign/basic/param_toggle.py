from dataclasses import dataclass

from typing import Any, Callable, Dict, Tuple, Protocol
from functools import partial
from pymol.Qt import QtWidgets

from .. import issues


class QtEventSignal(Protocol):
    def connect(self): ...


@dataclass(frozen=True)
class ParamChangeRegistryItem:
    """
    A class that registers a mapping between two config items.
    """
    widget_name: str
    widget_signal_name: str
    source_cfg_item: str
    target_cfg_item: str

    param_mapping: Dict[Any, Tuple]

    def widget_signal(self, ui)-> QtEventSignal:
        try:
            widget: QtWidgets = getattr(ui,self.widget_name) # type: ignore
            event= getattr(widget, self.widget_signal_name) # type: ignore
            return event
        except AttributeError as e:
            raise issues.InternalError(f"Widget {self.widget_name} does not have signal {self.widget_signal_name}") from e 



    def register(self, register_func: Callable[[str, str, Dict[str, Tuple]],None], ui: Any):
        event = self.widget_signal(ui=ui)
        event.connect(
            partial(
                register_func,
                self.source_cfg_item,
                self.target_cfg_item,
                self.param_mapping
            ) # type: ignore
        )



@dataclass(frozen=True)
class ParamChangeRegister:
    register_func: Callable[[str, str, Dict[str, Tuple]],None]
    registry: tuple[ParamChangeRegistryItem, ...]


    def register_all(self, ui):

        for registry_item in self.registry:
            registry_item.register(self.register_func, ui=ui)
