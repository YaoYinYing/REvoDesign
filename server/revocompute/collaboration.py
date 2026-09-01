# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Project collaboration and scope authorization primitives.

This module deliberately owns a separate SQLite database from ``UserDatabase``.
User ids are opaque foreign-key values; account lifecycle remains the concern of
``auth.UserDatabase``.
"""

from __future__ import annotations

import re
import secrets
import time
import unicodedata
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text


PROJECT_VISIBILITIES = frozenset({"private", "internal", "public"})
PROJECT_ROLES = frozenset({"owner", "maintainer", "contributor", "viewer"})
INVITATION_STATUSES = frozenset({"pending", "accepted", "declined", "revoked", "expired"})

# Capabilities are intentionally explicit and centralized.  A viewer can read
# but cannot submit or reuse artifacts; contributors can submit and reuse.
ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "owner": frozenset({
        "view_project", "view_tasks", "view_results", "use_artifacts",
        "submit_tasks", "cancel_own_tasks", "cancel_project_tasks",
        "invite_members", "manage_members", "change_project_settings",
        "delete_project", "transfer_ownership",
    }),
    "maintainer": frozenset({
        "view_project", "view_tasks", "view_results", "use_artifacts",
        "submit_tasks", "cancel_own_tasks", "cancel_project_tasks",
        "invite_members", "manage_members", "change_project_settings",
    }),
    "contributor": frozenset({
        "view_project", "view_tasks", "view_results", "use_artifacts",
        "submit_tasks", "cancel_own_tasks",
    }),
    "viewer": frozenset({"view_project", "view_tasks", "view_results"}),
}


def _storage_prefix(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return (value or "scope")[:32]


def new_storage_key(display_name: str) -> str:
    """Return a readable, opaque and immutable storage namespace key."""
    return f"{_storage_prefix(display_name)}-{secrets.token_urlsafe(6).lower().replace('_', '-').replace('=', '')}"


class CollaborationDatabase:
    """SQLite-backed Projects, memberships and invitations."""

    def __init__(self, path: str):
        import os

        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.engine = sa.create_engine(
            f"sqlite:///{self.path}", future=True,
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        self.metadata = MetaData()
        self.projects = Table(
            "projects", self.metadata,
            Column("id", Integer, primary_key=True), Column("name", String(200), nullable=False),
            Column("slug", String(200), nullable=False, unique=True), Column("description", Text),
            Column("visibility", String(16), nullable=False, default="private"),
            Column("storage_key", String(128), nullable=False, unique=True),
            Column("created_at", Float, nullable=False), Column("updated_at", Float, nullable=False),
            Column("archived_at", Float),
        )
        self.members = Table(
            "project_members", self.metadata,
            Column("project_id", Integer, primary_key=True), Column("user_id", Integer, primary_key=True),
            Column("role", String(16), nullable=False), Column("created_at", Float, nullable=False),
        )
        self.invitations = Table(
            "project_invitations", self.metadata,
            Column("id", Integer, primary_key=True), Column("project_id", Integer, nullable=False),
            Column("invited_user_id", Integer, nullable=False), Column("invited_by", Integer, nullable=False),
            Column("proposed_role", String(16), nullable=False), Column("status", String(16), nullable=False),
            Column("created_at", Float, nullable=False), Column("expires_at", Float, nullable=False),
            Column("accepted_at", Float),
        )
        sa.Index("uq_pending_project_invite", self.invitations.c.project_id, self.invitations.c.invited_user_id, unique=True, sqlite_where=self.invitations.c.status == "pending")
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA busy_timeout=30000")
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            self.metadata.create_all(conn, checkfirst=True)

    @staticmethod
    def _row(row: Any) -> dict[str, Any] | None:
        return dict(row._mapping) if row is not None else None

    def create_project(self, name: str | int, owner_user_id: int | str, *, slug: str | None = None, description: str | None = None, visibility: str = "private") -> dict[str, Any]:
        # Accept both ``(name, owner_id)`` and the Flask-facing ``(owner_id, name)``.
        if isinstance(name, int) and isinstance(owner_user_id, str):
            name, owner_user_id = owner_user_id, name
        name = str(name)
        owner_user_id = int(owner_user_id)
        if visibility not in PROJECT_VISIBILITIES:
            raise ValueError("invalid project visibility")
        slug = slug or _storage_prefix(name)
        now = time.time()
        with self.engine.begin() as conn:
            result = conn.execute(sa.insert(self.projects).values(name=name, slug=slug, description=description, visibility=visibility, storage_key=new_storage_key(name), created_at=now, updated_at=now))
            project_id = result.inserted_primary_key[0]
            conn.execute(sa.insert(self.members).values(project_id=project_id, user_id=owner_user_id, role="owner", created_at=now))
        return self.get_project(project_id)  # type: ignore[return-value]

    def get_project(self, project_id: int | str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(self.projects).where(self.projects.c.id == project_id)).first()
        return self._row(row)

    def get_project_by_slug(self, slug: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(self.projects).where(self.projects.c.slug == slug)).first()
        return self._row(row)

    def list_projects(self, user_id: int, *, authenticated: bool = True) -> list[dict[str, Any]]:
        """List member projects plus discoverable internal/public projects."""
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(self.projects).join(self.members, self.projects.c.id == self.members.c.project_id).where(self.members.c.user_id == user_id)).mappings().all()
            if authenticated:
                rows += conn.execute(sa.select(self.projects).where(self.projects.c.visibility.in_(["internal", "public"]), self.projects.c.archived_at.is_(None))).mappings().all()
        seen=set(); result=[]
        for row in rows:
            if row["id"] not in seen and row.get("archived_at") is None: seen.add(row["id"]); result.append(dict(row))
        return result

    def membership(self, project_id: int | str, user_id: int):
        return self.get_membership(project_id, user_id)

    def rename_project(self, project_id: int, name: str, *, slug: str | None = None) -> None:
        if not str(name).strip():
            raise ValueError("project name cannot be empty")
        values = {"name": name, "updated_at": time.time()}
        if slug is not None:
            values["slug"] = slug
        with self.engine.begin() as conn:
            conn.execute(sa.update(self.projects).where(self.projects.c.id == project_id).values(**values))

    def archive_project(self, project_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(sa.update(self.projects).where(self.projects.c.id == project_id).values(archived_at=time.time(), updated_at=time.time()))

    def update_project(self, project_id: int, **fields: Any) -> None:
        """Update mutable settings while preserving the immutable storage key."""
        allowed = {"name", "description", "visibility"}
        values = {k: v for k, v in fields.items() if k in allowed}
        if "visibility" in values and values["visibility"] not in PROJECT_VISIBILITIES:
            raise ValueError("invalid project visibility")
        if "name" in values and not str(values["name"]).strip():
            raise ValueError("project name cannot be empty")
        if not values:
            return
        values["updated_at"] = time.time()
        with self.engine.begin() as conn:
            conn.execute(sa.update(self.projects).where(self.projects.c.id == project_id).values(**values))

    def list_members(self, project_id: int) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            return [self._row(r) for r in conn.execute(sa.select(self.members).where(self.members.c.project_id == project_id)).all()]  # type: ignore[misc]

    def get_membership(self, project_id: int, user_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(self.members).where(self.members.c.project_id == project_id, self.members.c.user_id == user_id)).first()
        return self._row(row)

    def set_member_role(self, project_id: int, user_id: int, role: str) -> bool:
        if role not in PROJECT_ROLES or role == "owner":
            raise ValueError("invalid member role")
        with self.engine.begin() as conn:
            return conn.execute(sa.update(self.members).where(self.members.c.project_id == project_id, self.members.c.user_id == user_id).values(role=role)).rowcount == 1

    def remove_member(self, project_id: int, user_id: int) -> bool:
        """Remove a non-owner member; the sole owner cannot be removed."""
        membership = self.get_membership(project_id, user_id)
        if not membership or membership["role"] == "owner":
            return False
        with self.engine.begin() as conn:
            return conn.execute(sa.delete(self.members).where(self.members.c.project_id == project_id, self.members.c.user_id == user_id)).rowcount == 1

    def invite(self, project_id: int, invited_user_id: int, invited_by: int, role: str = "viewer", *, expires_at: float | None = None) -> dict[str, Any]:
        if role not in PROJECT_ROLES or role == "owner":
            raise ValueError("invalid invitation role")
        now = time.time()
        with self.engine.begin() as conn:
            result = conn.execute(sa.insert(self.invitations).values(project_id=project_id, invited_user_id=invited_user_id, invited_by=invited_by, proposed_role=role, status="pending", created_at=now, expires_at=expires_at or now + 7 * 86400))
            invitation_id = result.inserted_primary_key[0]
        return self.get_invitation(invitation_id)  # type: ignore[return-value]

    def get_invitation(self, invitation_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            return self._row(conn.execute(sa.select(self.invitations).where(self.invitations.c.id == invitation_id)).first())

    def revoke_invitation(self, invitation_id: int) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(sa.update(self.invitations).where(self.invitations.c.id == invitation_id, self.invitations.c.status == "pending").values(status="revoked")).rowcount == 1

    def respond_invitation(self, invitation_id: int, user_id: int, accepted: bool) -> bool:
        now = time.time()
        with self.engine.begin() as conn:
            inv = conn.execute(sa.select(self.invitations).where(self.invitations.c.id == invitation_id, self.invitations.c.invited_user_id == user_id, self.invitations.c.status == "pending")).first()
            if not inv or inv.expires_at < now:
                if inv:
                    conn.execute(sa.update(self.invitations).where(self.invitations.c.id == invitation_id).values(status="expired"))
                return False
            status = "accepted" if accepted else "declined"
            conn.execute(sa.update(self.invitations).where(self.invitations.c.id == invitation_id).values(status=status, accepted_at=now if accepted else None))
            if accepted:
                conn.execute(sa.insert(self.members).values(project_id=inv.project_id, user_id=user_id, role=inv.proposed_role, created_at=now).prefix_with("OR REPLACE"))
            return True

    def can(self, project_id: int, user_id: int | None, capability: str, *, authenticated: bool = True) -> bool:
        project = self.get_project(project_id)
        if not project or project["archived_at"] is not None:
            return False
        if project["visibility"] == "public" and capability in {"view_project", "view_tasks", "view_results"}:
            return True
        if project["visibility"] == "internal" and authenticated and capability in {"view_project", "view_tasks", "view_results"}:
            return True
        if user_id is None:
            return False
        membership = self.get_membership(project_id, user_id)
        return bool(membership and capability in ROLE_CAPABILITIES.get(membership["role"], frozenset()))

    can_view_project = lambda self, project_id, user_id=None, **kw: self.can(project_id, user_id, "view_project", **kw)
    can_submit_task = lambda self, project_id, user_id: self.can(project_id, user_id, "submit_tasks")
    can_use_artifact = lambda self, project_id, user_id: self.can(project_id, user_id, "use_artifacts")
    can_manage_members = lambda self, project_id, user_id: self.can(project_id, user_id, "manage_members")


ProjectDatabase = CollaborationDatabase
# Name used by the Flask application wiring.
CollaborationStore = CollaborationDatabase
