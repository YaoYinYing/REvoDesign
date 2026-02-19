# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


import pytest

from REvoDesign.driver.ui_driver import ConfigBus


# Pytest tests
def test_require_non_headless_in_headless_mode():
    config_bus = ConfigBus()
    with pytest.raises(RuntimeError, match="cannot be called when the application is running in headless mode"):
        config_bus.initialize_widget_with_group()

    language = config_bus.get_value("language")
    assert language is not None
