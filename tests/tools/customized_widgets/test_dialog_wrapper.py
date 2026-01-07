import os
from unittest.mock import patch

import pytest

from REvoDesign import issues
from REvoDesign.Qt import QtCore, QtWidgets
from REvoDesign.tools.customized_widgets import (
    AskedValue,
    AskedValueCollection,
    MultiCheckableComboBox,
    ValueDialog,
    set_widget_value,
)

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
        AskedValue(
            key="field4",
            val=1.0,
            typing=float,
            choices=(
                1.0,
                2.5,
                3.5,
            ),
        ),
        AskedValue(
            key="field5",
            val="choice1",
            typing=str,
            choices=(
                "choice1",
                "choice2",
                "choice3",
            ),
        ),
        AskedValue(
            key="field6",
            val="",
            typing=str,
            reason="Field 6 Reason",
            choices=[
                "choice1",
                "choice2",
                "choice3",
            ],
            multiple_choices=True,
        ),
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


@pytest.mark.parametrize(
    "index, expected_widget_type",
    [
        (0, QtWidgets.QLineEdit),
        (1, QtWidgets.QSpinBox),
        (2, QtWidgets.QCheckBox),
        (3, QtWidgets.QComboBox),
        (4, QtWidgets.QComboBox),
        (5, MultiCheckableComboBox),
    ],
)
def test_dialog_wrapper_field_widget_types(dialog, index, expected_widget_type, test_worker):
    """
    Validates the widget type assigned to each field and captures a screenshot.
    """
    widget = dialog.table.cellWidget(index, 2)
    assert isinstance(widget, expected_widget_type)
    save_screenshot(dialog, f"field_widget_types_row_{index}")


def test_dialog_wrapper_dialog_initialization(dialog, test_worker):
    """
    Verifies that the dialog initializes correctly and captures a screenshot.
    """
    assert dialog.windowTitle() == "Test Dialog"
    assert dialog.layout.itemAt(0).widget().text() == "Sample Banner"
    assert dialog.table.rowCount() == 6
    save_screenshot(dialog, "dialog_initialization")


def test_dialog_wrapper_required_field_validation(dialog, qtbot, monkeypatch, test_worker):
    """
    Tests that required fields are validated and QMessageBox is triggered. Captures a screenshot.
    """
    # Clear the required field
    widget = dialog.table.cellWidget(0, 2)
    widget.setText("")

    with patch("REvoDesign.tools.customized_widgets.QtWidgets.QMessageBox.warning") as mock_msgbox_warning:

        # Mock QMessageBox to capture the warning call
        # def mock_warning(parent, title, message):
        #     assert title == "Missing Input"
        #     assert "Please provide a value for 'field1'" in message
        #     # save_screenshot(parent, "required_field_validation_warning")
        #     return QtWidgets.QMessageBox.Ok

        # Simulate OK button click
        ok_button = dialog.layout.itemAt(4).itemAt(0).widget()

        with patch.object(dialog, "close") as close_mock:

            qtbot.mouseClick(ok_button, QtCore.Qt.LeftButton)
            mock_msgbox_warning.assert_called_once()
            # with pytest.raises(issues.NoInputError):
            monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *args, **kwargs: QtWidgets.QMessageBox.Yes)
        #     close_mock.assert_not_called()
        dialog.close()


@pytest.mark.parametrize(
    "index, expected_widget_type, updated_value, expected_value",
    [
        (0, QtWidgets.QLineEdit, "Updated Text", "Updated Text"),
        (1, QtWidgets.QSpinBox, 50, 50),
        (2, QtWidgets.QCheckBox, False, False),
        (3, QtWidgets.QComboBox, 2.5, "2.5"),
        (4, QtWidgets.QComboBox, "choice2", "choice2"),
        (5, MultiCheckableComboBox, ["choice2", "choice3"], ["choice2", "choice3"]),
    ],
)
def test_dialog_wrapper_valid_field_submission(
    index, expected_widget_type, updated_value, expected_value, dialog, qtbot, test_worker
):
    """
    Tests that valid fields are correctly submitted and captures a screenshot.
    """
    widget = dialog.table.cellWidget(index, 2)
    assert isinstance(widget, expected_widget_type)
    set_widget_value(widget, updated_value)

    # Simulate OK button click
    qtbot.mouseClick(dialog.layout.itemAt(4).itemAt(0).widget(), QtCore.Qt.LeftButton)

    # Verify updated values
    assert len(dialog.updated_values) == 6
    assert dialog.updated_values[index].val == expected_value

    save_screenshot(dialog, f"valid_field_submission-{index}-{expected_widget_type.__name__}")


def test_dialog_wrapper_dialog_rejection(test_worker, dialog, qtbot):
    """
    Ensures dialog rejection works as expected and captures a screenshot.
    """
    cancel_button = dialog.layout.itemAt(4).itemAt(1).widget()
    save_screenshot(dialog, "dialog_rejection")

    # Verify dialog is rejected

    with patch.object(dialog, "close") as close_mock:
        qtbot.mouseClick(cancel_button, QtCore.Qt.LeftButton)

        close_mock.assert_called_once()


"""
AskedValue(key="field1", val="default", typing=str, required=True, reason="Field 1 Reason"),
AskedValue(key="field2", val=42, typing=int, choices=range(10, 100)),
AskedValue(key="field3", val=True, typing=bool, required=False),
AskedValue(key="field4", val=1.0, typing=float, choices=(1.0, 2.5, 3.5,)),
AskedValue(key="field5", val='choice1', typing=str, choices=("choice1", "choice2", "choice3",)),
AskedValue(key="field6", val='', typing=list, reason="Field 6 Reason", choices=["choice1", "choice2", "choice3",]),

"""


def test_dialog_wrapper_field_populates_correctly(test_worker, dialog):
    """
    Tests that fields are populated with the correct initial values and captures a screenshot.
    """

    assert dialog.table.cellWidget(0, 2).text() == "default"
    assert dialog.table.cellWidget(1, 2).value() == 42
    assert dialog.table.cellWidget(2, 2).isChecked()
    assert dialog.table.cellWidget(3, 2).currentText() == "1.0"
    assert dialog.table.cellWidget(4, 2).currentText() == "choice1"
    assert isinstance(widget := dialog.table.cellWidget(5, 2), MultiCheckableComboBox)
    assert widget.get_checked_items() == []

    save_screenshot(dialog, "field_populates_correctly")
