# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path

from REvoDesign.bootstrap import REVODESIGN_CONFIG_FILE

from .conftest import EXPECTED_MAIN_CONFIG_FILE


def test_import_time_config_bootstrap_uses_test_data_dir():
    assert Path(REVODESIGN_CONFIG_FILE).resolve() == Path(EXPECTED_MAIN_CONFIG_FILE).resolve()
