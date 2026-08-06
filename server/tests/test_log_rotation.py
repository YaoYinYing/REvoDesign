# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import os
import threading
import time
import zipfile

import pytest
from revocompute.maintenance.tasks import log_rotation as log_rotation_module
from revocompute.maintenance.tasks.log_rotation import log_rotation_task, rotate_logs


def test_line_threshold_rotates_to_zip_and_truncates_live_log(tmp_path):
    log = tmp_path / "worker.log"
    content = "one\ntwo\nthree\n"
    log.write_text(content, encoding="utf-8")

    assert rotate_logs(str(tmp_path), 2, False, None, now=1_000_000) == 1

    archives = list(tmp_path.glob("worker.log.*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as bundle:
        assert bundle.read("worker.log").decode() == content
    assert log.read_text(encoding="utf-8") == ""


def test_scheduled_period_rotates_nonempty_logs(tmp_path):
    log = tmp_path / "maintenance.log"
    log.write_text("entry\n", encoding="utf-8")

    assert rotate_logs(str(tmp_path), None, True, None, now=1_000_000) == 1


def test_rotation_passes_are_serialized_across_scheduler_jobs(monkeypatch, tmp_path):
    active = 0
    max_active = 0
    state_lock = threading.Lock()
    start = threading.Barrier(3)

    def recording_rotation(*_args, **_kwargs):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with state_lock:
            active -= 1
        return 0

    monkeypatch.setattr(log_rotation_module, "_rotate_logs", recording_rotation)

    def run_rotation():
        start.wait()
        rotate_logs(str(tmp_path), 1, False, None)

    threads = [threading.Thread(target=run_rotation) for _ in range(2)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert max_active == 1


def test_size_cap_removes_oldest_archive_before_touching_live_log(tmp_path):
    log = tmp_path / "web.log"
    log.write_bytes(b"x" * 300_000)
    oldest = tmp_path / "web.log.old.zip"
    newest = tmp_path / "web.log.new.zip"
    oldest.write_bytes(b"a" * 400_000)
    newest.write_bytes(b"b" * 400_000)
    os.utime(oldest, (1, 1))
    os.utime(newest, (2, 2))

    assert rotate_logs(str(tmp_path), None, False, 800_000, now=3) == 0

    assert not oldest.exists()
    assert newest.exists()
    assert log.stat().st_size == 300_000


def test_size_cap_rotates_live_log_when_archives_cannot_reduce_total(tmp_path):
    log = tmp_path / "web.log"
    content = os.urandom(2 * 1024**2)
    log.write_bytes(content)

    assert rotate_logs(str(tmp_path), None, False, 1024**2, now=3) == 1

    archives = list(tmp_path.glob("web.log.*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as bundle:
        assert bundle.read("web.log") == content
    assert log.stat().st_size == 0


def test_size_rotation_stops_after_total_falls_below_cap(tmp_path):
    large = tmp_path / "a.log"
    untouched = tmp_path / "b.log"
    large.write_bytes(b"x" * (2 * 1024**2))
    untouched.write_text("keep me\n", encoding="utf-8")

    assert rotate_logs(str(tmp_path), None, False, 1024**2, now=3) == 1

    assert large.stat().st_size == 0
    assert untouched.read_text(encoding="utf-8") == "keep me\n"
    assert not list(tmp_path.glob("b.log.*.zip"))


def test_log_rotation_task_configures_all_triggers(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("ROTATE_LOG_MAX_LINENO", "1000")
    monkeypatch.setenv("ROTATE_LOG_PERIOD", "0 0 * * *")
    monkeypatch.setenv("MAX_LOG_SIZE", "512.5M")

    log_rotation_task.configure()

    assert log_rotation_task.is_enabled is True
    assert log_rotation_task.env == {
        "ROTATE_LOG_MAX_LINENO": 1000,
        "ROTATE_LOG_PERIOD": "0 0 * * *",
        "MAX_LOG_SIZE": int(512.5 * 1024**2),
        "LOG_DIR": str(tmp_path),
    }
    assert log_rotation_task.args["trigger"].timezone is not None
    assert log_rotation_task.args["args"] == (
        str(tmp_path),
        None,
        True,
        int(512.5 * 1024**2),
    )


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("ROTATE_LOG_MAX_LINENO", "0", "must be a positive integer"),
        ("ROTATE_LOG_PERIOD", "not a cron", "Wrong number of fields"),
        ("MAX_LOG_SIZE", "0", "must be positive"),
    ],
)
def test_log_rotation_rejects_non_positive_settings(monkeypatch, name, value, message):
    for setting in ("ROTATE_LOG_MAX_LINENO", "ROTATE_LOG_PERIOD", "MAX_LOG_SIZE"):
        monkeypatch.delenv(setting, raising=False)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        log_rotation_task.configure()
