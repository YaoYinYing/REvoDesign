# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from celery.result import AsyncResult
from flask import Flask, g, jsonify, request
from pssm_gremlin_server.config import (
    GremlinConfig,
    ensure_directories as _ensure_directories,
    env_csv as _env_csv,
    env_path as _env_path,
    env_required as _env_required,
    format_runner_identity as _format_runner_identity,
    resolve_docker_user as _resolve_docker_user,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from pssm_gremlin_server.maintenance.tasks.result_cleanup import (
    delete_task_artifacts as _delete_result_artifacts,
    deleted_status_from_task as _result_deleted_status,
)

# Ensure AUTH_SECRET_KEY is set *before* auth.py initialises its token
# serializer, otherwise multi-worker gunicorn generates independent signing
# keys per worker and tokens from one worker fail validation on another.
if not os.environ.get("AUTH_SECRET_KEY"):
    os.environ["AUTH_SECRET_KEY"] = os.urandom(32).hex()

from pssm_gremlin_server.auth import UserDatabase  # noqa: E402
from pssm_gremlin_server.auth import _env_bool  # noqa: E402
from pssm_gremlin_server.auth import _env_str  # noqa: E402

CONFIG = GremlinConfig.from_env()
_env_required("ADMIN_USERS")
_ADMIN_USERNAMES = tuple(_env_csv("ADMIN_USERS", ""))
if not _ADMIN_USERNAMES:
    raise RuntimeError("Required environment variable ADMIN_USERS must contain a username")
if len(_ADMIN_USERNAMES) != len(set(_ADMIN_USERNAMES)):
    raise RuntimeError("Environment variable ADMIN_USERS must not contain duplicate usernames")
ADMIN_USERS = set(_ADMIN_USERNAMES)

THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)
TEMPLATE_IMAGE_DIR = os.path.join(THIS_DIR, "templates", "images")

app = Flask(__name__, template_folder="./templates")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MiB upload limit


