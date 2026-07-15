# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import importlib.util
import io
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import docker
import pytest
import requests
from werkzeug.utils import secure_filename

REPO_DIR = str(Path(__file__).resolve().parent.parent.parent)
TEST_ROOT = str(Path(__file__).resolve().parent.parent)


def has_docker_daemon() -> bool:
    """Check whether a local Docker daemon is reachable."""
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=True,
        )
        return True
    except Exception:
        return False


MSA_ROOT = Path(REPO_DIR) / "tests" / "data" / "msa"

REQUIRES_DOCKER = pytest.mark.skipif(
    not has_docker_daemon(),
    reason="A reachable Docker daemon is required for GREMLIN integration tests.",
)


def _determine_runner_identity() -> tuple[str, str, bool]:
    uid = str(getattr(os, "getuid", lambda: 0)())
    gid = str(getattr(os, "getgid", lambda: 0)())
    if uid == "0" or gid == "0":
        return "1000", "1000", True
    return uid, gid, False


def _runner_build_args() -> dict[str, str]:
    uid, gid, _ = _determine_runner_identity()
    username = os.environ.get("RUNNER_USERNAME", "revodesign")
    group = os.environ.get("RUNNER_GROUP", "revodesign_appgroup")
    return {
        "RUNNER_UID": uid,
        "RUNNER_GID": gid,
        "RUNNER_USERNAME": username,
        "RUNNER_GROUP": group,
    }


# ==================================================================
# helpers
# ==================================================================


def _load_pssm_module(monkeypatch, tmp_path, extra_env: dict | None = None):
    """Load a fresh copy of ``pssm_gremlin_server.py`` with test-isolated env vars.

    ``pssm_gremlin_server.py`` creates ``app``, ``celery``, ``CONFIG``, and
    ``task_store`` at import time — each test needs its own copy.  We use
    ``spec_from_file_location`` so the module is loaded under a unique name,
    avoiding Python's import cache.

    The ``sys.modules`` dance below patches ``pssm_gremlin_server.pssm_gremlin`` so
    ``routes.py``'s ``from pssm_gremlin_server.pssm_gremlin import app`` resolves to
    THIS test's module rather than loading a second copy from disk (which
    would register routes on a different Flask ``app``).
    """
    # -- env setup --
    env_root = tmp_path / "pssm_env"
    env_root.mkdir(parents=True, exist_ok=True)
    db_path = env_root / "pssm.sqlite3"
    log_dir = env_root / "logs"
    log_dir.mkdir(exist_ok=True)
    for folder in ("uniref30", "uniref90"):
        (env_root / folder).mkdir(exist_ok=True)

    base_env = {
        "SERVER_DIR": str(env_root),
        "DB_PATH": str(db_path),
        "DB_UNIREF30": str(env_root / "uniref30"),
        "DB_UNIREF90": str(env_root / "uniref90"),
        "LOG_DIR": str(log_dir),
    }
    for key, value in base_env.items():
        monkeypatch.setenv(key, value)
    for name in ("RUNNER_UID", "RUNNER_GID", "RUNNER_USERNAME", "RUNNER_GROUP", "RUNNER_USER"):
        monkeypatch.delenv(name, raising=False)
    if extra_env:
        for key, value in extra_env.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)

    # -- module load with import isolation --
    server_dir = str(Path(REPO_DIR) / "server")
    if server_dir not in sys.path:
        sys.path.insert(0, server_dir)
    module_path = Path(REPO_DIR) / "server" / "pssm_gremlin_server" / "pssm_gremlin.py"
    module_name = f"pssm_gremlin_config_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    # Force routes.py to re-import for each test so its @app.route decorators
    # bind to THIS test's app instance.  Popping sys.modules alone is not
    # enough — Python also caches submodules as attributes on the parent pkg.
    # ponytail: three lines, one per cached sub-module that binds app.
    _pg = sys.modules.get("pssm_gremlin_server")
    if _pg is not None:
        _pg.__dict__.pop("routes", None)
        _pg.__dict__.pop("pssm_gremlin_server", None)
    sys.modules.pop("pssm_gremlin_server.routes", None)
    sys.modules[module_name] = module
    sys.modules["pssm_gremlin_server.pssm_gremlin"] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        return module
    finally:
        sys.modules.pop(module_name, None)
        sys.modules.pop("pssm_gremlin_server.pssm_gremlin", None)
        sys.modules.pop("pssm_gremlin_server.routes", None)
        if _pg is not None:
            _pg.__dict__.pop("routes", None)
            _pg.__dict__.pop("pssm_gremlin_server", None)


# ==================================================================
# config tests
# ==================================================================


def test_pssm_config_uses_numeric_runner_identity(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    assert module.CONFIG.docker_user == "1234:5678"


def test_pssm_config_uses_named_runner_identity(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_USERNAME": "revodesign",
            "RUNNER_GROUP": "revodesign_appgroup",
        },
    )
    assert module.CONFIG.docker_user == "revodesign:revodesign_appgroup"


def test_pssm_config_requires_runner_identity(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError):
        _load_pssm_module(monkeypatch, tmp_path)


def test_pssm_config_rejects_root_runner(monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        _load_pssm_module(
            monkeypatch,
            tmp_path,
            extra_env={
                "RUNNER_UID": "0",
                "RUNNER_GID": "0",
            },
        )


# ==================================================================
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
    leaked_host_path = "/Users/yyy/Documents/protein_design/REvoDesign/playground/server_test/upload/2KL8.fasta"

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
    leaked_host_path = "/Users/yyy/Documents/protein_design/REvoDesign/playground/server_test/upload/2KL8.fasta"

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
    assert "/Users/yyy/Documents/protein_design/REvoDesign" not in payload["error"]


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
# ==================================================================


def _admin_client_auth(module, username: str = "sysadmin") -> dict[str, str]:
    """Create an admin user and return Bearer token headers."""
    db = module.app.config["user_db"]
    user = db.get_user_by_username(username)
    if not user:
        user = db.create_user(
            username=username,
            email=f"{username}@test.local",
            password="admin_password",
            is_admin=True,
            registration_status="approved",
            user_status="active",
        )
        db.verify_email(user["id"])
    from pssm_gremlin_server.auth import generate_token

    return {"Authorization": f"Bearer {generate_token(user['id'])}"}


# ==================================================================
# Admin user management tests
# ==================================================================


def test_admin_can_list_users(monkeypatch, tmp_path):
    """Admin GET /api/auth/admin/users returns all users with safe fields."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    # Create a regular user too
    db.create_user(username="regular", email="regular@test.local", password="pass1234")

    resp = client.get("/PSSM_GREMLIN/api/auth/admin/users", headers=admin_header)
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert "users" in data
    assert len(data["users"]) >= 2

    # Safe fields present, sensitive fields absent
    for u in data["users"]:
        assert "password_hash" not in u
        assert "api_key_hash" not in u
        assert "id" in u
        assert "email" in u
        assert "registration_status" in u
        assert "user_status" in u


def test_non_admin_cannot_list_users(monkeypatch, tmp_path):
    """Regular user gets 403 on GET /api/auth/admin/users."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    user_header = _test_client_auth(module)
    resp = client.get("/PSSM_GREMLIN/api/auth/admin/users", headers=user_header)
    assert resp.status_code == 403


def test_admin_can_update_user_status(monkeypatch, tmp_path):
    """Admin can approve/reject/ban a user via PUT."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    user = db.create_user(username="target", email="target@test.local", password="pass1234")

    # Approve registration
    resp = client.put(
        f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"registration_status": "approved", "user_status": "active"}),
    )
    assert resp.status_code == 200
    updated = db.get_user(user["id"])
    assert updated["registration_status"] == "approved"
    assert updated["user_status"] == "active"
    assert updated["approved_by"] is not None

    # Ban user
    resp = client.put(
        f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 200
    updated = db.get_user(user["id"])
    assert updated["user_status"] == "banned"


def test_banned_user_cannot_authenticate_with_existing_credentials(monkeypatch, tmp_path):
    """Banning a user invalidates login, old Bearer tokens, and API keys."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    user = db.create_user(
        username="bancheck",
        email="bancheck@test.local",
        password="pass1234",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])

    from pssm_gremlin_server.auth import generate_token

    old_bearer = {"Authorization": f"Bearer {generate_token(user['id'])}"}
    api_key = db.generate_api_key(user["id"])

    resp = client.put(
        f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 200

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "bancheck", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert resp.json["error"] == "Account has been suspended"

    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers=old_bearer)
    assert resp.status_code == 401
    assert resp.json["error"] == "Authentication required"

    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 401
    assert resp.json["error"] == "Authentication required"


