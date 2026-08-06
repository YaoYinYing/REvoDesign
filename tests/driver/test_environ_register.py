# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from REvoDesign.driver import environ_register


class FakeConfig:
    def __init__(self):
        self.reload_count = 0

    def reload(self):
        self.reload_count += 1


class FakeBus:
    _instance = object()

    def __init__(self, variables, override_existing=False, enable_experimental=False):
        self.cfg_group = {"environ": FakeConfig()}
        self.variables = variables
        self.override_existing = override_existing
        self.enable_experimental = enable_experimental

    def get_value(self, cfg_item, converter=None, **_kwargs):
        if cfg_item == "variables":
            return dict(self.variables)
        if cfg_item == "override_existing":
            return self.override_existing
        if cfg_item == "enable_experimental":
            return self.enable_experimental
        raise AssertionError(f"unexpected config item: {cfg_item}")


def _patch_bus(monkeypatch, bus):
    class FakeConfigBus:
        _instance = object()

        def __new__(cls):
            return bus

        @classmethod
        def is_initialized(cls):
            return True

    monkeypatch.setattr(environ_register, "ConfigBus", FakeConfigBus)


def test_register_environment_variables_preserves_existing_process_values(monkeypatch):
    monkeypatch.setenv("REVODESIGN_TEST_EXISTING", "from-shell")
    monkeypatch.delenv("REVODESIGN_TEST_NEW", raising=False)
    bus = FakeBus(
        {
            "REVODESIGN_TEST_EXISTING": "from-yaml",
            "REVODESIGN_TEST_NEW": "new-value",
            "REVODESIGN_TEST_SKIPPED": None,
        }
    )
    _patch_bus(monkeypatch, bus)

    environ_register.register_environment_variables()

    assert bus.cfg_group["environ"].reload_count == 1
    assert environ_register.os.environ["REVODESIGN_TEST_EXISTING"] == "from-shell"
    assert environ_register.os.environ["REVODESIGN_TEST_NEW"] == "new-value"
    assert "REVODESIGN_TEST_SKIPPED" not in environ_register.os.environ


def test_register_environment_variables_can_explicitly_override(monkeypatch):
    monkeypatch.setenv("REVODESIGN_TEST_EXISTING", "from-shell")
    bus = FakeBus({"REVODESIGN_TEST_EXISTING": "from-yaml"}, override_existing=True)
    _patch_bus(monkeypatch, bus)

    environ_register.register_environment_variables()

    assert environ_register.os.environ["REVODESIGN_TEST_EXISTING"] == "from-yaml"


def test_register_environment_variables_exports_experimental_flag(monkeypatch):
    monkeypatch.delenv("REVODESIGN_ENABLE_EXPERIMENTAL", raising=False)
    bus = FakeBus({}, enable_experimental=True)
    _patch_bus(monkeypatch, bus)

    environ_register.register_environment_variables()

    assert environ_register.os.environ["REVODESIGN_ENABLE_EXPERIMENTAL"] == "1"
