# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""pytest configuration and shared helpers for pssm_gremlin_server tests.

Run from the repo root::

    pytest server/tests/ -k "not Docker and not docker"
"""

from __future__ import annotations

import importlib.util
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import docker
import pytest
import requests
from werkzeug.utils import secure_filename

# ── path setup ────────────────────────────────────────────────────────────────

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

REPO_DIR = str(Path(__file__).resolve().parent.parent.parent)
TEST_ROOT = str(Path(__file__).resolve().parent.parent)

# ── Docker availability ────────────────────────────────────────────────────────


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


# ── runner identity helpers ────────────────────────────────────────────────────


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


# ── module loader ──────────────────────────────────────────────────────────────


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
        _pg.__dict__.pop("pssm_gremlin", None)
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
            _pg.__dict__.pop("pssm_gremlin", None)


# ── test client auth helpers ───────────────────────────────────────────────────


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


# ── live-server helpers ────────────────────────────────────────────────────────


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


def _extract_md5(location: str) -> str:
    return location.rstrip("/").rsplit("/", 1)[-1]


# ── Docker integration helpers ─────────────────────────────────────────────────


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


def _volume_args(bindings: Iterable[tuple[str, str, str]]) -> list[str]:
    args: list[str] = []
    for host_path, container_path, mode in bindings:
        args.extend(["-v", f"{host_path}:{container_path}:{mode}"])
    return args


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


# ── Docker stack fixture ───────────────────────────────────────────────────────


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
                _wait_for_server_ready(
                    base_url,
                    {},
                    timeout=server_ready_timeout,
                    web_container=self.web_name,
                )
                _inject_admin_password(str(self.server_dir / "users.sqlite3"), self.username, self.password)
                break
            except AssertionError:
                if attempt < max_attempts - 1:
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
        for volume in volumes_to_remove:
            _run_command(["docker", "volume", "rm", volume], check=False)
