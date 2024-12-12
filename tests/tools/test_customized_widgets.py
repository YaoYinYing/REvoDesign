import pytest

from REvoDesign.tools.customized_widgets import real_bool


def test_real_bool_true():
    # Test cases that should return True
    true_values = ["True", "true", "1", 'yes', 'Yes', 'Y', 1, True]
    for value in true_values:
        assert real_bool(value) is True


def test_real_bool_false():
    # Test cases that should return False
    false_values = ["False", "false", "0", 'no', 'No', 'N', 0, False]
    for value in false_values:
        assert real_bool(value) is False
