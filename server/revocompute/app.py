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
from pathlib import Path
from typing import Any

from celery.result import AsyncResult
from flask import Flask, g, jsonify, request
from revocompute.auth import _SECRET_KEY as _TOKEN_SIGNING_KEY  # noqa: E402
from revocompute.auth import UserDatabase  # noqa: E402
from revocompute.auth import _env_bool  # noqa: E402
from revocompute.config import ComputeConfig
from revocompute.config import ensure_directories as _ensure_directories
from revocompute.config import env_csv as _env_csv
from revocompute.config import env_path as _env_path
from revocompute.config import env_required as _env_required
from revocompute.config import format_runner_identity as _format_runner_identity
from revocompute.config import resolve_docker_user as _resolve_docker_user
from revocompute.maintenance.tasks.result_cleanup import delete_task_artifacts as _delete_result_artifacts
from revocompute.maintenance.tasks.result_cleanup import deleted_status_from_task as _result_deleted_status
from revocompute.task_types import load_registry as _load_task_registry
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

CONFIG = ComputeConfig.from_env()
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

# Gunicorn preloads this once, then forks workers with the same ephemeral key.
app.secret_key = app.secret_key or _TOKEN_SIGNING_KEY


# Bootstrap every configured admin if the user database is empty.
if _user_db.user_count() == 0:
    _credential_lines = os.environ.get("ADMIN_BOOTSTRAP_CREDENTIALS", "").splitlines()
    _bootstrap_passwords = dict(line.split("\t", 1) for line in _credential_lines if "\t" in line)
    if set(_bootstrap_passwords) != ADMIN_USERS:
        raise RuntimeError(
            "Bootstrap credentials for every ADMIN_USERS entry are required for an empty "
            "user database; start the deployment with restart.sh"
        )
    for _admin_username in _ADMIN_USERNAMES:
        try:
            _created_admin = _user_db.create_user(
                username=_admin_username,
                email=f"{_admin_username}@revodesign.local",
                password=_bootstrap_passwords[_admin_username],
                role="admin",
                registration_status="approved",
                user_status="active",
            )
            _user_db.verify_email(_created_admin["id"])
            logging.warning(
                "No users found — created configured admin user %r. " "Log in and change its password immediately.",
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
task_runtime = importlib.import_module("revocompute.task_runtime")

celery = task_runtime.celery
task_store = task_runtime.task_store

from revocompute.manage_db import ManageDatabase  # noqa: E402

manage_db = ManageDatabase(CONFIG.manage_db_path)
app.config["manage_db"] = manage_db

# Define directories for storing files
app.config["UPLOAD_FOLDER"] = CONFIG.upload_folder
app.config["RESULTS_FOLDER"] = CONFIG.results_folder
app.config["RESULT_DOWNLOAD_MODE"] = CONFIG.result_download_mode

_ensure_directories(CONFIG.upload_folder, CONFIG.results_folder)

# Load the task type registry — gremlin is always enabled; additional runners
# are gated by the ENABLED_TASKRUNNERS env var.  If the YAML files are missing
# (e.g. in tests or non-standard deployments), register a hardcoded gremlin
# fallback so existing functionality still works.
_enabled_runners = set(_env_csv("ENABLED_TASKRUNNERS", ""))
try:
    _load_task_registry(CONFIG.task_types_config, CONFIG.runners_dir, _enabled_runners)
except FileNotFoundError:
    logging.warning(
        "Task type registry not found at %s — registering built-in gremlin fallback. "
        "Create config/task_types.yaml to register additional task types.",
        CONFIG.task_types_config,
    )
    from revocompute.task_types import RunnerConfig, RunnerMount, TaskParam, TaskType
    from revocompute.task_types import register as _register_tt  # noqa: E402

    _register_tt(
        TaskType(
            name="gremlin",
            display_name="PSSM-GREMLIN",
            docker_image="revodesign-revocompute-runner",
            command=["bash", "/app/revocompute/run.sh"],
            input_extension=".fasta",
            input_label="FASTA file",
            stage_markers={
                "hhblits": "HHblits MSA generation",
                "hhfilter": "HHfilter filtering",
                "gremlin": "GREMLIN optimization",
                "blast": "PSI-BLAST PSSM",
            },
            result_patterns=("*.pkl", "*_ascii_mtx_file", "*.GREMLIN.mrf.pkl"),
            params=(TaskParam(name="iter", type="int", default=100, description="GREMLIN optimization iterations"),),
        ),
        RunnerConfig(),
    )


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
    return _safe_join(app.config["RESULTS_FOLDER"], f"{task_id}_results.zip")


def _safe_fasta_prefix(filename: str) -> str:
    base = os.path.basename(str(filename or "result.fasta"))
    stem = os.path.splitext(base)[0]
    safe = secure_filename(stem)
    return safe or "result"


def _task_zip_download_name(task: dict[str, Any]) -> str:
    prefix = _safe_fasta_prefix(str(task.get("filename") or "result.fasta"))
    return f"{prefix}_{task['md5sum']}_results.zip"


def _is_admin_user() -> bool:
    """Return whether the authenticated user has the canonical admin role."""
    user = g.get("current_user")
    return bool(user and user.get("role") == "admin")


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
    if _is_admin_user():
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


# ---------------------------------------------------------------------------
# Register HTTP routes (imported late to avoid circular imports — routes.py
# needs ``app`` and helpers that are only available after this module loads).
# ---------------------------------------------------------------------------
importlib.import_module("revocompute.routes")

if __name__ == "__main__":
    # Containerized server binds to all interfaces by design.
    app.run(host="0.0.0.0", port=CONFIG.port)  # nosec B104
