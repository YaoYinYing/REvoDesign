# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import hmac
import io
import json
import os
import platform
import tempfile
import time
import urllib.error
import urllib.request
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

import REvoDesign.tools.package_manager as package_manager
from REvoDesign.Qt import QtWidgets
from REvoDesign.tools.package_manager import (
    GitSolver,
    PIPInstaller,
    REvoDesignPackageManager,
    _compute_hmac,
    _python_version_matches,
    fetch_gist_file,
    fetch_gist_json,
    filter_sensitive_data,
    get_github_repo_tags,
    load_packaged_extras_json,
    run_command,
    solve_installation_config,
    verify_manifest,
)


# Test for fetch_gist_file
def test_pm_fetch_gist_file_valid_url():
    mock_url = "https://example.com/file.ui"
    mock_data = "mock UI content"

    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        save_to_file = tmp_file.name

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = mock_data.encode("utf-8")

        fetch_gist_file(mock_url, save_to_file)

    with open(save_to_file) as file:
        content = file.read()
        assert content == mock_data

    os.remove(save_to_file)


def test_pm_fetch_gist_file_invalid_url():
    with pytest.raises(ValueError, match="URL must start with 'https'"):
        fetch_gist_file("http://example.com/file.ui", "temp_file.ui")


def test_pm_fetch_gist_file_url_error():
    mock_url = "https://example.com/file.ui"

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Mock error")):
        with pytest.raises(urllib.error.URLError, match="Failed to download file:"):
            fetch_gist_file(mock_url, "temp_file.ui")


def test_pm_fetch_gist_file_uses_timeout(monkeypatch, tmp_path):
    calls = []

    def mock_read(url, **kwargs):
        calls.append((url, kwargs))
        return b"mock UI content"

    output = tmp_path / "manager.ui"
    monkeypatch.setattr(package_manager, "_read_https_url", mock_read)

    fetch_gist_file("https://example.com/file.ui", str(output), timeout=3)

    assert output.read_text() == "mock UI content"
    assert calls == [("https://example.com/file.ui", {"timeout": 3})]


# Test for fetch_gist_json


def test_pm_fetch_gist_json_valid():
    mock_url = "https://example.com/data.json"
    mock_json = {"key1": "value1", "key2": "value2"}

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_json).encode("utf-8")

        result = fetch_gist_json(mock_url)

    assert result == mock_json


def test_pm_fetch_gist_json_invalid_structure():
    mock_url = "https://example.com/data.json"
    mock_data = ["value1", "value2"]

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(mock_data).encode("utf-8")

        result = fetch_gist_json(mock_url)

    assert result == {}  # Expecting empty dictionary due to invalid structure


def test_pm_fetch_gist_json_error():
    mock_url = "https://example.com/data.json"

    with patch("urllib.request.urlopen", side_effect=Exception("Mock error")):
        result = fetch_gist_json(mock_url)

    assert result == {}


def test_pm_load_packaged_extras_json(tmp_path):
    registry = tmp_path / "REvoDesignExtrasTableRich.json"
    registry.write_text(json.dumps({"entities": []}))

    assert load_packaged_extras_json(registry) == {"entities": []}


def test_pm_ensure_ui_file_cache_hit_no_network(monkeypatch, tmp_path):
    """Cached file exists and upgrade=False → return cached, no fetch."""
    ui_file = tmp_path / "REvoDesign_installer.ui"
    ui_file.write_text("<ui/>")
    monkeypatch.setattr(package_manager, "PACKAGED_MANAGER_UI_FILE", ui_file)
    mock_fetch = MagicMock(side_effect=AssertionError("cache hit must not fetch"))
    monkeypatch.setattr(package_manager, "fetch_gist_file", mock_fetch)

    plugin = REvoDesignPackageManager()

    assert plugin.ensure_ui_file() == str(ui_file)
    mock_fetch.assert_not_called()


