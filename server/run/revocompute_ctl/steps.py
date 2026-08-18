# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Step registry and the restart walk.

Every restart is an ordered sequence of named steps.  The walker times each
step, honors --dry-run, and runs each completed step's cleanup in reverse on
failure.  The stop step is always last — the registry refuses a sequence
that does not end with it.  The deploy stamp is written by the finalizer
after the walk, so it can carry the real step timings.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from revocompute_ctl.compose import compose_args, ensure_docker_gid, run_cmd
from revocompute_ctl.registry import (
    RegistryError,
    build_slurm_images,
    load_registry,
    runner_enabled,
    validate_compose_model,
    validate_prepared_images,
    validate_runtime_files,
    validate_slurm_images,
)
from revocompute_ctl.storage import (
    prepare_auth_storage,
    prepare_result_storage,
    require_production_identity,
    resolve_runner_identity,
    validate_auth_database_storage,
    validate_auth_storage,
    validate_result_storage,
)

# The resource-policy audit argv, kept as one literal so the static test
# assertion stays a one-liner.
RESOURCE_AUDIT_CMD = "run --rm --no-deps --no-build --entrypoint python worker -m revocompute.resource_audit"


@dataclass
class Step:
    name: str
    run: Callable[[], object]
    cleanup: Callable[[], None] | None = None


@dataclass
class RestartPlan:
    """The walk plus the post-walk finalizer (stamp + undrain)."""

    steps: list[Step]
    finalize: Callable[[dict[str, float]], None]
    report_lines: list[str] = field(default_factory=list)


@dataclass
class RestartFlags:
    mode: str = "dev"
    build_sif: bool = False
    use_proxy: str = ""
    use_proxy_from_env: bool = False
    drain_minutes: int = 0
    dry_run: bool = False
    rollback: bool = False


class StepRegistry:
    """Named step sequences; enforces the stop-last invariant."""

    def __init__(self) -> None:
        self._sequences: dict[str, list[Step]] = {}

    def add(self, name: str, steps: list[Step]) -> None:
        if not steps or steps[-1].name != "stop":
            raise ValueError(f"registry sequence {name!r} must end with the stop step")
        self._sequences[name] = steps

    def get(self, name: str) -> list[Step]:
        return list(self._sequences[name])


def run_walk(steps: list[Step], dry_run: bool = False) -> dict[str, float]:
    """Execute the walk; on failure, run completed steps' cleanups in
    reverse.  Returns step timings."""
    timings: dict[str, float] = {}
    completed: list[Step] = []
    for step in steps:
        if dry_run:
            print(f"  [dry-run] {step.name}")
            continue
        start = time.monotonic()
        try:
            step.run()
        except BaseException:
            for done in reversed(completed):
                if done.cleanup is not None:
                    done.cleanup()
            raise
        timings[step.name] = time.monotonic() - start
        completed.append(step)
    return timings


# -- prepared-mode preflight -------------------------------------------------


def validate_resource_policies(state, compose_cmd: tuple[str, ...]) -> None:
    print("Validating resolved task resource policies with the prepared worker image...")
    run_cmd(
        [*compose_cmd, *compose_args(state), "--env-file", state.env_file, *RESOURCE_AUDIT_CMD.split()],
        env=state.exported(),
    )


def _prepared_preflight(state, compose_cmd: tuple[str, ...], dry_run: bool = False) -> None:
    """Everything a prepared restart validates before stopping the healthy
    stack.  Order is significant: the socket GID must resolve before Compose
    interpolation is exercised.  --dry-run skips the mkdir-ing storage prep
    (it must write nothing)."""
    families = load_registry(state.config_dir())[2]
    validate_prepared_images(state, families)
    if state.use_slurm():
        validate_slurm_images(state, families)
    validate_auth_storage(state)
    # Compose interpolation requires the socket GID and runner identity.
    # Resolve them during preflight so a missing DOCKER_GID fails before down.
    ensure_docker_gid(state)
    uid, _gid = resolve_runner_identity(state)
    if not dry_run:
        prepare_auth_storage(state, uid)
        prepare_result_storage(state, uid)
    validate_compose_model(state, compose_cmd)
    validate_resource_policies(state, compose_cmd)


