import pytest
from pymol.Qt import QtCore, QtWidgets

from REvoDesign.tools.customized_widgets import (AskedValue,
                                                 AskedValueCollection,
                                                 MultiCheckableComboBox,
                                                 ValueDialog, real_bool)


@pytest.mark.parametrize("input_value, expected", [
    ("True", True),
    ("true", True),
    ("1", True),
    ("yes", True),
    (1, True),
    (True, True),
    ("False", False),
    ("false", False),
    ("0", False),
    ("no", False),
    (0, False),
    (False, False),
])
def test_real_bool(input_value, expected):
    assert real_bool(input_value) is expected


@pytest.fixture
def sample_asked_value_collection():

    asked_values = [
        AskedValue(key="field1", val="test", typing=str, required=True),
        AskedValue(key="field2", val=42, typing=int, required=False, choices=range(0, 100)),
        AskedValue(key="field3", val=42, typing=int, required=False, choices=(29, 30, 42,)),
    ]
    return AskedValueCollection(asked_values=asked_values, banner="Test Banner")


def test_typing_fixed(sample_asked_value_collection: AskedValueCollection):
    sample_asked_value_collection.asked_values[2].val = '30'
    fixed = sample_asked_value_collection.typing_fixed
    assert fixed.asked_values[2].val == 30


def test_as_dict(sample_asked_value_collection: AskedValueCollection):
    dict_form = sample_asked_value_collection.asdict
    for i, asked in enumerate(sample_asked_value_collection.asked_values):
        assert asked.key in dict_form, f"{asked.key} should be in dict_form"
        assert dict_form[asked.key] == asked.val, f"{asked.key} in dict form should be {asked.val}"


def test_multicheckable_combobox(qtbot):
    choices = ["Option1", "Option2", "Option3"]
    combo_box = MultiCheckableComboBox(choices)
    qtbot.addWidget(combo_box)

    # Verify initial state
    assert combo_box.get_checked_items() == []

    # Check some items
    combo_box.set_checked_items(["Option1", "Option3"])
    assert combo_box.get_checked_items() == ["Option1", "Option3"]

    # Simulate popup closing to update `self.checked_items`
    combo_box.hidePopup()

    # Verify currentText override
    assert combo_box.currentText() == "Option1, Option3"


def test_value_dialog_initialization(qtbot, sample_asked_value_collection):

    dialog = ValueDialog("Test Dialog", sample_asked_value_collection)
    qtbot.addWidget(dialog)

    # Verify the banner message
    assert dialog.layout.itemAt(0).widget().text() == "Test Banner"

    # Verify table population
    assert dialog.table.rowCount() == 3
    assert dialog.table.columnCount() == 3


def test_value_dialog_ok_button(qtbot, sample_asked_value_collection):

    dialog = ValueDialog("Test Dialog", sample_asked_value_collection)
    qtbot.addWidget(dialog)

    # Simulate input changes
    widget = dialog.table.cellWidget(0, 2)
    if isinstance(widget, QtWidgets.QLineEdit):
        widget.setText("updated_value")

    # Simulate OK button click
    qtbot.mouseClick(dialog.layout.itemAt(2).itemAt(0).widget(), QtCore.Qt.LeftButton)

    # Verify updated values
    assert len(dialog.updated_values) == 3
    assert dialog.updated_values[0].val == "updated_value"


def test_appendable_value_dialog(qtbot):
    from REvoDesign.tools.customized_widgets import AppendableValueDialog

    dialog = AppendableValueDialog()
    qtbot.addWidget(dialog)

    # Add a row and verify
    dialog._add_row("key1", "val1")
    assert len(dialog.row_widgets) == 2

    # Remove a row and verify
    dialog._remove_row(dialog.row_widgets[0][0])
    assert len(dialog.row_widgets) == 1

    # Verify OK button behavior
    qtbot.mouseClick(dialog.layout.itemAt(2).itemAt(0).widget(), QtCore.Qt.LeftButton)
    assert len(dialog.updated_values) == 1
    assert dialog.updated_values[0].key == "key1"
    assert dialog.updated_values[0].val == "val1"
