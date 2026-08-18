# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the revocompute_ctl deployment control module.

Two shims stand in for docker:
- the PATH shim logs argv, answers ``image inspect --format`` from a
  tag→id map (empty ids mean "unknown", which keeps every no-op path honest),
  and executes ``docker run ... -c SCRIPT`` with mount targets rewritten to
  the host paths — so stamp, backup, and sentinel round-trips are real.
- the apptainer shim creates the staged .sif output.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parents[1]
RUN_DIR = SERVER_DIR / "run"
if str(RUN_DIR) not in sys.path:
    sys.path.insert(0, str(RUN_DIR))

from conftest import REPO_DIR, _load_pssm_module, _test_client_auth  # noqa: E402
from revocompute_ctl import drain as drain_mod  # noqa: E402
from revocompute_ctl import promotion  # noqa: E402
from revocompute_ctl import stamp as stamp_mod  # noqa: E402
from revocompute_ctl.env import EnvState, parse_env_file  # noqa: E402
from revocompute_ctl.registry import RuntimeFamily, build_slurm_images  # noqa: E402
from revocompute_ctl.steps import Step, StepRegistry, run_walk  # noqa: E402

RUNNER_IMAGE = "revodesign-revocompute-runner"

_DOCKER_SHIM = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    printf "%s\\n" "$*" >> "${SHIM_LOG}"
    if [[ "$1" == "compose" && "$*" == *" ps --status running --services"* ]]; then
      printf "redis\\nweb\\ngateway\\nmaintenance\\nworker\\n"
      exit 0
    fi
    if [[ "$1" == "image" && "$2" == "inspect" && "$3" == "--format" ]]; then
      img="${@: -1}"
      grep -F "${img}=" "${SHIM_IDS}" 2>/dev/null | head -1 | cut -d= -f2- || true
      exit 0
    fi
    if [[ "$1" == "run" ]]; then
      declare -a subs=()
      prev=""
      for arg in "$@"; do
        if [[ "$prev" == "-v" ]]; then
          subs+=("-e" "s|${arg#*:}|${arg%%:*}|g")
        fi
        prev="$arg"
      done
      script="${@: -1}"
      transformed="$script"
      for ((i=0; i<${#subs[@]}; i+=2)); do
        transformed="$(printf '%s' "$transformed" | sed "${subs[$i]}" "${subs[$((i+1))]}")"
      done
      sh -c "$transformed"
      exit $?
    fi
    exit 0
    """
)

_APPTAINER_SHIM = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    printf "%s\\n" "$*" >> "${SHIM_LOG}"
    if [[ "${APPTAINER_FAIL:-0}" == "1" ]]; then exit 1; fi
    touch "${3}"
    """
)


def _write_shims(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    docker.write_text(_DOCKER_SHIM, encoding="utf-8")
    docker.chmod(0o755)
    apptainer = bin_dir / "apptainer"
    apptainer.write_text(_APPTAINER_SHIM, encoding="utf-8")
    apptainer.chmod(0o755)
    return bin_dir


def _shimmed_state(monkeypatch, tmp_path: Path, bin_dir: Path, ids: dict[str, str], **values) -> tuple[EnvState, Path]:
    ids_file = tmp_path / "ids.txt"
    ids_file.write_text("".join(f"{key}={value}\n" for key, value in ids.items()), encoding="utf-8")
    monkeypatch.setenv("SHIM_IDS", str(ids_file))
    log = tmp_path / "docker.log"
    monkeypatch.setenv("SHIM_LOG", str(log))
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    state = EnvState(str(tmp_path / "fake.env"), values=dict(values))
    return state, log


def _deploy_env(tmp_path: Path, config_dir: Path | None = None) -> tuple[Path, Path, Path]:
    """SERVER_DIR + AUTH_DIR + env file, the harness shape."""
    task_dir = tmp_path / "tasks"
    auth_dir = tmp_path / "auth"
    log_dir = tmp_path / "logs"
    for path in (task_dir, auth_dir, log_dir):
        path.mkdir(parents=True, exist_ok=True)
    os.chmod(auth_dir, 0o777)
    results_dir = task_dir / "results"
    results_dir.mkdir(exist_ok=True)
    os.chmod(results_dir, 0o777)
    lines = [
        f"SERVER_DIR={task_dir}",
        f"AUTH_DIR={auth_dir}",
        f"LOG_DIR={log_dir}",
        "ADMIN_USERS=admin",
        "RUNNER_UID=1000",
        "RUNNER_GID=1000",
        "RUNNER_USERNAME=revodesign",
        "RUNNER_GROUP=revodesign",
        "SERVER_IMAGE=example/revodesign-server:latest",
    ]
    if config_dir is not None:
        lines.append(f"CONFIG_DIR={config_dir}")
    env_file = tmp_path / "server.env"
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return task_dir, auth_dir, env_file


def _run_cli(
    monkeypatch, tmp_path: Path, env_file: Path, bin_dir: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"REVODESIGN_SERVER_ENV": str(env_file), "DOCKER_GID": "0", "PATH": f"{bin_dir}:{env['PATH']}"})
    return subprocess.run(
        ["bash", str(Path(REPO_DIR) / "server" / "run" / "restart.sh"), *args],
        cwd=REPO_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def _mutating_commands(log: Path) -> list[str]:
    """The tag/rmi subset of the shim log — the mutations promotion makes."""
    return [line for line in log.read_text(encoding="utf-8").splitlines() if line.startswith(("tag ", "rmi "))]


# -- registry invariant -------------------------------------------------------


def test_step_registry_requires_stop_last():
    registry = StepRegistry()
    with pytest.raises(ValueError, match="stop"):
        registry.add("x", [Step("a", lambda: None)])
    registry.add("x", [Step("a", lambda: None), Step("stop", lambda: None)])
    assert [step.name for step in registry.get("x")] == ["a", "stop"]


def test_walk_runs_completed_cleanups_in_reverse_on_failure():
    events: list[str] = []

    def fail() -> None:
        events.append("run:b")
        raise RuntimeError("boom")

    walk = [
        Step("a", lambda: events.append("run:a"), cleanup=lambda: events.append("cleanup:a")),
        Step("b", fail, cleanup=lambda: events.append("cleanup:b")),
    ]
    with pytest.raises(RuntimeError):
        run_walk(walk)
    assert events == ["run:a", "run:b", "cleanup:a"]  # b's own cleanup is caller's job


# -- env parsing --------------------------------------------------------------


def test_env_file_parsing_and_redis_password_round_trip(tmp_path):
    env_file = tmp_path / "server.env"
    env_file.write_text("# comment\nexport A=1\nB=\"two\"\nC='three'\n", encoding="utf-8")
    assert parse_env_file(env_file) == {"A": "1", "B": "two", "C": "three"}

    env_file.write_text("REDIS_URL=redis://redis:6379/0\nBROKER_URL=redis://127.0.0.1:6380/0\n", encoding="utf-8")
    password = EnvState(str(env_file)).ensure_redis_password()
    assert len(password) == 48
    text = env_file.read_text(encoding="utf-8")
    assert f"REDIS_URL=redis://:{password}@redis:6379/0" in text
    assert f"BROKER_URL=redis://:{password}@127.0.0.1:6380/0" in text
    # A second process reuses the persisted secret instead of regenerating.
    assert EnvState(str(env_file)).ensure_redis_password() == password


def test_env_state_precedence_runtime_over_file_over_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNNER_UID", "999")
    state = EnvState(str(tmp_path / "fake.env"), values={"RUNNER_UID": "888"})
    assert state.get("RUNNER_UID") == "888"  # file beats environment
    state.runtime["RUNNER_UID"] = "777"  # the shell's later export wins
    assert state.get("RUNNER_UID") == "777"


# -- promotion ----------------------------------------------------------------


def test_promotion_order_tags_previous_before_rmi(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    state, log = _shimmed_state(
        monkeypatch,
        tmp_path,
        bin_dir,
        {f"{RUNNER_IMAGE}:next": "sha256:new", f"{RUNNER_IMAGE}:latest": "sha256:old"},
    )
    promotion.promote_docker(state, {"gremlin": RUNNER_IMAGE}, {}, "dev")
    assert _mutating_commands(log) == [
        f"tag {RUNNER_IMAGE}:latest {RUNNER_IMAGE}:previous",
        f"rmi {RUNNER_IMAGE}:latest",
        f"tag {RUNNER_IMAGE}:next {RUNNER_IMAGE}:latest",
    ]


def test_promotion_cache_hit_has_zero_churn(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    state, log = _shimmed_state(
        monkeypatch,
        tmp_path,
        bin_dir,
        {f"{RUNNER_IMAGE}:next": "sha256:same", f"{RUNNER_IMAGE}:latest": "sha256:same"},
    )
    promotion.promote_docker(state, {"gremlin": RUNNER_IMAGE}, {}, "dev")
    assert _mutating_commands(log) == [f"rmi {RUNNER_IMAGE}:next"]


def test_promotion_first_deploy_skips_previous(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    state, log = _shimmed_state(monkeypatch, tmp_path, bin_dir, {f"{RUNNER_IMAGE}:next": "sha256:new"})
    promotion.promote_docker(state, {"gremlin": RUNNER_IMAGE}, {}, "dev")
    assert _mutating_commands(log) == [f"tag {RUNNER_IMAGE}:next {RUNNER_IMAGE}:latest"]


def test_promotion_empty_ids_are_a_no_op(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    state, log = _shimmed_state(monkeypatch, tmp_path, bin_dir, {})
    promotion.promote_docker(state, {"gremlin": RUNNER_IMAGE}, {}, "dev")
    assert _mutating_commands(log) == []


def test_promotion_prod_retags_previous_from_pre_pull_baseline(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    state, log = _shimmed_state(monkeypatch, tmp_path, bin_dir, {f"{RUNNER_IMAGE}:latest": "sha256:new"})
    promotion.promote_docker(
        state, {"gremlin": RUNNER_IMAGE}, {"gremlin": {"latest": "sha256:old", "next": ""}}, "prod"
    )
    assert _mutating_commands(log) == [f"tag sha256:old {RUNNER_IMAGE}:previous"]


def test_promotion_prod_unchanged_retags_nothing(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    state, log = _shimmed_state(monkeypatch, tmp_path, bin_dir, {f"{RUNNER_IMAGE}:latest": "sha256:same"})
    promotion.promote_docker(
        state, {"gremlin": RUNNER_IMAGE}, {"gremlin": {"latest": "sha256:same", "next": ""}}, "prod"
    )
    assert _mutating_commands(log) == []


def test_promotion_dev_retags_previous_from_baseline_for_nextless_images(tmp_path, monkeypatch):
    """The server image has no :next (compose build replaces latest in
    place) — dev promotion must tag previous from the pre-build baseline id
    so rollback can restore it."""
    bin_dir = _write_shims(tmp_path)
    state, log = _shimmed_state(monkeypatch, tmp_path, bin_dir, {"revodesign-server:latest": "sha256:new"})
    promotion.promote_docker(
        state, {"server": "revodesign-server"}, {"server": {"latest": "sha256:old", "next": ""}}, "dev"
    )
    assert _mutating_commands(log) == ["tag sha256:old revodesign-server:previous"]


def test_sif_staging_builds_missing_skips_unchanged(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    sif_dir = tmp_path / "sifs"
    sif_dir.mkdir()
    family = RuntimeFamily(
        "gremlin",
        RUNNER_IMAGE,
        "docker/runners/pssm_gremlin/Dockerfile",
        "docker/runners/pssm_gremlin/gremlin.def",
        str(sif_dir / "gremlin.sif"),
    )
    state, _log = _shimmed_state(monkeypatch, tmp_path, bin_dir, {})
    build_slurm_images(state, [family], set())  # missing SIF → stage .next
    assert (sif_dir / "gremlin.sif.next").is_file()

    (sif_dir / "gremlin.sif.next").unlink()
    (sif_dir / "gremlin.sif").touch()
    build_slurm_images(state, [family], set())  # unchanged → skip
    assert not (sif_dir / "gremlin.sif.next").exists()

    build_slurm_images(state, [family], {"gremlin"})  # changed → stage
    assert (sif_dir / "gremlin.sif.next").is_file()


def test_sif_staging_drops_failed_runner_from_enabled_list(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    monkeypatch.setenv("APPTAINER_FAIL", "1")
    sif_dir = tmp_path / "sifs"
    sif_dir.mkdir()
    family = RuntimeFamily(
        "gremlin",
        RUNNER_IMAGE,
        "docker/runners/pssm_gremlin/Dockerfile",
        "docker/runners/pssm_gremlin/gremlin.def",
        str(sif_dir / "gremlin.sif"),
    )
    state, _log = _shimmed_state(monkeypatch, tmp_path, bin_dir, {})
    build_slurm_images(state, [family], set())
    assert state.get("ENABLED_TASKRUNNERS") == ""  # dropped for the run


# -- stamp / backup / drain round-trips through the container transport -------


def test_stamp_round_trip_and_config_backup(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    task_dir, _auth_dir, _env = _deploy_env(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "task_types.yaml").write_text("job_executor: docker\n", encoding="utf-8")
    state, _log = _shimmed_state(
        monkeypatch, tmp_path, bin_dir, {}, SERVER_DIR=str(task_dir), CONFIG_DIR=str(config_dir)
    )

    backup = stamp_mod.backup_config(state)
    assert (Path(backup) / "task_types.yaml").is_file()

    stamp_mod.write_stamp(state, {"commit": "abc", "mode": "prepared"})
    stamp_path = config_dir / ".deploy-stamp"
    assert stamp_path.is_file()
    assert stamp_mod.load_stamp(state) == {"commit": "abc", "mode": "prepared"}


def test_drain_sentinel_lifecycle(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    task_dir, _auth_dir, _env = _deploy_env(tmp_path)
    state, _log = _shimmed_state(monkeypatch, tmp_path, bin_dir, {}, SERVER_DIR=str(task_dir))
    drain_mod.begin_drain(state, 1)  # docker executor: sentinel only, no squeue wait
    assert (task_dir / ".maintenance").is_file()
    drain_mod.end_drain(state)
    assert not (task_dir / ".maintenance").exists()


# -- proxy broadcasting -------------------------------------------------------


def test_proxy_broadcasts_to_subprocess_env_without_leaking_output(tmp_path, monkeypatch):
    """--use-proxy must reach every subprocess environment (the shell's
    global export) while the URL never appears in the ctl's own output."""
    proxy_url = "http://test-user:test-password@proxy.invalid:8080"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    env_dumper = bin_dir / "docker"
    env_dumper.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "HTTP_PROXY=${HTTP_PROXY}" "HTTPS_PROXY=${HTTPS_PROXY}" '
        '"NO_PROXY=${NO_PROXY}" >> "${SHIM_LOG}"\nif [[ "$*" == *" ps --status running --services"* ]]; then '
        'printf "redis\\nweb\\ngateway\\nmaintenance\\nworker\\n"; fi\n',
        encoding="utf-8",
    )
    env_dumper.chmod(0o755)
    task_dir, _auth_dir, env_file = _deploy_env(tmp_path)
    monkeypatch.setenv("SHIM_LOG", str(tmp_path / "docker.log"))
    monkeypatch.delenv("NO_PROXY", raising=False)  # the shell default must apply
    result = _run_cli(monkeypatch, tmp_path, env_file, bin_dir, "build", f"--use-proxy={proxy_url}")

    assert result.returncode == 0, result.stderr
    assert proxy_url not in result.stdout
    assert proxy_url not in result.stderr
    broadcast = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert f"HTTP_PROXY={proxy_url}" in broadcast
    assert f"HTTPS_PROXY={proxy_url}" in broadcast
    assert "NO_PROXY=localhost,127.0.0.1,.local" in broadcast


# -- dry-run ------------------------------------------------------------------


def test_dry_run_predicts_and_writes_nothing(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    task_dir, _auth_dir, env_file = _deploy_env(tmp_path)
    monkeypatch.setenv("SHIM_IDS", str(tmp_path / "ids.txt"))
    monkeypatch.setenv("SHIM_LOG", str(tmp_path / "docker.log"))
    result = _run_cli(monkeypatch, tmp_path, env_file, bin_dir, "restart", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "Planned restart walk:" in result.stdout
    assert "Image changes:" in result.stdout
    commands = (tmp_path / "docker.log").read_text(encoding="utf-8").splitlines()
    assert all("version" in command or "image inspect" in command for command in commands)
    assert not (task_dir / "backups").exists()
    assert not (task_dir / ".maintenance").exists()
    assert not (SERVER_DIR / "config" / ".deploy-stamp").exists()


# -- rollback -----------------------------------------------------------------


def test_rollback_refuses_without_stamp(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    _task_dir, _auth_dir, env_file = _deploy_env(tmp_path)
    monkeypatch.setenv("SHIM_IDS", str(tmp_path / "ids.txt"))
    monkeypatch.setenv("SHIM_LOG", str(tmp_path / "docker.log"))
    result = _run_cli(monkeypatch, tmp_path, env_file, bin_dir, "restart", "--rollback")

    assert result.returncode != 0
    assert "No deploy stamp found" in result.stderr


def test_rollback_restores_previous_set_and_config(tmp_path, monkeypatch):
    bin_dir = _write_shims(tmp_path)
    config_dir = tmp_path / "config"
    shutil.copytree(Path(REPO_DIR) / "server" / "config", config_dir)
    task_dir, _auth_dir, env_file = _deploy_env(tmp_path, config_dir)

    ids = {f"{RUNNER_IMAGE}:previous": "sha256:prev", f"{RUNNER_IMAGE}:latest": "sha256:bad"}
    state, _log = _shimmed_state(
        monkeypatch, tmp_path, bin_dir, ids, SERVER_DIR=str(task_dir), CONFIG_DIR=str(config_dir)
    )
    backup = stamp_mod.backup_config(state)
    stamp_mod.write_stamp(
        state,
        {
            "commit": "abc123",
            "mode": "prepared",
            "changed": ["gremlin"],
            "config_backup": backup,
            "registry_sha256": stamp_mod.registry_sha256(str(config_dir)),
        },
    )
    # Drift the registry in a validation-neutral way.
    registry_file = config_dir / "task_types.yaml"
    registry_file.write_text(registry_file.read_text(encoding="utf-8") + "\n# drifted\n", encoding="utf-8")

    result = _run_cli(monkeypatch, tmp_path, env_file, bin_dir, "restart", "--rollback")
    assert result.returncode == 0, result.stderr
    assert "Rolling back" in result.stdout
    assert not registry_file.read_text(encoding="utf-8").endswith("# drifted\n")  # config restored
    commands = (tmp_path / "docker.log").read_text(encoding="utf-8").splitlines()
    assert f"tag {RUNNER_IMAGE}:previous {RUNNER_IMAGE}:latest" in commands
    assert "All prepared deployment services are running." in result.stdout
    rolled = stamp_mod.load_stamp(state)
    assert rolled["mode"] == "rollback"


# -- route gate ---------------------------------------------------------------


def test_upload_gate_returns_503_under_maintenance_sentinel(monkeypatch, tmp_path):
    module = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678"},
    )
    client = module.app.test_client()
    auth_header = _test_client_auth(module)

    def payload():
        # werkzeug closes the file object while building the body — one per request.
        return {"file": (io.BytesIO(b">seq\nACDEFGHIK"), "t.fasta"), "task_type": "gremlin"}

    sentinel = Path(module.CONFIG.server_dir) / ".maintenance"
    sentinel.write_text("deployment maintenance\n", encoding="utf-8")
    blocked = client.post("/compute/api/post", headers=auth_header, data=payload())
    assert blocked.status_code == 503
    assert b"submissions are paused" in blocked.data

    sentinel.unlink()
    allowed = client.post("/compute/api/post", headers=auth_header, data=payload())
    # Without the sentinel the request proceeds past the gate (the downstream
    # failure mode in a unit-test env is irrelevant here).
    assert b"submissions are paused" not in allowed.data
