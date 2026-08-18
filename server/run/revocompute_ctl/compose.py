# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Docker / Compose helpers — the only subprocess path in the control module.

run_cmd never logs argv (proxy URLs must not leak into logs).  stdout and
stderr are inherited unless capture is requested.
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import sys
from typing import Sequence

log = logging.getLogger("revocompute_ctl")


def run_cmd(
    argv: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
    check: bool = True,
    capture: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one command. Never log the argv — callers log their own summaries."""
    completed = subprocess.run(
        list(argv),
        env=env if env is not None else dict(os.environ),
        input=stdin,
        text=True,
        check=False,
        capture_output=capture,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, list(argv))
    return completed


def detect_compose_cmd() -> tuple[str, ...]:
    """Return the compose command array (docker compose or docker-compose)."""
    if shutil.which("docker") and run_cmd(["docker", "compose", "version"], check=False).returncode == 0:
        return ("docker", "compose")
    if shutil.which("docker-compose"):
        return ("docker-compose",)
    raise SystemExit("docker compose plugin was not found. Install Docker Compose v2 or docker-compose.")


def compose_args(state) -> list[str]:
    """Port of compose_files(): -f base plus the slurm/docker override."""
    from revocompute_ctl import COMPOSE_DOCKER_FILE, COMPOSE_FILE, COMPOSE_SLURM_FILE

    files = ["-f", str(COMPOSE_FILE)]
    if state.use_slurm():
        if COMPOSE_SLURM_FILE.is_file():
            files += ["-f", str(COMPOSE_SLURM_FILE)]
    else:
        if COMPOSE_DOCKER_FILE.is_file():
            files += ["-f", str(COMPOSE_DOCKER_FILE)]
    return files


def resolve_socket_path(path: str) -> str | None:
    """Resolve a unix:// docker endpoint through symlinks to a live socket."""
    if path.startswith("unix://"):
        path = path[len("unix://") :]
    depth = 0
    while os.path.islink(path) and depth < 10:
        target = os.readlink(path)
        if not target:
            break
        path = target if target.startswith("/") else os.path.join(os.path.dirname(path), target)
        depth += 1
    try:
        is_socket = stat.S_ISSOCK(os.stat(path, follow_symlinks=True).st_mode)
    except OSError:
        is_socket = False
    return path if is_socket else None


def detect_docker_gid() -> str | None:
    """Detect the container-visible docker socket group id."""
    if sys.platform == "darwin":
        return "0"
    candidates: list[str] = []
    endpoint = run_cmd(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        check=False,
        capture=True,
    )
    host = (endpoint.stdout or "").strip()
    if host.startswith("unix://"):
        candidates.append(host)
    candidates.append("/var/run/docker.sock")
    for candidate in candidates:
        resolved = resolve_socket_path(candidate)
        if not resolved:
            continue
        try:
            return str(os.stat(resolved, follow_symlinks=True).st_gid)
        except OSError:
            continue
    return None


def ensure_docker_gid(state) -> str:
    """Port of ensure_docker_gid(): no-op for SLURM; detect or fail otherwise."""
    if state.use_slurm():
        return ""
    gid = state.get("DOCKER_GID")
    if not gid:
        gid = detect_docker_gid() or ""
    if not gid:
        print("Unable to auto-detect Docker socket group id; set DOCKER_GID for this command.", file=sys.stderr)
        raise SystemExit(1)
    state.runtime["DOCKER_GID"] = gid
    print(f"Using Docker socket group id {gid}.")
    return gid


def container_fs(
    state,
    script: str,
    mounts: list[tuple[str, str]],
    *,
    stdin_data: str | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a host-filesystem operation inside a throwaway container as the
    runner identity.  Deployment-owned directories (CONFIG_DIR, SERVER_DIR)
    are reachable regardless of the invoking host user — the same pattern as
    the pre-stop sweep, which runs in the worker container for the same
    reason."""
    uid = state.runtime.get("RUNNER_UID") or state.get("RUNNER_UID") or "1000"
    gid = state.runtime.get("RUNNER_GID") or state.get("RUNNER_GID") or "1000"
    image = state.get("SERVER_IMAGE") or "revodesign-revocompute-server"
    argv = ["docker", "run", "--rm", "-i", "--user", f"{uid}:{gid}", "--entrypoint", "sh"]
    for host, target in mounts:
        argv += ["-v", f"{host}:{target}"]
    argv += [image, "-c", script]
    return run_cmd(argv, env=state.exported(), stdin=stdin_data, capture=capture, check=check)


def image_id(state, image: str) -> str:
    """docker image inspect --format '{{.Id}}' → the id, or '' on any failure.

    An empty id means "unknown" — promotion treats unknown as unchanged, which
    is also what keeps the fake-docker test harness (empty inspect output)
    behaviorally identical to the shell script.
    """
    result = run_cmd(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        env=state.exported(),
        check=False,
        capture=True,
    )
    return (result.stdout or "").strip()
