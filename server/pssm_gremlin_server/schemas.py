# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Pydantic models for GREMLIN server request and response validation.

All inbound request payloads are validated through these models at the API
boundary.  Response models ensure sensitive fields (``password_hash``,
``api_key_hash``) are never leaked.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _check_email_format(email: str) -> str:
    """Validate basic email format — ``@`` with a dot in the domain."""
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Invalid email address")
    return email


def normalize_email(email: str) -> str:
    """Normalize an email address: lowercase, strip, remove ``+suffix``.

    ``user+tag@domain.com`` → ``user@domain.com`` — prevents one person
    from creating multiple accounts via plus-aliased addresses.
    """
    email = email.strip().lower()
    local, at, domain = email.partition("@")
    local = local.split("+")[0]
    return f"{local}{at}{domain}"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Login payload — ``username`` may be a username or email address."""

    login_id: str = Field(min_length=1, alias="username")
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    """Self-registration payload (requires ``ENABLE_REGISTER``)."""

    username: str = Field(min_length=3, max_length=64)
    email: str
    password: str = Field(min_length=8)
    affiliation: str | None = None
    terms_agreed: bool = False
    captcha_token: str
    captcha_answer: str

    @field_validator("email", mode="before")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return normalize_email(v)

    @model_validator(mode="after")
    def _validate(self) -> RegisterRequest:
        _check_email_format(self.email)
        if not self.terms_agreed:
            raise ValueError("You must agree to the Terms of Service")
        return self


class AdminCreateUserRequest(BaseModel):
    """Admin user-creation payload — pre-verified, immediately active."""

    username: str = Field(min_length=3, max_length=64)
    email: str
    password: str = Field(min_length=8)
    affiliation: str | None = None
    is_admin: bool = False
    role: str = "user"

    @field_validator("email", mode="before")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return normalize_email(v)

    @model_validator(mode="after")
    def _validate(self) -> AdminCreateUserRequest:
        _check_email_format(self.email)
        if self.role not in ("admin", "user", "guest"):
            raise ValueError("role must be 'admin', 'user', or 'guest'")
        return self


class AdminUpdateUserRequest(BaseModel):
    """Fields admin may update on a user.  All optional — only sent keys change."""

    email: str | None = None
    affiliation: str | None = None
    password: str | None = Field(default=None, min_length=8)
    registration_status: Literal["approved", "rejected"] | None = None
    user_status: Literal["active", "banned"] | None = None
    role: Literal["admin", "user", "guest"] | None = None

    @field_validator("email", mode="before")
    @classmethod
    def _norm_email(cls, v: str | None) -> str | None:
        return normalize_email(v) if v else None


class BatchUserRequest(BaseModel):
    """Batch enable / disable / delete payload."""

    action: Literal["enable", "disable", "delete"]
    user_ids: list[int] = Field(min_length=1)


class ForgotPasswordRequest(BaseModel):
    """Password-reset request — email is normalized but format is checked
    in the route so we never leak whether an address is registered."""

    email: str

    @field_validator("email", mode="before")
    @classmethod
    def _norm_email(cls, v: str) -> str:
        return normalize_email(v)


class ResetPasswordRequest(BaseModel):
    """New-password payload (after clicking reset link)."""

    token: str = Field(min_length=1)
    password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    """Password-change payload for authenticated users."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    """Safe user fields for API responses — never includes sensitive columns."""

    id: int
    username: str
    email: str
    email_verified: bool
    is_admin: bool
    role: str
    affiliation: str | None
    registration_status: str
    user_status: str
    created_at: float | None
    approved_by: int | None
    approved_at: float | None
    registration_ip: str | None = None
