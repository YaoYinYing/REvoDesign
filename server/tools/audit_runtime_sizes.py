# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Report Docker and SIF bytes once runtime artifacts exist on a builder.

This tool is deliberately inspect-only: it never builds, pulls, or runs an
image. Run it on the production builder after the normal build pipeline.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml


def _docker_size(image: str) -> int | None:
    docker = shutil.which("docker")
    if not docker:
        return None
    result = subprocess.run(  # nosec B603 -- fixed executable and arguments
        [docker, "image", "inspect", "--format", "{{.Size}}", image],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def collect_sizes(task_types_path: Path) -> list[dict[str, Any]]:
    registry = yaml.safe_load(task_types_path.read_text(encoding="utf-8")) or {}
    tasks_by_runtime: dict[str, list[str]] = {}
    for task_name, task in (registry.get("task_types") or {}).items():
        tasks_by_runtime.setdefault(task["runtime_family"], []).append(task_name)

    rows: list[dict[str, Any]] = []
    for runtime_name, runtime in (registry.get("runtime_families") or {}).items():
        sif_path = str(runtime.get("slurm_image") or "")
        rows.append(
            {
                "runtime_family": runtime_name,
                "tasks": sorted(tasks_by_runtime.get(runtime_name, [])),
                "docker_image": runtime["docker_image"],
                "docker_bytes": _docker_size(runtime["docker_image"]),
                "sif_path": sif_path or None,
                "sif_bytes": os.path.getsize(sif_path) if sif_path and os.path.isfile(sif_path) else None,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    server_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--task-types", type=Path, default=server_root / "config" / "task_types.yaml")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Exit non-zero unless every declared Docker image and SIF is present",
    )
    args = parser.parse_args()
    rows = collect_sizes(args.task_types)
    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        print("runtime_family\ttasks\tdocker_bytes\tsif_bytes\tdocker_image\tsif_path")
        for row in rows:
            print(
                "\t".join(
                    [
                        row["runtime_family"],
                        ",".join(row["tasks"]),
                        str(row["docker_bytes"] or "missing"),
                        str(row["sif_bytes"] or "missing"),
                        row["docker_image"],
                        row["sif_path"] or "-",
                    ]
                )
            )
    if args.require_all and any(row["docker_bytes"] is None or row["sif_bytes"] is None for row in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
