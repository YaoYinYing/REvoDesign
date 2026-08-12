# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sqlite3

import pytest
from revocompute.manage_db import ManageDatabase
from revocompute.resource_audit import _read_database
from revocompute.resource_policy import (
    ResolvedResources,
    ResourceValidationError,
    normalize_resource_value,
    resolve_resources,
)


def _resolve(task=None, global_values=None, *, gpu=False, queues=(), timeout=7200):
    task = task or {}
    global_values = global_values or {}
    return resolve_resources(
        task.get,
        global_values.get,
        requires_gpu=gpu,
        allowed_queues=queues,
        default_timeout_seconds=timeout,
    )


def test_canonical_resources_override_legacy_values_and_are_explicit():
    resources = _resolve(
        {"cpus": 16, "memory": "32G", "nproc": 2, "slurm_mem": "4G"},
        {"cpus": 8, "memory": "8G"},
    )
    assert resources.cpus == 16
    assert resources.memory == "32G"
    assert resources.max_runtime_seconds == 7200
    assert resources.slurm_time == "02:00:00"
    assert resources.nodes == 1
    assert resources.ntasks == 1


def test_legacy_resources_are_migration_fallbacks():
    resources = _resolve(
        {"slurm_cpus_per_task": "12", "maxmem": "24"},
        {"cpus": "4", "memory": "8G"},
    )
    assert resources.cpus == 12
    assert resources.memory == "24G"
    assert resources.sources["cpus"] == "task:slurm_cpus_per_task"
    assert resources.sources["memory"] == "task:maxmem"


def test_gpu_policy_reserves_one_device_but_cpu_policy_ignores_global_gres():
    assert _resolve(gpu=True).gres == "gpu:1"
    assert _resolve(global_values={"slurm_gres": "gpu:a100:1"}, gpu=True).gres == "gpu:a100:1"
    assert _resolve(global_values={"slurm_gres": "gpu:a100:1"}, gpu=False).gres is None
    with pytest.raises(ResourceValidationError, match="CPU-only"):
        _resolve({"slurm_gres": "gpu:1"}, gpu=False)


def test_partition_allowlist_is_enforced_and_has_deterministic_default():
    assert _resolve(queues=("normal", "gpu")).partition == "normal"
    assert _resolve({"slurm_partition": "gpu"}, queues=("normal", "gpu")).partition == "gpu"
    with pytest.raises(ResourceValidationError, match="allowed queue"):
        _resolve({"slurm_partition": "debug"}, queues=("normal", "gpu"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cpus", 0),
        ("memory", "many"),
        ("slurm_time", "forever"),
        ("slurm_gres", "gpu:all"),
        ("slurm_partition", "normal --exclusive"),
    ],
)
def test_invalid_resource_values_fail_closed(field, value):
    with pytest.raises(ResourceValidationError):
        normalize_resource_value(field, value)


def test_slurm_constraint_expressions_are_preserved_without_whitespace_or_options():
    assert normalize_resource_value("slurm_constraint", "[a100|h100]&nvlink") == "[a100|h100]&nvlink"
    with pytest.raises(ResourceValidationError):
        normalize_resource_value("slurm_constraint", "a100 --exclusive")


def test_resource_snapshot_round_trip_is_strict():
    resources = _resolve(
        {"cpus": 8, "memory": "16G", "slurm_partition": "normal"}, gpu=True
    )
    restored = ResolvedResources.from_snapshot(resources.public_dict())
    assert restored.public_dict() == resources.public_dict()
    broken = resources.public_dict()
    broken["slurm_time"] = "00:01:00"
    with pytest.raises(ResourceValidationError, match="inconsistent"):
        ResolvedResources.from_snapshot(broken)


def test_manage_database_migrates_canonical_columns_and_resolves_policy(tmp_path):
    database_path = tmp_path / "manage.sqlite"
    connection = sqlite3.connect(database_path)
    connection.execute(
        "CREATE TABLE task_type_config ("
        "tool TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1, "
        "nproc INTEGER, maxmem INTEGER)"
    )
    connection.execute("INSERT INTO task_type_config (tool, nproc, maxmem) VALUES ('gremlin', 6, 12)")
    connection.commit()
    connection.close()

    database = ManageDatabase(str(database_path))
    try:
        columns = {row[1] for row in database._conn.execute("PRAGMA table_info(task_type_config)")}
        assert {"cpus", "memory"}.issubset(columns)
        resources = database.resolve_task_resources(
            "gremlin", requires_gpu=False, default_timeout_seconds=3600
        )
        assert resources.cpus == 6
        assert resources.memory == "12G"
        database.task_type_upsert("gremlin", cpus=10, memory="20G")
        updated = database.resolve_task_resources(
            "gremlin", requires_gpu=False, default_timeout_seconds=3600
        )
        assert updated.cpus == 10
        assert updated.memory == "20G"
    finally:
        database.close()


def test_preflight_database_read_is_read_only(tmp_path):
    database_path = tmp_path / "manage.sqlite"
    connection = sqlite3.connect(database_path)
    connection.execute(
        "CREATE TABLE task_type_config (tool TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1, nproc INTEGER)"
    )
    connection.execute(
        "CREATE TABLE resource_config (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at REAL NOT NULL)"
    )
    connection.execute("INSERT INTO task_type_config VALUES ('gremlin', 1, 4)")
    connection.execute("INSERT INTO resource_config VALUES ('memory', '8G', 0)")
    connection.commit()
    before = [row[1] for row in connection.execute("PRAGMA table_info(task_type_config)")]
    connection.close()

    globals_, tasks = _read_database(str(database_path))
    assert globals_["memory"] == "8G"
    assert tasks["gremlin"]["nproc"] == 4

    connection = sqlite3.connect(database_path)
    try:
        after = [row[1] for row in connection.execute("PRAGMA table_info(task_type_config)")]
    finally:
        connection.close()
    assert after == before