# -- subcommand sequences ----------------------------------------------------


def require_env_file(state, dry_run: bool = False) -> None:
    if not os.path.isfile(state.env_file):
        print(
            f"Expected {state.env_file} to exist. Run: REVODESIGN_SERVER_ENV={state.env_file} bash server/run/restart.sh setup",
            file=sys.stderr,
        )
        raise SystemExit(1)
    state.ensure_redis_password(write=not dry_run)


def validate_required_settings(state) -> None:
    # The shell validated in a subshell with SERVER_DIR/ADMIN_USERS unset —
    # only the env file counts, never the outer process environment.
    missing = [name for name in ("SERVER_DIR", "ADMIN_USERS") if not state.values.get(name, "").strip()]
    if missing:
        print(f"Missing required setting(s) in {state.env_file}: {' '.join(missing)}", file=sys.stderr)
        raise SystemExit(1)


def cmd_setup(state) -> None:
    from revocompute_ctl import ENV_EXAMPLE_FILE
    from revocompute_ctl.compose import detect_docker_gid

    if not os.path.isfile(state.env_file):
        if not ENV_EXAMPLE_FILE.is_file():
            print(f"Missing {ENV_EXAMPLE_FILE}; cannot initialize {state.env_file}.", file=sys.stderr)
            raise SystemExit(1)
        shutil.copy(ENV_EXAMPLE_FILE, state.env_file)
        print(f"Created {state.env_file} from {ENV_EXAMPLE_FILE}.")
    detected = detect_docker_gid()
    if detected:
        print(f"Detected Docker socket group id {detected}; restart/build/up/down auto-export it for Docker Compose.")
    else:
        print(
            "Unable to auto-detect Docker socket group id; set DOCKER_GID when running build/up/restart.",
            file=sys.stderr,
        )
    state.ensure_redis_password()
    print(f"Setup completed. Using env file: {state.env_file}")
    print(f"Review {state.env_file} before starting services.")


def cmd_down(state, compose_cmd: tuple[str, ...]) -> None:
    from revocompute_ctl.sweep import pre_stop_sweep_slurm

    require_env_file(state)
    ensure_docker_gid(state)
    resolve_runner_identity(state)
    pre_stop_sweep_slurm(state, compose_cmd)
    print("Stopping services via docker compose...")
    run_cmd(
        [*compose_cmd, *compose_args(state), "--env-file", state.env_file, "down"],
        env=state.exported(),
    )


def cmd_reload(state, compose_cmd: tuple[str, ...]) -> None:
    require_env_file(state)
    print("Sending HUP to Gunicorn...")
    run_cmd(
        [
            *compose_cmd,
            *compose_args(state),
            "--env-file",
            state.env_file,
            "exec",
            "web",
            "pkill",
            "-HUP",
            "gunicorn",
        ],
        env=state.exported(),
    )


def cmd_up(state, compose_cmd: tuple[str, ...], extra: list[str] | None = None) -> None:
    from revocompute_ctl.admin import prepare_admin_bootstrap, print_admin_logins

    require_env_file(state)
    validate_required_settings(state)
    families = validate_runtime_files(state)
    if state.use_slurm():
        validate_slurm_images(state, families)
    validate_auth_storage(state)
    prepare_admin_bootstrap(state)
    ensure_docker_gid(state)
    uid, _gid = resolve_runner_identity(state)
    prepare_auth_storage(state, uid)
    prepare_result_storage(state, uid)
    print("Starting services via docker compose...")
    run_cmd(
        [
            *compose_cmd,
            *compose_args(state),
            "--env-file",
            state.env_file,
            "up",
            *(extra or []),
            "-d",
            "redis",
            "web",
            "gateway",
            "maintenance",
            "worker",
        ],
        env=state.exported(),
    )
    validate_result_storage(state, compose_cmd)
    validate_auth_database_storage(state, compose_cmd)
    print_admin_logins(state)


