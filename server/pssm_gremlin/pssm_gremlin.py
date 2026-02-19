# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


#! /mnt/data/envs/conda_env/envs/REvoDesign/bin/python

from __future__ import annotations

import hashlib
import os
import shutil
import signal
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import docker
from absl import app, logging
from celery import Celery
from celery.result import AsyncResult
from docker import types
from flask import Flask, jsonify, redirect, render_template, request, send_from_directory
from flask_httpauth import HTTPBasicAuth
from sqlalchemy import Column, Float, Index, Integer, MetaData, String, Table, Text, create_engine, desc, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

THIS_FILE = os.path.abspath(__file__)
THIS_DIR = os.path.dirname(THIS_FILE)

app = Flask(__name__, template_folder="./templates")
auth = HTTPBasicAuth()

class TaskDatabase:
    """Minimal SQLite-based task tracker for GREMLIN jobs."""

    VALID_STATUSES = {"pending", "processing", "success", "failed", "cancelled"}

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
            Column("error", Text),
            Column("celery_task_id", String),
        )
        Index("idx_tasks_uploaded_at", self.tasks_table.c.uploaded_at)
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
            self.metadata.create_all(conn)

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
        return dict(row) if row else None

    def list_tasks(self) -> list[dict]:
        stmt = select(self.tasks_table).order_by(desc(self.tasks_table.c.uploaded_at))
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [dict(row) for row in rows]


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


def _resolve_docker_user() -> str:
    env_user = os.environ.get("PSSM_GREMLIN_RUNNER_USER")
    env_uid = os.environ.get("PSSM_GREMLIN_RUNNER_UID")
    env_gid = os.environ.get("PSSM_GREMLIN_RUNNER_GID")

    if env_user:
        return env_user

    if env_uid and env_gid:
        return f"{env_uid}:{env_gid}"

    if env_uid:
        return env_uid

    try:
        return f"{os.geteuid()}:{os.getegid()}"
    except AttributeError:
        return "0:0"


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

    @classmethod
    def from_env(cls) -> "GremlinConfig":
        server_dir = _env_path("PSSM_GREMLIN_SERVER_DIR", "/mnt/data/yinying/server/")
        upload_folder = os.path.join(server_dir, "upload")
        results_folder = os.path.join(server_dir, "results")
        return cls(
            server_dir=server_dir,
            upload_folder=upload_folder,
            results_folder=results_folder,
            db_path=_env_path("PSSM_GREMLIN_DB_PATH", os.path.join(server_dir, "pssm_gremlin.sqlite3")),
            docker_image=os.environ.get("PSSM_GREMLIN_RUNNER_IMAGE", "revodesign-pssm-gremlin"),
            docker_user=_resolve_docker_user(),
            uniref30_db=_env_path(
                "PSSM_GREMLIN_DB_UNIREF30",
                "/mnt/db/uniref30_uc30/UniRef30_2022_02/UniRef30_2022_02",
            ),
            uniref90_db=_env_path("PSSM_GREMLIN_DB_UNIREF90", "/mnt/db/uniref90/uniref90"),
            nproc=_env_int("PSSM_GREMLIN_NPROC", 16),
            port=_env_int("PSSM_GREMLIN_PORT", 8080),
        )


CONFIG = GremlinConfig.from_env()


user_file = os.environ.get("PSSM_GREMLIN_USERS_FILE", os.path.join(THIS_DIR, "users.txt"))
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


# Celery configurations
redis_url = os.environ.get("PSSM_GREMLIN_REDIS_URL", "redis://localhost:6379/0")
celery_backend = os.environ.get("PSSM_GREMLIN_RESULT_BACKEND", redis_url)
celery_broker = os.environ.get("PSSM_GREMLIN_BROKER_URL", redis_url)
celery = Celery(
    app.name,
    broker=celery_broker,
    backend=celery_backend,
)

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


def _request_metadata() -> dict[str, str | None]:
    ip = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("CF-Connecting-IPv6")
        or request.remote_addr
    )
    return {
        "ip": ip,
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "username": auth.current_user() or "anonymous",
    }


def _task_zip_path(task: Any) -> str:
    filename = task if isinstance(task, str) else task["filename"]
    base = os.path.splitext(filename)[0]
    return os.path.join(app.config["RESULTS_FOLDER"], f"{base}_PSSM_GREMLIN_results.zip")


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
    logging.info("Mounting %s -> %s", source_path, target_path)
    mount = types.Mount(
        target=str(target_path),
        source=str(source_path),
        type="bind",
        read_only=read_only,
    )
    return mount, str(mounted_path)


