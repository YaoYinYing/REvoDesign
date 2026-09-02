# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""End-to-end authorization, snapshot, and provenance tests for @ references."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

import pytest
from conftest import _load_pssm_module, _test_client_auth


@pytest.fixture
def module(monkeypatch, tmp_path):
    loaded = _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLED_TASKRUNNERS": "gremlin"},
    )

    class Queued:
        id = "artifact-reference-test"

    monkeypatch.setattr(loaded.run_compute_task, "apply_async", lambda *args, **kwargs: Queued())
    return loaded


def _user(module, username):
    headers = _test_client_auth(module, username)
    return module.app.config["user_db"].get_user_by_username(username), headers


def _source_task(module, owner, *, project=None, status="finished", publish=True, symlink=False):
    task_id = uuid.uuid4().hex
    scope = {
        "scope_type": "project" if project else "personal",
        "scope_id": str(project["id"] if project else owner["id"]),
        "storage_key": project["storage_key"] if project else owner["storage_key"],
    }
    task = {"md5sum": task_id, **scope}
    root = Path(module.app.config["storage_resolver"].get_task_root(task))
    root.mkdir(parents=True)
    artifact = root / "models" / "source.fasta"
    artifact.parent.mkdir()
    content = b">source\nACDEFG\n"
    if symlink:
        outside = root.parent / "outside.fasta"
        outside.write_bytes(content)
        artifact.symlink_to(outside)
    else:
        artifact.write_bytes(content)
    if publish:
        manifest = {
            "artifacts": [
                {
                    "path": "models/source.fasta",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                    "media_type": "text/plain",
                    "role": "artifact",
                }
            ]
        }
    else:
        manifest = {"artifacts": []}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    module.task_store.upsert_task(
        task_id,
        filename="input.fasta",
        file_path=str(artifact),
        uploaded_at=time.time(),
        started_at=time.time(),
        finished_at=time.time() if status == "finished" else None,
        status=status,
        is_binary=0,
        username=owner["username"],
        submitted_by_user_id=int(owner["id"]),
        task_type="gremlin",
        **scope,
    )
    return module.task_store.get_task(task_id), artifact


def _submit_reference(module, headers, source, *, project=None, path="models/source.fasta"):
    data = {
        "task_type": "gremlin",
        "artifact_references": f"@{source['md5sum']}/{path}",
        "scope_type": "project" if project else "personal",
    }
    if project:
        data["scope_id"] = str(project["id"])
    return module.app.test_client().post(
        "/compute/api/post", headers=headers, data=data, content_type="multipart/form-data"
    )


def _join_project(store, project, user, role):
    invitation = store.invite(project["id"], user["id"], project["owner_user_id"], role)
    assert store.respond_invitation(invitation["id"], user["id"], True)


def _disable_cancel_dispatch(module, monkeypatch):
    route_globals = module.app.view_functions["cancel_task"].__wrapped__.__globals__
    monkeypatch.setattr(route_globals["cancel_compute_resources"], "delay", lambda *args, **kwargs: None)


