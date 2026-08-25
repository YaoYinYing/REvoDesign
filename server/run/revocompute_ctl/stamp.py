# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Deploy stamp and config backup.

A successful restart writes CONFIG_DIR/.deploy-stamp — commit, dirty flag,
mode, step timings, changed/unchanged families, image digests, SIF sha256s,
registry sha256, and the config-backup path.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path

from revocompute_ctl.compose import container_fs, image_id, run_cmd
from revocompute_ctl.registry import RuntimeFamily

STAMP_FILENAME = ".deploy-stamp"


def registry_sha256(config_dir: str) -> str:
    registry = Path(config_dir) / "task_types.yaml"
    return _sha256_file(str(registry)) if registry.is_file() else ""


def backup_config(state) -> str:
    """CONFIG_DIR → SERVER_DIR/backups/config-<ts> (pre-down), copied by a
    throwaway container as the runner identity."""
    stamp = datetime.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    backup = os.path.join(state.server_dir(), "backups", f"config-{stamp}")
    container_fs(
        state,
        f"mkdir -p /srv/backups && cp -a /cfg /srv/backups/{os.path.basename(backup)}",
        [(state.config_dir(), "/cfg"), (state.server_dir(), "/srv")],
    )
    print(f"Config backup written to: {backup}")
    return backup


def write_stamp(state, payload: dict) -> str:
    path = os.path.join(state.config_dir(), STAMP_FILENAME)
    container_fs(
        state,
        f"cat > /cfg/{STAMP_FILENAME}",
        [(state.config_dir(), "/cfg")],
        stdin_data=json.dumps(payload, indent=2, sort_keys=True),
    )
    print(f"Deploy stamp written to: {path}")
    return path


def stamp_payload(
    state,
    *,
    mode: str,
    timings: dict[str, float],
    changed: list[str],
    unchanged: list[str],
    images: dict[str, str],
    baseline: dict[str, dict[str, str]],
    families: list[RuntimeFamily],
    backup_path: str,
) -> dict:
    """Assemble the stamp.  Reads the current digests (post-up)."""
    # The caller's cwd is not the checkout; pin git to the server root.
    commit = run_cmd(["git", "-C", state.server_root(), "rev-parse", "HEAD"], check=False, capture=True).stdout.strip()
    dirty = (
        run_cmd(["git", "-C", state.server_root(), "status", "--porcelain"], check=False, capture=True).stdout.strip()
        != ""
    )
    digests: dict[str, dict[str, str]] = {}
    for name, image in images.items():
        digests[name] = {
            "latest": image_id(state, f"{image}:latest"),
            "baseline_latest": (baseline.get(name) or {}).get("latest", ""),
        }
    sif_sha256s: dict[str, str] = {}
    if state.use_slurm():
        # Multi-GB files — hash only SIFs this deploy actually changed.
        for family in families:
            if family.name in changed and os.path.isfile(family.slurm_image):
                sif_sha256s[family.name] = _sha256_file(family.slurm_image)
    return {
        "commit": commit,
        "dirty": dirty,
        "mode": mode,
        "stamped_at": datetime.datetime.now().astimezone().isoformat(),
        "timings": timings,
        "changed": changed,
        "unchanged": unchanged,
        "digests": digests,
        "sif_sha256s": sif_sha256s,
        "registry_sha256": registry_sha256(state.config_dir()),
        "config_backup": backup_path,
    }


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
