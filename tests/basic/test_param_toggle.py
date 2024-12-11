import pytest
from unittest.mock import MagicMock, call
from functools import partial
from REvoDesign.basic.param_toggle import ParamChangeRegistryItem, ParamChangeRegister  


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
        param_mapping={"key1": ("value1",)}
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
        param_mapping={"key1": ("value1",)}
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

def test_param_change_register_register_all():
    # Mock the UI, widgets, and signals
    mock_ui = MagicMock()
    mock_widget1 = MagicMock()
    mock_signal1 = MagicMock()

    mock_widget2 = MagicMock()
    mock_signal2 = MagicMock()

    mock_ui.widget1 = mock_widget1
    mock_widget1.signal1 = mock_signal1

    mock_ui.widget2 = mock_widget2
    mock_widget2.signal2 = mock_signal2

    # Mock the register function
    mock_register_func = MagicMock()

    # Create registry items
    registry_item1 = ParamChangeRegistryItem(
        widget_name="widget1",
        widget_signal_name="signal1",
        source_cfg_item="source1",
        target_cfg_item="target1",
        param_mapping={"keyA": ("valueA",)}
    )

    registry_item2 = ParamChangeRegistryItem(
        widget_name="widget2",
        widget_signal_name="signal2",
        source_cfg_item="source2",
        target_cfg_item="target2",
        param_mapping={"keyB": ("valueB",)}
    )

    # Create the ParamChangeRegister instance
    param_register = ParamChangeRegister(
        register_func=mock_register_func,
        registry=(registry_item1, registry_item2)
    )

    # Register all items
    param_register.register_all(mock_ui)

    # Assert the signals were connected to the register function
    mock_signal1.connect.assert_called_once()
    mock_signal2.connect.assert_called_once()

    # Verify the first connected partial function
    connected_partial1 = mock_signal1.connect.call_args[0][0]
    assert connected_partial1.func == mock_register_func
    assert connected_partial1.args == ("source1", "target1", {"keyA": ("valueA",)})

    # Verify the second connected partial function
    connected_partial2 = mock_signal2.connect.call_args[0][0]
    assert connected_partial2.func == mock_register_func
    assert connected_partial2.args == ("source2", "target2", {"keyB": ("valueB",)})
