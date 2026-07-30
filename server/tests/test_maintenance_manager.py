# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

import pytest
from pssm_gremlin_server.maintenance import manager
from pssm_gremlin_server.maintenance.model import PeriodicTask
from pssm_gremlin_server.maintenance.tasks import admin_digest
from pssm_gremlin_server.maintenance.tasks.admin_digest import admin_digest_task
from pssm_gremlin_server.maintenance.tasks.database_backup import database_backup_task
from pssm_gremlin_server.maintenance.tasks.log_rotation import log_rotation_task
from pssm_gremlin_server.maintenance.tasks.result_cleanup import result_cleanup_task


class RecordingScheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append((func, trigger, kwargs))


@pytest.fixture(autouse=True)
def _clear_log_rotation_settings(monkeypatch):
    for name in ("ROTATE_LOG_MAX_LINENO", "ROTATE_LOG_PERIOD", "MAX_LOG_SIZE"):
        monkeypatch.delenv(name, raising=False)


def test_configure_logging_writes_maintenance_log(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    logger = logging.getLogger(f"maintenance-test-{id(tmp_path)}")
    logger.propagate = False

    try:
        log_path = manager.configure_logging(logger=logger)
        logger.info("maintenance log test")
        for handler in logger.handlers:
            handler.flush()

        assert log_path == str(tmp_path / "maintenance.log")
        assert "maintenance log test" in (tmp_path / "maintenance.log").read_text(encoding="utf-8")
    finally:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)


