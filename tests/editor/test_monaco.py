import os
from pathlib import Path
from unittest.mock import patch

import pytest

from REvoDesign.editor.monaco.monaco import MonacoEditorManager, edit_file_with_monaco


@pytest.fixture
def mock_config_store():
    """Fixture to mock ConfigStore."""
    with patch("REvoDesign.editor.monaco.server.ConfigStore") as MockConfigStore:
        mock_store = MockConfigStore.return_value
        yield mock_store


@pytest.fixture
def mock_server_control():
    """Fixture to mock ServerControl."""
    with patch("REvoDesign.editor.monaco.server.ServerControl") as MockServerControl:
        mock_server = MockServerControl.return_value
        yield mock_server


@pytest.fixture
def mock_user_data_dir(test_tmp_dir):
    """Fixture to mock user_data_dir."""
    with patch("platformdirs.user_data_dir", return_value=test_tmp_dir) as mock:
        yield mock


@pytest.fixture
def mock_run_worker_thread_with_progress():
    """Fixture to mock run_worker_thread_with_progress."""
    with patch("REvoDesign.tools.utils.run_worker_thread_with_progress") as mock:
        yield mock


@pytest.mark.serial
def test_ensure_editor_downloaded(test_tmp_dir, mock_user_data_dir, mock_config_store):
    manager = MonacoEditorManager(app_name="TestApp", app_author="TestAuthor")

    # Mock the editor_path to use the temporary directory
    manager.editor_path = test_tmp_dir
    manager.html_template_path = os.path.join(test_tmp_dir, "index.html")
    Path(manager.html_template_path).touch()  # Create a dummy template
    manager.ensure_editor_downloaded(no_upgrade=True)


def test_copy_html_template(test_tmp_dir):
    manager = MonacoEditorManager(app_name="TestApp", app_author="TestAuthor")

    # Mock the editor_path to use the temporary directory
    manager.editor_path = test_tmp_dir
    manager.html_template_path = os.path.join(test_tmp_dir, "index.html")
    version_dir = os.path.join(test_tmp_dir, "monaco-editor")
    os.makedirs(version_dir)
    Path(manager.html_template_path).touch()  # Create a dummy template

    with patch("shutil.copy") as mock_copy:
        manager.copy_html_template(version_dir)
        mock_copy.assert_called_once_with(manager.html_template_path, os.path.join(version_dir, "index.html"))


def test_edit_file_with_monaco(mock_server_control, mock_config_store, test_tmp_dir, test_worker):

    file_path = os.path.join(test_tmp_dir, "file.txt")
    with open(file_path, "w") as f:
        f.write("Some content")

    with patch("webbrowser.open") as mock_webbrowser_open:
        edit_file_with_monaco(file_path)
        mock_webbrowser_open.assert_called_once()
