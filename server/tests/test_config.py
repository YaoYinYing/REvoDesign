# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import pytest
from conftest import (
    _admin_client_auth,
    _extract_md5,
    _insert_pending_task,
    _load_pssm_module,
    _test_client_auth,
    _upsert_task_for_user,
)

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
