# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Runner identity and host storage preparation/validation.

restart.sh never changes host permissions — it validates that the deployment
account provisioned them and refuses to start otherwise.
"""

from __future__ import annotations

import grp
import os
import pwd
import stat
import subprocess
import sys
from pathlib import Path

from revocompute_ctl.compose import compose_args, run_cmd


def resolve_runner_identity(state) -> tuple[str, str]:
    """Auto-derive RUNNER_UID/RUNNER_GID from the configured names, then
    export both like the shell did."""
    user = state.get("RUNNER_USERNAME") or "revodesign"
    group = state.get("RUNNER_GROUP") or "revodesign_appgroup"

    uid = state.get("RUNNER_UID")
    if not uid:
        try:
            uid = str(pwd.getpwnam(user).pw_uid)
        except KeyError:
            uid = ""
    gid = state.get("RUNNER_GID")
    if not gid:
        try:
            gid = str(grp.getgrnam(group).gr_gid)
        except KeyError:
            try:
                gid = str(pwd.getpwnam(user).pw_gid)
            except KeyError:
                gid = ""
        if not gid:
            gid = "1000"
    uid = uid or "1000"

    state.runtime["RUNNER_UID"] = uid
    state.runtime["RUNNER_GID"] = gid
    print(f"Using runner identity {uid}:{gid} (user {user}, group {group}).")
    return uid, gid


def path_mode_allows_runner(path: str, uid: str, gid: str, required: str) -> bool:
    """True when the runner's uid/gid holds the octal `required` bits on the
    path — via plain mode bits or a named-user ACL (POSIX ACL effective bits).
    """
    info = os.stat(path)
    shift = 6 if info.st_uid == int(uid) else 3 if info.st_gid == int(gid) else 0
    if ((stat.S_IMODE(info.st_mode) >> shift) & int(required, 8)) == int(required, 8):
        return True

    # Numeric mode bits do not identify a named-user ACL. Inspect it read-only
    # and apply the ACL mask when the runner has an explicit entry.
    try:
        output = subprocess.run(["getfacl", "-cpn", path], check=True, capture_output=True, text=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

    def permission_bits(value: str) -> int:
        return sum(bit for flag, bit in zip(value, (4, 2, 1)) if flag != "-")

    named = None
    mask = 7
    for line in output.splitlines():
        fields = line.split(":")
        if len(fields) == 3 and fields[0] == "user" and fields[1] == uid:
            named = permission_bits(fields[2])
        elif len(fields) == 3 and fields[0] == "mask" and not fields[1]:
            mask = permission_bits(fields[2])
    effective = (named & mask) if named is not None else 0
    return bool(effective & int(required, 8) == int(required, 8))


_PROVISION_HINT = "Provision runner rwx access before activation; restart.sh does not change host permissions."


def prepare_auth_storage(state, uid: str) -> None:
    auth_dir = state.get("AUTH_DIR")
    if not auth_dir:
        raise SystemExit("AUTH_DIR must be set")
    user_db = os.path.join(auth_dir, "users.sqlite3")
    os.makedirs(auth_dir, exist_ok=True)
    if not path_mode_allows_runner(auth_dir, uid, "0", "7"):
        print(f"AUTH_DIR is not accessible to runner uid {uid}: {auth_dir}", file=sys.stderr)
        print(_PROVISION_HINT, file=sys.stderr)
        raise SystemExit(1)

    sqlite_files = [user_db] + [str(path) for path in Path(auth_dir).glob("users.sqlite3-*")]
    for path in sqlite_files:
        if os.path.exists(path) and not path_mode_allows_runner(path, uid, "0", "6"):
            print(f"SQLite auth file is not writable by runner uid {uid}: {path}", file=sys.stderr)
            print(
                "Provision runner read/write access before activation; restart.sh does not change host permissions.",
                file=sys.stderr,
            )
            raise SystemExit(1)


def prepare_result_storage(state, uid: str) -> None:
    results_dir = os.path.join(state.server_dir(), "results")
    os.makedirs(results_dir, exist_ok=True)
    if not path_mode_allows_runner(results_dir, uid, "0", "7"):
        print(f"Results directory is not accessible to runner uid {uid}: {results_dir}", file=sys.stderr)
        print(_PROVISION_HINT, file=sys.stderr)
        raise SystemExit(1)


def validate_result_storage(state, compose_cmd: tuple[str, ...]) -> None:
    from revocompute_ctl import COMPOSE_FILE

    results_dir = os.path.join(state.server_dir(), "results")
    web_check = run_cmd(
        [
            *compose_cmd,
            "-f",
            str(COMPOSE_FILE),
            "--env-file",
            state.env_file,
            "exec",
            "-T",
            "web",
            "sh",
            "-c",
            'test -w "$1" && test -x "$1"',
            "sh",
            results_dir,
        ],
        env=state.exported(),
        check=False,
    )
    if web_check.returncode != 0:
        print(f"Results directory is not writable by the web container: {results_dir}", file=sys.stderr)
        raise SystemExit(1)
    gateway_check = run_cmd(
        [
            *compose_cmd,
            "-f",
            str(COMPOSE_FILE),
            "--env-file",
            state.env_file,
            "exec",
            "-T",
            "gateway",
            "sh",
            "-c",
            "test -r /srv/results && test -x /srv/results",
        ],
        env=state.exported(),
        check=False,
    )
    if gateway_check.returncode != 0:
        print(f"Results directory is not readable by the Nginx gateway: {results_dir}", file=sys.stderr)
        raise SystemExit(1)


_AUTH_DB_WRITE_CHECK = (
    'import os, sqlite3; path=os.environ["USER_DB_PATH"]; conn=sqlite3.connect(path); '
    'conn.execute("BEGIN IMMEDIATE"); conn.rollback()'
)


def validate_auth_database_storage(state, compose_cmd: tuple[str, ...]) -> None:
    result = run_cmd(
        [
            *compose_cmd,
            *compose_args(state),
            "--env-file",
            state.env_file,
            "exec",
            "-T",
            "web",
            "python",
            "-c",
            _AUTH_DB_WRITE_CHECK,
        ],
        env=state.exported(),
        check=False,
    )
    if result.returncode != 0:
        print("Auth database is not writable by the web service; refusing to report readiness.", file=sys.stderr)
        raise SystemExit(1)


def validate_auth_storage(state) -> None:
    auth_dir = state.get("AUTH_DIR")
    if not auth_dir:
        print("AUTH_DIR must be set to a web-only host directory outside SERVER_DIR.", file=sys.stderr)
        raise SystemExit(1)
    server_dir, auth_dir_real = os.path.realpath(state.server_dir()), os.path.realpath(auth_dir)
    if os.path.commonpath([server_dir, auth_dir_real]) == server_dir:
        raise SystemExit("AUTH_DIR must be outside SERVER_DIR")


def require_production_identity(state) -> tuple[str, str]:
    uid, gid = resolve_runner_identity(state)
    if uid != "1000" or gid != "1000":
        print(f"Production images require RUNNER_UID=1000 and RUNNER_GID=1000; got {uid}:{gid}.", file=sys.stderr)
        raise SystemExit(1)
    return uid, gid
