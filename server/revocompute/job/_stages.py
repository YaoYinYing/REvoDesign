# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Shared stage-parsing helpers used by both Docker and SLURM runners."""

from __future__ import annotations

_RUNNER_STAGE_PREFIX = "REVODESIGN_STAGE:"


def extract_stage_from_log_line(line: str, stage_markers: dict[str, str]) -> str | None:
    """Extract a stage marker from a runner log line.

    Returns the stage key if found, or None.
    """
    marker_pos = line.find(_RUNNER_STAGE_PREFIX)
    if marker_pos < 0:
        return None
    raw_marker = line[marker_pos + len(_RUNNER_STAGE_PREFIX) :].strip().lower()  # noqa: E203
    if not raw_marker:
        return None
    token = raw_marker.split()[0]
    if token in stage_markers:
        return token
    return None
