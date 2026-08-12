# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Result-retention maintenance task and shared artifact deletion helpers."""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from revocompute.config import ComputeConfig, env_float
from revocompute.db import TaskDatabase
from revocompute.maintenance.model import PeriodicTask

_TASK_ID_PATTERN = re.compile(r"[a-fA-F0-9]{32}$")
_TERMINAL_RESULT_STATUSES = {"finished", "failed", "cancelled"}
_CLEANUP_CLAIMS = {
    "finished": ("deleting:finished", "cleaned:finished"),
    "failed": ("deleting:cancel", "cleaned:cancel"),
    "cancelled": ("deleting:cancel", "cleaned:cancel"),
}
_CLAIMED_CLEANUPS = dict(_CLEANUP_CLAIMS.values())


def _path_is_within(base_dir: str, candidate: str) -> bool:
    base_abs = os.path.abspath(base_dir)
    target_abs = os.path.abspath(candidate)
    try:
        common = os.path.commonpath([base_abs, target_abs])
    except ValueError:
        return False
    return common == base_abs


def deleted_status_from_task(task: dict[str, Any]) -> str:
    """Return the existing deleted-state spelling used by the task database."""
    current_status = str(task.get("status") or "").strip().lower()
    if current_status in {"deleted:finshed", "deleted:cancel"}:
        return current_status
    if current_status == "finished":
        return "deleted:finshed"
    return "deleted:cancel"


def delete_task_artifacts(task: dict[str, Any], results_folder: str, workspace_folder: str | None = None) -> None:
    """Safely remove one task's result tree, archive cache, and input snapshot."""
    result_dir = task.get("result_dir")
    if result_dir:
        safe_result_dir = os.path.abspath(str(result_dir))
        if os.path.isdir(safe_result_dir):
            if safe_result_dir in {os.path.abspath(os.sep), os.path.abspath(os.path.expanduser("~"))}:
                logging.warning("Refusing to delete unsafe root-like directory: %s", safe_result_dir)
            elif not _path_is_within(results_folder, safe_result_dir):
                logging.warning("Refusing to delete result directory outside RESULTS_FOLDER: %s", safe_result_dir)
            else:
                shutil.rmtree(safe_result_dir, ignore_errors=True)

    task_id = str(task.get("md5sum") or "").strip().lower()
    if not _TASK_ID_PATTERN.fullmatch(task_id):
        logging.warning("Refusing to delete zip for invalid task id: %s", task.get("md5sum"))
        return
    zip_path = os.path.abspath(os.path.join(results_folder, f"{task_id}_results.zip"))
    if _path_is_within(results_folder, zip_path) and os.path.exists(zip_path):
        os.remove(zip_path)

    if workspace_folder:
        username = str(task.get("username") or "")
        workspace_dir = os.path.abspath(os.path.join(workspace_folder, username, task_id))
        if _path_is_within(workspace_folder, workspace_dir) and os.path.isdir(workspace_dir):
            shutil.rmtree(workspace_dir, ignore_errors=True)


def cleanup_expired_task_artifacts(
    retention_days: float,
    *,
    task_store: TaskDatabase,
    results_folder: str,
    now: float | None = None,
) -> int:
    """Delete artifacts for terminal tasks older than *retention_days*."""
    if retention_days <= 0:
        raise ValueError("retention_days must be positive")
    cutoff = (time.time() if now is None else now) - retention_days * 86400
    cleaned = 0
    for task in task_store.list_tasks():
        status = str(task.get("status") or "").strip().lower()
        finished_at = task.get("finished_at")
        if status in _CLAIMED_CLEANUPS:
            claim_status = status
            cleaned_status = _CLAIMED_CLEANUPS[status]
        else:
            if status not in _TERMINAL_RESULT_STATUSES or finished_at is None or finished_at > cutoff:
                continue
            claim_status, cleaned_status = _CLEANUP_CLAIMS[status]
            if not task_store.claim_task_cleanup(
                task["md5sum"],
                expected_status=status,
                expected_finished_at=finished_at,
                claim_status=claim_status,
            ):
                continue
        workspace_folder = os.path.join(os.path.dirname(results_folder), "workspaces")
        delete_task_artifacts(task, results_folder, workspace_folder)
        if not task_store.complete_task_cleanup(
            task["md5sum"],
            claim_status=claim_status,
            cleaned_status=cleaned_status,
        ):
            logging.warning("Cleanup claim changed before completion for task %s", task["md5sum"])
            continue
        cleaned += 1
    return cleaned


def run_result_cleanup(retention_days: float) -> int:
    """Open the configured task store and run one result-retention pass."""
    config = ComputeConfig.from_env()
    task_store = TaskDatabase(config.db_path)
    cleaned = cleanup_expired_task_artifacts(
        retention_days,
        task_store=task_store,
        results_folder=config.results_folder,
    )
    if cleaned:
        logging.info("Removed expired result artifacts for %d task(s)", cleaned)
    return cleaned


class ResultCleanupTask(PeriodicTask):
    """Environment-configured terminal-result retention cleanup."""

    id = "result-retention-cleanup"

    @property
    def task_method(self) -> Callable[..., Any]:
        return run_result_cleanup

    def configure(self) -> None:
        retention_days = env_float("RESULT_RETENTION_DAYS", 0.0)
        self.env = {"RESULT_RETENTION_DAYS": retention_days}
        self._is_enabled = False
        self._args = {}

        if retention_days < 0:
            raise ValueError("RESULT_RETENTION_DAYS must be zero or positive")
        if retention_days == 0:
            return

        self._is_enabled = True
        self._args = {
            "trigger": "interval",
            "days": 1,
            "args": (retention_days,),
            "misfire_grace_time": 86400,
            "next_run_time": datetime.now(timezone.utc),
        }


result_cleanup_task = ResultCleanupTask()
