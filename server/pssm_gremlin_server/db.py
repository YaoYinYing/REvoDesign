# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""SQLite task tracker for GREMLIN jobs."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    desc,
    func,
    select,
    update,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError


class TaskDatabase:
    """Minimal SQLite-based task tracker for GREMLIN jobs."""

    DELETED_STATUSES = {"deleted:finshed", "deleted:cancel"}
    TERMINAL_STATUSES = {"deleted:finshed", "deleted:cancel", "cancelled"}

    VALID_STATUSES = {
        "pending",
        "running",
        "packing results",
        "finished",
        "failed",
        "cancelled",
        "deleted:finshed",
        "deleted:cancel",
    }

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.path}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        self.metadata = MetaData()
        self.tasks_table = Table(
            "tasks",
            self.metadata,
            Column("md5sum", String(32), primary_key=True),
            Column("filename", String, nullable=False),
            Column("file_path", String, nullable=False),
            Column("result_dir", String, nullable=False),
            Column("uploaded_at", Float, nullable=False),
            Column("started_at", Float),
            Column("finished_at", Float),
            Column("walltime", Float),
            Column("status", String, nullable=False),
            Column("is_binary", Integer, nullable=False),
            Column("source_ip", String),
            Column("user_agent", String),
            Column("username", String),
            Column("local user", String, key="local_user"),
            Column("request_headers", Text),
            Column("run_stage", String),
            Column("error", Text),
            Column("celery_task_id", String),
        )
        Index("idx_tasks_uploaded_at", self.tasks_table.c.uploaded_at)
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as conn:
            self._safe_apply_pragmas(conn)
            try:
                self.metadata.create_all(conn, checkfirst=True)
            except OperationalError as exc:
                # Gunicorn can spawn multiple workers simultaneously which may try to
                # initialize the SQLite schema at the same time. The loser of that
                # race observes an "already exists" error; we can safely ignore it.
                if "already exists" not in str(exc).lower():
                    raise
                logging.warning("TaskDatabase metadata already present, skipping creation")
            self._ensure_columns(conn)

    @staticmethod
    def _safe_apply_pragmas(conn) -> None:
        # During dockerized server tests, concurrent web/worker startup can briefly
        # contend on the same SQLite file. Retrying PRAGMA setup avoids process
        # exit on transient lock without changing DB semantics.
        for attempt in range(3):
            try:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
                conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
                return
            except OperationalError as exc:
                if "database is locked" not in str(exc).lower():
                    raise
                if attempt == 2:
                    logging.warning(
                        "SQLite pragma initialization is locked; proceeding with default pragmas for this process."
                    )
                    return
                time.sleep(0.2 * (attempt + 1))

    @staticmethod
    def _ensure_columns(conn) -> None:
        existing_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(tasks);").fetchall()}
        if "local user" not in existing_columns:
            conn.exec_driver_sql('ALTER TABLE tasks ADD COLUMN "local user" TEXT;')
        if "request_headers" not in existing_columns:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN request_headers TEXT;")
        if "run_stage" not in existing_columns:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN run_stage TEXT;")

    @staticmethod
    def _normalize_task_row(row: dict) -> dict:
        normalized = dict(row)
        if "local user" in normalized and "local_user" not in normalized:
            normalized["local_user"] = normalized["local user"]
        return normalized

    def _ensure_status(self, status: str) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid GREMLIN task status {status}")

    @classmethod
    def _is_deleted_status(cls, status: Any) -> bool:
        return str(status or "").strip().lower() in cls.DELETED_STATUSES

    def upsert_task(self, md5sum: str, **fields) -> None:
        if not fields:
            return
        status = fields.get("status")
        if status:
            self._ensure_status(status)
        stmt = sqlite_insert(self.tasks_table).values(md5sum=md5sum, **fields)
        stmt = stmt.on_conflict_do_update(
            index_elements=[self.tasks_table.c.md5sum],
            set_={col: getattr(stmt.excluded, col) for col in fields},
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def update_task(self, md5sum: str, **fields) -> None:
        if not fields:
            return
        status = fields.get("status")
        if status:
            self._ensure_status(status)
        stmt = update(self.tasks_table).where(self.tasks_table.c.md5sum == md5sum).values(**fields)
        # Terminal tasks (deleted / cancelled) must stay terminal.
        # Ignore late worker writes (running/packing/finished/run_stage, etc.)
        # that would otherwise resurrect tasks after user deletion or
        # cancellation.
        if status is None or (not self._is_deleted_status(status)):
            stmt = stmt.where(self.tasks_table.c.status.notin_(tuple(self.TERMINAL_STATUSES)))
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def get_task(self, md5sum: str) -> dict | None:
        stmt = select(self.tasks_table).where(self.tasks_table.c.md5sum == md5sum)
        with self.engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return self._normalize_task_row(row) if row else None

    def list_tasks(self) -> list[dict]:
        stmt = select(self.tasks_table).order_by(desc(self.tasks_table.c.uploaded_at))
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [self._normalize_task_row(row) for row in rows]

    def count_user_active_tasks(self, username: str) -> int:
        """Count pending, running, and packing tasks for a user."""
        stmt = (
            select(func.count())
            .select_from(self.tasks_table)
            .where(
                self.tasks_table.c.username == username,
                self.tasks_table.c.status.in_(["pending", "running", "packing results"]),
            )
        )
        with self.engine.connect() as conn:
            return conn.execute(stmt).scalar() or 0

    def delete_task(self, md5sum: str) -> None:
        stmt = self.tasks_table.delete().where(self.tasks_table.c.md5sum == md5sum)
        with self.engine.begin() as conn:
            conn.execute(stmt)
