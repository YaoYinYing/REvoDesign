# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Abstract compute job interface.

Each runner backend (Docker, SLURM/Apptainer) implements the Job ABC so
``task_runtime.py`` can submit / poll / cancel without backend-specific
branching.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class JobState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(ABC):
    """A compute job submitted to a backend (Docker, SLURM, …).

    Subclasses implement ``submit``, ``poll``, and ``cancel`` for their
    specific runtime.  The caller only needs to call ``submit()`` then
    ``poll()`` — the ABC handles the rest.
    """

    def __init__(
        self,
        task_id: str,
        tt: Any,  # TaskType (avoid circular import)
        runner: Any,  # RunnerConfig
        entities: list[dict],
        output_dir: str,
        stage_callback: Any = None,
    ):
        self.task_id = task_id
        self.tt = tt
        self.runner = runner
        self.entities = entities
        self.output_dir = output_dir
        self.stage_callback = stage_callback
        self._job_id: str | None = None

    # -- public API ----------------------------------------------------------

    @abstractmethod
    def submit(self) -> str:
        """Submit the job to the backend, return the backend job id."""
        ...

    @abstractmethod
    def poll(self) -> JobState:
        """Block until the job reaches a terminal state, return that state."""
        ...

    @abstractmethod
    def cancel(self) -> None:
        """Kill a running job."""
        ...

    # -- helpers -------------------------------------------------------------

    @property
    def job_id(self) -> str | None:
        return self._job_id

    @property
    def file_entities(self) -> list[dict]:
        return [e for e in self.entities if e["type"] == "file"]

    @property
    def param_entities(self) -> list[dict]:
        return [e for e in self.entities if e["type"] != "file"]

    @property
    def workspace_key(self) -> str:
        if not self.file_entities:
            raise RuntimeError("A compute job requires at least one input file")
        return str(self.file_entities[0]["workspace_key"])

    @property
    def virtual_workspace_root(self) -> str:
        return f"/mnt/revocompute/{self.workspace_key}"

    @property
    def input_snapshot_root(self) -> str:
        if not self.file_entities:
            raise RuntimeError("A compute job requires at least one input file")
        return str(self.file_entities[0]["snapshot_root"])
