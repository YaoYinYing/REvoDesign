# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest
from revocompute.maintenance.tasks.database_backup import run_database_backup


def _open_wal_database(path, table, value):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"CREATE TABLE {table} (value TEXT)")
    conn.execute(f"INSERT INTO {table} VALUES (?)", (value,))
    conn.commit()
    return conn


def _configure_sources(monkeypatch, tmp_path):
    task_db = tmp_path / "tasks.sqlite3"
    user_db = tmp_path / "users.sqlite3"
    monkeypatch.setenv("SERVER_DIR", str(tmp_path))
    monkeypatch.setenv("DB_PATH", str(task_db))
    monkeypatch.setenv("USER_DB_PATH", str(user_db))
    monkeypatch.setenv("RUNNER_UID", "1234")
    monkeypatch.setenv("RUNNER_GID", "5678")
    return task_db, user_db


def test_database_backup_captures_wal_data_and_prunes_snapshot_sets(monkeypatch, tmp_path):
    task_db, user_db = _configure_sources(monkeypatch, tmp_path)
    task_conn = _open_wal_database(task_db, "tasks", "task-row")
    user_conn = _open_wal_database(user_db, "users", "user-row")
    backup_dir = tmp_path / "backups"

    try:
        snapshots = [
            run_database_backup(
                str(backup_dir),
                2,
                now=datetime(2026, 1, day, tzinfo=timezone.utc),
            )
            for day in (1, 2, 3)
        ]
    finally:
        task_conn.close()
        user_conn.close()

    assert not snapshots[0].exists()
    assert snapshots[1].is_dir()
    assert snapshots[2].is_dir()
    assert sorted(path.name for path in backup_dir.iterdir()) == [snapshots[1].name, snapshots[2].name]

    with sqlite3.connect(snapshots[2] / "tasks.sqlite3") as conn:
        assert conn.execute("SELECT value FROM tasks").fetchone() == ("task-row",)
        assert conn.execute("PRAGMA quick_check").fetchone() == ("ok",)
    with sqlite3.connect(snapshots[2] / "users.sqlite3") as conn:
        assert conn.execute("SELECT value FROM users").fetchone() == ("user-row",)
        assert conn.execute("PRAGMA quick_check").fetchone() == ("ok",)


def test_database_backup_keeps_all_snapshots_when_retention_is_unset(monkeypatch, tmp_path):
    task_db, user_db = _configure_sources(monkeypatch, tmp_path)
    with sqlite3.connect(task_db) as conn:
        conn.execute("CREATE TABLE tasks (value TEXT)")
    with sqlite3.connect(user_db) as conn:
        conn.execute("CREATE TABLE users (value TEXT)")
    backup_dir = tmp_path / "backups"

    for day in (1, 2, 3):
        run_database_backup(
            str(backup_dir),
            None,
            now=datetime(2026, 2, day, tzinfo=timezone.utc),
        )

    assert len(list(backup_dir.iterdir())) == 3


def test_database_backup_leaves_no_partial_snapshot_when_a_source_is_missing(monkeypatch, tmp_path):
    task_db, _user_db = _configure_sources(monkeypatch, tmp_path)
    with sqlite3.connect(task_db) as conn:
        conn.execute("CREATE TABLE tasks (value TEXT)")
    backup_dir = tmp_path / "backups"

    with pytest.raises(FileNotFoundError, match="missing source database"):
        run_database_backup(
            str(backup_dir),
            30,
            now=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

    assert list(backup_dir.iterdir()) == []
