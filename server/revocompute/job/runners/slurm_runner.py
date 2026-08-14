# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""SLURM + Apptainer job runner.

Uses ``srun`` for direct stdout/stderr capture — the same living-output
pattern as the Docker runner. A temporary wrapper script verifies the input
snapshot, exports ``APPTAINERENV_*`` environment variables, and invokes
Apptainer.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
from typing import Any

from revocompute.job import Job, JobState
from revocompute.job._stages import extract_stage_from_log_line
from revocompute.resource_policy import ResolvedResources, resolve_resources

_SLURM_JOB_ID_RE = re.compile(r"srun:\s+[Jj]ob\s+(\d+)")


class SlurmJob(Job):
    """A compute job submitted via SLURM + Apptainer.

    ``submit()`` launches ``srun`` via ``subprocess.Popen`` and returns
    the real SLURM job id (captured from srun's stderr banner), falling
    back to a pid-based id if the banner never arrives.  ``poll()`` waits
    for the process to exit and returns ``COMPLETED`` or ``FAILED`` based
    on the exit code.
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
        resource_policy: ResolvedResources | None = None,
    ):
        super().__init__(task_id, tt, runner, entities, output_dir, stage_callback)
        self._db = manage_db
        self._username = username
        self._process: subprocess.Popen | None = None
        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._wrapper_script_path: str | None = None
        self._slurm_job_id: str | None = None
        self._job_id_event = threading.Event()
        self._resolved_resource_policy = resource_policy

    def reconnect(self, slurm_job_id: str) -> bool | None:
        """Check whether a SLURM job is still alive after a server restart.

        We cannot re-attach the srun subprocess, but we can query sacct.
        Returns ``True`` when the job is still active, ``False`` when sacct
        says it is no longer active, and ``None`` when the state cannot be
        determined (sacct missing, query failed, or timed out).  Callers must
        treat ``None`` as unknown — not as failure — because the job may
        still be running on the cluster.
        """
        self._slurm_job_id = slurm_job_id
        self._job_id_event.set()
        sacct = shutil.which("sacct")
        if not sacct:
            return None
        try:
            result = subprocess.run(
                [sacct, "-j", slurm_job_id, "--noheader", "-o", "State", "-P"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return None
            state = (result.stdout or "").strip().split("\n")[0].strip()
            return state in ("RUNNING", "PENDING", "CONFIGURING")
        except Exception:
            return None

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

        # srun prints "srun: job NNNN queued and waiting for resources" on
        # stderr right after submitting — grab the real job id so scancel
        # works.  Fall back to the pid-based id if the banner never arrives.
        self._job_id_event.wait(timeout=5.0)
        if self._slurm_job_id:
            self._job_id = self._slurm_job_id

        logging.info("SLURM job %s (pid %s) started for task %s", self._job_id, self._process.pid, self.task_id)
        return self._job_id

    def poll(self) -> JobState:
        if self._process is None:
            raise RuntimeError("poll() called before submit()")

        max_runtime = self._resolve_resources().max_runtime_seconds
        try:
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
                if not self._has_result_artifact():
                    logging.error(
                        "SLURM job %s exited successfully but produced no non-empty result artifacts",
                        self._job_id,
                    )
                    return JobState.FAILED
                self._maybe_stage_callback(JobState.COMPLETED)
                return JobState.COMPLETED

            logging.error("SLURM job %s failed with exit code %s", self._job_id, exit_code)
            return JobState.FAILED
        finally:
            self._remove_wrapper_script()

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

    def _build_srun_args(self) -> list[str]:
        resources = self._resolve_resources()
        resolved = {
            "partition": resources.partition,
            "cpus-per-task": resources.cpus,
            "gres": resources.gres,
            "mem": resources.memory,
            "time": resources.slurm_time,
            "nodes": resources.nodes,
            "ntasks": resources.ntasks,
            "qos": resources.qos,
            "account": resources.account,
            "constraint": resources.constraint,
        }
        opts: list[str] = []
        for option, value in resolved.items():
            if value is None:
                continue
            opts.append(f"--{option}={value}")
        if resources.exclusive:
            opts.append("--exclusive")

        # The worker container's /app/server cwd does not exist on compute
        # nodes.  Use the task-specific shared output directory so slurmstepd
        # never falls back to /tmp and every job has an isolated valid cwd.
        opts.append(f"--chdir={self.output_dir}")
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
        self._wrapper_script_path = path
        return path

    def _render_wrapper(self) -> str:
        lines = ["#!/bin/bash", "set -euo pipefail", ""]
        self._render_input_staging(lines)
        lines.append("")
        self._render_apptainer_invocation(lines)
        return "\n".join(lines) + "\n"

    def _render_input_staging(self, lines: list[str]) -> None:
        lines.append("# -- immutable input snapshot verification --")
        for fe in self.file_entities:
            lines.append(f"test -f {_sh_quote(fe['snapshot_path'])}")
            checksum_record = f"{fe['hash']}  {fe['snapshot_path']}"
            lines.append(f"printf '%s\\n' {_sh_quote(checksum_record)} | sha256sum --check --status")

    def _render_apptainer_invocation(self, lines: list[str]) -> None:
        sif_image = self.tt.runtime.slurm_image
        if not sif_image:
            raise RuntimeError(f"Runner {self.tt.name!r} has slurm_image unset")

        bind_parts: list[str] = []
        bind_parts.append(
            f"--bind {_sh_quote(self.input_snapshot_root)}:{_sh_quote(self.virtual_workspace_root + '/inputs')}:ro"
        )
        bind_parts.append(f"--bind {_sh_quote(self.output_dir)}:{_sh_quote(self.virtual_workspace_root + '/outputs')}")
        for m in self.runner.mounts:
            bind_parts.append(f"--bind {_sh_quote(m.host_path)}:{_sh_quote(m.container_path)}:{m.mode}")

        lines.append("# -- apptainer --")
        # APPTAINERENV_ prefixed vars are forwarded into the container.
        lines.append(f"export APPTAINERENV_TASK_ID={_sh_quote(self.task_id)}")
        lines.append(f"export APPTAINERENV_TASK_TYPE={_sh_quote(self.tt.name)}")
        for key, val in self.runner.env.items():
            lines.append(f"export APPTAINERENV_{key}={_sh_quote(val)}")

        # Keep threaded numerical libraries inside the allocation.  Without
        # this, PyTorch/OpenMP can observe all host CPUs even when Slurm grants
        # a smaller cpus-per-task value, causing silent overcommit.
        lines.extend(
            [
                'allocated_cpus="${SLURM_CPUS_PER_TASK:-1}"',
                'case "${allocated_cpus}" in (*[!0-9]*|""|0) allocated_cpus=1 ;; esac',
                'export APPTAINERENV_NPROC="${allocated_cpus}"',
                'export APPTAINERENV_GREMLIN_CALC_CPU_NUM="${allocated_cpus}"',
                'export APPTAINERENV_OMP_NUM_THREADS="${allocated_cpus}"',
                'export APPTAINERENV_MKL_NUM_THREADS="${allocated_cpus}"',
                'export APPTAINERENV_OPENBLAS_NUM_THREADS="${allocated_cpus}"',
                'export APPTAINERENV_VECLIB_MAXIMUM_THREADS="${allocated_cpus}"',
                'export APPTAINERENV_NUMEXPR_NUM_THREADS="${allocated_cpus}"',
                'export APPTAINERENV_TF_NUM_INTRAOP_THREADS="${allocated_cpus}"',
                'export APPTAINERENV_TF_NUM_INTEROP_THREADS="${allocated_cpus}"',
            ]
        )

        params = {e["name"]: e["verified_value"] for e in self.param_entities}
        params_json = json.dumps(params, separators=(",", ":"), sort_keys=True)
        # Apptainer strips one backslash from APPTAINERENV_* values during
        # forwarding — escape once more so JSON strings (e.g. SMILES with
        # backslashes) survive intact inside the container.
        lines.append(f"export APPTAINERENV_TASK_PARAMS={_sh_quote(params_json.replace(chr(92), chr(92) * 2))}")
        inputs_json = json.dumps(
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
        lines.append(f"export APPTAINERENV_TASK_INPUTS={_sh_quote(inputs_json.replace(chr(92), chr(92) * 2))}")
        gpu_flag = " --nv" if self.tt.gpus else ""
        # --containall: private /dev,/proc,/sys and fresh tmpfs for /tmp and
        # $HOME — no host HOME, shared filesystems, or credentials visible.
        # --cleanenv: host env is dropped; only the APPTAINERENV_* variables
        # exported above are forwarded. All required mounts are the explicit
        # --bind entries, so containment costs nothing for these images.
        cmd = f"apptainer run{gpu_flag} --containall --cleanenv {' '.join(bind_parts)} {_sh_quote(sif_image)}"
        for arg in self.tt.runner_args:
            cmd += f" {_sh_quote(arg)}"
        if self.tt.name == "gremlin" and not self.tt.runner_args:
            # GREMLIN/PSSM consumes its worker count from -j; environment
            # thread caps alone do not constrain its BLAST/HH-suite flags.
            cmd += ' -j "${allocated_cpus}"'
        if self.file_entities:
            cmd += f" -i {_sh_quote(self.file_entities[0]['mounted'])}"
        cmd += f" -o {_sh_quote(self.virtual_workspace_root + '/outputs')}"
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
        try:
            for line in iter(stream.readline, ""):
                self._stderr_lines.append(line)
                match = _SLURM_JOB_ID_RE.search(line)
                if match and self._slurm_job_id is None:
                    self._slurm_job_id = match.group(1)
                    self._job_id_event.set()
        finally:
            if self._slurm_job_id is None:
                self._job_id_event.set()  # no banner seen — stop the wait
            stream.close()

    def _save_output(self) -> None:
        # Keep scheduler diagnostics in a clearly named, previewable namespace
        # instead of ambiguous ``slurm_srun-32.out`` files at the result root.
        execution_dir = os.path.join(self.output_dir, "execution")
        os.makedirs(execution_dir, exist_ok=True)
        username = _sanitize_name(self._username or "unknown-user")
        task_name = _sanitize_name(getattr(self.tt, "name", "unknown-task"))
        task_id = _sanitize_name(self.task_id)
        out_path = os.path.join(execution_dir, f"slurm-{username}-{task_name}-{task_id}.stdout.log")
        err_path = os.path.join(execution_dir, f"slurm-{username}-{task_name}-{task_id}.stderr.log")
        try:
            with open(out_path, "w") as f:
                f.writelines(self._stdout_lines)
            with open(err_path, "w") as f:
                f.writelines(self._stderr_lines)
        except OSError as exc:
            logging.warning("Could not save SLURM output for %s: %s", self._job_id, exc)

    def _has_result_artifact(self) -> bool:
        """Return true when the task produced a real, non-empty result file.

        SLURM capture logs, wrapper scripts, and completion sentinels are
        operational files.  They cannot by themselves prove that a scientific
        tool succeeded—some tools catch inference errors and still exit zero.
        """
        for root, _dirs, files in os.walk(self.output_dir):
            for filename in files:
                if filename == "task_finished":
                    continue
                if filename.startswith("_slurm_wrapper_") and filename.endswith(".sh"):
                    continue
                if self._is_execution_log(os.path.join(root, filename)):
                    continue
                path = os.path.join(root, filename)
                try:
                    if not os.path.islink(path) and os.path.isfile(path) and os.path.getsize(path) > 0:
                        return True
                except OSError:
                    continue
        return False

    def _is_execution_log(self, path: str) -> bool:
        relative = os.path.relpath(path, self.output_dir).replace(os.sep, "/")
        filename = os.path.basename(relative)
        return (
            relative.startswith("execution/slurm-")
            and filename.startswith("slurm-")
            and filename.endswith((".stdout.log", ".stderr.log"))
        )

    def _maybe_stage_callback(self, state: JobState) -> None:
        if state == JobState.COMPLETED and self.stage_callback and self.tt.stage_markers:
            stages = list(self.tt.stage_markers.items())
            if stages:
                self.stage_callback(stages[-1][0])

    def _remove_wrapper_script(self) -> None:
        """Delete the internal wrapper script so internal paths never leak
        into the user download archive."""
        path = self._wrapper_script_path
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass


def _sanitize_name(s: str) -> str:
    """SLURM job names: alphanumeric, underscore, hyphen only."""
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in (s or "unknown")) or "unknown"


def _sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"
