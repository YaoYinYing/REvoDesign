# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""SLURM + Apptainer job runner.

Ephemeral sbatch scripts tie the two together — SLURM allocates resources,
Apptainer isolates the compute binary.  Each ``SlurmJob`` writes a temporary
sbatch script, submits it, and polls ``squeue`` until a terminal state.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from revocompute.config import ComputeConfig
from revocompute.job import Job, JobState

# -- self-contained (no imports from task_runtime — avoids circular deps) -----
CONFIG = ComputeConfig.from_env()

_SQUEUE_STATE_MAP: dict[str, JobState] = {
    # Terminal
    "COMPLETED": JobState.COMPLETED,
    "CD": JobState.COMPLETED,
    "FAILED": JobState.FAILED,
    "F": JobState.FAILED,
    "TIMEOUT": JobState.FAILED,
    "TO": JobState.FAILED,
    "CANCELLED": JobState.CANCELLED,
    "CA": JobState.CANCELLED,
    "NODE_FAIL": JobState.FAILED,
    "NF": JobState.FAILED,
    "PREEMPTED": JobState.FAILED,
    "PR": JobState.FAILED,
    "BOOT_FAIL": JobState.FAILED,
    "BF": JobState.FAILED,
    "DEADLINE": JobState.FAILED,
    "DL": JobState.FAILED,
    "OUT_OF_MEMORY": JobState.FAILED,
    "OOM": JobState.FAILED,
    # Running
    "RUNNING": JobState.RUNNING,
    "R": JobState.RUNNING,
    "COMPLETING": JobState.RUNNING,
    "CG": JobState.RUNNING,
    "CONFIGURING": JobState.RUNNING,
    "CF": JobState.RUNNING,
    # Pending
    "PENDING": JobState.PENDING,
    "PD": JobState.PENDING,
    "REQUEUED": JobState.PENDING,
    "RQ": JobState.PENDING,
    "RESV_DEL_HOLD": JobState.PENDING,
    "RD": JobState.PENDING,
}

_TERMINAL_STATES = {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}
_SBATCH_JOB_ID_RE = re.compile(r"Submitted batch job (\d+)")


