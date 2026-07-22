# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import pytest
from conftest import _load_pssm_module

# config tests
# ==================================================================


def test_pssm_config_uses_numeric_runner_identity(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    assert module.CONFIG.docker_user == "1234:5678"


def test_pssm_config_uses_named_runner_identity(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_USERNAME": "revodesign",
            "RUNNER_GROUP": "revodesign_appgroup",
        },
    )
    assert module.CONFIG.docker_user == "revodesign:revodesign_appgroup"


def test_pssm_config_defaults_are_not_cluster_paths(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "SERVER_DIR": None,
            "DB_PATH": None,
            "DB_UNIREF30": None,
            "DB_UNIREF90": None,
            "RUNNER_HOST_ROOT": None,
        },
    )

    assert module.CONFIG.server_dir.endswith("pssm_gremlin_data")
    assert not module.CONFIG.server_dir.startswith("/mnt/")
    assert not module.CONFIG.uniref30_db.startswith("/mnt/")
    assert not module.CONFIG.uniref90_db.startswith("/mnt/")
    assert module._ROOT_MOUNT_DIRECTORY == str(module.Path(module.CONFIG.server_dir).parent)


def test_pssm_config_uses_runner_host_root_override(monkeypatch, tmp_path):
    host_root = tmp_path / "runner_host_root"
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "RUNNER_HOST_ROOT": str(host_root),
        },
    )

    assert module._ROOT_MOUNT_DIRECTORY == str(host_root)


def test_pssm_config_requires_runner_identity(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError):
        _load_pssm_module(monkeypatch, tmp_path)


def test_pssm_config_rejects_root_runner(monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        _load_pssm_module(
            monkeypatch,
            tmp_path,
            extra_env={
                "RUNNER_UID": "0",
                "RUNNER_GID": "0",
            },
        )
