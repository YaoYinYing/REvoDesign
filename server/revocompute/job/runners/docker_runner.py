# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Docker container job runner.

Implements the Job ABC for Docker containers — submit, poll logs with
stage parsing, cancel, and teardown.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

from revocompute.config import ComputeConfig
from revocompute.job import Job, JobState
from revocompute.job._stages import extract_stage_from_log_line
from revocompute.resource_policy import ResolvedResources, resolve_resources

import docker

CONFIG = ComputeConfig.from_env()


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
        manage_db: Any = None,
        resource_policy: ResolvedResources | None = None,
    ):
        super().__init__(task_id, tt, runner, entities, output_dir, stage_callback)
        self._docker_client_arg = docker_client  # lazy — connect in submit()
        self._client: Any = None
        self._container: Any = None
        self._db = manage_db
        self._resolved_resource_policy = resource_policy

    def _resolve_resources(self) -> ResolvedResources:
        if self._resolved_resource_policy is not None:
            return self._resolved_resource_policy
        if self._db is not None and hasattr(self._db, "resolve_task_resources"):
            resources = self._db.resolve_task_resources(
                self.tt.name,
                requires_gpu=self.tt.gpus,
                default_timeout_seconds=self.runner.max_runtime_seconds,
            )
        else:
            resources = resolve_resources(
                lambda _field: None,
                lambda _field: None,
                requires_gpu=self.tt.gpus,
                allowed_queues=(),
                default_timeout_seconds=self.runner.max_runtime_seconds,
            )
        self._resolved_resource_policy = resources
        return resources

    # -- Job ABC -------------------------------------------------------------

    def _ensure_client(self) -> None:
        """Lazy-init the Docker client — avoids connecting at import time."""
        if self._client is None:
            self._client = self._docker_client_arg or docker.from_env()

    def submit(self) -> str:
        self._ensure_client()
        resources = self._resolve_resources()
        volumes = self._build_volumes()
        container_env = self._build_env()
        allocated_cpus = str(resources.cpus)
        container_env.update(
            {
                "NPROC": allocated_cpus,
                "GREMLIN_CALC_CPU_NUM": allocated_cpus,
                "OMP_NUM_THREADS": allocated_cpus,
                "MKL_NUM_THREADS": allocated_cpus,
                "OPENBLAS_NUM_THREADS": allocated_cpus,
                "NUMEXPR_NUM_THREADS": allocated_cpus,
                "TF_NUM_INTRAOP_THREADS": allocated_cpus,
                "TF_NUM_INTEROP_THREADS": allocated_cpus,
            }
        )
        command_args = self._build_command_args()

        self._container = self._client.containers.run(
            image=self.tt.runtime.docker_image,
            entrypoint=list(self.tt.runtime.entrypoint),
            command=command_args,
            remove=False,
            detach=True,
            volumes=volumes,
            environment=container_env,
            device_requests=([docker.types.DeviceRequest(count=1, capabilities=[["gpu"]])] if self.tt.gpus else None),
            nano_cpus=resources.cpus * 1_000_000_000,
            mem_limit=resources.memory.lower(),
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
        timed_out = threading.Event()

        def _enforce_timeout() -> None:
            timed_out.set()
            logging.error(
                "Docker job %s exceeded its %d second runtime limit",
                self.task_id,
                self._resolve_resources().max_runtime_seconds,
            )
            try:
                self._container.kill()
            except Exception:
                logging.exception("Failed to kill timed-out Docker job %s", self.task_id)

        timeout_timer = threading.Timer(
            self._resolve_resources().max_runtime_seconds,
            _enforce_timeout,
        )
        timeout_timer.daemon = True
        timeout_timer.start()
        try:
            for line in self._container.logs(stream=True):
                decoded = line.strip().decode("utf-8", errors="replace")
                if decoded:
                    stage = extract_stage_from_log_line(decoded, self.tt.stage_markers)
                    if stage and stage != last_stage:
                        last_stage = stage
                        if self.stage_callback:
                            try:
                                self.stage_callback(stage)
                            except Exception:
                                pass  # stage callback must not crash the job
                    stderr_lines.append(decoded)
                    if len(stderr_lines) > 200:
                        stderr_lines.pop(0)
                    logging.info(decoded)

            wait_result = self._container.wait()
            status_code = wait_result.get("StatusCode", 1)
            if timed_out.is_set():
                return JobState.FAILED
            if status_code != 0:
                raise docker.errors.ContainerError(
                    container=self._container,
                    exit_status=status_code,
                    command=list(self.tt.runtime.entrypoint),
                    image=self.tt.runtime.docker_image,
                    stderr="\n".join(stderr_lines[-200:]),
                )
            return JobState.COMPLETED
        finally:
            timeout_timer.cancel()
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
                raise docker.errors.DockerException(f"Mount source '{host}' for '{m.container_path}' does not exist")
            volumes[host] = {"bind": m.container_path, "mode": m.mode}

        os.makedirs(self.output_dir, exist_ok=True)
        if self.file_entities:
            volumes[os.path.abspath(self.input_snapshot_root)] = {
                "bind": f"{self.virtual_workspace_root}/inputs",
                "mode": "ro",
            }
        volumes[os.path.abspath(self.output_dir)] = {
            "bind": f"{self.virtual_workspace_root}/outputs",
            "mode": "rw",
        }
        return volumes

    def _build_env(self) -> dict[str, str]:
        params = {e["name"]: e["verified_value"] for e in self.param_entities}
        container_env: dict[str, str] = dict(self.runner.env)
        container_env["TASK_ID"] = self.task_id
        container_env["TASK_TYPE"] = self.tt.name
        container_env["TASK_PARAMS"] = json.dumps(params, separators=(",", ":"), sort_keys=True)
        container_env["TASK_INPUTS"] = json.dumps(
            [
                {
                    "name": entity["name"],
                    "path": entity["mounted"],
                    "relative_path": entity["relative_path"],
                }
                for entity in self.file_entities
            ],
            separators=(",", ":"),
            sort_keys=True,
        )
        return container_env

    def _build_command_args(self) -> list[str]:
        command_args: list[str] = list(self.tt.runner_args)
        if self.file_entities:
            command_args.extend(["-i", self.file_entities[0]["mounted"]])
        command_args.extend(["-o", f"{self.virtual_workspace_root}/outputs"])
        return command_args

    def _teardown(self) -> None:
        if self._container is not None:
            try:
                self._container.remove(force=True)
            except docker.errors.DockerException:
                pass
            self._container = None
