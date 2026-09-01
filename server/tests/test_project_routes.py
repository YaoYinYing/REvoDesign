# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP authorization and lifecycle coverage for Project scope."""

from __future__ import annotations

from conftest import _load_pssm_module, _test_client_auth


def _module(monkeypatch, tmp_path):
    return _load_pssm_module(
        monkeypatch,
        tmp_path,
        extra_env={"RUNNER_UID": "1234", "RUNNER_GID": "5678", "ENABLED_TASKRUNNERS": "gremlin"},
    )


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
    assert client.get(f"/compute/api/projects/{project['id']}", headers=owner_headers).status_code == 404
