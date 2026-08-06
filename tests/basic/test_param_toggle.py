# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


from unittest.mock import MagicMock, patch

import pytest

from REvoDesign.basic.param_toggle import ParamChangeRegistryItem
from REvoDesign.driver.param_toggle_register import register_param_changes


def test_param_change_registry_item_signal():
    # Mock the UI and the widget with a signal
    mock_ui = MagicMock()
    mock_widget = MagicMock()
    mock_signal = MagicMock()

    mock_ui.some_widget = mock_widget
    mock_widget.some_signal = mock_signal

    # Create a registry item
    registry_item = ParamChangeRegistryItem(
        widget_name="some_widget",
        widget_signal_name="some_signal",
        source_cfg_item="source_item",
        target_cfg_item="target_item",
        param_mapping={"key1": ("value1",)},
    )

    # Retrieve the signal
    signal = registry_item.widget_signal(mock_ui)

    # Assert the correct signal is returned
    assert signal == mock_signal


def test_param_change_registry_item_register():
    # Mock the UI, widget, and signal
    mock_ui = MagicMock()
    mock_widget = MagicMock()
    mock_signal = MagicMock()

    mock_ui.some_widget = mock_widget
    mock_widget.some_signal = mock_signal

    # Mock the register function
    mock_register_func = MagicMock()

    # Create a registry item
    registry_item = ParamChangeRegistryItem(
        widget_name="some_widget",
        widget_signal_name="some_signal",
        source_cfg_item="source_item",
        target_cfg_item="target_item",
        param_mapping={"key1": ("value1",)},
    )

    # Register the item
    registry_item.register(mock_register_func, mock_ui)

    # Assert the signal was connected to the register function
    mock_signal.connect.assert_called_once()

    # Get the connected partial function
    connected_partial = mock_signal.connect.call_args[0][0]

    # Assert the partial function was set up correctly
    assert connected_partial.func == mock_register_func
    assert connected_partial.args == ("source_item", "target_item", {"key1": ("value1",)})


def test_register_param_changes_iterates_registry():
    ui = MagicMock()
    items = (MagicMock(), MagicMock())

    with (
        patch("REvoDesign.driver.param_toggle_register.ParamChangeCollections", items),
        patch("REvoDesign.driver.param_toggle_register.refresh_widget_while_another_changed") as register_func,
    ):
        register_param_changes(ui)

    for item in items:
        item.register.assert_called_once_with(register_func, ui=ui)