def test_own_personal_artifact_becomes_immutable_snapshot_with_provenance(module):
    alice, headers = _user(module, "alice")
    source, source_path = _source_task(module, alice)

    response = _submit_reference(module, headers, source)

    assert response.status_code == 302, response.get_data(as_text=True)
    task = module.task_store.get_task(response.headers["Location"].rsplit("/", 1)[-1])
    snapshot = Path(module.app.config["storage_resolver"].get_input_root(task)) / "inputs" / "source.fasta"
    assert snapshot.read_bytes() == source_path.read_bytes()
    assert "/users/" in module.app.config["storage_resolver"].get_task_root(task)
    provenance = json.loads(task["artifact_provenance"])
    assert provenance[0]["downstream_task_id"] == task["md5sum"]
    assert provenance[0]["source_task_id"] == source["md5sum"]
    assert provenance[0]["source_artifact_path"] == "models/source.fasta"
    assert provenance[0]["sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest()
    source_path.unlink()
    assert snapshot.is_file()


def test_same_project_contributor_can_reuse_but_viewer_cannot(module):
    alice, _ = _user(module, "alice")
    bob, bob_headers = _user(module, "bob")
    viewer, viewer_headers = _user(module, "viewer")
    store = module.app.config["collaboration"]
    project = store.create_project(alice["id"], "Shared Science")
    project["owner_user_id"] = alice["id"]
    _join_project(store, project, bob, "contributor")
    _join_project(store, project, viewer, "viewer")
    source, _ = _source_task(module, alice, project=project)

    allowed = _submit_reference(module, bob_headers, source, project=project)
    denied = _submit_reference(module, viewer_headers, source, project=project)

    assert allowed.status_code == 302
    task = module.task_store.get_task(allowed.headers["Location"].rsplit("/", 1)[-1])
    assert task["scope_type"] == "project"
    assert task["scope_id"] == str(project["id"])
    assert "/projects/" in module.app.config["storage_resolver"].get_task_root(task)
    assert denied.status_code == 403


def test_archived_project_artifacts_remain_reusable_but_project_is_frozen(module):
    alice, _ = _user(module, "alice")
    bob, bob_headers = _user(module, "bob")
    viewer, viewer_headers = _user(module, "viewer")
    store = module.app.config["collaboration"]
    project = store.create_project(alice["id"], "Frozen Science")
    project["owner_user_id"] = alice["id"]
    _join_project(store, project, bob, "contributor")
    _join_project(store, project, viewer, "viewer")
    source, _ = _source_task(module, alice, project=project)
    assert store.archive_project(project["id"])

    reused_to_personal = _submit_reference(module, bob_headers, source)
    viewer_denied = _submit_reference(module, viewer_headers, source)
    project_submission_denied = _submit_reference(module, bob_headers, source, project=project)

    assert reused_to_personal.status_code == 302
    downstream = module.task_store.get_task(reused_to_personal.headers["Location"].rsplit("/", 1)[-1])
    assert downstream["scope_type"] == "personal"
    assert json.loads(downstream["artifact_provenance"])[0]["source_scope_id"] == str(project["id"])
    assert viewer_denied.status_code == 403
    assert project_submission_denied.status_code == 403


def test_task_mutation_uses_immutable_submitter_id_across_username_rename(module, monkeypatch):
    alice, _ = _user(module, "alice")
    bob, bob_headers = _user(module, "bob")
    maintainer, maintainer_headers = _user(module, "maintainer")
    viewer, viewer_headers = _user(module, "viewer")
    store = module.app.config["collaboration"]
    project = store.create_project(alice["id"], "Identity")
    project["owner_user_id"] = alice["id"]
    for user, role in ((bob, "contributor"), (maintainer, "maintainer"), (viewer, "viewer")):
        _join_project(store, project, user, role)

    source, _ = _source_task(module, alice, project=project)
    submitted = _submit_reference(module, bob_headers, source, project=project)
    task_id = submitted.headers["Location"].rsplit("/", 1)[-1]
    task = module.task_store.get_task(task_id)
    assert task["submitted_by_user_id"] == bob["id"]

    _disable_cancel_dispatch(module, monkeypatch)
    module.app.config["user_db"].update_user(bob["id"], username="bob-renamed")
    impostor = module.app.config["user_db"].create_user(
        "bob",
        "bob-impostor@test.local",
        "password",
        registration_status="approved",
        user_status="active",
    )
    module.app.config["user_db"].verify_email(impostor["id"])
    from revocompute.auth import generate_token

    impostor_headers = {"Authorization": f"Bearer {generate_token(impostor['id'])}"}
    impostor = module.app.config["user_db"].get_user_by_username("bob")
    _join_project(store, project, impostor, "contributor")
    client = module.app.test_client()
    assert client.post(f"/compute/api/cancel/{task_id}", headers=impostor_headers).status_code == 403
    assert client.post(f"/compute/api/cancel/{task_id}", headers=bob_headers).status_code == 200

    other_source, _ = _source_task(module, alice, project=project)
    other_task_id = _submit_reference(module, bob_headers, other_source, project=project).headers["Location"].rsplit(
        "/", 1
    )[-1]
    assert client.post(f"/compute/api/cancel/{other_task_id}", headers=viewer_headers).status_code == 403
    assert client.post(f"/compute/api/cancel/{other_task_id}", headers=maintainer_headers).status_code == 200


def test_personal_task_mutation_remains_bound_to_user_id_after_rename(module, monkeypatch):
    alice, alice_headers = _user(module, "alice")
    source, _ = _source_task(module, alice)
    submitted = _submit_reference(module, alice_headers, source)
    task_id = submitted.headers["Location"].rsplit("/", 1)[-1]
    _disable_cancel_dispatch(module, monkeypatch)
    module.app.config["user_db"].update_user(alice["id"], username="alice-renamed")

    response = module.app.test_client().post(f"/compute/api/cancel/{task_id}", headers=alice_headers)

    assert response.status_code == 200
    assert module.task_store.get_task(task_id)["submitted_by_user_id"] == alice["id"]


def test_cross_user_and_cross_project_reuse_are_denied(module):
    alice, _ = _user(module, "alice")
    bob, bob_headers = _user(module, "bob")
    personal, _ = _source_task(module, alice)
    assert _submit_reference(module, bob_headers, personal).status_code == 403

    store = module.app.config["collaboration"]
    first = store.create_project(alice["id"], "First")
    second = store.create_project(alice["id"], "Second")
    for project in (first, second):
        invitation = store.invite(project["id"], bob["id"], alice["id"], "contributor")
        assert store.respond_invitation(invitation["id"], bob["id"], True)
    source, _ = _source_task(module, alice, project=first)
    assert _submit_reference(module, bob_headers, source, project=second).status_code == 403


@pytest.mark.parametrize("condition", ["non_final", "not_manifest", "traversal", "absolute", "symlink"])
def test_unusable_artifact_references_fail_closed(module, condition):
    alice, headers = _user(module, "alice")
    source, _ = _source_task(
        module,
        alice,
        status="running" if condition == "non_final" else "finished",
        publish=condition != "not_manifest",
        symlink=condition == "symlink",
    )
    path = {
        "traversal": "../models/source.fasta",
        "absolute": "/etc/passwd",
    }.get(condition, "models/source.fasta")

    response = _submit_reference(module, headers, source, path=path)

    assert response.status_code in {400, 403}
    assert b"/tmp/" not in response.data
