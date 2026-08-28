# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Celery and compute task runtime.

This module is intentionally independent of Flask authentication.  Importing it
may initialize the shared task store and task directories, but never imports or
opens the user database.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import zipfile
from dataclasses import replace
from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import docker
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
    """Lexical + symlink-aware containment.

    The lexical check is fast and works for not-yet-existing paths.  The
    second check resolves the base and the deepest existing ancestor of the
    candidate (`lexists` so a dangling symlink is caught too), so a symlink
    planted inside the base cannot point the real target outside it.
    """
    base_abs = os.path.abspath(base_dir)
    target_abs = os.path.abspath(candidate)
    try:
        if os.path.commonpath([base_abs, target_abs]) != base_abs:
            return False
    except ValueError:
        return False

    probe = target_abs
    tail_parts: list[str] = []
    while probe and not os.path.lexists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        tail_parts.append(os.path.basename(probe))
        probe = parent
    resolved_target = os.path.realpath(os.path.join(probe, *reversed(tail_parts)))
    resolved_base = os.path.realpath(base_abs)
    try:
        return os.path.commonpath([resolved_base, resolved_target]) == resolved_base
    except ValueError:
        return False


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


def _workflow_state(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = task.get("workflow_state")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _run_compute_workflow(
    task_id: str,
    task: dict[str, Any],
    tt,
    runner,
    entities: list[dict],
    output_dir: str,
    resource_policies: dict[str, ResolvedResources],
    stage_callback,
) -> JobState:
    """Run an ordered workflow through the existing one-allocation Job API."""
    state = _workflow_state(task)
    for stage in tt.workflow:
        previous = state.get(stage.name, {})
        if previous.get("status") == "completed":
            continue
        policy = resource_policies.get(stage.name)
        if policy is None:
            raise ResourceValidationError(f"Workflow stage {stage.name!r} has no resource snapshot")
        markers = {name: tt.stage_markers[name] for name in stage.stage_markers}
        stage_tt = replace(
            tt,
            name=stage.name.replace(".", "-"),
            runner_args=stage.runner_args,
            gpus=stage.requires_gpu,
            requires_network=stage.requires_network,
            stage_markers=markers,
            workflow=(),
        )
        first_marker = next(iter(markers))
        if not task_store.update_task(task_id, status="queued", run_stage=first_marker):
            return JobState.CANCELLED
        job = _create_job(
            task_id,
            stage_tt,
            runner,
            entities,
            output_dir,
            stage_callback,
            username=task.get("username", ""),
            resource_policy=policy,
        )
        jid = job.submit()
        state[stage.name] = {"status": "running", "job_id": jid, "started_at": time.time()}
        handles = {"workflow_state": json.dumps(state, sort_keys=True)}
        if isinstance(job, SlurmJob):
            handles["slurm_job_id"] = jid
        elif isinstance(job, DockerJob):
            handles["container_id"] = jid
        if not task_store.update_task(task_id, **handles):
            job.cancel()
            return JobState.CANCELLED
        result = job.poll()
        state[stage.name].update(status=result.value, finished_at=time.time())
        task_store.update_task(
            task_id,
            workflow_state=json.dumps(state, sort_keys=True),
            slurm_job_id=None,
            container_id=None,
        )
        if result != JobState.COMPLETED:
            return result
    return JobState.COMPLETED


# ---------------------------------------------------------------------------
# Result finalization and optional archive cache
# ---------------------------------------------------------------------------


_TEXT_PREVIEW_EXTENSIONS = {
    ".a3m",
    ".aln",
    ".bib",
    ".bibtex",
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


def _iso_timestamp(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(value)).astimezone().isoformat() if value is not None else None
    except (TypeError, ValueError, OSError):
        return None


def _public_run_record(task: dict[str, Any], task_type: Any, finished_at: float) -> dict[str, Any]:
    raw_form = task.get("input_form")
    try:
        form = json.loads(raw_form) if isinstance(raw_form, str) else raw_form
    except (json.JSONDecodeError, TypeError):
        form = {}
    form = form if isinstance(form, dict) else {}
    entities = form.get("entities") if isinstance(form.get("entities"), list) else []
    params_by_name = {parameter.name: parameter for parameter in task_type.params} if task_type else {}
    inputs = [
        {
            "path": str(entity.get("relative_path") or entity.get("verified_value") or ""),
            "sha256": str(entity.get("hash") or ""),
        }
        for entity in entities
        if entity.get("type") == "file" and (entity.get("relative_path") or entity.get("verified_value"))
    ]
    parameters = []
    for entity in entities:
        if entity.get("type") == "file" or not entity.get("name"):
            continue
        definition = params_by_name.get(entity["name"])
        parameters.append(
            {
                "name": entity["name"],
                "label": (
                    definition.label or entity["name"].replace("_", " ").title()
                    if definition
                    else entity["name"].replace("_", " ").title()
                ),
                "value": entity.get("verified_value", entity.get("value")),
                "unit": definition.unit if definition else "",
            }
        )
    started_at = task.get("started_at")
    walltime = (
        max(finished_at - float(started_at), 0.0) if isinstance(started_at, (int, float)) else task.get("walltime")
    )
    return {
        "method": {
            "id": task.get("task_type", "gremlin"),
            "name": task_type.display_name if task_type else task.get("task_type", "gremlin"),
            "summary": task_type.summary if task_type else "",
            "output_summary": task_type.output_summary if task_type else "",
        },
        "inputs": inputs,
        "parameters": parameters,
        "submitted_at": form.get("submitted_at") or _iso_timestamp(task.get("uploaded_at")),
        "started_at": _iso_timestamp(started_at),
        "finished_at": _iso_timestamp(finished_at),
        "walltime_seconds": walltime,
        "citations": (
            [{"num": number, "doi": doi, "title": title} for number, doi, title in task_type.citation_dois]
            if task_type
            else []
        ),
    }


def _default_artifact_role(relative_path: str) -> str:
    basename = os.path.basename(relative_path)
    if relative_path == "citations.bib" or relative_path.startswith("debug/"):
        return "provenance"
    if (
        relative_path.startswith(("execution/", "log/"))
        or basename in {"task_finished", "task_failed.txt"}
        or (basename.startswith(".") and basename.endswith("-complete"))
        or relative_path.endswith((".stderr.log", ".stdout.log", ".err"))
    ):
        return "diagnostic"
    return "artifact"


def _json_path(value: Any, path: str) -> Any:
    for part in path.split(".") if path else ():
        if isinstance(value, list) and part.isdigit():
            index = int(part)
            if index >= len(value):
                raise KeyError(path)
            value = value[index]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise KeyError(path)
    return value


def _validate_scientific_view(
    definition: Any,
    sources: dict[str, list[str]],
    result_dir: str,
) -> list[str]:
    """Check resolved files against the declared protocol, without task-name branches."""
    problems: list[str] = []
    singular = {
        "alignment": ("alignment",),
    }.get(definition.plugin, ())
    for source in singular:
        if len(sources.get(source, [])) != 1:
            problems.append(f"{definition.title}: {source} source must resolve to exactly one artifact")
    if problems:
        return problems

    if definition.plugin == "entity-table":
        tables = sources.get("table", [])
        structures = sources.get("structure", [])
        if len(tables) != 1:
            problems.append(f"{definition.title}: table source must resolve to exactly one artifact")
        if len(structures) > 1:
            problems.append(f"{definition.title}: structure source must resolve to at most one artifact")
        if len(tables) == 1:
            delimiter = "\t" if tables[0].lower().endswith(".tsv") else ","
            try:
                with open(_safe_join(result_dir, *tables[0].split("/")), newline="", encoding="utf-8") as handle:
                    columns = next(csv.reader(handle, delimiter=delimiter), [])
            except (OSError, UnicodeError, csv.Error):
                columns = []
            required_columns = set(definition.mapping.get("key_columns", []))
            required_columns.update(definition.mapping.get("evidence_columns", []))
            required_columns.update(
                definition.mapping[key]
                for key in ("label_column", "chain_column", "residue_column")
                if definition.mapping.get(key)
            )
            missing = sorted(required_columns - set(columns))
            if missing:
                problems.append(f"{definition.title}: table is missing columns {', '.join(missing)}")
        return problems

    if definition.plugin == "trajectory":
        topologies = sources.get("topology", [])
        coordinates = sources.get("coordinates", [])
        if definition.mapping["association"] == "single" and (len(topologies) != 1 or len(coordinates) != 1):
            problems.append(
                f"{definition.title}: single association requires exactly one topology and coordinate artifact"
            )
        elif definition.mapping["association"] == "stem-prefix":
            stems = [os.path.splitext(os.path.basename(path))[0] for path in topologies]
            for path in coordinates:
                name = os.path.basename(path)
                if not any(name.startswith(f"{stem}_") for stem in stems):
                    problems.append(f"{definition.title}: coordinate {path} has no declared topology association")
        expected_suffix = f".{definition.mapping['coordinate_format']}"
        if any(not path.lower().endswith(expected_suffix) for path in coordinates):
            problems.append(f"{definition.title}: coordinate format does not match the declared artifacts")
        return problems

    paths = sources.get("series", []) if definition.plugin == "metric-series" else sources.get("matrices", [])
    if definition.plugin == "scalar-summary":
        paths = sources["data"]
    if definition.plugin not in {"metric-series", "matrix", "scalar-summary"}:
        return problems
    for relative_path in paths:
        path = _safe_join(result_dir, *relative_path.split("/"))
        try:
            if definition.mapping.get("format") == "csv":
                with open(path, newline="", encoding="utf-8") as handle:
                    columns = next(csv.reader(handle), [])
                required = set(definition.mapping.get("value_columns", []))
                required.add(definition.mapping.get("x_column") or definition.mapping.get("row_labels_column"))
                missing = sorted(column for column in required if column and column not in columns)
                if missing:
                    problems.append(f"{definition.title}: data is missing columns {', '.join(missing)}")
                continue
            if os.path.getsize(path) > 8 * 1024 * 1024:
                problems.append(f"{definition.title}: JSON source exceeds the 8 MiB scientific-view limit")
                continue
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            if definition.plugin == "scalar-summary":
                values = [_json_path(payload, field["path"]) for field in definition.mapping["fields"]]
                if any(isinstance(value, (dict, list)) or value is None for value in values):
                    raise ValueError("scalar fields must resolve to values")
            else:
                values = _json_path(payload, definition.mapping["value_path"])
                if not isinstance(values, list) or (
                    definition.plugin == "matrix" and values and not all(isinstance(row, list) for row in values)
                ):
                    raise ValueError("declared numeric data has the wrong shape")
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            problems.append(f"{definition.title}: declared data mapping could not be resolved")
    return problems


def _resolve_result_views(
    task_type: Any,
    artifacts: list[dict[str, Any]],
    result_dir: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    views: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    if task_type is None or not task_type.result_workspace:
        return views, checks, problems
    paths = [artifact["path"] for artifact in artifacts]
    artifact_by_path = {artifact["path"]: artifact for artifact in artifacts}
    for definition in task_type.result_workspace:
        resolved_sources: dict[str, list[str]] = {}
        for source_name, selectors in definition.sources.items():
            matches: list[str] = []
            for selector in selectors:
                selected = (
                    [path for path in paths if fnmatchcase(path, selector.value)]
                    if selector.is_glob
                    else [selector.value] if selector.value in artifact_by_path else []
                )
                if len(selected) > 500:
                    problems.append(f"{definition.title}: {source_name} matched more than 500 artifacts")
                    selected = selected[:500]
                nonempty = [path for path in selected if artifact_by_path[path]["size"] > 0]
                status = "passed" if nonempty or not selector.required else "failed"
                checks.append(
                    {
                        "view_id": definition.id,
                        "source": source_name,
                        "required": selector.required,
                        "status": status,
                        "matched": len(nonempty),
                    }
                )
                if selector.required and not nonempty:
                    problems.append(f"{definition.title}: required {source_name} output is missing or empty")
                matches.extend(nonempty)
            resolved_sources[source_name] = list(dict.fromkeys(matches))
        problems.extend(_validate_scientific_view(definition, resolved_sources, result_dir))
        view = {
            "id": definition.id,
            "plugin": definition.plugin,
            "role": definition.role,
            "title": definition.title,
            "description": definition.description,
            "sources": resolved_sources,
            "mapping": definition.mapping,
        }
        views.append(view)
        artifact_role = "primary" if definition.role == "primary" else "evidence"
        for source_name, source_paths in resolved_sources.items():
            role = "evidence" if source_name == "supporting" else artifact_role
            for path in source_paths:
                if artifact_by_path[path]["role"] not in {"provenance", "diagnostic"}:
                    artifact_by_path[path]["role"] = role
    return views, checks, list(dict.fromkeys(problems))


def _finalize_results_manifest(
    task: dict[str, Any],
    *,
    execution_state: str,
    finished_at: float,
) -> dict[str, Any]:
    """Atomically publish the immutable scientific result record for a task."""
    if execution_state not in {"completed", "failed"}:
        raise ValueError("execution_state must be completed or failed")
    result_dir = os.path.abspath(task["result_dir"])
    os.makedirs(result_dir, exist_ok=True)
    try:
        task_type, _ = _get_task_type(task.get("task_type", "gremlin"))
    except KeyError:
        task_type = None
    if task_type is not None and task_type.citation_bibtex:
        with open(os.path.join(result_dir, "citations.bib"), "w", encoding="utf-8") as handle:
            handle.write(task_type.citation_bibtex.strip() + "\n")
    artifacts: list[dict[str, Any]] = []
    for root, dirs, files in os.walk(result_dir, followlinks=False):
        dirs[:] = sorted(directory for directory in dirs if not os.path.islink(os.path.join(root, directory)))
        for filename in sorted(files):
            path = os.path.join(root, filename)
            relative_path = os.path.relpath(path, result_dir).replace(os.sep, "/")
            if relative_path in {"manifest.json", ".manifest.json.tmp"} or os.path.islink(path):
                continue
            stat = os.stat(path, follow_symlinks=False)
            artifacts.append(
                {
                    "path": relative_path,
                    "size": stat.st_size,
                    "sha256": _sha256_file(path),
                    "media_type": mimetypes.guess_type(relative_path)[0] or "application/octet-stream",
                    "preview": _preview_kind(relative_path),
                    "role": _default_artifact_role(relative_path),
                }
            )
    views, checks, problems = _resolve_result_views(task_type, artifacts, result_dir)
    if execution_state == "failed":
        output_state = "not_assessed"
    elif task_type is None or not task_type.result_workspace:
        output_state = "not_configured"
    else:
        output_state = "failed" if problems else "passed"
    manifest = {
        "schema_version": 3,
        "task_id": task["md5sum"],
        "task_type": task.get("task_type", "gremlin"),
        "created_at": _iso_timestamp(finished_at),
        "run": _public_run_record(task, task_type, finished_at),
        "output_check": {"state": output_state, "checks": checks, "problems": problems},
        "limitations": list(task_type.considerations) if task_type else [],
        "artifacts": artifacts,
        "views": views,
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


def _finalize_failed_results(task: dict, error: Any, *, finished_at: float) -> None:
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
        _finalize_results_manifest(task, execution_state="failed", finished_at=finished_at)
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
    _capture_debug_submission(task, _entities_from_input_form(task))
    _finalize_failed_results(task, error_message, finished_at=finish_time)
    task_store.update_task(
        md5sum,
        status="failed",
        finished_at=finish_time,
        walltime=finish_time - start_time,
        error=error_message,
        run_stage=run_stage,
    )
    _cleanup_task_workspace(task)


def _cleanup_task_workspace(task: dict[str, Any]) -> None:
    """Delete the per-task input workspace once the job reaches a terminal
    state.  Results live in the separate results folder and are untouched;
    only the immutable input snapshot and staging area are removed, so
    finished tasks no longer hold duplicate input copies on disk."""
    username = str(task.get("username") or "").strip()
    md5sum = str(task.get("md5sum") or "")
    if not username or not md5sum:
        return
    try:
        workspace_dir = _safe_join(CONFIG.workspace_folder, username, md5sum)
    except ValueError:
        return
    if os.path.isdir(workspace_dir):
        shutil.rmtree(workspace_dir, ignore_errors=True)
        logging.info("Cleaned up workspace %s for finished task %s", workspace_dir, md5sum)


def _entities_from_input_form(task: dict[str, Any]) -> list[dict]:
    """Parse the file/param entities out of a task row's ``input_form`` blob."""
    raw_form = task.get("input_form")
    if not raw_form:
        return []
    try:
        parsed = json.loads(raw_form) if isinstance(raw_form, str) else raw_form
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, dict):
        return []
    entities = parsed.get("entities")
    return entities if isinstance(entities, list) else []


def _capture_debug_submission(task: dict[str, Any], entities: list[dict], params: dict | None = None) -> None:
    """Best-effort copy of the user's submission into the result dir so it
    survives workspace cleanup: the submission form as ``debug/submission.json``
    plus each input snapshot copied to its user-facing path under
    ``debug/inputs/``.  Any failure only logs a warning — debug capture must
    never fail a job finalization."""
    result_dir = str(task.get("result_dir") or "")
    if not result_dir:
        return
    try:
        debug_dir = _safe_join(result_dir, "debug")
        inputs_dir = _safe_join(debug_dir, "inputs")
        os.makedirs(inputs_dir, exist_ok=True)

        raw_form = task.get("input_form")
        if isinstance(raw_form, str):
            try:
                raw_form = json.loads(raw_form)
            except json.JSONDecodeError:
                raw_form = None
        form = raw_form if isinstance(raw_form, dict) else {}

        # The DB record is the source of truth — same convention as
        # _execute_compute_task, where the Celery ``params`` argument is
        # ignored in favor of the input_form param entities.
        if params is None:
            params = {
                e["name"]: e.get("verified_value", e.get("value"))
                for e in entities
                if e.get("type") != "file" and e.get("name")
            }

        files: list[dict[str, Any]] = []
        for fe in [e for e in entities if e.get("type") == "file"]:
            relative_path = str(fe.get("relative_path") or "").replace("\\", "/")
            snapshot_path = str(fe.get("snapshot_path") or "")
            parts = relative_path.split("/")
            if not relative_path or relative_path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
                logging.warning(
                    "Skipping debug capture for invalid input path %r in task %s",
                    relative_path,
                    task.get("md5sum"),
                )
                continue
            if (
                not _path_is_within(CONFIG.workspace_folder, snapshot_path)
                or os.path.islink(snapshot_path)
                or not os.path.isfile(snapshot_path)
            ):
                logging.warning(
                    "Skipping debug capture for invalid snapshot %r in task %s",
                    snapshot_path,
                    task.get("md5sum"),
                )
                continue
            destination = _safe_join(inputs_dir, *parts)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            # Hardlink first: workspace and results live on the same server
            # filesystem, so the debug copy costs no extra disk and the
            # workspace deletion later only drops its own link.  Copy when
            # linking is impossible (e.g. the results dir is a different
            # mount).
            try:
                os.link(snapshot_path, destination)
            except OSError:
                shutil.copyfile(snapshot_path, destination)
            files.append(
                {
                    "name": relative_path,
                    "size": os.path.getsize(destination),
                    "sha256": str(fe.get("hash") or ""),
                }
            )

        submission = {
            "task_type": task.get("task_type", "gremlin"),
            "params": params,
            "username": str(task.get("username") or form.get("user") or ""),
            "submitted_at": form.get("submitted_at") or task.get("uploaded_at"),
            "files": files,
        }
        submission_path = _safe_join(debug_dir, "submission.json")
        with open(submission_path, "w", encoding="utf-8") as handle:
            json.dump(submission, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
    except Exception as exc:  # pylint: disable=broad-except
        logging.warning("Failed to capture debug submission for task %s: %s", task.get("md5sum"), exc)


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
    resource_policies: dict[str, ResolvedResources] = {}
    if raw_form:
        try:
            parsed = json.loads(raw_form) if isinstance(raw_form, str) else raw_form
            entities = parsed.get("entities", [])
            if parsed.get("resource_policy"):
                resource_policy = ResolvedResources.from_snapshot(parsed["resource_policy"])
            raw_policies = parsed.get("resource_policies", {})
            if not isinstance(raw_policies, dict):
                raise TypeError("resource_policies must be an object")
            resource_policies = {name: ResolvedResources.from_snapshot(policy) for name, policy in raw_policies.items()}
        except (json.JSONDecodeError, TypeError, ResourceValidationError):
            logging.warning("Task %s: input_form or resource policy is invalid.", md5sum)
            _record_failure(md5sum, task, time.time(), "", "Task input or resource policy is invalid")
            return

    # Verify file entities reference existing files
    for fe in [e for e in entities if e["type"] == "file"]:
        upload_file = os.path.join(CONFIG.upload_folder, f"{fe['hash']}.upload")
        if not os.path.lexists(upload_file):
            _record_failure(md5sum, task, time.time(), "", f"Uploaded input file not found: {upload_file}")
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
            _record_failure(
                md5sum,
                task,
                time.time(),
                "",
                f"Immutable input snapshot is missing or changed: {fe.get('relative_path', 'unknown')}",
            )
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
        is_first = stage_state.get("first")
        logging.info("Stage callback for task %s: stage=%s changed=%s first=%s", md5sum, stage, stage_changed, is_first)
        stage_state["current"] = stage
        if is_first:
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
        if tt.workflow:
            final_state = _run_compute_workflow(
                md5sum,
                task,
                tt,
                runner,
                entities,
                output_dir,
                resource_policies,
                _on_stage_change,
            )
        else:
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
            _capture_debug_submission(task, entities, params)
            _cleanup_task_workspace(task)
            return

        final_stage = stage_state["current"] or (stages[-1][0] if stages else "")
        refreshed_task = task_store.get_task(md5sum) or task
        if _is_terminal_status(refreshed_task.get("status")):
            return
        _capture_debug_submission(task, entities, params)
        finish_time = time.time()
        _finalize_results_manifest(refreshed_task, execution_state="completed", finished_at=finish_time)
        refreshed_task = task_store.get_task(md5sum) or refreshed_task
        if _is_terminal_status(refreshed_task.get("status")):
            return
        task_store.update_task(
            md5sum,
            status="finished",
            finished_at=finish_time,
            walltime=finish_time - start_time,
            error=None,
            run_stage=final_stage,
        )
        _cleanup_task_workspace(task)
    except docker.errors.ContainerError as exc:
        _record_failure(md5sum, task, start_time, stage_state["current"], f"docker: {exc}")
    except docker.errors.DockerException as exc:
        _record_failure(md5sum, task, start_time, stage_state["current"], f"docker: {exc}")
        logging.error("Docker daemon unavailable for task %s (type=%s): %s", md5sum, task_type, exc)
    except Exception as exc:  # pylint: disable=broad-except
        _record_failure(md5sum, task, start_time, stage_state["current"], str(exc))
        logging.exception("Unexpected failure while running task %s (type=%s)", md5sum, task_type)


# ---------------------------------------------------------------------------
# Orphaned compute-resource recovery after worker restart
#
# A managed stack shutdown sweeps SLURM jobs before stopping the worker, but
# an OOM, crash, or direct container restart bypasses that hook.  On worker
# startup, fail those orphaned records and best-effort cancel their allocation.
# Docker containers survive a worker restart and are reconnected instead.
# ---------------------------------------------------------------------------


def _stop_orphaned_workflow_execution(task_id: str, slurm_job_id: str, container_id: str) -> str:
    """Stop a workflow allocation before another worker resumes its stage."""
    if slurm_job_id:
        if slurm_job_id.isdigit():
            scancel = shutil.which("scancel")
            if not scancel:
                return f"Cannot resume while SLURM job {slurm_job_id} cannot be cancelled"
            try:
                subprocess.run([scancel, slurm_job_id], timeout=10, check=True)
            except (OSError, subprocess.SubprocessError) as exc:
                return f"Could not cancel SLURM job {slurm_job_id}: {exc}"
        else:
            match = re.fullmatch(r"srun-([1-9][0-9]*)", slurm_job_id)
            if not match:
                return f"Cannot resume workflow with unknown SLURM handle {slurm_job_id!r}"
            pid = int(match.group(1))
            try:
                command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
            except FileNotFoundError:
                command = b""
            except OSError as exc:
                return f"Could not inspect srun process {pid}: {exc}"
            if command:
                if b"srun" not in command or task_id[:8].encode("ascii") not in command:
                    return f"Refusing to stop unverified process {pid} for workflow recovery"
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    return f"Could not stop srun process {pid}: {exc}"
                if not _wait_for_process_exit(pid, 10.0):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except OSError as exc:
                        return f"Could not kill srun process {pid}: {exc}"
                    if not _wait_for_process_exit(pid, 2.0):
                        return f"srun process {pid} did not exit after SIGKILL"

    if container_id:
        client = None
        try:
            client = docker.from_env()
            client.containers.get(container_id).stop(timeout=10)
        except docker.errors.NotFound:
            pass
        except docker.errors.DockerException as exc:
            return f"Could not stop Docker container {container_id}: {exc}"
        finally:
            if client is not None:
                client.close()
    return ""


def _wait_for_process_exit(pid: int, timeout: float) -> bool:
    """Wait for a PID to disappear or become a reaped-ready zombie."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            state = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[2]
        except FileNotFoundError:
            return True
        except (OSError, IndexError):
            state = ""
        if state == "Z":
            return True
        time.sleep(0.1)
    return False


def _recover_orphaned_tasks() -> int:
    """Resolve compute records whose owning Celery worker disappeared."""
    handled = 0
    for task in task_store.list_tasks():
        if task.get("status") not in {"running", "queued"}:
            continue
        md5sum = task["md5sum"]
        slurm_job_id = str(task.get("slurm_job_id") or "").strip()
        container_id = str(task.get("container_id") or "")
        task_type = task.get("task_type", "gremlin")
        try:
            workflow_task = bool(_get_task_type(task_type)[0].workflow)
        except KeyError:
            workflow_task = False
        if workflow_task:
            if not task_store.claim_task_recovery(md5sum, expected_status=str(task.get("status") or "")):
                continue
            stop_error = _stop_orphaned_workflow_execution(md5sum, slurm_job_id, container_id)
            if stop_error:
                task_store.update_task(md5sum, status="queued", error=stop_error)
                logging.error("Recovery left workflow %s queued: %s", md5sum, stop_error)
                handled += 1
                continue
            state = _workflow_state(task)
            for step in state.values():
                if step.get("status") == "running":
                    step["status"] = "interrupted"
            if not task_store.update_task(
                md5sum,
                status="pending",
                slurm_job_id=None,
                container_id=None,
                workflow_state=json.dumps(state, sort_keys=True),
                error=None,
            ):
                handled += 1
                continue
            try:
                resumed = run_compute_task.apply_async(args=[md5sum], kwargs={"task_type": task_type})
            except Exception as exc:  # pylint: disable=broad-except
                task_store.update_task(md5sum, status="queued", error=f"Workflow recovery enqueue failed: {exc}")
                logging.exception("Recovery could not enqueue workflow %s", md5sum)
            else:
                if not task_store.update_task(md5sum, celery_task_id=resumed.id):
                    resumed.revoke(terminate=True)
            handled += 1
            continue
        if slurm_job_id:
            cancellation_error = ""
            scancel = shutil.which("scancel")
            if scancel and slurm_job_id.isdigit():
                try:
                    subprocess.run([scancel, slurm_job_id], timeout=10, check=True)
                except (OSError, subprocess.SubprocessError) as exc:
                    cancellation_error = f"; scheduler cancellation could not be confirmed: {exc}"
                    logging.warning("Recovery could not cancel SLURM job %s for %s: %s", slurm_job_id, md5sum, exc)
            else:
                cancellation_error = "; scheduler cancellation could not be attempted"
            _record_failure(
                md5sum,
                task,
                task.get("started_at") or time.time(),
                str(task.get("run_stage") or ""),
                f"SLURM task lost its worker{cancellation_error}",
            )
            handled += 1
            continue
        if not container_id and task.get("status") == "running":
            _record_failure(
                md5sum,
                task,
                task.get("started_at") or time.time(),
                str(task.get("run_stage") or ""),
                "Compute task lost its worker before recording a resource handle",
            )
            handled += 1
            continue
        if not container_id:
            continue
        logging.info("Recovery: checking orphaned task %s", md5sum)
        try:
            from revocompute.job.runners.docker_runner import DockerJob
            from revocompute.task_types import get as _gt

            tt, runner = _gt(task_type)
            job = DockerJob(md5sum, tt, runner, [], task["result_dir"])
            if job.reconnect(container_id):
                logging.info("Recovery: reconnected Docker %s for %s", container_id, md5sum)
                threading.Thread(
                    target=_poll_recovered_docker_job,
                    args=(md5sum, task, tt, job),
                    name=f"recover-{md5sum[:12]}",
                    daemon=True,
                ).start()
                handled += 1
            else:
                _record_failure(
                    md5sum,
                    task,
                    task.get("started_at") or time.time(),
                    "",
                    "Docker container not found after server restart",
                )
                handled += 1
        except Exception as exc:  # pylint: disable=broad-except
            logging.error("Recovery failed for Docker task %s: %s", md5sum, exc)
            _record_failure(md5sum, task, task.get("started_at") or time.time(), "", f"Recovery error: {exc}")
            handled += 1
    return handled


def _poll_recovered_docker_job(md5sum, task, tt, job) -> None:
    """Poll and finalize a reconnected container without delaying worker readiness."""
    try:
        _finalize_after_poll(md5sum, task, tt, job.poll())
    except Exception as exc:  # pylint: disable=broad-except
        logging.exception("Recovery polling failed for Docker task %s", md5sum)
        _record_failure(md5sum, task, task.get("started_at") or time.time(), "", f"Recovery error: {exc}")


def _finalize_after_poll(md5sum, task, tt, state):
    """Publish results or record failure after a recovered job completes."""
    if state == JobState.FAILED:
        _record_failure(md5sum, task, task.get("started_at") or time.time(), "", "Recovered compute job failed")
    elif state == JobState.CANCELLED:
        task_store.update_task(md5sum, status="cancelled", finished_at=time.time())
        _capture_debug_submission(task, _entities_from_input_form(task))
        _cleanup_task_workspace(task)
    else:
        refreshed = task_store.get_task(md5sum) or task
        if _is_terminal_status(refreshed.get("status")):
            return
        _capture_debug_submission(task, _entities_from_input_form(task))
        finish_time = time.time()
        _finalize_results_manifest(refreshed, execution_state="completed", finished_at=finish_time)
        refreshed = task_store.get_task(md5sum) or refreshed
        if _is_terminal_status(refreshed.get("status")):
            return
        task_store.update_task(
            md5sum,
            status="finished",
            finished_at=finish_time,
            walltime=finish_time - (task.get("started_at") or finish_time),
            error=None,
            run_stage=list(tt.stage_markers.items())[-1][0] if tt.stage_markers else "",
        )
        _cleanup_task_workspace(task)


try:
    from celery.signals import worker_ready

    @worker_ready.connect
    def _on_worker_ready(sender, **kwargs):
        try:
            count = _recover_orphaned_tasks()
            if count:
                logging.info("Handled %d orphaned task(s)", count)
            else:
                logging.info("Recovery: no orphaned tasks found")
        except Exception:  # boot-time recovery must never die silently
            logging.exception("Recovery pass failed")

except ImportError:
    pass  # celery.signals not available in all environments


# ---------------------------------------------------------------------------
# Celery task wrappers
# ---------------------------------------------------------------------------


@celery.task(name="run_compute_task", bind=True, max_retries=0)
def run_compute_task(self, md5sum: str, task_type: str = "gremlin", params: dict | None = None):
    """Compute task — dispatched by task_type."""
    return _execute_compute_task(md5sum, task_type, params)


@celery.task(name="cancel_compute_resources", bind=True, max_retries=0)
def cancel_compute_resources(self, slurm_job_id: str | None = None, container_id: str | None = None):
    """Kill a task's compute resources from the worker, which is the only
    container with SLURM tooling (and the Docker socket) mounted.  The web
    process cannot scancel or docker-stop directly."""
    if slurm_job_id:
        scancel = shutil.which("scancel")
        if not scancel:
            logging.warning("scancel not found; cannot cancel SLURM job %s", slurm_job_id)
        else:
            try:
                subprocess.run([scancel, str(slurm_job_id)], timeout=10, check=True)
                logging.info("Cancelled SLURM job %s", slurm_job_id)
            except Exception as exc:  # pylint: disable=broad-except
                logging.warning("Failed to scancel SLURM job %s: %s", slurm_job_id, exc)
    if container_id:
        docker_executable = shutil.which("docker")
        if not docker_executable:
            logging.warning("docker not found; cannot stop container %s", container_id)
        else:
            try:
                subprocess.run([docker_executable, "stop", str(container_id)], timeout=15, check=True)
                logging.info("Stopped Docker container %s", container_id)
            except Exception as exc:  # pylint: disable=broad-except
                logging.warning("Failed to stop Docker container %s: %s", container_id, exc)


@celery.task(name="build_results_archive", bind=True, max_retries=0)
def build_results_archive(self, md5sum: str):
    """Create the full-task ZIP only after a user explicitly requests it."""
    task_id = _normalize_task_id(md5sum)
    task = task_store.get_task(task_id) if task_id else None
    if task is None or task.get("status") not in {"finished", "failed"}:
        raise ValueError("Task results are not ready")
    return _build_results_archive(task)
