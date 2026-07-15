# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import io
import json
import time
import uuid

import pytest
from conftest import (
    _admin_client_auth,
    _extract_md5,
    _insert_pending_task,
    _load_pssm_module,
    _test_client_auth,
    _upsert_task_for_user,
)

# Auth endpoint tests — /api/auth/me, API keys, password reset, etc.
# ==================================================================
# Race condition tests — TOCTOU and concurrent state manipulation
# ==================================================================


def test_race_cancel_finished_task_rejected(monkeypatch, tmp_path):
    """Cancelling an already-finished task returns 400 (TOCTOU after completion)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    db = module.task_store

    # Simulate task that finished while user was about to click cancel
    result_dir = tmp_path / "race_cancel"
    result_dir.mkdir(parents=True, exist_ok=True)
    md5sum = uuid.uuid4().hex
    fasta_path = result_dir / "seqs.fasta"
    fasta_path.write_text(">race\nACDE\n", encoding="utf-8")
    db.upsert_task(
        md5sum,
        filename="seqs.fasta",
        file_path=str(fasta_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        status="finished",
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username="tester",
    )
    resp = client.post(f"/PSSM_GREMLIN/api/cancel/{md5sum}", headers=auth_header)
    assert resp.status_code == 400
    assert "not pending or running" in resp.json["error"]


def test_race_cancel_already_cancelled_task(monkeypatch, tmp_path):
    """Re-cancelling a cancelled task returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    db = module.task_store

    result_dir = tmp_path / "race_recancel"
    result_dir.mkdir(parents=True, exist_ok=True)
    md5sum = uuid.uuid4().hex
    fasta_path = result_dir / "seqs.fasta"
    fasta_path.write_text(">race\nACDE\n", encoding="utf-8")
    db.upsert_task(
        md5sum,
        filename="seqs.fasta",
        file_path=str(fasta_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        status="cancelled",
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username="tester",
    )
    resp = client.post(f"/PSSM_GREMLIN/api/cancel/{md5sum}", headers=auth_header)
    assert resp.status_code == 400
    assert "not pending or running" in resp.json["error"]


def test_race_delete_already_cancelled_task(monkeypatch, tmp_path):
    """Deleting a cancelled task succeeds (cleanup is idempotent)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    db = module.task_store

    result_dir = tmp_path / "race_del_cancelled"
    result_dir.mkdir(parents=True, exist_ok=True)
    md5sum = uuid.uuid4().hex
    fasta_path = result_dir / "seqs.fasta"
    fasta_path.write_text(">race\nACDE\n", encoding="utf-8")
    db.upsert_task(
        md5sum,
        filename="seqs.fasta",
        file_path=str(fasta_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        status="cancelled",
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username="tester",
    )
    resp = client.delete(f"/PSSM_GREMLIN/api/delete/{md5sum}", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json["status"] == "deleted"


def test_race_upload_dedup_race_condition(monkeypatch, tmp_path):
    """Two rapid uploads with identical content get proper dedup."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *a, **kw: _DummyAsyncResult())

    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    content = b">same\nACDEFGHIKLMNPQRSTVWY\n"

    # First upload
    r1 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(content), "same.fasta")},
        headers=auth_header,
    )
    assert r1.status_code == 302
    # Second upload — same content, no delay
    r2 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(content), "same.fasta")},
        headers=auth_header,
    )
    # Already queued → 202 dedup
    assert r2.status_code == 202
    assert r2.json["status"] == "Task already queued or running"


def test_race_token_usage_after_concurrent_logout(monkeypatch, tmp_path):
    """Token used in a race with logout — token still valid (no server invalidation)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    _test_client_auth(module)
    # Get token
    login = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester", "password": "password"}),
    )
    token = login.json["token"]
    # Logout (clears cookie, doesn't revoke token)
    client.post("/PSSM_GREMLIN/api/auth/logout")
    # Token still works
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json["username"] == "tester"


def test_race_status_polling_during_task_transition(monkeypatch, tmp_path):
    """Polling GET /api/running during status transitions returns consistent state."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    db = module.task_store

    result_dir = tmp_path / "poll_race"
    result_dir.mkdir(parents=True, exist_ok=True)
    md5sum = uuid.uuid4().hex
    fasta_path = result_dir / "s.fasta"
    fasta_path.write_text(">x\nACDE\n", encoding="utf-8")

    # Simulate rapid polling across status transitions
    transitions = ["pending", "running", "packing results", "finished"]
    for status in transitions:
        db.upsert_task(
            md5sum,
            filename="s.fasta",
            file_path=str(fasta_path),
            result_dir=str(result_dir),
            uploaded_at=time.time(),
            status=status,
            is_binary=0,
            source_ip="127.0.0.1",
            user_agent="pytest",
            username="tester",
        )
        resp = client.get(f"/PSSM_GREMLIN/api/running/{md5sum}", headers=auth_header)
        valid_statuses = {200, 202}
        assert resp.status_code in valid_statuses, f"Status {status}: got {resp.status_code}"


