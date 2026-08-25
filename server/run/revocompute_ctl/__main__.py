# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""CLI entry — the argument contract of run/restart.sh, verbatim."""

from __future__ import annotations

import os
import sys

from revocompute_ctl import PRIMARY_ENV_FILE
from revocompute_ctl.compose import detect_compose_cmd
from revocompute_ctl.env import EnvState
from revocompute_ctl.steps import (
    RestartFlags,
    build_restart_plan,
    cmd_down,
    cmd_reload,
    cmd_setup,
    cmd_up,
    require_env_file,
    run_walk,
    validate_required_settings,
)
from revocompute_ctl.ui import USAGE


def _usage_exit(message: str) -> None:
    print(message, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    raise SystemExit(1)


def parse_args(argv: list[str]) -> tuple[str, str, RestartFlags]:
    """Port of the shell's hand-rolled argument loop, messages included."""
    if not argv:
        return "restart", "", RestartFlags()
    subcommand = argv[0]
    rest = argv[1:]
    reset_username = ""
    if subcommand == "reset-passwd":
        if len(rest) != 1:
            print("reset-passwd requires exactly one username.", file=sys.stderr)
            print(USAGE, file=sys.stderr)
            raise SystemExit(1)
        reset_username = rest[0]
        rest = []

    flags = RestartFlags()
    position = 0
    while position < len(rest):
        arg = rest[position]
        if arg.startswith("--mode="):
            flags.mode = arg[len("--mode=") :]
            if flags.mode not in ("dev", "prod", "prepared"):
                _usage_exit(f"Invalid mode: {flags.mode}. Expected dev, prod, or prepared.")
            if subcommand != "restart":
                _usage_exit("--mode is only supported by the restart subcommand.")
        elif arg == "--mode":
            _usage_exit("Too many arguments. Use --mode=dev, --mode=prod, or --mode=prepared.")
        elif arg == "--allowed-slurm-queue":
            position += 1
            if position >= len(rest) or rest[position].startswith("--"):
                print("--allowed-slurm-queue requires a value.", file=sys.stderr)
                raise SystemExit(1)
            os.environ["SLURM_ALLOWED_QUEUES"] = rest[position]
        elif arg.startswith("--enabled-runners="):
            os.environ["ENABLED_TASKRUNNERS"] = arg[len("--enabled-runners=") :]
        elif arg == "--enabled-runners":
            position += 1
            if position >= len(rest) or rest[position].startswith("--"):
                print("--enabled-runners requires a comma-separated value, e.g. 'gremlin,pythia_ddg'.", file=sys.stderr)
                raise SystemExit(1)
            os.environ["ENABLED_TASKRUNNERS"] = rest[position]
        elif arg == "--build-sif":
            flags.build_sif = True
        elif arg.startswith("--use-proxy="):
            flags.use_proxy = arg[len("--use-proxy=") :]
            os.environ["HTTP_PROXY"] = flags.use_proxy
            os.environ["HTTPS_PROXY"] = flags.use_proxy
            os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "localhost,127.0.0.1,.local")
        elif arg == "--use-proxy":
            flags.use_proxy_from_env = True
        elif arg == "--dry-run":
            if subcommand != "restart":
                _usage_exit("--dry-run is only supported by the restart subcommand.")
            flags.dry_run = True
        elif arg == "--keep-gateway":
            if subcommand != "restart":
                _usage_exit("--keep-gateway is only supported by the restart subcommand.")
            flags.keep_gateway = True
        else:
            _usage_exit(f"Unexpected argument: {arg}")
        position += 1
    return subcommand, reset_username, flags


def resolve_env_file() -> str:
    selected = os.environ.get("REVODESIGN_SERVER_ENV", "")
    if selected:
        return selected if selected.startswith("/") else os.path.join(os.getcwd(), selected)
    return str(PRIMARY_ENV_FILE)


