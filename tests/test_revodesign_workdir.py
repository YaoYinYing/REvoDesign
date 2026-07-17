# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path


class RecordingBus:
    def __init__(self):
        self.values = {}

    def set_value(self, key, value):
        self.values[key] = value


def test_set_working_directory_does_not_mutate_process_cwd(app, monkeypatch, tmp_path):
    from REvoDesign.REvoDesign import REvoDesignPlugin

    original_cwd = tmp_path / "original"
    target_dir = tmp_path / "target"
    original_cwd.mkdir()
    target_dir.mkdir()
    monkeypatch.chdir(original_cwd)

    plugin = REvoDesignPlugin()
    plugin.bus = RecordingBus()

    plugin.set_working_directory(str(target_dir))

    assert plugin.PWD == str(target_dir)
    assert plugin.bus.values["work_dir"] == str(target_dir)
    assert Path.cwd() == original_cwd.resolve()