def test_race_batch_delete_duplicate_ids(monkeypatch, tmp_path):
    """Batch delete with duplicate task IDs handles dedup correctly."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    db = module.task_store

    result_dir = tmp_path / "dedup_race"
    result_dir.mkdir(parents=True, exist_ok=True)
    md5sum = uuid.uuid4().hex
    fasta_path = result_dir / "s.fasta"
    fasta_path.write_text(">x\nACDE\n", encoding="utf-8")
    db.upsert_task(
        md5sum,
        filename="s.fasta",
        file_path=str(fasta_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        status="cancelled",
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username="tester",
    )
    # Send the same md5sum 3 times
    resp = client.post(
        "/PSSM_GREMLIN/api/delete",
        headers={**auth_header, "Content-Type": "application/json"},
        data=json.dumps({"md5sums": [md5sum, md5sum, md5sum]}),
    )
    assert resp.status_code == 200
    assert len(resp.json["deleted"]) == 1


def test_race_batch_delete_with_nonexistent_and_duplicate(monkeypatch, tmp_path):
    """Batch delete with mix of valid, invalid, duplicate, and nonexistent IDs."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    db = module.task_store

    result_dir = tmp_path / "mixed_race"
    result_dir.mkdir(parents=True, exist_ok=True)
    valid_md5 = uuid.uuid4().hex
    another_md5 = uuid.uuid4().hex
    fasta_path = result_dir / "s.fasta"
    fasta_path.write_text(">x\nACDE\n", encoding="utf-8")
    for md5 in (valid_md5, another_md5):
        db.upsert_task(
            md5,
            filename="s.fasta",
            file_path=str(fasta_path),
            result_dir=str(result_dir),
            uploaded_at=time.time(),
            status="cancelled",
            is_binary=0,
            source_ip="127.0.0.1",
            user_agent="pytest",
            username="tester",
        )

    nonexistent = "0" * 32
    resp = client.post(
        "/PSSM_GREMLIN/api/delete",
        headers={**auth_header, "Content-Type": "application/json"},
        data=json.dumps({"md5sums": [valid_md5, nonexistent, valid_md5, another_md5]}),
    )
    assert resp.status_code == 200
    result = resp.json
    assert valid_md5 in result["deleted"]
    assert another_md5 in result["deleted"]
    assert nonexistent in result["not_found"]
    assert len(result["deleted"]) == 2


def test_race_cancel_concurrent_with_worker_completion(monkeypatch, tmp_path):
    """Cancel while worker completes — DB terminal-status guard prevents resurrection."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.task_store

    result_dir = tmp_path / "worker_race"
    result_dir.mkdir(parents=True, exist_ok=True)
    md5sum = uuid.uuid4().hex
    fasta_path = result_dir / "s.fasta"
    fasta_path.write_text(">x\nACDE\n", encoding="utf-8")
    db.upsert_task(
        md5sum,
        filename="s.fasta",
        file_path=str(fasta_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        status="cancelled",
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username="tester",
    )
    # Simulate worker trying to write "finished" after user cancelled
    db.update_task(md5sum, status="finished", error=None)
    task = db.get_task(md5sum)
    # Terminal status guard: cancelled tasks stay cancelled
    assert task["status"] == "cancelled", f"Task resurrected to {task['status']}"


def test_race_status_polling_on_deleted_task(monkeypatch, tmp_path):
    """Polling a deleted task returns the correct deleted status."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    db = module.task_store

    result_dir = tmp_path / "deleted_poll"
    result_dir.mkdir(parents=True, exist_ok=True)
    md5sum = uuid.uuid4().hex
    # Covers both delete-status variants
    for d_status in ("deleted:cancel", "deleted:finshed"):
        fasta_path = result_dir / f"{d_status.replace(':', '_')}.fasta"
        fasta_path.write_text(">x\nACDE\n", encoding="utf-8")
        db.upsert_task(
            md5sum,
            filename="s.fasta",
            file_path=str(fasta_path),
            result_dir=str(result_dir),
            uploaded_at=time.time(),
            status=d_status,
            is_binary=0,
            source_ip="127.0.0.1",
            user_agent="pytest",
            username="tester",
        )
        resp = client.get(f"/PSSM_GREMLIN/api/running/{md5sum}", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json
        assert data["md5sum"] == md5sum


