# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""pytest configuration for pssm_gremlin_server tests.

Run from the repo root::

    pytest server/tests/ -k "not Docker and not docker"
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the server directory is on sys.path so test helpers can import
# from pssm_gremlin_server without installing the package first.
SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
