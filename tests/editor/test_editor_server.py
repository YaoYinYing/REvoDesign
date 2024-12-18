from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from REvoDesign.editor.monaco.config import ConfigStore
from REvoDesign.editor.monaco.server import ServerControl, app


def create_mock_file_with_content(tmp_path, filename, content):
    """Helper function to create a mock file with content."""
    file_path = tmp_path / filename
    file_path.write_text(content)
    return str(file_path.resolve())


def _make_token_fixture(use_token: bool):
    """Factory function to create token-related fixtures."""
    def _fixture(tmp_path):
        cfg = ConfigStore()
        cfg.set("editor.backend.no_token", not use_token)

        token = None
        if use_token:
            token = "mock_token"
            cfg.set("editor.token", token)

        editable = create_mock_file_with_content(tmp_path, "editable.txt", "I am editable")
        readonly = create_mock_file_with_content(tmp_path, "readonly.txt", "I am readonly")

        # Luckydog file that may hit by xss
        luckydog = create_mock_file_with_content(tmp_path, "luckydog.txt", "I am luckydog")

        not_exists_file = str(tmp_path / "not_exists.txt")
        not_exists_dir_and_file = str(tmp_path / "not_exists_dir" / "not_exists_file.txt")

        cfg.set("monaco.file_whitelist.editable", [editable, not_exists_dir_and_file])
        cfg.set("monaco.file_whitelist.readonly", [readonly, not_exists_file])
        cfg.set("monaco.file.luckydog", luckydog)

        return cfg, token

    return _fixture


@pytest.fixture(params=[True, False])
def mock_config_store(request, tmp_path):
    """Parameterized fixture for token and no-token scenarios."""
    use_token = request.param
    return _make_token_fixture(use_token)(tmp_path)


