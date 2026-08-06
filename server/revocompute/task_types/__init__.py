# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Task type registry: dataclasses, YAML loader, and registration.

Server code never needs to know about individual task types — a new task
type is a YAML entry + a runner YAML + a Docker image.  The registry pairs
each TaskType (portable, same on every deployment) with a RunnerConfig
(machine-specific paths, limits, and defaults).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskParam:
    """A parameter the user can set when submitting a job."""

    name: str
    type: str = "str"  # "str" | "int" | "float" | "bool"
    default: Any = None
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class TaskType:
    """Portable task definition — same on every deployment.

    Declares what the task *is*: its Docker image, command, I/O contract,
    progress stages, and the parameters users can submit.  Machine-specific
    paths and resource limits live in RunnerConfig.
    """

    name: str  # "gremlin", "alphafold", "diffdock", "esm"
    display_name: str  # "PSSM-GREMLIN", "AlphaFold2"

    # Docker runner
    docker_image: str
    command: list[str]

    # I/O
    input_extension: str  # ".fasta", ".pdb"
    input_label: str  # "FASTA file", "PDB file"

    # Optional fields with defaults
    gpus: bool = False
    result_patterns: tuple[str, ...] = ("*",)
    stage_markers: dict[str, str] = field(default_factory=dict)
    params: tuple[TaskParam, ...] = ()


@dataclass(frozen=True)
class RunnerMount:
    """A bind mount from host into the runner container."""

    host_path: str  # "/srv/revodesign/databases/uniref30"
    container_path: str  # "/opt/db/uniref30"
    mode: str = "ro"  # "ro" | "rw"


@dataclass(frozen=True)
class RunnerConfig:
    """Deployment-specific settings for a task type.

    Loaded from ``config/runners/<name>.yaml`` at startup.  Host paths are
    machine-specific — edit the YAML when deploying to a new node, never
    the global ``.env``.
    """

    mounts: tuple[RunnerMount, ...] = ()
    env: dict[str, str] = field(default_factory=dict)  # extra env vars → container
    nproc: int | None = None  # override server default if set
    maxmem: int | None = None  # override server default if set
    max_runtime_seconds: int | None = None  # override task_type default if set
    defaults: dict[str, Any] = field(default_factory=dict)  # default param values


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: dict[str, tuple[TaskType, RunnerConfig]] = {}


def register(task_type: TaskType, runner: RunnerConfig) -> None:
    """Register a task type + runner config pair."""
    _registry[task_type.name] = (task_type, runner)


def get(name: str) -> tuple[TaskType, RunnerConfig]:
    """Look up a registered task type + runner config."""
    if name not in _registry:
        raise KeyError(f"Unknown task type: {name!r}")
    return _registry[name]


def list_types() -> list[TaskType]:
    """Return all registered task types (for ``GET /api/types``)."""
    return [tt for tt, _ in _registry.values()]


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


def _load_runner_config(path: str) -> RunnerConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return RunnerConfig(
        mounts=tuple(
            RunnerMount(
                host_path=m["host_path"],
                container_path=m["container_path"],
                mode=m.get("mode", "ro"),
            )
            for m in data.get("mounts", [])
        ),
        env=data.get("env", {}),
        nproc=data.get("nproc"),
        maxmem=data.get("maxmem"),
        max_runtime_seconds=data.get("max_runtime_seconds"),
        defaults=data.get("defaults", {}),
    )


def load_registry(task_types_yaml: str, runners_dir: str, enabled: set[str]) -> None:
    """Load task type definitions and per-runner configs.

    Reads ``task_types.yaml``, then for each enabled task type loads the
    corresponding ``config/runners/<name>.yaml`` if it exists.  Filtered by
    ``ENABLED_TASKRUNNERS``; ``gremlin`` is always enabled.
    """
    with open(task_types_yaml, encoding="utf-8") as f:
        types_data = yaml.safe_load(f)

    if not types_data:
        return

    for name, entry in types_data.get("task_types", {}).items():
        if name != "gremlin" and name not in enabled:
            continue

        tt = TaskType(
            name=name,
            display_name=entry["display_name"],
            docker_image=entry["docker_image"],
            command=entry["command"],
            gpus=entry.get("gpus", False),
            input_extension=entry["input_extension"],
            input_label=entry["input_label"],
            result_patterns=tuple(entry.get("result_patterns", ["*"])),
            stage_markers=entry.get("stage_markers", {}),
            params=tuple(TaskParam(**p) for p in entry.get("params", [])),
        )

        runner_yaml = os.path.join(runners_dir, f"{name}.yaml")
        runner = _load_runner_config(runner_yaml) if os.path.exists(runner_yaml) else RunnerConfig()

        register(tt, runner)
