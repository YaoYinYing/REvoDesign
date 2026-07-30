# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_guard():
    script_path = Path(__file__).resolve().parents[2] / "dev/tools/check_ascii_sources.py"
    spec = importlib.util.spec_from_file_location("check_ascii_sources", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ascii_source_guard_accepts_ascii(tmp_path):
    guard = _load_guard()
    source = tmp_path / "bootstrap.py"
    source.write_text('print("ASCII only")\n', encoding="utf-8")

    assert guard.scan_file(source) == []


def test_ascii_source_guard_reports_safe_location_and_codepoint(tmp_path):
    guard = _load_guard()
    source = tmp_path / "bootstrap.py"
    source.write_text("# map filename \N{RIGHTWARDS ARROW} path\n", encoding="utf-8")

    assert guard.scan_file(source) == [
        f"{source}:1:16: non-ASCII character U+2192 (\\u2192); "
        "standalone distributed Python sources must remain ASCII-only"
    ]


def test_ascii_source_guard_checks_configured_sources(tmp_path, capsys):
    guard = _load_guard()
    source = tmp_path / "bootstrap.py"
    source.write_text("# bad \N{EM DASH}\n", encoding="utf-8")
    guard.REPO_ROOT = tmp_path
    guard.ASCII_ONLY_PATHS = (Path("bootstrap.py"),)

    assert guard.main() == 1
    assert "bootstrap.py:1:7: non-ASCII character U+2014 (\\u2014)" in capsys.readouterr().err
