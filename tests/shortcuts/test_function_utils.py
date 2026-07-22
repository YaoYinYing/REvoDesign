# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import subprocess

from REvoDesign.shortcuts import function_utils


class DummyProcess:
    def __init__(self, returncode: int | None = None):
        self.returncode = returncode
        self.terminated = False
        self.killed = False
        self.wait_calls: list[float | None] = []

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = 0

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        return self.returncode


class HangingProcess(DummyProcess):
    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if not self.killed:
            raise subprocess.TimeoutExpired(cmd="pymol", timeout=timeout)
        return 0


def test_visualize_conformer_sdf_tracks_preview_process(monkeypatch, tmp_path):
    sdf_file = tmp_path / "ligand.sdf"
    sdf_file.write_text("mock", encoding="utf-8")
    process = DummyProcess()
    calls = []

    monkeypatch.setattr(function_utils.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(function_utils.subprocess, "Popen", fake_popen)
    function_utils._PREVIEW_PROCESSES.clear()

    function_utils.visualize_conformer_sdf(str(sdf_file), "New Window")

    assert process in function_utils._PREVIEW_PROCESSES
    assert calls[0][0][0] == [
        "/usr/bin/pymol",
        "-xi",
        str(tmp_path / "ligand_load_to_preview.pml"),
    ]
    assert calls[0][1]["stdin"] is subprocess.DEVNULL

    function_utils.cleanup_conformer_preview_processes()


def test_visualize_conformer_sdf_prunes_finished_preview_processes(monkeypatch, tmp_path):
    sdf_file = tmp_path / "ligand.sdf"
    sdf_file.write_text("mock", encoding="utf-8")
    finished = DummyProcess(returncode=0)
    running = DummyProcess()

    monkeypatch.setattr(function_utils.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(function_utils.subprocess, "Popen", lambda *args, **kwargs: running)
    function_utils._PREVIEW_PROCESSES.clear()
    function_utils._PREVIEW_PROCESSES.add(finished)

    function_utils.visualize_conformer_sdf(str(sdf_file), "New Window")

    assert finished not in function_utils._PREVIEW_PROCESSES
    assert running in function_utils._PREVIEW_PROCESSES

    function_utils.cleanup_conformer_preview_processes()


def test_cleanup_conformer_preview_processes_kills_stubborn_process():
    process = HangingProcess()
    function_utils._PREVIEW_PROCESSES.clear()
    function_utils._PREVIEW_PROCESSES.add(process)

    function_utils.cleanup_conformer_preview_processes(timeout=0.01)

    assert process.terminated is True
    assert process.killed is True
    assert process not in function_utils._PREVIEW_PROCESSES