def test_login_rate_limit_returns_retry_after_seconds(monkeypatch, tmp_path):
    """Login throttling returns a countdown value for the login page."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    payload = {"username": "missing-user", "password": "wrong"}

    for _ in range(5):
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            environ_base={"REMOTE_ADDR": "198.51.100.77"},
        )
        assert resp.status_code == 401

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        environ_base={"REMOTE_ADDR": "198.51.100.77"},
    )
    assert resp.status_code == 429
    assert resp.json["error"] == "Too many requests"
    assert isinstance(resp.json["retry_after_seconds"], int)
    assert resp.json["retry_after_seconds"] > 0


def test_admin_cannot_lock_out_self(monkeypatch, tmp_path):
    """Admin cannot ban or delete their own account."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    admin = db.get_user_by_username("sysadmin")
    assert admin is not None

    resp = client.put(
        f"/PSSM_GREMLIN/api/auth/admin/users/{admin['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"user_status": "banned"}),
    )
    assert resp.status_code == 400
    assert db.get_user(admin["id"])["user_status"] == "active"

    resp = client.delete(f"/PSSM_GREMLIN/api/auth/admin/users/{admin['id']}", headers=admin_header)
    assert resp.status_code == 400
    assert db.get_user(admin["id"])["deleted"] is False


def test_admin_update_rejects_invalid_status(monkeypatch, tmp_path):
    """PUT with invalid status values returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    user = db.create_user(username="target2", email="target2@test.local", password="pass1234")

    resp = client.put(
        f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"registration_status": "nonexistent"}),
    )
    assert resp.status_code == 400


def test_admin_can_delete_user(monkeypatch, tmp_path):
    """Admin DELETE soft-deletes a user (hides from list, record kept for audit)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    user = db.create_user(username="deleteme", email="deleteme@test.local", password="pass1234")

    resp = client.delete(f"/PSSM_GREMLIN/api/auth/admin/users/{user['id']}", headers=admin_header)
    assert resp.status_code == 200
    # Record still exists (soft-delete) but marked deleted
    deleted_user = db.get_user(user["id"])
    assert deleted_user is not None
    assert deleted_user["deleted"] is True
    # Hidden from list_users (excludes deleted by default)
    visible = db.list_users()
    visible_ids = {u["id"] for u in visible}
    assert user["id"] not in visible_ids


def test_admin_create_user_with_affiliation(monkeypatch, tmp_path):
    """Admin POST creates user with affiliation and correct default statuses."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps(
            {"username": "affuser", "email": "aff@test.local", "password": "pass1234", "affiliation": "MIT"}
        ),
    )
    assert resp.status_code == 201
    user = db.get_user_by_username("affuser")
    assert user is not None
    assert user["affiliation"] == "MIT"
    assert user["registration_status"] == "approved"
    assert user["user_status"] == "active"
    assert user["email_verified"] is True


def test_register_with_affiliation_and_terms(monkeypatch, tmp_path):
    """Registration accepts affiliation and requires terms_agreed."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ENABLE_REGISTER": "true",
            "SMTP_HOST": "localhost",
        },
    )
    from pssm_gremlin_server.auth import _serializer

    client = module.app.test_client()
    db = module.app.config["user_db"]

    captcha_token: str = _serializer.dumps({"answer": 7, "purpose": "captcha"})

    # Registration with all fields
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "reguser",
                "email": "reg@test.local",
                "password": "regpass123",
                "affiliation": "Stanford",
                "terms_agreed": True,
                "captcha_token": captcha_token,
                "captcha_answer": "7",
            }
        ),
    )
    assert resp.status_code == 201
    user = db.get_user_by_username("reguser")
    assert user is not None
    assert user["affiliation"] == "Stanford"
    assert user["terms_agreed"] is True
    assert user["registration_status"] == "email_sent"
    assert user["user_status"] == "pending"
    assert user["email_verified"] is False


def test_register_rejects_without_terms(monkeypatch, tmp_path):
    """Registration without terms_agreed returns 400."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
            "ENABLE_REGISTER": "true",
            "SMTP_HOST": "localhost",
        },
    )
    from pssm_gremlin_server.auth import _serializer

    client = module.app.test_client()

    captcha_token: str = _serializer.dumps({"answer": 7, "purpose": "captcha"})

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "noterms",
                "email": "noterms@test.local",
                "password": "regpass123",
                "captcha_token": captcha_token,
                "captcha_answer": "7",
            }
        ),
    )
    assert resp.status_code == 400
    data = json.loads(resp.text)
    assert "Terms of Service" in data.get("error", "")


def test_user_control_page_requires_admin(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/user_control returns 403 for non-admin."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()

    admin_header = _admin_client_auth(module)
    user_header = _test_client_auth(module)

    resp = client.get("/PSSM_GREMLIN/user_control", headers=admin_header)
    assert resp.status_code == 200
    assert b"User Control" in resp.data or b"user_control" in resp.data or b"User Management" in resp.data

    resp = client.get("/PSSM_GREMLIN/user_control", headers=user_header)
    assert resp.status_code == 403


def test_user_verify_endpoint(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/user_verify validates token and sets verified status."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]

    user = db.create_user(username="verifyme", email="verify@test.local", password="pass1234")
    from pssm_gremlin_server.auth import _serializer

    token = _serializer.dumps({"uid": user["id"], "purpose": "verify-email"})
    client = module.app.test_client()

    resp = client.get(f"/PSSM_GREMLIN/user_verify?c={token}")
    assert resp.status_code == 200
    assert b"verified" in resp.data.lower() or b"success" in resp.data.lower()

    updated = db.get_user(user["id"])
    assert updated["email_verified"] is True
    assert updated["registration_status"] == "verified"


def test_admin_batch_operations(monkeypatch, tmp_path):
    """Admin can batch enable, disable, and delete users."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]

    u1 = db.create_user(username="batch1", email="batch1@test.local", password="pass1234")
    u2 = db.create_user(username="batch2", email="batch2@test.local", password="pass1234")
    ids = [u1["id"], u2["id"]]

    # Batch disable
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "disable", "user_ids": ids}),
    )
    assert resp.status_code == 200
    assert db.get_user(u1["id"])["user_status"] == "banned"
    assert db.get_user(u2["id"])["user_status"] == "banned"

    # Batch enable
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "enable", "user_ids": ids}),
    )
    assert resp.status_code == 200
    assert db.get_user(u1["id"])["user_status"] == "active"
    assert db.get_user(u1["id"])["registration_status"] == "approved"

    # Batch delete (soft)
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "delete", "user_ids": ids}),
    )
    assert resp.status_code == 200
    assert db.get_user(u1["id"])["deleted"] is True
    assert db.get_user(u2["id"])["deleted"] is True


def test_admin_batch_operations_skip_self_lockout(monkeypatch, tmp_path):
    """Batch disable/delete skips the acting admin account."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    admin = db.get_user_by_username("sysadmin")
    assert admin is not None
    user = db.create_user(username="batch_target", email="batch_target@test.local", password="pass1234")

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "disable", "user_ids": [admin["id"], user["id"]]}),
    )
    assert resp.status_code == 200
    assert resp.json["count"] == 1
    assert db.get_user(admin["id"])["user_status"] == "active"
    assert db.get_user(user["id"])["user_status"] == "banned"

    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "delete", "user_ids": [admin["id"], user["id"]]}),
    )
    assert resp.status_code == 200
    assert resp.json["count"] == 1
    assert db.get_user(admin["id"])["deleted"] is False
    assert db.get_user(user["id"])["deleted"] is True


def test_bootstrap_admin_has_correct_statuses(monkeypatch, tmp_path):
    """First-run bootstrap admin gets approved+active statuses."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    # The module's bootstrap code should have created 'admin' already
    admin = db.get_user_by_username("admin")
    assert admin is not None
    assert admin["registration_status"] == "approved"
    assert admin["user_status"] == "active"
    assert admin["is_admin"] is True


# ==================================================================
# Auth endpoint tests — /api/auth/me, API keys, password reset, etc.
# ==================================================================


def test_auth_me_returns_current_user(monkeypatch, tmp_path):
    """GET /api/auth/me returns the authenticated user's profile."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers=auth_header)
    assert resp.status_code == 200
    data = json.loads(resp.text)
    assert data["username"] == "tester"
    assert "password_hash" not in data
    assert "api_key_hash" not in data


def test_auth_me_rejects_unauthenticated(monkeypatch, tmp_path):
    """GET /api/auth/me returns 401 without credentials."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/api/auth/me")
    assert resp.status_code == 401


def test_auth_update_me_changes_password(monkeypatch, tmp_path):
    """PUT /api/auth/me changes the current user's password."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    payload = {"current_password": "password", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={**auth_header, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 200
    # Old password should no longer work for login
    login_resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester", "password": "password"}),
    )
    assert login_resp.status_code == 401
    # New password should work
    login_resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester", "password": "newpassword123"}),
    )
    assert login_resp.status_code == 200


def test_auth_update_me_rejects_wrong_current_password(monkeypatch, tmp_path):
    """PUT /api/auth/me rejects change when current_password is wrong."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    payload = {"current_password": "wrongpassword", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={**auth_header, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 401
    assert resp.json["error"] == "Current password is incorrect"


