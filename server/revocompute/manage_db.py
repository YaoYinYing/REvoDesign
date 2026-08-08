# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""SQLite store for runtime admin configuration.

Three tables:

  task_type_config
    tool     TEXT PRIMARY KEY
    enabled  INTEGER DEFAULT 1
    nproc    INTEGER
    maxmem   INTEGER
    max_runtime_seconds INTEGER
    slurm_partition      TEXT
    slurm_cpus_per_task  INTEGER
    slurm_gres           TEXT
    slurm_mem            TEXT
    slurm_time           TEXT
    slurm_nodes          INTEGER
    slurm_ntasks         INTEGER
    slurm_qos            TEXT
    slurm_account        TEXT
    slurm_constraint     TEXT
    slurm_exclusive      INTEGER

  resource_config
    key      TEXT PRIMARY KEY
    value    TEXT NOT NULL
    updated_at REAL NOT NULL

Per-task-type fields override global resource_config keys of the same name.
Use ``task_type_resolve(tool, field)`` for the resolution chain.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time

# Fields in task_type_config that can override global resource_config keys
_SLURM_FIELDS = (
    "slurm_partition",
    "slurm_cpus_per_task",
    "slurm_gres",
    "slurm_mem",
    "slurm_time",
    "slurm_nodes",
    "slurm_ntasks",
    "slurm_qos",
    "slurm_account",
    "slurm_constraint",
    "slurm_exclusive",
)

_ALL_TASK_TYPE_FIELDS = (
    "enabled",
    "nproc",
    "maxmem",
    "max_runtime_seconds",
) + _SLURM_FIELDS


