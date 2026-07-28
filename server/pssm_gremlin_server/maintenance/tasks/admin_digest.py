# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Periodic administrator registration-digest task."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pssm_gremlin_server.auth import send_admin_digest
from pssm_gremlin_server.config import env_int, env_str
from pssm_gremlin_server.maintenance.model import PeriodicTask


def run_admin_digest() -> bool:
    """Send one digest for registrations not previously notified."""
    return send_admin_digest()


class AdminDigestTask(PeriodicTask):
    """Environment-configured administrator registration digest."""

    id = "admin-registration-digest"

    @property
    def task_method(self) -> Callable[..., Any]:
        return run_admin_digest

    def configure(self) -> None:
        digest_minutes = env_int("ADMIN_NEW_USER_INFORM", 0)
        notify_email = env_str("ADMIN_NOTIFY_EMAIL", "")
        self.env = {
            "ADMIN_NEW_USER_INFORM": digest_minutes,
            "ADMIN_NOTIFY_EMAIL": notify_email,
        }
        self._is_enabled = False
        self._args = {}

        if digest_minutes < 0:
            raise ValueError("ADMIN_NEW_USER_INFORM must be zero or positive")
        if digest_minutes == 0 or not notify_email:
            return

        self._is_enabled = True
        self._args = {
            "trigger": "interval",
            "minutes": digest_minutes,
            "misfire_grace_time": max(60, digest_minutes * 60),
        }


admin_digest_task = AdminDigestTask()