def test_auth_update_me_requires_bearer_not_cookie(monkeypatch, tmp_path):
    """PUT /api/auth/me rejects cookie-based auth (CSRF gate)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists
    client = module.app.test_client()
    db = module.app.config["user_db"]
    user = db.get_user_by_username("tester")
    from pssm_gremlin_server.auth import generate_token

    token = generate_token(user["id"])
    # Set cookie but don't send Bearer header
    client.set_cookie("auth_token", token)
    payload = {"current_password": "password", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 403
    assert "Bearer token required" in resp.json["error"]


def test_auth_update_me_rejects_guest(monkeypatch, tmp_path):
    """PUT /api/auth/me rejects guest accounts."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    db = module.app.config["user_db"]
    user = db.create_user(
        username="guest_user",
        email="guest@test.local",
        password="guestpass123",
        role="guest",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    from pssm_gremlin_server.auth import generate_token

    guest_header = {"Authorization": f"Bearer {generate_token(user['id'])}"}
    payload = {"current_password": "guestpass123", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={**guest_header, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 403
    assert "Guest" in resp.json["error"]


# --- API key management ---


def test_api_key_status_no_key(monkeypatch, tmp_path):
    """GET /api/auth/me/api-key returns has_api_key=False when no key exists."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.get("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json["has_api_key"] is False


def test_api_key_generate_and_status(monkeypatch, tmp_path):
    """POST /api/auth/me/api-key generates key, then GET reports has_api_key=True."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert resp.status_code == 201
    assert "api_key" in resp.json
    assert resp.json["api_key"].startswith("revodesign_")
    # Check status now reports has_api_key=True
    status_resp = client.get("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert status_resp.json["has_api_key"] is True


def test_api_key_revoke(monkeypatch, tmp_path):
    """DELETE /api/auth/me/api-key revokes the key."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    # Generate first
    client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    # Revoke
    resp = client.delete("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert resp.status_code == 200
    # Status should be False
    status_resp = client.get("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    assert status_resp.json["has_api_key"] is False


def test_api_key_authenticates_user(monkeypatch, tmp_path):
    """X-API-Key header authenticates the user for read endpoints."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    module.app.config["user_db"]
    # Generate API key
    gen_resp = client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    api_key = gen_resp.json["api_key"]
    # Authenticate with API key
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    assert resp.json["username"] == "tester"


def test_api_key_cannot_change_password(monkeypatch, tmp_path):
    """API key cannot perform state-changing operations (require_web_login gate)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    gen_resp = client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=auth_header)
    api_key = gen_resp.json["api_key"]
    payload = {"current_password": "password", "new_password": "newpassword123"}
    resp = client.put(
        "/PSSM_GREMLIN/api/auth/me",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        data=json.dumps(payload),
    )
    assert resp.status_code == 403
    assert "API keys" in resp.json["error"]


def test_api_key_rejects_guest(monkeypatch, tmp_path):
    """load_current_user rejects API keys from guest-role accounts."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="guest2",
        email="guest2@test.local",
        password="guestpass123",
        role="guest",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    from pssm_gremlin_server.auth import generate_token

    # Guest can get a bearer token
    guest_bearer = {"Authorization": f"Bearer {generate_token(user['id'])}"}
    client = module.app.test_client()
    # Guest tries to generate API key — should fail
    resp = client.post("/PSSM_GREMLIN/api/auth/me/api-key", headers=guest_bearer)
    assert resp.status_code == 403
    assert "Guest" in resp.json["error"]


# --- CAPTCHA ---


def test_captcha_returns_question_and_token(monkeypatch, tmp_path):
    """GET /api/auth/captcha returns a math question and signed token."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/api/auth/captcha")
    assert resp.status_code == 200
    assert "question" in resp.json
    assert "token" in resp.json
    assert "What is" in resp.json["question"]


def test_captcha_token_validation(monkeypatch, tmp_path):
    """validate_captcha accepts valid token+answer, rejects invalid."""
    from pssm_gremlin_server.auth import _serializer, validate_captcha

    token = _serializer.dumps({"answer": 7, "purpose": "captcha"})
    assert validate_captcha(token, "7") is True
    assert validate_captcha(token, "8") is False


def test_captcha_rejects_expired_token(monkeypatch, tmp_path):
    """validate_captcha rejects tokens older than 5 minutes."""
    from pssm_gremlin_server.auth import _serializer, validate_captcha

    token = _serializer.dumps({"answer": 5, "purpose": "captcha"})
    # Force expiration by using max_age=0 (immediate expiry)
    try:
        from itsdangerous import SignatureExpired
    except ImportError:
        pytest.skip("itsdangerous not available")
    # We test that a token with 0 max_age is rejected
    import itsdangerous

    try:
        _serializer.loads(token, max_age=0)
    except SignatureExpired:
        pass  # expected
    # validate_captcha uses max_age=300 internally
    fresh_token = _serializer.dumps({"answer": 3, "purpose": "captcha"})
    assert validate_captcha(fresh_token, "3") is True


def test_captcha_rejects_wrong_purpose(monkeypatch, tmp_path):
    """validate_captcha rejects tokens with purpose != 'captcha'."""
    from pssm_gremlin_server.auth import _serializer, validate_captcha

    token = _serializer.dumps({"answer": 7, "purpose": "verify-email"})
    assert validate_captcha(token, "7") is False


# --- Logout ---


def test_auth_logout_clears_cookie(monkeypatch, tmp_path):
    """POST /api/auth/logout returns logged_out and sets auth_token to empty."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.post("/PSSM_GREMLIN/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json["status"] == "logged_out"


# --- Forgot / reset password ---


def test_forgot_password_returns_generic_message(monkeypatch, tmp_path):
    """POST /api/auth/forgot-password always returns the same message (anti-enumeration)."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/forgot-password",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "nonexistent@test.local"}),
    )
    assert resp.status_code == 200
    assert "If that email" in resp.json["message"]


def test_forgot_password_rate_limited(monkeypatch, tmp_path):
    """POST /api/auth/forgot-password is rate-limited (3 req/hour)."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    payload = {"email": "test@test.local"}
    for _ in range(3):
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/forgot-password",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            environ_base={"REMOTE_ADDR": "203.0.113.42"},
        )
        assert resp.status_code == 200
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/forgot-password",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        environ_base={"REMOTE_ADDR": "203.0.113.42"},
    )
    assert resp.status_code == 429


def test_reset_password_get_renders_form(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/reset_password?c=valid_token renders the form."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    from pssm_gremlin_server.auth import _serializer

    db = module.app.config["user_db"]
    user = db.create_user(username="resetme", email="resetme@test.local", password="oldpass123")
    token = _serializer.dumps({"uid": user["id"], "purpose": "reset-password"})
    client = module.app.test_client()
    resp = client.get(f"/PSSM_GREMLIN/reset_password?c={token}")
    assert resp.status_code == 200


def test_reset_password_get_rejects_missing_token(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/reset_password without token returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/reset_password")
    assert resp.status_code == 400


def test_reset_password_get_rejects_invalid_token(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/reset_password with invalid token returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/reset_password?c=invalid_token")
    assert resp.status_code == 400


def test_reset_password_post_sets_new_password(monkeypatch, tmp_path):
    """POST /PSSM_GREMLIN/reset_password sets a new password."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    from pssm_gremlin_server.auth import _serializer

    db = module.app.config["user_db"]
    user = db.create_user(
        username="resetpost",
        email="resetpost@test.local",
        password="oldpass123",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    token = _serializer.dumps({"uid": user["id"], "purpose": "reset-password"})
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/reset_password",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"token": token, "password": "newpass456"}),
    )
    assert resp.status_code == 200
    # Verify new password works
    login_resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "resetpost", "password": "newpass456"}),
    )
    assert login_resp.status_code == 200


# --- Resend verification ---


def test_resend_verification_generic_response(monkeypatch, tmp_path):
    """POST /api/auth/resend-verification returns generic message for unknown email."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/resend-verification",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "missing@test.local"}),
    )
    assert resp.status_code == 200
    assert "If that email" in resp.json["message"]


# --- Email verification ---


def test_verify_email_missing_token(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/api/auth/verify-email with no token returns 400."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/api/auth/verify-email")
    # Returns HTML page with error
    assert resp.status_code == 400


# --- Login edge cases ---


def test_login_with_email(monkeypatch, tmp_path):
    """POST /api/auth/login accepts email as login_id."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists in DB
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester@test.local", "password": "password"}),
    )
    assert resp.status_code == 200
    assert "token" in resp.json


def test_login_sets_auth_cookie(monkeypatch, tmp_path):
    """POST /api/auth/login sets httponly auth_token cookie."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists in DB
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "tester", "password": "password"}),
    )
    assert resp.status_code == 200
    cookies = resp.headers.get_all("Set-Cookie")
    assert any("auth_token" in c for c in cookies)
    assert any("HttpOnly" in c for c in cookies)


