# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import REPO_DIR


def _run_restart_script(
    tmp_path,
    *arguments,
    uid="1000",
    gid="1000",
    admins="admin",
    omit_settings=(),
    fail_chmod=False,
    config_dir=None,
    build_proxy=None,
    seed_user_db=False,
):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True)
    docker_log = tmp_path / "docker.log"
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "${DOCKER_LOG}"\n'
        'if [[ "$*" == *" ps --status running --services"* ]]; then\n'
        '  printf "redis\\nweb\\ngateway\\nmaintenance\\nworker\\n"\n'
        "fi\n",
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
    # Model a host-mounted directory that the configured container uid can
    # traverse. Production may instead grant the same access with a POSIX ACL.
    auth_dir.chmod(0o777)
    results_dir = task_dir / "results"
    results_dir.mkdir()
    results_dir.chmod(0o777)
    if seed_user_db:
        import sqlite3

        from werkzeug.security import generate_password_hash

        with sqlite3.connect(auth_dir / "users.sqlite3") as conn:
            conn.execute(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT NOT NULL, token_version INTEGER DEFAULT 0)"
            )
            conn.execute(
                "INSERT INTO users (username, password_hash, token_version) VALUES (?, ?, ?)",
                (admins.split(",", 1)[0], generate_password_hash("old-password"), 0),
            )
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
    if config_dir is not None:
        settings["CONFIG_DIR"] = str(config_dir)
    if build_proxy is not None:
        settings["REVODESIGN_BUILD_PROXY"] = build_proxy
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


def _make_deployed_config(tmp_path, executor="docker", missing_sif=None):
    source_root = Path(REPO_DIR) / "server" / "config"
    config_dir = tmp_path / "deployed-config"
    shutil.copytree(source_root / "runners", config_dir / "runners")
    registry = yaml.safe_load((source_root / "task_types.yaml").read_text(encoding="utf-8"))
    registry["job_executor"] = executor
    registry["container_runtime"] = "apptainer" if executor == "slurm" else "docker"
    sif_dir = tmp_path / "sifs"
    sif_dir.mkdir()
    for name, runtime in registry["runtime_families"].items():
        sif_path = sif_dir / f"{name}.sif"
        runtime["slurm_image"] = str(sif_path)
        if executor == "slurm" and name != missing_sif:
            sif_path.touch()
    (config_dir / "task_types.yaml").write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    return config_dir


def test_restart_modes_choose_build_or_pull(tmp_path):
    dev_result, dev_commands = _run_restart_script(tmp_path / "dev", "restart")
    assert dev_result.returncode == 0, dev_result.stderr
    assert "Bootstrap admin credentials written to:" in dev_result.stdout
    assert "password:" not in dev_result.stdout
    assert any(
        "build --build-arg" in command and "revodesign-revocompute-runner" in command for command in dev_commands
    )
    assert any("build web worker" in command for command in dev_commands)
    assert not any(" pull " in command for command in dev_commands)
    assert any("up --no-build -d redis web gateway maintenance worker" in command for command in dev_commands)

    prod_result, prod_commands = _run_restart_script(tmp_path / "prod", "restart", "--mode=prod")
    assert prod_result.returncode == 0, prod_result.stderr
    assert not any(" build " in command for command in prod_commands)
    pull_index = next(i for i, command in enumerate(prod_commands) if " pull web gateway" in command)
    up_index = next(i for i, command in enumerate(prod_commands) if "up --no-build" in command)
    assert pull_index < up_index
    assert any(command == "pull revodesign-revocompute-runner" for command in prod_commands)


def test_proxy_build_redacts_url_and_uses_non_persisted_build_args(tmp_path):
    proxy_url = "http://test-user:test-password@proxy.invalid:8080"
    result, commands = _run_restart_script(tmp_path, "build", f"--use-proxy={proxy_url}")

    assert result.returncode == 0, result.stderr
    assert proxy_url not in result.stdout
    assert proxy_url not in result.stderr
    assert "credential redacted" in result.stdout
    build_commands = [command for command in commands if command.startswith("build ")]
    assert build_commands
    assert all("--build-arg HTTP_PROXY=" in command for command in build_commands)
    assert all("Dockerfile.proxy" not in command for command in build_commands)


def test_proxy_build_can_read_url_from_selected_env_file(tmp_path):
    proxy_url = "http://test-user:test-password@proxy.invalid:8080"
    result, commands = _run_restart_script(
        tmp_path,
        "build",
        "--use-proxy",
        build_proxy=proxy_url,
    )

    assert result.returncode == 0, result.stderr
    assert proxy_url not in result.stdout
    assert proxy_url not in result.stderr
    assert "credential redacted" in result.stdout
    assert any("--build-arg HTTP_PROXY=" in command for command in commands)