def test_pm_ensure_ui_file_fetches_on_cache_miss(monkeypatch, tmp_path):
    """No cached file → fetch from Gist and cache it."""
    ui_file = tmp_path / "REvoDesign_installer.ui"
    monkeypatch.setattr(package_manager, "PACKAGED_MANAGER_UI_FILE", ui_file)

    fetch_calls = []

    def mock_fetch(ui_file_url, save_to_file, **kwargs):
        fetch_calls.append(save_to_file)
        with open(save_to_file, "w") as fh:
            fh.write("<ui from gist/>")

    monkeypatch.setattr(package_manager, "fetch_gist_file", mock_fetch)

    plugin = REvoDesignPackageManager()

    result = plugin.ensure_ui_file()
    assert result == str(ui_file)
    assert len(fetch_calls) == 1
    assert open(ui_file).read() == "<ui from gist/>"


def test_pm_load_packaged_json_does_not_fetch_network(monkeypatch, qtbot):
    plugin = REvoDesignPackageManager()
    list_view = QtWidgets.QListView()
    qtbot.addWidget(list_view)
    plugin.installer_ui = SimpleNamespace(listView_extras=list_view)

    monkeypatch.setattr(
        package_manager,
        "load_packaged_extras_json",
        lambda: {
            "entities": [
                {
                    "name": "Local Extras",
                    "description": "Vendored extras registry",
                    "extras": [],
                }
            ],
        },
    )
    monkeypatch.setattr(
        package_manager,
        "fetch_gist_json",
        MagicMock(side_effect=AssertionError("startup must not fetch extras")),
    )

    plugin.load_packaged_json()

    assert plugin.remote_extra_group_data.entities[0].name == "Local Extras"


def test_pm_run_command_success():
    """
    Test run_command for a successful command execution.
    """
    cmd = ("echo", "Hello, World!")

    mock_stdout = io.StringIO("Hello, World!\n")
    mock_stderr = io.StringIO("")

    mock_popen = MagicMock()
    mock_popen.stdout = mock_stdout
    mock_popen.stderr = mock_stderr
    mock_popen.wait.return_value = 0
    mock_popen.returncode = 0

    with patch("subprocess.Popen", return_value=mock_popen):
        result = run_command(cmd, verbose=False)

    assert result.returncode == 0
    assert "Hello, World!" in result.stdout
    assert result.stderr == ""


def test_pm_run_command_failure():
    """
    Test run_command for a command that fails (non-zero return code).
    """
    cmd = ("false",)

    mock_stdout = io.StringIO("")
    mock_stderr = io.StringIO("Error: something went wrong\n")

    mock_popen = MagicMock()
    mock_popen.stdout = mock_stdout
    mock_popen.stderr = mock_stderr
    mock_popen.wait.return_value = 1
    mock_popen.returncode = 1

    with patch("subprocess.Popen", return_value=mock_popen):
        result = run_command(cmd, verbose=False)

    assert result.returncode == 1
    assert "something went wrong" in result.stderr
    assert result.stdout == ""


def test_pm_run_command_verbose_failure():
    """
    Test run_command for a command that fails with verbose=True, raising an exception.
    """
    cmd = ("false",)

    mock_stdout = io.StringIO("")
    mock_stderr = io.StringIO("Error: bad stuff happened\n")

    mock_popen = MagicMock()
    mock_popen.stdout = mock_stdout
    mock_popen.stderr = mock_stderr
    mock_popen.wait.return_value = 1
    mock_popen.returncode = 1

    with patch("subprocess.Popen", return_value=mock_popen):
        with pytest.raises(RuntimeError, match="--> Command failed"):
            run_command(cmd, verbose=True)


def test_pm_run_command_with_env():
    """
    Test run_command with environment variables.
    """
    cmd = ("printenv", "MY_VAR")
    env = {"MY_VAR": "test_value"}

    mock_stdout = io.StringIO("test_value\n")
    mock_stderr = io.StringIO("")

    mock_popen = MagicMock()
    mock_popen.stdout = mock_stdout
    mock_popen.stderr = mock_stderr
    mock_popen.wait.return_value = 0
    mock_popen.returncode = 0

    with patch("subprocess.Popen", return_value=mock_popen) as mock_subproc:
        result = run_command(cmd, env=env)

    assert result.returncode == 0
    assert "test_value" in result.stdout
    mock_subproc.assert_called_once()
    # Check that env was passed correctly
    assert mock_subproc.call_args.kwargs["env"]["MY_VAR"] == "test_value"