class SlurmJob(Job):
    """A compute job submitted via SLURM + Apptainer."""

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

    # -- Job ABC -------------------------------------------------------------

    def submit(self) -> str:
        if self._db is not None and not self._db.slurm_enabled():
            raise RuntimeError(
                "SLURM is disabled — set slurm_enabled=true in admin config"
            )
        script_path = self._build_sbatch_script()
        try:
            result = subprocess.run(
                ["sbatch", str(script_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(f"sbatch failed: {result.stderr.strip()}")

            match = _SBATCH_JOB_ID_RE.search(result.stdout)
            if not match:
                raise RuntimeError(
                    f"Could not parse job ID from sbatch output: {result.stdout!r}"
                )
            self._job_id = match.group(1)
        finally:
            script_path.unlink(missing_ok=True)

        logging.info("SLURM job %s submitted for task %s", self._job_id, self.task_id)
        return self._job_id

    def poll(self) -> JobState:
        if self._job_id is None:
            raise RuntimeError("poll() called before submit()")

        poll_interval = 5.0  # seconds
        # ponytail: generous upper bound — SLURM queue times can be long
        max_poll = (self.runner.max_runtime_seconds or 86400) // 5 + 60
        iterations = 0

        while iterations < max_poll:
            state = self._query_state()
            if state in _TERMINAL_STATES:
                self._maybe_stage_callback(state)
                return state
            time.sleep(poll_interval)
            iterations += 1

        logging.error("SLURM job %s timed out after %d polls", self._job_id, iterations)
        return JobState.FAILED

    def cancel(self) -> None:
        if self._job_id is None:
            return
        try:
            subprocess.run(["scancel", self._job_id], timeout=10, check=True)
            logging.info("SLURM job %s cancelled", self._job_id)
        except subprocess.CalledProcessError as exc:
            logging.warning("scancel %s failed: %s", self._job_id, exc)

    # -- sbatch script generation --------------------------------------------

    def _build_sbatch_script(self) -> Path:
        """Write a temporary sbatch script, return its Path.

        The script is self-contained: it stages input files (with the
        ``.upload`` → original-extension fix), then invokes Apptainer.
        """
        sbatch_args: dict[str, Any] = {}
        if self._db is not None:
            sbatch_args = self._db.slurm_sbatch_args(self.tt.name)

        script = self._render_script(sbatch_args)
        fd, path = tempfile.mkstemp(
            suffix=".sbatch", prefix=f"revo_{self.task_id[:8]}_"
        )
        with os.fdopen(fd, "w") as f:
            f.write(script)
        os.chmod(path, 0o700)
        return Path(path)

    def _render_script(self, sbatch_args: dict[str, Any]) -> str:
        """Render the complete sbatch script as a string."""
        lines = ["#!/bin/bash", "set -euo pipefail"]
        self._render_sbatch_directives(lines, sbatch_args)
        lines.append("")
        self._render_input_staging(lines)
        lines.append("")
        self._render_apptainer_invocation(lines)
        return "\n".join(lines) + "\n"

    def _render_sbatch_directives(
        self, lines: list[str], sbatch_args: dict[str, Any]
    ) -> None:
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
            "slurm_exclusive": "exclusive",
        }
        for field, option in _FIELD_TO_OPTION.items():
            value = sbatch_args.get(field)
            if value is None:
                continue
            if field == "slurm_exclusive":
                if str(value).lower() in ("true", "1", "yes"):
                    lines.append(f"#SBATCH --{option}")
            else:
                lines.append(f"#SBATCH --{option}={value}")

        # Standard directives (always last so they take precedence)
        lines.append(f"#SBATCH --job-name=revo_{self.task_id[:8]}")
        lines.append(
            f"#SBATCH --output={_sh_quote(os.path.join(self.output_dir, f'slurm_{self.task_id[:8]}_%j.out'))}"
        )
        lines.append(
            f"#SBATCH --error={_sh_quote(os.path.join(self.output_dir, f'slurm_{self.task_id[:8]}_%j.err'))}"
        )

    def _render_input_staging(self, lines: list[str]) -> None:
        """Create hardlinks from ``<hash>.upload`` to the original filename.

        Some compute runners validate input file suffixes (``.fasta``,
        ``.pdb``) and will reject ``.upload``.  This makes the original
        extension visible inside the container.
        """
        upload_dir = CONFIG.upload_folder
        lines.append("# -- input staging (restore original filenames) --")
        for fe in self.file_entities:
            original = fe["verified_value"]  # e.g. "input.fasta"
            file_hash = fe["hash"]  # e.g. "abc123"
            src = os.path.join(upload_dir, f"{file_hash}.upload")
            dst = os.path.join(self.output_dir, original)
            lines.append(f"ln -f {_sh_quote(src)} {_sh_quote(dst)}")

    def _render_apptainer_invocation(self, lines: list[str]) -> None:
        """Build the ``apptainer run`` command line."""
        sif_image = getattr(self.runner, "slurm_image", "") or ""
        if not sif_image:
            raise RuntimeError(
                f"Runner {self.tt.name!r} has slurm_image unset — cannot launch Apptainer"
            )

        bind_parts: list[str] = []
        upload_dir = CONFIG.upload_folder

        # Input files: bind restored files read-only
        for fe in self.file_entities:
            original = fe["verified_value"]
            src = os.path.join(self.output_dir, original)
            bind_parts.append(
                f"--bind {_sh_quote(src)}:/workspace/inputs/{_sh_quote(original)}:ro"
            )
        # Upload dir (shared databases, etc.)
        bind_parts.append(f"--bind {_sh_quote(upload_dir)}:/workspace/inputs:ro")
        # Output dir
        bind_parts.append(
            f"--bind {_sh_quote(self.output_dir)}:/workspace/outputs"
        )

        # Extra mounts from runner config
        for m in self.runner.mounts:
            bind_parts.append(
                f"--bind {_sh_quote(m.host_path)}:{_sh_quote(m.container_path)}:{m.mode}"
            )

        # Environment from runner config
        env_parts: list[str] = []
        for key, val in self.runner.env.items():
            env_parts.append(f"export {_sh_quote(key)}={_sh_quote(val)}")
        env_parts.append(f"export TASK_ID={_sh_quote(self.task_id)}")
        env_parts.append(f"export TASK_TYPE={_sh_quote(self.tt.name)}")
        params = {e["name"]: e["verified_value"] for e in self.param_entities}
        if params:
            env_parts.append(f"export TASK_PARAMS={_sh_quote(json.dumps(params))}")

        lines.append("# -- apptainer invocation --")
        for ep in env_parts:
            lines.append(ep)

        # Build apptainer command
        cmd = f"apptainer run --nv {' '.join(bind_parts)} {_sh_quote(sif_image)}"
        if self.file_entities:
            original = self.file_entities[0]["verified_value"]
            cmd += f" -i /workspace/inputs/{_sh_quote(original)}"
        cmd += " -o /workspace/outputs"
        for key, flag in (("iter", "-r"),):
            if key in params:
                cmd += f" {flag} {params[key]}"
        lines.append(cmd)

    # -- squeue / sacct helpers ----------------------------------------------

    def _query_state(self) -> JobState:
        try:
            result = subprocess.run(
                ["squeue", "-j", self._job_id, "-h", "-o", "%T"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logging.warning(
                "squeue query for job %s failed: %s", self._job_id, exc
            )
            return JobState.RUNNING  # assume still running, next poll will retry

        state_raw = result.stdout.strip()
        if not state_raw:
            # Job vanished from squeue — check sacct for terminal state
            return self._query_sacct()
        return _SQUEUE_STATE_MAP.get(state_raw.upper(), JobState.RUNNING)

    def _query_sacct(self) -> JobState:
        """Fallback: query sacct when the job is no longer in squeue."""
        try:
            result = subprocess.run(
                ["sacct", "-j", self._job_id, "-o", "State", "-n", "-P"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            return JobState.FAILED

        lines = [
            l.strip() for l in result.stdout.strip().splitlines() if l.strip()
        ]
        if not lines:
            return JobState.FAILED
        # Take the first non-batch state line
        for line in lines:
            state = line.upper().split()[0] if line else ""
            if state and "BATCH" not in state:
                return _SQUEUE_STATE_MAP.get(state, JobState.FAILED)
        return _SQUEUE_STATE_MAP.get(
            lines[0].upper().split()[0], JobState.FAILED
        )

    def _maybe_stage_callback(self, state: JobState) -> None:
        """Emit the final stage marker if the job completed successfully."""
        if state == JobState.COMPLETED and self.stage_callback and self.tt.stage_markers:
            stages = list(self.tt.stage_markers.items())
            if stages:
                self.stage_callback(stages[-1][0])


def _sh_quote(s: str) -> str:
    """Single-quote a string for safe shell embedding."""
    return "'" + s.replace("'", "'\"'\"'") + "'"
