# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Task and runtime-family registry.

Server code never needs to know about individual task types — a new task
type selects a shared runtime family, while the family owns the image,
entrypoint, Dockerfile, Apptainer definition, and machine-specific runner
configuration.
"""

from __future__ import annotations

import os
import re
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
    label: str = ""
    choices: tuple[Any, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    unit: str = ""
    help: str = ""
    advanced: bool = False


@dataclass(frozen=True)
class InputCapability:
    """A safe, declarative input-workspace component.

    Capabilities select browser code that is already shipped with the server;
    registry YAML cannot supply executable code or remote plugin locations.
    """

    plugin: str
    id: str
    title: str = ""
    description: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InputStep:
    """One meaningful, ordered step in the user-facing experiment protocol."""

    id: str
    title: str
    description: str
    capabilities: tuple[InputCapability, ...]


@dataclass(frozen=True)
class Category:
    """Server-owned presentation metadata for a scientific method group."""

    name: str
    label: str
    description: str
    order: int


@dataclass(frozen=True)
class ResultView:
    """A safe task-owned composition of local result-view plugins."""

    plugin: str
    id: str
    title: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeFamily:
    """Portable execution environment shared by one or more task types."""

    name: str
    docker_image: str
    entrypoint: tuple[str, ...]
    dockerfile: str
    definition: str
    slurm_image: str = ""


@dataclass(frozen=True)
class WorkflowStage:
    """One scheduler allocation in an ordered task workflow."""

    name: str
    display_name: str
    requires_gpu: bool
    runner_args: tuple[str, ...] = ()
    stage_markers: tuple[str, ...] = ()
    requires_network: bool = False


@dataclass(frozen=True)
class TaskType:
    """Portable user-facing task definition.

    Runtime implementation details live in RuntimeFamily. Machine-specific
    paths and resource limits live in RunnerConfig.
    """

    name: str  # "gremlin", "alphafold", "diffdock", "esm"
    display_name: str  # "PSSM-GREMLIN", "AlphaFold2"

    runtime: RuntimeFamily

    input_extension: str  # ".fasta", ".pdb"
    input_label: str  # "FASTA file", "PDB file"

    # Optional fields with defaults
    input_extensions: tuple[str, ...] = ()
    primary_input_extensions: tuple[str, ...] = ()
    allow_multiple_inputs: bool = False
    max_input_files: int = 1
    min_input_files: int = 1
    runner_args: tuple[str, ...] = ()
    gpus: bool = False
    requires_network: bool = False
    stage_markers: dict[str, str] = field(default_factory=dict)
    workflow: tuple[WorkflowStage, ...] = ()
    params: tuple[TaskParam, ...] = ()
    input_workspace: tuple[InputStep, ...] = ()
    result_workspace: tuple[ResultView, ...] = ()
    # Method citations: citation_dois is an ordered map (position -> DOI) —
    # projects with multiple papers (AF2, ColabFold, ESM) list them all. The
    # BibTeX is resolved from the DOIs by tools/resolve_citations.py (never
    # hand-guessed) and checked in as citation_bibtex. The server writes it
    # into every result dir as citations.bib at finalize.
    citation_dois: tuple[tuple[int, str, str], ...] = ()
    citation_bibtex: str = ""
    category: str = "other"
    summary: str = ""
    use_when: str = ""
    input_summary: str = ""
    output_summary: str = ""
    considerations: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunnerMount:
    """A bind mount from host into the runner container."""

    host_path: str  # "/srv/revodesign/databases/uniref30"
    container_path: str  # "/opt/db/uniref30"
    mode: str = "ro"  # "ro" | "rw"


@dataclass(frozen=True)
class RunnerConfig:
    """Deployment-specific settings for a task type.

    Loaded from ``config/runners/<runtime-family>.yaml`` at startup. Host paths are
    machine-specific — edit the YAML when deploying to a new node, never
    the global ``.env``.
    """

    mounts: tuple[RunnerMount, ...] = ()
    env: dict[str, str] = field(default_factory=dict)  # extra env vars → container
    max_runtime_seconds: int | None = None  # override task_type default if set
    defaults: dict[str, Any] = field(default_factory=dict)  # default param values


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_registry: dict[str, tuple[TaskType, RunnerConfig]] = {}
_runtime_registry: dict[str, RuntimeFamily] = {}
_category_registry: dict[str, Category] = {}
_job_executor = "docker"
_container_runtime = "docker"

_INPUT_CAPABILITY_PLUGINS = {
    "files",
    "sequence",
    "structure",
    "regions",
    "rfdiffusion-regions",
    "parameters",
    "review",
}
_INPUT_CAPABILITY_OPTION_KEYS = {
    "files": {"primary_required"},
    "sequence": set(),
    "structure": {"source", "select_chains", "select_residues"},
    "regions": {"source", "fields", "syntax", "modes"},
    "rfdiffusion-regions": {"source", "fields", "syntax", "modes"},
    "parameters": set(),
    "review": {"show_paths"},
}

_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[^\s]+$")


def _load_citation_dois(raw: Any, name: str) -> tuple[tuple[int, str, str], ...]:
    """Validate the ordered citation_dois list. Each entry is
    {num, doi, title}: the DOI identifies the paper and the declared title
    enables human checks (the resolver verifies it against the fetched
    BibTeX). BibTeX is resolved from the DOIs by
    tools/resolve_citations.py — never hand-guessed."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError(f"Task type {name!r} citation_dois must be a list of {{num, doi, title}}")
    ordered: list[tuple[int, str, str]] = []
    seen: set[int] = set()
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != {"num", "doi", "title"}:
            raise ValueError(f"Task type {name!r} citation entries must be exactly {{num, doi, title}}")
        num = entry["num"]
        if not isinstance(num, int) or isinstance(num, bool) or num in seen:
            raise ValueError(f"Task type {name!r} has an invalid citation num: {num!r}")
        seen.add(num)
        doi = entry["doi"]
        title = entry.get("title", "")
        if not isinstance(doi, str) or not _DOI_PATTERN.fullmatch(doi.strip()):
            raise ValueError(f"Task type {name!r} has an invalid citation DOI: {doi!r}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Task type {name!r} citation {num} must declare the paper title")
        ordered.append((num, doi.strip(), title.strip()))
    return tuple(sorted(ordered))