@pytest.fixture(autouse=True)
def static_python_version(monkeypatch):
    """
    Force a deterministic python version so version-based filters behave consistently.
    """
    version = "3.11.11"
    monkeypatch.setattr(platform, "python_version", lambda: version)
    monkeypatch.setattr("REvoDesign.tools.package_manager.platform.python_version", lambda: version)
    monkeypatch.setitem(package_manager.PLATFORM_INFO, "PYTHON_VERSION", version)


@pytest.fixture(autouse=True)
def reset_thread_components():
    package_manager.ThreadPoolRegistry._entries.clear()
    package_manager.ThreadExecutionManager._instances.clear()
    dashboard = package_manager.ThreadDashboard._instance
    if dashboard is not None:
        dashboard.close()
        package_manager.ThreadDashboard._instance = None
    yield
    package_manager.ThreadPoolRegistry._entries.clear()
    package_manager.ThreadExecutionManager._instances.clear()
    dashboard = package_manager.ThreadDashboard._instance
    if dashboard is not None:
        dashboard.close()
        package_manager.ThreadDashboard._instance = None


@pytest.mark.parametrize(
    ("spec", "current_version", "python_version_matched"),
    [
        # empty match
        (None, "3.10", True),
        (" , , ", "3.9", True),
        (">=3.8", None, True),
        # lists and exclusion
        ("3.10,3.11,3.12", "3.10", True),
        ("3.10,3.11,3.12", "3.13", False),
        ("3.10,3.11,3.12,!=3.11.8", "3.10", True),
        ("3.10,3.11,3.12,!=3.11.8", "3.11.8", False),
        # ranges
        (">3.8", "3.9", True),
        (">=3.8,<3.11", "3.10", True),
        (">=3.8,<3.11", "3.11", False),
        (">3.8", "3.8", False),
        ("<=3.9", "3.10", False),
        ("<=3.10", "3.10", True),
        # equals
        ("==3.9", "3.9", True),
        ("==3.9", "3.10", False),
        ("==3.10", "3.10.4", True),
        ("==3.10.1", "3.10.2", False),
        # not equals
        ("!=3.9", "3.9", False),
        ("!=3.9", "3.8", True),
        ("!=3.10.4", "3.10.4", False),
        ("!=3.10.4", "3.10.5", True),
        # mixed
        (">=3.8,<3.11,!=3.10.2", "3.10.2", False),
        (">=3.8,<3.11,!=3.10.2", "3.10.3", True),
        (">=3.10,==3.10.0", "3.10.1", False),
        # spaces included
        (" >= 3.10 , < 3.11 ", "3.10.5", True),
        # invalid
        ("foo,bar", "3.11", True),
        ("==invalid,>=3.8", "3.9", True),
        (">=3.8", "invalid", True),
    ],
)
def test_python_version_matches(spec, current_version, python_version_matched):
    assert _python_version_matches(spec, current_version) is python_version_matched


@pytest.fixture
def mock_shutil_which():
    """
    Fixture to mock shutil.which function.
    """
    with patch("shutil.which") as mock_which:
        yield mock_which


@pytest.fixture
def mock_run_command():
    """
    Fixture to mock the run_command function.
    """
    with patch("REvoDesign.tools.package_manager.run_command") as mock_run:
        yield mock_run


@pytest.fixture
def git_solver_instance(mock_shutil_which):
    """
    Fixture to provide a GitSolver instance.
    """
    mock_shutil_which.side_effect = lambda tool: f"/mock/path/to/{tool}" if tool in ["git", "conda"] else None
    return GitSolver()


def test_pm_post_init(git_solver_instance):
    """
    Test that __post_init__ correctly initializes attributes.
    """
    assert git_solver_instance.has_git == "/mock/path/to/git"
    assert git_solver_instance.has_conda == "/mock/path/to/conda"
    assert git_solver_instance.has_mamba is None
    assert git_solver_instance.has_winget is None


