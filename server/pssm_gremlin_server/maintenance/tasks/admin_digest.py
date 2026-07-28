# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Periodic administrator registration-digest task."""

from __future__ import annotations

from pssm_gremlin_server.auth import send_admin_digest


def run_admin_digest() -> bool:
    """Send one digest for registrations not previously notified."""
    return send_admin_digest()
