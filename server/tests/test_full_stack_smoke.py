# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from unittest.mock import Mock

import pytest
from full_stack_smoke import _wait_for_task


def test_wait_for_task_rejects_http_error_before_parsing_json() -> None:
    response = Mock(status_code=500, text="upstream unavailable")
    response.json.side_effect = AssertionError("non-200 response must not be parsed")
    session = Mock()
    session.get.return_value = response

    with pytest.raises(AssertionError, match="returned HTTP 500: upstream unavailable"):
        _wait_for_task(session, "http://server.test", "task-id", {}, timeout=1)

    response.json.assert_not_called()


def test_wait_for_task_accepts_pending_202_response(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = Mock(status_code=202, text='{"status":"pending"}')
    pending.json.return_value = {"status": "pending"}
    finished = Mock(status_code=200, text='{"status":"finished"}')
    finished.json.return_value = {"status": "finished"}
    session = Mock()
    session.get.side_effect = [pending, finished]
    monkeypatch.setattr("full_stack_smoke.time.sleep", lambda _: None)

    _wait_for_task(session, "http://server.test", "task-id", {}, timeout=1)

    assert session.get.call_count == 2