def test_pm_where_to_install_with_winget(mock_shutil_which):
    """
    Test the where_to_install property when winget is available.
    """
    mock_shutil_which.side_effect = lambda tool: f"/mock/path/to/{tool}" if tool == "winget" else None
    solver = GitSolver()
    expected_command = [
        "/mock/path/to/winget",
        "install",
        "--id",
        "Git.Git",
        "-e",
        "--source",
        "winget",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]
    assert solver.where_to_install == expected_command


def test_pm_where_to_install_with_conda(mock_shutil_which):
    """
    Test the where_to_install property when conda is available.
    """
    mock_shutil_which.side_effect = lambda tool: f"/mock/path/to/{tool}" if tool == "conda" else None
    solver = GitSolver()
    expected_command = ["/mock/path/to/conda", "install", "-y", "git"]
    assert solver.where_to_install == expected_command


def test_pm_where_to_install_with_apt_and_sudo(mock_shutil_which):
    """
    Ensure Linux package managers are supported and prefixed with sudo when needed.
    """

    def fake_which(tool):
        mapping = {
            "apt-get": "/mock/path/to/apt-get",
            "sudo": "/mock/path/to/sudo",
        }
        return mapping.get(tool)

    mock_shutil_which.side_effect = fake_which
    solver = GitSolver()
    expected_command = ["/mock/path/to/sudo", "/mock/path/to/apt-get", "install", "-y", "git"]
    assert solver.where_to_install == expected_command


def test_pm_fetch_git_installed(git_solver_instance):
    """
    Test fetch_git method when git is already installed.
    """
    result, error_log = git_solver_instance.fetch_git(["dummy_command"])
    assert result is True
    assert error_log == ""


def test_pm_fetch_git_install_failure(mock_run_command, mock_shutil_which):
    """
    Test fetch_git method when installation succeeds.
    """
    mock_run_command.return_value = MagicMock(returncode=1, stdout="Mock STDOUT", stderr="Mock STDERR")
    mock_shutil_which.side_effect = lambda tool: None if tool == "git" else f"/mock/path/to/{tool}"

    solver = GitSolver()
    result, error_log = solver.fetch_git(["dummy_command"])

    assert result is False
    assert error_log != ""
    assert solver.has_git is None


@pytest.fixture
def pip_installer():
    """Fixture for PIPInstaller instance."""
    return PIPInstaller()


def test_pm_ensurepip_success(pip_installer, mocker):
    """Test ensurepip executes successfully."""
    mock_run_command = mocker.patch("REvoDesign.tools.package_manager.run_command")
    mock_run_command.return_value = MagicMock(returncode=0)

    pip_installer.ensurepip()

    mock_run_command.assert_called()


def test_pm_ensurepip_failure(pip_installer, mocker):
    """Test ensurepip raises an error on failure."""
    mock_run_command = mocker.patch("REvoDesign.tools.package_manager.run_command")
    mocker.patch("REvoDesign.tools.package_manager.notify_box")
    mock_run_command.return_value = MagicMock(returncode=1, stdout="stdout", stderr="stderr")

    pip_installer.ensurepip()


def test_pm_install_revo_design_success(pip_installer, mocker):
    """Test installing the REvoDesign package successfully."""
    mock_run_command = mocker.patch("REvoDesign.tools.package_manager.run_command")
    mock_solve_installation_config = mocker.patch("REvoDesign.tools.package_manager.solve_installation_config")
    mock_solve_installation_config.return_value = "mocked_package_string"
    mock_run_command.return_value = MagicMock(returncode=0)

    result = pip_installer.install(package_name="REvoDesign", source="https://example.com@v1.0")

    mock_solve_installation_config.assert_called_once_with(
        source="https://example.com@v1.0",
        git_url="https://example.com",
        git_tag="v1.0",
        extras=None,
        package_name="REvoDesign",
    )

    mock_run_command.assert_called()
    assert result.returncode == 0


def test_pm_uninstall(pip_installer, mocker):
    """Test uninstalling a package."""
    mock_run_command = mocker.patch("REvoDesign.tools.package_manager.run_command")
    mock_run_command.return_value = MagicMock(returncode=0)

    result = pip_installer.uninstall(package_name="some_package")

    mock_run_command.assert_called_once_with(
        [pip_installer.python_exe, "-m", "pip", "uninstall", "-y", "some_package"],
        verbose=pip_installer.verbose_level > -1,
        env=pip_installer.env,
    )

    assert result.returncode == 0


