# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Scheduled, transactionally consistent SQLite database snapshots."""

from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from revocompute.config import ComputeConfig, env_int, env_path, env_str
from revocompute.maintenance.model import PeriodicTask

_SNAPSHOT_PATTERN = re.compile(r"\d{8}T\d{6}\.\d{6}Z$")


def _backup_sqlite_database(source: Path, destination: Path) -> None:
    """Back up one SQLite database, including committed WAL contents."""
    if not source.is_file():
        raise FileNotFoundError(f"Database to back up does not exist: {source}")
    source_uri = f"{source.resolve().as_uri()}?mode=ro"
    with (
        sqlite3.connect(source_uri, uri=True, timeout=30) as source_conn,
        sqlite3.connect(destination, timeout=30) as destination_conn,
    ):
        source_conn.backup(destination_conn)
        result = destination_conn.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite backup integrity check failed for {destination}: {result!r}")
    destination.chmod(0o600)


def _database_sources() -> dict[str, Path]:
    config = ComputeConfig.from_env()
    user_db_default = os.path.join(config.server_dir, "users.sqlite3")
    return {
        "tasks": Path(config.db_path),
        "users": Path(env_path("USER_DB_PATH", user_db_default)),
    }


def prune_database_backups(backup_dir: Path, max_backups: int) -> list[Path]:
    """Remove oldest complete snapshot directories beyond *max_backups*."""
    if max_backups <= 0:
        raise ValueError("max_backups must be positive")
    snapshots = sorted(
        entry
        for entry in backup_dir.iterdir()
        if entry.is_dir() and not entry.is_symlink() and _SNAPSHOT_PATTERN.fullmatch(entry.name)
    )
    removed: list[Path] = []
    for snapshot in snapshots[:-max_backups]:
        shutil.rmtree(snapshot)
        removed.append(snapshot)
    return removed


def run_database_backup(
    backup_path: str,
    max_backups: int | None,
    *,
    now: datetime | None = None,
) -> Path:
    """Create one complete task/user database snapshot and apply retention."""
    backup_dir = Path(backup_path).expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    sources = _database_sources()
    missing = [str(source) for source in sources.values() if not source.is_file()]
    if missing:
        raise FileNotFoundError(f"Database backup aborted; missing source database(s): {', '.join(missing)}")

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    snapshot_name = current_time.strftime("%Y%m%dT%H%M%S.%fZ")
    snapshot = backup_dir / snapshot_name
    temporary = backup_dir / f".{snapshot_name}.tmp-{os.getpid()}"
    if snapshot.exists() or temporary.exists():
        raise FileExistsError(f"Database backup snapshot already exists: {snapshot}")

    try:
        temporary.mkdir(mode=0o700)
        for label, source in sources.items():
            _backup_sqlite_database(source, temporary / f"{label}.sqlite3")
        temporary.replace(snapshot)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    if max_backups is not None:
        removed = prune_database_backups(backup_dir, max_backups)
        if removed:
            logging.info("Removed %d old database backup snapshot(s)", len(removed))
    logging.info("Created database backup snapshot: %s", snapshot)
    return snapshot


class DatabaseBackupTask(PeriodicTask):
    """Cron-configured backup of the task and user SQLite databases."""

    id = "database-backup"

    @property
    def task_method(self) -> Callable[..., Any]:
        return run_database_backup

    def configure(self) -> None:
        cron_expression = env_str("BACKUP_DB_CRON", "").strip()
        backup_path_raw = env_str("BACKUP_DB_PATH", "").strip()
        max_backups_raw = env_str("MAX_DB_BACKUP", "").strip()
        self.env = {
            "BACKUP_DB_CRON": cron_expression,
            "BACKUP_DB_PATH": backup_path_raw,
            "MAX_DB_BACKUP": None,
        }
        self._is_enabled = False
        self._args = {}

        if not cron_expression:
            return
        if not backup_path_raw:
            raise ValueError("BACKUP_DB_PATH is required when BACKUP_DB_CRON is set")

        max_backups = env_int("MAX_DB_BACKUP", 0) if max_backups_raw else None
        self.env["MAX_DB_BACKUP"] = max_backups
        if max_backups is not None and max_backups <= 0:
            raise ValueError("MAX_DB_BACKUP must be a positive integer when set")

        trigger = CronTrigger.from_crontab(cron_expression, timezone=os.environ.get("TZ", "UTC"))
        backup_path = os.path.abspath(os.path.expanduser(backup_path_raw))
        self.env["BACKUP_DB_PATH"] = backup_path
        self._is_enabled = True
        self._args = {
            "trigger": trigger,
            "args": (backup_path, max_backups),
            "misfire_grace_time": 3600,
        }


database_backup_task = DatabaseBackupTask()
