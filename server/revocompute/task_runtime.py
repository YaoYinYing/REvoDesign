# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Celery and compute task runtime.

This module is intentionally independent of Flask authentication.  Importing it
may initialize the shared task store and task directories, but never imports or
opens the user database.
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import re
import time
import zipfile
from datetime import datetime
from typing import Any

from celery import Celery
from revocompute.config import ComputeConfig, ensure_directories, env_csv, env_path
from revocompute.db import TaskDatabase
from revocompute.job import Job, JobState
from revocompute.job.runners.docker_runner import DockerJob
from revocompute.job.runners.slurm_runner import SlurmJob
from revocompute.manage_db import ManageDatabase  # noqa: E402
from revocompute.resource_policy import ResolvedResources, ResourceValidationError
from revocompute.task_types import get as _get_task_type
from revocompute.task_types import get_job_executor as _get_job_executor
from revocompute.task_types import load_registry as _load_task_registry
from revocompute.task_types import register as _register_tt  # noqa: F401 -- test/plugin compatibility

import docker

CONFIG = ComputeConfig.from_env()
_manage_db = ManageDatabase(CONFIG.manage_db_path)

_redis_password = os.environ.get("REDIS_PASSWORD", "")
_redis_auth = f":{_redis_password}@" if _redis_password else ""
redis_url = os.environ.get("REDIS_URL", f"redis://{_redis_auth}localhost:6379/0")
celery = Celery(
    "revocompute",
    broker=os.environ.get("BROKER_URL", redis_url),
    backend=os.environ.get("RESULT_BACKEND", redis_url),
)
celery.conf.broker_connection_retry_on_startup = True

task_store = TaskDatabase(CONFIG.db_path)
ensure_directories(CONFIG.upload_folder, CONFIG.workspace_folder, CONFIG.results_folder)

# Load the task type registry — shared by web and worker processes.
# gremlin is always enabled; additional runners are gated by ENABLED_TASKRUNNERS.
_enabled_runners = set(env_csv("ENABLED_TASKRUNNERS", ""))
_load_task_registry(CONFIG.task_types_config, CONFIG.runners_dir, _enabled_runners)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_TASK_ID_PATTERN = re.compile(r"[a-fA-F0-9]{32}$")
_ROOT_MOUNT_DIRECTORY = env_path("RUNNER_HOST_ROOT", os.path.dirname(CONFIG.server_dir))
ROOT_MOUNT_DIRECTORY = _ROOT_MOUNT_DIRECTORY

# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------


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
    import grp
    import pwd

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


# ---------------------------------------------------------------------------
# Task zip path — generic (not GREMLIN-specific)
# ---------------------------------------------------------------------------


def _task_zip_path(task: Any) -> str:
    raw_task_id = task if isinstance(task, str) else task["md5sum"]
    task_id = _normalize_task_id(raw_task_id)
    if task_id is None:
        raise ValueError(f"Invalid task id for result archive: {raw_task_id!r}")
    return _safe_join(CONFIG.results_folder, f"{task_id}_results.zip")


def _virtual_upload_path(filename: str) -> str:
    safe_name = os.path.basename(filename or "unknown")
    return f"/srv/REvoDesign/compute/upload/{safe_name}"


# ---------------------------------------------------------------------------
# Stage tracking
# ---------------------------------------------------------------------------


