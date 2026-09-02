# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP authorization and lifecycle coverage for Project scope."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from conftest import _load_pssm_module, _test_client_auth


def _module(monkeypatch, tmp_path):
    return _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLED_TASKRUNNERS": "gremlin"},
    )


def _join(store, project_id, owner_id, user_id, role):
    invitation = store.invite(project_id, user_id, owner_id, role)
    assert store.respond_invitation(invitation["id"], user_id, True)


def _insert_project_task(module, project, submitter, *, status="pending"):
    task_id = uuid.uuid4().hex
    module.task_store.upsert_task(
        task_id,
        filename="input.fasta",
        file_path="/display-only/input.fasta",
        uploaded_at=time.time(),
        status=status,
        is_binary=0,
        username=submitter["username"],
        submitted_by_user_id=int(submitter["id"]),
        task_type="gremlin",
        scope_type="project",
        scope_id=str(project["id"]),
        storage_key=project["storage_key"],
    )
    return module.task_store.get_task(task_id)


def _publish_result_manifest(module, task):
    root = Path(module.app.config["storage_resolver"].get_task_root(task))
    root.mkdir(parents=True)
    artifacts = []
    for path, role, content in (
        ("models/model.pdb", "primary", b"ATOM\n"),
        ("logs/run.log", "diagnostic", b"private diagnostics\n"),
        ("provenance/source.json", "provenance", b"{}\n"),
    ):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        artifacts.append(
            {
                "path": path,
                "role": role,
                "media_type": "text/plain",
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "preview": "text",
                "cardinality": "one",
            }
        )
    manifest = {
        "artifacts": artifacts,
        "views": [
            {"type": "structure", "sources": {"structures": ["models/model.pdb"]}},
            {"type": "text", "sources": {"logs": ["logs/run.log"]}},
        ],
        "result": {"files": {"model": [artifacts[0]], "log": [artifacts[1]]}},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_project_visibility_discovery_and_private_lookup(monkeypatch, tmp_path):
    module = _module(monkeypatch, tmp_path)
    owner_headers = _test_client_auth(module, "owner")
    outsider_headers = _test_client_auth(module, "outsider")
    owner = module.app.config["user_db"].get_user_by_username("owner")
    store = module.app.config["collaboration"]
    private = store.create_project(owner["id"], "Private")
    internal = store.create_project(owner["id"], "Internal", visibility="internal")
    public = store.create_project(owner["id"], "Public", visibility="public")
    client = module.app.test_client()

    anonymous = client.get("/compute/api/projects").get_json()["projects"]
    authenticated = client.get("/compute/api/projects", headers=outsider_headers).get_json()["projects"]

    assert {item["id"] for item in anonymous} == {public["id"]}
    assert {item["id"] for item in authenticated} == {internal["id"], public["id"]}
    assert client.get(f"/compute/api/projects/{private['id']}", headers=outsider_headers).status_code == 404
    assert client.get(f"/compute/api/projects/{public['id']}").status_code == 200
    assert client.get(f"/compute/projects/{public['id']}").status_code == 200
    assert client.get(f"/compute/projects/{private['id']}", headers=owner_headers).status_code == 200


def test_duplicate_names_settings_invitation_and_archive_lifecycle(monkeypatch, tmp_path):
    module = _module(monkeypatch, tmp_path)
    owner_headers = _test_client_auth(module, "owner")
    invited_headers = _test_client_auth(module, "invited")
    invited = module.app.config["user_db"].get_user_by_username("invited")
    client = module.app.test_client()

    first = client.post(
        "/compute/api/projects",
        headers=owner_headers,
        json={"name": "Same Name", "visibility": "private"},
    )
    second = client.post(
        "/compute/api/projects",
        headers=owner_headers,
        json={"name": "Same Name", "visibility": "private"},
    )
    assert first.status_code == second.status_code == 201
    assert first.get_json()["slug"] != second.get_json()["slug"]
    project = first.get_json()
    storage_key = project["storage_key"]

    updated = client.patch(
        f"/compute/api/projects/{project['id']}",
        headers=owner_headers,
        json={"name": "Renamed", "description": "Science", "visibility": "internal"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["storage_key"] == storage_key

    invitation = client.post(
        f"/compute/api/projects/{project['id']}/invitations",
        headers=owner_headers,
        json={"user_id": invited["id"], "role": "contributor"},
    )
    assert invitation.status_code == 201
    accepted = client.post(
        f"/compute/api/invitations/{invitation.get_json()['id']}",
        headers=invited_headers,
        json={"action": "accept"},
    )
    assert accepted.status_code == 200
    assert module.app.config["collaboration"].can_submit_task(project["id"], invited["id"])

    archived = client.delete(f"/compute/api/projects/{project['id']}", headers=owner_headers)
    assert archived.status_code == 200
    archived_project = client.get(f"/compute/api/projects/{project['id']}", headers=owner_headers)
    assert archived_project.status_code == 200
    assert archived_project.get_json()["capabilities"] == [
        "use_artifacts",
        "view_project",
        "view_results",
        "view_tasks",
    ]
    assert client.patch(
        f"/compute/api/projects/{project['id']}", headers=owner_headers, json={"name": "Not mutable"}
    ).status_code == 404
    assert client.post(
        f"/compute/api/projects/{project['id']}/invitations",
        headers=owner_headers,
        json={"user_id": invited["id"], "role": "viewer"},
    ).status_code == 403
    assert client.patch(
        f"/compute/api/projects/{project['id']}/members/{invited['id']}",
        headers=owner_headers,
        json={"role": "viewer"},
    ).status_code == 403


def test_project_user_search_requires_invitation_capability_and_filters_candidates(monkeypatch, tmp_path):
    module = _module(monkeypatch, tmp_path)
    user_db = module.app.config["user_db"]
    headers = {name: _test_client_auth(module, name) for name in ("owner", "maintainer", "contributor", "viewer")}
    users = {name: user_db.get_user_by_username(name) for name in headers}
    candidate_headers = _test_client_auth(module, "search-candidate")
    del candidate_headers
    member_headers = _test_client_auth(module, "search-member")
    del member_headers
    pending_headers = _test_client_auth(module, "search-pending")
    del pending_headers
    deleted_headers = _test_client_auth(module, "search-deleted")
    del deleted_headers
    candidate = user_db.get_user_by_username("search-candidate")
    member = user_db.get_user_by_username("search-member")
    pending = user_db.get_user_by_username("search-pending")
    deleted = user_db.get_user_by_username("search-deleted")
    user_db.update_user(deleted["id"], deleted=True)

    store = module.app.config["collaboration"]
    project = store.create_project(users["owner"]["id"], "Search Scope")
    for role in ("maintainer", "contributor", "viewer"):
        _join(store, project["id"], users["owner"]["id"], users[role]["id"], role)
    _join(store, project["id"], users["owner"]["id"], member["id"], "viewer")
    store.invite(project["id"], pending["id"], users["owner"]["id"], "viewer")
    client = module.app.test_client()
    endpoint = f"/compute/api/projects/{project['id']}/users/search?q=search"

    assert client.get(endpoint).status_code == 401
    for role in ("contributor", "viewer"):
        assert client.get(endpoint, headers=headers[role]).status_code == 403
    for role in ("owner", "maintainer"):
        response = client.get(endpoint, headers=headers[role])
        assert response.status_code == 200
        assert response.get_json()["users"] == [
            {"id": candidate["id"], "username": "search-candidate", "display_name": "search-candidate"}
        ]
    assert client.get(f"/compute/api/projects/{project['id']}/users/search?q=s", headers=headers["owner"]).json == {
        "users": []
    }
    assert client.get("/compute/api/users/search?q=search", headers=headers["owner"]).status_code == 404


def test_project_task_attribution_is_visible_only_to_members_and_admin(monkeypatch, tmp_path):
    module = _module(monkeypatch, tmp_path)
    owner_headers = _test_client_auth(module, "owner")
    outsider_headers = _test_client_auth(module, "outsider")
    admin_headers = _test_client_auth(module, "project-admin")
    admin = module.app.config["user_db"].get_user_by_username("project-admin")
    module.app.config["user_db"].update_user(admin["id"], role="admin")
    owner = module.app.config["user_db"].get_user_by_username("owner")
    store = module.app.config["collaboration"]
    project = store.create_project(owner["id"], "Published Tasks", visibility="internal")
    task = _insert_project_task(module, project, owner)
    _insert_project_task(module, project, owner, status="deleted:cancel")
    client = module.app.test_client()
    endpoint = f"/compute/api/projects/{project['id']}/tasks"

    member_task = client.get(endpoint, headers=owner_headers).json["tasks"][0]
    outsider_task = client.get(endpoint, headers=outsider_headers).json["tasks"][0]
    admin_task = client.get(endpoint, headers=admin_headers).json["tasks"][0]
    assert member_task["submitted_by"] == "owner"
    assert outsider_task["submitted_by"] is None
    assert admin_task["submitted_by"] == "owner"
    assert "username" not in member_task | outsider_task | admin_task
    assert len(client.get(endpoint, headers=owner_headers).json["tasks"]) == 1
    assert client.get(f"/compute/api/projects/{project['id']}", headers=owner_headers).json["task_count"] == 1

    assert client.get(f"/compute/api/running/{task['md5sum']}", headers=outsider_headers).status_code == 202
    assert client.get(f"/compute/results/{task['md5sum']}", headers=outsider_headers).status_code == 200
    assert client.get(f"/compute/api/tasks/{task['md5sum']}/input", headers=outsider_headers).status_code == 403

    store.update_project(project["id"], visibility="public")
    assert client.get(endpoint).json["tasks"][0]["submitted_by"] is None
    assert client.get(f"/compute/api/running/{task['md5sum']}").status_code == 202
    assert client.get(f"/compute/results/{task['md5sum']}").status_code == 200
    assert client.get(f"/compute/api/tasks/{task['md5sum']}/input").status_code == 401


def test_public_project_failure_hides_diagnostics_from_non_members(monkeypatch, tmp_path):
    module = _module(monkeypatch, tmp_path)
    owner_headers = _test_client_auth(module, "owner")
    owner = module.app.config["user_db"].get_user_by_username("owner")
    project = module.app.config["collaboration"].create_project(owner["id"], "Public Failure", visibility="public")
    task = _insert_project_task(module, project, owner, status="failed")
    module.task_store.update_task(task["md5sum"], error="private runner path: /srv/results/secret")
    client = module.app.test_client()

    public_payload = client.get(f"/compute/api/running/{task['md5sum']}").get_json()
    owner_payload = client.get(f"/compute/api/running/{task['md5sum']}", headers=owner_headers).get_json()

    assert public_payload["error"] == "Task failed"
    assert "private runner path" not in public_payload["error"]
    assert owner_payload["error"] != "Task failed"


def test_project_visibility_drives_filtered_result_workspace(monkeypatch, tmp_path):
    module = _module(monkeypatch, tmp_path)
    owner_headers = _test_client_auth(module, "owner")
    outsider_headers = _test_client_auth(module, "outsider")
    owner = module.app.config["user_db"].get_user_by_username("owner")
    store = module.app.config["collaboration"]
    client = module.app.test_client()

    projects = {
        visibility: store.create_project(owner["id"], visibility.title(), visibility=visibility)
        for visibility in ("private", "internal", "public")
    }
    tasks = {
        visibility: _insert_project_task(module, project, owner, status="finished")
        for visibility, project in projects.items()
    }
    for task in tasks.values():
        _publish_result_manifest(module, task)

    for visibility, task in tasks.items():
        page = f"/compute/results/{task['md5sum']}"
        api = f"/compute/api/results/{task['md5sum']}"
        assert client.get(page, headers=owner_headers).status_code == 200
        owner_payload = client.get(api, headers=owner_headers).get_json()
        assert owner_payload["archive"]["request_url"]
        assert {artifact["role"] for artifact in owner_payload["artifacts"]} == {
            "primary",
            "diagnostic",
            "provenance",
        }
        assert client.get(
            f"/compute/api/results/{task['md5sum']}/artifacts/logs/run.log", headers=owner_headers
        ).status_code == 200
        outsider_status = 403 if visibility == "private" else 200
        anonymous_status = 200 if visibility == "public" else 403
        assert client.get(page, headers=outsider_headers).status_code == outsider_status
        assert client.get(page).status_code == anonymous_status
        assert client.get(api, headers=outsider_headers).status_code == outsider_status
        assert client.get(api).status_code == anonymous_status

    for headers in (outsider_headers, None):
        task = tasks["internal" if headers else "public"]
        request_headers = headers or {}
        page = client.get(f"/compute/results/{task['md5sum']}", headers=request_headers)
        payload = client.get(f"/compute/api/results/{task['md5sum']}", headers=request_headers).get_json()
        artifact_root = f"/compute/api/results/{task['md5sum']}/artifacts/"

        assert '"owner"' not in page.text
        assert "/display-only/input.fasta" not in page.text
        assert {artifact["path"] for artifact in payload["artifacts"]} == {"models/model.pdb"}
        assert payload["archive"] == {"ready": False, "request_url": None, "download_url": None}
        assert payload["views"] == [{"type": "structure", "sources": {"structures": ["models/model.pdb"]}}]
        assert client.get(artifact_root + "models/model.pdb", headers=request_headers).status_code == 200
        assert client.get(artifact_root + "logs/run.log", headers=request_headers).status_code == 404
        assert client.get(artifact_root + "provenance/source.json", headers=request_headers).status_code == 404
        assert client.post(f"/compute/api/results/{task['md5sum']}/archive", headers=request_headers).status_code in {
            401,
            403,
        }


def test_personal_result_routes_remain_private(monkeypatch, tmp_path):
    module = _module(monkeypatch, tmp_path)
    owner_headers = _test_client_auth(module, "owner")
    outsider_headers = _test_client_auth(module, "outsider")
    admin_headers = _test_client_auth(module, "admin-reader")
    user_db = module.app.config["user_db"]
    owner = user_db.get_user_by_username("owner")
    admin = user_db.get_user_by_username("admin-reader")
    user_db.update_user(admin["id"], role="admin")
    task_id = uuid.uuid4().hex
    module.task_store.upsert_task(
        task_id,
        filename="personal.fasta",
        file_path="/display-only/personal.fasta",
        uploaded_at=time.time(),
        status="finished",
        is_binary=0,
        username=owner["username"],
        submitted_by_user_id=int(owner["id"]),
        task_type="gremlin",
        scope_type="personal",
        scope_id=str(owner["id"]),
        storage_key=owner["storage_key"],
    )
    task = module.task_store.get_task(task_id)
    _publish_result_manifest(module, task)
    client = module.app.test_client()

    for suffix in (f"/compute/results/{task_id}", f"/compute/api/results/{task_id}", f"/compute/api/results/{task_id}/artifacts/models/model.pdb"):
        assert client.get(suffix, headers=owner_headers).status_code == 200
        assert client.get(suffix, headers=admin_headers).status_code == 200
        assert client.get(suffix, headers=outsider_headers).status_code == 403
        assert client.get(suffix).status_code == 403
