# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Common contract for self-configuring periodic maintenance tasks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from apscheduler.schedulers.base import BaseScheduler


class PeriodicTask(ABC):
    """A maintenance task that owns its environment and scheduler options."""

    id: str
    max_instances: int = 1

    def __init__(self) -> None:
        self.env: dict[str, Any] = {}
        self._args: dict[str, Any] = {}
        self._is_enabled = False

    @property
    @abstractmethod
    def task_method(self) -> Callable[..., Any]:
        """Callable invoked by APScheduler."""

    @property
    def is_enabled(self) -> bool:
        """Whether the latest environment configuration enables this task."""
        return self._is_enabled

    @property
    def args(self) -> dict[str, Any]:
        """Keyword arguments passed to ``scheduler.add_job``."""
        return dict(self._args)

    @abstractmethod
    def configure(self) -> None:
        """Read environment variables and update ``env``, ``args``, and state."""

    def register(self, scheduler: BaseScheduler) -> bool:
        """Configure and, when enabled, register this task with *scheduler*."""
        self.configure()
        if not self.is_enabled:
            return False
        scheduler.add_job(
            self.task_method,
            id=self.id,
            replace_existing=True,
            coalesce=True,
            max_instances=self.max_instances,
            **self.args,
        )
        return True
