import base64
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
from types import SimpleNamespace

import docker
import pytest
import requests
from werkzeug.utils import secure_filename

from tests.conftest import REPO_DIR, TEST_ROOT, has_docker

MSA_ROOT = Path(REPO_DIR) / "tests" / "data" / "msa"

REQUIRES_DOCKER = pytest.mark.skipif(not has_docker, reason="Docker CLI is required for GREMLIN integration tests.")


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


def _configure_pssm_env(
    monkeypatch,
    tmp_path,
    extra_env: dict | None = None,
    users_text: str | None = None,
) -> None:
    env_root = tmp_path / "pssm_env"
    env_root.mkdir(parents=True, exist_ok=True)
    db_path = env_root / "pssm.sqlite3"
    log_dir = env_root / "logs"
    log_dir.mkdir(exist_ok=True)
    for folder in ("uniref30", "uniref90"):
        (env_root / folder).mkdir(exist_ok=True)
    users_file = env_root / "users.txt"
    users_file.write_text(users_text or "tester:password\n", encoding="utf-8")

    base_env = {
        "SERVER_DIR": str(env_root),
        "DB_PATH": str(db_path),
        "DB_UNIREF30": str(env_root / "uniref30"),
        "DB_UNIREF90": str(env_root / "uniref90"),
        "USERS_FILE": str(users_file),
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


def _load_pssm_module(
    monkeypatch,
    tmp_path,
    extra_env: dict | None = None,
    users_text: str | None = None,
):
    _configure_pssm_env(monkeypatch, tmp_path, extra_env, users_text)
    module_path = Path(REPO_DIR) / "server" / "pssm_gremlin" / "pssm_gremlin.py"
    module_name = f"pssm_gremlin_config_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
        return module
    finally:
        sys.modules.pop(module_name, None)


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
    auth_header = _basic_auth_header("tester", "password")

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
    assert "applyThemeMode(nextMode, true, true);" in html


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


def test_upload_records_headers_and_local_user(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "RUNNER_UID": "1234",
            "RUNNER_GID": "5678",
        },
    )
    monkeypatch.setattr(module, "_local_user_identity", lambda: "pytest:staff-1000:20")

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    auth_header = base64.b64encode(b"tester:password").decode("ascii")
    response = client.post(
        "/PSSM_GREMLIN/api/post",
        data={"file": (io.BytesIO(b">test\nACDE\n"), "upload.fasta")},
        headers={
            "Authorization": f"Basic {auth_header}",
            "X-Test-Header": "abc\tdef",
        },
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


def _basic_auth_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


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
    auth_header = _basic_auth_header("tester", "password")

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
    assert "/srv/REvoDesign/PSSM_GREMLIN/upload/2KL8.fasta" in body
    assert "/Users/yyy/Documents/protein_design/REvoDesign" not in body
    assert 'id="logoutBtn"' in body


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
    auth_header = _basic_auth_header("tester", "password")

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
        users_text="tester:password\nother:password2\n",
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _basic_auth_header("tester", "password")
    other_header = _basic_auth_header("other", "password2")

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
        users_text="tester:password\nother:password2\n",
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _basic_auth_header("tester", "password")
    other_header = _basic_auth_header("other", "password2")

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
    auth_header = _basic_auth_header("tester", "password")

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
        users_text="tester:password\nother:password2\n",
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _basic_auth_header("tester", "password")
    other_header = _basic_auth_header("other", "password2")

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
        users_text="tester:password\nadmin:admin_password\n",
    )
    client = module.app.test_client()
    admin_header = _basic_auth_header("admin", "admin_password")

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
        users_text="tester:password\nother:password2\n",
    )

    class _DummyAsyncResult:
        id = "celery-test-id"

    monkeypatch.setattr(module.run_gremlin_task, "apply_async", lambda *args, **kwargs: _DummyAsyncResult())

    client = module.app.test_client()
    owner_header = _basic_auth_header("tester", "password")
    other_header = _basic_auth_header("other", "password2")

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
        users_text="tester:password\nother:password2\nadmin:admin_password\n",
    )

    client = module.app.test_client()
    owner_header = _basic_auth_header("tester", "password")

    md5sum = uuid.uuid4().hex
    upload_dir = tmp_path / "upload_owner"
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_file = upload_dir / "owner.fasta"
    upload_file.write_text(">owner\nACDE\n", encoding="utf-8")
    result_dir = tmp_path / "delete_owner"
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
        users_text="tester:password\n",
    )

    client = module.app.test_client()
    auth_header = _basic_auth_header("tester", "password")

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
        users_text="tester:password\n",
    )
    client = module.app.test_client()
    owner_header = _basic_auth_header("tester", "password")

    md5sum = uuid.uuid4().hex
    upload_file = tmp_path / "upload_pending.fasta"
    upload_file.write_text(">pending\nACDE\n", encoding="utf-8")
    result_dir = tmp_path / "delete_pending"
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
        users_text="tester:password\nother:password2\nadmin:admin_password\n",
    )

    client = module.app.test_client()
    other_header = _basic_auth_header("other", "password2")

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
        users_text="tester:password\n",
    )

    client = module.app.test_client()
    auth_header = _basic_auth_header("tester", "password")

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
        users_text="tester:password\nother:password2\nadmin:admin_password\n",
    )

    client = module.app.test_client()
    admin_header = _basic_auth_header("admin", "admin_password")

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
        users_text="tester:password\nadmin:admin_password\n",
    )

    client = module.app.test_client()
    admin_header = _basic_auth_header("admin", "admin_password")

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
        users_text="tester:password\nother:password2\nadmin:admin_password\n",
    )

    client = module.app.test_client()
    user_header = _basic_auth_header("tester", "password")

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
        users_text="tester:password\n",
    )
    client = module.app.test_client()
    auth_header = _basic_auth_header("tester", "password")

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


