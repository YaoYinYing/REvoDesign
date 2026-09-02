# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Fresh-schema bootstrap and fail-fast Project Scope epoch coverage."""

from __future__ import annotations

import sqlite3

import pytest
from revocompute.auth import UserDatabase
from revocompute.collaboration import CollaborationDatabase
from revocompute.db import TaskDatabase


def test_fresh_empty_and_current_databases_boot_and_reopen(tmp_path):
    user_path = tmp_path / "users.sqlite3"
    task_path = tmp_path / "tasks.sqlite3"
    collaboration_path = tmp_path / "collaboration.sqlite3"
    user_path.touch()
    task_path.touch()
    collaboration_path.touch()

    users = UserDatabase(str(user_path))
    user = users.create_user("alice", "alice@example.test", "password")
    tasks = TaskDatabase(str(task_path))
    collaboration = CollaborationDatabase(str(collaboration_path))
    project = collaboration.create_project(user["id"], "Science")
    for database in (users, tasks, collaboration):
        database.engine.dispose()

    reopened_users = UserDatabase(str(user_path))
    reopened_tasks = TaskDatabase(str(task_path))
    reopened_collaboration = CollaborationDatabase(str(collaboration_path))
    assert reopened_users.get_user(user["id"])["storage_key"] == user["storage_key"]
    assert reopened_tasks.list_tasks() == []
    assert reopened_collaboration.get_project(project["id"])["storage_key"] == project["storage_key"]


def test_old_task_schema_fails_clearly_without_altering_columns(tmp_path):
    path = tmp_path / "tasks.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE tasks (md5sum VARCHAR(32) PRIMARY KEY, filename VARCHAR NOT NULL, "
        "scope_type VARCHAR NOT NULL, scope_id VARCHAR NOT NULL, storage_key VARCHAR NOT NULL, "
        "artifact_provenance TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO tasks VALUES ('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'old.fasta', 'personal', '1', "
                 "'old-abcdef', '[]')")
    conn.commit()
    original_columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    conn.close()

    with pytest.raises(RuntimeError, match="Incompatible task database.*submitted_by_user_id"):
        TaskDatabase(str(path))

    conn = sqlite3.connect(path)
    assert {row[1] for row in conn.execute("PRAGMA table_info(tasks)")} == original_columns
    assert conn.execute("SELECT filename FROM tasks").fetchone() == ("old.fasta",)
    conn.close()


def test_partial_collaboration_schema_fails_clearly_without_bootstrapping_missing_tables(tmp_path):
    path = tmp_path / "collaboration.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)")
    conn.execute("INSERT INTO projects (name) VALUES ('Old Project')")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="Incompatible collaboration database"):
        CollaborationDatabase(str(path))

    conn = sqlite3.connect(path)
    assert {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} == {"projects"}
    assert conn.execute("SELECT name FROM projects").fetchone() == ("Old Project",)
    conn.close()
