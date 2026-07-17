# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import io
import json
import os
import time
import uuid
import zipfile
from pathlib import Path

import docker
import pytest
from conftest import (
    _admin_client_auth,
    _extract_md5,
    _insert_pending_task,
    _load_pssm_module,
    _test_client_auth,
    _upsert_task_for_user,
)
from werkzeug.utils import secure_filename

# Flask test-client tests
# ==================================================================


def test_server_exposes_local_favicon_assets(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert "image" in (favicon.content_type or "")

    logo_svg = client.get("/PSSM_GREMLIN/logo.svg")
    assert logo_svg.status_code == 200
    assert "svg" in (logo_svg.content_type or "")

    page = client.get("/PSSM_GREMLIN/create_task", headers=auth_header)
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'href="/favicon.ico"' in html
    assert 'href="/PSSM_GREMLIN/logo.svg"' in html
    assert 'class="btn btn-soft theme-toggle mode-auto"' in html
    assert 'class="theme-icon" aria-hidden="true">◐</span>' in html
    assert 'src="/static/js/theme.js"' in html
    assert 'type="file" name="file" id="fileInput" accept=".fasta" class="sr-only"' in html
    assert 'id="fileButton"' in html
    assert "file-input-offscreen" not in html


def _insert_pending_task(module, result_dir: Path, filename: str = "input.fasta") -> str:
    result_dir.mkdir(parents=True, exist_ok=True)
    fasta_path = result_dir / filename
    fasta_path.write_text(">test\nACDE\n", encoding="utf-8")
    md5sum = uuid.uuid4().hex
    module.task_store.upsert_task(
        md5sum,
        filename=filename,
        file_path=str(fasta_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        status="pending",
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username="tester",
    )
    return md5sum


def test_run_gremlin_task_handles_docker_daemon_error(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    md5sum = _insert_pending_task(module, tmp_path / "result")

    def _raise_docker_error(*, fasta_path, output_dir, stage_callback=None):
        del fasta_path, output_dir
        del stage_callback
        raise docker.errors.DockerException(
            "Error while fetching server API version: ('Connection aborted.', PermissionError(13, 'Permission denied'))"
        )

    monkeypatch.setattr(module, "run_pssm_gremlin_in_docker", _raise_docker_error)

    module.run_gremlin_task(md5sum)
    task = module.task_store.get_task(md5sum)

    assert task is not None
    assert task["status"] == "failed"
    assert task["error"].startswith("docker:")
    assert "Permission denied" in task["error"]

    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_PSSM_GREMLIN_results.zip"
    assert zip_path.is_file()
    assert not Path(task["result_dir"]).exists()
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        failure_report = archive.read("task_failed.txt").decode("utf-8")
    assert any(name.endswith("input.fasta") for name in names)
    assert "Permission denied" in failure_report


def test_run_pssm_gremlin_in_docker_limits_thread_env(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "NPROC": "4",
            "MAXMEM": "96",
        },
    )
    input_fasta = tmp_path / "input.fasta"
    input_fasta.write_text(">test\nACDE\n", encoding="utf-8")
    output_dir = tmp_path / "result"
    output_dir.mkdir(parents=True, exist_ok=True)

    captured_kwargs: dict[str, object] = {}

    class _DummyContainer:
        def logs(self, stream=False):
            del stream
            return []

        def wait(self):
            return {"StatusCode": 0}

        def remove(self, force=False):
            del force
            return None

    class _DummyContainers:
        def run(self, **kwargs):
            captured_kwargs.update(kwargs)
            return _DummyContainer()

    class _DummyDockerClient:
        containers = _DummyContainers()

    monkeypatch.setattr(module.docker, "from_env", lambda: _DummyDockerClient())
    monkeypatch.setattr(module.signal, "signal", lambda *_args, **_kwargs: None)

    module.run_pssm_gremlin_in_docker(
        fasta_path=str(input_fasta),
        output_dir=str(output_dir),
    )

    environment = captured_kwargs["environment"]
    assert isinstance(environment, dict)
    expected_values = {
        "GREMLIN_CALC_CPU_NUM": "4",
        "OMP_NUM_THREADS": "4",
        "OPENBLAS_NUM_THREADS": "4",
        "MKL_NUM_THREADS": "4",
        "VECLIB_MAXIMUM_THREADS": "4",
        "NUMEXPR_NUM_THREADS": "4",
        "TF_NUM_INTRAOP_THREADS": "4",
        "TF_NUM_INTEROP_THREADS": "4",
        "OMP_DYNAMIC": "FALSE",
        "MKL_DYNAMIC": "FALSE",
        "MAXMEM": "96",
    }
    for key, value in expected_values.items():
        assert environment.get(key) == value


def test_run_gremlin_task_packs_results_and_cleans_result_dir(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    md5sum = _insert_pending_task(module, tmp_path / "result")
    observed_statuses: list[str] = []
    original_update_task = module.task_store.update_task

    def _track_update(md5_value: str, **fields):
        if "status" in fields:
            observed_statuses.append(fields["status"])
        return original_update_task(md5_value, **fields)

    def _fake_runner(*, fasta_path, output_dir, stage_callback=None):
        del fasta_path
        if stage_callback:
            stage_callback("hhblits")
            stage_callback("hhfilter")
            stage_callback("gremlin")
            stage_callback("blast")
        output_path = Path(output_dir)
        (output_path / "log").mkdir(parents=True, exist_ok=True)
        (output_path / "log" / "task_finished").write_text("done\n", encoding="utf-8")
        (output_path / "pssm_msa").mkdir(parents=True, exist_ok=True)
        (output_path / "pssm_msa" / "input_ascii_mtx_file").write_text("pssm\n", encoding="utf-8")

    monkeypatch.setattr(module.task_store, "update_task", _track_update)
    monkeypatch.setattr(module, "run_pssm_gremlin_in_docker", _fake_runner)
    monkeypatch.setattr(module, "_local_user_identity", lambda: "pytest:staff-1000:20")

    module.run_gremlin_task(md5sum)

    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "finished"
    assert task["local_user"] == "pytest:staff-1000:20"
    assert task["run_stage"] == "blast"
    assert not Path(task["result_dir"]).exists()

    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_PSSM_GREMLIN_results.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert any(name.endswith("log/task_finished") for name in names)
    assert any(name.endswith("pssm_msa/input_ascii_mtx_file") for name in names)

    assert "running" in observed_statuses
    assert "packing results" in observed_statuses
    assert "finished" in observed_statuses
    assert observed_statuses.index("running") < observed_statuses.index("packing results")
    assert observed_statuses.index("packing results") < observed_statuses.index("finished")


def test_task_store_update_ignores_late_non_deleted_updates(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    md5sum = _insert_pending_task(module, tmp_path / "result")
    deleted_at = time.time()
    module.task_store.update_task(
        md5sum,
        status="deleted:cancel",
        finished_at=deleted_at,
        error="Task deleted by user",
    )

    # Simulate stale worker writes arriving after a delete request.
    module.task_store.update_task(md5sum, status="packing results", run_stage="blast")
    module.task_store.update_task(md5sum, status="finished", walltime=12.3, error=None)
    module.task_store.update_task(md5sum, run_stage="hhblits")

    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:cancel"
    assert task["error"] == "Task deleted by user"
    assert task["finished_at"] == deleted_at


def test_run_gremlin_task_does_not_resurrect_deleted_task(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    md5sum = _insert_pending_task(module, tmp_path / "result")
    observed_statuses: list[str] = []
    original_update_task = module.task_store.update_task

    def _track_update(md5_value: str, **fields):
        if "status" in fields:
            observed_statuses.append(fields["status"])
        return original_update_task(md5_value, **fields)

    def _fake_runner(*, fasta_path, output_dir, stage_callback=None):
        del fasta_path
        if stage_callback:
            stage_callback("blast")
        output_path = Path(output_dir)
        (output_path / "log").mkdir(parents=True, exist_ok=True)
        (output_path / "log" / "task_finished").write_text("done\n", encoding="utf-8")
        original_update_task(
            md5sum,
            status="deleted:cancel",
            finished_at=time.time(),
            walltime=0.1,
            error="Task deleted by user",
            celery_task_id=None,
        )
        task = module.task_store.get_task(md5sum)
        assert task is not None
        module._delete_task_artifacts(task)

    monkeypatch.setattr(module.task_store, "update_task", _track_update)
    monkeypatch.setattr(module, "run_pssm_gremlin_in_docker", _fake_runner)
    monkeypatch.setattr(module, "_local_user_identity", lambda: "pytest:staff-1000:20")

    module.run_gremlin_task(md5sum)

    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:cancel"
    assert "packing results" not in observed_statuses
    assert "finished" not in observed_statuses
    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_PSSM_GREMLIN_results.zip"
    assert not zip_path.exists()


def test_delete_task_artifacts_skips_paths_outside_results_folder(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    md5sum = uuid.uuid4().hex
    external_result_dir = tmp_path / "legacy_external_results"
    external_result_dir.mkdir(parents=True, exist_ok=True)
    (external_result_dir / "artifact.txt").write_text("payload\n", encoding="utf-8")

    module._delete_task_artifacts(
        {
            "md5sum": md5sum,
            "result_dir": str(external_result_dir),
        }
    )

    assert external_result_dir.exists()


def test_upload_records_headers_and_local_user(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    monkeypatch.setattr(module.routes, "_local_user_identity", lambda: "pytest:staff-1000:20")

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    headers = _test_client_auth(module)
    headers["X-Test-Header"] = "abc\tdef"
    response = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.fasta")},
        headers=headers,
    )
    assert response.status_code == 302
    md5sum = _extract_md5(response.headers["Location"])
    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "pending"
    assert task["local_user"] == "pytest:staff-1000:20"
    assert task["celery_task_id"] == "celery-test-id"

    headers = json.loads(task["request_headers"])
    assert headers["X-Test-Header"] == "abc def"
    assert "\n" not in task["request_headers"]
    assert "\r" not in task["request_headers"]


def _bearer_headers(base_url: str, username: str, password: str) -> dict[str, str]:
    """Log in via the token endpoint and return a Bearer authorization header."""
    resp = requests.post(
        f"{base_url}/PSSM_GREMLIN/api/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    if resp.status_code != 200:
        raise AssertionError(f"Login failed ({resp.status_code}): {resp.text}")
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _inject_admin_password(db_path: str, username: str, password: str) -> None:
    """Replace the auto-generated admin password with a known one.

    The server bootstraps an admin with a random password on first run.
    This overwrites the hash so tests can authenticate with Bearer headers.
    """
    import sqlite3

    from werkzeug.security import generate_password_hash

    _hash = generate_password_hash(password)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (_hash, username))
    conn.commit()
    conn.close()


def _test_client_auth(module, username: str = "tester", password: str = "password") -> dict[str, str]:
    """Create a test user and return Bearer token headers for Flask test-client tests.

    Unlike :func:`_bearer_headers`, this works without a running HTTP server —
    it creates the user directly in the DB and generates a token locally.
    """
    db = module.app.config["user_db"]
    user = db.get_user_by_username(username)
    if not user:
        user = db.create_user(
            username=username,
            email=f"{username}@test.local",
            password=password,
            user_status="active",
            registration_status="approved",
        )
        db.verify_email(user["id"])
    from pssm_gremlin_server.auth import generate_token

    return {"Authorization": f"Bearer {generate_token(user['id'])}"}


def _upsert_task_for_user(
    module,
    md5sum: str,
    *,
    filename: str,
    file_path: Path | str,
    result_dir: Path | str,
    username: str,
    status: str = "finished",
    run_stage: str | None = None,
) -> None:
    module.task_store.upsert_task(
        md5sum,
        filename=filename,
        file_path=str(file_path),
        result_dir=str(result_dir),
        uploaded_at=time.time(),
        started_at=time.time(),
        finished_at=time.time(),
        walltime=1.0,
        status=status,
        is_binary=0,
        source_ip="127.0.0.1",
        user_agent="pytest",
        username=username,
        run_stage=run_stage,
    )


def test_dashboard_masks_host_file_paths_on_read_errors(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    leaked_host_path = "/home/server-user/REvoDesign/playground/server_test/upload/2KL8.fasta"

    _upsert_task_for_user(
        module,
        md5sum,
        filename="2KL8.fasta",
        file_path=leaked_host_path,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.get("/PSSM_GREMLIN/dashboard", headers=auth_header)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "00:00:01" in body
    assert 'id="logoutBtn"' in body
    assert 'href="https://github.com/YaoYinYing/REvoDesign" target="_blank"' not in body


def test_failed_status_masks_host_paths_in_api_error(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    leaked_host_path = "/home/server-user/REvoDesign/playground/server_test/upload/2KL8.fasta"

    _upsert_task_for_user(
        module,
        md5sum,
        filename="2KL8.fasta",
        file_path=leaked_host_path,
        result_dir=result_dir,
        username="tester",
        status="failed",
    )
    module.task_store.update_task(
        md5sum,
        error=f"Unable to read sequence: [Errno 2] No such file or directory: '{leaked_host_path}'",
    )

    response = client.get(f"/PSSM_GREMLIN/api/running/{md5sum}", headers=auth_header)
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["status"] == "failed"
    assert "/srv/REvoDesign/PSSM_GREMLIN/upload/2KL8.fasta" in payload["error"]
    assert "/home/server-user/REvoDesign" not in payload["error"]


def test_private_dashboard_blocks_non_owner_access(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")

    upload = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.fasta")},
        headers=owner_header,
    )
    assert upload.status_code == 302
    md5sum = _extract_md5(upload.headers["Location"])

    owner_running = client.get(f"/PSSM_GREMLIN/api/running/{md5sum}", headers=owner_header)
    assert owner_running.status_code == 202
    assert owner_running.json["status"] == "pending"

    for route in ("running", "results", "download", "cancel"):
        method = client.post if route == "cancel" else client.get
        response = method(f"/PSSM_GREMLIN/api/{route}/{md5sum}", headers=other_header)
        assert response.status_code == 403
        assert response.json["status"] == "forbidden"

    owner_dashboard = client.get("/PSSM_GREMLIN/dashboard", headers=owner_header)
    other_dashboard = client.get("/PSSM_GREMLIN/dashboard", headers=other_header)
    assert owner_dashboard.status_code == 200
    assert other_dashboard.status_code == 200
    assert md5sum in owner_dashboard.get_data(as_text=True)
    assert md5sum not in other_dashboard.get_data(as_text=True)


def test_public_dashboard_allows_cross_user_task_access(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "PUBLIC_DASHBOARD": "true",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")

    upload = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.fasta")},
        headers=owner_header,
    )
    assert upload.status_code == 302
    md5sum = _extract_md5(upload.headers["Location"])

    other_running = client.get(f"/PSSM_GREMLIN/api/running/{md5sum}", headers=other_header)
    assert other_running.status_code == 202
    assert other_running.json["status"] == "pending"

    other_dashboard = client.get("/PSSM_GREMLIN/dashboard", headers=other_header)
    assert other_dashboard.status_code == 200
    assert md5sum in other_dashboard.get_data(as_text=True)


def test_dashboard_running_trace_reflects_log_progress(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "trace_result"
    result_dir.mkdir(parents=True, exist_ok=True)
    fasta_path = result_dir / "trace.fasta"
    fasta_path.write_text(">trace\nACDE\n", encoding="utf-8")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="trace.fasta",
        file_path=fasta_path,
        result_dir=result_dir,
        username="tester",
        status="running",
        run_stage="hhfilter",
    )

    response = client.get("/PSSM_GREMLIN/dashboard", headers=auth_header)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "hhblits: searching for co-evolutionary sequences [done]" in body
    assert "hhfilter: filtering co-evolutionary [running]" in body
    assert "gremlin: calculating co-evolution signals [pending]" in body
    assert "blast: searching for consensus profile [pending]" in body


def test_public_mode_scopes_task_id_by_user(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "PUBLIC_DASHBOARD": "true",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")

    owner_upload = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "same.fasta")},
        headers=owner_header,
    )
    assert owner_upload.status_code == 302
    owner_md5 = _extract_md5(owner_upload.headers["Location"])

    other_upload = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "same.fasta")},
        headers=other_header,
    )
    assert other_upload.status_code == 302
    other_md5 = _extract_md5(other_upload.headers["Location"])

    assert owner_md5 != other_md5


def test_admin_can_manage_other_users_tasks_in_private_mode(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin",
        },
    )
    client = module.app.test_client()
    admin_header = _test_client_auth(module, "admin", "admin_password")

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "admin_manage_other_user"
    result_dir.mkdir(parents=True, exist_ok=True)
    _upsert_task_for_user(
        module,
        md5sum,
        filename="owner.fasta",
        file_path=result_dir / "owner.fasta",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    running = client.get(f"/PSSM_GREMLIN/api/running/{md5sum}", headers=admin_header)
    assert running.status_code == 200
    assert running.json["status"] == "finished"

    results = client.get(f"/PSSM_GREMLIN/api/results/{md5sum}", headers=admin_header, follow_redirects=False)
    assert results.status_code == 302

    dashboard = client.get("/PSSM_GREMLIN/dashboard", headers=admin_header)
    assert dashboard.status_code == 200
    assert md5sum in dashboard.get_data(as_text=True)


def test_private_mode_scopes_task_id_by_user(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")

    payload = {"file": (io.BytesIO(b">test\nACDE\n"), "same.fasta")}
    owner_upload = client.post("/PSSM_GREMLIN/api/post", data=payload, headers=owner_header)
    assert owner_upload.status_code == 302
    owner_md5 = _extract_md5(owner_upload.headers["Location"])

    other_upload = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "same.fasta")},
        headers=other_header,
    )
    assert other_upload.status_code == 302
    other_md5 = _extract_md5(other_upload.headers["Location"])

    assert owner_md5 != other_md5


def test_owner_can_delete_own_task_results(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    client = module.app.test_client()
    owner_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    upload_dir = tmp_path / "upload_owner"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_file = upload_dir / "owner.fasta"
    upload_file.write_text(">owner\nACDE\n", encoding="utf-8")
    result_dir = Path(module.app.config["RESULTS_FOLDER"]) / "delete_owner"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "artifact.txt").write_text("payload\n", encoding="utf-8")
    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_PSSM_GREMLIN_results.zip"
    zip_path.write_bytes(b"zip")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="owner.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.delete(f"/PSSM_GREMLIN/api/delete/{md5sum}", headers=owner_header)
    assert response.status_code == 200
    assert response.json["status"] == "deleted"
    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:finshed"
    assert not result_dir.exists()
    assert not zip_path.exists()
    assert upload_file.exists()

    running = client.get(f"/PSSM_GREMLIN/api/running/{md5sum}", headers=owner_header)
    assert running.status_code == 200
    assert running.json["status"] == "deleted:finshed"


def test_dashboard_hides_deleted_tasks_until_resubmitted(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    upload_file = tmp_path / "deleted_hidden.fasta"
    upload_file.write_text(">hidden\nACDE\n", encoding="utf-8")
    result_dir = tmp_path / "deleted_hidden"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "artifact.txt").write_text("payload\n", encoding="utf-8")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="hidden.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="deleted:finshed",
    )

    hidden_dashboard = client.get("/PSSM_GREMLIN/dashboard", headers=auth_header)
    assert hidden_dashboard.status_code == 200
    assert md5sum not in hidden_dashboard.get_data(as_text=True)

    _upsert_task_for_user(
        module,
        md5sum,
        filename="hidden.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="pending",
    )

    visible_dashboard = client.get("/PSSM_GREMLIN/dashboard", headers=auth_header)
    assert visible_dashboard.status_code == 200
    assert md5sum in visible_dashboard.get_data(as_text=True)


def test_delete_pending_task_marks_deleted_cancel(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    owner_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    upload_file = tmp_path / "upload_pending.fasta"
    upload_file.write_text(">pending\nACDE\n", encoding="utf-8")
    result_dir = Path(module.app.config["RESULTS_FOLDER"]) / "delete_pending"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "artifact.txt").write_text("payload\n", encoding="utf-8")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="pending.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="pending",
    )

    response = client.delete(f"/PSSM_GREMLIN/api/delete/{md5sum}", headers=owner_header)
    assert response.status_code == 200
    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:cancel"
    assert not result_dir.exists()
    assert upload_file.exists()


