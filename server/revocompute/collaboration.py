# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""SQLite-backed Project collaboration and authorization primitives."""

from __future__ import annotations

import os
import re
import secrets
import time
import unicodedata
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from revocompute.schema_epoch import require_current_schema

PROJECT_VISIBILITIES = frozenset({"private", "internal", "public"})
PROJECT_ROLES = frozenset({"owner", "maintainer", "contributor", "viewer"})
INVITATION_STATUSES = frozenset({"pending", "accepted", "declined", "revoked", "expired"})
READ_CAPABILITIES = frozenset({"view_project", "view_tasks", "view_results"})
ARCHIVED_MEMBER_CAPABILITIES = READ_CAPABILITIES | {"use_artifacts"}
ROLE_CAPABILITIES = {
    "owner": frozenset(
        {
            *READ_CAPABILITIES,
            "use_artifacts",
            "submit_tasks",
            "cancel_own_tasks",
            "cancel_project_tasks",
            "invite_members",
            "manage_members",
            "change_project_settings",
            "delete_project",
            "transfer_ownership",
        }
    ),
    "maintainer": frozenset(
        {
            *READ_CAPABILITIES,
            "use_artifacts",
            "submit_tasks",
            "cancel_own_tasks",
            "cancel_project_tasks",
            "invite_members",
            "manage_members",
            "change_project_settings",
        }
    ),
    "contributor": frozenset({*READ_CAPABILITIES, "use_artifacts", "submit_tasks", "cancel_own_tasks"}),
    "viewer": READ_CAPABILITIES,
}


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return (re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "project")[:80]


def new_storage_key(display_name: str) -> str:
    """Create a readable key whose identity is a random immutable suffix."""
    suffix = secrets.token_urlsafe(8).lower().replace("_", "-").replace("=", "")
    return f"{_slug(display_name)[:32]}-{suffix}"


