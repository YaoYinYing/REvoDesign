# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP authorization and lifecycle coverage for Project scope."""

from __future__ import annotations

import time
import uuid

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
    _insert_project_task(module, project, owner)
    client = module.app.test_client()
    endpoint = f"/compute/api/projects/{project['id']}/tasks"

    member_task = client.get(endpoint, headers=owner_headers).json["tasks"][0]
    outsider_task = client.get(endpoint, headers=outsider_headers).json["tasks"][0]
    admin_task = client.get(endpoint, headers=admin_headers).json["tasks"][0]
    assert member_task["submitted_by"] == "owner"
    assert outsider_task["submitted_by"] is None
    assert admin_task["submitted_by"] == "owner"
    assert "username" not in member_task | outsider_task | admin_task

    store.update_project(project["id"], visibility="public")
    assert client.get(endpoint).json["tasks"][0]["submitted_by"] is None
