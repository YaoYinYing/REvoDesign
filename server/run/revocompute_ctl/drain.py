# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Maintenance drain around a restart.

``--drain=<minutes>`` blocks new submissions through the web-visible
``SERVER_DIR/.maintenance`` sentinel (routes.py answers 503 while it exists)
and waits for in-flight SLURM jobs to finish; the pre-stop sweep cancels
whatever remains when the timeout hits.
"""

from __future__ import annotations

import os
import sys
import time

from revocompute_ctl.compose import run_cmd

SENTINEL_NAME = ".maintenance"


def sentinel_path(state) -> str:
    return os.path.join(state.server_dir(), SENTINEL_NAME)


def begin_drain(state, minutes: int) -> None:
    """Create the sentinel and wait for the SLURM queue to empty (SLURM
    deployments only; docker deployments get the sentinel alone).  The
    sentinel is written by a throwaway container as the runner identity —
    SERVER_DIR is deployment-owned."""
    from revocompute_ctl.compose import container_fs

    container_fs(
        state,
        f"printf 'deployment maintenance\\n' > /srv/{SENTINEL_NAME}",
        [(state.server_dir(), "/srv")],
    )
    print(f"Maintenance mode enabled (submissions paused) — draining in-flight jobs, up to {minutes} min.")
    if not state.use_slurm():
        return
    deadline = time.monotonic() + minutes * 60
    user = state.get("RUNNER_USERNAME") or "revodesign"
    while time.monotonic() < deadline:
        jobs = run_cmd(
            ["squeue", "-h", "-u", user, "-o", "%i"], env=state.exported(), check=False, capture=True
        ).stdout.strip()
        if not jobs:
            print("In-flight SLURM jobs drained.")
            return
        print(f"Waiting for in-flight SLURM jobs: {jobs}")
        time.sleep(10)
    print(
        f"[SLURM] Drain timeout after {minutes} minutes — the pre-stop sweep will cancel the remainder.",
        file=sys.stderr,
    )


def end_drain(state) -> None:
    """Remove the sentinel — post-up and on failure alike."""
    from revocompute_ctl.compose import container_fs

    container_fs(state, f"rm -f /srv/{SENTINEL_NAME}", [(state.server_dir(), "/srv")], check=False)
    print("Maintenance mode lifted; submissions resumed.")
