# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Standalone APScheduler manager for lightweight server maintenance jobs."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from pssm_gremlin_server.config import env_int, env_str
from pssm_gremlin_server.maintenance.tasks.admin_digest import run_admin_digest
from pssm_gremlin_server.maintenance.tasks.result_cleanup import run_result_cleanup


def configure_jobs(scheduler: BlockingScheduler) -> list[str]:
    """Register enabled maintenance jobs and return their stable IDs."""
    registered: list[str] = []

    digest_minutes = env_int("ADMIN_NEW_USER_INFORM", 0)
    if digest_minutes < 0:
        raise ValueError("ADMIN_NEW_USER_INFORM must be zero or positive")
    if digest_minutes > 0 and env_str("ADMIN_NOTIFY_EMAIL", ""):
        scheduler.add_job(
            run_admin_digest,
            "interval",
            minutes=digest_minutes,
            id="admin-registration-digest",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=max(60, digest_minutes * 60),
        )
        registered.append("admin-registration-digest")

    retention_days = env_int("RESULT_RETENTION_DAYS", 0)
    if retention_days < 0:
        raise ValueError("RESULT_RETENTION_DAYS must be zero or positive")
    if retention_days > 0:
        scheduler.add_job(
            run_result_cleanup,
            "interval",
            days=1,
            args=(retention_days,),
            id="result-retention-cleanup",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=86400,
            next_run_time=datetime.now(timezone.utc),
        )
        registered.append("result-retention-cleanup")

    return registered


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
