# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Read-only deployment resource-policy preflight.

Designed to run inside the already-prepared worker image before Compose stops
the healthy stack. It never writes the management database.
"""

from __future__ import annotations

import os
import sqlite3
import sys

from revocompute.config import ComputeConfig, env_csv
from revocompute.resource_policy import ResourceValidationError, resolve_resources
from revocompute.task_types import get as get_task_type
from revocompute.task_types import list_types, load_registry


def _read_database(path: str) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
    if not os.path.isfile(path):
        return {}, {}
    connection = sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        globals_: dict[str, str] = {}
        tasks: dict[str, dict[str, object]] = {}
        if "resource_config" in tables:
            globals_ = dict(connection.execute("SELECT key, value FROM resource_config"))
        if "task_type_config" in tables:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(task_type_config)")]
            rows = connection.execute(  # skipcq: BAN-B608 — column names come from PRAGMA table_info, not user input
                f"SELECT {', '.join(columns)} FROM task_type_config"
            )
            for row in rows:
                record = dict(zip(columns, row, strict=True))
                tasks[str(record.pop("tool"))] = record
        return globals_, tasks
    finally:
        connection.close()


def main() -> int:
    config = ComputeConfig.from_env()
    load_registry(
        config.task_types_config,
        config.runners_dir,
        set(env_csv("ENABLED_TASKRUNNERS", "")),
    )
    globals_, task_values = _read_database(config.manage_db_path)
    stored_allowed = globals_.get("slurm_allowed_queues")
    allowed = (
        tuple(value.strip() for value in stored_allowed.split(",") if value.strip())
        if stored_allowed is not None
        else tuple(config.slurm_allowed_queues)
    )
    failed = False
    for task_type in list_types():
        _, runner = get_task_type(task_type.name)
        values = task_values.get(task_type.name, {})
        if values.get("enabled") == 0:
            print(f"[RESOURCE] {task_type.name}: disabled (not audited)")
            continue
        try:
            resolved = resolve_resources(
                values.get,
                globals_.get,
                requires_gpu=task_type.gpus,
                allowed_queues=allowed,
                default_timeout_seconds=runner.max_runtime_seconds,
            )
            accelerator = resolved.gres or "cpu"
            partition = resolved.partition or "scheduler-default"
            print(
                f"[RESOURCE] {task_type.name}: cpus={resolved.cpus} memory={resolved.memory} "
                f"time={resolved.slurm_time} accelerator={accelerator} partition={partition}"
            )
        except ResourceValidationError as exc:
            failed = True
            print(f"[RESOURCE] {task_type.name}: INVALID: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