_RESULT_VIEW_PLUGINS = {"residue-table-structure"}
_RESULT_VIEW_OPTION_KEYS = {
    "residue-table-structure": {
        "table_path",
        "structure_path",
        "chain_column",
        "residue_column",
        "numbering",
        "group",
    }
}


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


def list_runtimes() -> list[RuntimeFamily]:
    """Return all runtime families loaded from the portable registry."""
    return list(_runtime_registry.values())


def list_categories() -> list[Category]:
    """Return scientific categories in their server-owned display order."""
    return sorted(_category_registry.values(), key=lambda category: (category.order, category.name))


def iter_capabilities(task_type: TaskType) -> tuple[InputCapability, ...]:
    """Flatten one task's semantic steps into deterministic plugin order."""
    return tuple(capability for step in task_type.input_workspace for capability in step.capabilities)


def get_job_executor() -> str:
    """Return the executor selected once for the active registry."""
    return _job_executor


def get_container_runtime() -> str:
    """Return the container runtime selected once for the active registry."""
    return _container_runtime


def _valid_identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value.replace("_", "").replace("-", "").isalnum()


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value.strip()


def _load_input_capability(entry: Any, seen_ids: set[str]) -> InputCapability:
    if not isinstance(entry, dict):
        raise ValueError("Each input workspace capability must be a mapping")
    unknown = set(entry) - {"plugin", "id", "title", "description", "options"}
    if unknown:
        raise ValueError(f"Unknown input workspace capability fields: {sorted(unknown)}")
    plugin = entry.get("plugin")
    capability_id = entry.get("id")
    if plugin not in _INPUT_CAPABILITY_PLUGINS:
        raise ValueError(f"Unknown input workspace plugin: {plugin!r}")
    if not _valid_identifier(capability_id):
        raise ValueError(f"Invalid input workspace capability id: {capability_id!r}")
    if capability_id in seen_ids:
        raise ValueError(f"Duplicate input workspace capability id: {capability_id!r}")
    options = entry.get("options", {})
    if not isinstance(options, dict):
        raise ValueError(f"Options for input workspace capability {capability_id!r} must be a mapping")
    unknown_options = set(options) - _INPUT_CAPABILITY_OPTION_KEYS[plugin]
    if unknown_options:
        raise ValueError(f"Unknown options for input workspace plugin {plugin!r}: {sorted(unknown_options)}")
    seen_ids.add(capability_id)
    return InputCapability(
        plugin=plugin,
        id=capability_id,
        title=str(entry.get("title") or ""),
        description=str(entry.get("description") or ""),
        options=options,
    )


