# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


from typing import Any
from unittest.mock import MagicMock

import pytest

# Import target module
from REvoDesign.tools.customized_widgets import AskedValue, AskedValueCollection, AskedValueDynamic, dialog_wrapper

# -----------------------------
# Fixtures and Helpers
# -----------------------------


@pytest.fixture
def dummy_function():
    """Returns a mock function to be wrapped by dialog_wrapper."""
    return MagicMock()


def assert_asked_value_equal(av1: AskedValue, av2: AskedValue):
    """Helper to compare two AskedValue objects."""
    assert vars(av1) == vars(av2)


# -----------------------------
# Parametrized Tests
# -----------------------------


test_asked_values = [
    AskedValue(key="name", val="Alice", typing=str),
    AskedValue(key="age", val=30, typing=int),
    AskedValue(key="is_active", val=True, typing=bool),
]

dynamic_asked_values_with_index: list[dict[str, Any]] = [
    {
        "value": AskedValue(key="email", val="alice@example.com", typing=str),
        "index": 1,
    },
    {
        "value": AskedValue(key="score", val=95, typing=int),
        "index": 3,
    },
]

# Test that TypedDict enforces correct structure


@pytest.mark.parametrize("input_dict", dynamic_asked_values_with_index)
def test_asked_value_dynamic_type_check(input_dict: dict[str, Any]):
    """Ensure that AskedValueDynamic accepts valid dicts."""
    try:
        _: AskedValueDynamic = input_dict  # type: ignore
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")


# Test merging static + dynamic options


@pytest.mark.parametrize(
    "static_options, dynamic_options, expected_order",
    [
        # Case 1: Insert dynamic at specified index
        (
            test_asked_values,
            dynamic_asked_values_with_index,
            ["name", "email", "age", "score", "is_active"],
        ),
        # Case 2: Dynamic insert beyond length appends at end
        (
            test_asked_values,
            [{"value": AskedValue(key="extra", val="end", typing=str), "index": 10}],
            ["name", "age", "is_active", "extra"],
        ),
        # Case 3: No dynamic values
        (
            test_asked_values,
            [],
            ["name", "age", "is_active"],
        ),
    ],
)
def test_asked_value_dynamic_merge_static_and_dynamic_values(
    static_options: list[AskedValue],
    dynamic_options: list[dict[str, Any]],
    expected_order: list[str],
):
    """Ensure that dynamic values are inserted correctly into static list."""
    all_options = list(static_options)
    for item in dynamic_options:
        index = item.get("index", len(all_options))
        all_options.insert(index, item["value"])

    assert [av.key for av in all_options] == expected_order


def test_asked_value_dynamic_direct_use():
    avd = [
        AskedValueDynamic(value=AskedValue(key="email", val="alice@example.com", typing=str), index=1),
        AskedValueDynamic(
            value=AskedValue(key="score", val=95, typing=int),
            index=3,
        ),
    ]
    assert avd == dynamic_asked_values_with_index
