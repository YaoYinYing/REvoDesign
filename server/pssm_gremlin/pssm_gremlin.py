# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


#! /mnt/data/envs/conda_env/envs/REvoDesign/bin/python

from __future__ import annotations

import hashlib
import json
import logging
import os
import pwd
import grp
import re
import shutil
import signal
import subprocess
import time
from glob import glob
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import docker
from celery import Celery
from celery.result import AsyncResult
from docker import types
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from flask_httpauth import HTTPBasicAuth
from sqlalchemy import Column, Float, Index, Integer, MetaData, String, Table, Text, create_engine, desc, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)

app = Flask(__name__, template_folder="./templates")
auth = HTTPBasicAuth()

class TaskDatabase:
    """Minimal SQLite-based task tracker for GREMLIN jobs."""

    VALID_STATUSES = {
        "pending",
        "running",
        "packing results",
        "finished",
        "failed",
        "cancelled",
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
            Column("error", Text),
            Column("celery_task_id", String),
        )
        Index("idx_tasks_uploaded_at", self.tasks_table.c.uploaded_at)
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
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
    def _ensure_columns(conn) -> None:
        existing_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(tasks);").fetchall()}
        if "local user" not in existing_columns:
            conn.exec_driver_sql('ALTER TABLE tasks ADD COLUMN "local user" TEXT;')
        if "request_headers" not in existing_columns:
            conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN request_headers TEXT;")

    @staticmethod
    def _normalize_task_row(row: dict) -> dict:
        normalized = dict(row)
        if "local user" in normalized and "local_user" not in normalized:
            normalized["local_user"] = normalized["local user"]
        return normalized

    def _ensure_status(self, status: str) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid GREMLIN task status {status}")

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
        stmt = (
            update(self.tasks_table)
            .where(self.tasks_table.c.md5sum == md5sum)
            .values(**fields)
        )
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

    def delete_task(self, md5sum: str) -> None:
        stmt = self.tasks_table.delete().where(self.tasks_table.c.md5sum == md5sum)
        with self.engine.begin() as conn:
            conn.execute(stmt)


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


def _env_bool(var_name: str, default: bool) -> bool:
    raw = os.environ.get(var_name)
    if raw is None or raw == "":
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"Environment variable {var_name} must be a boolean value "
        "(one of: true/false/1/0/yes/no/on/off)."
    )


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
    port: int
    public_dashboard: bool

    @classmethod
    def from_env(cls) -> "GremlinConfig":
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
            port=_env_int("PORT", 8080),
            public_dashboard=_env_bool("PUBLIC_DASHBOARD", False),
        )


CONFIG = GremlinConfig.from_env()


user_file = os.environ.get("USERS_FILE", os.path.join(THIS_DIR, "users.txt"))
user_file = os.path.abspath(user_file)

if not os.path.exists(user_file):
    raise FileNotFoundError(
        f"Unable to start GREMLIN server without user credentials. Expected file at {user_file}"
    )

# A dictionary of users and their hashed passwords
users = {}

with open(user_file) as f:
    for line in f:
        if line.strip() == "":
            continue
        if line.strip().startswith(("#", ";")):
            continue
        username, password = line.strip().split(":")
        users[username] = generate_password_hash(password)

ADMIN_USERS = set(_env_csv("ADMIN_USERS", "admin"))


# Celery configurations
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
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


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_for_log(value: str, max_len: int = 4096) -> str:
    cleaned = _CONTROL_CHARS.sub(" ", value)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


def _sanitize_headers_for_log(raw_headers: dict[str, str]) -> str:
    sanitized: dict[str, str] = {}
    for key, value in raw_headers.items():
        safe_key = _sanitize_for_log(str(key), max_len=256)
        safe_value = _sanitize_for_log(str(value), max_len=2048)
        if safe_key:
            sanitized[safe_key] = safe_value
    return json.dumps(sanitized, ensure_ascii=True, sort_keys=True)


def _request_metadata() -> dict[str, str | None]:
    ip = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("CF-Connecting-IPv6")
        or request.remote_addr
    )
    headers = {str(k): str(v) for k, v in request.headers.items()}
    return {
        "ip": ip,
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "username": auth.current_user() or "anonymous",
        "headers_json": _sanitize_headers_for_log(headers),
    }