def _load_input_workspace(raw: Any) -> tuple[InputStep, ...]:
    if raw is None:
        raise ValueError("Every task type must declare input_workspace")
    if not isinstance(raw, dict) or set(raw) != {"steps"}:
        raise ValueError("input_workspace must contain only a steps list")
    entries = raw["steps"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("input_workspace.steps must be a non-empty list")
    steps: list[InputStep] = []
    step_ids: set[str] = set()
    capability_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - {"id", "title", "description", "capabilities"}:
            raise ValueError("Each input workspace step must contain id, title, description, and capabilities")
        step_id = entry.get("id")
        if not _valid_identifier(step_id) or step_id in step_ids:
            raise ValueError(f"Invalid or duplicate input workspace step id: {step_id!r}")
        raw_capabilities = entry.get("capabilities")
        if not isinstance(raw_capabilities, list) or not raw_capabilities:
            raise ValueError(f"Input workspace step {step_id!r} must contain capabilities")
        step_ids.add(step_id)
        steps.append(
            InputStep(
                id=step_id,
                title=_required_text(entry.get("title"), f"Input workspace step {step_id!r} title"),
                description=str(entry.get("description") or "").strip(),
                capabilities=tuple(_load_input_capability(item, capability_ids) for item in raw_capabilities),
            )
        )
    capabilities = tuple(capability for step in steps for capability in step.capabilities)
    if capabilities[0].plugin not in {"files", "sequence"}:
        raise ValueError("The first input workspace capability must collect files or a sequence")
    if capabilities[-1].plugin != "review":
        raise ValueError("The last input workspace capability must be review")
    known_ids = {capability.id for capability in capabilities}
    for capability in capabilities:
        source = capability.options.get("source")
        if source and source not in known_ids:
            raise ValueError(f"Input workspace capability {capability.id!r} references unknown source {source!r}")
    return tuple(steps)


def _load_result_workspace(raw: Any) -> tuple[ResultView, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, dict) or set(raw) != {"views"} or not isinstance(raw["views"], list):
        raise ValueError("result_workspace must contain only a views list")
    views: list[ResultView] = []
    seen: set[str] = set()
    for entry in raw["views"]:
        if not isinstance(entry, dict) or set(entry) - {"plugin", "id", "title", "options"}:
            raise ValueError("Invalid result workspace view")
        plugin = entry.get("plugin")
        view_id = entry.get("id")
        if plugin not in _RESULT_VIEW_PLUGINS:
            raise ValueError(f"Unknown result workspace plugin: {plugin!r}")
        if not isinstance(view_id, str) or not view_id or not view_id.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"Invalid result workspace view id: {view_id!r}")
        if view_id in seen:
            raise ValueError(f"Duplicate result workspace view id: {view_id!r}")
        options = entry.get("options", {})
        if not isinstance(options, dict) or set(options) - _RESULT_VIEW_OPTION_KEYS[plugin]:
            raise ValueError(f"Invalid options for result workspace plugin {plugin!r}")
        required = {"table_path", "structure_path", "chain_column", "residue_column", "numbering"}
        if not required.issubset(options) or options["numbering"] not in {"label_seq_id", "auth_seq_id"}:
            raise ValueError(f"Incomplete result workspace mapping for {view_id!r}")
        for key in ("table_path", "structure_path"):
            path = str(options[key])
            if path.startswith("/") or any(part in {"", ".", ".."} for part in path.split("/")):
                raise ValueError(f"Unsafe result workspace artifact path: {path!r}")
        seen.add(view_id)
        views.append(ResultView(plugin=plugin, id=view_id, title=str(entry.get("title") or view_id), options=options))
    return tuple(views)


