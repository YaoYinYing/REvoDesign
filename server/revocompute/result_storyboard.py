# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Runner-declared result files and trusted storyboard assets."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml


class ResultContractError(ValueError):
    """A runner result declaration is malformed or unsafe."""


def runner_root(task_type: Any, server_dir: str) -> Path:
    """Return the configured runner directory, never a task-output directory."""
    del server_dir  # Runtime data storage is not where deployment assets live.
    source_root = Path(__file__).resolve().parents[1]
    root = (source_root / task_type.runtime.dockerfile).resolve().parent
    runners = (source_root / "docker" / "runners").resolve()
    if not root.is_relative_to(runners):
        raise ResultContractError("Runner assets must live under docker/runners")
    return root


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise ResultContractError("Result paths must be non-empty relative paths")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ResultContractError("Result paths must not escape their runner")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ResultContractError(f"Could not read {path.name}") from exc
    if not isinstance(value, dict):
        raise ResultContractError(f"{path.name} must be a mapping")
    return value


def expected_file_tree(task_type: Any, server_dir: str) -> dict[str, dict[str, Any]]:
    """Load the small logical-file contract owned by a runner."""
    path = runner_root(task_type, server_dir) / "expected_files.yaml"
    if not path.is_file():
        return {}
    raw = _load_yaml(path)
    if set(raw) != {"result"} or not isinstance(raw["result"], dict) or set(raw["result"]) != {"files"}:
        raise ResultContractError("expected_files.yaml must contain result.files")
    files = raw["result"]["files"]
    if not isinstance(files, dict):
        raise ResultContractError("result.files must be a mapping")
    parsed: dict[str, dict[str, Any]] = {}
    for logical_id, entry in files.items():
        if (
            not isinstance(logical_id, str)
            or not logical_id[:1].isalpha()
            or not logical_id.replace("_", "").isalnum()
            or not isinstance(entry, dict)
        ):
            raise ResultContractError("Invalid logical result file")
        if set(entry) - {"path", "pattern", "required", "type", "cardinality"}:
            raise ResultContractError(f"Unknown fields for result file {logical_id}")
        selector = entry.get("path", entry.get("pattern"))
        if ("path" in entry) == ("pattern" in entry) or not _safe_relative(selector):
            raise ResultContractError(f"Result file {logical_id} needs exactly one path or pattern")
        cardinality = entry.get("cardinality", "one")
        if cardinality not in {"one", "many"} or not isinstance(entry.get("required"), bool):
            raise ResultContractError(f"Result file {logical_id} has invalid cardinality or required")
        parsed[logical_id] = {**entry, "cardinality": cardinality}
    return parsed


def resolve_expected_files(
    tree: dict[str, dict[str, Any]], artifacts: list[dict[str, Any]]
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[str]]:
    """Resolve only manifest-published regular files into logical identities."""
    by_path = {item["path"]: item for item in artifacts}
    resolved: dict[str, list[dict[str, Any]]] = {}
    checks: list[dict[str, Any]] = []
    problems: list[str] = []
    for logical_id, definition in tree.items():
        selector = definition.get("path") or definition["pattern"]
        matches = [by_path[path] for path in sorted(by_path) if fnmatchcase(path, selector) and by_path[path]["size"] > 0]
        if definition["cardinality"] == "one" and len(matches) > 1:
            problems.append(f"{logical_id}: expected one file, found {len(matches)}")
            matches = matches[:1]
        if len(matches) > 500:
            problems.append(f"{logical_id}: matched more than 500 files")
            matches = matches[:500]
        if definition["required"] and not matches:
            problems.append(f"{logical_id}: required output is missing or empty")
        resolved[logical_id] = matches
        checks.append({"file_id": logical_id, "required": definition["required"], "matched": len(matches),
                       "status": "passed" if matches or not definition["required"] else "failed"})
    return resolved, checks, problems


def storyboard_declaration(task_type: Any, server_dir: str, file_ids: set[str]) -> dict[str, Any] | None:
    """Read a trusted, local runner declaration; never discover task output code."""
    root = runner_root(task_type, server_dir)
    path = root / "storyboard" / "storyboard.yaml"
    if not path.is_file():
        return None
    raw = _load_yaml(path)
    if set(raw) != {"identifier", "entrypoint", "requires", "optional"}:
        raise ResultContractError("storyboard.yaml has unknown or missing fields")
    identifier = raw["identifier"]
    entrypoint = raw["entrypoint"]
    if isinstance(entrypoint, str) and entrypoint.startswith("./"):
        entrypoint = entrypoint[2:]
    entrypoint = _safe_relative(entrypoint)
    if not isinstance(identifier, str) or not identifier.replace("-", "").isalnum():
        raise ResultContractError("Storyboard identifier is invalid")
    asset = (path.parent / entrypoint).resolve()
    if not asset.is_file() or not asset.is_relative_to(path.parent.resolve()) or asset.suffix != ".js":
        raise ResultContractError("Storyboard entrypoint must be a local JavaScript asset")
    requires, optional = raw["requires"], raw["optional"]
    if not all(isinstance(items, list) and all(isinstance(item, str) for item in items) for items in (requires, optional)):
        raise ResultContractError("Storyboard file references must be lists")
    if set(requires) & set(optional) or not set(requires + optional).issubset(file_ids):
        raise ResultContractError("Storyboard references unknown logical files")
    return {"identifier": identifier, "entrypoint": entrypoint, "requires": requires, "optional": optional}