def test_unset_maintenance_settings_register_no_jobs(monkeypatch):
    monkeypatch.delenv("ADMIN_NEW_USER_INFORM", raising=False)
    monkeypatch.delenv("ADMIN_NOTIFY_EMAIL", raising=False)
    monkeypatch.delenv("RESULT_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("BACKUP_DB_CRON", raising=False)
    monkeypatch.delenv("BACKUP_DB_PATH", raising=False)
    monkeypatch.delenv("MAX_DB_BACKUP", raising=False)
    scheduler = RecordingScheduler()

    assert manager.configure_jobs(scheduler) == []
    assert scheduler.jobs == []


def test_configure_jobs_registers_enabled_digest_and_cleanup(monkeypatch):
    monkeypatch.setenv("ADMIN_NEW_USER_INFORM", "15")
    monkeypatch.setenv("ADMIN_NOTIFY_EMAIL", "admin@example.com")
    monkeypatch.setenv("RESULT_RETENTION_DAYS", "30")
    monkeypatch.delenv("BACKUP_DB_CRON", raising=False)
    monkeypatch.delenv("BACKUP_DB_PATH", raising=False)
    monkeypatch.delenv("MAX_DB_BACKUP", raising=False)
    scheduler = RecordingScheduler()

    assert manager.configure_jobs(scheduler) == [
        "admin-registration-digest",
        "result-retention-cleanup",
    ]

    digest_func, digest_trigger, digest_options = scheduler.jobs[0]
    assert digest_func is admin_digest_task.task_method
    assert digest_trigger == "interval"
    assert digest_options["minutes"] == 15
    assert digest_options["id"] == admin_digest_task.id
    assert digest_options["coalesce"] is True
    assert digest_options["max_instances"] == 1
    assert admin_digest_task.is_enabled is True
    assert admin_digest_task.env == {
        "ADMIN_NEW_USER_INFORM": 15,
        "ADMIN_NOTIFY_EMAIL": "admin@example.com",
    }

    cleanup_func, cleanup_trigger, cleanup_options = scheduler.jobs[1]
    assert cleanup_func is result_cleanup_task.task_method
    assert cleanup_trigger == "interval"
    assert cleanup_options["days"] == 1
    assert cleanup_options["args"] == (30,)
    assert cleanup_options["id"] == result_cleanup_task.id
    assert cleanup_options["next_run_time"] is not None
    assert cleanup_options["coalesce"] is True
    assert cleanup_options["max_instances"] == 1
    assert result_cleanup_task.is_enabled is True
    assert result_cleanup_task.env == {"RESULT_RETENTION_DAYS": 30}


def test_result_cleanup_accepts_fractional_retention_days(monkeypatch):
    monkeypatch.delenv("ADMIN_NEW_USER_INFORM", raising=False)
    monkeypatch.delenv("ADMIN_NOTIFY_EMAIL", raising=False)
    monkeypatch.setenv("RESULT_RETENTION_DAYS", "0.1")
    monkeypatch.delenv("BACKUP_DB_CRON", raising=False)
    scheduler = RecordingScheduler()

    assert manager.configure_jobs(scheduler) == ["result-retention-cleanup"]
    _, trigger, options = scheduler.jobs[0]
    assert trigger == "interval"
    assert options["args"] == pytest.approx((0.1,))
    assert result_cleanup_task.env["RESULT_RETENTION_DAYS"] == pytest.approx(0.1)


def test_configure_jobs_registers_database_backup_cron(monkeypatch, tmp_path):
    monkeypatch.delenv("ADMIN_NEW_USER_INFORM", raising=False)
    monkeypatch.delenv("ADMIN_NOTIFY_EMAIL", raising=False)
    monkeypatch.delenv("RESULT_RETENTION_DAYS", raising=False)
    monkeypatch.setenv("BACKUP_DB_CRON", "0 0 * * *")
    monkeypatch.setenv("BACKUP_DB_PATH", str(tmp_path / "backups"))
    monkeypatch.setenv("MAX_DB_BACKUP", "30")
    monkeypatch.setenv("TZ", "UTC")
    scheduler = RecordingScheduler()

    assert manager.configure_jobs(scheduler) == ["database-backup"]

    backup_func, backup_trigger, backup_options = scheduler.jobs[0]
    assert backup_func is database_backup_task.task_method
    assert backup_trigger is database_backup_task.args["trigger"]
    assert backup_options["args"] == (str(tmp_path / "backups"), 30)
    assert backup_options["id"] == database_backup_task.id
    assert backup_options["coalesce"] is True
    assert backup_options["max_instances"] == 1
    assert database_backup_task.is_enabled is True
    assert database_backup_task.env == {
        "BACKUP_DB_CRON": "0 0 * * *",
        "BACKUP_DB_PATH": str(tmp_path / "backups"),
        "MAX_DB_BACKUP": 30,
    }


def test_configure_jobs_registers_log_rotation(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("ROTATE_LOG_MAX_LINENO", "1000")
    monkeypatch.setenv("ROTATE_LOG_PERIOD", "0 0 * * *")
    scheduler = RecordingScheduler()

    assert manager.configure_jobs(scheduler) == ["log-rotation"]

    assert len(scheduler.jobs) == 2
    threshold_func, threshold_trigger, threshold_options = scheduler.jobs[0]
    assert threshold_func is log_rotation_task.task_method
    assert threshold_trigger == "interval"
    assert threshold_options["hours"] == 1
    assert threshold_options["args"] == (str(tmp_path), 1000, False, None)
    assert threshold_options["id"] == "log-rotation-thresholds"

    task_func, trigger, options = scheduler.jobs[1]
    assert task_func is log_rotation_task.task_method
    assert trigger is log_rotation_task.args["trigger"]
    assert options["args"] == (str(tmp_path), None, True, None)
    assert options["id"] == log_rotation_task.id


def test_database_backup_retention_is_unlimited_when_unset(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKUP_DB_CRON", "0 0 * * *")
    monkeypatch.setenv("BACKUP_DB_PATH", str(tmp_path / "backups"))
    monkeypatch.delenv("MAX_DB_BACKUP", raising=False)

    database_backup_task.configure()

    assert database_backup_task.is_enabled is True
    assert database_backup_task.env["MAX_DB_BACKUP"] is None
    assert database_backup_task.args["args"] == (str(tmp_path / "backups"), None)


def test_database_backup_ignores_other_settings_when_cron_is_unset(monkeypatch):
    monkeypatch.delenv("BACKUP_DB_CRON", raising=False)
    monkeypatch.setenv("BACKUP_DB_PATH", "/unused")
    monkeypatch.setenv("MAX_DB_BACKUP", "not-an-integer")

    database_backup_task.configure()

    assert database_backup_task.is_enabled is False
    assert database_backup_task.args == {}


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"BACKUP_DB_CRON": "0 0 * * *"}, "BACKUP_DB_PATH is required"),
        (
            {"BACKUP_DB_CRON": "not a cron", "BACKUP_DB_PATH": "/tmp/backups"},
            "Wrong number of fields",
        ),
        (
            {"BACKUP_DB_CRON": "0 0 * * *", "BACKUP_DB_PATH": "/tmp/backups", "MAX_DB_BACKUP": "0"},
            "MAX_DB_BACKUP must be a positive integer",
        ),
    ],
)
def test_database_backup_configuration_rejects_invalid_values(monkeypatch, env, message):
    monkeypatch.delenv("BACKUP_DB_CRON", raising=False)
    monkeypatch.delenv("BACKUP_DB_PATH", raising=False)
    monkeypatch.delenv("MAX_DB_BACKUP", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        database_backup_task.configure()


def test_admin_digest_task_delegates_to_email_service(monkeypatch):
    monkeypatch.setattr(admin_digest, "send_admin_digest", lambda: True)

    assert admin_digest.run_admin_digest() is True


def test_task_register_reconfigures_from_current_environment(monkeypatch):
    monkeypatch.setenv("ADMIN_NEW_USER_INFORM", "15")
    monkeypatch.setenv("ADMIN_NOTIFY_EMAIL", "admin@example.com")
    scheduler = RecordingScheduler()

    assert admin_digest_task.register(scheduler) is True

    monkeypatch.delenv("ADMIN_NEW_USER_INFORM")
    assert admin_digest_task.register(scheduler) is False
    assert admin_digest_task.is_enabled is False
    assert admin_digest_task.args == {}
    assert len(scheduler.jobs) == 1


def test_manager_uses_periodic_task_register_interface():
    calls = []

    class StubTask(PeriodicTask):
        id = "stub-task"

        @property
        def task_method(self):
            return lambda: None

        def configure(self):
            raise AssertionError("manager must delegate configuration to register")

        def register(self, scheduler):
            calls.append(scheduler)
            return True

    scheduler = RecordingScheduler()

    assert manager.configure_jobs(scheduler, (StubTask(),)) == ["stub-task"]
    assert calls == [scheduler]


@pytest.mark.parametrize("name", ["ADMIN_NEW_USER_INFORM", "RESULT_RETENTION_DAYS"])
def test_negative_maintenance_interval_is_rejected(monkeypatch, name):
    monkeypatch.delenv("ADMIN_NEW_USER_INFORM", raising=False)
    monkeypatch.delenv("ADMIN_NOTIFY_EMAIL", raising=False)
    monkeypatch.delenv("RESULT_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("BACKUP_DB_CRON", raising=False)
    monkeypatch.delenv("BACKUP_DB_PATH", raising=False)
    monkeypatch.delenv("MAX_DB_BACKUP", raising=False)
    monkeypatch.setenv(name, "-1")

    with pytest.raises(ValueError, match=f"{name} must be zero or positive"):
        manager.configure_jobs(RecordingScheduler())
