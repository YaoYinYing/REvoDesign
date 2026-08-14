# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""SQLite store for runtime admin configuration.

Three tables:

  task_type_config
    tool                 TEXT PRIMARY KEY
    enabled              INTEGER DEFAULT 1
    cpus                 INTEGER
    memory               TEXT
    max_runtime_seconds  INTEGER
    slurm_partition      TEXT
    slurm_gres           TEXT
    slurm_time           TEXT
    slurm_nodes          INTEGER
    slurm_ntasks         INTEGER
    slurm_qos            TEXT
    slurm_account        TEXT
    slurm_constraint     TEXT
    slurm_exclusive      INTEGER

  resource_config
    key        TEXT PRIMARY KEY
    value      TEXT NOT NULL
    updated_at REAL NOT NULL

Per-task canonical fields override global canonical defaults. Use
``resolve_task_resources`` for job launch.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time

from revocompute.resource_policy import (
    CANONICAL_TASK_FIELDS,
    GLOBAL_RESOURCE_KEYS,
    ResolvedResources,
    normalize_resource_value,
    resolve_resources,
)

_ALL_TASK_TYPE_FIELDS = CANONICAL_TASK_FIELDS


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
            "  tool                 TEXT PRIMARY KEY,"
            "  enabled              INTEGER NOT NULL DEFAULT 1,"
            "  cpus                 INTEGER,"
            "  memory               TEXT,"
            "  max_runtime_seconds  INTEGER,"
            "  slurm_partition      TEXT,"
            "  slurm_gres           TEXT,"
            "  slurm_time           TEXT,"
            "  slurm_nodes          INTEGER,"
            "  slurm_ntasks         INTEGER,"
            "  slurm_qos            TEXT,"
            "  slurm_account        TEXT,"
            "  slurm_constraint     TEXT,"
            "  slurm_exclusive      INTEGER"
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
        self._migrate_columns()

    def _migrate_columns(self) -> None:
        """Add resource columns if they don't exist yet (idempotent)."""
        for field in _ALL_TASK_TYPE_FIELDS:
            col_type = (
                "INTEGER"
                if field
                in (
                    "enabled",
                    "cpus",
                    "max_runtime_seconds",
                    "slurm_nodes",
                    "slurm_ntasks",
                    "slurm_exclusive",
                )
                else "TEXT"
            )
            with self._lock:
                existing = {row[1] for row in self._conn.execute("PRAGMA table_info(task_type_config)")}
                if field not in existing:
                    try:
                        self._conn.execute(f"ALTER TABLE task_type_config ADD COLUMN {field} {col_type}")
                        self._conn.commit()
                    except sqlite3.OperationalError as exc:
                        # Web, worker, and maintenance may start together. A
                        # sibling process can win this idempotent migration
                        # between our PRAGMA check and ALTER statement.
                        if "duplicate column name" not in str(exc).lower():
                            raise

    # -- task_type_config --------------------------------------------------

    def task_type_all(self) -> list[dict]:
        """Return all task type config rows."""
        cols = ("tool",) + _ALL_TASK_TYPE_FIELDS
        with self._lock:
            rows = self._conn.execute(  # skipcq: BAN-B608 — cols are module-level field constants, values bound below
                f"SELECT {', '.join(cols)} FROM task_type_config ORDER BY tool"
            ).fetchall()
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
            # BAN-B608: cols are module-level field constants; the value is bound via ?
            row = self._conn.execute(
                f"SELECT {', '.join(cols)} FROM task_type_config WHERE tool = ?",  # skipcq: BAN-B608
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
        updates = {key: normalize_resource_value(key, value) for key, value in fields.items() if key in allowed}
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
            # BAN-B608: keys are allowlisted against _ALL_TASK_TYPE_FIELDS; values bound via ?
            self._conn.execute(
                f"INSERT INTO task_type_config (tool, {columns}) "  # skipcq: BAN-B608
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

    def task_type_value(self, tool: str, field: str) -> str | None:
        """Return only a per-task value, without falling back globally."""
        row = self.task_type_get(tool)
        if row is None or row.get(field) is None:
            return None
        value = row[field]
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    # -- resource_config (key-value) ---------------------------------------

    def resource_all(self) -> dict[str, str]:
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM resource_config ORDER BY key").fetchall()
            return {r[0]: r[1] for r in rows}

    def resource_get(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM resource_config WHERE key = ?", (key,)).fetchone()
            return row[0] if row else default

    def resource_set(self, key: str, value: object) -> None:
        if key not in GLOBAL_RESOURCE_KEYS:
            raise ValueError(f"Unknown global resource key: {key}")
        normalized = normalize_resource_value(key, value)
        if normalized is None:
            self.resource_delete(key)
            return
        if isinstance(normalized, bool):
            serialized = "true" if normalized else "false"
        elif isinstance(normalized, tuple):
            serialized = ",".join(normalized)
        else:
            serialized = str(normalized)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO resource_config (key, value, updated_at) " "VALUES (?, ?, ?)",
                (key, serialized, time.time()),
            )
            self._conn.commit()

    def resource_delete(self, key: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM resource_config WHERE key = ?", (key,))
            self._conn.commit()

    def apply_resource_updates(
        self,
        task_updates: list[tuple[str, dict]],
        resource_updates: list[tuple[str, object]],
    ) -> int:
        """Apply an already-validated admin update in one transaction."""
        with self._lock:
            try:
                for tool, raw_fields in task_updates:
                    updates = {
                        key: normalize_resource_value(key, value)
                        for key, value in raw_fields.items()
                        if key in _ALL_TASK_TYPE_FIELDS
                    }
                    for bool_field in ("enabled", "slurm_exclusive"):
                        if bool_field in updates and isinstance(updates[bool_field], bool):
                            updates[bool_field] = 1 if updates[bool_field] else 0
                    if not updates:
                        continue
                    columns = ", ".join(updates)
                    placeholders = ", ".join("?" for _ in updates)
                    # BAN-B608: keys are allowlisted against _ALL_TASK_TYPE_FIELDS; values bound via ?
                    self._conn.execute(
                        f"INSERT INTO task_type_config (tool, {columns}) "  # skipcq: BAN-B608
                        f"VALUES (?, {placeholders}) "
                        f"ON CONFLICT(tool) DO UPDATE SET "
                        + ", ".join(f"{column}=excluded.{column}" for column in updates),
                        [tool, *updates.values()],
                    )
                for key, raw_value in resource_updates:
                    if key not in GLOBAL_RESOURCE_KEYS:
                        raise ValueError(f"Unknown global resource key: {key}")
                    value = normalize_resource_value(key, raw_value)
                    if value is None:
                        self._conn.execute("DELETE FROM resource_config WHERE key = ?", (key,))
                        continue
                    if isinstance(value, bool):
                        serialized = "true" if value else "false"
                    elif isinstance(value, tuple):
                        serialized = ",".join(value)
                    else:
                        serialized = str(value)
                    self._conn.execute(
                        "INSERT OR REPLACE INTO resource_config (key, value, updated_at) VALUES (?, ?, ?)",
                        (key, serialized, time.time()),
                    )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return len(task_updates) + len(resource_updates)

    # -- SLURM helpers -----------------------------------------------------

    def slurm_enabled(self) -> bool:
        """Whether the SLURM runner feature is globally enabled."""
        return self.resource_get("slurm_enabled", "false").lower() in ("true", "1", "yes", "on")

    def slurm_allowed_queues(self) -> list[str]:
        """Return the whitelist of allowed SLURM queues/partitions."""
        raw = self.resource_get("slurm_allowed_queues", "")
        return [q.strip() for q in raw.split(",") if q.strip()]

    def resolve_task_resources(
        self,
        tool: str,
        *,
        requires_gpu: bool,
        default_timeout_seconds: int | None,
    ) -> ResolvedResources:
        """Return the canonical end-to-end resource policy for one task."""
        return resolve_resources(
            lambda field: self.task_type_value(tool, field),
            lambda field: self.resource_get(field),
            requires_gpu=requires_gpu,
            allowed_queues=self.slurm_allowed_queues(),
            default_timeout_seconds=default_timeout_seconds,
        )

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._conn.close()
