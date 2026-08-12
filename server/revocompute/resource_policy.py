# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Typed resource policy shared by admin configuration and job launchers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Callable


class ResourceValidationError(ValueError):
    """A resource setting cannot be represented safely or consistently."""


_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_CONSTRAINT_RE = re.compile(r"^(?!-)[A-Za-z0-9_.&|*+!()\[\]-]{1,256}$")
_MEMORY_RE = re.compile(r"^[1-9][0-9]*(?:[KMGTP])?$", re.IGNORECASE)
_TIME_RE = re.compile(r"^(?:[0-9]+-)?(?:[0-9]{1,2}):[0-5][0-9]:[0-5][0-9]$")
_GRES_RE = re.compile(r"^gpu:(?:(?:[A-Za-z][A-Za-z0-9_.-]*):)?[1-9][0-9]*$")
_BOOL_TRUE = {"true", "1", "yes", "on"}
_BOOL_FALSE = {"false", "0", "no", "off"}

CANONICAL_TASK_FIELDS = (
    "enabled",
    "cpus",
    "memory",
    "max_runtime_seconds",
    "slurm_partition",
    "slurm_gres",
    "slurm_time",
    "slurm_nodes",
    "slurm_ntasks",
    "slurm_qos",
    "slurm_account",
    "slurm_constraint",
    "slurm_exclusive",
)

# Retained for database migration and read compatibility only. New UI/API
# clients should use cpus/memory.
LEGACY_TASK_FIELDS = ("nproc", "maxmem", "slurm_cpus_per_task", "slurm_mem")

GLOBAL_RESOURCE_KEYS = {
    "cpus",
    "memory",
    "max_runtime_seconds",
    "slurm_partition",
    "slurm_gres",
    "slurm_time",
    "slurm_nodes",
    "slurm_ntasks",
    "slurm_qos",
    "slurm_account",
    "slurm_constraint",
    "slurm_exclusive",
    "slurm_enabled",
    "slurm_allowed_queues",
} | set(LEGACY_TASK_FIELDS)


