import pytest
from unittest.mock import MagicMock
from functools import partial

from REvoDesign.basic.menu_item import MenuCollection, MenuItem


def test_menu_item_initialization():
    mock_action = MagicMock()
    mock_func = MagicMock()
    kwargs = {"arg1": "value1"}

    menu_item = MenuItem(action=mock_action, func=mock_func, kwargs=kwargs)

    assert menu_item.action == mock_action
    assert menu_item.func == mock_func
    assert menu_item.kwargs == kwargs


def test_menu_collection_bind():
    mock_action1 = MagicMock()
    mock_func1 = MagicMock()
    mock_action2 = MagicMock()
    mock_func2 = MagicMock()

    menu_item1 = MenuItem(action=mock_action1, func=mock_func1)
    menu_item2 = MenuItem(action=mock_action2, func=mock_func2, kwargs={"key": "value"})

    menu_collection = MenuCollection(menu_items=(menu_item1, menu_item2))

    # Verify that the actions were connected to the correct functions
    assert len(mock_action1.triggered.connect.call_args_list) == 1
    assert len(mock_action2.triggered.connect.call_args_list) == 1

    # Check the partial object with function and arguments
    connected_partial1 = mock_action1.triggered.connect.call_args_list[0][0][0]
    connected_partial2 = mock_action2.triggered.connect.call_args_list[0][0][0]

    # Verify the functions and arguments for partials
    assert connected_partial1.func == mock_func1
    assert connected_partial2.func == mock_func2
    assert connected_partial2.keywords == {"key": "value"}