def _local_user_identity() -> str:
    """Return username/group and uid/gid from fresh commands."""
    try:
        username = subprocess.run(["id", "-un"], check=True, capture_output=True, text=True).stdout.strip()
        groupname = subprocess.run(["id", "-gn"], check=True, capture_output=True, text=True).stdout.strip()
        uid = subprocess.run(["id", "-u"], check=True, capture_output=True, text=True).stdout.strip()
        gid = subprocess.run(["id", "-g"], check=True, capture_output=True, text=True).stdout.strip()
        if username and groupname and uid and gid:
            return _sanitize_for_log(f"{username}:{groupname}-{uid}:{gid}", max_len=256)
    except Exception:  # pylint: disable=broad-except
        pass

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
    task_id = task if isinstance(task, str) else task["md5sum"]
    return os.path.join(app.config["RESULTS_FOLDER"], f"{task_id}_PSSM_GREMLIN_results.zip")


def _virtual_upload_path(filename: str) -> str:
    safe_name = os.path.basename(filename or "unknown.fasta")
    return f"/srv/REvoDesign/PSSM_GREMLIN/upload/{safe_name}"


def _sanitize_task_error(task: dict[str, Any], error: Any) -> str | None:
    if error is None:
        return None
    message = str(error)
    file_path = str(task.get("file_path") or "")
    if file_path:
        message = message.replace(file_path, _virtual_upload_path(task.get("filename", "unknown.fasta")))
    return message


_RUNNING_TRACE_STEPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "hhblits",
        "hhblits: searching for co-evolutionary sequences",
        ("*_gremlin_hhblits.log", "*_gremlin_hhblits.err"),
    ),
    (
        "hhfilter",
        "hhfilter: filtering co-evolutionary",
        ("*_gremlin_hhfilter.log", "*_gremlin_hhfilter.err"),
    ),
    (
        "gremlin",
        "gremlin: calculating co-evolution signals",
        ("*_gremlin_tfv1.log", "*_gremlin_tfv1.err"),
    ),
    (
        "blast",
        "blast: searching for consensus profile",
        ("*_pssm_psiblast.log", "*_pssm_psiblast.err"),
    ),
)


def _running_stage_started(log_dir: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if glob(os.path.join(log_dir, pattern)):
            return True
    return False


def _build_running_trace(task: dict[str, Any]) -> str:
    if task.get("status") != "running":
        return ""

    default_lines = [label for _, label, _ in _RUNNING_TRACE_STEPS]
    result_dir = str(task.get("result_dir") or "")
    if not result_dir:
        return "\n".join(default_lines)
    log_dir = os.path.join(result_dir, "log")
    if not os.path.isdir(log_dir):
        return "\n".join(default_lines)

    started_flags = [bool(_running_stage_started(log_dir, patterns)) for _, _, patterns in _RUNNING_TRACE_STEPS]
    started_indices = [index for index, started in enumerate(started_flags) if started]
    current_index = max(started_indices) if started_indices else 0

    traced_lines: list[str] = []
    for index, (_, label, _) in enumerate(_RUNNING_TRACE_STEPS):
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
    _ROOT_MOUNT_DIRECTORY = os.path.abspath("/tmp/")
    os.makedirs(_ROOT_MOUNT_DIRECTORY, exist_ok=True)


@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


def _is_admin_user(username: str | None = None) -> bool:
    target = (username if username is not None else auth.current_user()) or ""
    return target in ADMIN_USERS


def _task_access_allowed(task: dict[str, Any]) -> bool:
    if _is_admin_user():
        return True
    if CONFIG.public_dashboard:
        return True
    current_user = auth.current_user() or ""
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
    return hashlib.md5(scoped_key.encode("utf-8")).hexdigest()


def _task_delete_allowed(task: dict[str, Any]) -> bool:
    current_user = auth.current_user() or ""
    if _is_admin_user(current_user):
        return True
    return bool(current_user) and task.get("username") == current_user


def _delete_task_artifacts(task: dict[str, Any]) -> None:
    result_dir = task.get("result_dir")
    if result_dir and os.path.isdir(result_dir):
        shutil.rmtree(result_dir, ignore_errors=True)
    zip_path = _task_zip_path(task)
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


def _create_mount(mount_name: str, path: str, read_only=True) -> tuple[types.Mount, str]:
    """Create a mount point for each file and directory used by the model."""
    path = os.path.abspath(path)
    target_path = os.path.join(_ROOT_MOUNT_DIRECTORY, mount_name)

    if not read_only:
        logging.warning(f"{mount_name} is not read-only!")

    if os.path.isdir(path):
        source_path = path
        mounted_path = target_path
    else:
        source_path = os.path.dirname(path)
        mounted_path = os.path.join(target_path, os.path.basename(path))
    if not os.path.exists(source_path):
        os.makedirs(source_path)
    logging.info(f"Mounting {source_path} -> {target_path}" )
    mount = types.Mount(
        target=str(target_path),
        source=str(source_path),
        type="bind",
        read_only=read_only,
    )
    return mount, str(mounted_path)


def _runner_thread_env(nproc: int) -> dict[str, str]:
    limited_nproc = max(1, int(nproc))
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
    }


