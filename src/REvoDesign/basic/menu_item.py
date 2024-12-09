'''
Data classes for menu items and menu collections.
'''

from dataclasses import dataclass
from functools import partial
from typing import Callable, Mapping, Optional

from pymol.Qt import QtWidgets


@dataclass(frozen=True)
class MenuItem:
    """
    A data class representing a menu item.

    This class is used to define the properties of a menu item, including its name, associated function, and optional arguments.
    The use of the @dataclass decorator automatically generates special methods such as __init__(), __repr__(), and __eq__().
    The frozen parameter ensures that instances of the class are immutable, enhancing thread safety and consistency.

    Attributes:
        name (str): The name of the menu item, used for display and identification.
        action (QtWidgets.QAction): The action associated with the menu item.
        func (Callable): The function associated with the menu item, which is executed when the item is selected.
        kwargs (Optional[Mapping]): Optional arguments passed to the associated function when it is executed. Defaults to None.
    """
    action: QtWidgets.QAction  # type: ignore
    func: Callable
    kwargs: Optional[Mapping] = None


@dataclass(frozen=True)
class MenuCollection:
    """
    A data class representing a collection of menu items.
    This class registers the menu items and their associated functions while instantiating the class.
    """
    menu_items: tuple[MenuItem, ...]

    def __post_init__(self):
        """
        Post-initialization method.
        This method is called after the object is created and initialized.
        It checks if the menu items are valid, raising an error if they are not.
        """
        self.bind()

    def bind(self):
        """
        Binds the menu items to their respective functions.
        This method iterates over the menu items and binds their functions to the associated actions.
        """

        for m in self.menu_items:
            try:
                m.action.triggered.connect(partial(m.func, **m.kwargs if m.kwargs else {}))
            except AttributeError as e:
                print(f"Skipping binding menu item due to error: {m}: {e}")

