import os

import pytest
from pymol.Qt import QtCore, QtWidgets

from REvoDesign.tools.customized_widgets import (AskedValue,
                                                 AskedValueCollection,
                                                 ValueDialog)

SCREENSHOT_DIR = "screenshots/unit/value_dialog"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


@pytest.fixture
def sample_asked_value_collection():
    """
    Creates a sample AskedValueCollection for testing.
    """
    asked_values = [
        AskedValue(key="field1", val="default", typing=str, required=True, reason="Field 1 Reason"),
        AskedValue(key="field2", val=42, typing=int, choices=range(10, 100)),
        AskedValue(key="field3", val=True, typing=bool, required=False),
    ]
    return AskedValueCollection(asked_values=asked_values, banner="Sample Banner")


@pytest.fixture
def dialog(qtbot, sample_asked_value_collection):
    """
    Provides an instance of ValueDialog for testing.
    """
    dialog = ValueDialog("Test Dialog", sample_asked_value_collection)
    qtbot.addWidget(dialog)
    return dialog


def save_screenshot(widget, name):
    """
    Saves a screenshot of the widget to the designated directory.
    """
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    widget.grab().save(path)


@pytest.mark.parametrize("index, expected_widget_type", [
    (0, QtWidgets.QLineEdit),
    (1, QtWidgets.QSpinBox),
    (2, QtWidgets.QComboBox),
])
def test_field_widget_types(dialog, index, expected_widget_type):
    """
    Validates the widget type assigned to each field and captures a screenshot.
    """
    widget = dialog.table.cellWidget(index, 2)
    assert isinstance(widget, expected_widget_type)
    save_screenshot(dialog, f"field_widget_types_row_{index}")


def test_dialog_initialization(dialog):
    """
    Verifies that the dialog initializes correctly and captures a screenshot.
    """
    assert dialog.windowTitle() == "Test Dialog"
    assert dialog.layout.itemAt(0).widget().text() == "Sample Banner"
    assert dialog.table.rowCount() == 3
    save_screenshot(dialog, "dialog_initialization")


def test_required_field_validation(dialog, qtbot, monkeypatch):
    """
    Tests that required fields are validated and QMessageBox is triggered. Captures a screenshot.
    """
    # Clear the required field
    widget = dialog.table.cellWidget(0, 2)
    widget.setText("")

    # Mock QMessageBox to capture the warning call
    def mock_warning(parent, title, message):
        assert title == "Missing Input"
        assert "Please provide a value for 'field1'" in message
        save_screenshot(parent, "required_field_validation_warning")
        return QtWidgets.QMessageBox.Ok

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", mock_warning)

    # Simulate OK button click
    ok_button = dialog.layout.itemAt(2).itemAt(0).widget()
    qtbot.mouseClick(ok_button, QtCore.Qt.LeftButton)

    # Ensure dialog remains open and validation failed
    assert len(dialog.updated_values) == 0
    assert not dialog.result()  # Dialog should not close


def test_valid_field_submission(dialog, qtbot):
    """
    Tests that valid fields are correctly submitted and captures a screenshot.
    """
    # Modify field values
    line_edit = dialog.table.cellWidget(0, 2)
    line_edit.setText("Updated Text")

    spin_box = dialog.table.cellWidget(1, 2)
    spin_box.setValue(50)

    combo_box = dialog.table.cellWidget(2, 2)
    combo_box.setCurrentText("False")

    # Simulate OK button click
    qtbot.mouseClick(dialog.layout.itemAt(2).itemAt(0).widget(), QtCore.Qt.LeftButton)

    # Verify updated values
    assert len(dialog.updated_values) == 3
    assert dialog.updated_values[0].val == "Updated Text"
    assert dialog.updated_values[1].val == 50
    assert dialog.updated_values[2].val is False
    save_screenshot(dialog, "valid_field_submission")


def test_dialog_rejection(dialog, qtbot):
    """
    Ensures dialog rejection works as expected and captures a screenshot.
    """
    cancel_button = dialog.layout.itemAt(2).itemAt(1).widget()
    qtbot.mouseClick(cancel_button, QtCore.Qt.LeftButton)

    # Verify dialog is rejected
    assert not dialog.result()
    save_screenshot(dialog, "dialog_rejection")


def test_field_populates_correctly(dialog):
    """
    Tests that fields are populated with the correct initial values and captures a screenshot.
    """
    assert dialog.table.cellWidget(0, 2).text() == "default"
    assert dialog.table.cellWidget(1, 2).value() == 42
    assert dialog.table.cellWidget(2, 2).currentText() == "True"
    save_screenshot(dialog, "field_populates_correctly")
