# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Admin bootstrap credentials and reset-passwd.

Credentials are generated on the host and handed to the web container
through the environment; plaintext passwords are never printed.
"""

from __future__ import annotations

import datetime
import os
import secrets
import sqlite3
import sys
import tempfile
from pathlib import Path

from revocompute_ctl.storage import prepare_auth_storage, resolve_runner_identity
from werkzeug.security import generate_password_hash


def _needs_admin_bootstrap(user_db: str) -> bool:
    path = Path(user_db)
    if not path.is_file():
        return True
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            has_users = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone()
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] if has_users else 0
        return count == 0
    except sqlite3.Error:
        return False


def prepare_admin_bootstrap(state) -> None:
    """Generate ADMIN_BOOTSTRAP_CREDENTIALS for the configured admins when the
    user database has no users yet."""
    if state.get("ADMIN_BOOTSTRAP_CREDENTIALS"):
        return
    auth_dir = state.get("AUTH_DIR") or os.path.join(state.server_root(), "auth-data")
    user_db = os.path.join(auth_dir, "users.sqlite3")
    if not _needs_admin_bootstrap(user_db):
        return

    credentials: list[str] = []
    seen: list[str] = []
    for admin_username in state.get_csv("ADMIN_USERS"):
        admin_username = admin_username.strip()
        if not admin_username:
            continue
        if admin_username in seen:
            print(f"ADMIN_USERS must not contain duplicate usernames: {admin_username}", file=sys.stderr)
            raise SystemExit(1)
        seen.append(admin_username)
        admin_pw = secrets.token_hex(16)
        credentials.append(f"{admin_username}\t{admin_pw}\n")
    if not credentials:
        print("ADMIN_USERS must contain at least one username.", file=sys.stderr)
        raise SystemExit(1)
    state.runtime["ADMIN_BOOTSTRAP_CREDENTIALS"] = "".join(credentials)


def print_admin_logins(state) -> None:
    """Persist generated bootstrap credentials to a 0600 file in AUTH_DIR and
    clear them from the environment."""
    credentials = state.get("ADMIN_BOOTSTRAP_CREDENTIALS")
    if not credentials:
        return
    auth_dir = state.get("AUTH_DIR") or os.path.join(state.server_root(), "auth-data")
    os.makedirs(auth_dir, exist_ok=True)
    handle, credential_file = tempfile.mkstemp(dir=auth_dir, prefix="bootstrap-admin-credentials.")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(credentials)
    os.chmod(credential_file, 0o600)
    print(f"Bootstrap admin credentials written to: {credential_file} (mode 0600)")
    state.runtime.pop("ADMIN_BOOTSTRAP_CREDENTIALS", None)


def cmd_reset_passwd(state, username: str) -> None:
    """Rotate one user's password hash, invalidate tokens, back up the auth
    database, and write the new credential to a 0600 file."""
    if not state.get("AUTH_DIR") or not state.server_dir():
        print(f"AUTH_DIR and SERVER_DIR must be set in {state.env_file}.", file=sys.stderr)
        raise SystemExit(1)
    if not username.isprintable() or len(username) > 128:
        print("Username must contain printable characters and be at most 128 characters.", file=sys.stderr)
        raise SystemExit(1)

    user_db = os.path.join(state.get("AUTH_DIR"), "users.sqlite3")
    if not os.path.isfile(user_db):
        print(f"User database is missing: {user_db}", file=sys.stderr)
        raise SystemExit(1)

    stamp = datetime.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    backup_dir = os.path.join(state.server_dir(), "backups", f"auth-pre-reset-passwd-{stamp}")
    backup_db = os.path.join(backup_dir, "users.sqlite3")
    os.makedirs(backup_dir, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    handle, credential_file = tempfile.mkstemp(dir=state.get("AUTH_DIR"), prefix="reset-admin-credentials.")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(f"{username}\t{secrets.token_hex(16)}\n")
    os.chmod(credential_file, 0o600)

    try:
        with sqlite3.connect(user_db) as source:
            columns = {row[1] for row in source.execute("PRAGMA table_info(users)")}
            required = {"username", "password_hash"}
            if not required <= columns:
                raise SystemExit("users table has an incompatible schema")
            row = source.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            if row is None:
                raise SystemExit("username does not exist")
            with open(credential_file, encoding="utf-8") as stream:
                password = stream.readline().rstrip("\n").split("\t", 1)[1]
            with sqlite3.connect(backup_db) as destination:
                source.backup(destination)
            values = {"password_hash": generate_password_hash(password)}
            if "token_version" in columns:
                values["token_version"] = "token_version + 1"
            assignments = ", ".join(
                f"{key} = {value}" if key == "token_version" else f"{key} = ?" for key, value in values.items()
            )
            params = [value for key, value in values.items() if key != "token_version"] + [username]
            updated = source.execute(f"UPDATE users SET {assignments} WHERE username = ?", params).rowcount
            if updated != 1:
                raise SystemExit("password reset did not update exactly one user")
    except BaseException:
        os.remove(credential_file)
        try:
            os.rmdir(backup_dir)
        except OSError:
            pass
        print("Password reset failed; no credential file was retained.", file=sys.stderr)
        raise SystemExit(1)

    os.chmod(backup_db, 0o600)
    uid, _gid = resolve_runner_identity(state)
    prepare_auth_storage(state, uid)
    print(f"Password reset completed for user: {username}")
    print(f"Auth database backup written to: {backup_db} (mode 0600)")
    print(f"New credential written to: {credential_file} (mode 0600)")