def test_pm_ensure_package(pip_installer, mocker):
    """Test ensuring a package installation."""
    mock_install = mocker.patch.object(pip_installer, "install")
    mock_install.return_value = MagicMock(returncode=0)

    pip_installer.ensure_package(package_string="some_package")

    mock_install.assert_called_once_with("some_package", upgrade=True, env=None, mirror=None)


class TestGetGithubRepoTags:

    def test_pm_valid_repo_url(self, monkeypatch):
        package_manager._GITHUB_TAG_CACHE.clear()
        repo_url = "https://github.com/BradyAJohnston/MolecularNodes"
        monkeypatch.setattr(
            package_manager,
            "_read_https_url",
            lambda url, **_kwargs: json.dumps([{"name": "v1.0.0"}, {"name": "v1.1.0"}]).encode(),
        )

        tags = get_github_repo_tags(repo_url)

        assert tags == ["v1.0.0", "v1.1.0"]

    def test_pm_invalid_repo_url(self):
        package_manager._GITHUB_TAG_CACHE.clear()
        repo_url = "https://example.com/nonexistent/repo"
        tags = get_github_repo_tags(repo_url)
        assert isinstance(tags, list)
        assert len(tags) == 0

    def test_pm_http_error(self, monkeypatch):
        package_manager._GITHUB_TAG_CACHE.clear()

        def mock_read(url, **_kwargs):
            raise HTTPError(url, 404, "Not Found", None, None)

        monkeypatch.setattr(package_manager, "_read_https_url", mock_read)

        repo_url = "https://github.com/BradyAJohnston/MolecularNodes"
        tags = get_github_repo_tags(repo_url)
        assert isinstance(tags, list)
        assert len(tags) == 0

    def test_pm_url_error(self, monkeypatch):
        package_manager._GITHUB_TAG_CACHE.clear()

        def mock_read(*_args, **_kwargs):
            raise URLError("Failed to reach the server")

        monkeypatch.setattr(package_manager, "_read_https_url", mock_read)

        repo_url = "https://github.com/BradyAJohnston/MolecularNodes"
        tags = get_github_repo_tags(repo_url)
        assert isinstance(tags, list)
        assert len(tags) == 0


def test_pm_get_github_repo_tags_uses_timeout_auth_and_cache(monkeypatch):
    calls = []

    def mock_read(url, **kwargs):
        calls.append((url, kwargs))
        return json.dumps([{"name": "v2.0.0"}]).encode()

    monkeypatch.setenv("GITHUB_TOKEN", "token-123")
    monkeypatch.setattr(package_manager, "_read_https_url", mock_read)
    package_manager._GITHUB_TAG_CACHE.clear()

    result = get_github_repo_tags("https://github.com/test_owner/test_repo", timeout=3)

    assert result == ["v2.0.0"]
    assert calls == [
        (
            "https://api.github.com/repos/test_owner/test_repo/tags",
            {
                "timeout": 3,
                "headers": {
                    "Accept": "application/vnd.github+json",
                    "Authorization": "Bearer token-123",
                },
            },
        )
    ]
    cached_at, cached_tags = package_manager._GITHUB_TAG_CACHE["https://api.github.com/repos/test_owner/test_repo/tags"]
    assert cached_at > 0
    assert cached_tags == ["v2.0.0"]

    assert get_github_repo_tags("https://github.com/test_owner/test_repo", timeout=3) == ["v2.0.0"]
    assert len(calls) == 1


def test_pm_get_github_repo_tags_falls_back_to_cached_tags(monkeypatch):
    api_url = "https://api.github.com/repos/test_owner/test_repo/tags"
    package_manager._GITHUB_TAG_CACHE[api_url] = (0.0, ["cached-tag"])

    def mock_read(url, **_kwargs):
        raise urllib.error.URLError(reason="Network unreachable")

    monkeypatch.setattr(package_manager, "_read_https_url", mock_read)

    result = get_github_repo_tags("https://github.com/test_owner/test_repo")

    assert result == ["cached-tag"]