def test_non_owner_cannot_delete_task_results(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    client = module.app.test_client()
    other_header = _test_client_auth(module, "other", "password2")

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "delete_denied"
    result_dir.mkdir(parents=True, exist_ok=True)
    _upsert_task_for_user(
        module,
        md5sum,
        filename="owner.fasta",
        file_path=result_dir / "owner.fasta",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.delete(f"/PSSM_GREMLIN/api/delete/{md5sum}", headers=other_header)
    assert response.status_code == 403
    assert response.json["status"] == "forbidden"
    assert module.task_store.get_task(md5sum) is not None


def test_single_delete_rejects_invalid_task_id(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )

    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    response = client.delete("/PSSM_GREMLIN/api/delete/not-a-md5", headers=auth_header)
    assert response.status_code == 400
    assert response.json["status"] == "bad_request"


def test_admin_can_batch_delete_tasks(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin",
        },
    )

    client = module.app.test_client()
    admin_header = _test_client_auth(module, "admin", "admin_password")

    md5_a = uuid.uuid4().hex
    md5_b = uuid.uuid4().hex
    missing_md5 = "0" * 32

    result_a = tmp_path / "batch_a"
    result_b = tmp_path / "batch_b"
    result_a.mkdir(parents=True, exist_ok=True)
    result_b.mkdir(parents=True, exist_ok=True)

    _upsert_task_for_user(
        module,
        md5_a,
        filename="a.fasta",
        file_path=result_a / "a.fasta",
        result_dir=result_a,
        username="tester",
        status="finished",
    )
    _upsert_task_for_user(
        module,
        md5_b,
        filename="b.fasta",
        file_path=result_b / "b.fasta",
        result_dir=result_b,
        username="other",
        status="finished",
    )

    response = client.post(
        "/PSSM_GREMLIN/api/delete",
        headers=admin_header,
        json={"md5sums": [md5_a, md5_b, "zz", missing_md5]},
    )
    assert response.status_code == 200
    payload = response.json
    assert set(payload["deleted"]) == {md5_a, md5_b}
    assert payload["not_found"] == [missing_md5]
    assert payload["ignored"] == ["zz"]
    assert payload["forbidden"] == []
    task_a = module.task_store.get_task(md5_a)
    task_b = module.task_store.get_task(md5_b)
    assert task_a is not None and task_a["status"] == "deleted:finshed"
    assert task_b is not None and task_b["status"] == "deleted:finshed"


def test_batch_delete_guards_and_normalizes_each_md5sum(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin",
        },
    )

    client = module.app.test_client()
    admin_header = _test_client_auth(module, "admin", "admin_password")

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "batch_guard_normalize"
    result_dir.mkdir(parents=True, exist_ok=True)
    _upsert_task_for_user(
        module,
        md5sum,
        filename="guard.fasta",
        file_path=result_dir / "guard.fasta",
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.post(
        "/PSSM_GREMLIN/api/delete",
        headers=admin_header,
        json={"md5sums": [md5sum.upper(), f"  {md5sum}  ", "zz", "", md5sum]},
    )
    assert response.status_code == 200
    payload = response.json
    assert payload["status"] == "ok"
    assert payload["deleted"] == [md5sum]
    assert payload["ignored"] == ["zz"]
    assert payload["not_found"] == []
    assert payload["forbidden"] == []
    task = module.task_store.get_task(md5sum)
    assert task is not None
    assert task["status"] == "deleted:finshed"


def test_non_admin_batch_delete_only_deletes_owned_tasks(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ADMIN_USERS": "admin",
        },
    )

    client = module.app.test_client()
    user_header = _test_client_auth(module)

    own_md5 = uuid.uuid4().hex
    other_md5 = uuid.uuid4().hex
    own_result = tmp_path / "owned_batch_delete"
    other_result = tmp_path / "foreign_batch_delete"
    own_result.mkdir(parents=True, exist_ok=True)
    other_result.mkdir(parents=True, exist_ok=True)
    _upsert_task_for_user(
        module,
        own_md5,
        filename="owned.fasta",
        file_path=own_result / "owned.fasta",
        result_dir=own_result,
        username="tester",
        status="finished",
    )
    _upsert_task_for_user(
        module,
        other_md5,
        filename="foreign.fasta",
        file_path=other_result / "foreign.fasta",
        result_dir=other_result,
        username="other",
        status="finished",
    )

    response = client.post(
        "/PSSM_GREMLIN/api/delete",
        headers=user_header,
        json={"md5sums": [own_md5, other_md5]},
    )
    assert response.status_code == 200
    payload = response.json
    assert payload["status"] == "ok"
    assert payload["deleted"] == [own_md5]
    assert payload["forbidden"] == [other_md5]
    assert payload["ignored"] == []
    assert payload["not_found"] == []
    own_task = module.task_store.get_task(own_md5)
    other_task = module.task_store.get_task(other_md5)
    assert own_task is not None and own_task["status"] == "deleted:finshed"
    assert other_task is not None and other_task["status"] == "finished"


