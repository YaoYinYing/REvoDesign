# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Pydantic models for REvoCompute server request and response validation.

All inbound request payloads are validated through these models at the API
boundary.  Response models ensure sensitive fields (``password_hash``,
``api_key_hash``) are never leaked.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

AcademicPosition = Literal[
    "undergraduate_student",
    "masters_student",
    "phd_student",
    "postdoctoral_researcher",
    "research_assistant",
    "lecturer",
    "assistant_professor",
    "associate_professor",
    "professor",
    "industry_researcher",
    "other",
]
_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")

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
    if not isinstance(email, str):
        raise ValueError("email must be a string")
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
    full_name: str = Field(min_length=1, max_length=128)
    affiliation: str = Field(min_length=1, max_length=256)
    position: AcademicPosition
    pi_name: str = Field(min_length=1, max_length=128)
    terms_agreed: bool = False
    captcha_token: str
    captcha_answer: str

    @field_validator("username")
    @classmethod
    def _sanitize_username(cls, v: str) -> str:
        v = v.strip()
        if not _USERNAME_PATTERN.fullmatch(v):
            raise ValueError("username must use 3-64 letters, digits, dots, underscores, or hyphens")
        return v

    @field_validator("full_name", "affiliation", "pi_name", mode="before")
    @classmethod
    def _strip_required_profile_field(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("field must not be blank")
        return v.strip()

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
    full_name: str | None = Field(default=None, max_length=128)
    affiliation: str | None = None
    position: AcademicPosition | None = None
    pi_name: str | None = Field(default=None, max_length=128)
    role: str = "user"

    @field_validator("username")
    @classmethod
    def _sanitize_username(cls, v: str) -> str:
        v = v.strip()
        if not _USERNAME_PATTERN.fullmatch(v):
            raise ValueError("username must use 3-64 letters, digits, dots, underscores, or hyphens")
        return v

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
    full_name: str | None = Field(default=None, max_length=128)
    affiliation: str | None = None
    position: AcademicPosition | None = None
    pi_name: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, min_length=8)
    registration_status: Literal["approved", "rejected"] | None = None
    user_status: Literal["active", "banned"] | None = None
    role: Literal["admin", "user", "guest"] | None = None
    allow_gpu_use: bool | None = None

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


class TaskSubmissionRequest(BaseModel):
    """Task submission form payload — validated at the API boundary.

    The file itself is validated via Flask's request.files (not pydantic).
    This model validates the accompanying form fields.
    """

    task_type: str = Field(default="gremlin")
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_type", mode="before")
    @classmethod
    def _normalize_type(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("task_type must not be blank")
        return v.strip().lower()

    @model_validator(mode="after")
    def _validate_against_registry(self) -> TaskSubmissionRequest:
        from revocompute.task_types import get as _get_type

        try:
            tt, runner = _get_type(self.task_type)
        except KeyError:
            raise ValueError(f"Unknown task type: {self.task_type!r}") from None

        # Validate submitted params against the task type's param definitions
        known_params = {p.name: p for p in tt.params}
        for key in self.params:
            if key not in known_params:
                raise ValueError(f"Unknown parameter {key!r} for task type {self.task_type!r}")

        for name, param in known_params.items():
            if name in self.params:
                raw = self.params[name]
            elif name in runner.defaults:
                raw = runner.defaults[name]
            elif param.default is not None:
                raw = param.default
            elif param.required:
                raise ValueError(f"Parameter {name!r} is required for task type {self.task_type!r}")
            else:
                continue
            _coerce_param_value(param, raw)

        return self

    def coerce_params(self) -> dict[str, Any]:
        """Return params with values coerced to their declared types."""
        from revocompute.task_types import get as _get_type

        tt, runner = _get_type(self.task_type)
        known_params = {p.name: p for p in tt.params}
        coerced: dict[str, Any] = {}
        for key, param in known_params.items():
            if key in self.params:
                raw = self.params[key]
            elif key in runner.defaults:
                raw = runner.defaults[key]
            elif param.default is not None:
                raw = param.default
            else:
                continue
            coerced[key] = _coerce_param_value(param, raw)
        return coerced


def _coerce_param_value(param: Any, raw: Any) -> Any:
    """Coerce and constrain one task parameter from any submission source."""
    if param.type in ("int", "float"):
        try:
            value = int(raw) if param.type == "int" else float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"Parameter {param.name!r} must be a valid {param.type}") from None
        if param.minimum is not None and value < param.minimum:
            raise ValueError(f"Parameter {param.name!r} must be at least {param.minimum}")
        if param.maximum is not None and value > param.maximum:
            raise ValueError(f"Parameter {param.name!r} must be at most {param.maximum}")
    elif param.type == "bool":
        if isinstance(raw, bool):
            value = raw
        else:
            normalized = str(raw).strip().lower()
            if normalized not in {"true", "1", "yes", "false", "0", "no"}:
                raise ValueError(f"Parameter {param.name!r} must be a valid bool")
            value = normalized in {"true", "1", "yes"}
    else:
        value = str(raw)
    if param.choices and value not in param.choices:
        raise ValueError(f"Parameter {param.name!r} must be one of {list(param.choices)!r}")
    return value


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    """Safe user fields for API responses — never includes sensitive columns."""

    id: int
    username: str
    email: str
    email_verified: bool
    role: str
    full_name: str | None = None
    affiliation: str | None
    position: str | None = None
    pi_name: str | None = None
    registration_status: str
    user_status: str
    created_at: float | None
    approved_by: int | None
    approved_at: float | None
    registration_ip: str | None = None
    registration_country: str | None = None
