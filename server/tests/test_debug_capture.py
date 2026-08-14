# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Debug submission capture: the user's submission form and input copies are
written into the result dir before workspace cleanup, so they survive it."""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def rt(monkeypatch, tmp_path):
    """Import task_runtime with a self-contained server/config layout."""
    env_root = tmp_path / "server"
    shutil.copytree(SERVER_DIR / "config", env_root / "config")
    monkeypatch.setenv("SERVER_DIR", str(env_root))
    monkeypatch.setenv("CONFIG_DIR", str(env_root / "config"))
    monkeypatch.setenv("RUNNER_UID", "1234")
    monkeypatch.setenv("RUNNER_GID", "5678")
    _pg = sys.modules.get("revocompute")
    if _pg is not None:
        _pg.__dict__.pop("task_runtime", None)
    sys.modules.pop("revocompute.task_runtime", None)
    try:
        module = importlib.import_module("revocompute.task_runtime")
    finally:
        if _pg is not None:
            _pg.__dict__.pop("task_runtime", None)
        sys.modules.pop("revocompute.task_runtime", None)
    monkeypatch.setattr(
        module,
        "CONFIG",
        replace(
            module.CONFIG,
            workspace_folder=str(env_root / "workspaces"),
            results_folder=str(env_root / "results"),
        ),
    )
    return module


def _make_task(rt, relative_paths=("query.fasta",)):
    md5 = "a" * 32
    ws = Path(rt.CONFIG.workspace_folder)
    snapshot_root = ws / "alice" / md5 / "inputs"
    snapshot_root.mkdir(parents=True)
    entities = []
    for index, relative_path in enumerate(relative_paths):
        snapshot = snapshot_root / relative_path
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        content = f">seq{index}\nACDE\n".encode()
        snapshot.write_bytes(content)
        entities.append(
            {
                "name": "primary_input" if index == 0 else f"input_{index + 1}",
                "type": "file",
                "value": Path(relative_path).name,
                "verified_value": relative_path,
                "relative_path": relative_path,
                "mounted": f"/mnt/revocompute/alice/inputs/{relative_path}",
                "hash": hashlib.sha256(content).hexdigest(),
                "snapshot_path": str(snapshot),
                "snapshot_root": str(snapshot_root),
                "workspace_key": "alice",
            }
        )
    entities.append({"name": "max_iter", "type": "int", "value": 5, "verified_value": 5})
    result_dir = Path(rt.CONFIG.results_folder) / md5
    result_dir.mkdir(parents=True)
    task = {
        "md5sum": md5,
        "task_type": "gremlin",
        "username": "alice",
        "result_dir": str(result_dir),
        "input_form": json.dumps(
            {
                "user": "alice",
                "workspace_key": "alice",
                "virtual_root": "/mnt/revocompute/alice",
                "snapshot_root": str(snapshot_root),
                "submitted_at": "2026-08-14T00:00:00+00:00",
                "entities": entities,
            }
        ),
        "uploaded_at": 1700000000.0,
    }
    return task, entities


class _FakeTaskStore:
    def __init__(self, task):
        self.task = task
        self.updates = []

    def get_task(self, md5sum):
        return self.task

    def update_task(self, md5sum, **fields):
        self.updates.append(fields)


class _FakeTaskType:
    stage_markers = {"running": "Running", "done": "Done"}


# -- capture helper ------------------------------------------------------------


def test_capture_writes_submission_json_and_input_copies(rt, tmp_path):
    task, entities = _make_task(rt)
    rt._capture_debug_submission(task, entities)

    debug_dir = tmp_path / "server" / "results" / task["md5sum"] / "debug"
    assert (debug_dir / "inputs" / "query.fasta").read_bytes() == b">seq0\nACDE\n"

    submission = json.loads((debug_dir / "submission.json").read_text(encoding="utf-8"))
    assert submission["task_type"] == "gremlin"
    assert submission["username"] == "alice"
    assert submission["submitted_at"] == "2026-08-14T00:00:00+00:00"
    assert submission["params"] == {"max_iter": 5}
    (file_entry,) = submission["files"]
    assert file_entry["name"] == "query.fasta"
    assert file_entry["size"] == len(b">seq0\nACDE\n")
    assert file_entry["sha256"] == hashlib.sha256(b">seq0\nACDE\n").hexdigest()


def test_capture_keeps_nested_user_facing_paths(rt):
    task, entities = _make_task(rt, relative_paths=("sub/dir/input.fa",))
    rt._capture_debug_submission(task, entities)

    debug_dir = Path(task["result_dir"]) / "debug"
    assert (debug_dir / "inputs" / "sub" / "dir" / "input.fa").read_bytes() == b">seq0\nACDE\n"
    submission = json.loads((debug_dir / "submission.json").read_text(encoding="utf-8"))
    assert submission["files"][0]["name"] == "sub/dir/input.fa"


def test_capture_uses_explicit_params_argument(rt):
    task, entities = _make_task(rt)
    rt._capture_debug_submission(task, entities, {"overrides": "raw"})

    debug_dir = Path(task["result_dir"]) / "debug"
    submission = json.loads((debug_dir / "submission.json").read_text(encoding="utf-8"))
    assert submission["params"] == {"overrides": "raw"}


def test_capture_skips_path_traversal(rt):
    task, entities = _make_task(rt)
    entities.insert(
        0,
        {
            "name": "evil",
            "type": "file",
            "relative_path": "../evil.fa",
            "snapshot_path": entities[0]["snapshot_path"],
        },
    )
    rt._capture_debug_submission(task, entities)

    debug_dir = Path(task["result_dir"]) / "debug"
    assert not (debug_dir / "inputs" / "evil.fa").exists()
    submission = json.loads((debug_dir / "submission.json").read_text(encoding="utf-8"))
    assert all(fe["name"] != "../evil.fa" for fe in submission["files"])


def test_capture_skips_snapshot_outside_workspace(rt, tmp_path):
    task, entities = _make_task(rt)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"secret")
    entities.insert(
        0,
        {
            "name": "evil",
            "type": "file",
            "relative_path": "stolen.bin",
            "snapshot_path": str(outside),
        },
    )
    rt._capture_debug_submission(task, entities)

    debug_dir = Path(task["result_dir"]) / "debug"
    assert not (debug_dir / "inputs" / "stolen.bin").exists()


def test_capture_never_raises_on_missing_snapshot(rt):
    task, entities = _make_task(rt)
    entities[0]["snapshot_path"] = str(Path(entities[0]["snapshot_path"]).parent / "gone.fa")
    # Must not raise — the job finalization keeps going regardless.
    rt._capture_debug_submission(task, entities)

    debug_dir = Path(task["result_dir"]) / "debug"
    submission = json.loads((debug_dir / "submission.json").read_text(encoding="utf-8"))
    assert submission["files"] == []


# -- terminal-point wiring -----------------------------------------------------


def test_record_failure_captures_before_workspace_cleanup(rt, monkeypatch):
    task, _ = _make_task(rt)
    fake_store = _FakeTaskStore(task)
    monkeypatch.setattr(rt, "task_store", fake_store)

    rt._record_failure(task["md5sum"], task, 100.0, "running", "boom")

    assert fake_store.updates[-1]["status"] == "failed"
    # Workspace was cleaned up, so the debug copy proves capture ran first.
    assert not (Path(rt.CONFIG.workspace_folder) / "alice" / task["md5sum"]).exists()
    result_dir = Path(task["result_dir"])
    debug_dir = result_dir / "debug"
    assert (debug_dir / "submission.json").is_file()
    assert (debug_dir / "inputs" / "query.fasta").read_bytes() == b">seq0\nACDE\n"
    # The failed-task manifest published after capture includes the debug files.
    manifest = json.loads((result_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "debug/submission.json" in {a["path"] for a in manifest["artifacts"]}


def test_finalize_after_poll_publishes_debug_files_in_manifest(rt, monkeypatch):
    task, _ = _make_task(rt)
    fake_store = _FakeTaskStore(task)
    monkeypatch.setattr(rt, "task_store", fake_store)

    rt._finalize_after_poll(task["md5sum"], task, _FakeTaskType(), rt.JobState.COMPLETED)

    assert fake_store.updates[-1]["status"] == "finished"
    assert not (Path(rt.CONFIG.workspace_folder) / "alice" / task["md5sum"]).exists()
    manifest = json.loads((Path(task["result_dir"]) / "manifest.json").read_text(encoding="utf-8"))
    artifact_paths = {artifact["path"] for artifact in manifest["artifacts"]}
    assert "debug/submission.json" in artifact_paths
    assert "debug/inputs/query.fasta" in artifact_paths


def test_entities_from_input_form_tolerates_bad_rows(rt):
    assert rt._entities_from_input_form({}) == []
    assert rt._entities_from_input_form({"input_form": "not json"}) == []
    assert rt._entities_from_input_form({"input_form": '"just a string"'}) == []
    assert rt._entities_from_input_form({"input_form": json.dumps({"entities": {"not": "a list"}})}) == []
