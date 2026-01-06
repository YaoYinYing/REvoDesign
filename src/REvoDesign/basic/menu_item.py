"""
Data classes for menu items and menu collections.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cached_property

from REvoDesign import issues
from REvoDesign.Qt import QtCore, QtWidgets

_translate = QtCore.QCoreApplication.translate


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
        action_text (Optional[str]): The text to display in the menu item if we need to build the action from scratch. Defaults to None.
        menu_section (Optional[str]): The menu section to which the menu item belongs if we need to build the action from scratch. Defaults to None.
    """

    action: str
    func: Callable | str
    args: tuple | None = None
    kwargs: Mapping | None = None
    action_text: str | None = None
    menu_section: str | QtWidgets.QMenu | None = None

    @cached_property
    def func_to_call(self) -> Callable:
        """
        Returns the real callable function to be executed.
        If the function is a string, it will be resolved to a callable function.
        """
        if isinstance(self.func, str):
            from REvoDesign.tools.utils import resolve_dotted_function, resolve_lambda_expression

            if self.func.startswith("LAMBDA:"):
                return resolve_lambda_expression(self.func, as_partial=True)
            return resolve_dotted_function(self.func)
        return self.func

    @cached_property
    def trigger(self):
        """
        Returns a triggered function that is lazy resolved
        """
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
            # if the action does not exist in the ui, we need to create it first
            if not hasattr(self.ui, m.action):

                # print(f"Try to build the menu action {m.action} because it is missing in the {self.ui}. ")
                # Falling back to the menu section if provided.

                if m.menu_section is None:
                    raise issues.InternalError(
                        f"To build a menu action ({m.action}) that does not exist in the menu section, a menu section must be provided."
                    )
                # print(f"Menu Section: {m.menu_section}")

                # Get the menu section object
                if isinstance(m.menu_section, str):
                    menu_section_obj = getattr(self.ui, m.menu_section)
                else:
                    menu_section_obj: QtWidgets.QMenu = m.menu_section

                # double check the menu section object type
                if not isinstance(menu_section_obj, QtWidgets.QMenu):
                    raise issues.InternalError(
                        f"Menu section must be a QMenu object, instead of {type(menu_section_obj)}"
                    )
                try:

                    # build a new action and add it to the menu
                    action = QtWidgets.QAction(m.action_text or m.action, parent=menu_section_obj)
                    action.setObjectName(m.action)
                    action.setText(_translate("REvoDesignPyMOL_UI", m.action_text or m.action))
                    action.triggered.connect(m.trigger)
                    menu_section_obj.addAction(action)

                    print(f"Successfully bound menu item {m} ({action}) to menu section {m.menu_section} ({menu_section_obj}).")
                except Exception as e:
                    print(f"Skipping binding menu item due to error: {m}: {e}")
                    continue
            # otherwise, we can just bind the function to the existing action
            else:
                try:
                    action: QtWidgets.QAction = getattr(self.ui, m.action)
                    action.triggered.connect(m.trigger)
                except AttributeError as e:
                    print(f"Skipping binding menu item due to error: {m}: {e}")
