# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import io
import json
import os
import secrets
import shutil
import time
import uuid
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import docker
import pytest
import requests
from conftest import (
    MSA_ROOT,
    REPO_DIR,
    REQUIRES_DOCKER,
    TEST_ROOT,
    DockerServerStack,
    _bearer_headers,
    _build_image,
    _create_invalid_residue_fasta,
    _determine_runner_identity,
    _extract_md5,
    _find_free_port,
    _inject_admin_password,
    _load_pssm_module,
    _require_path,
    _run_command,
    _runner_build_args,
    _wait_for_failed_task,
    _wait_for_server_ready,
    _wait_for_task,
    has_docker_daemon,
)

# Docker-specific helpers (most are imported from conftest)
# ==================================================================


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