@pytest.fixture
def test_client(mock_config_store):
    """Fixture to create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_temp_dir(test_tmp_dir):
    """Fixture to use the test temporary directory."""
    return Path(test_tmp_dir)


# Helper to reset rate limits
def reset_rate_limits():
    from REvoDesign.editor.monaco.server import failed_attempts
    failed_attempts.clear()


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


@pytest.mark.parametrize("use_token", [True, False])
def test_load_file_not_found(use_token, mock_config_store, test_client):
    """Test the /load_file endpoint with an invalid file path."""
    reset_rate_limits()
    if not use_token and mock_config_store[1]:
        pytest.skip("Token required but not provided in mock_config_store.")

    cfg, token = mock_config_store

    file_path = cfg.get("monaco.file_whitelist.readonly")[1]
    url = f"/load_file?file_path={file_path}"
    if use_token and token:
        url += f"&token={token}"
    response = test_client.get(url)
    assert response.status_code == 404
    assert response.json() == {"error": "File not found"}


@pytest.mark.parametrize("use_token", [True, False])
def test_load_file_not_allowed(use_token, mock_temp_dir, test_client, mock_config_store):
    """Test the /load_file endpoint with a file not in the whitelist."""
    reset_rate_limits()
    if not use_token and mock_config_store[1]:
        pytest.skip("Token required but not provided in mock_config_store.")
    cfg, token = mock_config_store
    temp_file = mock_temp_dir / "not_allowed.txt"
    temp_file.write_text("Unauthorized access")
    url = f"/load_file?file_path={temp_file}"
    if use_token and token:
        url += f"&token={token}"
    response = test_client.get(url)
    assert response.status_code == 403
    assert response.json()["detail"] == "Loading this file is not allowed: Permission denied."


@pytest.mark.parametrize("use_token", [True, False])
def test_save_file_not_allowed(use_token, mock_temp_dir, test_client, mock_config_store):
    """Test the /save_file endpoint with a file not in the editable whitelist."""
    reset_rate_limits()
    if not use_token and mock_config_store[1]:
        pytest.skip("Token required but not provided in mock_config_store.")
    cfg, token = mock_config_store
    temp_file = mock_temp_dir / "readonly.txt"
    data = {"file_path": str(temp_file), "content": "Invalid Write"}
    url = "/save_file"
    if use_token and token:
        url += f"?token={token}"
    response = test_client.post(url, json=data)
    assert response.status_code == 403
    assert response.json()["detail"] == "Writing into this file is not allowed."


@pytest.mark.parametrize("use_token", [True, False])
def test_save_file_directory_not_found(use_token, test_client, mock_config_store):
    """Test the /save_file endpoint with an invalid directory."""
    reset_rate_limits()
    if not use_token and mock_config_store[1]:
        pytest.skip("Token required but not provided in mock_config_store.")
    cfg, token = mock_config_store
    file_path = cfg.get("monaco.file_whitelist.editable")[1]
    data = {"file_path": file_path, "content": "Content"}
    url = "/save_file"
    if use_token and token:
        url += f"?token={token}"
    response = test_client.post(url, json=data)
    assert response.status_code == 400
    assert response.json()["error"].startswith("Directory does not exist")


@pytest.mark.parametrize("use_token", [True, False])
def test_rate_limiting(use_token, mock_temp_dir, test_client, mock_config_store):
    """Test rate limiting on repeated failed authentication attempts."""
    reset_rate_limits()
    if not use_token and mock_config_store[1]:
        pytest.skip("Token required but not provided in mock_config_store.")
    cfg, token = mock_config_store
    temp_file = mock_temp_dir / "invalid_readonly.txt"
    temp_file.write_text("Rate limit test")
    url = f"/load_file?file_path={temp_file}"
    if use_token and token:
        url += f"&token={token}"
    # Simulate repeated failed requests
    for _ in range(10):
        response = test_client.get(url)
    # After the limit is exceeded, a 429 response should be returned
    response = test_client.get(url)
    assert response.status_code == 429
    assert response.json()["detail"] == "Too many failed attempts. Please try again later."


def test_server_control(mock_config_store, initialize_server):
    """Test starting and stopping the server."""
    reset_rate_limits()
    initialize_server.start_server()
    assert initialize_server.is_running is True

    initialize_server.stop_server()
    assert initialize_server.is_running is False


@pytest.mark.parametrize("use_token", [True, False])
def test_load_file_success(use_token, mock_config_store, test_client):
    """Test the /load_file endpoint with a valid file path under both token and no-token scenarios."""
    reset_rate_limits()
    if not use_token and mock_config_store[1]:
        pytest.skip("Token required but not provided in mock_config_store.")

    cfg, token = mock_config_store
    temp_file = cfg.get("monaco.file_whitelist.readonly")[0]
    url = f"/load_file?file_path={temp_file}"
    if use_token and token:
        url += f"&token={token}"
    response = test_client.get(url)
    assert response.status_code == 200
    assert response.json() == {"content": "I am readonly"}


@pytest.mark.parametrize(
    "file_path, expected_status, description",
    [
        ("<script>alert('XSS')</script>", 403, "XSS injection with script tags"),
        ("../unauthorized", 403, "Path traversal attempt"),
        ("valid_file.txt", 403, "Valid file path"),
        ('../../../../../../../../etc/passwd', 403, 'Path traversal attempt: Hit'),
        ('../../../../../../../../etcdss/passwd', 403, 'Path traversal attempt: Not hit'),
        ("lucky.dog", 403, "Lucky dog gets caught"),  # a file that does exist and gets caught by attacker
        ("<img src=x onerror=alert('XSS')>", 403, "XSS injection with image tag"),
        ("<svg onload=alert('XSS')>", 403, "XSS injection with SVG tag"),
    ]
)
def test_editor_xss_injection(file_path, expected_status, description, test_client, mock_config_store):
    """Test various XSS injection and path traversal attacks on the editor endpoint."""
    reset_rate_limits()
    cfg, token = mock_config_store
    if file_path == "lucky.dog":
        file_path = cfg.get("monaco.file.luckydog")

    url = f"/editor?file_path={file_path}"
    if token:
        url += f"&token={token}"
    response = test_client.get(url)
    assert response.status_code == expected_status, description
    if expected_status == 400:
        assert "<script>" not in response.text, "Response should not include script tags"
        assert "alert" not in response.text, "Response should not include alert calls"


@pytest.mark.parametrize("use_token", [True, False])
def test_save_file_success(use_token, mock_config_store, test_client):
    """Test the /save_file endpoint with a valid file path under both token and no-token scenarios."""
    reset_rate_limits()
    if not use_token and mock_config_store[1]:
        pytest.skip("Token required but not provided in mock_config_store.")

    cfg, token = mock_config_store
    temp_file = cfg.get("monaco.file_whitelist.editable")[0]
    data = {"file_path": temp_file, "content": "Updated Content"}
    url = f"/save_file"
    if use_token and token:
        url += f"?token={token}"
    response = test_client.post(url, json=data)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    assert Path(temp_file).read_text() == "Updated Content"