class ManageDatabase:
    """Thread-safe admin config backed by SQLite (WAL mode)."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS task_type_config ("
            "  tool    TEXT PRIMARY KEY,"
            "  enabled INTEGER NOT NULL DEFAULT 1,"
            "  nproc   INTEGER,"
            "  maxmem  INTEGER,"
            "  max_runtime_seconds INTEGER,"
            "  slurm_partition     TEXT,"
            "  slurm_cpus_per_task INTEGER,"
            "  slurm_gres          TEXT,"
            "  slurm_mem           TEXT,"
            "  slurm_time          TEXT,"
            "  slurm_nodes         INTEGER,"
            "  slurm_ntasks        INTEGER,"
            "  slurm_qos           TEXT,"
            "  slurm_account       TEXT,"
            "  slurm_constraint    TEXT,"
            "  slurm_exclusive     INTEGER"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS resource_config ("
            "  key        TEXT PRIMARY KEY,"
            "  value      TEXT NOT NULL,"
            "  updated_at REAL NOT NULL"
            ")"
        )
        self._conn.commit()
        # ponytail: migrate pre-SLURM task_type_config tables in-place
        self._migrate_columns()

    def _migrate_columns(self) -> None:
        """Add SLURM columns if they don't exist yet (idempotent)."""
        existing = {row[1] for row in self._conn.execute("PRAGMA table_info(task_type_config)")}
        for field in _SLURM_FIELDS:
            if field not in existing:
                col_type = (
                    "INTEGER"
                    if field
                    in (
                        "slurm_cpus_per_task",
                        "slurm_nodes",
                        "slurm_ntasks",
                        "slurm_exclusive",
                    )
                    else "TEXT"
                )
                with self._lock:
                    self._conn.execute(f"ALTER TABLE task_type_config ADD COLUMN {field} {col_type}")
                    self._conn.commit()

    # -- task_type_config --------------------------------------------------

    def task_type_all(self) -> list[dict]:
        """Return all task type config rows."""
        cols = ("tool",) + _ALL_TASK_TYPE_FIELDS
        with self._lock:
            rows = self._conn.execute(f"SELECT {', '.join(cols)} FROM task_type_config ORDER BY tool").fetchall()
            result: list[dict] = []
            for r in rows:
                row = {"tool": r[0]}
                for i, field in enumerate(_ALL_TASK_TYPE_FIELDS, 1):
                    val = r[i]
                    if field in ("enabled", "slurm_exclusive"):
                        row[field] = bool(val) if val is not None else None
                    else:
                        row[field] = val
                result.append(row)
            return result

    def task_type_get(self, tool: str) -> dict | None:
        """Return one task type config row, or None."""
        cols = ("tool",) + _ALL_TASK_TYPE_FIELDS
        with self._lock:
            row = self._conn.execute(
                f"SELECT {', '.join(cols)} FROM task_type_config WHERE tool = ?",
                (tool,),
            ).fetchone()
            if row is None:
                return None
            result = {"tool": row[0]}
            for i, field in enumerate(_ALL_TASK_TYPE_FIELDS, 1):
                val = row[i]
                if field in ("enabled", "slurm_exclusive"):
                    result[field] = bool(val) if val is not None else None
                else:
                    result[field] = val
            return result

    def task_type_upsert(self, tool: str, **fields) -> None:
        """Insert or update one task type config row."""
        allowed = set(_ALL_TASK_TYPE_FIELDS)
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        # Convert bool → int for boolean columns
        for bool_field in ("enabled", "slurm_exclusive"):
            if bool_field in updates and isinstance(updates[bool_field], bool):
                updates[bool_field] = 1 if updates[bool_field] else 0

        columns = ", ".join(updates.keys())
        placeholders = ", ".join("?" for _ in updates)
        values = list(updates.values())

        with self._lock:
            self._conn.execute(
                f"INSERT INTO task_type_config (tool, {columns}) "
                f"VALUES (?, {placeholders}) "
                f"ON CONFLICT(tool) DO UPDATE SET " + ", ".join(f"{c}=excluded.{c}" for c in updates),
                [tool] + values,
            )
            self._conn.commit()

    def task_type_is_enabled(self, tool: str) -> bool | None:
        """Return True/False if an explicit toggle exists, None if not configured."""
        row = self.task_type_get(tool)
        if row is None:
            return None
        return row["enabled"]

    def task_type_resolve(self, tool: str, field: str) -> str | None:
        """Resolve a setting: per-task-type → global resource → None.

        For boolean fields (enabled, slurm_exclusive), returns "true"/"false".
        For all others, returns the raw value or None.
        """
        row = self.task_type_get(tool)
        if row is not None:
            val = row.get(field)
            if val is not None:
                if isinstance(val, bool):
                    return "true" if val else "false"
                return str(val)
        # Fall back to resource_config
        return self.resource_get(field)

    # -- resource_config (key-value) ---------------------------------------

    def resource_all(self) -> dict[str, str]:
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM resource_config ORDER BY key").fetchall()
            return {r[0]: r[1] for r in rows}

    def resource_get(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM resource_config WHERE key = ?", (key,)).fetchone()
            return row[0] if row else default

    def resource_set(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO resource_config (key, value, updated_at) " "VALUES (?, ?, ?)",
                (key, value, time.time()),
            )
            self._conn.commit()

    # -- legacy compat: the old key-value API mapped to structured tables --

    def get(self, key: str, default: str | None = None) -> str | None:
        """Legacy get — resolves resource_config keys and task_type.<name>.<field>."""
        # task_type.<name>.enabled → task_type_config
        if key.startswith("task_type.") and key.endswith(".enabled"):
            tool = key[len("task_type.") : -len(".enabled")]
            val = self.task_type_is_enabled(tool)
            return "true" if val is True else ("false" if val is False else default)
        # task_type.<name>.<field> → task_type_config
        if key.startswith("task_type."):
            parts = key.split(".", 2)
            if len(parts) == 3:
                _, tool, field = parts
                row = self.task_type_get(tool)
                if row and field in row:
                    val = row[field]
                    return str(val) if val is not None else default
            return default
        return self.resource_get(key, default)

    # -- SLURM helpers -----------------------------------------------------

    def slurm_enabled(self) -> bool:
        """Whether the SLURM runner feature is globally enabled."""
        return self.resource_get("slurm_enabled", "false").lower() in ("true", "1", "yes", "on")

    def slurm_allowed_queues(self) -> list[str]:
        """Return the whitelist of allowed SLURM queues/partitions."""
        raw = self.resource_get("slurm_allowed_queues", "")
        return [q.strip() for q in raw.split(",") if q.strip()]

    def slurm_sbatch_args(self, tool: str | None = None) -> dict[str, str | int | None]:
        """Build the resolved sbatch argument dict for a task type (or global).

        Resolution: task_type_config → resource_config → None (omitted from sbatch).
        """
        args: dict[str, str | int | None] = {}
        for field in _SLURM_FIELDS:
            val = None
            if tool:
                val = self.task_type_resolve(tool, field)
            else:
                val = self.resource_get(field)
            if val is not None:
                # Convert back to proper types for integer fields
                if field in ("slurm_cpus_per_task", "slurm_nodes", "slurm_ntasks"):
                    try:
                        args[field] = int(val)
                    except (ValueError, TypeError):
                        pass
                elif field == "slurm_exclusive":
                    args[field] = val.lower() in ("true", "1", "yes", "on")
                else:
                    args[field] = val
        return args
