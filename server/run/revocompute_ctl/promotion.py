# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Deployment image promotion.

Docker: runner images build to ``:next``; after the stack is down the tag
scheme advances ``latest`` → ``previous`` → (``next`` → ``latest``), so the
rollback target always survives the post-deploy prune.  Unchanged families
see zero churn.  Prod pulls retag ``previous`` from the pre-pull baseline id.

SIFs: builds stage ``<sif>.next``; promotion moves them into place after
down, saving the current SIF as ``<sif>.previous``.
"""

from __future__ import annotations

import os

from revocompute_ctl.compose import image_id, run_cmd
from revocompute_ctl.registry import RuntimeFamily, runner_enabled


def taggable_images(state, families: list[RuntimeFamily]) -> dict[str, str]:
    """name → image for every image the tag scheme manages: runner families
    plus the server image.  Images that carry an explicit tag or digest are
    externally managed and excluded from the next/latest/previous dance."""
    managed: dict[str, str] = {}
    server_image = state.get("SERVER_IMAGE") or "revodesign-revocompute-server"
    if ":" not in server_image and "@" not in server_image:
        managed["server"] = server_image
    for family in families:
        if ":" not in family.docker_image and "@" not in family.docker_image:
            managed[family.name] = family.docker_image
    return managed


def _tagged(image: str, tag: str) -> str:
    return f"{image}:{tag}"


def capture_baseline_digests(state, images: dict[str, str]) -> dict[str, dict[str, str]]:
    """Pre-down digest capture: {name: {latest, next}} — reads only, safe
    for --dry-run.  SIF hashes are recorded post-up by the stamp instead."""
    baseline: dict[str, dict[str, str]] = {}
    for name, image in images.items():
        baseline[name] = {
            "latest": image_id(state, _tagged(image, "latest")),
            "next": image_id(state, _tagged(image, "next")),
        }
    return baseline


def changed_image_names(state, images: dict[str, str], baseline: dict[str, dict[str, str]], mode: str) -> set[str]:
    """Families whose image will change in this restart: dev compares
    :next vs :latest, prod compares the post-pull latest against the
    pre-pull baseline, prepared is always unchanged."""
    changed: set[str] = set()
    for name, image in images.items():
        next_id = image_id(state, _tagged(image, "next"))
        latest_id = image_id(state, _tagged(image, "latest"))
        if mode == "dev":
            if next_id and (not latest_id or next_id != latest_id):
                changed.add(name)
        elif mode == "prod":
            baseline_latest = (baseline.get(name) or {}).get("latest", "")
            if latest_id and baseline_latest and latest_id != baseline_latest:
                changed.add(name)
    return changed


def promote_docker(state, images: dict[str, str], baseline: dict[str, dict[str, str]], mode: str) -> None:
    """Advance the tag scheme after down + build/pull."""
    for name, image in images.items():
        latest_tag = _tagged(image, "latest")
        next_tag = _tagged(image, "next")
        previous_tag = _tagged(image, "previous")
        next_id = image_id(state, next_tag)
        latest_id = image_id(state, latest_tag)
        if mode == "prod":
            baseline_latest = (baseline.get(name) or {}).get("latest", "")
            if baseline_latest and latest_id and baseline_latest != latest_id:
                print(f"Tagging previous {image} from the pre-pull image ({baseline_latest[:12]})")
                run_cmd(["docker", "tag", baseline_latest, previous_tag], env=state.exported())
            continue
        if mode == "prepared":
            continue
        if not next_id:
            # No :next staging — the image was replaced in place (the server
            # image via `compose build`).  Retag previous from the pre-down
            # baseline id so rollback can restore it.
            baseline_latest = (baseline.get(name) or {}).get("latest", "")
            if baseline_latest and latest_id and baseline_latest != latest_id:
                print(f"Tagging previous {image} from the pre-build image ({baseline_latest[:12]})")
                run_cmd(["docker", "tag", baseline_latest, previous_tag], env=state.exported())
            continue
        if not latest_id:
            print(f"Promoting {next_tag} → {latest_tag} (first deploy)")
            run_cmd(["docker", "tag", next_tag, latest_tag], env=state.exported())
        elif next_id != latest_id:
            print(f"Promoting {image}: latest → previous, next → latest")
            run_cmd(["docker", "tag", latest_tag, previous_tag], env=state.exported())
            run_cmd(["docker", "rmi", latest_tag], env=state.exported())
            run_cmd(["docker", "tag", next_tag, latest_tag], env=state.exported())
        else:
            print(f"Runner image unchanged: {image}")
            run_cmd(["docker", "rmi", next_tag], env=state.exported())


def promote_sifs(state, families: list[RuntimeFamily]) -> None:
    """Move any staged ``<sif>.next`` into place, saving the current SIF as
    ``<sif>.previous``.  The staging set itself decides what to promote —
    only stale or missing families ever have a ``.next``."""
    for family in families:
        if not runner_enabled(state, family.name):
            continue
        sif = family.slurm_image
        staged = f"{sif}.next"
        if os.path.isfile(staged):
            if os.path.isfile(sif):
                os.replace(sif, f"{sif}.previous")
            os.replace(staged, sif)
            print(f"[SLURM] Promoted staged SIF: {sif}")


def prune_dangling(state) -> None:
    """Dangling-only prune; ``previous`` and ``latest`` tags always survive."""
    run_cmd(["docker", "image", "prune", "-f"], env=state.exported(), check=False)
    run_cmd(["docker", "buildx", "prune", "-f"], env=state.exported(), check=False)


# -- rollback support --------------------------------------------------------


def verify_rollback_targets(state, images: dict[str, str], changed: set[str]) -> None:
    """Refuse the rollback (naming the stamped commit) when any previous tag
    from the changed set no longer exists."""
    missing = [
        _tagged(image, "previous")
        for name, image in images.items()
        if name in changed and not image_id(state, _tagged(image, "previous"))
    ]
    if missing:
        raise RollbackRefused(f"Rollback targets missing: {', '.join(missing)}")


def rollback_docker(state, images: dict[str, str], changed: set[str]) -> None:
    for name, image in images.items():
        if name not in changed:
            continue
        previous_tag = _tagged(image, "previous")
        latest_tag = _tagged(image, "latest")
        print(f"Rolling back {image}: previous → latest")
        run_cmd(["docker", "tag", previous_tag, latest_tag], env=state.exported())


def rollback_sifs(state, families: list[RuntimeFamily]) -> None:
    for family in families:
        if not runner_enabled(state, family.name):
            continue
        previous = f"{family.slurm_image}.previous"
        if os.path.isfile(previous):
            print(f"[SLURM] Rolling back SIF: {family.slurm_image}")
            os.replace(previous, family.slurm_image)


class RollbackRefused(Exception):
    """The stamped previous set cannot be restored."""