@pytest.mark.parametrize(
    "env, expected",
    [
        (
            {"username": "user123", "password": "secret123", "email": "user@example.com"},
            {"username": "user123", "email": "user@example.com"},
        ),
        (
            {"api_key": "abcdef", "session_id": "12345", "token": "xyz"},
            {},
        ),
        (
            {"token": "value", "password": "value", "non_sensitive": "value"},
            {"non_sensitive": "value"},
        ),
        (
            {"data_key": "value", "info": "value", "random_key": "value"},
            {"info": "value"},
        ),
    ],
)
def test_pm_filter_sensitive_data(env, expected):
    """
    Tests the filter_sensitive_data function for various cases.

    Args:
        env (dict): Input dictionary to filter.
        expected (dict): Expected dictionary after filtering.
    """
    assert filter_sensitive_data(env) == expected


def test_pm_filter_sensitive_data_empty_dict():
    """
    Tests that the function returns an empty dictionary when the input is empty.
    """
    assert filter_sensitive_data({}) == {}


def test_pm_filter_sensitive_data_case_insensitivity():
    """
    Tests that the function correctly filters keys regardless of case.
    """
    env = {"TOKEN": "value", "Password": "value", "email": "user@example.com"}
    expected = {"email": "user@example.com"}
    assert filter_sensitive_data(env) == expected


# Mock utility function for run_command
def mocked_run_command(cmd):
    class MockCompletedProcess:
        def __init__(self, stdout):
            self.stdout = stdout

    if "pip" in cmd:
        return MockCompletedProcess(stdout="pip 21.0.1 from /path/to/pip")
    if "chcp" in cmd:
        return MockCompletedProcess(stdout="Active code page: 65001")
    return MockCompletedProcess(stdout="mock output")


# Mock utility function for fetch_gist_json


def mock_fetch_gist_json(url):
    if "ipinfo.io" in url:
        return {"ip": "127.0.0.1", "city": "MockCity"}
    return None


@pytest.fixture
def mock_environment():
    with (
        patch("platform.uname", return_value=platform.uname()),
        patch("platform.architecture", return_value=("64bit", "")),
        patch("platform.system", return_value="Linux"),
        patch("platform.release", return_value="5.15.0-1"),
        patch("platform.version", return_value="mock-version"),
        patch("os.cpu_count", return_value=8),
        patch("sys.platform", "linux"),
        patch("os.getenv", side_effect=lambda key: "mock_value" if key.startswith("CONDA") else None),
        patch.dict(os.environ, {"CONDA_PREFIX": ""}, {"OPENAI_TOKEN": "my_awesome_chatgpt_token"}),
        patch("socket.gethostbyname_ex", return_value=("localhost", [], ["127.0.0.1"])),
        patch("REvoDesign.tools.package_manager.run_command", side_effect=mocked_run_command),
        patch("REvoDesign.tools.package_manager.fetch_gist_json", side_effect=mock_fetch_gist_json),
    ):
        yield


def test_pm_issue_collection_default(mock_environment):
    from REvoDesign.tools.package_manager import issue_collection

    result = issue_collection()
    assert isinstance(result, dict)
    assert result["Platform::Platform"] == "linux"
    assert result["Platform::CPU::Num"] == 8
    assert "Python::Version" in result
    assert result["Network::IP"] == ["127.0.0.1"]
    assert "PyQt::Version" in result


def test_pm_issue_collection_with_dummy(mock_environment):
    from REvoDesign.tools.package_manager import issue_collection

    result = issue_collection(collect_dummy=True)
    assert "Dummy::Environ" in result
    assert "Dummy::Pip::List" in result


def test_pm_issue_collection_no_network(mock_environment):
    from REvoDesign.tools.package_manager import issue_collection

    result = issue_collection(network=False)
    assert "Network::Location" not in result
    assert result["Network::IP"] == ["127.0.0.1"]


def test_pm_issue_collection_drop_sensitive(mock_environment):
    from REvoDesign.tools.package_manager import issue_collection

    result = issue_collection(drop_sensitives=True, collect_dummy=True)
    assert not any(k for k in result["Dummy::Environ"] if "TOKEN" in k.upper())


