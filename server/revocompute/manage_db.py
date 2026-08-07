# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Key-value SQLite store for runtime admin configuration.

Schema: ``config (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at REAL)``
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time


class ManageDatabase:
    """Thread-safe key-value store backed by SQLite (WAL mode)."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS config ("
            "  key    TEXT PRIMARY KEY,"
            "  value  TEXT NOT NULL,"
            "  updated_at REAL NOT NULL"
            ")"
        )
        self._conn.commit()

    def get(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, time.time()),
            )
            self._conn.commit()

    def delete(self, key: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM config WHERE key = ?", (key,))
            self._conn.commit()
            return cur.rowcount > 0

    def all(self) -> dict[str, str]:
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM config ORDER BY key").fetchall()
            return {row[0]: row[1] for row in rows}