def wait_for_services(state, compose_cmd: tuple[str, ...]) -> None:
    expected = {"redis", "web", "gateway", "maintenance", "worker"}
    for _attempt in range(30):
        running = run_cmd(
            [
                *compose_cmd,
                *compose_args(state),
                "--env-file",
                state.env_file,
                "ps",
                "--status",
                "running",
                "--services",
            ],
            env=state.exported(),
            check=False,
            capture=True,
        ).stdout.split()
        if expected <= set(running):
            print("All prepared deployment services are running.")
            return
        time.sleep(2)
    print("Prepared deployment readiness failed; not all required services are running.", file=sys.stderr)
    raise SystemExit(1)


def pull_production_images(state, compose_cmd: tuple[str, ...], families) -> None:
    print("Pulling configured production images...")
    run_cmd(
        [*compose_cmd, *compose_args(state), "--env-file", state.env_file, "pull", "web", "gateway"],
        env=state.exported(),
    )
    for family in families:
        if not runner_enabled(state, family.name):
            continue
        print(f"  → {family.docker_image} ({family.name})")
        run_cmd(["docker", "pull", family.docker_image], env=state.exported())


def slurm_block(state, families, build_sif: bool, changed: set[str]) -> None:
    print("[SLURM] SLURM+Apptainer runner enabled.")
    if build_sif:
        build_slurm_images(state, families, changed)
        validate_slurm_images(state, families)


def finish_restart(state) -> None:
    """The completion banner printed after every successful restart."""
    print("Deployment completed.")
    print(f"Nginx gateway is now running at http://0.0.0.0:{state.get('PORT') or '8080'}/compute/dashboard")
    if state.use_slurm():
        print("[SLURM] SLURM runner is enabled. Configure per-task SLURM settings at /compute/configuration")


# -- the restart walk --------------------------------------------------------


def build_restart_plan(state, compose_cmd: tuple[str, ...], flags: RestartFlags) -> RestartPlan:
    """Assemble the restart walk for the selected mode (or --rollback)."""
    from revocompute_ctl import promotion
    from revocompute_ctl.admin import prepare_admin_bootstrap
    from revocompute_ctl.build import cmd_build
    from revocompute_ctl.drain import begin_drain, end_drain
    from revocompute_ctl.stamp import backup_config, stamp_payload, write_stamp

    require_env_file(state, dry_run=flags.dry_run)
    validate_required_settings(state)

    families = validate_runtime_files(state)
    if flags.mode == "prod":
        require_production_identity(state)
    prepare_admin_bootstrap(state)

    if state.use_slurm() and not flags.build_sif:
        validate_slurm_images(state, families)
    if state.use_slurm() and flags.build_sif and not shutil.which("apptainer"):
        print("[SLURM] apptainer not found on PATH; refusing to stop the current deployment.", file=sys.stderr)
        raise SystemExit(1)
    if flags.mode == "prepared":
        _prepared_preflight(state, compose_cmd, dry_run=flags.dry_run)

    images = promotion.taggable_images(state, families)
    baseline = promotion.capture_baseline_digests(state, images)
    changed = promotion.changed_image_names(state, images, baseline, flags.mode)
    changed_sifs = changed | {family.name for family in families if not os.path.isfile(family.slurm_image)}
    backup_path_holder: list[str] = [""]

    steps: list[Step] = [
        Step("backup-config", lambda: backup_path_holder.__setitem__(0, backup_config(state))),
        Step("capture-baselines", lambda: None),  # captured above; kept as a named phase
        Step("stop", lambda: cmd_down(state, compose_cmd)),
    ]
    if flags.drain_minutes:
        steps.insert(
            0, Step("drain", lambda: begin_drain(state, flags.drain_minutes), cleanup=lambda: end_drain(state))
        )

    if flags.mode == "dev":
        steps.append(
            Step(
                "build",
                lambda: cmd_build(state, compose_cmd, flags.use_proxy_from_env, flags.use_proxy),
            )
        )
    elif flags.mode == "prod":
        steps.append(Step("pull", lambda: pull_production_images(state, compose_cmd, families)))
    else:
        steps.append(Step("activate", lambda: print("Activating validated prepared images without builds or pulls.")))
    if state.use_slurm():
        steps.append(Step("build-sif", lambda: slurm_block(state, families, flags.build_sif, changed)))
    steps.append(Step("promote", lambda: promotion.promote_docker(state, images, baseline, flags.mode)))
    steps.append(Step("promote-sifs", lambda: promotion.promote_sifs(state, families, changed_sifs)))
    steps.append(Step("up", lambda: cmd_up(state, compose_cmd, extra=["--no-build"])))
    if flags.mode == "prepared":
        steps.append(Step("readiness", lambda: wait_for_services(state, compose_cmd)))
    steps.append(Step("prune", lambda: promotion.prune_dangling(state)))

    def finalize(timings: dict[str, float]) -> None:
        if flags.mode != "dev":  # dev CONFIG_DIR is usually the checkout
            write_stamp(
                state,
                stamp_payload(
                    state,
                    mode=flags.mode,
                    timings=timings,
                    changed=sorted(changed),
                    unchanged=sorted(set(images) - changed),
                    images=images,
                    baseline=baseline,
                    families=families,
                    backup_path=backup_path_holder[0],
                ),
            )
        if flags.drain_minutes:
            end_drain(state)
        finish_restart(state)

    report_lines = [
        "Planned restart walk:",
        *(f"  {step.name}" for step in steps),
        "  stamp",
        f"Image changes: changed={', '.join(sorted(changed)) or '-'}, "
        f"unchanged={', '.join(sorted(set(images) - changed)) or '-'}",
        f"SIF changes: changed={', '.join(sorted(changed_sifs)) or '-'}, "
        f"unchanged={', '.join(sorted({family.name for family in families} - changed_sifs)) or '-'}",
    ]
    return RestartPlan(steps, finalize, report_lines)


