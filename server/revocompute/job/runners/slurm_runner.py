# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""SLURM + Apptainer job runner.

Uses ``srun`` for direct stdout/stderr capture — the same living-output
pattern as the Docker runner.  A temporary wrapper script performs input
staging, exports ``APPTAINERENV_*`` environment variables, and invokes
Apptainer.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Any

from revocompute.config import ComputeConfig
from revocompute.job import Job, JobState
from revocompute.job._stages import extract_stage_from_log_line

CONFIG = ComputeConfig.from_env()


class SlurmJob(Job):
    """A compute job submitted via SLURM + Apptainer.

    ``submit()`` launches ``srun`` via ``subprocess.Popen`` and returns
    a synthetic job id.  ``poll()`` waits for the process to exit and
    returns ``COMPLETED`` or ``FAILED`` based on the exit code.
    """

    def __init__(
        self,
        task_id: str,
        tt: Any,
        runner: Any,
        entities: list[dict],
        output_dir: str,
        stage_callback: Any = None,
        manage_db: Any = None,
        username: str = "",
    ):
        super().__init__(task_id, tt, runner, entities, output_dir, stage_callback)
        self._db = manage_db
        self._username = username
        self._process: subprocess.Popen | None = None
        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    # -- Job ABC -------------------------------------------------------------

    def submit(self) -> str:
        if self._db is not None and not self._db.slurm_enabled():
            raise RuntimeError("SLURM is disabled — set slurm_enabled=true in admin config")

        script_path = self._build_wrapper_script()
        os.makedirs(self.output_dir, exist_ok=True)

        cmd = ["srun"] + self._build_srun_args() + ["bash", script_path]
        logging.info("srun command: %s", " ".join(cmd))

        self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self._job_id = f"srun-{self._process.pid}"

        # Background threads for live stdout/stderr capture.  The stdout
        # thread also parses REVODESIGN_STAGE: markers.
        self._stdout_lines, self._stderr_lines = [], []
        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

        logging.info("SLURM job %s (pid %s) started for task %s", self._job_id, self._process.pid, self.task_id)
        return self._job_id

    def poll(self) -> JobState:
        if self._process is None:
            raise RuntimeError("poll() called before submit()")

        max_runtime = self.runner.max_runtime_seconds or 86400
        try:
            self._process.wait(timeout=max_runtime)
        except subprocess.TimeoutExpired:
            logging.error("SLURM job %s timed out after %d s", self._job_id, max_runtime)
            self._process.kill()
            self._process.wait()
            return JobState.FAILED

        if self._stdout_thread:
            self._stdout_thread.join(timeout=10)
        if self._stderr_thread:
            self._stderr_thread.join(timeout=10)

        self._save_output()

        exit_code = self._process.returncode
        if exit_code == 0:
            self._maybe_stage_callback(JobState.COMPLETED)
            return JobState.COMPLETED

        logging.error("SLURM job %s failed with exit code %s", self._job_id, exit_code)
        return JobState.FAILED

    def cancel(self) -> None:
        proc = self._process
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        logging.info("srun process %s terminated for task %s", proc.pid, self.task_id)

    # -- srun arguments ------------------------------------------------------

    def _build_srun_args(self) -> list[str]:
        sbatch_args: dict[str, Any] = {}
        if self._db is not None:
            sbatch_args = self._db.slurm_sbatch_args(self.tt.name)

        _FIELD_TO_OPTION = {
            "slurm_partition": "partition",
            "slurm_cpus_per_task": "cpus-per-task",
            "slurm_gres": "gres",
            "slurm_mem": "mem",
            "slurm_time": "time",
            "slurm_nodes": "nodes",
            "slurm_ntasks": "ntasks",
            "slurm_qos": "qos",
            "slurm_account": "account",
            "slurm_constraint": "constraint",
        }
        opts: list[str] = []
        for field, option in _FIELD_TO_OPTION.items():
            value = sbatch_args.get(field)
            if value is None:
                continue
            opts.append(f"--{option}={value}")

        opts.append(f"--job-name=revocomput_{_sanitize_name(self._username)}_{self.tt.name}_{self.task_id[:8]}")
        return opts

    # -- wrapper script ------------------------------------------------------

    def _build_wrapper_script(self) -> str:
        """Write the wrapper script into *output_dir* so the host-side
        ``srun`` process can read it.  Returns the path as a string."""
        script = self._render_wrapper()
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, f"_slurm_wrapper_{self.task_id[:8]}.sh")
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o700)
        return path

    def _render_wrapper(self) -> str:
        lines = ["#!/bin/bash", "set -euo pipefail", ""]
        self._render_input_staging(lines)
        lines.append("")
        self._render_apptainer_invocation(lines)
        return "\n".join(lines) + "\n"

    def _render_input_staging(self, lines: list[str]) -> None:
        upload_dir = CONFIG.upload_folder
        lines.append("# -- input staging --")
        for fe in self.file_entities:
            original = fe["verified_value"]
            src = os.path.join(upload_dir, f"{fe['hash']}.upload")
            dst = os.path.join(self.output_dir, original)
            lines.append(f"ln -f {_sh_quote(src)} {_sh_quote(dst)}")

    def _render_apptainer_invocation(self, lines: list[str]) -> None:
        sif_image = getattr(self.runner, "slurm_image", "") or ""
        if not sif_image:
            raise RuntimeError(f"Runner {self.tt.name!r} has slurm_image unset")

        bind_parts: list[str] = []
        for fe in self.file_entities:
            original = fe["verified_value"]
            src = os.path.join(self.output_dir, original)
            bind_parts.append(f"--bind {_sh_quote(src)}:/workspace/inputs/{_sh_quote(original)}:ro")
        bind_parts.append(f"--bind {_sh_quote(self.output_dir)}:/workspace/outputs")
        for m in self.runner.mounts:
            bind_parts.append(f"--bind {_sh_quote(m.host_path)}:{_sh_quote(m.container_path)}:{m.mode}")

        lines.append("# -- apptainer --")
        # APPTAINERENV_ prefixed vars are forwarded into the container.
        lines.append(f"export APPTAINERENV_TASK_ID={_sh_quote(self.task_id)}")
        lines.append(f"export APPTAINERENV_TASK_TYPE={_sh_quote(self.tt.name)}")
        for key, val in self.runner.env.items():
            lines.append(f"export APPTAINERENV_{key}={_sh_quote(val)}")

        params = {e["name"]: e["verified_value"] for e in self.param_entities}
        cmd = f"apptainer run --nv {' '.join(bind_parts)} {_sh_quote(sif_image)}"
        if self.file_entities:
            original = self.file_entities[0]["verified_value"]
            cmd += f" -i /workspace/inputs/{_sh_quote(original)}"
        cmd += " -o /workspace/outputs"
        for key, flag in (("iter", "-r"),):
            if key in params:
                cmd += f" {flag} {params[key]}"
        lines.append(cmd)

    # -- output capture ------------------------------------------------------

    def _read_stdout(self) -> None:
        stream = self._process.stdout
        last_stage: str | None = None
        markers = self.tt.stage_markers
        for line in iter(stream.readline, ""):
            self._stdout_lines.append(line)
            if markers and self.stage_callback:
                stage = extract_stage_from_log_line(line, markers)
                if stage and stage != last_stage:
                    last_stage = stage
                    try:
                        self.stage_callback(stage)
                    except Exception:
                        pass
        stream.close()

    def _read_stderr(self) -> None:
        stream = self._process.stderr
        for line in iter(stream.readline, ""):
            self._stderr_lines.append(line)
        stream.close()

    def _save_output(self) -> None:
        out_path = os.path.join(self.output_dir, f"slurm_{self._job_id}.out")
        err_path = os.path.join(self.output_dir, f"slurm_{self._job_id}.err")
        try:
            with open(out_path, "w") as f:
                f.writelines(self._stdout_lines)
            with open(err_path, "w") as f:
                f.writelines(self._stderr_lines)
        except OSError as exc:
            logging.warning("Could not save SLURM output for %s: %s", self._job_id, exc)

    def _maybe_stage_callback(self, state: JobState) -> None:
        if state == JobState.COMPLETED and self.stage_callback and self.tt.stage_markers:
            stages = list(self.tt.stage_markers.items())
            if stages:
                self.stage_callback(stages[-1][0])


def _sanitize_name(s: str) -> str:
    """SLURM job names: alphanumeric, underscore, hyphen only."""
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in (s or "unknown")) or "unknown"


def _sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"
