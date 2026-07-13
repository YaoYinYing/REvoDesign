# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Token-based authentication and user management for the GREMLIN server.

Replaces the static ``users.txt`` HTTP Basic Auth model with a SQLite-backed
user store, Bearer-token authentication, and an optional registration workflow
gated by ``ENABLE_REGISTER``.
"""

from __future__ import annotations

import logging
import os
import smtplib
import time
from collections.abc import Callable
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from typing import Any

import sqlalchemy as sa
from flask import current_app, g, jsonify, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _env_bool(var: str, default: bool) -> bool:
    raw = os.environ.get(var)
    if raw is None or raw == "":
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {var} must be a boolean value " "(one of: true/false/1/0/yes/no/on/off).")


def _env_str(var: str, default: str) -> str:
    # ponytail: treat empty string as unset — docker compose passes
    # ${VAR:-} which yields "" when VAR is absent in the env file.
    value = os.environ.get(var)
    return value if value else default


def _env_int(var: str, default: int) -> int:
    raw = os.environ.get(var, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {var} must be an integer, got {raw!r}") from exc


# ---------------------------------------------------------------------------
# User database
# ---------------------------------------------------------------------------

_metadata = sa.MetaData()

_users_table = sa.Table(
    "users",
    _metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("username", sa.String(128), nullable=False, unique=True, index=True),
    sa.Column("email", sa.String(256), nullable=False, unique=True),
    sa.Column("password_hash", sa.String(256), nullable=False),
    sa.Column("email_verified", sa.Boolean, nullable=False, default=False),
    sa.Column("is_admin", sa.Boolean, nullable=False, default=False),
    sa.Column("created_at", sa.Float, nullable=False),
    sa.Column("api_key_hash", sa.String(256), nullable=True),
)


def _get_user_db_path() -> str:
    """Resolve the user database path.

    Uses ``USER_DB_PATH`` env var, falling back to ``{SERVER_DIR}/users.sqlite3``.
    """
    from_server_dir = os.environ.get("SERVER_DIR", "")
    default = (
        os.path.join(from_server_dir, "users.sqlite3")
        if from_server_dir
        else os.path.join(os.getcwd(), "users.sqlite3")
    )
    return _env_str("USER_DB_PATH", default)


class UserDatabase:
    """SQLite-backed store for user accounts."""

    def __init__(self, path: str | None = None):
        self.path = os.path.abspath(path or _get_user_db_path())
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self.engine = sa.create_engine(
            f"sqlite:///{self.path}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
            _metadata.create_all(conn, checkfirst=True)
            self._ensure_columns(conn)

    @staticmethod
    def _ensure_columns(conn) -> None:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users);").fetchall()}
        if "api_key_hash" not in existing:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN api_key_hash TEXT;")

    # -- write helpers -------------------------------------------------------

    def create_user(self, username: str, email: str, password: str, *, is_admin: bool = False) -> dict[str, Any]:
        """Insert a new user.  Returns the row as a dict."""
        now = time.time()
        stmt = sa.insert(_users_table).values(
            username=username,
            email=email.lower().strip(),
            password_hash=generate_password_hash(password),
            email_verified=False,
            is_admin=is_admin,
            created_at=now,
        )
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
            row_id = result.inserted_primary_key[0]
        return self.get_user(row_id)  # type: ignore[return-value]

    def verify_email(self, user_id: int) -> None:
        stmt = sa.update(_users_table).where(_users_table.c.id == user_id).values(email_verified=True)
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def update_user(self, user_id: int, **fields: Any) -> None:
        """Update allowed user fields in-place.

        Allowed keys: ``username``, ``email``, ``password_hash``,
        ``email_verified``, ``is_admin``, ``api_key_hash``.
        Password and API key values must be pre-hashed by the caller.
        """
        _allowed = {"username", "email", "password_hash", "email_verified", "is_admin", "api_key_hash"}
        values = {k: v for k, v in fields.items() if k in _allowed}
        if not values:
            return
        stmt = sa.update(_users_table).where(_users_table.c.id == user_id).values(**values)
        with self.engine.begin() as conn:
            conn.execute(stmt)

    # -- API key helpers -----------------------------------------------------

    def generate_api_key(self, user_id: int) -> str:
        """Generate a new API key for *user_id*.

        Returns the *plaintext* key — store only its hash.  The caller is
        responsible for showing the plaintext once.
        """
        raw = "revodesign_" + os.urandom(32).hex()
        self.update_user(user_id, api_key_hash=generate_password_hash(raw))
        return raw

    def revoke_api_key(self, user_id: int) -> None:
        """Remove the API key for *user_id*."""
        self.update_user(user_id, api_key_hash=None)

    def validate_api_key(self, key: str) -> dict[str, Any] | None:
        """Return the user dict if *key* matches a stored API key, or ``None``."""
        if not key or not key.startswith("revodesign_"):
            return None
        users = sa.select(_users_table).where(_users_table.c.api_key_hash.isnot(None))
        with self.engine.connect() as conn:
            for row in conn.execute(users).mappings():
                if check_password_hash(row["api_key_hash"], key):
                    return dict(row)
        return None

    # -- read helpers --------------------------------------------------------

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        stmt = sa.select(_users_table).where(_users_table.c.id == user_id)
        with self.engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        stmt = sa.select(_users_table).where(_users_table.c.username == username.strip())
        with self.engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        stmt = sa.select(_users_table).where(_users_table.c.email == email.lower().strip())
        with self.engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return dict(row) if row else None

    def user_count(self) -> int:
        stmt = sa.select(sa.func.count()).select_from(_users_table)
        with self.engine.connect() as conn:
            return conn.execute(stmt).scalar_one()


# ---------------------------------------------------------------------------
# Token serialiser
# ---------------------------------------------------------------------------

_SECRET_KEY = _env_str(
    "AUTH_SECRET_KEY",
    os.environ.get("SECRET_KEY", os.urandom(32).hex()),
)

_TOKEN_MAX_AGE = _env_int("AUTH_TOKEN_MAX_AGE", 7 * 24 * 3600)  # 7 days

_serializer = URLSafeTimedSerializer(_SECRET_KEY, salt="revodesign-auth")


def generate_token(user_id: int) -> str:
    """Return a signed, time-limited bearer token for *user_id*."""
    return _serializer.dumps({"uid": user_id})  # type: ignore[return-value]


def validate_token(token: str) -> int | None:
    """Return *user_id* if *token* is valid, or ``None``."""
    try:
        payload = _serializer.loads(token, max_age=_TOKEN_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None
    return payload.get("uid")


# ---------------------------------------------------------------------------
# Request-scoped current user
# ---------------------------------------------------------------------------


def _extract_bearer_token() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    return auth_header[7:].strip()


def load_current_user() -> dict[str, Any] | None:
    """Resolve the authenticated user from the current request.

    Tries (in order):
    1. ``Authorization: Bearer <token>`` — web session token (time-limited).
    2. ``auth_token`` cookie — browser page navigations (same time-limited token).
    3. ``X-API-Key: <key>`` — long-lived API key (never expires).

    Returns the user dict or ``None``.
    """
    db: UserDatabase = current_app.config["user_db"]

    # 1. Bearer token (web login — full privileges)
    token = _extract_bearer_token()
    # 2. Cookie — browser page navigations after login
    if not token:
        token = request.cookies.get("auth_token")
    if token:
        user_id = validate_token(token)
        if user_id is not None:
            user = db.get_user(user_id)
            if user is not None:
                g.auth_method = "token"
                return user

    # 3. API key (programmatic access — restricted privileges)
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        user = db.validate_api_key(api_key)
        if user is not None:
            g.auth_method = "api_key"
            return user

    return None


def require_web_login():
    """Return a 403 error if the current request was authenticated via API key.

    Call inside route handlers that need full web-login privileges
    (profile changes, admin actions, API key management).
    """
    if g.get("auth_method") == "api_key":
        return jsonify({"error": "API keys cannot perform this action — use web login"}), 403
    return None


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def login_required(f: Callable) -> Callable:
    """Decorator that requires a valid Bearer token.

    Browser requests (``Accept: text/html``) are redirected to the login
    page.  API requests receive a JSON error so JavaScript can handle it.
    """

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        user = load_current_user()
        if user is None:
            if "text/html" in request.headers.get("Accept", ""):
                return redirect(url_for("login_page"))
            return (
                jsonify(
                    {
                        "error": "Authentication required",
                        "message": "Provide a valid Bearer token via the Authorization header",
                    }
                ),
                401,
            )
        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def optional_user(f: Callable) -> Callable:
    """Decorator that resolves the current user if a token is present, but does not require one."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        user = load_current_user()
        g.current_user = user  # may be None
        return f(*args, **kwargs)

    return decorated


