# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Task-type registry (task_types.yaml) — the Python port of the awk
runtime_manifest and every registry validation restart.sh performed.

The server owns the registry schema; this module only reads it.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml
from revocompute_ctl.compose import run_cmd

_SAFE_FAMILY_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class RuntimeFamily:
    name: str
    docker_image: str
    dockerfile: str
    definition: str
    slurm_image: str


class RegistryError(Exception):
    """Validation failed; the message is already user-facing."""


def load_registry(config_root: str) -> tuple[str, str, list[RuntimeFamily]]:
    """Parse task_types.yaml → (job_executor, container_runtime, families).

    Mirrors the awk manifest: an incomplete family fails with the same
    message; no families is an error.
    """
    registry_file = Path(config_root) / "task_types.yaml"
    if not registry_file.is_file():
        print(f"Runtime registry is missing: {registry_file}", file=sys.stderr)
        raise RegistryError
    with open(registry_file, encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    job_executor = str(document.get("job_executor") or "")
    container_runtime = str(document.get("container_runtime") or "")
    families: list[RuntimeFamily] = []
    for name, entry in (document.get("runtime_families") or {}).items():
        if not isinstance(entry, dict):
            print(f"Incomplete runtime family: {name}", file=sys.stderr)
            raise RegistryError
        image = str(entry.get("docker_image") or "")
        dockerfile = str(entry.get("dockerfile") or "")
        definition = str(entry.get("definition") or "")
        slurm_image = str(entry.get("slurm_image") or "")
        if not image or not dockerfile or not definition or not slurm_image:
            print(f"Incomplete runtime family: {name}", file=sys.stderr)
            raise RegistryError
        families.append(RuntimeFamily(name, image, dockerfile, definition, slurm_image))
    if not families:
        print("No runtime families declared in registry", file=sys.stderr)
        raise RegistryError
    return job_executor, container_runtime, families


def resolve_job_executor(registry_file: str) -> str:
    """The scalar read restart.sh performed before every dispatch: the
    executor that selects USE_SLURM and the compose override."""
    if not Path(registry_file).is_file():
        return ""
    with open(registry_file, encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    return str(document.get("job_executor") or "")


def validate_runtime_files(state) -> list[RuntimeFamily]:
    """Port of validate_runtime_files() — every family, artifact, and runner
    YAML check, with the pinned messages."""
    config_root = state.config_dir()
    registry_file = str(Path(config_root) / "task_types.yaml")
    runners_dir = Path(config_root) / "runners"
    server_root = Path(state.server_root())
    job_executor, container_runtime, families = load_registry(config_root)
    if job_executor not in ("docker", "slurm"):
        print(f"job_executor must be docker or slurm in {registry_file}", file=sys.stderr)
        raise RegistryError
    if (job_executor == "docker" and container_runtime != "docker") or (
        job_executor == "slurm" and container_runtime != "apptainer"
    ):
        print(f"container_runtime is inconsistent with job_executor in {registry_file}", file=sys.stderr)
        raise RegistryError
    if not runners_dir.is_dir():
        print(f"Runtime runner directory is missing: {runners_dir}", file=sys.stderr)
        raise RegistryError

    known: set[str] = set()
    for family in families:
        if not _SAFE_FAMILY_NAME.match(family.name):
            print(f"Runtime family name is not safe for Compose: {family.name}", file=sys.stderr)
            raise RegistryError
        for relative_path in (family.dockerfile, family.definition):
            if (
                relative_path.startswith("/")
                or relative_path == ".."
                or relative_path.startswith("../")
                or "/../" in relative_path
                or relative_path.endswith("/..")
                or "\\" in relative_path
            ):
                print(f"Runtime family {family.name} has unsafe build path: {relative_path}", file=sys.stderr)
                raise RegistryError
            if not (server_root / relative_path).is_file():
                print(
                    f"Runtime family {family.name} is missing build artifact: {server_root / relative_path}",
                    file=sys.stderr,
                )
                raise RegistryError

        runner_yaml = runners_dir / f"{family.name}.yaml"
        if not runner_yaml.is_file():
            print(f"Runtime family {family.name} is missing runner configuration: {runner_yaml}", file=sys.stderr)
            raise RegistryError
        if job_executor == "slurm" and not family.slurm_image.startswith("/"):
            print(f"SLURM runtime family {family.name} must declare an absolute slurm_image", file=sys.stderr)
            raise RegistryError

        definition_text = (server_root / family.definition).read_text(encoding="utf-8")
        bootstrap = _first_directive_value(definition_text, "Bootstrap:")
        definition_image = _first_directive_value(definition_text, "From:")
        expected_image = family.docker_image
        image_leaf = expected_image.rsplit("/", 1)[-1]
        if ":" not in image_leaf and "@" not in expected_image:
            expected_image = f"{expected_image}:latest"
        if bootstrap != "docker-daemon" or definition_image != expected_image:
            print(
                f"Runtime family {family.name} definition must use docker-daemon image {expected_image}",
                file=sys.stderr,
            )
            raise RegistryError
        known.add(family.name)

    for runner_yaml in sorted(runners_dir.glob("*.yaml")):
        name = runner_yaml.stem
        if name not in known:
            print(f"Stale runner configuration has no runtime family: {runner_yaml}", file=sys.stderr)
            raise RegistryError
    return families


def _first_directive_value(text: str, directive: str) -> str:
    for line in text.splitlines():
        if line.split(" ", 1)[0] == directive:
            return line.split(":", 1)[1].strip()
    return ""


# -- enabled-runner selection ------------------------------------------------


def expand_enabled_runners(state, families: list[RuntimeFamily]) -> None:
    """Normalize empty ENABLED_TASKRUNNERS ("build all") into an explicit
    list so a failed runner can be dropped from it for the rest of the run."""
    if state.get("ENABLED_TASKRUNNERS"):
        return
    state.runtime["ENABLED_TASKRUNNERS"] = ",".join(family.name for family in families)


def runner_enabled(state, name: str) -> bool:
    enabled = state.get("ENABLED_TASKRUNNERS")
    if not enabled:
        return True
    return name in enabled.split(",")


def drop_enabled_runner(state, target: str) -> None:
    remaining = [name for name in state.get("ENABLED_TASKRUNNERS").split(",") if name and name != target]
    state.runtime["ENABLED_TASKRUNNERS"] = ",".join(remaining)


# -- SLURM images ------------------------------------------------------------


def staged_sif_path(family: RuntimeFamily) -> str:
    """The activation target: a freshly staged .next when present, else the
    deployed SIF."""
    staged = f"{family.slurm_image}.next"
    return staged if Path(staged).is_file() else family.slurm_image


def validate_slurm_images(state, families: list[RuntimeFamily]) -> None:
    missing = 0
    for family in families:
        if not runner_enabled(state, family.name):
            continue
        target = staged_sif_path(family)
        if not Path(target).is_file():
            print(f"[SLURM] Missing SIF image: {family.slurm_image}", file=sys.stderr)
            print(
                "        Build it:  apptainer build --fakeroot "
                f"{family.slurm_image} {state.server_root()}/{family.definition}",
                file=sys.stderr,
            )
            missing += 1
        else:
            print(f"[SLURM] Found SIF image: {family.slurm_image}")
    if missing:
        print(
            f"[SLURM] {missing} SIF image(s) missing. Rerun with --build-sif to auto-build, or build manually.",
            file=sys.stderr,
        )
        raise RegistryError


def _docker_tag(image: str, suffix: str = "latest") -> str:
    repository = image.rsplit("/", 1)[-1]
    return f"{image}:{suffix}" if ":" not in repository and "@" not in image else image


def _docker_image_id(state, tag: str) -> str:
    return run_cmd(
        ["docker", "image", "inspect", "--format", "{{.Id}}", tag],
        env=state.exported(),
        check=False,
        capture=True,
    ).stdout.strip()


def _sif_source_tag(state, family: RuntimeFamily) -> str:
    """Use the prepared runner image when this restart built one."""
    latest = _docker_tag(family.docker_image)
    if latest.endswith(":latest"):
        prepared = f"{latest[:-len(':latest')]}:next"
        if _docker_image_id(state, prepared):
            return prepared
    return latest


def sif_stale(state, family: RuntimeFamily) -> bool:
    """True when the deployed SIF needs a rebuild: it is missing, or the
    family's docker image was created after the SIF (covers image updates
    promoted in an earlier restart — the image digest itself may be
    unchanged while the SIF still predates it)."""
    if not Path(family.slurm_image).is_file():
        return True
    latest = _docker_tag(family.docker_image)
    tag = _sif_source_tag(state, family)
    if tag != latest and _docker_image_id(state, tag) != _docker_image_id(state, latest):
        return True
    created = run_cmd(
        ["docker", "image", "inspect", "--format", "{{.Created}}", tag],
        env=state.exported(),
        check=False,
        capture=True,
    ).stdout.strip()
    try:
        import datetime

        image_ts = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        image_ts = 0.0
    return image_ts > os.path.getmtime(family.slurm_image)


def _sif_definition_for_tag(def_file: Path, source_tag: str) -> tuple[str, str | None]:
    """Return a definition using the prepared Docker tag, plus a temp path to clean up."""
    text = def_file.read_text(encoding="utf-8")
    current = _first_directive_value(text, "From:")
    if source_tag == current:
        return str(def_file), None
    updated = text.replace(f"From: {current}", f"From: {source_tag}", 1)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".def", delete=False)
    try:
        handle.write(updated)
    finally:
        handle.close()
    return handle.name, handle.name


def build_slurm_images(state, families: list[RuntimeFamily]) -> int:
    """Stage SIFs as ``<sif>.next`` for missing or stale families only;
    promotion (promotion.py) moves them into place after down.  Returns the
    number of SIFs built."""
    import shutil

    if not shutil.which("apptainer"):
        print("[SLURM] apptainer not found on PATH; cannot build requested SIF images.", file=sys.stderr)
        raise RegistryError

    expand_enabled_runners(state, families)
    built = 0
    for family in families:
        if not runner_enabled(state, family.name):
            continue
        def_file = Path(state.server_root()) / family.definition
        if not def_file.is_file():
            print(f"[SLURM] No .def file for runtime family '{family.name}': {def_file}", file=sys.stderr)
            drop_enabled_runner(state, family.name)
            continue
        staged = f"{family.slurm_image}.next"
        if Path(staged).is_file():
            continue
        if not sif_stale(state, family):
            print(f"[SLURM] SIF image unchanged: {family.slurm_image} — skipping.")
            continue
        print(f"[SLURM] Building {staged} from {def_file}...")
        # Atomic staging: a killed build must never leave a corrupt .next
        # that the next run treats as a valid staging.
        staging = f"{staged}.build"
        build_definition, temporary_definition = _sif_definition_for_tag(
            def_file, _sif_source_tag(state, family)
        )
        try:
            result = run_cmd(
                ["apptainer", "build", "--fakeroot", staging, build_definition],
                env=state.exported(),
                check=False,
            )
        finally:
            if temporary_definition is not None:
                os.remove(temporary_definition)
        if result.returncode != 0:
            if os.path.isfile(staging):
                os.remove(staging)
            print(f"[SLURM] Build failed for {family.name} — disabled for this restart.", file=sys.stderr)
            drop_enabled_runner(state, family.name)
        else:
            os.replace(staging, staged)
            built += 1
    if built:
        print(f"[SLURM] Built {built} SIF image(s).")
    return built


# -- prepared activation -----------------------------------------------------


def validate_prepared_images(state, families: list[RuntimeFamily]) -> None:
    required = [
        state.get("SERVER_IMAGE") or "revodesign-revocompute-server:latest",
        "nginx:1.28-alpine",
        "redis:7.2-alpine",
    ]
    for family in families:
        if runner_enabled(state, family.name):
            candidates = (family.docker_image, _docker_tag(family.docker_image, "next"))
            if all(
                run_cmd(
                    ["docker", "image", "inspect", image], env=state.exported(), check=False, capture=True
                ).returncode
                != 0
                for image in candidates
            ):
                print(f"Prepared Docker image is missing: {family.docker_image}", file=sys.stderr)
                raise RegistryError
    for image in required:
        result = run_cmd(["docker", "image", "inspect", image], env=state.exported(), check=False, capture=True)
        if result.returncode != 0:
            print(f"Prepared Docker image is missing: {image}", file=sys.stderr)
            raise RegistryError


def validate_compose_model(state, compose_cmd: tuple[str, ...]) -> None:
    run_cmd(
        [*compose_cmd, *state.compose_args(), "--env-file", state.env_file, "config", "--quiet"],
        env=state.exported(),
    )
