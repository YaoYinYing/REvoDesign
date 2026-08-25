# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Pre-stop SLURM sweep.

Kill and mark every in-flight SLURM task before the worker dies.  The worker
owns the srun clients, so stopping the stack orphans anything running; a
clean pre-stop sweep means no orphan can ever exist and no boot-time
recovery machinery is needed.
"""

from __future__ import annotations

import sys

from revocompute_ctl.compose import compose_args, run_cmd

# Byte-identical to the heredoc restart.sh fed to the worker container.
JOB_IDS_SOURCE = """from revocompute.task_runtime import task_store
for task in task_store.list_tasks():
    job_id = str(task.get("slurm_job_id") or "").strip()
    if task.get("status") in {"queued", "running"} and job_id.isdigit():
        print(job_id)
"""

SWEEP_SOURCE = """import json
import time
from revocompute.task_runtime import _get_task_type, _record_failure, task_store
for task in task_store.list_tasks():
    if task.get("status") in {"queued", "running"}:
        task_type = task.get("task_type", "gremlin")
        try:
            is_workflow = bool(getattr(_get_task_type(task_type)[0], "workflow", ()))
        except KeyError:
            is_workflow = False
        if is_workflow:
            try:
                state = json.loads(task.get("workflow_state") or "{}")
            except (TypeError, json.JSONDecodeError):
                state = {}
            for step in state.values():
                if step.get("status") == "running":
                    step["status"] = "interrupted"
            task_store.update_task(
                task["md5sum"],
                status="queued",
                slurm_job_id=None,
                container_id=None,
                workflow_state=json.dumps(state, sort_keys=True),
            )
            continue
        _record_failure(
            task["md5sum"],
            task,
            task.get("started_at") or time.time(),
            str(task.get("run_stage") or ""),
            "Cancelled by server restart",
        )
"""


def pre_stop_sweep_slurm(state, compose_cmd: tuple[str, ...]) -> None:
    """The worker container owns the srun clients, runs as the SLURM user,
    and holds write access to the task DB — the host account has none of the
    three, so the whole sweep runs inside the containers before down."""
    if not state.use_slurm():
        return
    jobs = run_cmd(
        [
            *compose_cmd,
            *compose_args(state),
            "--env-file",
            state.env_file,
            "exec",
            "-T",
            "worker",
            "python3",
            "-",
        ],
        env=state.exported(),
        stdin=JOB_IDS_SOURCE,
        check=False,
        capture=True,
    ).stdout.strip()
    if jobs:
        print(f"Cancelling this deployment's in-flight SLURM jobs: {jobs}")
        run_cmd(
            [
                *compose_cmd,
                *compose_args(state),
                "--env-file",
                state.env_file,
                "exec",
                "-T",
                "worker",
                "scancel",
                *jobs.split(),
            ],
            env=state.exported(),
            check=False,
        )
    print("Preserving workflows and finalizing other in-flight tasks before stopping the stack...")
    marked = run_cmd(
        [*compose_cmd, *compose_args(state), "--env-file", state.env_file, "exec", "-T", "worker", "python3", "-"],
        env=state.exported(),
        stdin=SWEEP_SOURCE,
        check=False,
        capture=True,
    )
    if marked.returncode != 0:
        print(
            "Pre-stop sweep failed to mark in-flight tasks; they may remain queued/running: "
            f"{(marked.stderr or '').strip()}",
            file=sys.stderr,
        )
