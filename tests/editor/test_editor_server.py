from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from REvoDesign.editor.monaco.config import ConfigStore
# Import the FastAPI app
from REvoDesign.editor.monaco.server import ServerControl, app


@pytest.fixture
def mock_config_store(test_tmp_dir):
    """Fixture to mock the ConfigStore."""
    ConfigStore.reset_instance()
    cfg = ConfigStore()
    cfg.set('editor.backend.no_token', False)
    cfg.set('editor.backend.html_dir', test_tmp_dir)
    yield cfg
    ConfigStore.reset_instance()


@pytest.fixture
def test_client():
    """Fixture to create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_temp_dir(test_tmp_dir):
    """Fixture to use the test temporary directory."""
    return Path(test_tmp_dir)


@pytest.fixture
def initialize_server():
    """Initialize ServerControl and clean up after tests."""
    server_control = ServerControl()
    yield server_control
    server_control.stop_server()

# Test cases


def test_favicon(test_client):
    """Test that the favicon endpoint returns the correct file."""
    response = test_client.get("/favicon.svg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"


def test_load_file_success(mock_temp_dir, test_client):
    """Test the /load_file endpoint with a valid file path."""
    temp_file = mock_temp_dir / "test.txt"
    temp_file.write_text("Hello, World!")

    response = test_client.get(f"/load_file?file_path={temp_file}")
    assert response.status_code == 200
    assert response.json() == {"content": "Hello, World!"}


def test_load_file_not_found(test_client):
    """Test the /load_file endpoint with an invalid file path."""
    response = test_client.get("/load_file?file_path=/invalid/path.txt")
    assert response.status_code == 404
    assert response.json() == {"error": "File not found"}


def test_save_file_success(mock_temp_dir, test_client):
    """Test the /save_file endpoint to save file content."""
    temp_file = mock_temp_dir / "test.txt"
    data = {"file_path": str(temp_file), "content": "New Content"}

    response = test_client.post("/save_file", json=data)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert temp_file.read_text() == "New Content"


def test_save_file_directory_not_found(test_client):
    """Test the /save_file endpoint with an invalid directory."""
    data = {"file_path": "/invalid/path/test.txt", "content": "Content"}

    response = test_client.post("/save_file", json=data)
    assert response.status_code == 400
    assert response.json()["error"].startswith("Directory does not exist")


def test_server_control(mock_config_store, initialize_server):
    """Test starting and stopping the server."""
    initialize_server.start_server()
    assert initialize_server.is_running is True

    initialize_server.stop_server()
    assert initialize_server.is_running is False