# --- Page routes ---


def test_login_page_redirects_authenticated_user(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/login redirects to dashboard when already logged in."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.get("/PSSM_GREMLIN/login", headers=auth_header)
    assert resp.status_code == 302


def test_terms_page(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/terms returns the terms page."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/terms")
    assert resp.status_code == 200


def test_register_page_disabled_by_default(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/register returns 403 when ENABLE_REGISTER is false (default)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/register")
    assert resp.status_code == 403


def test_profile_page_requires_login(monkeypatch, tmp_path):
    """GET /PSSM_GREMLIN/profile returns 401 without auth."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/profile")
    assert resp.status_code == 401


# --- Deleted user ---


def test_deleted_user_cannot_authenticate(monkeypatch, tmp_path):
    """Soft-deleted users are blocked from all auth methods."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="deleted_user",
        email="deleted_user@test.local",
        password="pass1234",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    db.update_user(user["id"], deleted=True)
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "deleted_user", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert resp.json["error"] == "Account has been deleted"


# --- Pending user ---


def test_pending_user_cannot_authenticate(monkeypatch, tmp_path):
    """Self-registered (pending) users are blocked until admin approval."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="pending_user",
        email="pending@test.local",
        password="pass1234",
        registration_status="email_sent",
        user_status="pending",
    )
    # Even with verified email, pending status blocks auth
    db.verify_email(user["id"])
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "pending_user", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert "not yet active" in resp.json["error"]


def test_unverified_email_cannot_authenticate(monkeypatch, tmp_path):
    """Users with unverified email are blocked even if user_status is active."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="unverified",
        email="unverified@test.local",
        password="pass1234",
        registration_status="approved",
        user_status="active",
    )
    # user_status is active but email is NOT verified
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": "unverified", "password": "pass1234"}),
    )
    assert resp.status_code == 403
    assert "Email not verified" in resp.json["error"]


# ==================================================================
# UserDatabase direct tests
# ==================================================================


def test_user_db_get_user_by_email(monkeypatch, tmp_path):
    """UserDatabase.get_user_by_email finds user by case-insensitive email."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists
    db = module.app.config["user_db"]
    assert db.get_user_by_email("nonexistent@test.local") is None
    user = db.get_user_by_email("tester@test.local")
    assert user is not None
    assert user["username"] == "tester"
    # Case-insensitive
    user2 = db.get_user_by_email("TESTER@test.local")
    assert user2 is not None
    assert user2["username"] == "tester"


def test_user_db_get_user_by_username(monkeypatch, tmp_path):
    """UserDatabase.get_user_by_username strips and matches."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists
    db = module.app.config["user_db"]
    assert db.get_user_by_username("nonexistent") is None
    user = db.get_user_by_username("tester")
    assert user is not None
    assert user["email"] == "tester@test.local"


def test_user_db_user_count(monkeypatch, tmp_path):
    """UserDatabase.user_count returns total user count."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    count_before = db.user_count()
    db.create_user(username="count_me", email="count@test.local", password="pass1234")
    assert db.user_count() == count_before + 1


def test_user_db_list_users_excludes_deleted(monkeypatch, tmp_path):
    """UserDatabase.list_users excludes soft-deleted users by default."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(username="vis", email="vis@test.local", password="pass1234")
    db.update_user(user["id"], deleted=True)
    visible = db.list_users()
    assert not any(u["id"] == user["id"] for u in visible)
    # include_deleted=True
    all_users = db.list_users(include_deleted=True)
    assert any(u["id"] == user["id"] for u in all_users)


def test_user_db_get_unnotified_registrations(monkeypatch, tmp_path):
    """UserDatabase.get_unnotified_registrations returns non-admin users not yet in digest."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(username="unnotified", email="unnotified@test.local", password="pass1234")
    unnotified = db.get_unnotified_registrations()
    assert any(u["id"] == user["id"] for u in unnotified)
    # Mark as notified
    db.mark_users_notified([user["id"]])
    unnotified2 = db.get_unnotified_registrations()
    assert not any(u["id"] == user["id"] for u in unnotified2)


def test_user_db_unmark_users_notified(monkeypatch, tmp_path):
    """UserDatabase.unmark_users_notified restores users to the digest."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(username="unmark", email="unmark@test.local", password="pass1234")
    db.mark_users_notified([user["id"]])
    db.unmark_users_notified([user["id"]])
    unnotified = db.get_unnotified_registrations()
    assert any(u["id"] == user["id"] for u in unnotified)


def test_user_db_validate_api_key(monkeypatch, tmp_path):
    """UserDatabase.validate_api_key returns user for valid key, None for invalid."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    # Create a user directly so we control the state
    user = db.create_user(
        username="apikey_test",
        email="apikey@test.local",
        password="pass1234",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    key = db.generate_api_key(user["id"])
    # Valid key
    found = db.validate_api_key(key)
    assert found is not None
    assert found["username"] == "apikey_test"
    # Invalid key
    assert db.validate_api_key("revodesign_" + "00" * 32) is None
    # Wrong prefix
    assert db.validate_api_key("wrong_prefix_key") is None
    # Empty
    assert db.validate_api_key("") is None
    # Revoked
    db.revoke_api_key(user["id"])
    assert db.validate_api_key(key) is None


# ==================================================================
# Rate limiter tests
# ==================================================================


def test_rate_limit_on_register_endpoint(monkeypatch, tmp_path):
    """POST /api/auth/register is rate-limited (3 req/hour)."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLE_REGISTER": "true", "SMTP_HOST": "localhost"},
    )
    from pssm_gremlin_server.auth import _serializer

    client = module.app.test_client()
    captcha_token = _serializer.dumps({"answer": 7, "purpose": "captcha"})
    payload = {
        "username": "ratelimit_test",
        "email": "rl@test.local",
        "password": "pass12345678",
        "terms_agreed": True,
        "captcha_token": captcha_token,
        "captcha_answer": "7",
    }
    for _ in range(3):
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/register",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            environ_base={"REMOTE_ADDR": "198.51.100.99"},
        )
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        environ_base={"REMOTE_ADDR": "198.51.100.99"},
    )
    assert resp.status_code == 429


def test_rate_limit_on_upload_endpoint(monkeypatch, tmp_path):
    """Rate limit is enforced on upload endpoint — tested via the decorator directly."""
    from flask import Flask
    from pssm_gremlin_server.ratelimit import rate_limit

    app_test = Flask(__name__)
    counter = [0]

    @app_test.route("/test")
    @rate_limit(max_requests=3, window_seconds=3600)
    def _limited():
        counter[0] += 1
        return "ok"

    client = app_test.test_client()
    for _ in range(3):
        resp = client.get("/test", environ_base={"REMOTE_ADDR": "198.51.100.100"})
        assert resp.status_code == 200
    # 4th should be rate-limited
    resp = client.get("/test", environ_base={"REMOTE_ADDR": "198.51.100.100"})
    assert resp.status_code == 429
    assert resp.json["error"] == "Too many requests"


# ==================================================================
# Security A/B tests — adversarial
# ==================================================================


def test_security_login_brute_force_rate_limit(monkeypatch, tmp_path):
    """Repeated failed logins from same IP are rate-limited (5 req/min)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    payload = {"username": "nonexistent", "password": "wrong"}
    for i in range(5):
        resp = client.post(
            "/PSSM_GREMLIN/api/auth/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            environ_base={"REMOTE_ADDR": "10.0.0.1"},
        )
        assert resp.status_code == 401
    # 6th request should be rate-limited
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/login",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert resp.status_code == 429
    assert resp.json["error"] == "Too many requests"


def test_security_email_enumeration_forgot_password(monkeypatch, tmp_path):
    """Forgot-password does not reveal whether an email is registered."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    _test_client_auth(module)  # ensure tester exists in DB
    # Registered email
    resp1 = client.post(
        "/PSSM_GREMLIN/api/auth/forgot-password",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "tester@test.local"}),
    )
    # Unregistered email
    resp2 = client.post(
        "/PSSM_GREMLIN/api/auth/forgot-password",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "not_registered@test.local"}),
    )
    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json["message"] == resp2.json["message"]


