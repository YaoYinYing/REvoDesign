from dataclasses import dataclass
from functools import partial
from typing import Callable, Mapping, Optional, Tuple
from REvoDesign.Qt import QtWidgets
@dataclass(frozen=True)
class MenuItem:
    action: QtWidgets.QAction
    func: Callable
    args: Optional[Tuple] = None
    kwargs: Optional[Mapping] = None
@dataclass(frozen=True)
class MenuCollection:
    menu_items: tuple[MenuItem, ...]
    def __post_init__(self):
        self.bind()
    def bind(self):
        for m in self.menu_items:
            try:
                m.action.triggered.connect(partial(m.func, *m.args if m.args else (), **m.kwargs if m.kwargs else {}))
            except AttributeError as e:
                print(f"Skipping binding menu item due to error: {m}: {e}")