def run_pssm_gremlin_in_docker(fasta_path, output_dir, docker_client=None):
    mounts = []
    command_args = []

    if os.path.exists(fasta_path):
        fasta = os.path.abspath(fasta_path)
        mount_fasta, mounted_fasta = _create_mount(mount_name="fasta", path=fasta, read_only=True)
        mounts.append(mount_fasta)
        command_args.append(f"-i {mounted_fasta}")

    os.makedirs(output_dir, exist_ok=True)
    output = os.path.abspath(output_dir)
    mount_output, mounted_output = _create_mount(mount_name="output", path=output, read_only=False)
    mounts.append(mount_output)
    command_args.append(f"-o {mounted_output}")

    uniref30_db = os.path.abspath(CONFIG.uniref30_db)
    mount_uniref30_db, mounted_uniref30_db = _create_mount(mount_name="uniref30_db", path=uniref30_db, read_only=True)
    mounts.append(mount_uniref30_db)
    command_args.append(f"-U {mounted_uniref30_db}")

    uniref90_db = os.path.abspath(CONFIG.uniref90_db)
    mount_uniref90_db, mounted_uniref90_db = _create_mount(mount_name="uniref90_db", path=uniref90_db, read_only=True)
    mounts.append(mount_uniref90_db)
    command_args.append(f"-u {mounted_uniref90_db}")

    command_args.append(f"-j {CONFIG.nproc}")

    logging.info(command_args)

    client = docker_client or docker.from_env()

    container = client.containers.run(
        image=CONFIG.docker_image,
        command=command_args,
        remove=True,
        detach=True,
        mounts=mounts,
        user=CONFIG.docker_user,
        stdout=True,
        stderr=True,
    )

    # Add signal handler to ensure CTRL+C also stops the running container.
    signal.signal(signal.SIGINT, lambda unused_sig, unused_frame: container.kill())

    for line in container.logs(stream=True):
        logging.info(line.strip().decode("utf-8"))

    return


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

    if task["status"] not in {"pending", "processing"}:
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
    update_fields = {"status": "processing", "error": None}
    if not task.get("started_at"):
        update_fields["started_at"] = start_time
    task_store.update_task(md5sum, **update_fields)

    try:
        run_pssm_gremlin_in_docker(
            fasta_path=uploaded_file,
            output_dir=output_dir,
        )
        finish_time = time.time()
        task_store.update_task(
            md5sum,
            status="success",
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
    md5sum = hasher.hexdigest()

    existing_task = task_store.get_task(md5sum)
    if existing_task and existing_task["status"] == "success":
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)

    if existing_task and existing_task["status"] in {"pending", "processing"}:
        return jsonify({"status": "Task already queued or running", "md5sum": md5sum}), 202

    result_dir = os.path.join(app.config["RESULTS_FOLDER"], md5sum)
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir)
    os.makedirs(result_dir, exist_ok=True)
    result_fasta_path = os.path.join(result_dir, safe_filename)
    shutil.copy(upload_path, result_fasta_path)

    zip_path = _task_zip_path(safe_filename)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    metadata = _request_metadata()
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

    status = task["status"]
    if status == "success":
        return jsonify({"status": "success", "md5sum": md5sum}), 200
    if status == "failed":
        return (
            jsonify({"status": "failed", "md5sum": md5sum, "error": task.get("error")}),
            404,
        )
    if status == "processing":
        return jsonify({"status": "processing", "md5sum": md5sum}), 202
    if status == "pending":
        return jsonify({"status": "pending", "md5sum": md5sum}), 202
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

    if task["status"] != "success":
        return redirect(f"/PSSM_GREMLIN/api/running/{md5sum}", code=302)

    zip_filename = _task_zip_path(task)
    if not os.path.exists(zip_filename):
        shutil.make_archive(os.path.splitext(zip_filename)[0], "zip", task["result_dir"])

    return redirect(f"/PSSM_GREMLIN/api/download/{md5sum}", code=302)


@app.route("/PSSM_GREMLIN/api/download/<md5sum>", methods=["GET"])
@auth.login_required
def download_results(md5sum):
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404

    if task["status"] != "success":
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

    if task["status"] not in {"pending", "processing"}:
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
    task_statuses = []
    for i, task in enumerate(task_store.list_tasks()):
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
                fasta_seq = f"Unable to read sequence: {exc}"

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
            }
        )

    sorted_task_statuses = sorted(task_statuses, key=lambda x: x["submitted_timestamp"], reverse=True)

    return render_template("pssm_gremlin_dashboard.html", sorted_task_statuses=sorted_task_statuses)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=CONFIG.port)
