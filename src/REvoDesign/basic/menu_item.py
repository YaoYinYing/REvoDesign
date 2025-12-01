'''
Data classes for menu items and menu collections.
'''

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from REvoDesign.Qt import QtWidgets


@dataclass(frozen=True)
class MenuItem:
    """
    A data class representing a menu item.

    This class is used to define the properties of a menu item, including its name, associated function, and optional arguments.
    The use of the @dataclass decorator automatically generates special methods such as __init__(), __repr__(), and __eq__().
    The frozen parameter ensures that instances of the class are immutable, enhancing thread safety and consistency.

    Attributes:
        action (str): The action attr name associated with the menu item.
        func (Callable): The function associated with the menu item, which is executed when the item is selected.
        args (Optional[Tuple]): Optional arguments passed to the associated function when it is executed. Defaults to None.
        kwargs (Optional[Mapping]): Optional arguments passed to the associated function when it is executed. Defaults to None.
    """
    action: str
    func: Callable | str
    args: tuple | None = None
    kwargs: Mapping | None = None

    @property
    def func_to_call(self):
        '''
        Returns the real callable function to be executed.
        If the function is a string, it will be resolved to a callable function.
        '''
        if isinstance(self.func, str):
            from REvoDesign.tools.utils import resolve_dotted_function
            return resolve_dotted_function(self.func)
        return self.func

    @property
    def trigger(self):
        '''
        Returns a triggered function that is lazy resolved
        '''
        return lambda: self.func_to_call(*self.args or (), **self.kwargs or {})


@dataclass(frozen=True)
class MenuCollection:
    """
    A data class representing a collection of menu items.
    This class registers the menu items and their associated functions while instantiating the class.
    """
    ui: QtWidgets.QWidget
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
            if not hasattr(self.ui, m.action):
                print(f"Skipping binding menu item: {m.action} is missing in the {self.ui}.")
                continue
            try:
                action: QtWidgets.QAction = getattr(self.ui, m.action)
                action.triggered.connect(m.trigger)
            except AttributeError as e:
                print(f"Skipping binding menu item due to error: {m}: {e}")
