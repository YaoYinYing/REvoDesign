import pytest
import yaml

from REvoDesign import issues
from REvoDesign.basic.extensions import resolve_extension
from REvoDesign.common.file_extensions import ExtColl
from REvoDesign.shortcuts.tools.esm2 import \
    list_all_esm_variant_predict_model_names
from REvoDesign.shortcuts.utils import (REGISTRY_DIR, DialogWrapperRegistry,
                                        _build_asked_value,
                                        resolve_choice_from,
                                        resolve_default_value)

from REvoDesign.tools.utils import resolve_dotted_function

# --- Test resolve_extension --- #


@pytest.mark.parametrize(
    "extension, expected_pattern",
    [
        ("PDB_STRICT", "Protein Data Bank format file ( *.pdb )"),
        ("pdb", "Customized - PDB File ( *.pdb )"),
        ("fasta", "Customized - FASTA File ( *.fasta )"),
        ("custom;txt", "Customized - CUSTOM File ( *.custom );;Customized - TXT File ( *.txt )"),
    ]
)
def test_resolve_extension(extension, expected_pattern):
    result = resolve_extension(extension)
    assert isinstance(result, ExtColl)
    assert result.filter_string == expected_pattern  # Adjust based on how __str__ or repr works for ExtColl


@pytest.mark.parametrize(
    "dotted_str",
    [
        "REvoDesign.tools.utils:device_picker",
        "REvoDesign.shortcuts.tools.esm2:list_all_esm_variant_predict_model_names",
        "REvoDesign.driver.group_register:CallableGroupValues.list_all_profile_parsers",
    ]
)
def test_resolve_dotted_function_pass(dotted_str):
    from typing import Callable

    result = resolve_dotted_function(dotted_str)
    assert isinstance(result, Callable)
    assert dotted_str.endswith(result.__name__)


@pytest.mark.parametrize(
    "dotted_str",
    [
        "REvoDesign.tools.utils.device_picker",
    ]
)
def test_resolve_dotted_function_error(dotted_str):
    with pytest.raises(issues.InvalidInputError):
        resolve_dotted_function(dotted_str)


@pytest.mark.parametrize(
    "input_str, expected_type, expected_val",
    [
        ('range:1,10', range, range(1, 10)),
        ('range:1,10,2', range, range(1, 10, 2)),
        (
            'REvoDesign.shortcuts.tools.esm2:list_all_esm_variant_predict_model_names',
            list,
            list_all_esm_variant_predict_model_names()
        ),
        ('CFG:ui.header_panel.cmap.default', str, 'bwr_r'),
        ('CFG:ui.header_panel.cmap.wtf', type(None), None)

    ]
)
def test_resolve_choice_from(input_str, expected_type, expected_val):
    result = resolve_choice_from(input_str)
    assert isinstance(result, expected_type)
    assert result == expected_val


@pytest.mark.parametrize(
    "input_str, error_type",
    [
        ('range:1,2,3,4', issues.InvalidInputError),
        ('REvoDesign.shortcuts.tools.esm2.ESM1V_MODEL_DICT', issues.InvalidInputError),
        ('CFG:ui:header_panel:cmap:wtf', issues.InvalidInputError),
        ('unexpected', issues.ConfigurationError)
    ]
)
def test_resolve_choice_from_error(input_str, error_type):
    with pytest.raises(error_type):
        resolve_choice_from(input_str)


@pytest.mark.parametrize(
    "input_type, expected_output",
    [
        (bool, False),
        (int, 0),
        (float, 0.0),
        (str, ""),
    ],
)
def test_resolve_default_value_valid_types(input_type, expected_output):
    assert resolve_default_value(input_type) == expected_output


def test_resolve_default_value_unknown_type():
    class CustomType:
        pass

    assert resolve_default_value(CustomType) is None

# --- Test _build_asked_value --- #


@pytest.mark.parametrize(
    "entry, expected_name, expected_type, expected_default",
    [
        (
            {"name": "num_iter", "type": "int", "default": 10},
            "num_iter", int, 10
        ),
        (
            {"name": "log_file", "type": "str", "default": "/tmp/log.txt"},
            "log_file", str, "/tmp/log.txt"
        ),
        (
            {"name": "verbose", "type": "bool", "default": True},
            "verbose", bool, True
        ),
        (
            {"name": "output_dir", "type": "str"},
            "output_dir", str, ""
        ),
        (
            {"name": "file_ext", "type": "str", "ext": "pdb;fasta"},
            "file_ext", str, ""
        ),
        (
            {"name": "num_iter", "type": "int", "choices_from": 'range:1,11', "default": 10},
            "num_iter", int, 10
        ),

    ]
)
def test_build_asked_value(entry, expected_name, expected_type, expected_default):
    asked_value = _build_asked_value(entry)
    assert asked_value.key == expected_name
    assert asked_value.typing == expected_type
    assert asked_value.val == expected_default


REQUIRED_KEYS = {"title", "banner", "options"}


@pytest.mark.parametrize(
    "yaml_path",
    list((REGISTRY_DIR).glob("*.yaml")),
    ids=lambda p: p.stem
)
def test_dialog_yaml_valid_structure(yaml_path):
    """
    Ensure every dialog YAML is:
    - valid YAML syntax
    - a dict of function names
    - each function has required keys: title, banner, options
    """
    with open(yaml_path, encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"YAML syntax error in {yaml_path.name}: {e}")

    assert isinstance(data, dict), f"{yaml_path.name} should contain a dict at top level."

    for func_id, config in data.items():
        assert isinstance(config, dict), f"{func_id} in {yaml_path.name} is not a dict"
        missing = REQUIRED_KEYS - config.keys()
        assert not missing, f"{func_id} in {yaml_path.name} missing keys: {missing}"
        assert isinstance(config["options"], list), f"{func_id}.options in {yaml_path.name} should be a list"
