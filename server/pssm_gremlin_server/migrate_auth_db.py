# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Explicit migration of a legacy shared user DB into web-only storage."""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AuthMigrationResult:
    destination: Path
    rollback_backup: Path | None
    user_count: int
    already_migrated: bool = False


def _is_within(parent: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath([parent, candidate]) == str(parent)
    except ValueError:
        return False


def _validate_database(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        result = conn.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed for {path}: {result!r}")
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def _backup_database(source: Path, destination: Path) -> None:
    """Create a self-contained SQLite snapshot, including committed WAL data."""
    with sqlite3.connect(source) as source_conn, sqlite3.connect(destination) as destination_conn:
        source_conn.backup(destination_conn)
    shutil.copystat(source, destination)


def _remove_sqlite_files(database: Path) -> None:
    database.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        Path(f"{database}{suffix}").unlink(missing_ok=True)


def migrate_auth_database(server_dir: Path, auth_dir: Path) -> AuthMigrationResult:
    server_dir = server_dir.expanduser().resolve()
    auth_dir = auth_dir.expanduser().resolve()
    if _is_within(server_dir, auth_dir):
        raise ValueError("AUTH_DIR must be outside SERVER_DIR")

    legacy_db = server_dir / "users.sqlite3"
    destination = auth_dir / "users.sqlite3"
    if destination.exists():
        if not legacy_db.exists():
            return AuthMigrationResult(
                destination=destination,
                rollback_backup=None,
                user_count=_validate_database(destination),
                already_migrated=True,
            )
        raise FileExistsError(f"Refusing to overwrite existing auth database: {destination}")
    if not legacy_db.is_file():
        raise FileNotFoundError(f"Legacy user database not found: {legacy_db}")

    auth_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    temporary = auth_dir / f"users.sqlite3.migrating.{stamp}"
    rollback_backup = auth_dir / f"users.sqlite3.pre-isolation.{stamp}.bak"
    legacy_count = _validate_database(legacy_db)
    try:
        # A filesystem copy of only users.sqlite3 is incomplete when committed
        # schema/data still lives in users.sqlite3-wal. SQLite's backup API
        # produces one consistent, standalone database from both files.
        _backup_database(legacy_db, temporary)
        copied_count = _validate_database(temporary)
        if copied_count != legacy_count:
            raise RuntimeError(f"User count mismatch after copy: source={legacy_count}, destination={copied_count}")
        shutil.copy2(temporary, rollback_backup)
        os.replace(temporary, destination)
        _remove_sqlite_files(legacy_db)
    finally:
        _remove_sqlite_files(temporary)

    return AuthMigrationResult(
        destination=destination,
        rollback_backup=rollback_backup,
        user_count=legacy_count,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-dir", required=True, type=Path)
    parser.add_argument("--auth-dir", required=True, type=Path)
    args = parser.parse_args()
    result = migrate_auth_database(args.server_dir, args.auth_dir)
    if result.already_migrated:
        print(f"Auth database is already isolated at {result.destination}.")
    else:
        print(f"Migrated {result.user_count} users to {result.destination}.")
        print(f"Rollback copy: {result.rollback_backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