def run_pssm_gremlin_in_docker(fasta_path, output_dir, docker_client=None):
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
    mount_uniref30_db, mounted_uniref30_db = _create_mount(mount_name="uniref30_db", path=os.path.dirname(uniref30_db), read_only=True)
    mounts.append(mount_uniref30_db)
    command_args.extend(["-U", os.path.join(mounted_uniref30_db, os.path.basename(uniref30_db))])

    uniref90_db = os.path.abspath(CONFIG.uniref90_db)
    
    mount_uniref90_db, mounted_uniref90_db = _create_mount(mount_name="uniref90_db", path=os.path.dirname(uniref90_db), read_only=True)
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
        user=CONFIG.docker_user,
        environment=_runner_thread_env(CONFIG.nproc),
        stdout=True,
        stderr=True,
    )

    stderr_lines: list[str] = []
    try:
        # Add signal handler to ensure CTRL+C also stops the running container.
        signal.signal(signal.SIGINT, lambda unused_sig, unused_frame: container.kill())

        for line in container.logs(stream=True):
            decoded = line.strip().decode("utf-8")
            if decoded:
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


def format_times(timestamp):
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    else:
        return None


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
        task_store.update_task(
            md5sum,
            status="failed",
            error="Uploaded FASTA file not found on disk",
            finished_at=time.time(),
        )
        logging.error("Uploaded file missing for task %s", md5sum)
        return

    start_time = task.get("started_at") or time.time()
    update_fields = {
        "status": "running",
        "error": None,
        "local_user": _local_user_identity(),
    }
    if not task.get("started_at"):
        update_fields["started_at"] = start_time
    task_store.update_task(md5sum, **update_fields)
    if task.get("request_headers"):
        logging.info("Request headers for task %s: %s", md5sum, _sanitize_for_log(task["request_headers"]))

    try:
        run_pssm_gremlin_in_docker(
            fasta_path=uploaded_file,
            output_dir=output_dir,
        )
        task_store.update_task(md5sum, status="packing results")
        refreshed_task = task_store.get_task(md5sum) or task
        _pack_results_archive(refreshed_task)
        finish_time = time.time()
        task_store.update_task(
            md5sum,
            status="finished",
            finished_at=finish_time,
            walltime=finish_time - start_time,
            error=None,
        )
    except docker.errors.ContainerError as exc:
        finish_time = time.time()
        task_store.update_task(
            md5sum,
            status="failed",
            finished_at=finish_time,
            walltime=finish_time - start_time,
            error=f"docker: {exc}",
        )
    except docker.errors.DockerException as exc:
        finish_time = time.time()
        task_store.update_task(
            md5sum,
            status="failed",
            finished_at=finish_time,
            walltime=finish_time - start_time,
            error=f"docker: {exc}",
        )
        logging.error("Docker daemon unavailable for GREMLIN task %s: %s", md5sum, exc)
    except Exception as exc:  # pylint: disable=broad-except
        finish_time = time.time()
        task_store.update_task(
            md5sum,
            status="failed",
            finished_at=finish_time,
            walltime=finish_time - start_time,
            error=str(exc),
        )
        logging.exception("Unexpected failure while running GREMLIN task %s", md5sum)


@app.route("/PSSM_GREMLIN/create_task", methods=["GET"])
@auth.login_required
def create_task():
    return render_template("create_task.html")


