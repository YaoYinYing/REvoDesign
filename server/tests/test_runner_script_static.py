# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path


RUNNER_SCRIPT = Path(__file__).resolve().parents[1] / "REvoDesign_PSSM_GREMLIN.sh"


def test_runner_script_does_not_eval_user_controlled_commands():
    script = RUNNER_SCRIPT.read_text()

    assert 'eval "$cmd"' not in script
    assert "eval $cmd" not in script
    assert "bash -c" not in script
    assert "sh -c" not in script


def test_runner_script_executes_pipeline_commands_as_arrays():
    script = RUNNER_SCRIPT.read_text()

    for command in ("hhblits", "hhfilter", "GREMLIN_TFv1.py", "psiblast"):
        assert command in script

    assert '"${cmd[@]}"' in script