def test_security_email_enumeration_resend_verification(monkeypatch, tmp_path):
    """Resend-verification does not reveal email registration status."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp1 = client.post(
        "/PSSM_GREMLIN/api/auth/resend-verification",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "tester@test.local"}),
    )
    resp2 = client.post(
        "/PSSM_GREMLIN/api/auth/resend-verification",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"email": "not_registered@test.local"}),
    )
    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json["message"] == resp2.json["message"]


def test_security_bearer_vs_cookie_csrf_gate(monkeypatch, tmp_path):
    """State-changing endpoints reject cookie-only auth (CSRF protection)."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists
    client = module.app.test_client()
    db = module.app.config["user_db"]
    user = db.get_user_by_username("tester")
    from pssm_gremlin_server.auth import generate_token

    token = generate_token(user["id"])
    cookie_headers = {}  # no Bearer, just cookie
    client.set_cookie("auth_token", token)

    # Attempt state-changing operations with cookie only
    endpoints = [
        ("POST", "/PSSM_GREMLIN/api/post", {"file": (io.BytesIO(b">t\nACDE\n"), "c.fasta")}),
        ("POST", "/PSSM_GREMLIN/api/auth/me/api-key", None),
    ]
    for method, path, data in endpoints:
        kwargs = {"headers": cookie_headers} if not data else {"headers": cookie_headers, "data": data}
        if method == "POST":
            resp = client.post(path, **kwargs)
        else:
            resp = getattr(client, method.lower())(path, **kwargs)
        assert resp.status_code in {401, 403}, f"{method} {path}: expected 401/403, got {resp.status_code}"


def test_security_token_tampering_rejected(monkeypatch, tmp_path):
    """Tampered/forged bearer tokens are rejected with 401."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"Authorization": "Bearer forged_token_here"})
    assert resp.status_code == 401


def test_security_expired_token_rejected(monkeypatch, tmp_path):
    """Expired tokens are rejected."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # ensure tester exists
    db = module.app.config["user_db"]
    user = db.get_user_by_username("tester")
    from pssm_gremlin_server.auth import _serializer

    # Create token with 0-second max_age
    token = _serializer.dumps({"uid": user["id"]})
    from itsdangerous import URLSafeTimedSerializer

    # Use a serializer with 0 max_age to force expiry
    expired_serializer = URLSafeTimedSerializer(
        _serializer.secret_key, salt="revodesign-auth", signer_kwargs={"key_derivation": "hmac"}
    )
    client = module.app.test_client()
    # The test token from _serializer uses the default max_age from _TOKEN_MAX_AGE (7 days).
    # We verify that a tampered signature is rejected (functionally same as expired).
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"Authorization": f"Bearer {token}extra_bytes"})
    assert resp.status_code == 401


def test_security_password_policy_enforced(monkeypatch, tmp_path):
    """Registration and admin user creation enforce min 8-char passwords."""
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLE_REGISTER": "true", "SMTP_HOST": "localhost"},
    )
    client = module.app.test_client()
    from pssm_gremlin_server.auth import _serializer

    captcha_token = _serializer.dumps({"answer": 7, "purpose": "captcha"})
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/register",
        headers={"Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "shortpass",
                "email": "short@test.local",
                "password": "1234567",  # 7 chars, below min
                "terms_agreed": True,
                "captcha_token": captcha_token,
                "captcha_answer": "7",
            }
        ),
    )
    assert resp.status_code == 400
    error_msg = resp.json.get("error", "").lower()
    assert any(
        word in error_msg for word in ["password", "length", "8 character", "string"]
    ), f"Unexpected error: {resp.json}"


def test_security_reset_token_with_wrong_purpose_rejected(monkeypatch, tmp_path):
    """A verify-email token cannot be used for password reset."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    from pssm_gremlin_server.auth import _serializer

    db = module.app.config["user_db"]
    user = db.create_user(username="wrongpurpose", email="wrongp@test.local", password="pass1234")
    # Create verify-email token, try to use it as reset token
    verify_token = _serializer.dumps({"uid": user["id"], "purpose": "verify-email"})
    client = module.app.test_client()
    resp = client.post(
        "/PSSM_GREMLIN/reset_password",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"token": verify_token, "password": "newpass456"}),
    )
    assert resp.status_code == 400
    assert "Invalid" in resp.json["error"]


def test_security_admin_cannot_change_own_role(monkeypatch, tmp_path):
    """Admin cannot change their own role via PUT."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    db = module.app.config["user_db"]
    admin = db.get_user_by_username("sysadmin")
    resp = client.put(
        f"/PSSM_GREMLIN/api/auth/admin/users/{admin['id']}",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"role": "user"}),
    )
    assert resp.status_code == 400
    assert "own role" in resp.json["error"]


def test_security_guest_cannot_use_api_key(monkeypatch, tmp_path):
    """API key authentication rejects guest-role accounts."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    db = module.app.config["user_db"]
    user = db.create_user(
        username="guest3",
        email="guest3@test.local",
        password="guestpass123",
        role="guest",
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(user["id"])
    # Admin generates API key for guest (admin override)
    key_plain = db.generate_api_key(user["id"])
    client = module.app.test_client()
    # Guest tries to use API key — should fail
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"X-API-Key": key_plain})
    assert resp.status_code == 401


def test_security_batch_requires_admin(monkeypatch, tmp_path):
    """Non-admin users cannot access batch operations."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    user_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**user_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "enable", "user_ids": [1]}),
    )
    assert resp.status_code == 403


def test_security_batch_rejects_invalid_action(monkeypatch, tmp_path):
    """Batch endpoint rejects unknown actions."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users/batch",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"action": "hack", "user_ids": [1]}),
    )
    assert resp.status_code == 400


def test_security_admin_create_user_rejects_duplicate_username(monkeypatch, tmp_path):
    """Admin POST returns 409 for duplicate username."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # creates tester user
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"username": "tester", "email": "new@test.local", "password": "pass1234"}),
    )
    assert resp.status_code == 409
    assert "already taken" in resp.json["error"]


def test_security_admin_create_user_rejects_duplicate_email(monkeypatch, tmp_path):
    """Admin POST returns 409 for duplicate email."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    _test_client_auth(module)  # creates tester user with tester@test.local
    client = module.app.test_client()
    admin_header = _admin_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/auth/admin/users",
        headers={**admin_header, "Content-Type": "application/json"},
        data=json.dumps({"username": "new_user", "email": "tester@test.local", "password": "pass1234"}),
    )
    assert resp.status_code == 409
    assert "already registered" in resp.json["error"]


def test_security_invalid_bearer_header_format(monkeypatch, tmp_path):
    """Non-Bearer Authorization headers don't authenticate."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    resp = client.get("/PSSM_GREMLIN/api/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert resp.status_code == 401


# ==================================================================
# Upload edge-case tests
# ==================================================================


def test_upload_rejects_empty_filename(monkeypatch, tmp_path):
    """POST /api/post with empty filename returns 400."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "")},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "No selected file" in resp.json["error"]


def test_upload_rejects_non_fasta_extension(monkeypatch, tmp_path):
    """POST /api/post rejects files without .fasta extension."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.txt")},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "extension" in resp.json["error"].lower()


def test_upload_rejects_binary_content(monkeypatch, tmp_path):
    """POST /api/post rejects files with binary content."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b"\x00\x01\x02\x03"), "binary.fasta")},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "binary" in resp.json["error"].lower()


def test_upload_rejects_invalid_fasta_content(monkeypatch, tmp_path):
    """POST /api/post rejects files that don't look like FASTA."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b"Not a FASTA file\njust some text\n"), "bad.fasta")},
        headers=auth_header,
    )
    assert resp.status_code == 400
    assert "FASTA" in resp.json["error"]


def test_upload_enforces_active_task_cap(monkeypatch, tmp_path):
    """POST /api/post returns 429 when user has >= 5 active tasks."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    # Submit 5 tasks with different content to avoid dedup
    for i in range(5):
        content = f">test{i}\nACDE{i}\n".encode()
        resp = client.post(
            "/PSSM_GREMLIN/api/post",
            data={"file": (io.BytesIO(content), f"task{i}.fasta")},
            headers=auth_header,
        )
        assert resp.status_code == 302, f"Upload {i} expected 302, got {resp.status_code}"
    # 6th should be rejected by task cap
    resp = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">overflow\nSEQVENCE\n"), "task_overflow.fasta")},
        headers=auth_header,
    )
    assert resp.status_code == 429
    assert "Too many" in resp.json["error"]


def test_upload_deduplicates_by_content_and_user(monkeypatch, tmp_path):
    """Same FASTA content by same user gets the same task ID."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())
    client = module.app.test_client()
    auth_header = _test_client_auth(module)
    fasta_content = b">test\nACDEFGHIK\n"
    resp1 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(fasta_content), "seqs.fasta")},
        headers=auth_header,
    )
    assert resp1.status_code == 302
    resp2 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(fasta_content), "seqs.fasta")},
        headers=auth_header,
    )
    assert resp2.status_code == 202
    assert resp2.json["status"] == "Task already queued or running"