def _current_docker_user() -> str:
    try:
        return f"{os.getuid()}:{os.getgid()}"
    except AttributeError:
        return "0:0"


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
@REQUIRES_DOCKER
def runner_image_tag(miniuc_databases) -> str:
    _ = miniuc_databases
    tag = f"revodesign-pssm-gremlin-runner-test:{uuid.uuid4().hex[:12]}"
    _build_image(tag, "server/docker/runner/Dockerfile", "server", build_args=_runner_build_args())
    yield tag
    _run_command(["docker", "rmi", "-f", tag], check=False)


@pytest.fixture(scope="session")
@REQUIRES_DOCKER
def server_image_tag(miniuc_databases) -> str:
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
        "--user",
        _current_docker_user(),
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
        self.users_file = self.users_dir / "users.txt"
        password = f"test_password_{secrets.token_hex(32)}"
        self.username = "test_username"
        self.password = password
        self.users_file.write_text(f"{self.username}:{self.password}\n", encoding="utf-8")
        self.db_path = self.state_dir / "pssm_gremlin.sqlite3"
        self.db_path.touch()
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
            "USERS_FILE": str(self.users_file),
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

    def start(self):
        _run_command(["docker", "network", "create", self.network])
        self._start_redis()
        self._start_web()
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
            "pssm_gremlin.celery",
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
            "pssm_gremlin:app",
        ]
        _run_command(cmd, cwd=Path(REPO_DIR) / "server")
        self.containers.append(self.web_name)

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
        for file_path in (self.db_path, self.users_file):
            self._safe_chmod(file_path, 0o666)

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
    base_url: str, auth: tuple[str, str], timeout: float = 120.0, web_container: str | None = None
) -> None:
    deadline = time.time() + timeout
    session = requests.Session()
    readiness_url = f"{base_url}/favicon.ico"
    auth_url = f"{base_url}/PSSM_GREMLIN/create_task"
    auth_headers = _basic_auth_header(auth[0], auth[1])
    last_error = ""
    unauthorized_count = 0
    while time.time() < deadline:
        try:
            readiness = session.get(readiness_url, timeout=5, allow_redirects=False)
            if readiness.status_code not in {200, 304}:
                last_error = f"readiness probe returned HTTP {readiness.status_code}"
                time.sleep(2)
                continue

            response = session.get(auth_url, timeout=5, headers=auth_headers, allow_redirects=False)
            if response.status_code == 200:
                return
            if response.status_code == 401:
                # CI can occasionally observe an early auth race while Gunicorn workers
                # finish initialization; retry until timeout before declaring bad creds.
                unauthorized_count += 1
                last_error = f"HTTP 401 ({unauthorized_count} unauthorized responses)"
                time.sleep(2)
                continue
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            last_error = f"connection failed ({exc.__class__.__name__})"

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
        if unauthorized_count:
            raise AssertionError(
                "PSSM GREMLIN server remained unauthorized for provided test credentials "
                f"({unauthorized_count} HTTP 401 responses).\n"
                f"web container: {web_container}\n"
                f"stdout:\n{logs.stdout}\n"
                f"stderr:\n{logs.stderr}"
            )
        raise AssertionError(
            f"PSSM GREMLIN server failed to start within timeout ({last_error}).\n"
            f"web container: {web_container}\n"
            f"stdout:\n{logs.stdout}\n"
            f"stderr:\n{logs.stderr}"
        )
    if unauthorized_count:
        raise AssertionError(
            "PSSM GREMLIN server remained unauthorized for provided test credentials "
            f"({unauthorized_count} HTTP 401 responses)."
        )
    raise AssertionError(f"PSSM GREMLIN server failed to start within timeout ({last_error})")


