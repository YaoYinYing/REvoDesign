# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Maintenance sentinel lifecycle for restart downtime."""

from __future__ import annotations

import os

SENTINEL_NAME = ".maintenance"


def sentinel_path(state) -> str:
    return os.path.join(state.server_dir(), SENTINEL_NAME)


def begin_maintenance(state) -> None:
    from revocompute_ctl.compose import container_fs

    container_fs(
        state,
        f"printf 'deployment maintenance\\n' > /srv/{SENTINEL_NAME}",
        [(state.server_dir(), "/srv")],
    )
    print("Maintenance mode enabled (submissions paused).")


def end_maintenance(state) -> None:
    from revocompute_ctl.compose import container_fs

    container_fs(state, f"rm -f /srv/{SENTINEL_NAME}", [(state.server_dir(), "/srv")], check=False)
    print("Maintenance mode lifted; submissions resumed.")