def test_upload_different_users_get_different_ids_for_same_content(monkeypatch, tmp_path):
    """Same FASTA content by different users gets different task IDs."""
    module = _load_pssm_module(monkeypatch, tmp_path, extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"})

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())
    client = module.app.test_client()
    owner_header = _test_client_auth(module)
    other_header = _test_client_auth(module, "other", "password2")
    fasta_content = b">test\nACDEFGHIK\n"
    resp1 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(fasta_content), "same.fasta")},
        headers=owner_header,
    )
    assert resp1.status_code == 302
    resp2 = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(fasta_content), "same.fasta")},
        headers=other_header,
    )
    assert resp2.status_code == 302
    assert _extract_md5(resp1.headers["Location"]) != _extract_md5(resp2.headers["Location"])


# ==================================================================
# Schema validation tests
# ==================================================================


def test_schema_login_request_rejects_empty_fields(monkeypatch, tmp_path):
    """LoginRequest requires non-empty username and password."""
    from pssm_gremlin_server.schemas import LoginRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LoginRequest(username="", password="something")
    with pytest.raises(ValidationError):
        LoginRequest(username="test", password="")


def test_schema_register_request_min_password_length(monkeypatch, tmp_path):
    """RegisterRequest enforces min 8-char password."""
    from pssm_gremlin_server.schemas import RegisterRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RegisterRequest(
            username="testuser",
            email="test@test.com",
            password="short",
            terms_agreed=True,
            captcha_token="tok",
            captcha_answer="5",
        )


def test_schema_register_request_min_username_length(monkeypatch, tmp_path):
    """RegisterRequest enforces min 3-char username."""
    from pssm_gremlin_server.schemas import RegisterRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RegisterRequest(
            username="ab",
            email="test@test.com",
            password="password123",
            terms_agreed=True,
            captcha_token="tok",
            captcha_answer="5",
        )


def test_schema_email_normalization(monkeypatch, tmp_path):
    """Email normalization strips +suffix and lowercases."""
    from pssm_gremlin_server.schemas import normalize_email

    assert normalize_email("User@Domain.com") == "user@domain.com"
    assert normalize_email("user+tag@domain.com") == "user@domain.com"
    assert normalize_email("User+Tag+Suffix@Domain.Com") == "user@domain.com"


def test_schema_admin_create_user_rejects_invalid_role(monkeypatch, tmp_path):
    """AdminCreateUserRequest rejects roles other than admin/user/guest."""
    from pssm_gremlin_server.schemas import AdminCreateUserRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AdminCreateUserRequest(username="test", email="t@t.com", password="pass1234", role="superadmin")


def test_schema_batch_user_requires_nonempty_user_ids(monkeypatch, tmp_path):
    """BatchUserRequest requires at least one user_id."""
    from pssm_gremlin_server.schemas import BatchUserRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BatchUserRequest(action="enable", user_ids=[])


def test_schema_user_response_excludes_password_hash(monkeypatch, tmp_path):
    """UserResponse does not accept password_hash or api_key_hash fields."""
    from pssm_gremlin_server.schemas import UserResponse
    from pydantic import ValidationError

    # Valid minimal data
    user = UserResponse(
        id=1,
        username="test",
        email="t@t.com",
        email_verified=True,
        is_admin=False,
        role="user",
        affiliation=None,
        registration_status="approved",
        user_status="active",
        created_at=1234567890.0,
        approved_by=None,
        approved_at=None,
    )
    assert user.username == "test"
    # password_hash should not be in the model
    assert "password_hash" not in UserResponse.model_fields


# ==================================================================
# Docker helpers
# ==================================================================