@app.route("/PSSM_GREMLIN/api/post", methods=["POST"])
@auth.login_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    uploaded_file = request.files["file"]
    if uploaded_file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    safe_filename = secure_filename(uploaded_file.filename)
    if not safe_filename:
        return jsonify({"error": "Invalid filename"}), 400

    if not safe_filename.lower().endswith(".fasta"):
        return (
            jsonify({"error": "Uploaded file must have the .fasta extension"}),
            400,
        )

    upload_path = os.path.abspath(os.path.join(app.config["UPLOAD_FOLDER"], safe_filename))
    uploaded_file.save(upload_path)

    hasher = hashlib.md5()
    with open(upload_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    content_md5 = hasher.hexdigest()
    metadata = _request_metadata()
    md5sum = _task_id_for_upload(content_md5, metadata["username"])

    existing_task = task_store.get_task(md5sum)
    if existing_task and not _task_access_allowed(existing_task):
        return _task_access_denied(md5sum)
    if existing_task and existing_task["status"] == "finished":
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)

    if existing_task and existing_task["status"] in {"pending", "running", "packing results"}:
        return jsonify({"status": "Task already queued or running", "md5sum": md5sum}), 202

    result_dir = os.path.join(app.config["RESULTS_FOLDER"], md5sum)
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir)
    os.makedirs(result_dir, exist_ok=True)
    result_fasta_path = os.path.join(result_dir, safe_filename)
    shutil.copy(upload_path, result_fasta_path)

    zip_path = _task_zip_path(md5sum)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    is_binary = _is_binary_file(upload_path)
    now = time.time()
    base_record = {
        "filename": safe_filename,
        "file_path": upload_path,
        "result_dir": result_dir,
        "uploaded_at": now,
        "started_at": None,
        "finished_at": None,
        "walltime": None,
        "is_binary": int(is_binary),
        "source_ip": metadata["ip"],
        "user_agent": metadata["user_agent"],
        "username": metadata["username"],
        "request_headers": metadata["headers_json"],
        "local_user": _local_user_identity(),
        "celery_task_id": None,
    }

    if is_binary:
        task_store.upsert_task(
            md5sum,
            **base_record,
            status="failed",
            error="Binary file uploads are not supported.",
        )
        return jsonify({"error": "Uploaded file contains binary content"}), 400

    task_store.upsert_task(
        md5sum,
        **base_record,
        status="pending",
        error=None,
    )

    async_result = run_gremlin_task.apply_async(args=[md5sum])
    task_store.update_task(md5sum, celery_task_id=async_result.id)

    return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)


@app.route("/PSSM_GREMLIN/api/running/<md5sum>", methods=["GET"])
@auth.login_required
def run_gremlin(md5sum):
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    status = task["status"]
    if status == "finished":
        return jsonify({"status": "finished", "md5sum": md5sum}), 200
    if status == "failed":
        return (
            jsonify({"status": "failed", "md5sum": md5sum, "error": _sanitize_task_error(task, task.get("error"))}),
            404,
        )
    if status == "running":
        return jsonify({"status": "running", "md5sum": md5sum}), 202
    if status == "pending":
        return jsonify({"status": "pending", "md5sum": md5sum}), 202
    if status == "packing results":
        return jsonify({"status": "packing results", "md5sum": md5sum}), 202
    if status == "cancelled":
        return jsonify({"status": "cancelled", "md5sum": md5sum}), 200

    return (
        jsonify({"status": "unknown", "md5sum": md5sum, "error": "Invalid task status"}),
        500,
    )


@app.route("/PSSM_GREMLIN/api/results/<md5sum>", methods=["GET"])
@auth.login_required
def get_results(md5sum):
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] != "finished":
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)

    return redirect(f"/PSSM_GREMLIN/api/download/{md5sum}", code=302)


@app.route("/PSSM_GREMLIN/api/download/<md5sum>", methods=["GET"])
@auth.login_required
def download_results(md5sum):
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] != "finished":
        return (
            jsonify(
                {
                    "status": "error",
                    "md5sum": md5sum,
                    "message": "results are not ready",
                }
            ),
            400,
        )

    zip_filename = _task_zip_path(task)
    if os.path.exists(zip_filename):
        return send_from_directory(
            app.config["RESULTS_FOLDER"],
            os.path.basename(zip_filename),
            as_attachment=True,
        )

    return (
        jsonify(
            {
                "status": "error",
                "md5sum": md5sum,
                "message": "result file not found",
            }
        ),
        404,
    )


