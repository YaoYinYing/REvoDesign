# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import time

import pytest

from revocompute.collaboration import CollaborationStore


@pytest.fixture
def store(tmp_path):
    return CollaborationStore(str(tmp_path / "collaboration.sqlite3"))


def test_create_duplicate_slug_and_immutable_storage_identity(store):
    first = store.create_project(1, "Protein Design")
    second = store.create_project(2, "Protein Design")
    assert first["slug"] == "protein-design"
    assert second["slug"] == "protein-design-2"
    assert first["storage_key"] != second["storage_key"]
    storage_key = first["storage_key"]
    assert store.rename_project(first["id"], "Renamed")
    renamed = store.get_project(first["id"])
    assert renamed["storage_key"] == storage_key
    assert renamed["slug"] == "protein-design"
    with pytest.raises(ValueError, match="slug is immutable"):
        store.rename_project(first["id"], "Again", slug="again")


def test_visibility_discovery_and_archival(store):
    private = store.create_project(1, "Private")
    internal = store.create_project(2, "Internal", visibility="internal")
    public = store.create_project(3, "Public", visibility="public")
    assert {p["id"] for p in store.list_projects(None, authenticated=False)} == {public["id"]}
    assert {p["id"] for p in store.list_projects(99)} == {internal["id"], public["id"]}
    assert store.can_submit_task(private["id"], 1)
    assert not store.can_submit_task(internal["id"], 99)
    assert store.archive_project(public["id"])
    assert not store.archive_project(public["id"])
    assert not store.can_view_project(public["id"], None, authenticated=False)


def test_effective_capabilities_for_members_and_outsiders(store):
    private = store.create_project(1, "Private")
    internal = store.create_project(2, "Internal", visibility="internal")
    public = store.create_project(3, "Public", visibility="public")
    assert "transfer_ownership" in store.capabilities(private["id"], 1)
    assert store.capabilities(private["id"], 99) == []
    assert store.capabilities(internal["id"], 99) == ["view_project", "view_results", "view_tasks"]
    assert store.capabilities(internal["id"], None, authenticated=False) == []
    assert store.capabilities(public["id"], None, authenticated=False) == [
        "view_project",
        "view_results",
        "view_tasks",
    ]
    assert store.archive_project(public["id"])
    assert store.capabilities(public["id"], 3) == []


def test_invitation_accept_decline_duplicate_and_expire(store):
    project = store.create_project(1, "Team")
    invitation = store.invite(project["id"], 2, 1, "contributor")
    with pytest.raises(ValueError, match="pending invitation"):
        store.invite(project["id"], 2, 1, "viewer")
    assert not store.respond_invitation(invitation["id"], 3, True)
    assert store.respond_invitation(invitation["id"], 2, True)
    assert store.get_membership(project["id"], 2)["role"] == "contributor"
    assert store.can_use_artifact(project["id"], 2)
    with pytest.raises(ValueError, match="already a project member"):
        store.invite(project["id"], 2, 1)

    declined = store.invite(project["id"], 3, 1)
    assert store.respond_invitation(declined["id"], 3, False)
    assert store.get_invitation(declined["id"])["status"] == "declined"

    expired = store.invite(project["id"], 4, 1, expires_at=time.time() + 0.01)
    time.sleep(0.02)
    assert not store.respond_invitation(expired["id"], 4, True)
    assert store.get_invitation(expired["id"])["status"] == "expired"


def test_invitation_revoke_and_listing(store):
    project = store.create_project(1, "Team")
    invitation = store.invite(project["id"], 2, 1)
    assert store.list_invitations(2) == [invitation]
    assert store.revoke_invitation(invitation["id"])
    assert not store.revoke_invitation(invitation["id"])
    assert store.list_invitations(2) == []
    assert store.list_invitations(2, status="revoked")[0]["id"] == invitation["id"]


def test_list_project_invitations_filters_and_refreshes_expiry(store):
    project = store.create_project(1, "Team")
    other_project = store.create_project(3, "Other")
    pending = store.invite(project["id"], 2, 1)
    revoked = store.invite(project["id"], 3, 1)
    assert store.revoke_invitation(revoked["id"])
    expiring = store.invite(project["id"], 4, 1, expires_at=time.time() + 0.01)
    store.invite(other_project["id"], 5, 3)
    time.sleep(0.02)

    invitations = store.list_project_invitations(project["id"])
    assert {item["id"] for item in invitations} == {pending["id"], revoked["id"], expiring["id"]}
    assert store.get_invitation(expiring["id"])["status"] == "expired"
    assert [item["id"] for item in store.list_project_invitations(project["id"], status="pending")] == [pending["id"]]
    assert [item["id"] for item in store.list_project_invitations(project["id"], status="expired")] == [expiring["id"]]
    with pytest.raises(ValueError, match="invalid invitation status"):
        store.list_project_invitations(project["id"], status="unknown")


def test_member_roles_removal_and_ownership_transfer(store):
    project = store.create_project(1, "Team")
    invitation = store.invite(project["id"], 2, 1, "viewer")
    assert store.respond_invitation(invitation["id"], 2, True)
    assert not store.can_use_artifact(project["id"], 2)
    assert store.set_member_role(project["id"], 2, "maintainer")
    assert store.can_manage_members(project["id"], 2)
    with pytest.raises(ValueError, match="transfer_ownership"):
        store.set_member_role(project["id"], 2, "owner")
    assert not store.remove_member(project["id"], 1)
    assert store.transfer_ownership(project["id"], 1, 2)
    assert store.get_membership(project["id"], 2)["role"] == "owner"
    assert store.get_membership(project["id"], 1)["role"] == "maintainer"
    assert store.remove_member(project["id"], 1)


def test_reopen_existing_database_preserves_records(store):
    project = store.create_project(1, "Persistent")
    reopened = CollaborationStore(store.path)
    assert reopened.get_project(project["id"])["storage_key"] == project["storage_key"]
    assert reopened.get_membership(project["id"], 1)["role"] == "owner"