@app.after_request
def _add_security_headers(response):
    """Add browser hardening headers to every response."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "interest-cohort=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'",
    )
    # HSTS only when the connection is already HTTPS — browsers ignore the
    # header over plain HTTP (RFC 6797 §7.2), and setting max-age on an
    # HTTP response could lock users out if HTTPS breaks later.
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


# ---------------------------------------------------------------------------
# Auth initialisation — replaces the old HTTPBasicAuth + users.txt model
# ---------------------------------------------------------------------------
_user_db = UserDatabase()
app.config["user_db"] = _user_db
ENABLE_REGISTER = _env_bool("ENABLE_REGISTER", False)

# Secrets for token signing — reuse a shared secret or generate a random one.
# In production set AUTH_SECRET_KEY to a fixed, high-entropy value so tokens
# survive process restarts.
_token_key = _env_str("AUTH_SECRET_KEY", os.urandom(32).hex())
app.secret_key = app.secret_key or _token_key


# Bootstrap every configured admin if the user database is empty.
if _user_db.user_count() == 0:
    _credential_lines = os.environ.get("ADMIN_BOOTSTRAP_CREDENTIALS", "").splitlines()
    _bootstrap_passwords = dict(
        line.split("\t", 1) for line in _credential_lines if "\t" in line
    )
    if set(_bootstrap_passwords) != ADMIN_USERS:
        raise RuntimeError(
            "Bootstrap credentials for every ADMIN_USERS entry are required for an empty "
            "user database; start the deployment with restart_pssm_flask.sh"
        )
    for _admin_username in _ADMIN_USERNAMES:
        try:
            _created_admin = _user_db.create_user(
                username=_admin_username,
                email=f"{_admin_username}@revodesign.local",
                password=_bootstrap_passwords[_admin_username],
                is_admin=True,
                registration_status="approved",
                user_status="active",
            )
            _user_db.verify_email(_created_admin["id"])
            logging.warning(
                "No users found — created configured admin user %r. "
                "Log in and change its password immediately.",
                _admin_username,
            )
        except IntegrityError:
            # Concurrent import may win an individual bootstrap insert race.
            _created_admin = _user_db.get_user_by_username(_admin_username)
            if _created_admin and not _created_admin.get("email_verified"):
                _user_db.verify_email(_created_admin["id"])
            logging.info(
                "Configured admin user %r already exists after bootstrap race.",
                _admin_username,
            )


# Worker-safe task runtime.  This module has no Flask/auth dependency, so the
# Celery process imports it directly without opening the user database.
from pssm_gremlin_server import task_runtime  # noqa: E402

celery = task_runtime.celery
task_store = task_runtime.task_store

# Define directories for storing files
app.config["UPLOAD_FOLDER"] = CONFIG.upload_folder
app.config["RESULTS_FOLDER"] = CONFIG.results_folder

_ensure_directories(CONFIG.upload_folder, CONFIG.results_folder)


def _is_binary_file(path: str) -> bool:
    try:
        with Path(path).open("rb") as f:
            chunk = f.read(4096)
    except OSError:
        return True
    if not chunk:
        return False
    if b"\0" in chunk:
        return True
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _is_fasta_content(path: str) -> bool:
    """Return True if *path* looks like a FASTA file (first non-blank line starts with '>')."""
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                return stripped.startswith(">")
    except OSError:
        return False
    return False


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_TASK_ID_PATTERN = re.compile(r"[a-fA-F0-9]{32}$")


def _path_is_within(base_dir: str, candidate: str) -> bool:
    base_abs = os.path.abspath(base_dir)
    target_abs = os.path.abspath(candidate)
    try:
        common = os.path.commonpath([base_abs, target_abs])
    except ValueError:
        return False
    return common == base_abs


def _safe_join(base_dir: str, *parts: str) -> str:
    candidate = os.path.abspath(os.path.join(base_dir, *parts))
    if not _path_is_within(base_dir, candidate):
        raise ValueError(f"Path escapes configured base directory: {candidate}")
    return candidate


def _normalize_task_id(raw_task_id: Any) -> str | None:
    task_id = str(raw_task_id or "").strip().lower()
    if not _TASK_ID_PATTERN.fullmatch(task_id):
        return None
    return task_id


def _sanitize_for_log(value: str, max_len: int = 4096) -> str:
    cleaned = _CONTROL_CHARS.sub(" ", value)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


_REDACTED_HEADERS = frozenset({"authorization", "cookie", "x-api-key"})


def _sanitize_headers_for_log(raw_headers: dict[str, str]) -> str:
    sanitized: dict[str, str] = {}
    for key, value in raw_headers.items():
        safe_key = _sanitize_for_log(str(key), max_len=256)
        if not safe_key or safe_key.lower() in _REDACTED_HEADERS:
            continue
        safe_value = _sanitize_for_log(str(value), max_len=2048)
        sanitized[safe_key] = safe_value
    return json.dumps(sanitized, ensure_ascii=True, sort_keys=True)


def _current_username() -> str:
    """Return the current authenticated username, or empty string."""
    user = g.get("current_user")
    return user["username"] if user else ""


# Parsed at import time — a tuple of header names to try for client IP.
_CLIENT_IP_HEADERS = tuple(
    h.strip().strip("'\"")
    for h in os.environ.get("CLIENT_IP_HEADERS", "X-Forwarded-For, X-Real-IP").split(",")
    if h.strip()
)
_CLIENT_COUNTRY_HEADER = os.environ.get("CLIENT_COUNTRY_HEADER", "").strip().strip("'\"") or None


def _client_ip() -> str | None:
    """Return the best-guess client IP, respecting ``CLIENT_IP_HEADERS``.

    ``CLIENT_IP_HEADERS`` is a comma-separated list of HTTP headers tried in
    priority order (e.g. ``CF-Connecting-IP, X-Forwarded-For, X-Real-IP``).
    Falls back to ``request.remote_addr``.
    """
    for header in _CLIENT_IP_HEADERS:
        value = request.headers.get(header, "").split(",")[0].strip()
        if value:
            return value
    remote = request.remote_addr
    return remote if remote else None


def _client_country() -> str | None:
    """Return the client country from ``CLIENT_COUNTRY_HEADER`` if configured.

    e.g. ``CLIENT_COUNTRY_HEADER=CF-IPCountry`` for Cloudflare.
    """
    if _CLIENT_COUNTRY_HEADER is None:
        return None
    value = request.headers.get(_CLIENT_COUNTRY_HEADER, "").strip()
    return value if value else None


def _request_metadata() -> dict[str, str | None]:
    ip = _client_ip()
    headers = {str(k): str(v) for k, v in request.headers.items()}
    return {
        "ip": ip,
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "username": _current_username() or "anonymous",
        "headers_json": _sanitize_headers_for_log(headers),
    }


def _task_zip_path(task: Any) -> str:
    raw_task_id = task if isinstance(task, str) else task["md5sum"]
    task_id = _normalize_task_id(raw_task_id)
    if task_id is None:
        raise ValueError(f"Invalid task id for result archive: {raw_task_id!r}")
    return _safe_join(app.config["RESULTS_FOLDER"], f"{task_id}_PSSM_GREMLIN_results.zip")


def _safe_fasta_prefix(filename: str) -> str:
    base = os.path.basename(str(filename or "result.fasta"))
    stem = os.path.splitext(base)[0]
    safe = secure_filename(stem)
    return safe or "result"


def _task_zip_download_name(task: dict[str, Any]) -> str:
    prefix = _safe_fasta_prefix(str(task.get("filename") or "result.fasta"))
    return f"{prefix}_{task['md5sum']}_PSSM_GREMLIN_results.zip"


def _is_admin_user(username: str | None = None) -> bool:
    # DB-based admin check — covers admins created through the user-control UI
    user = g.get("current_user")
    if user and (user.get("role") == "admin" or user.get("is_admin")):
        return True
    # Legacy env-var-based check
    target = (username if username is not None else _current_username()) or ""
    return target in ADMIN_USERS


def _task_access_allowed(task: dict[str, Any]) -> bool:
    if _is_admin_user():
        return True
    current_user = _current_username() or ""
    return bool(current_user) and task.get("username") == current_user


def _task_access_denied(md5sum: str):
    return (
        jsonify(
            {
                "status": "forbidden",
                "md5sum": md5sum,
                "message": "Task does not belong to the authenticated user",
            }
        ),
        403,
    )


def _task_id_for_upload(content_md5: str, username: str | None) -> str:
    # Keep task IDs owner-scoped so two users uploading the same FASTA never collide.
    owner = username or "anonymous"
    scoped_key = f"{owner}:{content_md5}"
    return hashlib.md5(scoped_key.encode("utf-8"), usedforsecurity=False).hexdigest()


def _task_delete_allowed(task: dict[str, Any]) -> bool:
    current_user = _current_username() or ""
    if _is_admin_user(current_user):
        return True
    return bool(current_user) and task.get("username") == current_user


def _delete_task_artifacts(task: dict[str, Any]) -> None:
    _delete_result_artifacts(task, app.config["RESULTS_FOLDER"])


def _revoke_celery_task(task: dict[str, Any]) -> None:
    celery_id = task.get("celery_task_id")
    if not celery_id:
        return
    try:
        result = AsyncResult(celery_id)
        result.revoke(terminate=True)
    except Exception as exc:  # pylint: disable=broad-except
        logging.warning("Failed to revoke Celery task %s: %s", celery_id, exc)


def _deleted_status_from_task(task: dict[str, Any]) -> str:
    return _result_deleted_status(task)


def _is_deleted_status(status: Any) -> bool:
    """True when task artifacts were removed by a user or maintenance."""
    normalized = str(status or "").strip().lower()
    return normalized in {
        "deleted:finshed",
        "deleted:cancel",
        "cleaned:finished",
        "cleaned:cancel",
    }


# Compatibility exports for callers that historically imported task symbols
# from this web module.  New code imports them from task_runtime directly.
_build_running_trace = task_runtime._build_running_trace
_extract_stage_from_log_line = task_runtime._extract_stage_from_log_line
_is_terminal_status = task_runtime._is_terminal_status
_pack_failed_results_archive = task_runtime._pack_failed_results_archive
_pack_results_archive = task_runtime._pack_results_archive
_ROOT_MOUNT_DIRECTORY = task_runtime._ROOT_MOUNT_DIRECTORY
_runner_thread_env = task_runtime._runner_thread_env
_task_is_terminal = task_runtime._task_is_terminal
format_times = task_runtime.format_times
format_walltime = task_runtime.format_walltime
run_gremlin_task = task_runtime.run_gremlin_task
run_pssm_gremlin_in_docker = task_runtime.run_pssm_gremlin_in_docker


# ---------------------------------------------------------------------------
# Register HTTP routes (imported late to avoid circular imports — routes.py
# needs ``app`` and helpers that are only available after this module loads).
# ---------------------------------------------------------------------------
importlib.import_module("pssm_gremlin_server.routes")

if __name__ == "__main__":
    # Containerized server binds to all interfaces by design.
    app.run(host="0.0.0.0", port=CONFIG.port)  # nosec B104
