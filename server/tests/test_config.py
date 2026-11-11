# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import pytest
from conftest import _load_pssm_module
from pssm_gremlin_server.config import env_choice, env_csv, env_float

# config tests
# ==================================================================


def test_env_float_accepts_fractional_values(monkeypatch):
    monkeypatch.setenv("RESULT_RETENTION_DAYS", "0.1")

    assert env_float("RESULT_RETENTION_DAYS", 0.0) == pytest.approx(0.1)


def test_env_float_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("RESULT_RETENTION_DAYS", raising=False)

    assert env_float("RESULT_RETENTION_DAYS", 2.5) == 2.5


@pytest.mark.parametrize("value", ["not-a-number", "nan", "inf", "-inf"])
def test_env_float_rejects_non_finite_or_invalid_values(monkeypatch, value):
    monkeypatch.setenv("RESULT_RETENTION_DAYS", value)

    with pytest.raises(ValueError, match="must be a finite number"):
        env_float("RESULT_RETENTION_DAYS", 0.0)


def test_env_csv_uses_default_when_explicitly_empty(monkeypatch):
    monkeypatch.setenv("ADMIN_USERS", "")

    assert env_csv("ADMIN_USERS", "admin") == ["admin"]


def test_env_choice_normalizes_allowed_value(monkeypatch):
    monkeypatch.setenv("RESULT_DOWNLOAD_MODE", " NGINX ")

    assert env_choice("RESULT_DOWNLOAD_MODE", "flask", {"flask", "nginx"}) == "nginx"


def test_env_choice_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("RESULT_DOWNLOAD_MODE", "object-storage")

    with pytest.raises(ValueError, match="must be one of: flask, nginx"):
        env_choice("RESULT_DOWNLOAD_MODE", "flask", {"flask", "nginx"})


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
    assert module.CONFIG.result_download_mode == "flask"


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


@pytest.mark.parametrize(
    "name",
    ["SERVER_DIR", "DB_UNIREF30", "DB_UNIREF90"],
)
def test_pssm_config_requires_deployment_settings_before_database_setup(monkeypatch, tmp_path, name):
    with pytest.raises(RuntimeError, match=f"Required environment variable {name} is not set"):
        _load_pssm_module(
            monkeypatch,
            tmp_path,
            extra_env={
                "RUNNER_UID": "1234",
                "RUNNER_GID": "5678",
                name: None,
            },
        )

    assert not (tmp_path / "pssm_env" / "users.sqlite3").exists()


def test_pssm_app_requires_admin_users_before_database_setup(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError, match="ADMIN_USERS is not set"):
        _load_pssm_module(
            monkeypatch,
            tmp_path,
            extra_env={
                "RUNNER_UID": "1234",
                "RUNNER_GID": "5678",
                "ADMIN_USERS": None,
            },
        )

    assert not (tmp_path / "pssm_env" / "users.sqlite3").exists()


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