def _load_workflow(raw: Any, task_name: str, stage_markers: dict[str, str]) -> tuple[WorkflowStage, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError(f"Task type {task_name!r} workflow must contain at least two stages")
    stages: list[WorkflowStage] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) - {
            "name",
            "display_name",
            "requires_gpu",
            "requires_network",
            "runner_args",
            "stage_markers",
        }:
            raise ValueError(f"Task type {task_name!r} has an invalid workflow stage")
        name = entry.get("name")
        requires_gpu = entry.get("requires_gpu", False)
        requires_network = entry.get("requires_network", False)
        runner_args = entry.get("runner_args", ())
        raw_markers = entry.get("stage_markers", ())
        if not isinstance(name, str) or not name.replace("_", "").isalnum() or name in seen:
            raise ValueError(f"Task type {task_name!r} has an invalid or duplicate workflow stage name")
        if not isinstance(requires_gpu, bool):
            raise ValueError(f"Workflow stage {task_name}.{name} requires_gpu must be a boolean")
        if not isinstance(requires_network, bool):
            raise ValueError(f"Workflow stage {task_name}.{name} requires_network must be a boolean")
        if not isinstance(runner_args, list) or not all(isinstance(arg, str) for arg in runner_args):
            raise ValueError(f"Workflow stage {task_name}.{name} runner_args must be a list of strings")
        if not isinstance(raw_markers, list) or not all(isinstance(marker, str) for marker in raw_markers):
            raise ValueError(f"Workflow stage {task_name}.{name} stage_markers must be a list of strings")
        markers = tuple(raw_markers)
        if not markers or not set(markers).issubset(stage_markers):
            raise ValueError(f"Workflow stage {task_name}.{name} must reference declared stage markers")
        seen.add(name)
        stages.append(
            WorkflowStage(
                name=f"{task_name}.{name}",
                display_name=str(entry.get("display_name") or name.replace("_", " ").title()),
                requires_gpu=requires_gpu,
                requires_network=requires_network,
                runner_args=tuple(runner_args),
                stage_markers=markers,
            )
        )
    return tuple(stages)


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


# PTC-W6004: operator-provisioned runner YAML path, not user input
def _load_runner_config(path: str) -> RunnerConfig:  # skipcq: PTC-W6004
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
        max_runtime_seconds=data.get("max_runtime_seconds"),
        defaults=data.get("defaults", {}),
    )


