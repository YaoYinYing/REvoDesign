# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import importlib
import sys

import matplotlib


def _reload_rfdiffusion_tools():
    sys.modules.pop("REvoDesign.tools.rfdiffusion_tools", None)
    return importlib.import_module("REvoDesign.tools.rfdiffusion_tools")


def test_import_does_not_force_matplotlib_backend(monkeypatch):
    calls = []
    monkeypatch.setattr(matplotlib, "use", lambda *args, **kwargs: calls.append((args, kwargs)))

    _reload_rfdiffusion_tools()

    assert calls == []


def test_plotting_can_prefer_interactive_backend_lazily(monkeypatch):
    module = _reload_rfdiffusion_tools()
    calls = []
    monkeypatch.delenv("MPLBACKEND", raising=False)
    monkeypatch.setattr(matplotlib, "use", lambda *args, **kwargs: calls.append((args, kwargs)))

    module._prefer_interactive_backend_for_plotting()

    assert calls == [((module.PREFERRED_INTERACTIVE_BACKEND,), {"force": False})]


def test_plotting_honors_existing_mplbackend(monkeypatch):
    module = _reload_rfdiffusion_tools()
    calls = []
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.setattr(matplotlib, "use", lambda *args, **kwargs: calls.append((args, kwargs)))

    module._prefer_interactive_backend_for_plotting()

    assert calls == []
