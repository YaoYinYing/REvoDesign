# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Self-configuring periodic maintenance task objects."""

from revocompute.maintenance.tasks.admin_digest import admin_digest_task
from revocompute.maintenance.tasks.database_backup import database_backup_task
from revocompute.maintenance.tasks.result_cleanup import result_cleanup_task

__all__ = ["admin_digest_task", "database_backup_task", "result_cleanup_task"]
