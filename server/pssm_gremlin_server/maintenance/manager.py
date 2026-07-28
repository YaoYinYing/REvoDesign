# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Standalone APScheduler manager for lightweight server maintenance jobs."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable

from apscheduler.schedulers.blocking import BlockingScheduler
from pssm_gremlin_server.maintenance.model import PeriodicTask
from pssm_gremlin_server.maintenance.tasks.admin_digest import admin_digest_task
from pssm_gremlin_server.maintenance.tasks.database_backup import database_backup_task
from pssm_gremlin_server.maintenance.tasks.result_cleanup import result_cleanup_task

PERIODIC_TASKS = (admin_digest_task, result_cleanup_task, database_backup_task)


def configure_jobs(
    scheduler: BlockingScheduler,
    tasks: Iterable[PeriodicTask] = PERIODIC_TASKS,
) -> list[str]:
    """Register enabled maintenance jobs and return their stable IDs."""
    return [task.id for task in tasks if task.register(scheduler)]


def build_scheduler() -> BlockingScheduler:
    """Create the single-process in-memory maintenance scheduler."""
    scheduler = BlockingScheduler(timezone=os.environ.get("TZ", "UTC"))
    registered = configure_jobs(scheduler)
    if registered:
        logging.info("Enabled maintenance jobs: %s", ", ".join(registered))
    else:
        logging.info("No maintenance jobs are enabled; scheduler will remain idle")
    return scheduler


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build_scheduler().start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