def test_wait_for_server_ready_retries_transient_401(monkeypatch):
    auth_attempts = {"count": 0}
    expected_auth = _basic_auth_header("tester", "password")["Authorization"]

    class _StubSession:
        def get(self, url, timeout=5, headers=None, allow_redirects=False):
            del timeout, allow_redirects
            if url.endswith("/favicon.ico"):
                return SimpleNamespace(status_code=200)
            if url.endswith("/PSSM_GREMLIN/create_task"):
                if not headers or headers.get("Authorization") != expected_auth:
                    return SimpleNamespace(status_code=401)
                if auth_attempts["count"] == 0:
                    auth_attempts["count"] += 1
                    return SimpleNamespace(status_code=401)
                return SimpleNamespace(status_code=200)
            return SimpleNamespace(status_code=404)

    monkeypatch.setattr(requests, "Session", lambda: _StubSession())
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)

    _wait_for_server_ready("http://127.0.0.1:9999", ("tester", "password"), timeout=5.0)


def _extract_md5(location: str) -> str:
    return location.rstrip("/").rsplit("/", 1)[-1]


def _wait_for_task(base_url: str, auth: tuple[str, str], md5sum: str, timeout: float = 900.0) -> None:
    deadline = time.time() + timeout
    session = requests.Session()
    session.auth = auth
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


def _wait_for_failed_task(base_url: str, auth: tuple[str, str], md5sum: str, timeout: float = 900.0) -> dict:
    deadline = time.time() + timeout
    with requests.Session() as session:
        session.auth = auth
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
        auth = (stack.username, stack.password)
        _wait_for_server_ready(base_url, auth, web_container=stack.web_name)

        fasta_path = MSA_ROOT / "2KL8.fasta"
        _require_path(fasta_path, "Validation FASTA file")

        session = requests.Session()
        session.auth = auth
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

        _wait_for_task(base_url, auth, md5sum)

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
@REQUIRES_DOCKER
def running_gremlin_server(miniuc_databases, runner_image_tag, server_image_tag):
    stack = DockerServerStack(
        runner_image_tag=runner_image_tag,
        server_image_tag=server_image_tag,
        miniuc=miniuc_databases,
        workdir=Path(TEST_ROOT) / "server",
    )
    stack.start()
    base_url = f"http://127.0.0.1:{stack.port}"
    auth = (stack.username, stack.password)
    _wait_for_server_ready(base_url, auth, web_container=stack.web_name)
    try:
        yield {"stack": stack, "base_url": base_url, "auth": auth}
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
    auth = running_gremlin_server["auth"]
    with requests.Session() as session:
        session.auth = auth
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
    auth = running_gremlin_server["auth"]
    md5sum = secrets.token_hex(16)
    with requests.Session() as session:
        session.auth = auth
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
#         session.auth = auth
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