def test_proxy_build_requires_env_value_for_bare_flag(tmp_path):
    result, commands = _run_restart_script(tmp_path, "build", "--use-proxy")

    assert result.returncode != 0
    assert "requires REVODESIGN_BUILD_PROXY" in result.stderr
    assert not any(command.startswith("build ") for command in commands)


def test_prepared_restart_validates_before_down_without_build_or_pull(tmp_path):
    config_dir = _make_deployed_config(tmp_path, executor="slurm")
    result, commands = _run_restart_script(
        tmp_path / "deployment",
        "restart",
        "--mode=prepared",
        config_dir=config_dir,
    )

    assert result.returncode == 0, result.stderr
    down_index = next(i for i, command in enumerate(commands) if command.endswith(" down"))
    assert any("image inspect example/revodesign-server:latest" in command for command in commands[:down_index])
    assert any(" config --quiet" in command for command in commands[:down_index])
    assert not any(" build " in command or " pull " in command for command in commands)
    assert any("up --no-build -d redis web gateway maintenance worker" in command for command in commands)
    assert "All prepared deployment services are running." in result.stdout

    steps_source = (Path(REPO_DIR) / "server" / "run" / "revocompute_ctl" / "steps.py").read_text(encoding="utf-8")
    prepared = steps_source.split("def _prepared_preflight", 1)[1].split("\ndef ", 1)[0]
    assert prepared.index("ensure_docker_gid") < prepared.index("validate_compose_model")


def test_prepared_restart_rejects_missing_sif_before_down(tmp_path):
    config_dir = _make_deployed_config(tmp_path, executor="slurm", missing_sif="esm")
    result, commands = _run_restart_script(
        tmp_path / "deployment",
        "restart",
        "--mode=prepared",
        config_dir=config_dir,
    )

    assert result.returncode != 0
    assert "Missing SIF image" in result.stderr
    assert not any(command.endswith(" down") for command in commands)


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
    credential_line = next(
        line for line in result.stdout.splitlines() if line.startswith("Bootstrap admin credentials written to:")
    )
    credential_file = Path(credential_line.removeprefix("Bootstrap admin credentials written to: ").split(" ", 1)[0])
    assert credential_file.stat().st_mode & 0o777 == 0o600
    credentials = [line.split("\t", 1) for line in credential_file.read_text(encoding="utf-8").splitlines()]
    assert [username for username, _password in credentials] == ["admin", "group_admin"]
    passwords = [password for _username, password in credentials]
    assert len(set(passwords)) == 2
    assert all(len(password) == 32 for password in passwords)


def test_up_generates_bootstrap_password_for_empty_user_database(tmp_path):
    root = tmp_path / "up"
    result, commands = _run_restart_script(root, "up")

    assert result.returncode == 0, result.stderr
    assert "Bootstrap admin credentials written to:" in result.stdout
    assert "password:" not in result.stdout
    assert any("up -d redis web gateway maintenance worker" in command for command in commands)
    assert any('exec -T web sh -c test -w "$1" && test -x "$1"' in command for command in commands)
    assert any("exec -T gateway sh -c test -r /srv/results && test -x /srv/results" in command for command in commands)
    assert any("exec -T web python -c" in command and "BEGIN IMMEDIATE" in command for command in commands)
    assert (root / "tasks" / "results").is_dir()


def test_reset_passwd_rotates_hash_invalidates_tokens_and_writes_protected_credential(tmp_path):
    result, _commands = _run_restart_script(
        tmp_path / "reset-passwd",
        "reset-passwd",
        "admin",
        uid=str(os.getuid()),
        gid=str(os.getgid()),
        seed_user_db=True,
    )

    assert result.returncode == 0, result.stderr
    assert "password:" not in result.stdout
    credential_line = next(line for line in result.stdout.splitlines() if line.startswith("New credential written to:"))
    credential_file = Path(credential_line.removeprefix("New credential written to: ").split(" ", 1)[0])
    assert credential_file.stat().st_mode & 0o777 == 0o600
    username, password = credential_file.read_text(encoding="utf-8").strip().split("\t", 1)
    assert username == "admin"
    assert len(password) == 32

    import sqlite3

    from werkzeug.security import check_password_hash

    with sqlite3.connect(tmp_path / "reset-passwd" / "auth" / "users.sqlite3") as conn:
        password_hash, token_version = conn.execute(
            "SELECT password_hash, token_version FROM users WHERE username = ?", ("admin",)
        ).fetchone()
    assert check_password_hash(password_hash, password)
    assert token_version == 1
    backup_line = next(
        line for line in result.stdout.splitlines() if line.startswith("Auth database backup written to:")
    )
    backup_db = Path(backup_line.removeprefix("Auth database backup written to: ").split(" ", 1)[0])
    assert backup_db.is_file()
    assert backup_db.stat().st_mode & 0o777 == 0o600


