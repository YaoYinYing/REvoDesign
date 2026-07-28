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
        shutil.copy2(legacy_db, temporary)
        copied_count = _validate_database(temporary)
        if copied_count != legacy_count:
            raise RuntimeError(
                f"User count mismatch after copy: source={legacy_count}, destination={copied_count}"
            )
        os.replace(temporary, destination)
        shutil.move(str(legacy_db), rollback_backup)
    finally:
        temporary.unlink(missing_ok=True)

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
