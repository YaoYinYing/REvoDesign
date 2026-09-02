# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Authoritative scope-aware storage resolution."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from typing import Any

_STORAGE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,119}\Z")
_TASK_ID = re.compile(r"[a-fA-F0-9]{32}\Z")


def path_is_within(base_dir: str, candidate: str) -> bool:
    """Return whether a path is lexically and symlink-resolved within base."""
    base_abs, target_abs = os.path.abspath(base_dir), os.path.abspath(candidate)
    try:
        if os.path.commonpath([base_abs, target_abs]) != base_abs:
            return False
    except ValueError:
        return False
    probe, tail = target_abs, []
    while probe and not os.path.lexists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        tail.append(os.path.basename(probe))
        probe = parent
    resolved = os.path.realpath(os.path.join(probe, *reversed(tail)))
    try:
        return os.path.commonpath([os.path.realpath(base_abs), resolved]) == os.path.realpath(base_abs)
    except ValueError:
        return False


def safe_join(base_dir: str, *parts: str) -> str:
    candidate = os.path.abspath(os.path.join(base_dir, *parts))
    if not path_is_within(base_dir, candidate):
        raise ValueError("path escapes configured storage root")
    return candidate


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class StorageResolver:
    """Resolve every task path exclusively from its immutable scope identity."""

    def __init__(self, results_dir: str, workspace_dir: str):
        self.results_dir = os.path.abspath(results_dir)
        self.workspace_dir = os.path.abspath(workspace_dir)

    @staticmethod
    def _scope_parts(task: dict[str, Any]) -> tuple[str, str, str]:
        scope_type = str(task.get("scope_type") or "")
        storage_key = str(task.get("storage_key") or "")
        task_id = str(task.get("md5sum") or "").lower()
        if scope_type not in {"personal", "project"}:
            raise ValueError("invalid task scope type")
        if not _STORAGE_KEY.fullmatch(storage_key):
            raise ValueError("invalid task scope storage key")
        if not _TASK_ID.fullmatch(task_id):
            raise ValueError("invalid task id")
        return scope_type, storage_key, task_id

    def get_scope_root(self, scope_type: str, storage_key: str, *, inputs: bool = False) -> str:
        if scope_type not in {"personal", "project"} or not _STORAGE_KEY.fullmatch(storage_key):
            raise ValueError("invalid scope identity")
        base = self.workspace_dir if inputs else self.results_dir
        collection = "users" if scope_type == "personal" else "projects"
        return safe_join(base, collection, storage_key)

    def get_task_root(self, task: dict[str, Any]) -> str:
        scope_type, storage_key, task_id = self._scope_parts(task)
        return safe_join(self.get_scope_root(scope_type, storage_key), "tasks", task_id)

    def get_input_root(self, task: dict[str, Any]) -> str:
        scope_type, storage_key, task_id = self._scope_parts(task)
        return safe_join(self.get_scope_root(scope_type, storage_key, inputs=True), "tasks", task_id)

    def get_output_root(self, task: dict[str, Any]) -> str:
        return self.get_task_root(task)

    def get_manifest_path(self, task: dict[str, Any]) -> str:
        return safe_join(self.get_task_root(task), "manifest.json")

    def get_archive_path(self, task: dict[str, Any]) -> str:
        task_id = str(task.get("md5sum") or "").lower()
        if not _TASK_ID.fullmatch(task_id):
            raise ValueError("invalid task id")
        return safe_join(os.path.dirname(self.get_task_root(task)), f"{task_id}_results.zip")

    scope_root = get_scope_root

    def task_root(self, scope_type: str, storage_key: str, task_id: str) -> str:
        return self.get_task_root({"scope_type": scope_type, "storage_key": storage_key, "md5sum": task_id})

    manifest_path = get_manifest_path

    def resolve_artifact(self, task: dict[str, Any], relative_path: str) -> dict[str, Any] | None:
        normalized = relative_path.replace("\\", "/")
        parts = normalized.split("/")
        if not normalized or normalized.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            return None
        try:
            with open(self.get_manifest_path(task), encoding="utf-8") as handle:
                manifest = json.load(handle)
            artifact = next(item for item in manifest.get("artifacts", []) if item.get("path") == normalized)
            path = safe_join(self.get_task_root(task), *parts)
        except (AttributeError, OSError, ValueError, StopIteration, TypeError):
            return None
        if not os.path.isfile(path) or os.path.islink(path):
            return None
        digest = _sha256_file(path)
        size = os.path.getsize(path)
        if artifact.get("sha256") and artifact["sha256"] != digest:
            return None
        if artifact.get("size") is not None and artifact["size"] != size:
            return None
        return {
            **artifact,
            "path": normalized,
            "physical_path": path,
            "sha256": digest,
            "size": size,
            "type": artifact.get("type") or artifact.get("media_type"),
        }


def snapshot_artifact(source: dict[str, Any], destination: str) -> dict[str, Any]:
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copyfile(source["physical_path"], destination)
    os.chmod(destination, 0o440)
    return {key: source[key] for key in ("path", "sha256", "size", "type") if key in source}
