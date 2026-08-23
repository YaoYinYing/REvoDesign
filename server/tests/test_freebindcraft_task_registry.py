# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path

import yaml

SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_freebindcraft_contract():
    registry = yaml.safe_load((SERVER_ROOT / "config/task_types.yaml").read_text(encoding="utf-8"))
    task = registry["task_types"]["freebindcraft"]
    runtime = registry["runtime_families"]["freebindcraft"]
    runner = yaml.safe_load((SERVER_ROOT / "config/runners/freebindcraft.yaml").read_text(encoding="utf-8"))
    script = (SERVER_ROOT / "docker/runners/freebindcraft/run.sh").read_text(encoding="utf-8")
    dockerfile = (SERVER_ROOT / runtime["dockerfile"]).read_text(encoding="utf-8")
    consumed = {line.split("_parse_param ", 1)[1].split()[0] for line in script.splitlines() if "_parse_param " in line}

    assert task["runtime_family"] == "freebindcraft"
    assert task["gpus"] is True
    assert task["input_extensions"] == [".pdb"]
    assert runner["mounts"] == [
        {
            "host_path": "/mnt/db/weights/alphafold/2022-12-06",
            "container_path": "/mnt/db/bindcraft/af_params",
            "mode": "ro",
        }
    ]
    assert {param["name"] for param in task["params"]} <= consumed
    assert 'filters_file="/opt/bindcraft/settings_filters/${filters_preset}.json"' in script
    assert '"filter_file"' not in script
    assert 'accepted_designs=("$output_dir"/Accepted/*.pdb)' in script
    assert "final_designs <= max_trajectories" in script
    assert 'ENV HTTP_PROXY="http' not in dockerfile
    assert "USER ${RUNNER_UID}:${RUNNER_GID}" in dockerfile