@app.route("/PSSM_GREMLIN/api/cancel/<md5sum>", methods=["POST", "GET"])
@auth.login_required
def cancel_task(md5sum):
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] not in {"pending", "running"}:
        return (
            jsonify({"error": "Task cannot be cancelled as it is not pending or running"}),
            400,
        )

    celery_id = task.get("celery_task_id")
    if celery_id:
        try:
            result = AsyncResult(celery_id)
            result.revoke(terminate=True)
        except Exception as exc:  # pylint: disable=broad-except
            logging.warning("Failed to revoke Celery task %s: %s", celery_id, exc)

    now = time.time()
    started_at = task.get("started_at")
    walltime = (now - started_at) if started_at else None
    task_store.update_task(
        md5sum,
        status="cancelled",
        finished_at=now,
        walltime=walltime,
        error="Task cancelled by user",
    )
    return jsonify({"status": "cancelled", "md5sum": md5sum}), 200


@app.route("/PSSM_GREMLIN/dashboard", methods=["GET"])
@auth.login_required
def task_dashboard():
    current_user = auth.current_user() or ""
    is_admin = _is_admin_user(current_user)
    all_tasks = task_store.list_tasks()
    if is_admin or CONFIG.public_dashboard:
        visible_tasks = all_tasks
    else:
        visible_tasks = [task for task in all_tasks if task.get("username") == current_user]

    task_statuses = []
    for i, task in enumerate(visible_tasks):
        submitted_time = task.get("uploaded_at")
        finished_time = task.get("finished_at")
        walltime = task.get("walltime")
        if task.get("is_binary"):
            fasta_seq = "Binary file rejected"
        else:
            try:
                with open(task["file_path"]) as f:
                    fasta_seq = f.read().strip()
            except (OSError, UnicodeDecodeError) as exc:
                if isinstance(exc, FileNotFoundError):
                    fasta_seq = (
                        "Unable to read sequence: "
                        f"file not found at {_virtual_upload_path(task.get('filename', 'unknown.fasta'))}"
                    )
                else:
                    fasta_seq = (
                        "Unable to read sequence: "
                        f"file unavailable at {_virtual_upload_path(task.get('filename', 'unknown.fasta'))}"
                    )

        task_statuses.append(
            {
                "id": i,
                "md5": task["md5sum"],
                "status": task["status"],
                "fasta_fn": task["filename"],
                "submitted_time": format_times(submitted_time),
                "finished_time": format_times(finished_time) if finished_time else "-",
                "walltime": int(walltime) if walltime is not None else "-",
                "submitted_timestamp": submitted_time or 0,
                "sequence": fasta_seq,
                "owner": task.get("username") or "-",
                "can_delete": is_admin or (task.get("username") == current_user),
                "running_trace": _build_running_trace(task),
            }
        )

    sorted_task_statuses = sorted(task_statuses, key=lambda x: x["submitted_timestamp"], reverse=True)

    return render_template(
        "pssm_gremlin_dashboard.html",
        sorted_task_statuses=sorted_task_statuses,
        current_username=current_user,
        is_admin_user=is_admin,
    )


@app.route("/PSSM_GREMLIN/api/delete/<md5sum>", methods=["POST", "DELETE"])
@auth.login_required
def delete_task(md5sum):
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_delete_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] in {"pending", "running", "packing results"}:
        _revoke_celery_task(task)

    _delete_task_artifacts(task)
    task_store.delete_task(md5sum)
    return jsonify({"status": "deleted", "md5sum": md5sum}), 200


@app.route("/PSSM_GREMLIN/api/delete", methods=["POST"])
@auth.login_required
def delete_tasks_batch():
    payload = request.get_json(silent=True) or {}
    md5sums = payload.get("md5sums")
    if not isinstance(md5sums, list):
        return jsonify({"error": "md5sums must be a JSON list"}), 400

    deleted: list[str] = []
    not_found: list[str] = []
    ignored: list[str] = []
    forbidden: list[str] = []
    seen: set[str] = set()

    for raw_md5 in md5sums:
        md5sum = str(raw_md5).strip()
        if not md5sum or md5sum in seen:
            continue
        seen.add(md5sum)
        if not re.fullmatch(r"[a-fA-F0-9]{32}", md5sum):
            ignored.append(md5sum)
            continue

        task = task_store.get_task(md5sum)
        if not task:
            not_found.append(md5sum)
            continue
        if not _task_delete_allowed(task):
            forbidden.append(md5sum)
            continue

        if task["status"] in {"pending", "running", "packing results"}:
            _revoke_celery_task(task)
        _delete_task_artifacts(task)
        task_store.delete_task(md5sum)
        deleted.append(md5sum)

    return (
        jsonify(
            {
                "status": "ok",
                "deleted": deleted,
                "not_found": not_found,
                "ignored": ignored,
                "forbidden": forbidden,
            }
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=CONFIG.port)
