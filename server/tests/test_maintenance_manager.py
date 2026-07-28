# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import pytest

from pssm_gremlin_server.maintenance import manager
from pssm_gremlin_server.maintenance.tasks import admin_digest


class RecordingScheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append((func, trigger, kwargs))


def test_unset_maintenance_settings_register_no_jobs(monkeypatch):
    monkeypatch.delenv("ADMIN_NEW_USER_INFORM", raising=False)
    monkeypatch.delenv("ADMIN_NOTIFY_EMAIL", raising=False)
    monkeypatch.delenv("RESULT_RETENTION_DAYS", raising=False)
    scheduler = RecordingScheduler()

    assert manager.configure_jobs(scheduler) == []
    assert scheduler.jobs == []


def test_configure_jobs_registers_enabled_digest_and_cleanup(monkeypatch):
    monkeypatch.setenv("ADMIN_NEW_USER_INFORM", "15")
    monkeypatch.setenv("ADMIN_NOTIFY_EMAIL", "admin@example.com")
    monkeypatch.setenv("RESULT_RETENTION_DAYS", "30")
    scheduler = RecordingScheduler()

    assert manager.configure_jobs(scheduler) == [
        "admin-registration-digest",
        "result-retention-cleanup",
    ]

    digest_func, digest_trigger, digest_options = scheduler.jobs[0]
    assert digest_func is manager.run_admin_digest
    assert digest_trigger == "interval"
    assert digest_options["minutes"] == 15
    assert digest_options["coalesce"] is True
    assert digest_options["max_instances"] == 1

    cleanup_func, cleanup_trigger, cleanup_options = scheduler.jobs[1]
    assert cleanup_func is manager.run_result_cleanup
    assert cleanup_trigger == "interval"
    assert cleanup_options["days"] == 1
    assert cleanup_options["args"] == (30,)
    assert cleanup_options["next_run_time"] is not None
    assert cleanup_options["coalesce"] is True
    assert cleanup_options["max_instances"] == 1


def test_admin_digest_task_delegates_to_email_service(monkeypatch):
    monkeypatch.setattr(admin_digest, "send_admin_digest", lambda: True)

    assert admin_digest.run_admin_digest() is True


@pytest.mark.parametrize("name", ["ADMIN_NEW_USER_INFORM", "RESULT_RETENTION_DAYS"])
def test_negative_maintenance_interval_is_rejected(monkeypatch, name):
    monkeypatch.delenv("ADMIN_NEW_USER_INFORM", raising=False)
    monkeypatch.delenv("ADMIN_NOTIFY_EMAIL", raising=False)
    monkeypatch.delenv("RESULT_RETENTION_DAYS", raising=False)
    monkeypatch.setenv(name, "-1")

    with pytest.raises(ValueError, match=f"{name} must be zero or positive"):
        manager.configure_jobs(RecordingScheduler())
