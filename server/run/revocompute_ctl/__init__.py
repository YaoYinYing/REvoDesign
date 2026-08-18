# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""REvoCompute deployment control — the Python port of run/restart.sh."""

from __future__ import annotations

from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = SERVER_ROOT / "docker-compose.yml"
COMPOSE_SLURM_FILE = SERVER_ROOT / "docker-compose.slurm.yml"
COMPOSE_DOCKER_FILE = SERVER_ROOT / "docker-compose.docker.yml"
ENV_EXAMPLE_FILE = SERVER_ROOT / ".env.example"
PRIMARY_ENV_FILE = SERVER_ROOT / ".env.production"
