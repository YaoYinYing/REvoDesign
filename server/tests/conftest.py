# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""pytest configuration for pssm_gremlin_server tests.

Run from the repo root::

    pytest server/tests/ -k "not Docker and not docker"
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ── path setup ────────────────────────────────────────────────────────────────

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
REPO_DIR = str(ROOT_DIR)
TEST_ROOT = os.path.abspath(".")


# ── Docker availability ────────────────────────────────────────────────────────

def has_docker_daemon() -> bool:
    """Check whether a local Docker daemon is reachable."""
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return True
    except Exception:
        return False
