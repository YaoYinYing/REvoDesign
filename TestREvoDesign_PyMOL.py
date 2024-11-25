from unittest.mock import MagicMock, patch

import pytest

from REvoDesign_PyMOL import GitSolver  # Replace with actual module path


# Mock notify_box to simply print the message
def mock_notify_box(*args, **kwargs):
    if args:
        return print(args[0])
    if kwargs:
        return print(kwargs['message'])


@pytest.fixture
def git_solver():
    return GitSolver()


@pytest.mark.parametrize("has_git, expected_result", [
    (True, True),
    (False, False)
])
@patch('REvoDesign_PyMOL.notify_box', side_effect=mock_notify_box)
def test_fetch_git_when_git_present(git_solver, has_git, expected_result):
    with patch.object(git_solver, 'has_git', new=has_git):
        result = git_solver.fetch_git(env=None)
        assert result == expected_result


@pytest.mark.parametrize("has_conda, has_winget, has_brew,expected_cmd", [
    (True, False,False, ['conda', 'install', '-y', 'git']),
    (False, False,True, ['brew', 'install', 'git']),
    (False, True,False, [
        "winget",
        "install",
        "--id",
        "Git.Git",
        "-e",
        "--source",
        "winget",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]),
])
@patch('REvoDesign_PyMOL.notify_box', side_effect=mock_notify_box)
def test_fetch_git_with_installers(mock_notify, git_solver, has_conda, has_winget, has_brew,expected_cmd):
    with patch.object(git_solver, 'has_git', new=False), patch.object(git_solver, 'has_conda', new=has_conda), patch.object(git_solver, 'has_winget', new=has_winget), patch.object(git_solver, 'has_brew', new=has_brew):
        with patch('REvoDesign_PyMOL.run_command') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = git_solver.fetch_git(env=None)
            assert result
            mock_run.assert_called_once_with(
                cmd=expected_cmd,
                verbose=True,
                env=None
            )
            # Ensure notify_box was called with the correct message
            mock_notify.assert_called_once_with('Git installed successfully.')


def test_fetch_git_failed_installation(git_solver):
    with patch.object(git_solver, 'has_git', new=False), patch.object(git_solver, 'has_conda', new=False), patch.object(git_solver, 'has_winget', new=False), patch('REvoDesign_PyMOL.run_command') as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        with patch('REvoDesign_PyMOL.notify_box', side_effect=mock_notify_box) as mock_notify:
            result = git_solver.fetch_git(env=None)
            assert not result
            # Ensure notify_box was called with the correct message
            mock_notify.assert_called()
