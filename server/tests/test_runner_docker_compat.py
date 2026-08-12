# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
RUNNER_DOCKERFILE = REPO_DIR / "server" / "docker" / "runners" / "pssm_gremlin" / "Dockerfile"
RUNNER_CONTEXT = REPO_DIR / "server"
DOCKER_BUILD_TIMEOUT = 900
DOCKER_RUN_TIMEOUT = 120
DOCKER_CLEANUP_TIMEOUT = 60


def _runner_identity() -> tuple[str, str]:
    uid = str(getattr(os, "getuid", lambda: 0)())
    gid = str(getattr(os, "getgid", lambda: 0)())
    if uid == "0" or gid == "0":
        return "1000", "1000"
    return uid, gid


@pytest.fixture(scope="session")
def runner_compat_image() -> str:
    uid, gid = _runner_identity()
    tag = f"revodesign-gremlin-python36-test:{uuid.uuid4().hex[:12]}"
    try:
        try:
            subprocess.run(
                [
                    "docker",
                    "build",
                    "--tag",
                    tag,
                    "--file",
                    str(RUNNER_DOCKERFILE),
                    "--build-arg",
                    f"RUNNER_UID={uid}",
                    "--build-arg",
                    f"RUNNER_GID={gid}",
                    "--build-arg",
                    "RUNNER_USERNAME=revodesign",
                    "--build-arg",
                    "RUNNER_GROUP=revodesign_appgroup",
                    str(RUNNER_CONTEXT),
                ],
                check=True,
                timeout=DOCKER_BUILD_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(f"Docker runner image build exceeded {DOCKER_BUILD_TIMEOUT} seconds")
        yield tag
    finally:
        try:
            subprocess.run(
                ["docker", "image", "rm", "--force", tag],
                check=False,
                timeout=DOCKER_CLEANUP_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(f"Docker runner image cleanup exceeded {DOCKER_CLEANUP_TIMEOUT} seconds")


def test_runner_scripts_support_configured_python(runner_compat_image: str) -> None:
    compatibility_check = """
import compileall
import sys

assert sys.version_info[:2] == (3, 6), sys.version
assert compileall.compile_dir('/app/revocompute/scripts', quiet=1)
sys.path.insert(0, '/app/revocompute/scripts')
from gremlin_labels import validate_position_label
assert validate_position_label('A_1', 'AC') == 'A_1'
"""
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "/opt/conda/envs/GREMLIN/bin/python",
                runner_compat_image,
                "-c",
                compatibility_check,
            ],
            check=True,
            timeout=DOCKER_RUN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"Docker runner compatibility check exceeded {DOCKER_RUN_TIMEOUT} seconds")