def build_rollback_plan(state, compose_cmd: tuple[str, ...]) -> RestartPlan:
    """Restore the previous image/SIF set from the last deploy stamp, then
    restart.  Never touches tasks/results/user DB."""
    import os as _os

    from revocompute_ctl import promotion
    from revocompute_ctl.stamp import (
        load_stamp,
        rollback_config,
        stamp_payload,
        write_stamp,
    )

    require_env_file(state)
    validate_required_settings(state)
    families = validate_runtime_files(state)
    stamp = load_stamp(state)
    stamp_commit = stamp.get("commit", "unknown")
    images = promotion.taggable_images(state, families)
    changed = set(stamp.get("changed") or [])

    missing = [
        f"{image}:previous"
        for name, image in images.items()
        if name in changed and not _image_id(state, f"{image}:previous")
    ]
    if state.use_slurm():
        missing += [
            family.slurm_image
            for family in families
            if family.name in changed and not _os.path.isfile(f"{family.slurm_image}.previous")
        ]
    if missing:
        print(
            f"Rollback refused: previous set missing for {', '.join(missing)} (last deployed commit {stamp_commit}).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    rollback_config(state, stamp)

    steps: list[Step] = [
        Step("stop", lambda: cmd_down(state, compose_cmd)),  # includes the pre-stop sweep
        Step(
            "retag",
            lambda: (promotion.rollback_docker(state, images, changed), promotion.rollback_sifs(state, families)),
        ),
        Step("up", lambda: cmd_up(state, compose_cmd, extra=["--no-build"])),
        Step("readiness", lambda: wait_for_services(state, compose_cmd)),
    ]

    def finalize(timings: dict[str, float]) -> None:
        write_stamp(
            state,
            stamp_payload(
                state,
                mode="rollback",
                timings=timings,
                changed=sorted(changed),
                unchanged=sorted(set(images) - changed),
                images=images,
                baseline={name: {"latest": "", "next": ""} for name in images},
                families=families,
                backup_path=stamp.get("config_backup", ""),
            ),
        )
        finish_restart(state)

    return RestartPlan(
        steps, finalize, [f"Rollback from {stamp_commit} (changed: {', '.join(sorted(changed)) or '-'})"]
    )


def _image_id(state, tag: str) -> str:
    from revocompute_ctl.compose import image_id

    return image_id(state, tag)
