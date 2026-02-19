import io
import os
import secrets
import socket
import shutil
import subprocess
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pytest
import requests

from tests.conftest import has_docker,REPO_DIR, TEST_ROOT

MSA_ROOT = Path(REPO_DIR) / "tests" / "data" / "msa"

pytestmark = pytest.mark.skipif(not has_docker, reason="Docker CLI is required for GREMLIN integration tests.")


def _run_command(
    command: list[str],
    *,
    env: dict | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(REPO_DIR),
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


def _require_path(path: Path, description: str) -> None:
    if not path.exists():
        pytest.skip(f"{description} not found at {path}. Rebuild the mock databases via tests/data/msa/README.md")


def _build_image(tag: str, dockerfile: str, context: str) -> None:
    _run_command(["docker", "build", "-t", tag, "-f", dockerfile, context])


@pytest.fixture(scope="session")
def runner_image_tag(miniuc_databases) -> str:
    _ = miniuc_databases
    tag = f"revodesign-pssm-gremlin-runner-test:{uuid.uuid4().hex[:12]}"
    _build_image(tag, "server/docker/runner/Dockerfile", "server")
    yield tag
    _run_command(["docker", "rmi", "-f", tag], check=False)


@pytest.fixture(scope="session")
def server_image_tag(miniuc_databases) -> str:
    _ = miniuc_databases
    tag = f"revodesign-pssm-gremlin-server-test:{uuid.uuid4().hex[:12]}"
    _build_image(tag, "server/docker/server/Dockerfile", ".")
    yield tag
    _run_command(["docker", "rmi", "-f", tag], check=False)


def _volume_args(bindings: Iterable[tuple[str, str, str]]) -> list[str]:
    args: list[str] = []
    for host_path, container_path, mode in bindings:
        args.extend(["-v", f"{host_path}:{container_path}:{mode}"])
    return args


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

    _run_command(command)

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
        self.state_dir = self.workdir / "server_state"
        if self.state_dir.exists():
            shutil.rmtree(self.state_dir, ignore_errors=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
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
        self.containers: list[str] = []
        self.volumes = [
            (str(self.state_dir), str(self.state_dir), "rw"),
            (self.miniuc["uniref30_mount"], self.miniuc["uniref30_mount"], "ro"),
            (self.miniuc["uniref90_mount"], self.miniuc["uniref90_mount"], "ro"),
            ("/var/run/docker.sock", "/var/run/docker.sock", "rw"),
        ]
        redis_url = f"redis://{self.redis_name}:6379/0"
        self.env = {
            "PSSM_GREMLIN_SERVER_DIR": str(self.server_dir),
            "PSSM_GREMLIN_DB_PATH": str(self.db_path),
            "PSSM_GREMLIN_DB_UNIREF30": self.miniuc["uniref30_prefix"],
            "PSSM_GREMLIN_DB_UNIREF90": self.miniuc["uniref90_prefix"],
            "PSSM_GREMLIN_USERS_FILE": str(self.users_file),
            "PSSM_GREMLIN_LOG_DIR": str(self.log_dir),
            "PSSM_GREMLIN_NPROC": "4",
            "PSSM_GREMLIN_GUNICORN_WORKERS": "2",
            "PSSM_GREMLIN_WORKER_CONCURRENCY": "2",
            "PSSM_GREMLIN_RUNNER_IMAGE": self.runner_image_tag,
            "PSSM_GREMLIN_RUNNER_UID": str(getattr(os, "getuid", lambda: 0)()),
            "PSSM_GREMLIN_RUNNER_GID": str(getattr(os, "getgid", lambda: 0)()),
            "PSSM_GREMLIN_PORT": str(self.port),
            "PSSM_GREMLIN_REDIS_URL": redis_url,
            "PSSM_GREMLIN_BROKER_URL": redis_url,
            "PSSM_GREMLIN_RESULT_BACKEND": redis_url,
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
        _run_command(cmd)
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
        _run_command(cmd)
        self.containers.append(self.web_name)

    def cleanup(self):
        for name in reversed(self.containers):
            _run_command(["docker", "rm", "-f", name], check=False)
        _run_command(["docker", "network", "rm", self.network], check=False)
        shutil.rmtree(self.state_dir, ignore_errors=True)


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
            if payload["status"] == "success":
                return
            if payload["status"] == "failed":
                raise AssertionError(f"GREMLIN task failed: {payload}")
        time.sleep(10)
    raise AssertionError("Timed out waiting for GREMLIN task to finish")


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
