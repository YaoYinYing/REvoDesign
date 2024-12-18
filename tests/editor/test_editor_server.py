from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from REvoDesign.editor.monaco.config import ConfigStore
from REvoDesign.editor.monaco.server import ServerControl, app, is_file_allowed


@pytest.fixture
def mock_config_store(test_tmp_dir):
    """Fixture to mock the ConfigStore."""
    cfg = ConfigStore()
    cfg.set("editor.backend.no_token", True)  # Allow bypassing token for testing
    cfg.set("editor.backend.html_dir", Path(test_tmp_dir))

    # Mock whitelists
    editable=Path(test_tmp_dir).resolve() / "editable.txt"
    editable.write_text('I am editable')
    readonly=Path(test_tmp_dir).resolve() / "readonly.txt"
    readonly.write_text('I am readonly')
    cfg.set("monaco.file_whitelist.editable", [str(editable)])
    cfg.set("monaco.file_whitelist.readonly", [str(readonly)])

    yield cfg
    ConfigStore.reset_instance()


@pytest.fixture
def test_client(mock_config_store):
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


def test_load_file_success(test_client,mock_config_store):
    """Test the /load_file endpoint with a valid file path."""

    temp_file = mock_config_store.get('monaco.file_whitelist.readonly')[0]
    temp_file=Path(temp_file).resolve()

    response = test_client.get(f"/load_file?file_path={str(temp_file)}")

    assert not 'Permission denied' in response.text, "Permission denied message should not be found in response"
    assert response.status_code == 200, "Status code should be 200"
    assert response.json() == {"content": "I am readonly"}


def test_load_file_not_found(test_client):
    """Test the /load_file endpoint with an invalid file path."""
    response = test_client.get("/load_file?file_path=/invalid/path.txt")
    assert response.status_code == 404
    assert response.json() == {"error": "File not found"}


def test_load_file_not_allowed(mock_temp_dir, test_client, mock_config_store):
    """Test the /load_file endpoint with a file not in the whitelist."""
    cfg = ConfigStore()
    editable_files_real = cfg.get("monaco.file_whitelist.editable", default=()) 
    editable_files_mock = mock_config_store.get("monaco.file_whitelist.editable", default=())

    assert editable_files_real == editable_files_mock, "Mock and real configs differ"
    temp_file = mock_temp_dir / "not_allowed.txt"
    temp_file.write_text("Unauthorized access")

    response = test_client.get(f"/load_file?file_path={temp_file}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Loading this file is not allowed: Permission denied."


def test_save_file_success(test_client,mock_config_store):

    """Test the /save_file endpoint to save file content."""
    temp_file = mock_config_store.get('monaco.file_whitelist.editable')[0]
    temp_file=Path(temp_file).resolve()
    data = {"file_path": str(temp_file), "content": "New Content"}
    # assert is_file_allowed(temp_file, require_editable=True)

    response = test_client.post(f"/save_file", json=data)
    assert response.status_code == 200, 'Status code should be 200'
    assert response.json() == {"status": "success"}, 'Response should be success'
    assert temp_file.read_text() == "New Content", 'File content should be updated'


def test_save_file_not_allowed(mock_temp_dir, test_client, mock_config_store):
    """Test the /save_file endpoint with a file not in the editable whitelist."""
    temp_file = mock_temp_dir / "readonly.txt"
    data = {"file_path": str(temp_file), "content": "Invalid Write"}

    response = test_client.post("/save_file", json=data)
    assert response.status_code == 403
    assert response.json()["detail"] == "Writing into this file is not allowed."


def test_save_file_directory_not_found(test_client):
    """Test the /save_file endpoint with an invalid directory."""
    data = {"file_path": "/invalid/path/test.txt", "content": "Content"}

    response = test_client.post("/save_file", json=data)
    assert response.status_code == 400
    assert response.json()["error"].startswith("Directory does not exist")


def test_rate_limiting(mock_temp_dir, test_client, mock_config_store):
    """Test rate limiting on repeated failed authentication attempts."""
    temp_file = mock_temp_dir / "invalid_readonly.txt"
    temp_file.write_text("Rate limit test")

    # Simulate repeated failed requests
    for _ in range(10):
        response = test_client.get(f"/load_file?file_path={temp_file}")

    # After the limit is exceeded, a 429 response should be returned
    response = test_client.get(f"/load_file?file_path={temp_file}")
    assert response.status_code == 429
    assert response.json()["detail"] == "Too many failed attempts. Please try again later."


def test_server_control(mock_config_store, initialize_server):
    """Test starting and stopping the server."""
    initialize_server.start_server()
    assert initialize_server.is_running is True

    initialize_server.stop_server()
    assert initialize_server.is_running is False
