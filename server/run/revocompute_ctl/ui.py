# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Usage text and the pinned output strings the tests assert verbatim.

Do not reword any string here without checking server/tests — several
messages are pinned by test_process_isolation.py and the ops guide.
"""

from __future__ import annotations

USAGE = """Usage: bash server/run/restart.sh [setup|build|up|down|reload|restart|reset-passwd]
       bash server/run/restart.sh restart [--mode=dev|--mode=prod|--mode=prepared]
       bash server/run/restart.sh reset-passwd <username>

       SLURM flags (when task_types.yaml selects job_executor: slurm):
           --allowed-slurm-queue q1,q2,...     Comma-separated SLURM partitions.
           --build-sif                         Build .sif images from .def files
                                               (requires apptainer on PATH).

       Build flags (build / restart --mode=dev):
           --use-proxy[=<url>]                 Use proxy for apt/pip/git during
                                               Docker builds via predefined
                                               non-persisted build arguments.
                                               Without a URL, read
                                               REVODESIGN_BUILD_PROXY from the
                                               selected environment file.
           --enabled-runners=<csv>             Comma-separated runner names,
                                               e.g. 'gremlin,pythia_ddg'.
                                               Default: all registered runners.

       Deploy safety flags (restart):
           --dry-run                           Print the planned step walk and
                                               per-family change predictions
                                               without executing anything.
           --drain=<minutes>                   Before stopping the stack, block
                                               new submissions and wait up to
                                               N minutes for running SLURM jobs
                                               to finish; the sweep cancels the
                                               remainder.
           --rollback                          Restore the previous image/SIF
                                               set from the last deploy stamp,
                                               then restart. Refuses when no
                                               stamp or previous set exists.

Environment:
  REVODESIGN_SERVER_ENV
          Optional path to env file (absolute or relative to current working directory).
          Defaults to server/.env.production.

Safety:
  Run as the deployment account, never through sudo or as root. Startup
  validates host permissions and does not change ownership or modes.

Subcommands:
  setup    Prepare the selected env file (create from .env.example if missing) and show detected DOCKER_GID.
  build    Build runner image and web/worker images.
  up       Start redis/web/worker with docker compose.
  down     Stop and remove the compose stack.
  reload   Send HUP to Gunicorn for a zero-downtime application reload.
  restart  Restart in dev mode by default.
           --mode=dev:  down, build local images with host UID/GID, then up.
           --mode=prod: down, pull configured images, then up without building.
           --mode=prepared: validate local images, SIFs, configuration, and
                            Compose before down, then up without build or pull.
           --use-proxy[=<url>]  Pass redacted, non-persisted proxy build arguments.
"""

# Pinned output strings (asserted verbatim by tests).
MSG_GENERATED_REDIS_PASSWORD = "Generated REDIS_PASSWORD and stored it in {}."
MSG_CREDENTIAL_WRITTEN = "New credential written to:"
MSG_AUTH_BACKUP_WRITTEN = "Auth database backup written to:"
MSG_BOOTSTRAP_WRITTEN = "Bootstrap admin credentials written to: {} (mode 0600)"
MSG_MISSING_REQUIRED = "Missing required setting(s)"
MSG_MISSING_SIF = "Missing SIF image"
MSG_CREDENTIAL_REDACTED = "credential redacted"
MSG_USING_ENV_FILE = "Using env file: "
MSG_SERVICES_RUNNING = "All prepared deployment services are running."
MSG_DUPLICATE_ADMINS = "ADMIN_USERS must not contain duplicate usernames: {}"
MSG_ROOT_REFUSAL = "Do not run restart.sh through sudo or as root"
MSG_MAINTENANCE_503 = "Server is in maintenance; submissions are paused"
