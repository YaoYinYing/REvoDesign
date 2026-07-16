# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import grp
import hashlib
import json
import logging
import os
import pwd
import re
import shutil
import signal
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import docker
from celery import Celery
from celery.result import AsyncResult
from docker import types
from flask import Flask, g, jsonify, request
from pssm_gremlin_server.db import TaskDatabase
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

# Ensure AUTH_SECRET_KEY is set *before* auth.py initialises its token
# serializer, otherwise multi-worker gunicorn generates independent signing
# keys per worker and tokens from one worker fail validation on another.
if not os.environ.get("AUTH_SECRET_KEY"):
    os.environ["AUTH_SECRET_KEY"] = os.urandom(32).hex()

from pssm_gremlin_server.auth import UserDatabase  # noqa: E402
from pssm_gremlin_server.auth import _env_bool  # noqa: E402
from pssm_gremlin_server.auth import _env_str  # noqa: E402
from pssm_gremlin_server.auth import send_admin_digest  # noqa: E402

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


def _env_path(var_name: str, default: str) -> str:
    value = os.environ.get(var_name)
    if value:
        return os.path.abspath(os.path.expanduser(value))
    return os.path.abspath(default)


def _env_int(var_name: str, default: int) -> int:
    raw = os.environ.get(var_name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {var_name} must be an integer, got {raw!r}") from exc


def _env_csv(var_name: str, default: str) -> list[str]:
    raw = os.environ.get(var_name, default)
    values = [value.strip() for value in raw.split(",")]
    return [value for value in values if value]


def _format_runner_identity(user_value: str, group_value: str) -> str:
    user = user_value.strip()
    group = group_value.strip()
    if not user or not group:
        raise RuntimeError("Runner user and group must both be provided.")
    if user in {"0", "root"} or group in {"0", "root"}:
        raise ValueError("GREMLIN runner cannot run as root. Provide a non-root user and group.")
    return f"{user}:{group}"


def _resolve_docker_user() -> str:
    username = os.environ.get("RUNNER_USERNAME")
    group = os.environ.get("RUNNER_GROUP")
    if username or group:
        if not username or not group:
            raise RuntimeError("RUNNER_USERNAME and RUNNER_GROUP must be set together.")
        return _format_runner_identity(username, group)

    env_uid = os.environ.get("RUNNER_UID")
    env_gid = os.environ.get("RUNNER_GID")
    if env_uid or env_gid:
        if not env_uid or not env_gid:
            raise RuntimeError("RUNNER_UID and RUNNER_GID must both be defined.")
        return _format_runner_identity(env_uid, env_gid)

    env_user = os.environ.get("RUNNER_USER")
    if env_user:
        if ":" not in env_user:
            raise RuntimeError("RUNNER_USER must be in the form '<user>:<group>'.")
        user_part, group_part = env_user.split(":", 1)
        return _format_runner_identity(user_part, group_part)

    raise RuntimeError(
        "Runner user configuration missing. Set RUNNER_UID/RUNNER_GID or RUNNER_USERNAME/RUNNER_GROUP "
        "to a dedicated non-root account."
    )


def _ensure_directories(*paths: str) -> None:
    for path in paths:
        os.makedirs(path, exist_ok=True)


@dataclass(frozen=True, slots=True)
class GremlinConfig:
    """Centralized configuration for GREMLIN server paths and runtime settings."""

    server_dir: str
    upload_folder: str
    results_folder: str
    db_path: str
    docker_image: str
    docker_user: str
    uniref30_db: str
    uniref90_db: str
    nproc: int
    maxmem: int
    port: int
    public_dashboard: bool

    @classmethod
    def from_env(cls) -> GremlinConfig:
        server_dir = _env_path("SERVER_DIR", "/mnt/data/yinying/server/")
        upload_folder = os.path.join(server_dir, "upload")
        results_folder = os.path.join(server_dir, "results")
        return cls(
            server_dir=server_dir,
            upload_folder=upload_folder,
            results_folder=results_folder,
            db_path=_env_path("DB_PATH", os.path.join(server_dir, "pssm_gremlin.sqlite3")),
            docker_image=os.environ.get("RUNNER_IMAGE", "revodesign-pssm-gremlin"),
            docker_user=_resolve_docker_user(),
            uniref30_db=_env_path(
                "DB_UNIREF30",
                "/mnt/db/uniref30_uc30/UniRef30_2022_02/UniRef30_2022_02",
            ),
            uniref90_db=_env_path("DB_UNIREF90", "/mnt/db/uniref90/uniref90"),
            nproc=_env_int("NPROC", 16),
            maxmem=_env_int("MAXMEM", 64),
            port=_env_int("PORT", 8080),
            public_dashboard=_env_bool("PUBLIC_DASHBOARD", False),
        )


CONFIG = GremlinConfig.from_env()


ADMIN_USERS = set(_env_csv("ADMIN_USERS", "admin"))

# Bootstrap: if the user database is empty (first run), create a default
# admin account so the server isn't locked out.
if _user_db.user_count() == 0:
    _default_admin = _env_str("DEFAULT_ADMIN_USERNAME", "admin")
    _default_pass = _env_str("DEFAULT_ADMIN_PASSWORD", os.urandom(16).hex())
    try:
        _created_admin = _user_db.create_user(
            username=_default_admin,
            email=f"{_default_admin}@revodesign.local",
            password=_default_pass,
            is_admin=True,
            registration_status="approved",
            user_status="active",
        )
        _user_db.verify_email(_created_admin["id"])
        logging.warning(
            "No users found — created default admin user %r with an auto-generated password. "
            "Log in and change it immediately.",
            _default_admin,
        )
    except IntegrityError:
        # Web and Celery can import the app concurrently on first boot.  If
        # another process won the bootstrap insert race, continue with it.
        _created_admin = _user_db.get_user_by_username(_default_admin)
        if _created_admin and not _created_admin.get("email_verified"):
            _user_db.verify_email(_created_admin["id"])
        logging.info("Default admin user %r already exists after bootstrap race.", _default_admin)


# Admin new-user digest: periodically email ADMIN_NOTIFY_EMAIL a table of
# registrations that haven't been included in a digest yet, then mark them
# notified so each user appears only once.
_admin_digest_minutes = _env_int("ADMIN_NEW_USER_INFORM", 0)
if _admin_digest_minutes > 0 and _env_str("ADMIN_NOTIFY_EMAIL", ""):
    import threading

    _digest_lock = os.path.join(_env_str("SERVER_DIR", os.getcwd()), ".admin_digest.lock")

    def _digest_loop() -> None:
        import random

        while True:
            _jitter = random.uniform(-5, 5)  # spread worker wake-ups
            time.sleep(_admin_digest_minutes * 60 + _jitter)
            try:
                # ponytail: file lock so only one worker sends the digest
                # (gunicorn --preload forks the thread into every worker).
                # flock is fd-scoped — kernel auto-releases on process death,
                # so a crash won't leave a stale lock behind.
                import fcntl

                with open(_digest_lock, "w") as _lock_fh:
                    fcntl.flock(_lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    send_admin_digest()
            except OSError:
                pass  # another worker has the lock — try next cycle
            except Exception:
                logging.exception("Admin digest thread failed")

    _digest_thread = threading.Thread(target=_digest_loop, daemon=True)
    _digest_thread.start()


# Celery configurations
_redis_password = os.environ.get("REDIS_PASSWORD", "")
_redis_auth = f":{_redis_password}@" if _redis_password else ""
redis_url = os.environ.get("REDIS_URL", f"redis://{_redis_auth}localhost:6379/0")
celery_backend = os.environ.get("RESULT_BACKEND", redis_url)
celery_broker = os.environ.get("BROKER_URL", redis_url)
celery = Celery(
    app.name,
    broker=celery_broker,
    backend=celery_backend,
)
celery.conf.broker_connection_retry_on_startup = True

# number of processors for a run
os.environ["GREMLIN_CALC_CPU_NUM"] = f"{CONFIG.nproc}"

# Define directories for storing files
app.config["UPLOAD_FOLDER"] = CONFIG.upload_folder
app.config["RESULTS_FOLDER"] = CONFIG.results_folder

# SQLite DB for tracking jobs
task_store = TaskDatabase(CONFIG.db_path)

_ensure_directories(CONFIG.upload_folder, CONFIG.results_folder)


def _is_binary_file(path: str) -> bool:
    try:
        with open(path, "rb") as f:
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
        with open(path, encoding="utf-8", errors="replace") as f:
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


def _local_user_identity() -> str:
    """Return username/group and uid/gid using in-process identity APIs."""
    uid_num = os.getuid()
    gid_num = os.getgid()
    try:
        username = pwd.getpwuid(uid_num).pw_name
    except KeyError:
        username = str(uid_num)
    try:
        groupname = grp.getgrgid(gid_num).gr_name
    except KeyError:
        groupname = str(gid_num)
    return _sanitize_for_log(f"{username}:{groupname}-{uid_num}:{gid_num}", max_len=256)


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


def _virtual_upload_path(filename: str) -> str:
    safe_name = os.path.basename(filename or "unknown.fasta")
    return f"/srv/REvoDesign/PSSM_GREMLIN/upload/{safe_name}"


def _sanitize_task_error(task: dict[str, Any], error: Any) -> str | None:
    """Redact internal filesystem paths from error messages before returning to clients."""
    if error is None:
        return None
    message = str(error)
    # Redact the task's own file path
    file_path = str(task.get("file_path") or "")
    if file_path:
        message = message.replace(file_path, _virtual_upload_path(task.get("filename", "unknown.fasta")))
    # Redact the server data directory (may contain user home dirs, DB paths, etc.)
    server_dir = os.environ.get("SERVER_DIR", "")
    if server_dir and server_dir in message:
        message = message.replace(server_dir, "<server_dir>")
    # Redact the task result directory
    result_dir = str(task.get("result_dir") or "")
    if result_dir and result_dir in message:
        message = message.replace(result_dir, "<result_dir>")
    return message


_RUNNING_TRACE_STEPS: tuple[tuple[str, str], ...] = (
    (
        "hhblits",
        "hhblits: searching for co-evolutionary sequences",
    ),
    (
        "hhfilter",
        "hhfilter: filtering co-evolutionary",
    ),
    (
        "gremlin",
        "gremlin: calculating co-evolution signals",
    ),
    (
        "blast",
        "blast: searching for consensus profile",
    ),
)

_RUNNING_STAGE_INDEX = {stage: index for index, (stage, _) in enumerate(_RUNNING_TRACE_STEPS)}
_RUNNER_STAGE_PREFIX = "REVODESIGN_STAGE:"
_RUNNER_STAGE_ALIASES = {
    "hhblits": "hhblits",
    "hhfilter": "hhfilter",
    "gremlin": "gremlin",
    "blast": "blast",
    "psiblast": "blast",
    "psi-blast": "blast",
}


def _extract_stage_from_log_line(line: str) -> str | None:
    marker_pos = line.find(_RUNNER_STAGE_PREFIX)
    if marker_pos < 0:
        return None
    raw_marker = line[marker_pos + len(_RUNNER_STAGE_PREFIX) :].strip().lower()
    if not raw_marker:
        return None
    token = raw_marker.split()[0]
    return _RUNNER_STAGE_ALIASES.get(token)


def _build_running_trace(task: dict[str, Any]) -> str:
    if task.get("status") != "running":
        return ""

    current_stage = str(task.get("run_stage") or "").strip().lower()
    current_index = _RUNNING_STAGE_INDEX.get(current_stage, 0)

    traced_lines: list[str] = []
    for index, (_, label) in enumerate(_RUNNING_TRACE_STEPS):
        if index < current_index:
            marker = "done"
        elif index == current_index:
            marker = "running"
        else:
            marker = "pending"
        traced_lines.append(f"{label} [{marker}]")
    return "\n".join(traced_lines)


try:
    _ROOT_MOUNT_DIRECTORY = f"/home/{os.getlogin()}"
except BaseException:
    _ROOT_MOUNT_DIRECTORY = os.path.abspath(tempfile.gettempdir())
    os.makedirs(_ROOT_MOUNT_DIRECTORY, exist_ok=True)


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
    if CONFIG.public_dashboard:
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
    result_dir = task.get("result_dir")
    if result_dir:
        safe_result_dir = os.path.abspath(str(result_dir))
        if os.path.isdir(safe_result_dir):
            if safe_result_dir in {os.path.abspath(os.sep), os.path.abspath(os.path.expanduser("~"))}:
                logging.warning("Refusing to delete unsafe root-like directory: %s", safe_result_dir)
            elif not _path_is_within(app.config["RESULTS_FOLDER"], safe_result_dir):
                logging.warning("Refusing to delete result directory outside RESULTS_FOLDER: %s", safe_result_dir)
            else:
                shutil.rmtree(safe_result_dir, ignore_errors=True)
    try:
        zip_path = _task_zip_path(task)
    except ValueError:
        logging.warning("Refusing to delete zip for invalid task id: %s", task.get("md5sum"))
        return
    if os.path.exists(zip_path):
        os.remove(zip_path)


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
    current_status = str(task.get("status") or "").strip().lower()
    if current_status in {"deleted:finshed", "deleted:cancel"}:
        return current_status
    if current_status == "finished":
        return "deleted:finshed"
    return "deleted:cancel"


def _is_deleted_status(status: Any) -> bool:
    """True when *status* is a deleted state (``deleted:finshed`` or ``deleted:cancel``)."""
    normalized = str(status or "").strip().lower()
    return normalized in {"deleted:finshed", "deleted:cancel"}


def _is_terminal_status(status: Any) -> bool:
    """True when *status* is terminal — deleted or cancelled."""
    normalized = str(status or "").strip().lower()
    return normalized in {"deleted:finshed", "deleted:cancel", "cancelled"}


def _task_is_terminal(md5sum: str) -> bool:
    task = task_store.get_task(md5sum)
    if not task:
        return False
    return _is_terminal_status(task.get("status"))


def _create_mount(mount_name: str, path: str, read_only=True) -> tuple[types.Mount, str]:
    """Create a mount point for each file and directory used by the model."""
    path = os.path.abspath(path)
    target_path = os.path.join(_ROOT_MOUNT_DIRECTORY, mount_name)

    if not read_only:
        logging.warning("%s is not read-only!", mount_name)

    if os.path.isdir(path):
        source_path = path
        mounted_path = target_path
    else:
        source_path = os.path.dirname(path)
        mounted_path = os.path.join(target_path, os.path.basename(path))
    if not os.path.exists(source_path):
        os.makedirs(source_path)
    logging.info("Mounting %s -> %s", source_path, target_path)
    mount = types.Mount(
        target=str(target_path),
        source=str(source_path),
        type="bind",
        read_only=read_only,
    )
    return mount, str(mounted_path)


def _runner_thread_env(nproc: int, maxmem: int) -> dict[str, str]:
    limited_nproc = max(1, int(nproc))
    limited_maxmem = max(1, int(maxmem))
    value = str(limited_nproc)
    return {
        "GREMLIN_CALC_CPU_NUM": value,
        "OMP_NUM_THREADS": value,
        "OPENBLAS_NUM_THREADS": value,
        "MKL_NUM_THREADS": value,
        "VECLIB_MAXIMUM_THREADS": value,
        "NUMEXPR_NUM_THREADS": value,
        "TF_NUM_INTRAOP_THREADS": value,
        "TF_NUM_INTEROP_THREADS": value,
        "OMP_DYNAMIC": "FALSE",
        "MKL_DYNAMIC": "FALSE",
        "MAXMEM": str(limited_maxmem),
    }


def run_pssm_gremlin_in_docker(fasta_path, output_dir, docker_client=None, stage_callback=None):
    mounts = []
    command_args = []

    if os.path.exists(fasta_path):
        fasta = os.path.abspath(fasta_path)
        mount_fasta, mounted_fasta = _create_mount(mount_name="fasta", path=fasta, read_only=True)
        mounts.append(mount_fasta)
        command_args.extend(["-i", mounted_fasta])

    os.makedirs(output_dir, exist_ok=True)
    output = os.path.abspath(output_dir)
    mount_output, mounted_output = _create_mount(mount_name="output", path=output, read_only=False)
    mounts.append(mount_output)
    command_args.extend(["-o", mounted_output])

    # sequence databases use prefixes instead of real file path
    # file prefix should be excluded before mounting the dir
    uniref30_db = os.path.abspath(CONFIG.uniref30_db)
    mount_uniref30_db, mounted_uniref30_db = _create_mount(
        mount_name="uniref30_db", path=os.path.dirname(uniref30_db), read_only=True
    )
    mounts.append(mount_uniref30_db)
    command_args.extend(["-U", os.path.join(mounted_uniref30_db, os.path.basename(uniref30_db))])

    uniref90_db = os.path.abspath(CONFIG.uniref90_db)

    mount_uniref90_db, mounted_uniref90_db = _create_mount(
        mount_name="uniref90_db", path=os.path.dirname(uniref90_db), read_only=True
    )
    mounts.append(mount_uniref90_db)
    command_args.extend(["-u", os.path.join(mounted_uniref90_db, os.path.basename(uniref90_db))])

    command_args.extend(["-j", str(CONFIG.nproc)])

    logging.info(command_args)

    client = docker_client or docker.from_env()

    container = client.containers.run(
        image=CONFIG.docker_image,
        command=command_args,
        remove=False,
        detach=True,
        mounts=mounts,
        environment=_runner_thread_env(CONFIG.nproc, CONFIG.maxmem),
        stdout=True,
        stderr=True,
    )

    stderr_lines: list[str] = []
    last_stage: str | None = None
    try:
        # Add signal handler to ensure CTRL+C also stops the running container.
        signal.signal(signal.SIGINT, lambda unused_sig, unused_frame: container.kill())

        for line in container.logs(stream=True):
            decoded = line.strip().decode("utf-8", errors="replace")
            if decoded:
                stage = _extract_stage_from_log_line(decoded)
                if stage and stage != last_stage:
                    last_stage = stage
                    if stage_callback:
                        stage_callback(stage)
                stderr_lines.append(decoded)
                logging.info(decoded)

        wait_result = container.wait()
        status_code = wait_result.get("StatusCode", 1)
        if status_code != 0:
            raise docker.errors.ContainerError(
                container=container,
                exit_status=status_code,
                command=command_args,
                image=CONFIG.docker_image,
                stderr="\n".join(stderr_lines[-200:]),
            )
    finally:
        try:
            container.remove(force=True)
        except docker.errors.DockerException:
            pass

    return


def _pack_results_archive(task: dict) -> None:
    zip_filename = _task_zip_path(task)
    zip_base = os.path.splitext(zip_filename)[0]
    if os.path.exists(zip_filename):
        os.remove(zip_filename)
    shutil.make_archive(zip_base, "zip", task["result_dir"])
    if os.path.isdir(task["result_dir"]):
        shutil.rmtree(task["result_dir"])


def _pack_failed_results_archive(task: dict, error: Any) -> None:
    """Archive partial outputs and a readable failure report for failed tasks."""
    result_dir = task.get("result_dir")
    if not result_dir:
        return
    try:
        os.makedirs(result_dir, exist_ok=True)
        report_path = os.path.join(result_dir, "task_failed.txt")
        message = _sanitize_task_error(task, error) or "Task failed."
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write("REvoDesign PSSM_GREMLIN task failed\n")
            handle.write(f"Task ID: {task.get('md5sum', 'unknown')}\n")
            handle.write(f"Input: {task.get('filename', 'unknown.fasta')}\n\n")
            handle.write(message)
            handle.write("\n")
        _pack_results_archive(task)
    except Exception as exc:  # pylint: disable=broad-except
        logging.warning("Failed to archive failed GREMLIN task %s: %s", task.get("md5sum"), exc)


def format_times(timestamp):
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    return None


def format_walltime(seconds: Any) -> str:
    if seconds is None:
        return "-"
    try:
        total_seconds = max(int(float(seconds)), 0)
    except (TypeError, ValueError):
        return "-"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@celery.task(name="run_gremlin_task")
def run_gremlin_task(md5sum):
    task = task_store.get_task(md5sum)
    if not task:
        logging.error("Task %s missing from database", md5sum)
        return

    if task["status"] not in {"pending", "running", "packing results"}:
        return

    output_dir = task["result_dir"]
    uploaded_file = os.path.join(output_dir, task["filename"])
    if not os.path.exists(uploaded_file):
        error_message = "Uploaded FASTA file not found on disk"
        _pack_failed_results_archive(task, error_message)
        task_store.update_task(
            md5sum,
            status="failed",
            error=error_message,
            finished_at=time.time(),
        )
        logging.error("Uploaded file missing for task %s", md5sum)
        return

    start_time = task.get("started_at") or time.time()
    current_stage = str(task.get("run_stage") or _RUNNING_TRACE_STEPS[0][0]).strip().lower()
    if current_stage not in _RUNNING_STAGE_INDEX:
        current_stage = _RUNNING_TRACE_STEPS[0][0]
    update_fields = {
        "status": "running",
        "error": None,
        "local_user": _local_user_identity(),
        "run_stage": current_stage,
    }
    if not task.get("started_at"):
        update_fields["started_at"] = start_time
    task_store.update_task(md5sum, **update_fields)
    if task.get("request_headers"):
        logging.info("Request headers for task %s: %s", md5sum, _sanitize_for_log(task["request_headers"]))

    stage_state = {"current": current_stage}

    def _on_stage_change(stage: str) -> None:
        if stage == stage_state["current"]:
            return
        if _task_is_terminal(md5sum):
            return
        stage_state["current"] = stage
        task_store.update_task(md5sum, run_stage=stage)

    try:
        run_pssm_gremlin_in_docker(
            fasta_path=uploaded_file,
            output_dir=output_dir,
            stage_callback=_on_stage_change,
        )
        if _task_is_terminal(md5sum):
            logging.info("Task %s was deleted during execution; skipping result packing and finalization.", md5sum)
            return
        final_stage = stage_state["current"] or _RUNNING_TRACE_STEPS[-1][0]
        task_store.update_task(md5sum, status="packing results", run_stage=final_stage)
        refreshed_task = task_store.get_task(md5sum) or task
        if _is_terminal_status(refreshed_task.get("status")):
            logging.info("Task %s was deleted before archive packing; skipping artifact packaging.", md5sum)
            return
        _pack_results_archive(refreshed_task)
        refreshed_task = task_store.get_task(md5sum) or refreshed_task
        if _is_terminal_status(refreshed_task.get("status")):
            logging.info("Task %s was deleted during archive packing; skipping final status update.", md5sum)
            return
        finish_time = time.time()
        task_store.update_task(
            md5sum,
            status="finished",
            finished_at=finish_time,
            walltime=finish_time - start_time,
            error=None,
            run_stage=final_stage,
        )
    except docker.errors.ContainerError as exc:
        finish_time = time.time()
        error_message = f"docker: {exc}"
        if not _task_is_terminal(md5sum):
            _pack_failed_results_archive(task, error_message)
            task_store.update_task(
                md5sum,
                status="failed",
                finished_at=finish_time,
                walltime=finish_time - start_time,
                error=error_message,
                run_stage=stage_state["current"],
            )
    except docker.errors.DockerException as exc:
        finish_time = time.time()
        error_message = f"docker: {exc}"
        if not _task_is_terminal(md5sum):
            _pack_failed_results_archive(task, error_message)
            task_store.update_task(
                md5sum,
                status="failed",
                finished_at=finish_time,
                walltime=finish_time - start_time,
                error=error_message,
                run_stage=stage_state["current"],
            )
        logging.error("Docker daemon unavailable for GREMLIN task %s: %s", md5sum, exc)
    except Exception as exc:  # pylint: disable=broad-except
        finish_time = time.time()
        error_message = str(exc)
        if not _task_is_terminal(md5sum):
            _pack_failed_results_archive(task, error_message)
            task_store.update_task(
                md5sum,
                status="failed",
                finished_at=finish_time,
                walltime=finish_time - start_time,
                error=error_message,
                run_stage=stage_state["current"],
            )
        logging.exception("Unexpected failure while running GREMLIN task %s", md5sum)


# ---------------------------------------------------------------------------
# Register HTTP routes (imported late to avoid circular imports — routes.py
# needs ``app`` and helpers that are only available after this module loads).
# ---------------------------------------------------------------------------
from pssm_gremlin_server import routes  # noqa: E402, F401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=CONFIG.port)  # nosec B104: containerized server, binding to all interfaces by design
