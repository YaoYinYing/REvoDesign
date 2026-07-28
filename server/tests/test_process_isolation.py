# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from conftest import REPO_DIR


def test_worker_runtime_import_has_no_auth_or_flask_side_effects(tmp_path):
    server_dir = Path(REPO_DIR) / "server"
    task_dir = tmp_path / "tasks"
    user_db = tmp_path / "auth-must-not-exist" / "users.sqlite3"
    code = """
import os
import sys
from pathlib import Path

from pssm_gremlin_server import task_runtime

assert "pssm_gremlin_server.auth" not in sys.modules
assert "pssm_gremlin_server.routes" not in sys.modules
assert "pssm_gremlin_server.pssm_gremlin" not in sys.modules
assert not Path(os.environ["USER_DB_PATH"]).exists()
assert task_runtime.run_gremlin_task.name == "run_gremlin_task"
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
    task_env = compose.split("x-task-env:", 1)[1].split("x-web-auth-env:", 1)[0]
    web = compose.split("  web:", 1)[1].split("  worker:", 1)[0]
    worker = compose.split("  worker:", 1)[1].split("  runner:", 1)[0]

    for secret in ("USER_DB_PATH", "AUTH_SECRET_KEY", "SMTP_PASSWORD", "RESEND_API_KEY"):
        assert secret not in task_env
    assert "web-auth-env" in web
    assert "/var/lib/revodesign-auth" in web
    assert "/var/run/docker.sock" not in web
    assert "web-auth-env" not in worker
    assert "/var/lib/revodesign-auth" not in worker
    assert "pssm_gremlin_server.task_runtime.celery" in worker
    assert "/var/run/docker.sock:/var/run/docker.sock" in worker


def test_task_database_upgrade_tolerates_duplicate_column_race():
    from pssm_gremlin_server.db import TaskDatabase

    class RacingConnection:
        def exec_driver_sql(self, statement):
            raise sa.exc.OperationalError(
                statement,
                {},
                Exception("duplicate column name: run_stage"),
            )

    existing: set[str] = set()
    TaskDatabase._add_column_if_missing(RacingConnection(), existing, "run_stage", "TEXT")
    assert "run_stage" in existing


def test_task_database_upgrade_keeps_other_errors_fatal():
    from pssm_gremlin_server.db import TaskDatabase

    class FailingConnection:
        def exec_driver_sql(self, statement):
            raise sa.exc.OperationalError(statement, {}, Exception("database disk image is malformed"))

    with pytest.raises(sa.exc.OperationalError, match="database disk image is malformed"):
        TaskDatabase._add_column_if_missing(FailingConnection(), set(), "run_stage", "TEXT")


def test_auth_database_migration_is_verified_and_recoverable(tmp_path):
    from pssm_gremlin_server.migrate_auth_db import migrate_auth_database

    server_dir = tmp_path / "shared-task-data"
    auth_dir = tmp_path / "web-only-auth"
    server_dir.mkdir()
    legacy = server_dir / "users.sqlite3"
    with sqlite3.connect(legacy) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
        conn.executemany("INSERT INTO users (username) VALUES (?)", [("one",), ("two",)])

    result = migrate_auth_database(server_dir, auth_dir)

    assert result.user_count == 2
    assert result.destination == auth_dir / "users.sqlite3"
    assert result.destination.is_file()
    assert result.rollback_backup is not None and result.rollback_backup.is_file()
    assert not legacy.exists()
    assert migrate_auth_database(server_dir, auth_dir).already_migrated is True


def test_auth_database_migration_includes_uncheckpointed_wal(tmp_path):
    from pssm_gremlin_server.migrate_auth_db import migrate_auth_database

    server_dir = tmp_path / "shared-task-data"
    auth_dir = tmp_path / "web-only-auth"
    server_dir.mkdir()
    legacy = server_dir / "users.sqlite3"
    writer = """
import os
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA wal_autocheckpoint=0")
conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT)")
conn.execute("INSERT INTO users (username) VALUES ('wal-user')")
conn.commit()
os._exit(0)
"""
    result = subprocess.run(
        [sys.executable, "-c", writer, str(legacy)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert Path(f"{legacy}-wal").is_file()

    migration = migrate_auth_database(server_dir, auth_dir)

    assert migration.user_count == 1
    with sqlite3.connect(migration.destination) as conn:
        assert conn.execute("SELECT username FROM users").fetchall() == [("wal-user",)]
    assert migration.rollback_backup is not None
    with sqlite3.connect(migration.rollback_backup) as conn:
        assert conn.execute("SELECT username FROM users").fetchall() == [("wal-user",)]
    assert not legacy.exists()
    assert not Path(f"{legacy}-wal").exists()
    assert not Path(f"{legacy}-shm").exists()
    assert not list(auth_dir.glob("users.sqlite3.migrating.*"))


def test_auth_database_migration_rejects_shared_auth_directory(tmp_path):
    from pssm_gremlin_server.migrate_auth_db import migrate_auth_database

    server_dir = tmp_path / "shared"
    server_dir.mkdir()
    with pytest.raises(ValueError, match="outside SERVER_DIR"):
        migrate_auth_database(server_dir, server_dir / "auth")
