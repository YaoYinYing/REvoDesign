# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Task-type registry (task_types.yaml) — the Python port of the awk
runtime_manifest and every registry validation restart.sh performed.

The server owns the registry schema; this module only reads it.
"""

from __future__ import annotations

import hashlib
import json
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
    requested = {name for name in state.get("ENABLED_TASKRUNNERS").split(",") if name}
    unknown = requested - known
    if unknown:
        print(f"Unknown runner selection: {', '.join(sorted(unknown))}", file=sys.stderr)
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


def _sif_digest_manifest(family: RuntimeFamily) -> Path:
    return Path(family.slurm_image).parent / "digest" / "image-sif.json"


def _sif_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _read_sif_manifest(family: RuntimeFamily) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(_sif_digest_manifest(family).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _record_sif_manifest(family: RuntimeFamily, docker_image_id: str, sif_path: str) -> None:
    manifest = _sif_digest_manifest(family)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    data = _read_sif_manifest(family)
    data[family.name] = {"docker_image_id": docker_image_id, "sif_sha256": _sif_sha256(sif_path)}
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=manifest.parent, delete=False)
    try:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    finally:
        handle.close()
    os.replace(handle.name, manifest)


def _sif_manifest_matches(family: RuntimeFamily, docker_image_id: str, sif_path: str) -> bool:
    entry = _read_sif_manifest(family).get(family.name) or {}
    return (
        bool(docker_image_id)
        and entry.get("docker_image_id") == docker_image_id
        and entry.get("sif_sha256") == _sif_sha256(sif_path)
    )


def _sif_source_tag(state, family: RuntimeFamily) -> str:
    return _docker_tag(family.docker_image)


def sif_stale(state, family: RuntimeFamily, path: str | None = None) -> bool:
    """True unless the SIF manifest proves the file matches the Docker image."""
    path = path or family.slurm_image
    if not Path(path).is_file():
        return True
    tag = _sif_source_tag(state, family)
    source_id = _docker_image_id(state, tag)
    return not _sif_manifest_matches(family, source_id, path)


def _sif_definition_for_tag(def_file: Path, source_tag: str) -> tuple[str, str | None]:
    """Return a definition using the source Docker tag, plus a temp path to clean up."""
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


def build_slurm_images(state, families: list[RuntimeFamily], *, fail_on_error: bool = False) -> int:
    """Stage SIFs as ``<sif>.next`` for missing or stale families only;
    promotion (promotion.py) moves them into place after down.  The source
    Docker image ID captured before each build is re-checked afterwards; a
    changed ID means the tag was retagged concurrently, and the staging is
    discarded instead of recording mismatched metadata.  Returns the number
    of SIFs built."""
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
            if not sif_stale(state, family, staged):
                continue
            os.remove(staged)
        if not sif_stale(state, family):
            print(f"[SLURM] SIF image unchanged: {family.slurm_image} — skipping.")
            continue
        print(f"[SLURM] Building {staged} from {def_file}...")
        # Atomic staging: a killed build must never leave a corrupt .next
        # that the next run treats as a valid staging.
        staging = f"{staged}.build"
        source_tag = _sif_source_tag(state, family)
        source_id = _docker_image_id(state, source_tag)
        if not source_id:
            print(f"[SLURM] Docker image identity is unavailable: {source_tag}", file=sys.stderr)
            raise RegistryError
        build_definition, temporary_definition = _sif_definition_for_tag(def_file, source_tag)
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
            if fail_on_error:
                raise RegistryError
        elif _docker_image_id(state, source_tag) != source_id:
            # The tag was retagged while apptainer ran: the staging belongs to
            # an image this process never saw.  Nothing tied to it may be
            # written or promoted.
            if os.path.isfile(staging):
                os.remove(staging)
            print(
                f"[SLURM] Docker image {source_tag} changed during the {family.name} SIF build — discarding it.",
                file=sys.stderr,
            )
            raise RegistryError
        else:
            os.replace(staging, staged)
            _record_sif_manifest(family, source_id, staged)
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
            latest = _docker_tag(family.docker_image)
            if (
                run_cmd(
                    ["docker", "image", "inspect", latest], env=state.exported(), check=False, capture=True
                ).returncode
                != 0
            ):
                print(f"Prepared Docker image is missing: {family.docker_image}", file=sys.stderr)
                raise RegistryError
            staged = Path(f"{family.slurm_image}.next")
            source_id = _docker_image_id(state, _sif_source_tag(state, family))
            if state.use_slurm():
                # Whatever staged_sif_path() selects is what activates — with
                # no staging that is the deployed SIF, so it is validated too.
                if staged.is_file():
                    if not _sif_manifest_matches(family, source_id, str(staged)):
                        print(f"Prepared SIF does not match Docker image: {family.name}", file=sys.stderr)
                        raise RegistryError
                elif Path(family.slurm_image).is_file() and sif_stale(state, family):
                    print(
                        f"Prepared SIF does not match Docker image: {family.name}",
                        file=sys.stderr,
                    )
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