class CollaborationDatabase:
    """Project store independent from ``UserDatabase``.

    User ids are opaque values. Callers verify account existence before invite.
    """

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.engine = sa.create_engine(
            f"sqlite:///{self.path}", future=True, connect_args={"check_same_thread": False, "timeout": 30}
        )
        self.metadata = sa.MetaData()
        self.projects = sa.Table(
            "projects",
            self.metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(200), nullable=False, unique=True),
            sa.Column("description", sa.Text),
            sa.Column("visibility", sa.String(16), nullable=False, server_default="private"),
            sa.Column("storage_key", sa.String(128), nullable=False, unique=True),
            sa.Column("created_at", sa.Float, nullable=False),
            sa.Column("updated_at", sa.Float, nullable=False),
            sa.Column("archived_at", sa.Float),
            sa.CheckConstraint("visibility IN ('private','internal','public')", name="ck_project_visibility"),
        )
        self.members = sa.Table(
            "project_members",
            self.metadata,
            sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("user_id", sa.Integer, primary_key=True),
            sa.Column("role", sa.String(16), nullable=False),
            sa.Column("created_at", sa.Float, nullable=False),
            sa.CheckConstraint("role IN ('owner','maintainer','contributor','viewer')", name="ck_member_role"),
        )
        self.invitations = sa.Table(
            "project_invitations",
            self.metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("invited_user_id", sa.Integer, nullable=False),
            sa.Column("invited_by", sa.Integer, nullable=False),
            sa.Column("proposed_role", sa.String(16), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("created_at", sa.Float, nullable=False),
            sa.Column("expires_at", sa.Float, nullable=False),
            sa.Column("accepted_at", sa.Float),
            sa.CheckConstraint("proposed_role IN ('maintainer','contributor','viewer')", name="ck_invite_role"),
            sa.CheckConstraint(
                "status IN ('pending','accepted','declined','revoked','expired')", name="ck_invite_status"
            ),
        )
        sa.Index("ix_project_members_user", self.members.c.user_id)
        sa.Index(
            "uq_project_owner",
            self.members.c.project_id,
            unique=True,
            sqlite_where=self.members.c.role == "owner",
        )
        sa.Index("ix_project_invitations_user_status", self.invitations.c.invited_user_id, self.invitations.c.status)
        sa.Index(
            "uq_pending_project_invite",
            self.invitations.c.project_id,
            self.invitations.c.invited_user_id,
            unique=True,
            sqlite_where=self.invitations.c.status == "pending",
        )
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA busy_timeout=30000")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            require_current_schema(
                conn,
                {
                    "projects": {column.name for column in self.projects.columns},
                    "project_members": {column.name for column in self.members.columns},
                    "project_invitations": {column.name for column in self.invitations.columns},
                },
                database_name="collaboration database",
            )
            self.metadata.create_all(conn, checkfirst=True)

    @staticmethod
    def _row(row: Any) -> dict[str, Any] | None:
        return dict(row._mapping) if row is not None else None

    def _unique_slug(self, conn: Any, requested: str) -> str:
        base, candidate, number = _slug(requested), _slug(requested), 2
        while conn.execute(sa.select(self.projects.c.id).where(self.projects.c.slug == candidate)).first():
            candidate, number = f"{base[:75]}-{number}", number + 1
        return candidate

    def create_project(
        self,
        owner_user_id: int,
        name: str,
        *,
        slug: str | None = None,
        description: str | None = None,
        visibility: str = "private",
    ) -> dict[str, Any]:
        """Create the project and sole owner membership atomically."""
        name = str(name).strip()
        if not name:
            raise ValueError("project name cannot be empty")
        if visibility not in PROJECT_VISIBILITIES:
            raise ValueError("invalid project visibility")
        now = time.time()
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    sa.insert(self.projects).values(
                        name=name,
                        slug=self._unique_slug(conn, slug or name),
                        description=description,
                        visibility=visibility,
                        storage_key=new_storage_key(name),
                        created_at=now,
                        updated_at=now,
                    )
                )
                project_id = result.inserted_primary_key[0]
                conn.execute(
                    sa.insert(self.members).values(
                        project_id=project_id, user_id=int(owner_user_id), role="owner", created_at=now
                    )
                )
        except IntegrityError as exc:
            raise ValueError("project identifier could not be allocated; retry creation") from exc
        return self.get_project(project_id)  # type: ignore[return-value]

    def get_project(self, project_id: int | str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            return self._row(conn.execute(sa.select(self.projects).where(self.projects.c.id == project_id)).first())

    def get_project_by_slug(self, slug: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            return self._row(conn.execute(sa.select(self.projects).where(self.projects.c.slug == slug)).first())

    def list_projects(self, user_id: int | None, *, authenticated: bool = True) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(self.projects)).all()
        return [
            project
            for row in rows
            if (project := self._row(row))
            and self.can(project["id"], user_id, "view_project", authenticated=authenticated)
        ]

    def update_project(self, project_id: int, **fields: Any) -> bool:
        unknown = set(fields) - {"name", "description", "visibility"}
        if unknown:
            raise ValueError(f"unsupported project fields: {', '.join(sorted(unknown))}")
        if "name" in fields:
            fields["name"] = str(fields["name"]).strip()
            if not fields["name"]:
                raise ValueError("project name cannot be empty")
        if "visibility" in fields and fields["visibility"] not in PROJECT_VISIBILITIES:
            raise ValueError("invalid project visibility")
        if not fields:
            return False
        fields["updated_at"] = time.time()
        with self.engine.begin() as conn:
            return (
                conn.execute(
                    sa.update(self.projects)
                    .where(self.projects.c.id == project_id, self.projects.c.archived_at.is_(None))
                    .values(**fields)
                ).rowcount
                == 1
            )

    def rename_project(self, project_id: int, name: str, *, slug: str | None = None) -> bool:
        if slug is not None:
            raise ValueError("project slug is immutable")
        return self.update_project(project_id, name=name)

    def archive_project(self, project_id: int) -> bool:
        now = time.time()
        with self.engine.begin() as conn:
            archived = conn.execute(
                sa.update(self.projects)
                .where(self.projects.c.id == project_id, self.projects.c.archived_at.is_(None))
                .values(archived_at=now, updated_at=now)
            ).rowcount
            if archived != 1:
                return False
            conn.execute(
                sa.update(self.invitations)
                .where(self.invitations.c.project_id == project_id, self.invitations.c.status == "pending")
                .values(status="revoked")
            )
            return True

    def list_members(self, project_id: int) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            return [
                dict(row._mapping)
                for row in conn.execute(
                    sa.select(self.members)
                    .where(self.members.c.project_id == project_id)
                    .order_by(self.members.c.created_at)
                )
            ]

    def get_membership(self, project_id: int | str, user_id: int) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            return self._row(
                conn.execute(
                    sa.select(self.members).where(
                        self.members.c.project_id == project_id, self.members.c.user_id == user_id
                    )
                ).first()
            )

    membership = get_membership

    def set_member_role(self, project_id: int, user_id: int, role: str) -> bool:
        if role not in PROJECT_ROLES or role == "owner":
            raise ValueError("owner changes require transfer_ownership")
        if not self._project_is_active(project_id):
            return False
        with self.engine.begin() as conn:
            return (
                conn.execute(
                    sa.update(self.members)
                    .where(
                        self.members.c.project_id == project_id,
                        self.members.c.user_id == user_id,
                        self.members.c.role != "owner",
                    )
                    .values(role=role)
                ).rowcount
                == 1
            )

    def transfer_ownership(self, project_id: int, current_owner_id: int, new_owner_id: int) -> bool:
        if not self._project_is_active(project_id):
            return False
        with self.engine.begin() as conn:
            current = conn.execute(
                sa.select(self.members.c.role).where(
                    self.members.c.project_id == project_id, self.members.c.user_id == current_owner_id
                )
            ).scalar_one_or_none()
            target = conn.execute(
                sa.select(self.members.c.role).where(
                    self.members.c.project_id == project_id, self.members.c.user_id == new_owner_id
                )
            ).scalar_one_or_none()
            if current != "owner" or target is None or current_owner_id == new_owner_id:
                return False
            conn.execute(
                sa.update(self.members)
                .where(self.members.c.project_id == project_id, self.members.c.user_id == current_owner_id)
                .values(role="maintainer")
            )
            conn.execute(
                sa.update(self.members)
                .where(self.members.c.project_id == project_id, self.members.c.user_id == new_owner_id)
                .values(role="owner")
            )
            return True

    def remove_member(self, project_id: int, user_id: int) -> bool:
        if not self._project_is_active(project_id):
            return False
        with self.engine.begin() as conn:
            return (
                conn.execute(
                    sa.delete(self.members).where(
                        self.members.c.project_id == project_id,
                        self.members.c.user_id == user_id,
                        self.members.c.role != "owner",
                    )
                ).rowcount
                == 1
            )

    def invite(
        self,
        project_id: int,
        invited_user_id: int,
        invited_by: int,
        role: str = "viewer",
        *,
        expires_at: float | None = None,
    ) -> dict[str, Any]:
        if role not in PROJECT_ROLES or role == "owner":
            raise ValueError("invalid invitation role")
        if not self._project_is_active(project_id):
            raise ValueError("project does not exist")
        if self.get_membership(project_id, invited_user_id):
            raise ValueError("user is already a project member")
        now, expiry = time.time(), expires_at or time.time() + 7 * 86400
        if expiry <= now:
            raise ValueError("invitation expiry must be in the future")
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    sa.insert(self.invitations).values(
                        project_id=project_id,
                        invited_user_id=invited_user_id,
                        invited_by=invited_by,
                        proposed_role=role,
                        status="pending",
                        created_at=now,
                        expires_at=expiry,
                    )
                )
                invitation_id = result.inserted_primary_key[0]
        except IntegrityError as exc:
            raise ValueError("a pending invitation already exists") from exc
        return self.get_invitation(invitation_id)  # type: ignore[return-value]

    def get_invitation(self, invitation_id: int | str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            return self._row(
                conn.execute(sa.select(self.invitations).where(self.invitations.c.id == invitation_id)).first()
            )

    def _expire_pending_invitations(self, conn: Any, *criteria: Any) -> None:
        conn.execute(
            sa.update(self.invitations)
            .where(
                *criteria,
                self.invitations.c.status == "pending",
                self.invitations.c.expires_at <= time.time(),
            )
            .values(status="expired")
        )

    def list_invitations(self, user_id: int, *, status: str = "pending") -> list[dict[str, Any]]:
        if status not in INVITATION_STATUSES:
            raise ValueError("invalid invitation status")
        with self.engine.begin() as conn:
            self._expire_pending_invitations(conn, self.invitations.c.invited_user_id == user_id)
            return [
                dict(row._mapping)
                for row in conn.execute(
                    sa.select(self.invitations)
                    .where(self.invitations.c.invited_user_id == user_id, self.invitations.c.status == status)
                    .order_by(self.invitations.c.created_at.desc())
                )
            ]

    def list_project_invitations(
        self,
        project_id: int | str,
        *,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a Project's invitations after refreshing expired pending rows."""
        if status is not None and status not in INVITATION_STATUSES:
            raise ValueError("invalid invitation status")
        with self.engine.begin() as conn:
            self._expire_pending_invitations(conn, self.invitations.c.project_id == project_id)
            query = sa.select(self.invitations).where(self.invitations.c.project_id == project_id)
            if status is not None:
                query = query.where(self.invitations.c.status == status)
            return [
                dict(row._mapping)
                for row in conn.execute(
                    query.order_by(self.invitations.c.created_at.desc()),
                )
            ]

    def revoke_invitation(self, invitation_id: int | str) -> bool:
        with self.engine.begin() as conn:
            return (
                conn.execute(
                    sa.update(self.invitations)
                    .where(self.invitations.c.id == invitation_id, self.invitations.c.status == "pending")
                    .values(status="revoked")
                ).rowcount
                == 1
            )

    def respond_invitation(self, invitation_id: int | str, user_id: int, accepted: bool) -> bool:
        now = time.time()
        with self.engine.begin() as conn:
            invitation = conn.execute(
                sa.select(self.invitations).where(
                    self.invitations.c.id == invitation_id,
                    self.invitations.c.invited_user_id == user_id,
                    self.invitations.c.status == "pending",
                )
            ).first()
            if invitation is None:
                return False
            project = conn.execute(
                sa.select(self.projects.c.archived_at).where(self.projects.c.id == invitation.project_id)
            ).first()
            if project is None or project.archived_at is not None:
                return False
            if invitation.expires_at <= now:
                conn.execute(
                    sa.update(self.invitations).where(self.invitations.c.id == invitation_id).values(status="expired")
                )
                return False
            conn.execute(
                sa.update(self.invitations)
                .where(self.invitations.c.id == invitation_id)
                .values(status="accepted" if accepted else "declined", accepted_at=now if accepted else None)
            )
            if accepted:
                conn.execute(
                    sa.insert(self.members).values(
                        project_id=invitation.project_id, user_id=user_id, role=invitation.proposed_role, created_at=now
                    )
                )
            return True

    def can(self, project_id: int | str, user_id: int | None, capability: str, *, authenticated: bool = True) -> bool:
        project = self.get_project(project_id)
        if not project:
            return False
        membership = self.get_membership(project_id, user_id) if user_id is not None else None
        if membership:
            capabilities = ROLE_CAPABILITIES[membership["role"]]
            if project["archived_at"] is not None:
                capabilities = capabilities.intersection(ARCHIVED_MEMBER_CAPABILITIES)
            return capability in capabilities
        if capability not in READ_CAPABILITIES:
            return False
        return project["visibility"] == "public" or (project["visibility"] == "internal" and authenticated)

    def _project_is_active(self, project_id: int | str) -> bool:
        project = self.get_project(project_id)
        return bool(project and project["archived_at"] is None)

    def capabilities(
        self,
        project_id: int | str,
        user_id: int | None,
        *,
        authenticated: bool = True,
    ) -> list[str]:
        """Return the principal's effective Project capabilities."""
        project = self.get_project(project_id)
        if not project:
            return []
        membership = self.get_membership(project_id, user_id) if user_id is not None else None
        if membership:
            capabilities = ROLE_CAPABILITIES[membership["role"]]
            if project["archived_at"] is not None:
                capabilities = capabilities.intersection(ARCHIVED_MEMBER_CAPABILITIES)
            return sorted(capabilities)
        may_read = project["visibility"] == "public" or (project["visibility"] == "internal" and authenticated)
        return sorted(READ_CAPABILITIES) if may_read else []

    def can_view_project(self, project_id: int | str, user_id: int | None = None, **kwargs: Any) -> bool:
        return self.can(project_id, user_id, "view_project", **kwargs)

    def can_submit_task(self, project_id: int | str, user_id: int) -> bool:
        return self.can(project_id, user_id, "submit_tasks")

    def can_use_artifact(self, project_id: int | str, user_id: int) -> bool:
        return self.can(project_id, user_id, "use_artifacts")

    def can_manage_members(self, project_id: int | str, user_id: int) -> bool:
        return self.can(project_id, user_id, "manage_members")


ProjectDatabase = CollaborationDatabase
CollaborationStore = CollaborationDatabase