def test_download_uses_safe_fasta_prefix_filename(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "download_safe_name"
    result_dir.mkdir(parents=True, exist_ok=True)
    upload_file = tmp_path / "unsafe_upload.fasta"
    upload_file.write_text(">x\nACDE\n", encoding="utf-8")
    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_PSSM_GREMLIN_results.zip"
    zip_path.write_bytes(b"zip")

    original_filename = "../unsafe name;\r\nX-Test:1.fasta"
    _upsert_task_for_user(
        module,
        md5sum,
        filename=original_filename,
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="finished",
    )

    response = client.get(f"/PSSM_GREMLIN/api/download/{md5sum}", headers=auth_header)
    assert response.status_code == 200
    disposition = response.headers.get("Content-Disposition", "")
    expected_prefix = secure_filename(os.path.splitext(os.path.basename(original_filename))[0]) or "result"
    assert "attachment" in disposition
    assert expected_prefix in disposition
    assert "\r" not in disposition
    assert "\n" not in disposition


def test_failed_task_archive_is_downloadable(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    md5sum = uuid.uuid4().hex
    result_dir = tmp_path / "failed_download"
    result_dir.mkdir(parents=True, exist_ok=True)
    upload_file = tmp_path / "failed.fasta"
    upload_file.write_text(">x\nACDE\n", encoding="utf-8")
    zip_path = Path(module.app.config["RESULTS_FOLDER"]) / f"{md5sum}_PSSM_GREMLIN_results.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("task_failed.txt", "runner failed\n")

    _upsert_task_for_user(
        module,
        md5sum,
        filename="failed.fasta",
        file_path=upload_file,
        result_dir=result_dir,
        username="tester",
        status="failed",
    )
    module.task_store.update_task(md5sum, error="runner failed")

    response = client.get(f"/PSSM_GREMLIN/api/download/{md5sum}", headers=auth_header)
    assert response.status_code == 200
    disposition = response.headers.get("Content-Disposition", "")
    assert "attachment" in disposition
    assert response.data


# ==================================================================
# Admin user control helpers
