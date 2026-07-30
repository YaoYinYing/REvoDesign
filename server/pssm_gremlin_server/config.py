# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Side-effect-free configuration for the GREMLIN web and worker processes."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass


def env_bool(var: str, default: bool) -> bool:
    raw = os.environ.get(var)
    if raw is None or raw == "":
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {var} must be a boolean value " "(one of: true/false/1/0/yes/no/on/off).")


def env_str(var: str, default: str) -> str:
    value = os.environ.get(var)
    return value if value else default


def env_int(var: str, default: int) -> int:
    raw = os.environ.get(var, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {var} must be an integer, got {raw!r}") from exc


def env_float(var: str, default: float) -> float:
    raw = os.environ.get(var, "")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {var} must be a finite number, got {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"Environment variable {var} must be a finite number, got {raw!r}")
    return value


def env_path(var: str, default: str) -> str:
    value = os.environ.get(var)
    if value:
        return os.path.abspath(os.path.expanduser(value))
    return os.path.abspath(default)


def env_required_path(var: str) -> str:
    return os.path.abspath(os.path.expanduser(env_required(var)))


def env_required(var: str) -> str:
    value = os.environ.get(var, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {var} is not set")
    return value


def env_csv(var: str, default: str) -> list[str]:
    source = os.environ.get(var) or default
    return [value for raw in source.split(",") if (value := raw.strip())]


def format_runner_identity(user_value: str, group_value: str) -> str:
    user = user_value.strip()
    group = group_value.strip()
    if not user or not group:
        raise RuntimeError("Runner user and group must both be provided.")
    if user in {"0", "root"} or group in {"0", "root"}:
        raise ValueError("GREMLIN runner cannot run as root. Provide a non-root user and group.")
    return f"{user}:{group}"


def resolve_docker_user() -> str:
    username = os.environ.get("RUNNER_USERNAME")
    group = os.environ.get("RUNNER_GROUP")
    if username or group:
        if not username or not group:
            raise RuntimeError("RUNNER_USERNAME and RUNNER_GROUP must be set together.")
        return format_runner_identity(username, group)

    env_uid = os.environ.get("RUNNER_UID")
    env_gid = os.environ.get("RUNNER_GID")
    if env_uid or env_gid:
        if not env_uid or not env_gid:
            raise RuntimeError("RUNNER_UID and RUNNER_GID must both be defined.")
        return format_runner_identity(env_uid, env_gid)

    env_user = os.environ.get("RUNNER_USER")
    if env_user:
        if ":" not in env_user:
            raise RuntimeError("RUNNER_USER must be in the form '<user>:<group>'.")
        user_part, group_part = env_user.split(":", 1)
        return format_runner_identity(user_part, group_part)

    raise RuntimeError(
        "Runner user configuration missing. Set RUNNER_UID/RUNNER_GID or RUNNER_USERNAME/RUNNER_GROUP "
        "to a dedicated non-root account."
    )


def ensure_directories(*paths: str) -> None:
    for path in paths:
        os.makedirs(path, exist_ok=True)


@dataclass(frozen=True, slots=True)
class GremlinConfig:
    """Centralized configuration for GREMLIN paths and runtime settings."""

    server_dir: str
    upload_folder: str
    results_folder: str
    db_path: str
    docker_image: str
    docker_user: str
    uniref30_db: str
    uniref90_db: str
    nproc: int
    maxmem: int
    port: int

    @classmethod
    def from_env(cls) -> GremlinConfig:
        server_dir = env_required_path("SERVER_DIR")
        return cls(
            server_dir=server_dir,
            upload_folder=os.path.join(server_dir, "upload"),
            results_folder=os.path.join(server_dir, "results"),
            db_path=env_path("DB_PATH", os.path.join(server_dir, "pssm_gremlin.sqlite3")),
            docker_image=os.environ.get("RUNNER_IMAGE", "revodesign-pssm-gremlin"),
            docker_user=resolve_docker_user(),
            uniref30_db=env_required_path("DB_UNIREF30"),
            uniref90_db=env_required_path("DB_UNIREF90"),
            nproc=env_int("NPROC", 16),
            maxmem=env_int("MAXMEM", 64),
            port=env_int("PORT", 8080),
        )