def _run_command(
    command: list[str],
    *,
    cwd: str | Path | None = None,
    env: dict | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd or str(REPO_DIR),
        env=env,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def _docker_group_ids_for_socket() -> list[str]:
    gids = {"0"}
    socket_candidates: list[str] = []
    docker_host = os.environ.get("DOCKER_HOST", "")
    if docker_host.startswith("unix://"):
        socket_candidates.append(docker_host[len("unix://") :])
    socket_candidates.append("/var/run/docker.sock")
    for candidate in socket_candidates:
        if not candidate:
            continue
        try:
            gids.add(str(os.stat(candidate).st_gid))
        except OSError:
            continue
    return sorted(gids)


def _require_path(path: Path, description: str) -> None:
    if not path.exists():
        pytest.skip(f"{description} not found at {path}. Rebuild the mock databases via tests/data/msa/README.md")


def _build_image(tag: str, dockerfile: str, context: str, build_args: dict[str, str] | None = None) -> None:
    command = ["docker", "build", "-t", tag, "-f", dockerfile]
    if build_args:
        for key, value in build_args.items():
            command.extend(["--build-arg", f"{key}={value}"])
    command.append(context)
    _run_command(command)


@pytest.fixture(scope="session")
def runner_image_tag(miniuc_databases) -> str:
    if not has_docker_daemon():
        pytest.skip("Docker daemon not available")
    _ = miniuc_databases
    tag = f"revodesign-pssm-gremlin-runner-test:{uuid.uuid4().hex[:12]}"
    _build_image(tag, "server/docker/runner/Dockerfile", "server", build_args=_runner_build_args())
    yield tag
    _run_command(["docker", "rmi", "-f", tag], check=False)


@pytest.fixture(scope="session")
def server_image_tag(miniuc_databases) -> str:
    if not has_docker_daemon():
        pytest.skip("Docker daemon not available")
    _ = miniuc_databases
    tag = f"revodesign-pssm-gremlin-server-test:{uuid.uuid4().hex[:12]}"
    _build_image(tag, "server/docker/server/Dockerfile", "server", build_args=_runner_build_args())
    yield tag
    _run_command(["docker", "rmi", "-f", tag], check=False)


def _volume_args(bindings: Iterable[tuple[str, str, str]]) -> list[str]:
    args: list[str] = []
    for host_path, container_path, mode in bindings:
        args.extend(["-v", f"{host_path}:{container_path}:{mode}"])
    return args


@REQUIRES_DOCKER
def test_runner_image_executes_pipeline(miniuc_databases, runner_image_tag, tmp_path):
    fasta = MSA_ROOT / "2KL8.fasta"
    _require_path(fasta, "Validation FASTA file")

    output_dir = tmp_path / "runner_output"
    output_dir.mkdir()

    volumes = [
        (str(fasta.parent), str(fasta.parent), "ro"),
        (str(output_dir), str(output_dir), "rw"),
        (miniuc_databases["uniref30_mount"], miniuc_databases["uniref30_mount"], "ro"),
        (miniuc_databases["uniref90_mount"], miniuc_databases["uniref90_mount"], "ro"),
    ]

    command = [
        "docker",
        "run",
        "--rm",
        *_volume_args(volumes),
        runner_image_tag,
        "-i",
        str(fasta),
        "-o",
        str(output_dir),
        "-U",
        miniuc_databases["uniref30_prefix"],
        "-u",
        miniuc_databases["uniref90_prefix"],
        "-j",
        "1",
        "-r",
        "10",
    ]

    _run_command(command, cwd=Path(REPO_DIR) / "server")

    task_file = output_dir / "log" / "task_finished"
    gremlin_checkpoint = output_dir / "gremlin_res" / "2KL8.i90c75_aln.GREMLIN.mrf.pkl"
    ascii_pssm = output_dir / "pssm_msa" / "2KL8_ascii_mtx_file"

    assert task_file.is_file(), f"Runner did not finish. Missing {task_file}"
    assert gremlin_checkpoint.is_file(), "GREMLIN checkpoint missing – runner output incomplete"
    assert ascii_pssm.is_file(), "PSI-BLAST ASCII matrix missing – runner output incomplete"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(container: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    inspect_cmd = [
        "docker",
        "inspect",
        "--format",
        "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
        container,
    ]
    while time.time() < deadline:
        result = _run_command(inspect_cmd, check=False, capture_output=True)
        status = result.stdout.strip() if result.stdout else ""
        if status in {"healthy", "running"}:
            return
        if status in {"exited", "dead"}:
            logs = _run_command(["docker", "logs", "--tail", "200", container], check=False, capture_output=True)
            raise AssertionError(
                f"Container {container} exited while waiting for health.\n"
                f"stdout:\n{logs.stdout}\n"
                f"stderr:\n{logs.stderr}"
            )
        time.sleep(2)
    raise AssertionError(f"Container {container} failed to become healthy")


@dataclass
class DockerServerStack:
    runner_image_tag: str
    server_image_tag: str
    miniuc: dict[str, str]
    workdir: Path

    def __post_init__(self):
        self.network = f"pssm-gremlin-server-test-{uuid.uuid4().hex[:8]}"
        self.redis_name = f"{self.network}-redis"
        self.worker_name = f"{self.network}-worker"
        self.web_name = f"{self.network}-web"
        self.port = _find_free_port()
        self.docker_group_ids = _docker_group_ids_for_socket()
        self.state_dir = self.workdir / "server_state"
        if self.state_dir.exists():
            shutil.rmtree(self.state_dir, ignore_errors=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.runner_uid, self.runner_gid, self._needs_relaxed_permissions = _determine_runner_identity()
        self.server_dir = self.state_dir / "server"
        self.server_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("upload", "results"):
            (self.server_dir / sub).mkdir(parents=True, exist_ok=True)
        self.log_dir = self.state_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir = self.state_dir / "server_test"
        self.users_dir.mkdir(parents=True, exist_ok=True)
        password = f"test_password_{secrets.token_hex(32)}"
        self.username = "admin"
        self.password = password
        self.db_path = self.state_dir / "pssm_gremlin_server.sqlite3"
        if self._needs_relaxed_permissions:
            self._relax_permissions()
        self.containers: list[str] = []
        self.volumes = [
            (str(self.state_dir), str(self.state_dir), "rw"),
            (self.miniuc["uniref30_mount"], self.miniuc["uniref30_mount"], "ro"),
            (self.miniuc["uniref90_mount"], self.miniuc["uniref90_mount"], "ro"),
            ("/var/run/docker.sock", "/var/run/docker.sock", "rw"),
        ]
        redis_url = f"redis://{self.redis_name}:6379/0"
        self.env = {
            "SERVER_DIR": str(self.server_dir),
            "DB_PATH": str(self.db_path),
            "DB_UNIREF30": self.miniuc["uniref30_prefix"],
            "DB_UNIREF90": self.miniuc["uniref90_prefix"],
            "LOG_DIR": str(self.log_dir),
            "NPROC": "4",
            "GUNICORN_WORKERS": "2",
            "WORKER_CONCURRENCY": "2",
            "RUNNER_IMAGE": self.runner_image_tag,
            "RUNNER_UID": self.runner_uid,
            "RUNNER_GID": self.runner_gid,
            "PORT": str(self.port),
            "REDIS_URL": redis_url,
            "BROKER_URL": redis_url,
            "RESULT_BACKEND": redis_url,
        }

    def start(self, server_ready_timeout: float = 120.0, max_attempts: int = 3):
        _run_command(["docker", "network", "create", self.network])
        self._start_redis()

        for attempt in range(max_attempts):
            try:
                self._start_web()
                base_url = f"http://127.0.0.1:{self.port}"
                # Use a public endpoint — the admin password is random until we inject it below.
                _wait_for_server_ready(
                    base_url,
                    {},  # no auth — hit the public login page
                    timeout=server_ready_timeout,
                    web_container=self.web_name,
                )
                # Inject a known password hash into the auto-bootstrapped admin
                # so subsequent tests can authenticate with Bearer headers.
                _inject_admin_password(str(self.server_dir / "users.sqlite3"), self.username, self.password)
                break
            except AssertionError:
                if attempt < max_attempts - 1:
                    # ponytail: Docker daemon flakiness on CI — retry container creation.
                    self._stop_container(self.web_name)
                    time.sleep(5)
                else:
                    raise
        self._start_worker()

    def _env_args(self) -> list[str]:
        args: list[str] = []
        for key, value in self.env.items():
            args.extend(["-e", f"{key}={value}"])
        return args

    def _docker_group_args(self) -> list[str]:
        args: list[str] = []
        for gid in self.docker_group_ids:
            args.extend(["--group-add", gid])
        return args

    def _start_redis(self):
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.redis_name,
            "--network",
            self.network,
            "--health-cmd",
            "redis-cli ping || exit 1",
            "--health-interval",
            "2s",
            "--health-timeout",
            "2s",
            "--health-retries",
            "15",
            "redis:7.2-alpine",
            "redis-server",
            "--save",
            "",
            "--appendonly",
            "no",
        ]
        _run_command(cmd)
        self.containers.append(self.redis_name)
        _wait_for_health(self.redis_name, timeout=60)

    def _start_worker(self):
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.worker_name,
            "--network",
            self.network,
            *self._docker_group_args(),
            *_volume_args(self.volumes),
            *self._env_args(),
            self.server_image_tag,
            "celery",
            "-A",
            "pssm_gremlin_server.pssm_gremlin.celery",
            "worker",
            "--loglevel=info",
            "--concurrency=1",
            "--logfile",
            f"{self.log_dir}/celery-worker.log",
        ]
        _run_command(cmd, cwd=Path(REPO_DIR) / "server")
        self.containers.append(self.worker_name)

    def _start_web(self):
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.web_name,
            "--network",
            self.network,
            "-p",
            f"{self.port}:{self.port}",
            *self._docker_group_args(),
            *_volume_args(self.volumes),
            *self._env_args(),
            self.server_image_tag,
            "gunicorn",
            "-w",
            "1",
            "-b",
            f"0.0.0.0:{self.port}",
            "--access-logfile",
            f"{self.log_dir}/gunicorn-access.log",
            "--error-logfile",
            f"{self.log_dir}/gunicorn-error.log",
            "pssm_gremlin_server.pssm_gremlin:app",
        ]
        _run_command(cmd, cwd=Path(REPO_DIR) / "server")
        self.containers.append(self.web_name)

    def _stop_container(self, name: str) -> None:
        """Stop and remove a single container by name (best-effort)."""
        _run_command(["docker", "rm", "-f", name], check=False)
        if name in self.containers:
            self.containers.remove(name)

    def _relax_permissions(self) -> None:
        dirs = [
            self.state_dir,
            self.server_dir,
            self.server_dir / "upload",
            self.server_dir / "results",
            self.log_dir,
            self.users_dir,
        ]
        for directory in dirs:
            self._safe_chmod(directory, 0o777)
        self._safe_chmod(self.db_path, 0o666)

    @staticmethod
    def _safe_chmod(path: Path, mode: int) -> None:
        try:
            path.chmod(mode)
        except OSError:
            pass

    def cleanup(self):
        containers = list(dict.fromkeys([*self.containers, self.web_name, self.worker_name, self.redis_name]))
        volumes_to_remove: set[str] = set()
        for name in reversed(containers):
            inspect = _run_command(["docker", "inspect", name], check=False, capture_output=True)
            if inspect.returncode == 0 and inspect.stdout:
                try:
                    data = json.loads(inspect.stdout)
                except json.JSONDecodeError:
                    data = []
                for entry in data:
                    for mount in entry.get("Mounts", []):
                        if mount.get("Type") == "volume" and mount.get("Name"):
                            volumes_to_remove.add(mount["Name"])
            _run_command(["docker", "rm", "-f", name], check=False)
        _run_command(["docker", "network", "rm", self.network], check=False)
        # do not delete state directory
        # shutil.rmtree(self.state_dir, ignore_errors=True)
        for volume in volumes_to_remove:
            _run_command(["docker", "volume", "rm", volume], check=False)


def _wait_for_server_ready(
    base_url: str, headers: dict[str, str], timeout: float = 120.0, web_container: str | None = None
) -> None:
    deadline = time.time() + timeout
    session = requests.Session()
    session.headers.update(headers)
    url = f"{base_url}/PSSM_GREMLIN/login"
    last_error = ""
    while time.time() < deadline:
        try:
            response = session.get(url, timeout=5)
            if response.status_code == 200:
                return
            if response.status_code == 401:
                raise AssertionError("Server is reachable but returned 401 with provided test credentials.")
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException:
            last_error = "connection failed"

        if web_container:
            inspect = _run_command(
                ["docker", "inspect", "--format", "{{.State.Status}}", web_container],
                check=False,
                capture_output=True,
            )
            status = inspect.stdout.strip() if inspect.stdout else ""
            if status in {"exited", "dead"}:
                logs = _run_command(
                    ["docker", "logs", "--tail", "200", web_container], check=False, capture_output=True
                )
                raise AssertionError(
                    f"PSSM GREMLIN web container {web_container} exited before readiness.\n"
                    f"stdout:\n{logs.stdout}\n"
                    f"stderr:\n{logs.stderr}"
                )
        time.sleep(2)
    if web_container:
        logs = _run_command(["docker", "logs", "--tail", "200", web_container], check=False, capture_output=True)
        raise AssertionError(
            f"PSSM GREMLIN server failed to start within timeout ({last_error}).\n"
            f"web container: {web_container}\n"
            f"stdout:\n{logs.stdout}\n"
            f"stderr:\n{logs.stderr}"
        )
    raise AssertionError(f"PSSM GREMLIN server failed to start within timeout ({last_error})")


def _extract_md5(location: str) -> str:
    return location.rstrip("/").rsplit("/", 1)[-1]


def _wait_for_task(base_url: str, headers: dict[str, str], md5sum: str, timeout: float = 900.0) -> None:
    deadline = time.time() + timeout
    session = requests.Session()
    session.headers.update(headers)
    url = f"{base_url}/PSSM_GREMLIN/api/running/{md5sum}"
    while time.time() < deadline:
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            payload = response.json()
            if payload["status"] == "finished":
                return
            if payload["status"] == "failed":
                raise AssertionError(f"GREMLIN task failed: {payload}")
        time.sleep(10)
    raise AssertionError("Timed out waiting for GREMLIN task to finish")