def _positive_int(value: Any, field: str, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ResourceValidationError(f"{field} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ResourceValidationError(f"{field} must be a positive integer") from exc
    if str(value).strip() != str(result) or result < 1 or (maximum is not None and result > maximum):
        suffix = f" at most {maximum}" if maximum is not None else ""
        raise ResourceValidationError(f"{field} must be a positive integer{suffix}")
    return result


def _boolean(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in _BOOL_TRUE:
        return True
    if normalized in _BOOL_FALSE:
        return False
    raise ResourceValidationError(f"{field} must be true or false")


def _name(value: Any, field: str) -> str:
    normalized = str(value).strip()
    if not _NAME_RE.fullmatch(normalized):
        raise ResourceValidationError(f"{field} contains unsupported characters")
    return normalized


def normalize_resource_value(field: str, value: Any) -> Any:
    """Validate and normalize one persisted task/global resource value."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if field in {"cpus", "nproc", "slurm_cpus_per_task"}:
        return _positive_int(value, field, 1024)
    if field in {"slurm_nodes", "slurm_ntasks"}:
        return _positive_int(value, field, 128)
    if field in {"max_runtime_seconds"}:
        return _positive_int(value, field, 31 * 24 * 60 * 60)
    if field == "maxmem":
        return _positive_int(value, field, 1024 * 1024)
    if field in {"memory", "slurm_mem"}:
        normalized = str(value).strip().upper()
        if not _MEMORY_RE.fullmatch(normalized):
            raise ResourceValidationError(f"{field} must look like 4000M or 16G")
        return normalized
    if field == "slurm_time":
        normalized = str(value).strip()
        if not _TIME_RE.fullmatch(normalized):
            raise ResourceValidationError(f"{field} must use [days-]HH:MM:SS")
        return normalized
    if field == "slurm_gres":
        normalized = str(value).strip()
        if not _GRES_RE.fullmatch(normalized):
            raise ResourceValidationError(f"{field} must look like gpu:1 or gpu:a100:1")
        return normalized
    if field in {"enabled", "slurm_exclusive", "slurm_enabled"}:
        return _boolean(value, field)
    if field == "slurm_allowed_queues":
        values = value if isinstance(value, (list, tuple)) else str(value).split(",")
        normalized_values = []
        for item in values:
            if not isinstance(item, str):
                raise ResourceValidationError("slurm_allowed_queues entries must be strings")
            if item.strip():
                normalized_values.append(_name(item, "slurm_allowed_queues"))
        return tuple(dict.fromkeys(normalized_values))
    if field == "slurm_constraint":
        normalized = str(value).strip()
        if not _CONSTRAINT_RE.fullmatch(normalized):
            raise ResourceValidationError("slurm_constraint contains unsupported characters")
        return normalized
    if field in {"slurm_partition", "slurm_qos", "slurm_account"}:
        return _name(value, field)
    raise ResourceValidationError(f"Unknown resource field: {field}")


def seconds_to_slurm_time(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    value = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{days}-{value}" if days else value


def slurm_time_to_seconds(value: str) -> int:
    normalized = normalize_resource_value("slurm_time", value)
    days = 0
    clock = normalized
    if "-" in normalized:
        raw_days, clock = normalized.split("-", 1)
        days = int(raw_days)
    hours, minutes, seconds = (int(part) for part in clock.split(":"))
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


@dataclass(frozen=True)
class ResolvedResources:
    cpus: int
    memory: str
    max_runtime_seconds: int
    partition: str | None
    gres: str | None
    nodes: int
    ntasks: int
    qos: str | None
    account: str | None
    constraint: str | None
    exclusive: bool
    requires_gpu: bool
    sources: dict[str, str]

    @property
    def slurm_time(self) -> str:
        return seconds_to_slurm_time(self.max_runtime_seconds)

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["slurm_time"] = self.slurm_time
        payload.pop("sources", None)
        return payload

    @classmethod
    def from_snapshot(cls, payload: dict[str, Any]) -> "ResolvedResources":
        """Validate a submission-time policy snapshot before job launch."""
        required = {"cpus", "memory", "max_runtime_seconds", "nodes", "ntasks", "requires_gpu"}
        missing = sorted(required - set(payload))
        if missing:
            raise ResourceValidationError(f"Resource snapshot is missing: {', '.join(missing)}")
        requires_gpu = _boolean(payload.get("requires_gpu", False), "requires_gpu")
        max_runtime = normalize_resource_value(
            "max_runtime_seconds", payload.get("max_runtime_seconds")
        )
        declared_time = payload.get("slurm_time")
        if declared_time and slurm_time_to_seconds(str(declared_time)) != max_runtime:
            raise ResourceValidationError("Resource snapshot time fields are inconsistent")
        gres = normalize_resource_value("slurm_gres", payload.get("gres"))
        if requires_gpu and not gres:
            raise ResourceValidationError("GPU resource snapshot has no GRES")
        if not requires_gpu and gres:
            raise ResourceValidationError("CPU resource snapshot unexpectedly requests GPU GRES")
        return cls(
            cpus=normalize_resource_value("cpus", payload.get("cpus")),
            memory=normalize_resource_value("memory", payload.get("memory")),
            max_runtime_seconds=max_runtime,
            partition=normalize_resource_value("slurm_partition", payload.get("partition")),
            gres=gres,
            nodes=normalize_resource_value("slurm_nodes", payload.get("nodes")),
            ntasks=normalize_resource_value("slurm_ntasks", payload.get("ntasks")),
            qos=normalize_resource_value("slurm_qos", payload.get("qos")),
            account=normalize_resource_value("slurm_account", payload.get("account")),
            constraint=normalize_resource_value("slurm_constraint", payload.get("constraint")),
            exclusive=_boolean(payload.get("exclusive", False), "slurm_exclusive"),
            requires_gpu=requires_gpu,
            sources={"snapshot": "submission"},
        )


def resolve_resources(
    lookup_task: Callable[[str], Any],
    lookup_global: Callable[[str], Any],
    *,
    requires_gpu: bool,
    allowed_queues: list[str] | tuple[str, ...],
    default_timeout_seconds: int | None,
) -> ResolvedResources:
    """Resolve per-task, global, legacy, and safe defaults exactly once."""
    sources: dict[str, str] = {}

    def first(field: str, candidates: list[tuple[str, str]], default: Any) -> Any:
        for source, key in candidates:
            raw = lookup_task(key) if source == "task" else lookup_global(key)
            if raw is not None and str(raw).strip() != "":
                sources[field] = f"{source}:{key}"
                return normalize_resource_value(key, raw)
        sources[field] = "default"
        return default

    cpus = first(
        "cpus",
        [("task", "cpus"), ("task", "slurm_cpus_per_task"), ("task", "nproc"),
         ("global", "cpus"), ("global", "slurm_cpus_per_task"), ("global", "nproc")],
        1,
    )
    memory = first(
        "memory",
        [("task", "memory"), ("task", "slurm_mem")],
        None,
    )
    if memory is None:
        task_legacy_mem = first("memory", [("task", "maxmem")], None)
        if task_legacy_mem is not None:
            memory = f"{task_legacy_mem}G"
    if memory is None:
        memory = first(
            "memory",
            [("global", "memory"), ("global", "slurm_mem")],
            None,
        )
    if memory is None:
        global_legacy_mem = first("memory", [("global", "maxmem")], None)
        memory = f"{global_legacy_mem}G" if global_legacy_mem is not None else "4G"
        if global_legacy_mem is None:
            sources["memory"] = "default"

    configured_runtime = first(
        "max_runtime_seconds",
        [("task", "max_runtime_seconds"), ("global", "max_runtime_seconds")],
        default_timeout_seconds or 86400,
    )
    configured_time = first(
        "slurm_time",
        [("task", "slurm_time"), ("global", "slurm_time")],
        None,
    )
    if configured_time is not None:
        configured_runtime = min(configured_runtime, slurm_time_to_seconds(configured_time))
        sources["max_runtime_seconds"] += "+slurm_time"

    partition = first(
        "partition", [("task", "slurm_partition"), ("global", "slurm_partition")], None
    )
    if allowed_queues and partition not in allowed_queues:
        if partition is None:
            partition = allowed_queues[0]
            sources["partition"] = "allowed_queues:first"
        else:
            raise ResourceValidationError(
                f"Partition {partition!r} is not in the configured allowed queue list"
            )

    gres = None
    if requires_gpu:
        gres = first("gres", [("task", "slurm_gres"), ("global", "slurm_gres")], "gpu:1")
    elif lookup_task("slurm_gres") not in {None, ""}:
        raise ResourceValidationError("CPU-only task has a per-task GPU GRES override")
    else:
        sources["gres"] = "not-required"

    return ResolvedResources(
        cpus=cpus,
        memory=memory,
        max_runtime_seconds=configured_runtime,
        partition=partition,
        gres=gres,
        nodes=first("nodes", [("task", "slurm_nodes"), ("global", "slurm_nodes")], 1),
        ntasks=first("ntasks", [("task", "slurm_ntasks"), ("global", "slurm_ntasks")], 1),
        qos=first("qos", [("task", "slurm_qos"), ("global", "slurm_qos")], None),
        account=first("account", [("task", "slurm_account"), ("global", "slurm_account")], None),
        constraint=first(
            "constraint", [("task", "slurm_constraint"), ("global", "slurm_constraint")], None
        ),
        exclusive=first(
            "exclusive", [("task", "slurm_exclusive"), ("global", "slurm_exclusive")], False
        ),
        requires_gpu=requires_gpu,
        sources=sources,
    )