def load_registry(task_types_yaml: str, runners_dir: str, enabled: set[str]) -> None:
    """Load task type definitions and per-runner configs.

    Reads runtime families and task types, then loads one machine-specific
    runner YAML per runtime family. Filtered by ``ENABLED_TASKRUNNERS``;
    ``gremlin`` is always enabled.
    """
    with open(task_types_yaml, encoding="utf-8") as f:
        types_data = yaml.safe_load(f)  # skipcq: PTC-W6004 — deployment-owned registry path, not user input

    if not types_data:
        raise ValueError(f"Task registry is empty: {task_types_yaml}")

    _registry.clear()
    _runtime_registry.clear()
    _category_registry.clear()

    if "job_executor" not in types_data or "container_runtime" not in types_data:
        raise ValueError("Task registry must declare global job_executor and container_runtime")
    job_executor = types_data["job_executor"]
    container_runtime = types_data["container_runtime"]
    if job_executor not in {"docker", "slurm"}:
        raise ValueError(f"Unsupported global job_executor: {job_executor!r}")
    if job_executor == "docker" and container_runtime != "docker":
        raise ValueError("Docker job_executor requires container_runtime: docker")
    if job_executor == "slurm" and container_runtime != "apptainer":
        raise ValueError("SLURM job_executor requires container_runtime: apptainer")

    runtimes: dict[str, RuntimeFamily] = {}
    for name, entry in types_data.get("runtime_families", {}).items():
        if "slurm_image" not in entry or not entry["slurm_image"]:
            raise ValueError(f"Runtime family {name!r} must declare slurm_image")
        slurm_image = str(entry.get("slurm_image") or "")
        if job_executor == "slurm" and not slurm_image:
            raise ValueError(f"SLURM runtime family {name!r} must set slurm_image")
        runtimes[name] = RuntimeFamily(
            name=name,
            docker_image=entry["docker_image"],
            entrypoint=tuple(entry["entrypoint"]),
            dockerfile=entry["dockerfile"],
            definition=entry["definition"],
            slurm_image=slurm_image,
        )
    _runtime_registry.update(runtimes)
    for task_name, task_entry in types_data.get("task_types", {}).items():
        runtime_name = task_entry.get("runtime_family")
        if runtime_name not in runtimes:
            raise ValueError(f"Task type {task_name!r} references unknown runtime family {runtime_name!r}")

    raw_categories = types_data.get("categories")
    if not isinstance(raw_categories, dict) or not raw_categories:
        raise ValueError("Task registry must declare scientific categories")
    category_orders: set[int] = set()
    for name, entry in raw_categories.items():
        if (
            not _valid_identifier(name)
            or not isinstance(entry, dict)
            or set(entry) != {"label", "description", "order"}
        ):
            raise ValueError(f"Invalid scientific category: {name!r}")
        order = entry["order"]
        if not isinstance(order, int) or isinstance(order, bool) or order in category_orders:
            raise ValueError(f"Scientific category {name!r} must have a unique integer order")
        category_orders.add(order)
        _category_registry[name] = Category(
            name=name,
            label=_required_text(entry["label"], f"Scientific category {name!r} label"),
            description=_required_text(entry["description"], f"Scientific category {name!r} description"),
            order=order,
        )

    runner_configs: dict[str, RunnerConfig] = {}
    for name, entry in types_data.get("task_types", {}).items():
        runtime_name = entry["runtime_family"]
        if name != "gremlin" and runtime_name not in enabled:
            continue
        if runtime_name not in runtimes:
            raise ValueError(f"Task type {name!r} references unknown runtime family {runtime_name!r}")
        runtime = runtimes[runtime_name]
        if runtime_name not in runner_configs:
            runner_yaml = os.path.join(runners_dir, f"{runtime_name}.yaml")
            if not os.path.exists(runner_yaml):
                raise FileNotFoundError(
                    f"Runtime family {runtime_name!r} requires runner configuration {runner_yaml!r}"
                )
            runner_configs[runtime_name] = _load_runner_config(runner_yaml)

        input_extensions = tuple(entry.get("input_extensions", [entry["input_extension"]]))
        primary_input_extensions = tuple(entry.get("primary_input_extensions", [entry["input_extension"]]))
        allow_multiple_inputs = entry.get("allow_multiple_inputs", False)
        max_input_files = entry.get("max_input_files", 1)
        min_input_files = entry.get("min_input_files", 1)
        if not input_extensions:
            raise ValueError(f"Task type {name!r} must accept at least one input extension")
        if not set(primary_input_extensions).issubset(input_extensions):
            raise ValueError(f"Task type {name!r} primary input extensions must be accepted input extensions")
        if not isinstance(max_input_files, int) or isinstance(max_input_files, bool) or max_input_files < 1:
            raise ValueError(f"Task type {name!r} max_input_files must be a positive integer")
        if not allow_multiple_inputs and max_input_files != 1:
            raise ValueError(f"Task type {name!r} must set max_input_files to 1 when multiple inputs are disabled")
        if (
            not isinstance(min_input_files, int)
            or isinstance(min_input_files, bool)
            or not 0 <= min_input_files <= max_input_files
        ):
            raise ValueError(f"Task type {name!r} min_input_files must be between zero and max_input_files")

        category = entry.get("category", "other")
        if category not in _category_registry:
            raise ValueError(f"Task type {name!r} references unknown category {category!r}")
        params = tuple(TaskParam(**{**p, "choices": tuple(p.get("choices", []))}) for p in entry.get("params", []))
        for param in params:
            if param.type not in {"str", "int", "float", "bool"}:
                raise ValueError(f"Task type {name!r} parameter {param.name!r} has unsupported type {param.type!r}")
        considerations = entry.get("considerations")
        if not isinstance(considerations, list) or not considerations:
            raise ValueError(f"Task type {name!r} must declare considerations")
        consideration_text = tuple(_required_text(item, f"Task type {name!r} consideration") for item in considerations)
        stage_markers = entry.get("stage_markers", {})
        tt = TaskType(
            name=name,
            display_name=entry["display_name"],
            runtime=runtime,
            runner_args=tuple(entry.get("runner_args", [])),
            gpus=entry.get("gpus", False),
            requires_network=entry.get("requires_network", False),
            input_extension=entry["input_extension"],
            input_label=entry["input_label"],
            category=category,
            summary=_required_text(entry.get("summary"), f"Task type {name!r} summary"),
            use_when=_required_text(entry.get("use_when"), f"Task type {name!r} use_when"),
            input_summary=_required_text(entry.get("input_summary"), f"Task type {name!r} input_summary"),
            output_summary=_required_text(entry.get("output_summary"), f"Task type {name!r} output_summary"),
            considerations=consideration_text,
            input_extensions=input_extensions,
            primary_input_extensions=primary_input_extensions,
            allow_multiple_inputs=allow_multiple_inputs,
            max_input_files=max_input_files,
            min_input_files=min_input_files,
            stage_markers=stage_markers,
            workflow=_load_workflow(entry.get("workflow"), name, stage_markers),
            params=params,
            input_workspace=_load_input_workspace(entry.get("input_workspace")),
            result_workspace=_load_result_workspace(entry.get("result_workspace")),
            citation_dois=_load_citation_dois(entry.get("citation_dois"), name),
            citation_bibtex=entry.get("citation_bibtex", ""),
        )

        register(tt, runner_configs[runtime_name])

    global _job_executor, _container_runtime
    _job_executor = job_executor
    _container_runtime = container_runtime
