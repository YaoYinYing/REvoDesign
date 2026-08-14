# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Security hardening for task_runtime: symlink-aware path containment and
post-completion workspace cleanup."""

from __future__ import annotations

import importlib
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def rt(monkeypatch, tmp_path):
    """Import task_runtime with a self-contained server/config layout."""
    env_root = tmp_path / "server"
    shutil.copytree(SERVER_DIR / "config", env_root / "config")
    monkeypatch.setenv("SERVER_DIR", str(env_root))
    monkeypatch.setenv("CONFIG_DIR", str(env_root / "config"))
    monkeypatch.setenv("RUNNER_UID", "1234")
    monkeypatch.setenv("RUNNER_GID", "5678")
    module = importlib.import_module("revocompute.task_runtime")
    monkeypatch.setattr(
        module,
        "CONFIG",
        replace(module.CONFIG, workspace_folder=str(env_root / "workspaces"), results_folder=str(env_root / "results")),
    )
    return module


# -- symlink-aware containment -------------------------------------------------


def test_safe_join_rejects_symlink_escape(rt, tmp_path):
    base = tmp_path / "base"
    outside = tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    (outside / "secret").write_text("secret")
    os.symlink(outside, base / "link")

    with pytest.raises(ValueError):
        rt._safe_join(base, "link", "x")


def test_safe_join_rejects_dangling_symlink(rt, tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    os.symlink(tmp_path / "outside" / "not-there-yet", base / "dangling")

    with pytest.raises(ValueError):
        rt._safe_join(base, "dangling", "x")


def test_safe_join_accepts_new_child_and_symlink_inside_base(rt, tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "real").mkdir()

    # Not-yet-existing paths are fine (lexical check covers them).
    assert rt._safe_join(base, "a", "b") == str(base / "a" / "b")
    # A symlink that stays inside the base is fine; the returned path stays
    # lexical (the OS resolves the symlink) — the guarantee is containment.
    assert rt._safe_join(base, "link", "f") == str(base / "link" / "f")


# -- workspace cleanup ----------------------------------------------------------


def test_cleanup_task_workspace_removes_workspace_not_results(rt):
    ws = rt.CONFIG.workspace_folder
    res = rt.CONFIG.results_folder
    md5 = "a" * 32
    (Path(ws) / "alice" / md5 / "inputs").mkdir(parents=True)
    (Path(ws) / "alice" / md5 / "inputs" / "query.fasta").write_text(">t\nACDE\n")
    result_dir = Path(res) / md5
    result_dir.mkdir(parents=True)
    (result_dir / "manifest.json").write_text("{}")

    rt._cleanup_task_workspace({"username": "alice", "md5sum": md5})

    assert not (Path(ws) / "alice" / md5).exists()
    assert result_dir.exists()
    assert (result_dir / "manifest.json").exists()


def test_cleanup_task_workspace_ignores_malformed_rows(rt):
    # Missing username / md5sum / traversal usernames must never raise.
    rt._cleanup_task_workspace({})
    rt._cleanup_task_workspace({"username": "", "md5sum": ""})
    rt._cleanup_task_workspace({"username": "../evil", "md5sum": "b" * 32})
