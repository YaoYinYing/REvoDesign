# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""ZIP and copy-truncate server logs on line-count or age thresholds."""

from __future__ import annotations

import logging
import os
import re
import time
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pssm_gremlin_server.config import env_float, env_int, env_path
from pssm_gremlin_server.maintenance.model import PeriodicTask

_SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*([KMGT]?B?)?", re.IGNORECASE)
_SIZE_MULTIPLIERS = {
    "": 1,
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "M": 1024**2,
    "MB": 1024**2,
    "G": 1024**3,
    "GB": 1024**3,
    "T": 1024**4,
    "TB": 1024**4,
}


def parse_log_size(value: str) -> int:
    """Parse a byte count with an optional binary K/M/G/T suffix."""
    match = _SIZE_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError("MAX_LOG_SIZE must be bytes or use a K, M, G, or T suffix")
    size = int(float(match.group(1)) * _SIZE_MULTIPLIERS[match.group(2).upper()])
    if size <= 0:
        raise ValueError("MAX_LOG_SIZE must be positive when set")
    return size


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _line in handle)


def _managed_log_size(log_dir: Path) -> int:
    paths = [*log_dir.glob("*.log"), *log_dir.glob("*.log.*.zip")]
    return sum(path.stat().st_size for path in paths if path.is_file())


def _prune_oldest_archives(log_dir: Path, max_size: int) -> None:
    total = _managed_log_size(log_dir)
    archives = sorted(
        log_dir.glob("*.log.*.zip"),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    for archive in archives:
        if total <= max_size:
            break
        size = archive.stat().st_size
        archive.unlink()
        total -= size
        logging.info("Removed oldest rotated log %s", archive)


def rotate_logs(
    log_dir: str,
    max_lines: int | None,
    period_days: float | None,
    max_size: int | None,
    *,
    now: float | None = None,
) -> int:
    """Rotate matching logs, enforce the total size cap, and return the count."""
    current_time = time.time() if now is None else now
    directory = Path(log_dir)
    rotated = 0

    if max_size is not None:
        _prune_oldest_archives(directory, max_size)
    rotate_for_size = max_size is not None and _managed_log_size(directory) > max_size

    for log_path in sorted(directory.glob("*.log")):
        marker = log_path.with_name(f".{log_path.name}.rotation")
        if not marker.exists():
            marker.touch()
            os.utime(marker, (current_time, current_time))

        by_lines = max_lines is not None and _line_count(log_path) > max_lines
        by_period = (
            period_days is not None
            and current_time - marker.stat().st_mtime >= period_days * 86400
        )
        if log_path.stat().st_size == 0 or not (by_lines or by_period or rotate_for_size):
            continue

        timestamp = datetime.fromtimestamp(current_time, timezone.utc).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
        archive = log_path.with_name(f"{log_path.name}.{timestamp}.zip")
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(log_path, arcname=log_path.name)
        # ponytail: copy-truncate keeps existing process file descriptors valid;
        # use service-specific reopen signals only if the tiny write race matters.
        log_path.open("w", encoding="utf-8").close()
        os.utime(marker, (current_time, current_time))
        rotated += 1
        logging.info("Rotated log %s to %s", log_path, archive)

    if max_size is not None:
        _prune_oldest_archives(directory, max_size)
    return rotated


class LogRotationTask(PeriodicTask):
    """Environment-configured log rotation."""

    id = "log-rotation"

    @property
    def task_method(self) -> Callable[..., Any]:
        return rotate_logs

    def configure(self) -> None:
        max_lines_raw = os.environ.get("ROTATE_LOG_MAX_LINENO", "").strip()
        period_raw = os.environ.get("ROTATE_LOG_PERIOD", "").strip()
        max_size_raw = os.environ.get("MAX_LOG_SIZE", "").strip()
        max_lines = env_int("ROTATE_LOG_MAX_LINENO", 0) if max_lines_raw else None
        period_days = env_float("ROTATE_LOG_PERIOD", 0.0) if period_raw else None
        max_size = parse_log_size(max_size_raw) if max_size_raw else None
        log_dir = env_path(
            "LOG_DIR",
            os.path.join(os.getcwd(), "pssm_gremlin_data", "logs"),
        )

        self.env = {
            "ROTATE_LOG_MAX_LINENO": max_lines,
            "ROTATE_LOG_PERIOD": period_days,
            "MAX_LOG_SIZE": max_size,
            "LOG_DIR": log_dir,
        }
        self._args = {}
        self._is_enabled = False

        if max_lines is not None and max_lines <= 0:
            raise ValueError("ROTATE_LOG_MAX_LINENO must be a positive integer when set")
        if period_days is not None and period_days <= 0:
            raise ValueError("ROTATE_LOG_PERIOD must be a positive number when set")
        if max_lines is None and period_days is None and max_size is None:
            return

        self._is_enabled = True
        self._args = {
            "trigger": "interval",
            "hours": 1,
            "args": (log_dir, max_lines, period_days, max_size),
            "misfire_grace_time": 3600,
            "next_run_time": datetime.now(timezone.utc),
        }


log_rotation_task = LogRotationTask()