def test_up_does_not_mutate_startup_storage_permissions(tmp_path):
    root = tmp_path / "no-permission-mutation"
    result, commands = _run_restart_script(root, "up", fail_chmod=True)

    assert result.returncode == 0, result.stderr
    assert "chmod" not in result.stderr
    assert "sudo" not in result.stderr
    assert any("up -d redis web gateway maintenance worker" in command for command in commands)

    storage_source = (Path(REPO_DIR) / "server" / "run" / "revocompute_ctl" / "storage.py").read_text(encoding="utf-8")
    startup_storage = storage_source.split("def prepare_auth_storage", 1)[1].split("def validate_result_storage", 1)[0]
    assert "chmod " not in startup_storage
    assert "chown " not in startup_storage
    assert "sudo " not in startup_storage


def test_up_accepts_runner_owned_writable_auth_db_when_host_chmod_fails(tmp_path):
    """Runner-owned SQLite files need access validation, not host chmod."""
    result, commands = _run_restart_script(
        tmp_path / "runner-owned-auth",
        "up",
        uid=str(os.getuid()),
        gid=str(os.getgid()),
        seed_user_db=True,
        fail_chmod=True,
    )

    assert result.returncode == 0, result.stderr
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


def test_restart_rejects_incomplete_external_runtime_config_before_shutdown(tmp_path):
    config_dir = tmp_path / "deployed-config"
    config_dir.mkdir()
    source = Path(REPO_DIR) / "server" / "config" / "task_types.yaml"
    (config_dir / "task_types.yaml").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result, commands = _run_restart_script(
        tmp_path / "deployment",
        "restart",
        config_dir=config_dir,
    )

    assert result.returncode != 0
    assert "Runtime runner directory is missing" in result.stderr
    assert not any(" down" in command or " pull " in command or " up " in command for command in commands)


def test_global_slurm_executor_selects_override_without_cli_backend_flag(tmp_path):
    config_dir = _make_deployed_config(tmp_path, executor="slurm")
    result, commands = _run_restart_script(tmp_path / "deployment", "up", config_dir=config_dir)

    assert result.returncode == 0, result.stderr
    slurm_override = str(Path(REPO_DIR) / "server" / "docker-compose.slurm.yml")
    assert any(
        slurm_override in command and "up -d redis web gateway maintenance worker" in command for command in commands
    )


def test_missing_global_slurm_family_image_is_rejected_before_shutdown(tmp_path):
    config_dir = _make_deployed_config(tmp_path, executor="slurm", missing_sif="esm")
    result, commands = _run_restart_script(
        tmp_path / "deployment",
        "restart",
        "--mode=prod",
        config_dir=config_dir,
    )

    assert result.returncode != 0
    assert "Missing SIF image" in result.stderr
    assert "esm.sif" in result.stderr
    assert not any(" down" in command or " pull " in command or " up " in command for command in commands)


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
            "CONFIG_DIR": str(server_dir / "config"),
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
    maintenance_env = compose.split("x-maintenance-env:", 1)[1].split("services:", 1)[0]
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
    # Executor-neutral base worker: the Docker socket lives only in
    # docker-compose.docker.yml (compose concatenates volume lists, so a
    # socket defined here could never be removed by the SLURM override).
    assert "/var/run/docker.sock" not in worker


def test_docker_executor_override_holds_socket_and_slurm_override_does_not():
    docker_override = (Path(REPO_DIR) / "server" / "docker-compose.docker.yml").read_text(encoding="utf-8")
    slurm_override = (Path(REPO_DIR) / "server" / "docker-compose.slurm.yml").read_text(encoding="utf-8")

    assert "/var/run/docker.sock:/var/run/docker.sock" in docker_override
    assert "DOCKER_GID" in docker_override
    assert "group_add" in docker_override
    assert "/var/run/docker.sock" not in slurm_override
    assert "REDIS_PASSWORD" in slurm_override
    assert "127.0.0.1:6380:6379" in slurm_override


def test_nginx_result_location_is_internal_and_read_only():
    config = (Path(REPO_DIR) / "server" / "docker" / "nginx" / "default.conf.template").read_text(encoding="utf-8")

    protected = config.split("location /_protected_results/", 1)[1]
    assert "internal;" in protected
    assert "alias /srv/results/;" in protected
    assert "disable_symlinks on;" in protected
    assert "sendfile on;" in protected
    assert "proxy_pass" not in protected
