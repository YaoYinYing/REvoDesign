# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Celery and GREMLIN task runtime.

This module is intentionally independent of Flask authentication.  Importing it
may initialize the shared task store and task directories, but never imports or
opens the user database.
"""

from __future__ import annotations

import grp
import logging
import os
import pwd
import re
import shutil
import signal
import time
from datetime import datetime
from typing import Any

import docker
from celery import Celery
from docker import types
from pssm_gremlin_server.config import GremlinConfig, ensure_directories, env_path
from pssm_gremlin_server.db import TaskDatabase

CONFIG = GremlinConfig.from_env()

_redis_password = os.environ.get("REDIS_PASSWORD", "")
_redis_auth = f":{_redis_password}@" if _redis_password else ""
redis_url = os.environ.get("REDIS_URL", f"redis://{_redis_auth}localhost:6379/0")
celery = Celery(
    "pssm_gremlin_server",
    broker=os.environ.get("BROKER_URL", redis_url),
    backend=os.environ.get("RESULT_BACKEND", redis_url),
)
celery.conf.broker_connection_retry_on_startup = True

os.environ["GREMLIN_CALC_CPU_NUM"] = str(CONFIG.nproc)

task_store = TaskDatabase(CONFIG.db_path)
ensure_directories(CONFIG.upload_folder, CONFIG.results_folder)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_TASK_ID_PATTERN = re.compile(r"[a-fA-F0-9]{32}$")
_ROOT_MOUNT_DIRECTORY = env_path("RUNNER_HOST_ROOT", os.path.dirname(CONFIG.server_dir))

_RUNNING_TRACE_STEPS: tuple[tuple[str, str], ...] = (
    ("hhblits", "hhblits: searching for co-evolutionary sequences"),
    ("hhfilter", "hhfilter: filtering co-evolutionary"),
    ("gremlin", "gremlin: calculating co-evolution signals"),
    ("blast", "blast: searching for consensus profile"),
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
    return _safe_join(CONFIG.results_folder, f"{task_id}_PSSM_GREMLIN_results.zip")


def _virtual_upload_path(filename: str) -> str:
    safe_name = os.path.basename(filename or "unknown.fasta")
    return f"/srv/REvoDesign/PSSM_GREMLIN/upload/{safe_name}"


def _sanitize_task_error(task: dict[str, Any], error: Any) -> str | None:
    """Redact internal filesystem paths from errors exposed to clients."""
    if error is None:
        return None
    message = str(error)
    file_path = str(task.get("file_path") or "")
    if file_path:
        message = message.replace(file_path, _virtual_upload_path(task.get("filename", "unknown.fasta")))
    if CONFIG.server_dir and CONFIG.server_dir in message:
        message = message.replace(CONFIG.server_dir, "<server_dir>")
    result_dir = str(task.get("result_dir") or "")
    if result_dir and result_dir in message:
        message = message.replace(result_dir, "<result_dir>")
    return message


def _extract_stage_from_log_line(line: str) -> str | None:
    marker_pos = line.find(_RUNNER_STAGE_PREFIX)
    if marker_pos < 0:
        return None
    raw_marker = line[marker_pos + len(_RUNNER_STAGE_PREFIX) :].strip().lower()
    if not raw_marker:
        return None
    return _RUNNER_STAGE_ALIASES.get(raw_marker.split()[0])


def _build_running_trace(task: dict[str, Any]) -> str:
    if task.get("status") != "running":
        return ""
    current_stage = str(task.get("run_stage") or "").strip().lower()
    current_index = _RUNNING_STAGE_INDEX.get(current_stage, 0)
    traced_lines: list[str] = []
    for index, (_, label) in enumerate(_RUNNING_TRACE_STEPS):
        marker = "done" if index < current_index else "running" if index == current_index else "pending"
        traced_lines.append(f"{label} [{marker}]")
    return "\n".join(traced_lines)


def _is_terminal_status(status: Any) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in {
        "deleted:finshed",
        "deleted:cancel",
        "deleting:finished",
        "deleting:cancel",
        "cleaned:finished",
        "cleaned:cancel",
        "cancelled",
    }


def _task_is_terminal(md5sum: str) -> bool:
    task = task_store.get_task(md5sum)
    return bool(task and _is_terminal_status(task.get("status")))


def _create_mount(mount_name: str, path: str, read_only: bool = True) -> tuple[types.Mount, str]:
    """Create a runner mount point for a file or directory."""
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
    return (
        types.Mount(target=str(target_path), source=str(source_path), type="bind", read_only=read_only),
        str(mounted_path),
    )


def _runner_thread_env(nproc: int, maxmem: int) -> dict[str, str]:
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
        "MAXMEM": str(max(1, int(maxmem))),
    }


def run_pssm_gremlin_in_docker(fasta_path, output_dir, docker_client=None, stage_callback=None):
    mounts = []
    command_args = []
    if os.path.exists(fasta_path):
        fasta = os.path.abspath(fasta_path)
        mount_fasta, mounted_fasta = _create_mount("fasta", fasta, read_only=True)
        mounts.append(mount_fasta)
        command_args.extend(["-i", mounted_fasta])

    os.makedirs(output_dir, exist_ok=True)
    mount_output, mounted_output = _create_mount("output", os.path.abspath(output_dir), read_only=False)
    mounts.append(mount_output)
    command_args.extend(["-o", mounted_output])

    uniref30_db = os.path.abspath(CONFIG.uniref30_db)
    mount_uniref30, mounted_uniref30 = _create_mount(
        "uniref30_db", os.path.dirname(uniref30_db), read_only=True
    )
    mounts.append(mount_uniref30)
    command_args.extend(["-U", os.path.join(mounted_uniref30, os.path.basename(uniref30_db))])

    uniref90_db = os.path.abspath(CONFIG.uniref90_db)
    mount_uniref90, mounted_uniref90 = _create_mount(
        "uniref90_db", os.path.dirname(uniref90_db), read_only=True
    )
    mounts.append(mount_uniref90)
    command_args.extend(["-u", os.path.join(mounted_uniref90, os.path.basename(uniref90_db))])
    command_args.extend(["-j", str(CONFIG.nproc)])

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


def _pack_results_archive(task: dict) -> None:
    zip_filename = _task_zip_path(task)
    zip_base = os.path.splitext(zip_filename)[0]
    if os.path.exists(zip_filename):
        os.remove(zip_filename)
    shutil.make_archive(zip_base, "zip", task["result_dir"])
    if os.path.isdir(task["result_dir"]):
        shutil.rmtree(task["result_dir"])


def _pack_failed_results_archive(task: dict, error: Any) -> None:
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
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S") if timestamp else None


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
        task_store.update_task(md5sum, status="failed", error=error_message, finished_at=time.time())
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
        if stage == stage_state["current"] or _task_is_terminal(md5sum):
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
            return
        _pack_results_archive(refreshed_task)
        refreshed_task = task_store.get_task(md5sum) or refreshed_task
        if _is_terminal_status(refreshed_task.get("status")):
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
        _record_failure(md5sum, task, start_time, stage_state["current"], f"docker: {exc}")
    except docker.errors.DockerException as exc:
        _record_failure(md5sum, task, start_time, stage_state["current"], f"docker: {exc}")
        logging.error("Docker daemon unavailable for GREMLIN task %s: %s", md5sum, exc)
    except Exception as exc:  # pylint: disable=broad-except
        _record_failure(md5sum, task, start_time, stage_state["current"], str(exc))
        logging.exception("Unexpected failure while running GREMLIN task %s", md5sum)


def _record_failure(md5sum: str, task: dict, start_time: float, run_stage: str, error_message: str) -> None:
    finish_time = time.time()
    if _task_is_terminal(md5sum):
        return
    _pack_failed_results_archive(task, error_message)
    task_store.update_task(
        md5sum,
        status="failed",
        finished_at=finish_time,
        walltime=finish_time - start_time,
        error=error_message,
        run_stage=run_stage,
    )