# Mock the notify_box function to capture its calls
def mock_notify_box(message, exception=None):
    print(f"Notification: {message}")
    if exception:
        raise exception(message)


# Patch the notify_box function to use the mock


@pytest.fixture(autouse=True)
def patch_notify_box(monkeypatch):
    monkeypatch.setattr("REvoDesign.tools.package_manager.notify_box", mock_notify_box)


def test_pm_installation_from_github_url():
    source = "https://github.com/user/revo-design"
    git_url = "https://github.com/user/revo-design"
    git_tag = "v1.0.0"
    extras = None
    expected_output = "REvoDesign @ git+https://github.com/user/revo-design@v1.0.0"
    assert solve_installation_config(source, git_url, git_tag, extras) == expected_output


# def test_pm_installation_from_local_git_repo(test_tmp_dir):
#     source = test_tmp_dir
#     os.makedirs(os.path.join(test_tmp_dir,'.git'), exist_ok=True)
#     git_url = "https://github.com/user/revo-design"
#     git_tag = "v1.0.0"
#     extras = None
#     expected_output =f"REvoDesign @ git+file://{test_tmp_dir}@v1.0.0"

#     assert solve_installation_config(source, git_url, git_tag, extras) == expected_output


def test_pm_installation_from_local_code_directory(test_tmp_dir):
    source = test_tmp_dir
    git_url = "https://github.com/user/revo-design"
    git_tag = None
    with open(os.path.join(test_tmp_dir, "pyproject.toml"), "w") as f:
        f.write("[tool.poetry]\nname = 'REvoDesign'")
    extras = "extra1,extra2"
    expected_output = f"{test_tmp_dir}[extra1,extra2]"
    assert solve_installation_config(source, git_url, git_tag, extras) == expected_output


def test_pm_installation_from_zipped_file():
    source = "/path/to/local/code.zip"
    git_url = "https://github.com/user/revo-design"
    git_tag = None
    extras = "extra1,extra2"
    expected_output = "/path/to/local/code.zip[extra1,extra2]"
    with patch("os.path.isfile", return_value=True):
        assert solve_installation_config(source, git_url, git_tag, extras) == expected_output


def test_pm_installation_from_invalid_dir(test_tmp_dir):
    source = test_tmp_dir
    git_url = "https://github.com/user/revo-design"
    git_tag = "v1.0.0"
    extras = None

    with pytest.raises(ValueError, match="should atleast be a Git repository or a code directory"):
        solve_installation_config(source, git_url, git_tag, extras)


def test_pm_installation_from_invalid_file_type():
    source = "/path/to/local/code.txt"
    git_url = "https://github.com/user/revo-design"
    git_tag = None
    extras = None
    with patch("os.path.isfile"), pytest.raises(FileNotFoundError, match="is neither a zipped file nor a tar.gz file!"):
        solve_installation_config(source, git_url, git_tag, extras)


def test_pm_installation_from_random_shit_source():
    source = "dudududada"
    git_url = "https://github.com/user/revo-design"
    git_tag = None
    extras = None
    with pytest.raises(ValueError, match="Unknown installation source"):
        solve_installation_config(source, git_url, git_tag, extras)


def test_pm_thread_manage_kill_entry(qtbot, monkeypatch):
    button = QtWidgets.QPushButton("Killable")
    qtbot.addWidget(button)

    class FakeProcess:
        terminated = False
        killed = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.killed = True

    def cancellable_task():
        thread = package_manager.QtCore.QThread.currentThread()
        start = time.monotonic()
        while time.monotonic() - start < 2:
            if thread.isInterruptionRequested():
                return "aborted"
            time.sleep(0.01)
        return "completed"

    worker_thread = package_manager.WorkerThread(cancellable_task)
    manager = package_manager.ThreadExecutionManager(worker_thread, description="Kill", trigger_buttons=button)
    fake_process = FakeProcess()
    package_manager.RunningProcessRegistry._worker_processes[id(worker_thread)] = {fake_process}
    package_manager.RunningProcessRegistry._process_worker[id(fake_process)] = id(worker_thread)
    assert manager.abort_overlays

    mock_cmd = SimpleNamespace(interrupt=MagicMock())
    monkeypatch.setattr(package_manager, "cmd", mock_cmd, raising=False)

    worker_thread.start()
    qtbot.wait(50)

    entry = next(iter(package_manager.ThreadPoolRegistry._entries.values()))
    package_manager.ThreadExecutionManager.kill_entry(entry)

    qtbot.waitUntil(lambda: not package_manager.ThreadPoolRegistry._entries, timeout=2000)
    qtbot.waitUntil(lambda: not package_manager.ThreadExecutionManager._instances, timeout=2000)
    worker_thread.wait(2000)
    result = worker_thread.handle_result()

    assert manager.abort_overlays == []
    assert not mock_cmd.interrupt.called
    assert fake_process.terminated
    assert not fake_process.killed
    assert result is None or result[0] == "aborted"