# ---------------------------------------------------------------------------
# Email verification (stdlib smtplib — no new dependency)
# ---------------------------------------------------------------------------


def _smtp_config() -> dict[str, Any]:
    return {
        "host": _env_str("SMTP_HOST", "localhost"),
        "port": _env_int("SMTP_PORT", 587),
        "username": _env_str("SMTP_USERNAME", ""),
        "password": _env_str("SMTP_PASSWORD", ""),
        "use_tls": _env_bool("SMTP_USE_TLS", True),
        "from_addr": _env_str("SMTP_FROM_ADDR", "noreply@revodesign.local"),
        "from_name": _env_str("SMTP_FROM_NAME", "REvoDesign GREMLIN Server"),
    }


def send_verification_email(user: dict[str, Any]) -> bool:
    """Send an email-verification message to *user*.

    Returns ``True`` on success, ``False`` on failure (logged).
    """
    cfg = _smtp_config()
    token = _serializer.dumps({"uid": user["id"], "purpose": "verify-email"})
    verify_url = _env_str("SERVER_BASE_URL", "http://localhost:8080").rstrip("/")
    verify_url = f"{verify_url}/PSSM_GREMLIN/api/auth/verify-email?token={token}"

    subject = "Verify your REvoDesign GREMLIN account"
    body = (
        f"Hello {user['username']},\n\n"
        f"Please verify your email address by clicking the link below.\n\n"
        f"{verify_url}\n\n"
        f"This link will expire in 1 hour.\n\n"
        f"If you did not create this account, please ignore this message.\n\n"
        f"— REvoDesign GREMLIN Server\n"
    )

    msg = MIMEMultipart()
    msg["From"] = f"{cfg['from_name']} <{cfg['from_addr']}>"
    msg["To"] = user["email"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        if cfg["use_tls"]:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
            server.starttls()
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=15)
        if cfg["username"] and cfg["password"]:
            server.login(cfg["username"], cfg["password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception:
        logging.exception("Failed to send verification email to %s", user["email"])
        return False


def validate_email_token(token: str) -> int | None:
    """Validate an email-verification token.  Returns *user_id* or ``None``."""
    try:
        payload = _serializer.loads(token, max_age=3600)  # 1-hour expiry
    except (SignatureExpired, BadSignature):
        return None
    if payload.get("purpose") != "verify-email":
        return None
    return payload.get("uid")
