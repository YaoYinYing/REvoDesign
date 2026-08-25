# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Runner/web image builds."""

from __future__ import annotations

import os
import sys

from revocompute_ctl.compose import compose_args, ensure_docker_gid, run_cmd
from revocompute_ctl.registry import (
    _docker_tag,
    drop_enabled_runner,
    expand_enabled_runners,
    runner_enabled,
    validate_runtime_files,
)


def build_runner_images(state, families, proxy_build_args: list[str], uid: str, gid: str) -> bool:
    expand_enabled_runners(state, families)
    print("Building runner images...")
    succeeded = True
    username = state.get("RUNNER_USERNAME") or "revodesign"
    group = state.get("RUNNER_GROUP") or "revodesign_appgroup"
    for family in families:
        if not runner_enabled(state, family.name):
            continue
        print(f"  → {family.docker_image} ({family.name})")
        argv = [
            "docker",
            "build",
            *proxy_build_args,
            "--build-arg",
            f"RUNNER_UID={uid}",
            "--build-arg",
            f"RUNNER_GID={gid}",
            "--build-arg",
            f"RUNNER_USERNAME={username}",
            "--build-arg",
            f"RUNNER_GROUP={group}",
            "-t",
            _docker_tag(family.docker_image),
            "-f",
            os.path.join(state.server_root(), family.dockerfile),
            state.server_root(),
        ]
        result = run_cmd(argv, env=state.exported(), check=False)
        if result.returncode != 0:
            print(f"  ✗ {family.name} build failed — disabled for this restart.", file=sys.stderr)
            drop_enabled_runner(state, family.name)
            succeeded = False
    return succeeded


def build_web_images(state, compose_cmd: tuple[str, ...], proxy_build_args: list[str], uid: str, gid: str) -> None:
    print("Building web/worker images...")
    username = state.get("RUNNER_USERNAME") or "revodesign"
    group = state.get("RUNNER_GROUP") or "revodesign_appgroup"
    if proxy_build_args:
        server_dockerfile = os.path.join(state.server_root(), "docker", "server", "Dockerfile")
        run_cmd(
            [
                "docker",
                "build",
                *proxy_build_args,
                "--build-arg",
                f"RUNNER_UID={uid}",
                "--build-arg",
                f"RUNNER_GID={gid}",
                "--build-arg",
                f"RUNNER_USERNAME={username}",
                "--build-arg",
                f"RUNNER_GROUP={group}",
                "--build-arg",
                f"PORT={state.get('PORT') or '8080'}",
                "-t",
                state.get("SERVER_IMAGE") or "revodesign-revocompute-server",
                "-f",
                server_dockerfile,
                state.server_root(),
            ],
            env=state.exported(),
        )
    else:
        run_cmd(
            [*compose_cmd, *compose_args(state), "--env-file", state.env_file, "build", "web", "worker"],
            env=state.exported(),
        )


def cmd_build(
    state,
    compose_cmd: tuple[str, ...],
    use_proxy_from_env: bool,
    use_proxy: str,
    *,
    runners_only: bool = False,
) -> None:
    """Build selected runner images, then optionally web/worker."""
    proxy_build_args = _resolve_proxy_args(state, use_proxy_from_env, use_proxy)
    from revocompute_ctl.storage import resolve_runner_identity

    families = validate_runtime_files(state)
    ensure_docker_gid(state)
    uid, gid = resolve_runner_identity(state)
    runners_ready = build_runner_images(state, families, proxy_build_args, uid, gid)
    if runners_only and not runners_ready:
        raise SystemExit(1)
    if not runners_only:
        build_web_images(state, compose_cmd, proxy_build_args, uid, gid)


def _resolve_proxy_args(state, use_proxy_from_env: bool, use_proxy: str) -> list[str]:
    if use_proxy_from_env:
        use_proxy = state.get("REVODESIGN_BUILD_PROXY")
        if not use_proxy:
            print(f"--use-proxy requires REVODESIGN_BUILD_PROXY in {state.env_file}.", file=sys.stderr)
            raise SystemExit(1)
        state.runtime["HTTP_PROXY"] = use_proxy
        state.runtime["HTTPS_PROXY"] = use_proxy
        state.runtime["NO_PROXY"] = state.get("NO_PROXY") or "localhost,127.0.0.1,.local"
    if not use_proxy:
        return []
    print("Using configured proxy for Docker builds (credential redacted).")
    http_proxy = state.runtime.get("HTTP_PROXY") or use_proxy
    https_proxy = state.runtime.get("HTTPS_PROXY") or use_proxy
    no_proxy = state.runtime.get("NO_PROXY") or "localhost,127.0.0.1,.local"
    return [
        "--build-arg",
        f"HTTP_PROXY={http_proxy}",
        "--build-arg",
        f"HTTPS_PROXY={https_proxy}",
        "--build-arg",
        f"NO_PROXY={no_proxy}",
        "--build-arg",
        f"http_proxy={http_proxy}",
        "--build-arg",
        f"https_proxy={https_proxy}",
        "--build-arg",
        f"no_proxy={no_proxy}",
    ]
