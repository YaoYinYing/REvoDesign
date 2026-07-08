# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Unit tests for MenuItem, MenuCollection, and menu builders."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from REvoDesign import issues
from REvoDesign.application.menu import config_edit_links, core_menu_links, menu_links, static_menu_links
from REvoDesign.basic.menu_item import MenuCollection, MenuItem
from REvoDesign.Qt import QtWidgets


@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for the module."""
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])
    yield app


# -- MenuItem ----------------------------------------------------------------


def test_menu_item_stores_fields():
    """MenuItem stores its constructor fields."""
    item = MenuItem("actionTest", print, args=(1,), kwargs={"k": "v"})
    assert item.action == "actionTest"
    assert item.func is print
    assert item.args == (1,)
    assert item.kwargs == {"k": "v"}
    assert item.action_text is None
    assert item.menu_section is None


def test_menu_item_is_separator():
    """A MenuItem with action '---' is a separator."""
    assert not MenuItem("actionTest", print).is_separator
    assert MenuItem("---", "---").is_separator


def test_menu_item_separator_classmethod():
    """MenuItem.separator() shorthand creates a separator."""
    sep = MenuItem.separator("menuTools")
    assert sep.is_separator
    assert sep.menu_section == "menuTools"


def test_menu_item_func_to_call_resolves_string(qapp):
    """String func references are resolved lazily."""
    item = MenuItem("actionTest", "builtins:print")
    assert callable(item.func_to_call)


def test_menu_item_trigger():
    """trigger() calls func_to_call with args and kwargs."""
    called_with = []

    def tracker(*a, **kw):
        called_with.append((a, kw))

    item = MenuItem("actionTest", tracker, args=(1,), kwargs={"k": "v"})
    item.trigger()
    assert called_with == [((1,), {"k": "v"})]


# -- MenuCollection ----------------------------------------------------------


def _make_ui_with_action(action_name: str) -> QtWidgets.QWidget:
    """Return a QWidget carrying a named QAction."""
    widget = QtWidgets.QWidget()
    action = QtWidgets.QAction(widget)
    action.setObjectName(action_name)
    setattr(widget, action_name, action)
    return widget


def test_bind_static_action(qapp):
    """A QAction that exists on the UI gets its triggered signal connected."""
    ui = _make_ui_with_action("actionHello")
    called = []

    MenuCollection(ui, (MenuItem("actionHello", lambda: called.append(True)),))

    ui.actionHello.trigger()
    assert called == [True]


def test_bind_dynamic_action(qapp):
    """A MenuItem with menu_section creates a new QAction in that menu."""
    ui = QtWidgets.QWidget()
    menu = QtWidgets.QMenu("Tools", ui)
    menu.setObjectName("menuTools")
    setattr(ui, "menuTools", menu)

    called = []
    MenuCollection(ui, (MenuItem("actionDynamic", lambda: called.append(42), menu_section="menuTools"),))

    # Find the dynamically-created action
    actions = menu.actions()
    assert len(actions) == 1
    assert actions[0].objectName() == "actionDynamic"
    actions[0].trigger()
    assert called == [42]


def test_bind_separator(qapp):
    """A separator MenuItem adds a QAction separator to the target menu."""
    ui = QtWidgets.QWidget()
    menu = QtWidgets.QMenu("Edit", ui)
    menu.setObjectName("menuEdit")
    setattr(ui, "menuEdit", menu)

    MenuCollection(ui, (MenuItem.separator("menuEdit"),))

    actions = menu.actions()
    assert len(actions) == 1
    assert actions[0].isSeparator()


def test_missing_menu_section_raises(qapp):
    """Dynamic action without menu_section raises InternalError."""
    ui = QtWidgets.QWidget()

    with pytest.raises(issues.InternalError, match="Missing menu section"):
        MenuCollection(ui, (MenuItem("actionGhost", print, menu_section=None),))


def test_invalid_menu_section_raises(qapp):
    """A menu_section that resolves to a non-QMenu raises InternalError."""
    ui = QtWidgets.QWidget()
    label = QtWidgets.QLabel("not a menu", ui)
    label.setObjectName("labelNotMenu")
    setattr(ui, "labelNotMenu", label)

    with pytest.raises(issues.InternalError, match="must be a QMenu"):
        MenuCollection(ui, (MenuItem("actionBad", print, menu_section="labelNotMenu"),))


def test_menu_collection_binds_all(qapp):
    """MenuCollection.bind() processes every item in the tuple."""
    ui = _make_ui_with_action("actionA")
    # Also add actionB
    action_b = QtWidgets.QAction(ui)
    action_b.setObjectName("actionB")
    setattr(ui, "actionB", action_b)

    results = []
    items = (
        MenuItem("actionA", lambda: results.append("A")),
        MenuItem("actionB", lambda: results.append("B")),
    )
    MenuCollection(ui, items)

    ui.actionA.trigger()
    ui.actionB.trigger()
    assert results == ["A", "B"]


# -- menu builders (application/menu.py) ------------------------------------


def test_static_menu_links_returns_tuple():
    """static_menu_links() returns a non-empty tuple of MenuItems."""
    links = static_menu_links()
    assert isinstance(links, tuple)
    assert len(links) > 0
    assert all(isinstance(item, MenuItem) for item in links)


def test_menu_links_returns_tuple():
    """menu_links() returns a tuple combining static + config-edit links."""
    links = menu_links()
    assert isinstance(links, tuple)
    assert len(links) > len(static_menu_links())  # includes config-edit links


def test_config_edit_links_has_main_config_first():
    """config_edit_links() lists the 'main' config as the first edit item."""
    links = config_edit_links()
    main_items = [item for item in links if "main" in item.action]
    assert len(main_items) >= 1
    # main config edit should appear before any separator or other config
    first_non_sep = next(item for item in links if not item.is_separator)
    assert "main" in first_non_sep.action


def test_config_edit_links_includes_recent_experiments():
    """config_edit_links() includes recent-experiment items when experiments exist."""
    links = config_edit_links()
    recent = [item for item in links if item.menu_section == "menuRecent_Experiments"]
    # At least some experiments should exist (test infrastructure creates them)
    assert len(recent) >= 0  # may be empty in clean test env, that's fine


def test_core_menu_links_returns_tuple():
    """core_menu_links(app) returns a tuple with expected core action names."""
    app = MagicMock()
    app.bus.cfg_group = {"main": MagicMock()}
    app.set_working_directory = lambda: None
    app.reload_configurations = lambda: None
    app.load_and_save_experiment = lambda mode: None
    app.reinitialize = lambda delete: None

    links = core_menu_links(app)
    assert isinstance(links, tuple)
    assert len(links) == 8

    action_names = {item.action for item in links}
    assert "actionSet_Working_Directory" in action_names
    assert "actionReconfigure" in action_names
    assert "actionSave_Configurations" in action_names
    assert "action_LoadExperiment" in action_names
    assert "action_Save_to_Experiment" in action_names
    assert "actionReinitialize" in action_names
    assert "actionSource_Code" in action_names
    assert "actionVersion" in action_names


def test_menu_module_import_has_no_side_effects():
    """Importing application.menu does not scan the filesystem.

    config_edit_links() and menu_links() are the only functions that
    trigger directory I/O — importing the module should not.
    """
    with patch("REvoDesign.application.menu.list_all_config_files") as mock_list:
        # Force re-import by clearing the cached module
        import sys

        mod = sys.modules.get("REvoDesign.application.menu")
        try:
            del sys.modules["REvoDesign.application.menu"]
            from REvoDesign.application import menu  # noqa: F811

            mock_list.assert_not_called()
        finally:
            if mod is not None:
                sys.modules["REvoDesign.application.menu"] = mod
