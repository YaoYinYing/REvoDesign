# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Docker container job runner.

Extracted from ``task_runtime._run_in_docker()`` — same lifecycle,
same stage parsing, same tmpfs mounts.  No behaviour change.
"""

from __future__ import annotations

import json
import logging
import os
import signal
from typing import Any

import docker
from revocompute.config import ComputeConfig
from revocompute.job import Job, JobState

# -- self-contained (no imports from task_runtime — avoids circular deps) -----
CONFIG = ComputeConfig.from_env()
_RUNNER_STAGE_PREFIX = "REVODESIGN_STAGE:"


def _extract_stage_from_log_line(line: str, stage_markers: dict[str, str]) -> str | None:
    """Extract a stage marker from a runner log line."""
    marker_pos = line.find(_RUNNER_STAGE_PREFIX)
    if marker_pos < 0:
        return None
    raw_marker = line[marker_pos + len(_RUNNER_STAGE_PREFIX):].strip().lower()  # noqa: E203
    if not raw_marker:
        return None
    token = raw_marker.split()[0]
    if token in stage_markers:
        return token
    return None


class DockerJob(Job):
    """Run a compute task inside a Docker container."""

    def __init__(
        self,
        task_id: str,
        tt: Any,
        runner: Any,
        entities: list[dict],
        output_dir: str,
        stage_callback: Any = None,
        docker_client: Any = None,
    ):
        super().__init__(task_id, tt, runner, entities, output_dir, stage_callback)
        self._docker_client_arg = docker_client  # lazy — connect in submit()
        self._client: Any = None
        self._container: Any = None
        self._link_path: str | None = None

    # -- Job ABC -------------------------------------------------------------

    def _ensure_client(self) -> None:
        """Lazy-init the Docker client — avoids connecting at import time."""
        if self._client is None:
            self._client = self._docker_client_arg or docker.from_env()

    def submit(self) -> str:
        self._ensure_client()
        volumes = self._build_volumes()
        container_env = self._build_env()
        command_args = self._build_command_args()

        self._container = self._client.containers.run(
            image=self.tt.docker_image,
            entrypoint=self.tt.command,
            command=command_args,
            remove=False,
            detach=True,
            volumes=volumes,
            environment=container_env,
            device_requests=(
                [docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])]
                if self.tt.gpus
                else None
            ),
            user=CONFIG.docker_user,
            stdout=True,
            stderr=True,
        )
        self._job_id = self._container.id
        return self._job_id

    def poll(self) -> JobState:
        if self._container is None:
            raise RuntimeError("poll() called before submit()")

        last_stage: str | None = None
        stderr_lines: list[str] = []
        try:
            try:
                signal.signal(signal.SIGINT, lambda _sig, _frame: self._container.kill())
            except ValueError:
                pass  # not in main thread — graceful degrade

            for line in self._container.logs(stream=True):
                decoded = line.strip().decode("utf-8", errors="replace")
                if decoded:
                    stage = _extract_stage_from_log_line(decoded, self.tt.stage_markers)
                    if stage and stage != last_stage:
                        last_stage = stage
                        if self.stage_callback:
                            self.stage_callback(stage)
                    stderr_lines.append(decoded)
                    logging.info(decoded)

            wait_result = self._container.wait()
            status_code = wait_result.get("StatusCode", 1)
            if status_code != 0:
                raise docker.errors.ContainerError(
                    container=self._container,
                    exit_status=status_code,
                    command=self.tt.command,
                    image=self.tt.docker_image,
                    stderr="\n".join(stderr_lines[-200:]),
                )
            return JobState.COMPLETED
        finally:
            self._teardown()

    def cancel(self) -> None:
        if self._container is not None:
            try:
                self._container.kill()
            except docker.errors.DockerException:
                pass
            self._teardown()

    # -- internal ------------------------------------------------------------

    def _build_volumes(self) -> dict[str, dict]:
        volumes: dict[str, dict] = {}
        for m in self.runner.mounts:
            host = os.path.expanduser(m.host_path)
            if not os.path.exists(host):
                raise docker.errors.DockerException(
                    f"Mount source '{host}' for '{m.container_path}' does not exist"
                )
            volumes[host] = {"bind": m.container_path, "mode": m.mode}

        os.makedirs(self.output_dir, exist_ok=True)
        if self.file_entities:
            fe = self.file_entities[0]
            upload_dir = CONFIG.upload_folder
            # ponytail: hardlink <original>.fasta -> <md5sum>.fasta so run.sh
            # sees the original filename.
            original_name = fe["verified_value"]
            hash_name = f"{fe['hash']}.upload"
            link_path = os.path.join(upload_dir, original_name)
            if not os.path.lexists(link_path):
                os.link(os.path.join(upload_dir, hash_name), link_path)
            self._link_path = link_path
            volumes[os.path.abspath(upload_dir)] = {"bind": "/workspace/inputs", "mode": "ro"}
        volumes[os.path.abspath(self.output_dir)] = {"bind": "/workspace/outputs", "mode": "rw"}
        return volumes

    def _build_env(self) -> dict[str, str]:
        params = {e["name"]: e["verified_value"] for e in self.param_entities}
        container_env: dict[str, str] = dict(self.runner.env)
        container_env["TASK_ID"] = self.task_id
        container_env["TASK_TYPE"] = self.tt.name
        if params:
            container_env["TASK_PARAMS"] = json.dumps(params)
        return container_env

    def _build_command_args(self) -> list[str]:
        params = {e["name"]: e["verified_value"] for e in self.param_entities}
        command_args: list[str] = []
        if self.file_entities:
            command_args.extend(["-i", self.file_entities[0]["mounted"]])
        command_args.extend(["-o", "/workspace/outputs"])
        for key, flag in (("iter", "-r"),):
            if key in params:
                command_args.extend([flag, str(params[key])])
        return command_args

    def _teardown(self) -> None:
        if self._container is not None:
            try:
                self._container.remove(force=True)
            except docker.errors.DockerException:
                pass
            self._container = None
        if self._link_path and os.path.lexists(self._link_path):
            try:
                os.unlink(self._link_path)
            except OSError:
                pass
