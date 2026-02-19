import importlib
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

MODULE_PATH = "server.pssm_gremlin.pssm_gremlin"


def _load_module(monkeypatch, tmp_path, extra_env=None):
    users_file = tmp_path / "users.txt"
    users_file.write_text("test:password\n", encoding="utf-8")
    server_dir = tmp_path / "srv"
    db30 = tmp_path / "db30"
    db90 = tmp_path / "db90"

    for path in (server_dir, db30, db90):
        path.mkdir(parents=True, exist_ok=True)

    env = {
        "PSSM_GREMLIN_SERVER_DIR": str(server_dir),
        "PSSM_GREMLIN_DB_UNIREF30": str(db30),
        "PSSM_GREMLIN_DB_UNIREF90": str(db90),
        "PSSM_GREMLIN_USERS_FILE": str(users_file),
        "PSSM_GREMLIN_REDIS_URL": "redis://redis:6379/0",
        "PSSM_GREMLIN_BROKER_URL": "redis://redis:6379/0",
        "PSSM_GREMLIN_RESULT_BACKEND": "redis://redis:6379/0",
        "PSSM_GREMLIN_RUNNER_IMAGE": "revodesign-pssm-gremlin-test",
        "PSSM_GREMLIN_RUNNER_UID": "1000",
        "PSSM_GREMLIN_RUNNER_GID": "1000",
        "PSSM_GREMLIN_NPROC": "4",
        "PSSM_GREMLIN_PORT": "8081",
    }

    if extra_env:
        env.update(extra_env)

    for key, value in env.items():
        monkeypatch.setenv(key, str(value))

    if MODULE_PATH in sys.modules:
        del sys.modules[MODULE_PATH]

    return importlib.import_module(MODULE_PATH)


def test_configuration_comes_from_environment(monkeypatch, tmp_path):
    module = _load_module(
        monkeypatch,
        tmp_path,
        extra_env={
            "PSSM_GREMLIN_PORT": "9090",
            "PSSM_GREMLIN_NPROC": "32",
            "PSSM_GREMLIN_RUNNER_UID": "123",
            "PSSM_GREMLIN_RUNNER_GID": "321",
        },
    )

    assert module.PORT == 9090
    assert module.NPROC == 32
    assert module.DOCKER_USER == "123:321"
    assert os.path.isdir(module.app.config["UPLOAD_FOLDER"])  # directories created eagerly


class _FakeContainer:
    def __init__(self):
        self.killed = False

    def logs(self, stream=True):  # pragma: no cover - deterministic output
        yield b"done"

    def kill(self):  # pragma: no cover - used by signal handler
        self.killed = True


class _FakeDocker:
    def __init__(self):
        self.calls = []
        self.containers = self

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeContainer()


def test_run_pssm_gremlin_mounts_expected_directories(monkeypatch, tmp_path):
    module = _load_module(monkeypatch, tmp_path)

    fasta_path = tmp_path / "input.fasta"
    fasta_path.write_text(
        ">seq\nAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    fake_client = _FakeDocker()
    module.run_pssm_gremlin_in_docker(str(fasta_path), str(output_dir), docker_client=fake_client)

    assert len(fake_client.calls) == 1
    kwargs = fake_client.calls[0]
    assert kwargs["image"] == module.DOCKER_IMAGE
    assert kwargs["user"] == module.DOCKER_USER
    assert kwargs["remove"] is True
    assert kwargs["detach"] is True
    assert any("-i" in arg for arg in kwargs["command"])
    assert any(not mount.read_only for mount in kwargs["mounts"])  # writable output mount


def _require_docker():
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI not available")
    try:
        subprocess.run(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover - best-effort check
        pytest.skip(f"Docker daemon unavailable: {exc}")


def test_server_docker_image_builds():
    _require_docker()
    repo_root = Path(__file__).resolve().parents[2]
    tag = f"revodesign-pssm-gremlin-server-test:{uuid.uuid4().hex}"
    build_cmd = ["docker", "build", "-f", "server/docker/server/Dockerfile", "-t", tag, "."]
    try:
        subprocess.run(build_cmd, cwd=repo_root, check=True)
    finally:
        subprocess.run(
            ["docker", "rmi", "-f", tag],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
