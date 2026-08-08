# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""SLURM + Apptainer job runner.

Uses ``srun`` for direct stdout/stderr capture — the same living-output
pattern as the Docker runner.  A temporary wrapper script performs input
staging, sets environment variables, and invokes Apptainer.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from revocompute.config import ComputeConfig
from revocompute.job import Job, JobState

# -- self-contained (no imports from task_runtime — avoids circular deps) -----
CONFIG = ComputeConfig.from_env()

_SRUN_JOB_ID_RE = re.compile(r"job\s+(\d+)\s")


class SlurmJob(Job):
    """A compute job submitted via SLURM + Apptainer.

    ``submit()`` launches ``srun`` as a subprocess and returns the
    SLURM job id.  ``poll()`` waits for ``srun`` to exit, saves the
    captured stdout/stderr into the output directory, and returns
    ``COMPLETED`` or ``FAILED`` based on the exit code.
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
    ):
        super().__init__(task_id, tt, runner, entities, output_dir, stage_callback)
        self._db = manage_db
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

        srun_args = self._build_srun_args()
        cmd = ["srun"] + srun_args + ["bash", str(script_path)]
        logging.info("srun command: %s", " ".join(cmd))

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Read stdout / stderr line-by-line in background threads so we
        # capture output live while the process runs.
        self._stdout_lines = []
        self._stderr_lines = []
        self._stdout_thread = threading.Thread(
            target=self._read_lines, args=(self._process.stdout, self._stdout_lines), daemon=True
        )
        self._stderr_thread = threading.Thread(
            target=self._read_lines, args=(self._process.stderr, self._stderr_lines), daemon=True
        )
        self._stdout_thread.start()
        self._stderr_thread.start()

        # Parse the SLURM job id from srun's stderr.  srun prints a line like
        #   srun: job 12345 queued and waiting for resources
        # when the allocation is granted.
        self._job_id = self._parse_job_id_from_stderr(timeout=120)
        if self._job_id is None:
            # Fall back to a synthetic id based on the process pid so
            # cancel() can still send a signal.
            self._job_id = f"srun-{self._process.pid}"
            logging.warning("Could not parse SLURM job id from srun stderr; using %s", self._job_id)

        logging.info("SLURM job %s (srun pid %s) started for task %s", self._job_id, self._process.pid, self.task_id)
        script_path.unlink(missing_ok=True)
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

        # Wait for reader threads to drain
        if self._stdout_thread:
            self._stdout_thread.join(timeout=10)
        if self._stderr_thread:
            self._stderr_thread.join(timeout=10)

        # Save captured output into the output directory
        self._save_output()

        exit_code = self._process.returncode
        if exit_code == 0:
            self._maybe_stage_callback(JobState.COMPLETED)
            return JobState.COMPLETED

        logging.error("SLURM job %s failed with exit code %s", self._job_id, exit_code)
        return JobState.FAILED

    def cancel(self) -> None:
        proc = self._process
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            logging.info("srun process %s terminated for task %s", proc.pid, self.task_id)

        # Also try scancel in case the allocation survived
        if self._job_id and not self._job_id.startswith("srun-"):
            try:
                subprocess.run(["scancel", self._job_id], timeout=10, check=True)
                logging.info("SLURM job %s cancelled via scancel", self._job_id)
            except subprocess.CalledProcessError as exc:
                logging.warning("scancel %s failed: %s", self._job_id, exc)

    # -- srun arguments ------------------------------------------------------

    def _build_srun_args(self) -> list[str]:
        """Convert per-task-type SLURM config to ``srun`` CLI flags."""
        sbatch_args: dict[str, Any] = {}
        if self._db is not None:
            sbatch_args = self._db.slurm_sbatch_args(self.tt.name)

        opts: list[str] = []
        _FIELD_TO_OPTION: dict[str, str] = {
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
        for field, option in _FIELD_TO_OPTION.items():
            value = sbatch_args.get(field)
            if value is None:
                continue
            if field == "slurm_exclusive":
                if str(value).lower() in ("true", "1", "yes"):
                    opts.append(f"--{option}")
            else:
                opts.append(f"--{option}={value}")

        # Job name
        opts.append(f"--job-name=revo_{self.task_id[:8]}")
        return opts

    # -- wrapper script ------------------------------------------------------

    def _build_wrapper_script(self) -> Path:
        """Write the temporary wrapper script, return its Path."""
        script = self._render_wrapper()
        fd, path = tempfile.mkstemp(suffix=".sh", prefix=f"revo_{self.task_id[:8]}_")
        with os.fdopen(fd, "w") as f:
            f.write(script)
        os.chmod(path, 0o700)
        return Path(path)

    def _render_wrapper(self) -> str:
        """Render the srun wrapper script — staging + env + apptainer."""
        lines = ["#!/bin/bash", "set -euo pipefail"]
        lines.append("")
        self._render_input_staging(lines)
        lines.append("")
        self._render_env(lines)
        lines.append("")
        self._render_apptainer_invocation(lines)
        return "\n".join(lines) + "\n"

    def _render_input_staging(self, lines: list[str]) -> None:
        """Create hardlinks from ``<hash>.upload`` to the original filename."""
        upload_dir = CONFIG.upload_folder
        lines.append("# -- input staging --")
        for fe in self.file_entities:
            original = fe["verified_value"]
            file_hash = fe["hash"]
            src = os.path.join(upload_dir, f"{file_hash}.upload")
            dst = os.path.join(self.output_dir, original)
            lines.append(f"ln -f {_sh_quote(src)} {_sh_quote(dst)}")

    def _render_env(self, lines: list[str]) -> None:
        """Export environment variables from runner config."""
        lines.append("# -- environment --")
        for key, val in self.runner.env.items():
            lines.append(f"export {_sh_quote(key)}={_sh_quote(val)}")
        lines.append(f"export TASK_ID={_sh_quote(self.task_id)}")
        lines.append(f"export TASK_TYPE={_sh_quote(self.tt.name)}")
        params = {e["name"]: e["verified_value"] for e in self.param_entities}
        if params:
            lines.append(f"export TASK_PARAMS={_sh_quote(json.dumps(params))}")

    def _render_apptainer_invocation(self, lines: list[str]) -> None:
        """Build the ``apptainer run`` command line."""
        sif_image = getattr(self.runner, "slurm_image", "") or ""
        if not sif_image:
            raise RuntimeError(f"Runner {self.tt.name!r} has slurm_image unset — cannot launch Apptainer")

        bind_parts: list[str] = []
        # Input files
        for fe in self.file_entities:
            original = fe["verified_value"]
            src = os.path.join(self.output_dir, original)
            bind_parts.append(f"--bind {_sh_quote(src)}:/workspace/inputs/{_sh_quote(original)}:ro")
        # Output dir
        bind_parts.append(f"--bind {_sh_quote(self.output_dir)}:/workspace/outputs")
        # Runner config mounts (databases, etc.)
        for m in self.runner.mounts:
            bind_parts.append(f"--bind {_sh_quote(m.host_path)}:{_sh_quote(m.container_path)}:{m.mode}")

        lines.append("# -- apptainer --")

        # Re-export env via --env so Apptainer picks them up (srun's
        # environment may be stripped by SLURM).
        env_flag_parts: list[str] = []
        for key, val in self.runner.env.items():
            env_flag_parts.append(f"{key}={val}")
        if env_flag_parts:
            lines.append("export APPTAINERENV_TASK_ID={}".format(_sh_quote(self.task_id)))
            lines.append("export APPTAINERENV_TASK_TYPE={}".format(_sh_quote(self.tt.name)))
            for key, val in self.runner.env.items():
                lines.append(f"export APPTAINERENV_{key}={_sh_quote(val)}")

        cmd = f"apptainer run --nv {' '.join(bind_parts)} {_sh_quote(sif_image)}"
        if self.file_entities:
            original = self.file_entities[0]["verified_value"]
            cmd += f" -i /workspace/inputs/{_sh_quote(original)}"
        cmd += " -o /workspace/outputs"
        params = {e["name"]: e["verified_value"] for e in self.param_entities}
        for key, flag in (("iter", "-r"),):
            if key in params:
                cmd += f" {flag} {params[key]}"
        lines.append(cmd)

    # -- output capture ------------------------------------------------------

    @staticmethod
    def _read_lines(stream, sink: list[str]) -> None:
        """Read lines from *stream* into *sink* (runs in a background thread)."""
        for line in iter(stream.readline, ""):
            sink.append(line)
        stream.close()

    def _parse_job_id_from_stderr(self, timeout: float) -> str | None:
        """Spin until we see a SLURM job id in srun's stderr, or *timeout*."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for line in self._stderr_lines:
                m = _SRUN_JOB_ID_RE.search(line)
                if m:
                    return m.group(1)
            if self._process is not None and self._process.poll() is not None:
                break
            time.sleep(0.5)
        return None

    def _save_output(self) -> None:
        """Write captured stdout / stderr to the output directory."""
        out_path = os.path.join(self.output_dir, f"slurm_{self._job_id}.out")
        err_path = os.path.join(self.output_dir, f"slurm_{self._job_id}.err")
        try:
            with open(out_path, "w") as f:
                f.writelines(self._stdout_lines)
            with open(err_path, "w") as f:
                f.writelines(self._stderr_lines)
        except OSError as exc:
            logging.warning("Could not save SLURM output for %s: %s", self._job_id, exc)

    # -- stage callback ------------------------------------------------------

    def _maybe_stage_callback(self, state: JobState) -> None:
        """Emit the final stage marker if the job completed successfully."""
        if state == JobState.COMPLETED and self.stage_callback and self.tt.stage_markers:
            stages = list(self.tt.stage_markers.items())
            if stages:
                self.stage_callback(stages[-1][0])


def _sh_quote(s: str) -> str:
    """Single-quote a string for safe shell embedding."""
    return "'" + s.replace("'", "'\"'\"'") + "'"
