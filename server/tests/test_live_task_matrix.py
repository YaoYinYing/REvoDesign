# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json

import pytest
import requests

from live_task_matrix import CASES, REPO_ROOT, WORKSPACES, form_value, poll_payload, save


def test_live_matrix_preserves_case_except_for_booleans():
    assert form_value("esm2_t6_8M_UR50D") == "esm2_t6_8M_UR50D"
    assert form_value("A") == "A"
    assert form_value(True) == "true"
    assert WORKSPACES["rfdiffusion"]["capabilities"]["design_regions"]["mode"] == "unconditional"
    opendde = json.loads((REPO_ROOT / CASES["opendde"][0]).read_text(encoding="utf-8"))
    assert opendde and isinstance(opendde, list)


def test_live_matrix_state_writes_are_atomic(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(type(state_path), "replace", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    with pytest.raises(OSError):
        save(state_path, {"tasks": {}})
    assert state_path.read_text(encoding="utf-8") == "old\n"
    assert list(tmp_path.iterdir()) == [state_path]


def test_live_matrix_accepts_terminal_failed_404_only():
    failed = requests.Response()
    failed.status_code = 404
    failed._content = b'{"status":"failed"}'
    missing = requests.Response()
    missing.status_code = 404
    missing._content = b'{"status":"not_found"}'
    malformed = requests.Response()
    malformed.status_code = 404
    malformed._content = b'[]'
    assert poll_payload(failed) == {"status": "failed"}
    assert poll_payload(missing) is None
    assert poll_payload(malformed) is None
