# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
Data classes for menu items and menu collections.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cached_property

from REvoDesign import issues
from REvoDesign.Qt import QtCore, QtWidgets

_translate = QtCore.QCoreApplication.translate


@dataclass(frozen=True)
class MenuItem:
    """A data class representing a menu item.

    Attributes:
        action: The action attr name associated with the menu item.
            Set to ``'---'`` for a separator.
        func: The function associated with the menu item, executed when
            the item is selected.  May be a callable, a dotted-string
            reference (``"pkg.mod:func"``), or ``"LAMBDA:..."``.
        args: Positional arguments passed to *func* on trigger.
        kwargs: Keyword arguments passed to *func* on trigger.
        action_text: Display text for dynamically-created actions.
        menu_section: Target QMenu (or its object name) for dynamically-
            created actions.
    """

    action: str
    func: Callable | str
    args: tuple | None = None
    kwargs: Mapping | None = None
    action_text: str | None = None
    menu_section: str | QtWidgets.QMenu | None = None

    @classmethod
    def separator(cls, menu_section: str | QtWidgets.QMenu) -> MenuItem:
        """Shorthand for a menu separator in *menu_section*."""
        return cls("---", "---", menu_section=menu_section)

    @cached_property
    def is_separator(self) -> bool:
        """Return True if this item is a menu separator."""
        return self.action == "---"

    @cached_property
    def func_to_call(self) -> Callable:
        """Return the resolved callable for this menu item."""
        if isinstance(self.func, str):
            from REvoDesign.tools.utils import resolve_dotted_function, resolve_lambda_expression

            if self.func.startswith("LAMBDA:"):
                return resolve_lambda_expression(self.func, as_partial=True)
            return resolve_dotted_function(self.func)
        return self.func

    @cached_property
    def trigger(self) -> Callable:
        """Return a zero-argument callable that invokes *func_to_call*."""
        return lambda: self.func_to_call(*self.args or (), **self.kwargs or {})


@dataclass(frozen=True)
class MenuCollection:
    """Bind a collection of MenuItems to a UI proxy's named QActions / QMenus."""

    ui: QtWidgets.QWidget
    menu_items: tuple[MenuItem, ...]

    def __post_init__(self) -> None:
        self.bind()

    def bind(self) -> None:
        """Bind every menu item to its QAction (static or dynamically-created)."""
        for item in self.menu_items:
            self.bind_one(item)

    def bind_one(self, item: MenuItem) -> None:
        """Bind a single *item* to the UI.

        When a QAction with *item.action* already exists on the UI it is
        connected directly.  Otherwise a new QAction is created and added
        to the menu section named by *item.menu_section*.
        """
        if hasattr(self.ui, item.action):
            getattr(self.ui, item.action).triggered.connect(item.trigger)  # type: ignore[union-attr]
            return

        menu = self._menu_section(item)
        if item.is_separator:
            menu.addSeparator()
            return

        action = QtWidgets.QAction(item.action_text or item.action, parent=menu)
        action.setObjectName(item.action)
        action.setText(_translate("REvoDesignPyMOL_UI", item.action_text or item.action))
        action.triggered.connect(item.trigger)
        menu.addAction(action)

    def _menu_section(self, item: MenuItem) -> QtWidgets.QMenu:
        """Resolve and validate the QMenu target for a dynamic *item*."""
        if item.menu_section is None:
            raise issues.InternalError(f"Missing menu section for dynamic menu action: {item.action!r}")

        if isinstance(item.menu_section, str):
            menu = getattr(self.ui, item.menu_section)
        else:
            menu = item.menu_section

        if not isinstance(menu, QtWidgets.QMenu):
            raise issues.InternalError(f"Menu section must be a QMenu, got {type(menu).__name__!r}")
        return menu


__all__ = ["MenuCollection", "MenuItem"]
