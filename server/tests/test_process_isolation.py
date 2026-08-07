# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_DIR


def _run_restart_script(
    tmp_path,
    *arguments,
    uid="1000",
    gid="1000",
    admins="admin",
    omit_settings=(),
    fail_chmod=False,
):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True)
    docker_log = tmp_path / "docker.log"
    docker = fake_bin / "docker"
    docker.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "${DOCKER_LOG}"\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    if fail_chmod:
        chmod = fake_bin / "chmod"
        chmod.write_text(
            '#!/usr/bin/env bash\necho "chmod: Operation not permitted" >&2\nexit 1\n',
            encoding="utf-8",
        )
        chmod.chmod(0o755)

    task_dir = tmp_path / "tasks"
    auth_dir = tmp_path / "auth"
    log_dir = tmp_path / "logs"
    for path in (task_dir, auth_dir, log_dir):
        path.mkdir(exist_ok=True)
    env_file = tmp_path / "server.env"
    settings = {
        "SERVER_DIR": str(task_dir),
        "AUTH_DIR": str(auth_dir),
        "LOG_DIR": str(log_dir),
        "ADMIN_USERS": admins,
        "RUNNER_UID": uid,
        "RUNNER_GID": gid,
        "RUNNER_USERNAME": "revodesign",
        "RUNNER_GROUP": "revodesign",
        "SERVER_IMAGE": "example/revodesign-server:latest",
    }
    env_file.write_text(
        "\n".join(f"{name}={value}" for name, value in settings.items() if name not in omit_settings),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "REVODESIGN_SERVER_ENV": str(env_file),
            "DOCKER_GID": "0",
            "DOCKER_LOG": str(docker_log),
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
        }
    )
    script = Path(REPO_DIR) / "server" / "run" / "restart.sh"
    result = subprocess.run(
        ["bash", str(script), *arguments],
        cwd=REPO_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    commands = docker_log.read_text(encoding="utf-8").splitlines()
    return result, commands


def test_restart_modes_choose_build_or_pull(tmp_path):
    dev_result, dev_commands = _run_restart_script(tmp_path / "dev", "restart")
    assert dev_result.returncode == 0, dev_result.stderr
    assert "Admin login — username: admin  password:" in dev_result.stdout
    assert any("--profile runner build runner" in command for command in dev_commands)
    assert any("build web worker" in command for command in dev_commands)
    assert not any(" pull " in command for command in dev_commands)
    assert any("up --no-build -d redis web gateway maintenance worker" in command for command in dev_commands)

    prod_result, prod_commands = _run_restart_script(tmp_path / "prod", "restart", "--mode=prod")
    assert prod_result.returncode == 0, prod_result.stderr
    assert not any(" build " in command for command in prod_commands)
    pull_index = next(i for i, command in enumerate(prod_commands) if " pull web gateway runner" in command)
    up_index = next(i for i, command in enumerate(prod_commands) if "up --no-build" in command)
    assert pull_index < up_index


def test_reload_sends_hup_through_compose(tmp_path):
    result, commands = _run_restart_script(tmp_path, "reload")

    assert result.returncode == 0, result.stderr
    assert any("exec web pkill -HUP gunicorn" in command for command in commands)


def test_restart_generates_distinct_password_for_each_configured_admin(tmp_path):
    result, _commands = _run_restart_script(
        tmp_path,
        "restart",
        admins="admin,group_admin",
    )

    assert result.returncode == 0, result.stderr
    login_lines = [line for line in result.stdout.splitlines() if line.startswith("Admin login — ")]
    assert [line.split()[4] for line in login_lines] == ["admin", "group_admin"]
    passwords = [line.rsplit("password: ", 1)[1] for line in login_lines]
    assert len(set(passwords)) == 2
    assert all(len(password) == 32 for password in passwords)


def test_up_generates_bootstrap_password_for_empty_user_database(tmp_path):
    root = tmp_path / "up"
    result, commands = _run_restart_script(root, "up")

    assert result.returncode == 0, result.stderr
    assert "Admin login — username: admin  password:" in result.stdout
    assert any("up -d redis web gateway maintenance worker" in command for command in commands)
    assert any('exec -T web sh -c test -w "$1" && test -x "$1"' in command for command in commands)
    assert any(
        "exec -T gateway sh -c test -r /srv/results && test -x /srv/results" in command for command in commands
    )
    assert (root / "tasks" / "results").is_dir()


def test_up_continues_after_chmod_failure_and_prints_manual_command(tmp_path):
    root = tmp_path / "chmod-failure"
    result, commands = _run_restart_script(root, "up", fail_chmod=True)

    assert result.returncode == 0, result.stderr
    assert "continuing with container access checks" in result.stderr
    assert "sudo chmod u+rwx,go+rx" in result.stderr
    assert f"{root}/tasks/results" in result.stderr
    assert any("up -d redis web gateway maintenance worker" in command for command in commands)


def test_up_rejects_duplicate_admin_usernames_before_start(tmp_path):
    result, commands = _run_restart_script(
        tmp_path,
        "up",
        admins="admin,admin",
    )

    assert result.returncode != 0
    assert "ADMIN_USERS must not contain duplicate usernames: admin" in result.stderr
    assert "Admin login" not in result.stdout
    assert not any("up -d redis web gateway maintenance worker" in command for command in commands)


def test_restart_mode_validation(tmp_path):
    identity_result, identity_commands = _run_restart_script(
        tmp_path / "identity",
        "restart",
        "--mode=prod",
        uid="1001",
    )
    assert identity_result.returncode != 0
    assert "Production images require RUNNER_UID=1000 and RUNNER_GID=1000" in identity_result.stderr
    assert not any(" down" in command or " pull " in command or " up " in command for command in identity_commands)

    spelling_result, _ = _run_restart_script(tmp_path / "spelling", "restart", "--mode", "prod")
    assert spelling_result.returncode != 0
    assert "Too many arguments" in spelling_result.stderr


@pytest.mark.parametrize(
    "name",
    ["SERVER_DIR", "ADMIN_USERS"],
)
def test_restart_rejects_missing_required_settings_before_shutdown(tmp_path, name):
    result, commands = _run_restart_script(
        tmp_path / name.lower(),
        "restart",
        omit_settings=(name,),
    )

    assert result.returncode != 0
    assert "Missing required setting(s)" in result.stderr
    assert name in result.stderr
    assert not any(
        " down" in command or " build " in command or " pull " in command or " up " in command for command in commands
    )


def test_worker_runtime_import_has_no_auth_or_flask_side_effects(tmp_path):
    server_dir = Path(REPO_DIR) / "server"
    task_dir = tmp_path / "tasks"
    user_db = tmp_path / "auth-must-not-exist" / "users.sqlite3"
    code = """
import os
import sys
from pathlib import Path

from revocompute import task_runtime

assert "revocompute.auth" not in sys.modules
assert "revocompute.routes" not in sys.modules
assert "revocompute.app" not in sys.modules
assert not Path(os.environ["USER_DB_PATH"]).exists()
assert task_runtime.run_compute_task.name == "run_compute_task"
assert task_runtime.task_store.path == os.path.abspath(os.environ["DB_PATH"])
"""
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(server_dir),
            "SERVER_DIR": str(task_dir),
            "DB_PATH": str(task_dir / "tasks.sqlite3"),
            "USER_DB_PATH": str(user_db),
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_NEW_USER_INFORM": "1",
            "ADMIN_NOTIFY_EMAIL": "admin@example.com",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not user_db.exists()


def test_compose_isolates_worker_auth_and_web_docker_socket():
    compose = (Path(REPO_DIR) / "server" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "AUTH_SECRET_KEY" not in compose
    task_env = compose.split("x-task-env:", 1)[1].split("x-web-auth-env:", 1)[0]
    web_auth_env = compose.split("x-web-auth-env:", 1)[1].split("x-maintenance-env:", 1)[0]
    maintenance_env = compose.split("x-maintenance-env:", 1)[1].split("x-docker-socket-access:", 1)[0]
    gateway = compose.split("  gateway:", 1)[1].split("  web:", 1)[0]
    web = compose.split("  web:", 1)[1].split("  maintenance:", 1)[0]
    maintenance = compose.split("  maintenance:", 1)[1].split("  worker:", 1)[0]
    worker = compose.split("  worker:", 1)[1].split("  runner:", 1)[0]

    for secret in ("USER_DB_PATH", "AUTH_SECRET_KEY", "SMTP_PASSWORD", "RESEND_API_KEY"):
        assert secret not in task_env
    assert "RUNNER_HOST_ROOT" in task_env
    assert "RESULT_RETENTION_DAYS" not in task_env
    assert "RESULT_RETENTION_DAYS" not in web_auth_env
    for rotation_setting in (
        "ROTATE_LOG_MAX_LINENO",
        "ROTATE_LOG_PERIOD",
        "MAX_LOG_SIZE",
    ):
        assert rotation_setting not in task_env
        assert rotation_setting not in web_auth_env
        assert rotation_setting in maintenance_env
    assert "PUBLIC_DASHBOARD" not in web_auth_env
    assert "RESULT_DOWNLOAD_MODE" in web_auth_env
    assert "RESULT_RETENTION_DAYS" in maintenance_env
    for backup_setting in ("BACKUP_DB_CRON", "BACKUP_DB_PATH", "MAX_DB_BACKUP"):
        assert backup_setting in maintenance_env
    assert "web-auth-env" in web
    assert "/var/lib/revodesign-auth" in web
    assert "/var/run/docker.sock" not in web
    assert "ports:" not in web
    assert "expose:" in web
    assert "ports:" in gateway
    assert "${SERVER_DIR}/results:/srv/results:ro" in gateway
    assert "/var/lib/revodesign-auth" not in gateway
    assert "user: ${RUNNER_UID}:${RUNNER_GID}" in gateway
    assert "read_only: true" in gateway
    assert "/tmp:size=16m,mode=1777" in gateway
    assert "maintenance-env" in maintenance
    assert "/var/lib/revodesign-auth" in maintenance
    assert "/var/run/docker.sock" not in maintenance
    assert "ports:" not in maintenance
    assert "revocompute.maintenance.manager" in maintenance
    assert "web-auth-env" not in worker
    assert "/var/lib/revodesign-auth" not in worker
    assert "revocompute.task_runtime.celery" in worker
    assert "/var/run/docker.sock:/var/run/docker.sock" in worker


def test_nginx_result_location_is_internal_and_read_only():
    config = (Path(REPO_DIR) / "server" / "docker" / "nginx" / "default.conf.template").read_text(encoding="utf-8")

    protected = config.split("location /_protected_results/", 1)[1]
    assert "internal;" in protected
    assert "alias /srv/results/;" in protected
    assert "disable_symlinks on;" in protected
    assert "sendfile on;" in protected
    assert "proxy_pass" not in protected
