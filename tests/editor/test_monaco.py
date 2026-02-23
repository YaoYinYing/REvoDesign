# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

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
def mock_run_worker_thread_in_pool():
    """Fixture to mock run_worker_thread_in_pool."""
    with patch("REvoDesign.tools.utils.run_worker_thread_in_pool") as mock:
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


@pytest.mark.parametrize(
    "autosave_enabled,autorefresh_enabled",
    [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ],
)
def test_edit_file_with_monaco_autosave_refresh_params(test_tmp_dir, autosave_enabled, autorefresh_enabled):
    file_path = os.path.join(test_tmp_dir, "combo.txt")
    Path(file_path).write_text("test")

    config_values = {
        "editor.backend.use_ssl": False,
        "editor.backend.host": "127.0.0.1",
        "editor.backend.port": 9999,
        "editor.token": None,
        "editor.backend.no_token": True,
        "editor.autosave.enabled": autosave_enabled,
        "editor.autosave.interval": 1,
        "editor.autorefresh.enabled": autorefresh_enabled,
        "editor.autorefresh.interval": 1,
    }

    server_monitor = SimpleNamespace(controller=SimpleNamespace(is_running=True))
    server_monitor._start_server = lambda: None
    stores_widget = SimpleNamespace(server_switches={"Editor_Backend": server_monitor})

    with (
        patch("REvoDesign.editor.monaco.monaco.ConfigStore") as MockConfigStore,
        patch("REvoDesign.editor.monaco.monaco.StoresWidget", return_value=stores_widget),
        patch("webbrowser.open") as mock_webbrowser_open,
    ):
        config_instance = MockConfigStore.return_value
        config_instance.get.side_effect = lambda key, default=None: config_values.get(key, default)

        edit_file_with_monaco(file_path)

        called_url = mock_webbrowser_open.call_args[0][0]

    parsed = urlparse(called_url)
    params = {key: value[0] for key, value in parse_qs(parsed.query).items()}

    assert params["autosaveEnabled"] == str(autosave_enabled).lower()
    assert params["refreshEnabled"] == str(autorefresh_enabled).lower()
    assert params["autosaveInterval"] == "1"
    assert params["refreshInterval"] == "1000"
