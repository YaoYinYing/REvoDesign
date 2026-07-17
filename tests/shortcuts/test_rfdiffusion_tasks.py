# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from types import SimpleNamespace

import pytest

from REvoDesign import issues
from REvoDesign.shortcuts.tools import rfdiffusion_tasks


def test_dgl_solver_does_not_run_pip_without_approval(monkeypatch):
    solver = rfdiffusion_tasks.DglSolver(installed=False)
    monkeypatch.setattr(solver, "fetch_cuda_version_before_install", lambda: None)
    monkeypatch.setattr(rfdiffusion_tasks, "_has_qapplication", lambda: True)
    monkeypatch.delenv(rfdiffusion_tasks.DGL_INSTALL_APPROVAL_ENV, raising=False)
    monkeypatch.setattr(rfdiffusion_tasks, "decide", lambda **_kwargs: False)

    def fail_run_command(_cmd):
        raise AssertionError("pip install should not run without approval")

    monkeypatch.setattr(rfdiffusion_tasks, "run_command", fail_run_command)

    assert solver.install() is False
    assert solver.installed is False


def test_dgl_solver_declines_without_qapplication(monkeypatch):
    solver = rfdiffusion_tasks.DglSolver(installed=False)
    monkeypatch.setattr(solver, "fetch_cuda_version_before_install", lambda: None)
    monkeypatch.setattr(rfdiffusion_tasks, "_has_qapplication", lambda: False)
    monkeypatch.delenv(rfdiffusion_tasks.DGL_INSTALL_APPROVAL_ENV, raising=False)

    def fail_decide(**_kwargs):
        raise AssertionError("headless DGL install approval should not open a dialog")

    def fail_run_command(_cmd):
        raise AssertionError("pip install should not run without approval")

    monkeypatch.setattr(rfdiffusion_tasks, "decide", fail_decide)
    monkeypatch.setattr(rfdiffusion_tasks, "run_command", fail_run_command)

    assert solver.install() is False
    assert solver.installed is False


def test_dgl_solver_env_approval_runs_pip(monkeypatch):
    solver = rfdiffusion_tasks.DglSolver(installed=False)
    commands = []
    monkeypatch.setattr(solver, "fetch_cuda_version_before_install", lambda: None)
    monkeypatch.setenv(rfdiffusion_tasks.DGL_INSTALL_APPROVAL_ENV, "1")
    monkeypatch.setattr(rfdiffusion_tasks, "decide", lambda **_kwargs: False)
    monkeypatch.setattr(
        rfdiffusion_tasks,
        "run_command",
        lambda cmd: commands.append(cmd) or SimpleNamespace(returncode=0, stderr=""),
    )

    assert solver.install() is True
    assert solver.installed is True
    assert commands == [
        [
            rfdiffusion_tasks.sys.executable,
            "-m",
            "pip",
            "install",
            "dgl==2.2.1",
            "-f",
            "https://data.dgl.ai/wheels/repo.html",
        ]
    ]


def test_ensure_dgl_raises_when_installation_is_declined(monkeypatch):
    solver = rfdiffusion_tasks.DglSolver(installed=False)
    monkeypatch.setattr(rfdiffusion_tasks, "DglSolver", lambda: solver)
    monkeypatch.setattr(solver, "install", lambda: False)

    with pytest.raises(issues.MissingExternalToolError, match="DGL installation was cancelled"):
        rfdiffusion_tasks.RfDiffusion.ensure_dgl()
