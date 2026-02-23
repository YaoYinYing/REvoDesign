import base64
import importlib.util
import io
import json
import os
import secrets
import socket
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import docker
import pytest
import requests

from tests.conftest import has_docker, REPO_DIR, TEST_ROOT

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

    def _raise_docker_error(*, fasta_path, output_dir):
        del fasta_path, output_dir
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

    def _fake_runner(*, fasta_path, output_dir):
        del fasta_path
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
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


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

    _run_command(command,cwd=Path(REPO_DIR) / "server")

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
        self._start_worker()
        self._start_web()

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


def _wait_for_server_ready(base_url: str, auth: tuple[str, str], timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    session = requests.Session()
    session.auth = auth
    url = f"{base_url}/PSSM_GREMLIN/create_task"
    while time.time() < deadline:
        try:
            response = session.get(url, timeout=5)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise AssertionError("PSSM GREMLIN server failed to start within timeout")


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


def _wait_for_failed_task(
    base_url: str, auth: tuple[str, str], md5sum: str, timeout: float = 900.0
) -> dict:
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
def test_server_image_handles_authenticated_requests(
    miniuc_databases, runner_image_tag, server_image_tag, tmp_path
):
    stack = DockerServerStack(
        runner_image_tag=runner_image_tag,
        server_image_tag=server_image_tag,
        miniuc=miniuc_databases,
        workdir=Path(TEST_ROOT)/ "server"
    )
    try:
        stack.start()
        base_url = f"http://127.0.0.1:{stack.port}"
        auth = (stack.username, stack.password)
        _wait_for_server_ready(base_url, auth)

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
    _wait_for_server_ready(base_url, auth)
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