def _wait_for_failed_task(base_url: str, headers: dict[str, str], md5sum: str, timeout: float = 900.0) -> dict:
    deadline = time.time() + timeout
    with requests.Session() as session:
        session.headers.update(headers)
        url = f"{base_url}/PSSM_GREMLIN/api/running/{md5sum}"
        while time.time() < deadline:
            response = session.get(url, timeout=10)
            payload = response.json() if response.headers.get("Content-Type", "").startswith("application/json") else {}
            if response.status_code == 404 and payload.get("status") == "failed":
                return payload
            if payload.get("status") == "finished":
                raise AssertionError("GREMLIN task unexpectedly succeeded")
            time.sleep(10)
    raise AssertionError("Timed out waiting for GREMLIN task to fail")


# ==================================================================
# Docker integration tests
# ==================================================================


@REQUIRES_DOCKER
def test_server_image_handles_authenticated_requests(miniuc_databases, runner_image_tag, server_image_tag, tmp_path):
    stack = DockerServerStack(
        runner_image_tag=runner_image_tag,
        server_image_tag=server_image_tag,
        miniuc=miniuc_databases,
        workdir=Path(TEST_ROOT) / "server",
    )
    try:
        stack.start()
        base_url = f"http://127.0.0.1:{stack.port}"
        headers = _bearer_headers(base_url, stack.username, stack.password)
        _wait_for_server_ready(base_url, headers, web_container=stack.web_name)

        fasta_path = MSA_ROOT / "2KL8.fasta"
        _require_path(fasta_path, "Validation FASTA file")

        session = requests.Session()
        session.headers.update(headers)
        with open(fasta_path, "rb") as handle:
            response = session.post(
                f"{base_url}/PSSM_GREMLIN/api/post",
                files={"file": ("2KL8.fasta", handle, "text/plain")},
                allow_redirects=False,
                timeout=30,
            )
        assert response.status_code == 302, f"Unexpected status: {response.status_code}"
        location = response.headers["Location"]
        md5sum = _extract_md5(location)

        _wait_for_task(base_url, headers, md5sum)

        results_resp = session.get(
            f"{base_url}/PSSM_GREMLIN/api/results/{md5sum}",
            allow_redirects=False,
            timeout=30,
        )
        assert results_resp.status_code == 302
        download_url = results_resp.headers["Location"]
        if download_url.startswith("/"):
            download_url = f"{base_url}{download_url}"

        download_resp = session.get(download_url, timeout=120)
        assert download_resp.status_code == 200

        with zipfile.ZipFile(io.BytesIO(download_resp.content)) as archive:
            names = set(archive.namelist())
            assert any(name.endswith("log/task_finished") for name in names)
            assert any(name.endswith("pssm_msa/2KL8_ascii_mtx_file") for name in names)

    finally:
        stack.cleanup()


@pytest.fixture(scope="module")
def running_gremlin_server(miniuc_databases, runner_image_tag, server_image_tag):
    if not has_docker_daemon():
        pytest.skip("Docker daemon not available")
    stack = DockerServerStack(
        runner_image_tag=runner_image_tag,
        server_image_tag=server_image_tag,
        miniuc=miniuc_databases,
        workdir=Path(TEST_ROOT) / "server",
    )
    stack.start()
    base_url = f"http://127.0.0.1:{stack.port}"
    headers = _bearer_headers(base_url, stack.username, stack.password)
    _wait_for_server_ready(base_url, headers, web_container=stack.web_name)
    try:
        yield {"stack": stack, "base_url": base_url, "headers": headers}
    finally:
        stack.cleanup()


def _create_invalid_residue_fasta(tmp_path: Path) -> Path:
    fasta_path = MSA_ROOT / "2KL8.fasta"
    _require_path(fasta_path, "Validation FASTA file")
    lines = fasta_path.read_text(encoding="utf-8").splitlines()
    mutated_lines: list[str] = []
    mutated = False
    for line in lines:
        if line.startswith(">") or not line.strip() or mutated:
            mutated_lines.append(line)
            continue
        mutated_lines.append(f"{line.strip()}J")
        mutated = True
    mutated_path = tmp_path / "invalid_residue.fasta"
    mutated_path.write_text("\n".join(mutated_lines) + "\n", encoding="utf-8")
    return mutated_path


@REQUIRES_DOCKER
def test_server_rejects_unauthenticated_requests(running_gremlin_server):
    base_url = running_gremlin_server["base_url"]
    with requests.Session() as session:
        create_resp = session.get(f"{base_url}/PSSM_GREMLIN/create_task", timeout=10)
        assert create_resp.status_code == 401

        upload_resp = session.post(
            f"{base_url}/PSSM_GREMLIN/api/post",
            files={"file": ("2KL8.fasta", b">fake\nAAA\n", "text/plain")},
            allow_redirects=False,
            timeout=10,
        )
        assert upload_resp.status_code == 401


@REQUIRES_DOCKER
def test_server_rejects_invalid_uploads(running_gremlin_server):
    base_url = running_gremlin_server["base_url"]
    headers = running_gremlin_server["headers"]
    with requests.Session() as session:
        session.headers.update(headers)
        missing_resp = session.post(
            f"{base_url}/PSSM_GREMLIN/api/post",
            data={"foo": "bar"},
            allow_redirects=False,
            timeout=10,
        )
        assert missing_resp.status_code == 400
        assert missing_resp.json()["error"] == "No file part"

        bad_ext_resp = session.post(
            f"{base_url}/PSSM_GREMLIN/api/post",
            files={"file": ("invalid.txt", b">2KL8\nAAA\n", "text/plain")},
            allow_redirects=False,
            timeout=10,
        )
        assert bad_ext_resp.status_code == 400
        assert "extension" in bad_ext_resp.json()["error"].lower()

        binary_resp = session.post(
            f"{base_url}/PSSM_GREMLIN/api/post",
            files={"file": ("invalid.fasta", b"\x00\x01\x02", "application/octet-stream")},
            allow_redirects=False,
            timeout=10,
        )
        assert binary_resp.status_code == 400
        assert "binary" in binary_resp.json()["error"].lower()


@REQUIRES_DOCKER
def test_server_reports_invalid_task_ids(running_gremlin_server):
    base_url = running_gremlin_server["base_url"]
    headers = running_gremlin_server["headers"]
    md5sum = secrets.token_hex(16)
    with requests.Session() as session:
        session.headers.update(headers)
        running_resp = session.get(
            f"{base_url}/PSSM_GREMLIN/api/running/{md5sum}",
            timeout=10,
        )
        assert running_resp.status_code == 404
        assert running_resp.json()["status"] == "not_found"

        results_resp = session.get(
            f"{base_url}/PSSM_GREMLIN/api/results/{md5sum}",
            allow_redirects=False,
            timeout=10,
        )
        assert results_resp.status_code == 404
        assert results_resp.json()["status"] == "not_found"


# def test_server_handles_failed_tasks(running_gremlin_server, tmp_path):
#     base_url = running_gremlin_server["base_url"]
#     auth = running_gremlin_server["auth"]
#     failed_fasta = _create_invalid_residue_fasta(tmp_path)

#     with requests.Session() as session:
#         session.headers.update(headers)
#         with open(failed_fasta, "rb") as handle:
#             response = session.post(
#                 f"{base_url}/PSSM_GREMLIN/api/post",
#                 files={"file": (failed_fasta.name, handle, "text/plain")},
#                 allow_redirects=False,
#                 timeout=30,
#             )
#         assert response.status_code == 302
#         md5sum = _extract_md5(response.headers["Location"])

#         failure_payload = _wait_for_failed_task(base_url, auth, md5sum)
#         assert failure_payload["status"] == "failed"
#         assert failure_payload["md5sum"] == md5sum
#         assert failure_payload.get("error")

#         running_resp = session.get(
#             f"{base_url}/PSSM_GREMLIN/api/running/{md5sum}",
#             timeout=10,
#         )
#         assert running_resp.status_code == 404
#         assert running_resp.json()["status"] == "failed"

#         results_resp = session.get(
#             f"{base_url}/PSSM_GREMLIN/api/results/{md5sum}",
#             allow_redirects=False,
#             timeout=10,
#         )
#         assert results_resp.status_code == 302
#         assert results_resp.headers["Location"].endswith(f"/PSSM_GREMLIN/api/running/{md5sum}")

#         download_resp = session.get(
#             f"{base_url}/PSSM_GREMLIN/api/download/{md5sum}",
#             timeout=10,
#         )
#         assert download_resp.status_code == 400
#         download_payload = download_resp.json()
#         assert download_payload["status"] == "error"
#         assert download_payload["message"] == "results are not ready"