def test_worker_thread_emits_and_records_errors(qtbot):
    def failing_task():
        raise RuntimeError("worker exploded")

    worker_thread = package_manager.WorkerThread(failing_task)
    errors = []
    notifications = []
    finished = []
    worker_thread.error_signal.connect(errors.append)
    worker_thread.notify_signal.connect(notifications.append)
    worker_thread.finished_signal.connect(lambda: finished.append(True))

    worker_thread.start()

    qtbot.waitUntil(lambda: bool(finished), timeout=2000)
    worker_thread.wait(2000)

    assert worker_thread.handle_result() is None
    assert isinstance(worker_thread.handle_error(), RuntimeError)
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert notifications == ["RuntimeError: worker exploded"]


def test_run_worker_thread_in_pool_reraises_worker_errors(qtbot, monkeypatch):
    monkeypatch.setattr(package_manager, "refresh_window", lambda: None)

    def failing_task():
        raise RuntimeError("worker exploded")

    with pytest.raises(RuntimeError, match="worker exploded"):
        package_manager.run_worker_thread_in_pool(failing_task, notify_slot=lambda _message: None)


# ── HMAC manifest verification ────────────────────────────────────────────


def test_pm_verify_manifest_all_match(monkeypatch, tmp_path):
    key = os.urandom(32)
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", key)
    files = {}
    manifest = {}
    for name in ("a.py", "b.ui"):
        path = tmp_path / name
        path.write_bytes(os.urandom(64))
        files[name] = str(path)
        manifest[name] = hmac.new(key, path.read_bytes(), "sha256").hexdigest()

    assert verify_manifest(files, manifest)


def test_pm_verify_manifest_mismatch(monkeypatch, tmp_path):
    key = os.urandom(32)
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", key)
    path = tmp_path / "a.py"
    path.write_bytes(b"original")
    manifest = {"a.py": hmac.new(key, b"tampered", "sha256").hexdigest()}

    assert not verify_manifest({"a.py": str(path)}, manifest)


def test_pm_verify_manifest_missing_entry(monkeypatch, tmp_path):
    key = os.urandom(32)
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", key)
    path = tmp_path / "a.py"
    path.write_bytes(b"data")

    assert not verify_manifest({"a.py": str(path)}, {})


def test_pm_compute_hmac_deterministic(monkeypatch, tmp_path):
    key = os.urandom(32)
    monkeypatch.setattr(package_manager, "_MANAGER_HMAC_KEY", key)
    path = tmp_path / "a.py"
    path.write_bytes(b"hello")

    assert _compute_hmac(str(path)) == _compute_hmac(str(path))


# ── fetch_tags graceful degradation ───────────────────────────────────────


def test_pm_fetch_tags_silent_on_network_error(monkeypatch, qtbot):
    plugin = REvoDesignPackageManager()
    list_view = QtWidgets.QListView()
    qtbot.addWidget(list_view)
    plugin.installer_ui = SimpleNamespace(listView_extras=list_view, comboBox_version=QtWidgets.QComboBox())
    monkeypatch.setattr(
        package_manager,
        "get_github_repo_tags",
        MagicMock(side_effect=URLError("offline")),
    )

    # Must not raise, must not call notify_box
    with patch("REvoDesign.tools.package_manager.notify_box") as mock_notify:
        plugin.fetch_tags()
        mock_notify.assert_not_called()