def _build_running_trace(task: dict[str, Any]) -> str:
    """Build a human-readable running trace from task stage markers."""
    if task.get("status") != "running":
        return ""
    task_type_name = task.get("task_type", "gremlin")
    try:
        tt, _ = _get_task_type(task_type_name)
    except KeyError:
        return ""
    stages = list(tt.stage_markers.items())
    if not stages:
        return ""
    current_stage = str(task.get("run_stage") or stages[0][0]).strip().lower()
    stage_keys = [s[0] for s in stages]
    try:
        current_index = stage_keys.index(current_stage)
    except ValueError:
        current_index = 0
    lines: list[str] = []
    for index, (_, label) in enumerate(stages):
        if index < current_index:
            marker = "done"
        elif index == current_index:
            marker = "running"
        else:
            marker = "pending"
        lines.append(f"{label} [{marker}]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Error sanitization
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Job dispatch (Docker / SLURM)
# ---------------------------------------------------------------------------


def _create_job(
    task_id: str,
    tt,
    runner,
    entities: list[dict],
    output_dir: str,
    stage_callback=None,
    username: str = "",
    resource_policy: ResolvedResources | None = None,
) -> Job:
    """Factory: return the correct Job subclass for the runner config."""
    if _get_job_executor() == "slurm":
        return SlurmJob(
            task_id,
            tt,
            runner,
            entities,
            output_dir,
            stage_callback=stage_callback,
            manage_db=_manage_db,
            username=username,
            resource_policy=resource_policy,
        )
    return DockerJob(
        task_id,
        tt,
        runner,
        entities,
        output_dir,
        stage_callback=stage_callback,
        manage_db=_manage_db,
        resource_policy=resource_policy,
    )


def _run_compute_job(
    task_id: str,
    tt,
    runner,
    entities: list[dict],
    output_dir: str,
    stage_callback=None,
    username: str = "",
    resource_policy: ResolvedResources | None = None,
) -> JobState:
    """Unified submit + poll — same flow for Docker and SLURM."""
    job = _create_job(
        task_id,
        tt,
        runner,
        entities,
        output_dir,
        stage_callback,
        username=username,
        resource_policy=resource_policy,
    )
    jid = job.submit()
    # Persist the job handle so cancel can stop the running process even
    # after a server restart (Celery/Redis state is ephemeral).
    if jid:
        if isinstance(job, SlurmJob):
            task_store.update_task(task_id, slurm_job_id=jid)
        elif isinstance(job, DockerJob):
            task_store.update_task(task_id, container_id=jid)
    return job.poll()


# ---------------------------------------------------------------------------
# Result finalization and optional archive cache
# ---------------------------------------------------------------------------


_TEXT_PREVIEW_EXTENSIONS = {
    ".a3m",
    ".aln",
    ".csv",
    ".fa",
    ".faa",
    ".fasta",
    ".json",
    ".log",
    ".md",
    ".mrf",
    ".pdb",
    ".sto",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
_STRUCTURE_PREVIEW_EXTENSIONS = {".cif", ".mmcif", ".pdb"}
_IMAGE_PREVIEW_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}


# PTC-W6004: internal utility — callers pass server-built snapshot paths only
def _sha256_file(path: str) -> str:  # skipcq: PTC-W6004
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preview_kind(relative_path: str) -> str | None:
    extension = os.path.splitext(relative_path)[1].lower()
    if extension in _STRUCTURE_PREVIEW_EXTENSIONS:
        return "structure"
    if extension in _IMAGE_PREVIEW_EXTENSIONS:
        return "image"
    if extension in {".csv", ".tsv"}:
        return "table"
    if extension in _TEXT_PREVIEW_EXTENSIONS:
        return "text"
    return None


def _finalize_results_manifest(task: dict) -> dict[str, Any]:
    """Atomically publish the immutable result-tree inventory for a task."""
    result_dir = os.path.abspath(task["result_dir"])
    os.makedirs(result_dir, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    for root, dirs, files in os.walk(result_dir, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
        for filename in sorted(files):
            path = os.path.join(root, filename)
            relative_path = os.path.relpath(path, result_dir).replace(os.sep, "/")
            if relative_path in {"manifest.json", ".manifest.json.tmp"} or os.path.islink(path):
                continue
            stat = os.stat(path, follow_symlinks=False)
            artifact = {
                "path": relative_path,
                "size": stat.st_size,
                "sha256": _sha256_file(path),
                "media_type": mimetypes.guess_type(relative_path)[0] or "application/octet-stream",
                "preview": _preview_kind(relative_path),
            }
            if relative_path.startswith("execution/slurm-") and relative_path.endswith((".stdout.log", ".stderr.log")):
                artifact["role"] = "diagnostic"
            artifacts.append(artifact)
    manifest = {
        "schema_version": 1,
        "task_id": task["md5sum"],
        "task_type": task.get("task_type", "gremlin"),
        "created_at": datetime.now().astimezone().isoformat(),
        "artifacts": artifacts,
        "total_size": sum(item["size"] for item in artifacts),
    }
    temporary = _safe_join(result_dir, ".manifest.json.tmp")
    destination = _safe_join(result_dir, "manifest.json")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)
    return manifest


def _build_results_archive(task: dict) -> str:
    """Build an optional ZIP from the artifacts published in the manifest."""
    zip_filename = _task_zip_path(task)
    result_dir = os.path.abspath(task["result_dir"])
    manifest_path = _safe_join(result_dir, "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise FileNotFoundError("Result manifest is not finalized") from exc
    temporary_zip = f"{os.path.splitext(zip_filename)[0]}.tmp-{os.getpid()}-{time.time_ns()}.zip"
    try:
        with zipfile.ZipFile(temporary_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(manifest_path, "manifest.json")
            for artifact in manifest.get("artifacts", []):
                relative_path = artifact.get("path", "")
                parts = relative_path.split("/")
                if not relative_path or any(part in {"", ".", ".."} for part in parts):
                    raise ValueError("Result manifest contains an invalid artifact path")
                path = _safe_join(result_dir, *parts)
                if os.path.islink(path) or not os.path.isfile(path):
                    raise FileNotFoundError(f"Published result artifact is unavailable: {relative_path}")
                archive.write(path, relative_path)
        os.replace(temporary_zip, zip_filename)
    finally:
        if os.path.exists(temporary_zip):
            os.unlink(temporary_zip)
    return zip_filename


def _finalize_failed_results(task: dict, error: Any) -> None:
    result_dir = task.get("result_dir")
    if not result_dir:
        return
    try:
        os.makedirs(result_dir, exist_ok=True)
        report_path = os.path.join(result_dir, "task_failed.txt")
        message = _sanitize_task_error(task, error) or "Task failed."
        task_type_name = task.get("task_type", "gremlin")
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(f"REvoDesign {task_type_name} task failed\n")
            handle.write(f"Task ID: {task.get('md5sum', 'unknown')}\n")
            handle.write(f"Input: {task.get('filename', 'unknown')}\n\n")
            handle.write(message)
            handle.write("\n")
        _finalize_results_manifest(task)
    except Exception as exc:  # pylint: disable=broad-except
        logging.warning("Failed to finalize failed task %s: %s", task.get("md5sum"), exc)


# ---------------------------------------------------------------------------
# Formatting utilities
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------


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


def _record_failure(md5sum: str, task: dict, start_time: float, run_stage: str, error_message: str) -> None:
    finish_time = time.time()
    if _task_is_terminal(md5sum):
        return
    _finalize_failed_results(task, error_message)
    task_store.update_task(
        md5sum,
        status="failed",
        finished_at=finish_time,
        walltime=finish_time - start_time,
        error=error_message,
        run_stage=run_stage,
    )


# ---------------------------------------------------------------------------
# Core task implementation (Celery-agnostic — called by both task wrappers)
# ---------------------------------------------------------------------------


def _execute_compute_task(md5sum: str, task_type: str = "gremlin", params: dict | None = None):
    """Core task logic — shared by legacy and generic Celery task wrappers.

    Reads entities from the task's ``input_form`` column.  The ``params``
    argument is retained for the Celery signature but is ignored in favor
    of the DB record.
    """
    task = task_store.get_task(md5sum)
    if not task:
        logging.error("Task %s missing from database", md5sum)
        return
    if task["status"] not in {"pending", "queued", "running"}:
        return

    try:
        tt, runner = _get_task_type(task_type)
    except KeyError:
        _record_failure(md5sum, task, time.time(), "", f"Unknown task type: {task_type!r}")
        return

    output_dir = task["result_dir"]

    # Parse entities from the input_form JSON blob
    raw_form = task.get("input_form")
    entities: list[dict] = []
    resource_policy: ResolvedResources | None = None
    if raw_form:
        try:
            parsed = json.loads(raw_form) if isinstance(raw_form, str) else raw_form
            entities = parsed.get("entities", [])
            if parsed.get("resource_policy"):
                resource_policy = ResolvedResources.from_snapshot(parsed["resource_policy"])
        except (json.JSONDecodeError, TypeError, ResourceValidationError):
            logging.warning("Task %s: input_form or resource policy is invalid.", md5sum)
            _record_failure(md5sum, task, time.time(), "", "Task input or resource policy is invalid")
            return

    # Verify file entities reference existing files
    for fe in [e for e in entities if e["type"] == "file"]:
        upload_file = os.path.join(CONFIG.upload_folder, f"{fe['hash']}.upload")
        if not os.path.lexists(upload_file):
            error_message = f"Uploaded input file not found: {upload_file}"
            _finalize_failed_results(task, error_message)
            task_store.update_task(md5sum, status="failed", error=error_message, finished_at=time.time())
            logging.error("Uploaded file missing for task %s: %s", md5sum, upload_file)
            return
        snapshot_path = str(fe.get("snapshot_path") or "")
        if (
            not snapshot_path
            or not _path_is_within(CONFIG.workspace_folder, snapshot_path)
            or os.path.islink(snapshot_path)
            or not os.path.isfile(snapshot_path)
            or _sha256_file(snapshot_path) != fe["hash"]
        ):
            error_message = f"Immutable input snapshot is missing or changed: {fe.get('relative_path', 'unknown')}"
            _finalize_failed_results(task, error_message)
            task_store.update_task(md5sum, status="failed", error=error_message, finished_at=time.time())
            logging.error("Input snapshot verification failed for task %s", md5sum)
            return

    stages = list(tt.stage_markers.items())
    start_time = task.get("started_at") or time.time()
    current_stage = str(task.get("run_stage") or (stages[0][0] if stages else "")).strip().lower()

    is_slurm = _get_job_executor() == "slurm"
    initial_status = "queued" if is_slurm else "running"
    update_fields: dict[str, Any] = {
        "status": initial_status,
        "error": None,
        "local_user": _local_user_identity(),
        "run_stage": current_stage,
    }
    if not task.get("started_at"):
        update_fields["started_at"] = start_time
    task_store.update_task(md5sum, **update_fields)
    if task.get("request_headers"):
        logging.info("Request headers for task %s: %s", md5sum, _sanitize_for_log(task["request_headers"]))

    stage_state = {"current": current_stage, "first": True}

    def _on_stage_change(stage: str) -> None:
        if _task_is_terminal(md5sum):
            return
        stage_changed = stage != stage_state["current"]
        stage_state["current"] = stage
        if stage_state.get("first"):
            stage_state["first"] = False
            task_store.update_task(md5sum, status="running", run_stage=stage)
        elif stage_changed:
            task_store.update_task(md5sum, run_stage=stage)

    try:
        job_kwargs = {
            "task_id": md5sum,
            "tt": tt,
            "runner": runner,
            "entities": entities,
            "output_dir": output_dir,
            "stage_callback": _on_stage_change,
            "username": task.get("username", ""),
        }
        if resource_policy is not None:
            job_kwargs["resource_policy"] = resource_policy
        final_state = _run_compute_job(**job_kwargs)
        if _task_is_terminal(md5sum):
            logging.info("Task %s was deleted during execution; skipping result packing and finalization.", md5sum)
            return

        if final_state == JobState.FAILED:
            _record_failure(
                md5sum,
                task,
                start_time,
                stage_state["current"],
                "SLURM job failed — check job logs for details",
            )
            return
        if final_state == JobState.CANCELLED:
            task_store.update_task(md5sum, status="cancelled", finished_at=time.time())
            return

        final_stage = stage_state["current"] or (stages[-1][0] if stages else "")
        refreshed_task = task_store.get_task(md5sum) or task
        if _is_terminal_status(refreshed_task.get("status")):
            return
        _finalize_results_manifest(refreshed_task)
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
        logging.error("Docker daemon unavailable for task %s (type=%s): %s", md5sum, task_type, exc)
    except Exception as exc:  # pylint: disable=broad-except
        _record_failure(md5sum, task, start_time, stage_state["current"], str(exc))
        logging.exception("Unexpected failure while running task %s (type=%s)", md5sum, task_type)


# ---------------------------------------------------------------------------
# Orphaned-task recovery after server restart
# ---------------------------------------------------------------------------


def _recover_orphaned_tasks() -> int:
    """Scan for running tasks whose Celery task was lost (e.g. Redis restart).

    Docker containers are reconnected and polled inline.  SLURM jobs are
    re-queued as lightweight polling tasks.
    """
    recovered = 0
    for task in task_store.list_tasks():
        if task.get("status") != "running":
            continue
        container_id = str(task.get("container_id") or "")
        slurm_job_id = str(task.get("slurm_job_id") or "")
        if not container_id and not slurm_job_id:
            continue
        md5sum = task["md5sum"]
        task_type = task.get("task_type", "gremlin")
        logging.info("Recovery: checking orphaned task %s", md5sum)

        from revocompute.task_types import get as _gt

        if container_id:
            try:
                from revocompute.job.runners.docker_runner import DockerJob

                tt, runner = _gt(task_type)
                job = DockerJob(md5sum, tt, runner, [], task["result_dir"])
                if job.reconnect(container_id):
                    logging.info("Recovery: reconnected Docker %s for %s", container_id, md5sum)
                    state = job.poll()
                    _finalize_after_poll(md5sum, task, tt, state)
                    recovered += 1
                else:
                    _record_failure(md5sum, task, task.get("started_at") or time.time(), "",
                                    "Docker container not found after server restart")
            except Exception as exc:
                logging.error("Recovery failed for Docker task %s: %s", md5sum, exc)
                _record_failure(md5sum, task, task.get("started_at") or time.time(), "",
                                f"Recovery error: {exc}")

        elif slurm_job_id:
            try:
                from revocompute.job.runners.slurm_runner import SlurmJob

                tt, runner = _gt(task_type)
                job = SlurmJob(md5sum, tt, runner, [], task["result_dir"])
                if job.reconnect(slurm_job_id):
                    logging.info("Recovery: SLURM job %s still running for %s, re-queuing poll",
                                 slurm_job_id, md5sum)
                    run_compute_task.apply_async(
                        args=[md5sum], kwargs={"task_type": task_type, "recover_slurm": slurm_job_id}
                    )
                    recovered += 1
                else:
                    _record_failure(md5sum, task, task.get("started_at") or time.time(), "",
                                    "SLURM job not found after server restart")
            except Exception as exc:
                logging.error("Recovery failed for SLURM task %s: %s", md5sum, exc)
    return recovered


def _finalize_after_poll(md5sum, task, tt, state):
    """Publish results or record failure after a recovered job completes."""
    if state == JobState.FAILED:
        _record_failure(md5sum, task, task.get("started_at") or time.time(), "",
                        "Recovered compute job failed")
    elif state == JobState.CANCELLED:
        task_store.update_task(md5sum, status="cancelled", finished_at=time.time())
    else:
        refreshed = task_store.get_task(md5sum) or task
        if _is_terminal_status(refreshed.get("status")):
            return
        _finalize_results_manifest(refreshed)
        refreshed = task_store.get_task(md5sum) or refreshed
        if _is_terminal_status(refreshed.get("status")):
            return
        finish_time = time.time()
        task_store.update_task(
            md5sum,
            status="finished",
            finished_at=finish_time,
            walltime=finish_time - (task.get("started_at") or finish_time),
            error=None,
            run_stage=list(tt.stage_markers.items())[-1][0] if tt.stage_markers else "",
        )


try:
    @celery.on_after_configure.connect
    def _setup_recovery_signal(sender, **kwargs):  # noqa: F811
        from celery.signals import worker_ready

        @worker_ready.connect
        def _on_worker_ready(sender, **kwargs):
            count = _recover_orphaned_tasks()
            if count:
                logging.info("Recovered %d orphaned task(s)", count)
except ImportError:
    pass  # celery.signals not available in all environments


# ---------------------------------------------------------------------------
# Celery task wrappers
# ---------------------------------------------------------------------------


@celery.task(name="run_compute_task", bind=True, max_retries=0)
def run_compute_task(self, md5sum: str, task_type: str = "gremlin", params: dict | None = None):
    """Compute task — dispatched by task_type."""
    return _execute_compute_task(md5sum, task_type, params)


@celery.task(name="build_results_archive", bind=True, max_retries=0)
def build_results_archive(self, md5sum: str):
    """Create the full-task ZIP only after a user explicitly requests it."""
    task_id = _normalize_task_id(md5sum)
    task = task_store.get_task(task_id) if task_id else None
    if task is None or task.get("status") not in {"finished", "failed"}:
        raise ValueError("Task results are not ready")
    return _build_results_archive(task)