def detect_executor(state: EnvState) -> tuple[bool, str]:
    """job_executor from the registry selects USE_SLURM (and the compose
    override).  config_dir() replicates the shell's CONFIG_DIR resolution —
    env file, then the outer environment, then the checkout config."""
    from revocompute_ctl.registry import resolve_job_executor

    registry_file = os.path.join(state.config_dir(), "task_types.yaml")
    executor = resolve_job_executor(registry_file)
    if executor == "slurm":
        state.runtime["SLURM_ENABLED"] = "true"
        return True, registry_file
    if executor == "docker":
        state.runtime["SLURM_ENABLED"] = "false"
        return False, registry_file
    print(f"job_executor must be docker or slurm in {registry_file}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    # Keep the shell controller's observable compose check before argument
    # handling; process-isolation tests pin this ordering.
    compose_cmd = detect_compose_cmd()
    subcommand, reset_username, flags = parse_args(sys.argv[1:])

    if subcommand in ("-h", "--help", "help"):
        print(USAGE)
        return

    env_file = resolve_env_file()
    if os.environ.get("REVODESIGN_SERVER_ENV") and not os.path.isfile(env_file) and subcommand != "setup":
        print(f"Explicit env file does not exist: {env_file}", file=sys.stderr)
        raise SystemExit(1)

    if flags.mode == "prepared" and flags.build_sif:
        print(
            "--build-sif is incompatible with --mode=prepared; prepare and validate SIFs before activation.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    state = EnvState(env_file) if os.path.isfile(env_file) else EnvState(env_file, values={})
    use_slurm, registry_file = detect_executor(state)
    if not use_slurm and (flags.build_sif or os.environ.get("SLURM_ALLOWED_QUEUES")):
        print(f"SLURM flags require job_executor: slurm in {registry_file}", file=sys.stderr)
        raise SystemExit(1)

    if subcommand not in ("-h", "--help", "help") and os.geteuid() == 0:
        print("Do not run restart.sh through sudo or as root; use the deployment account.", file=sys.stderr)
        raise SystemExit(1)

    print(f"Using env file: {env_file}")
    if os.environ.get("ENABLED_TASKRUNNERS"):
        state.runtime["ENABLED_TASKRUNNERS"] = os.environ["ENABLED_TASKRUNNERS"]
    if os.environ.get("SLURM_ALLOWED_QUEUES"):
        state.runtime["SLURM_ALLOWED_QUEUES"] = os.environ["SLURM_ALLOWED_QUEUES"]

    if subcommand == "setup":
        cmd_setup(state)
    elif subcommand in ("build", "prepare"):
        require_env_file(state)
        validate_required_settings(state)
        from revocompute_ctl.build import cmd_build

        cmd_build(
            state,
            compose_cmd,
            flags.use_proxy_from_env,
            flags.use_proxy,
            runners_only=subcommand == "prepare",
        )
        if subcommand == "prepare" and flags.build_sif:
            from revocompute_ctl.registry import build_slurm_images, validate_runtime_files, validate_slurm_images

            families = validate_runtime_files(state)
            build_slurm_images(state, families, fail_on_error=True)
            validate_slurm_images(state, families)
    elif subcommand == "up":
        cmd_up(state, compose_cmd)
    elif subcommand == "down":
        cmd_down(state, compose_cmd)
    elif subcommand == "reload":
        cmd_reload(state, compose_cmd)
    elif subcommand == "reset-passwd":
        require_env_file(state)
        validate_required_settings(state)
        from revocompute_ctl.admin import cmd_reset_passwd

        cmd_reset_passwd(state, reset_username)
    elif subcommand == "restart":
        plan = build_restart_plan(state, compose_cmd, flags)
        if flags.dry_run:
            for line in plan.report_lines:
                print(line)
            return
        timings = run_walk(plan.steps)
        plan.finalize(timings)
    else:
        print(f"Unknown subcommand: {subcommand}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
