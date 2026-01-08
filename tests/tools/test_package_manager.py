import io
import json
import os
import platform
import tempfile
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from REvoDesign.tools.package_manager import (
    GitSolver,
    PIPInstaller,
    fetch_gist_file,
    fetch_gist_json,
    filter_sensitive_data,
    get_github_repo_tags,
    run_command,
    solve_installation_config,
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

    def test_pm_valid_repo_url(self):
        # Test a valid repository URL, expecting a list of tags
        repo_url = "https://github.com/BradyAJohnston/MolecularNodes"
        tags = get_github_repo_tags(repo_url)
        assert isinstance(tags, list)
        assert len(tags) > 0
        for tag in tags:
            assert isinstance(tag, str)

    def test_pm_invalid_repo_url(self):
        # Test an invalid repository URL, expecting an empty list
        repo_url = "https://github.com/nonexistent/repo"
        tags = get_github_repo_tags(repo_url)
        assert isinstance(tags, list)
        assert len(tags) == 0

    def test_pm_http_error(self, monkeypatch):
        # Test handling of HTTPError
        def mock_urlopen(*args, **kwargs):
            raise HTTPError(args[0], 404, "Not Found", None, None)

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        repo_url = "https://github.com/BradyAJohnston/MolecularNodes"
        tags = get_github_repo_tags(repo_url)
        assert isinstance(tags, list)
        assert len(tags) == 0

    def test_pm_url_error(self, monkeypatch):
        # Test handling of URLError
        def mock_urlopen(*args, **kwargs):
            raise URLError("Failed to reach the server")

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        repo_url = "https://github.com/BradyAJohnston/MolecularNodes"
        tags = get_github_repo_tags(repo_url)
        assert isinstance(tags, list)
        assert len(tags) == 0


def test_pm_get_github_repo_tags_success():
    """Test successful retrieval of tags."""

    result = get_github_repo_tags("https://github.com/BradyAJohnston/MolecularNodes")
    assert result, "Github repository tags should not be empty"


def test_pm_get_github_repo_tags_http_error():
    """Test handling of an HTTPError."""
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(
            url="https://api.github.com/repos/test_owner/test_repo/tags", code=404, msg="Not Found", hdrs=None, fp=None
        ),
    ):
        result = get_github_repo_tags("https://github.com/test_owner/test_repo")
        assert result == []


def test_pm_get_github_repo_tags_url_error():
    """Test handling of a URLError."""
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError(reason="Network unreachable")):
        result = get_github_repo_tags("https://github.com/test_owner/test_repo")
        assert result == []


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
