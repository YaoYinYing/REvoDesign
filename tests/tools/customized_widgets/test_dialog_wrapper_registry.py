from unittest.mock import patch

import pytest

from REvoDesign.shortcuts.utils import (DialogWrapperRegistry,
                                        run_wrapped_func_in_thread)
from REvoDesign.tools.customized_widgets import AskedValue


@pytest.fixture
def mock_yaml_content():
    return {
        "test_func": {
            "title": "Test Function",
            "banner": "Run a test function",
            "options": [
                {
                    "name": "input_file",
                    "type": "str",
                    "default": "example.txt"
                }
            ]
        }
    }


@patch("REvoDesign.shortcuts.utils.Path.exists", return_value=True)
@patch("REvoDesign.shortcuts.utils.DialogWrapperRegistry._load_yaml")
def test_dialog_wrapper_registry_initialization(mock_load_yaml, mock_exists, mock_yaml_content):
    mock_load_yaml.return_value = mock_yaml_content

    registry = DialogWrapperRegistry("test_category")

    assert registry.config == mock_yaml_content
    mock_load_yaml.assert_called_once()


@patch("REvoDesign.shortcuts.utils.Path.exists", return_value=True)
@patch("REvoDesign.shortcuts.utils.DialogWrapperRegistry._load_yaml")
@patch("REvoDesign.shortcuts.utils.partial")
def test_dialog_wrapper_registry_register_with_thread(mock_partial, mock_load_yaml, mock_exists, mock_yaml_content):
    mock_load_yaml.return_value = mock_yaml_content

    def dummy_function(**kwargs):
        return kwargs

    registry = DialogWrapperRegistry("test_category")
    registry.funcs = {}  # reset

    kwargs = {"key": "value"}
    registry.register("test_func", dummy_function, use_thread=True, use_progressbar=False, kwargs=kwargs)

    assert "test_func" in registry.funcs
    mock_partial.assert_called_once_with(run_wrapped_func_in_thread, dummy_function, use_progressbar=False, **kwargs)


@patch("REvoDesign.shortcuts.utils.Path.exists", return_value=True)
@patch("REvoDesign.shortcuts.utils.DialogWrapperRegistry._load_yaml")
def ttest_dialog_wrapper_registry_register_without_thread(mock_load_yaml, mock_exists, mock_yaml_content):
    mock_load_yaml.return_value = mock_yaml_content

    def dummy_function(**kwargs):
        return kwargs
    registry = DialogWrapperRegistry("test_category")
    registry.funcs = {}  # reset

    registry.register("test_func", dummy_function, use_progressbar=False, use_thread=False)

    assert registry.funcs["test_func"] == dummy_function


@patch("REvoDesign.shortcuts.utils.Path.exists", return_value=True)
@patch("REvoDesign.shortcuts.utils.DialogWrapperRegistry._load_yaml")
def test_dialog_wrapper_registry_window_wrapper_dynamic_values(mock_load_yaml, mock_exists, mock_yaml_content):
    mock_load_yaml.return_value = mock_yaml_content

    def dummy_function(dynamic_values=None):
        return dynamic_values

    dynamic_value = {
        "value": AskedValue(
            "sele",
            val="(all)",
            typing=str,
            reason="mock dynamic value.",
            choices=['(all)', 'polymer.protein'],
            multiple_choices=True
        ),
        "index": 0,
    }

    registry = DialogWrapperRegistry("test_category")
    assert registry.funcs == {}

    wrapper = registry.register("test_func", dummy_function, use_progressbar=False, has_dynamic_values=True)
    assert registry.funcs == {"test_func": dummy_function}

    assert wrapper.__doc__ is not None
    assert 'given dynamic values' in wrapper.__doc__


@patch("REvoDesign.shortcuts.utils.Path.exists", return_value=True)
@patch("REvoDesign.shortcuts.utils.DialogWrapperRegistry._load_yaml")
def test_dialog_wrapper_registry_window_wrapper_no_dynamic_values(mock_load_yaml, mock_exists, mock_yaml_content):
    mock_load_yaml.return_value = mock_yaml_content

    def dummy_function():
        return "called"

    registry = DialogWrapperRegistry("test_category")

    wrapper = registry.register("test_func", dummy_function, use_progressbar=False, has_dynamic_values=False)

    assert wrapper.__doc__ is not None
    assert 'no dynamic values' in wrapper.__doc__


@patch("REvoDesign.shortcuts.utils.Path.exists", return_value=True)
@patch("REvoDesign.shortcuts.utils.DialogWrapperRegistry._load_yaml")
def test_dialog_wrapper_registry_unregister(mock_load_yaml, mock_exists, mock_yaml_content):
    mock_load_yaml.return_value = mock_yaml_content

    def dummy_function():
        return
    registry = DialogWrapperRegistry("test_category")
    registry.register("test_func", dummy_function, use_progressbar=False)

    assert registry.funcs == {"test_func": dummy_function}

    registry.unregister("test_func")
    assert "test_func" not in registry.funcs
