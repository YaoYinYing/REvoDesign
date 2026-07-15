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
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from typing import Any

import sqlalchemy as sa
from flask import current_app, g, jsonify, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

# ---------------------------------------------------------------------------
# Resend email (optional extra — falls back to stdlib SMTP when not installed)
# ---------------------------------------------------------------------------

try:
    import resend as _resend_module

    _resend_key = os.environ.get("RESEND_API_KEY", "")
    if _resend_key:
        _resend_module.api_key = _resend_key
    _HAS_RESEND = True
except ImportError:
    _resend_module = None  # type: ignore[assignment]
    _resend_key = ""
    _HAS_RESEND = False

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
    sa.Column("affiliation", sa.String(256), nullable=True),
    sa.Column("terms_agreed", sa.Boolean, nullable=False, default=False),
    sa.Column("registration_status", sa.String(32), nullable=False, default="email_sent"),
    sa.Column("user_status", sa.String(32), nullable=False, default="pending"),
    sa.Column("approved_by", sa.Integer, nullable=True),
    sa.Column("approved_at", sa.Float, nullable=True),
    sa.Column("deleted", sa.Boolean, nullable=False, default=False),
    sa.Column("role", sa.String(32), nullable=False, default="user"),
    sa.Column("admin_notified", sa.Boolean, nullable=False, default=False),
    sa.Column("registration_ip", sa.String(45), nullable=True),
    sa.Column("registration_country", sa.String(8), nullable=True),
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
        for col, coltype in [
            ("api_key_hash", "TEXT"),
            ("affiliation", "TEXT"),
            ("terms_agreed", "INTEGER"),
            ("registration_status", "TEXT"),
            ("user_status", "TEXT"),
            ("approved_by", "INTEGER"),
            ("approved_at", "FLOAT"),
            ("deleted", "INTEGER"),
            ("verification_resend_count", "INTEGER"),
            ("verification_resend_at", "FLOAT"),
            ("role", "TEXT"),
            ("admin_notified", "INTEGER"),
            ("registration_ip", "TEXT"),
            ("registration_country", "TEXT"),
        ]:
            if col not in existing:
                conn.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {col} {coltype};")
        # Backfill: when adding admin_notified for the first time, mark all
        # existing non-admin users as notified so they don't appear in the
        # first digest.  Admins are always excluded from the digest.
        if "admin_notified" not in existing:
            conn.exec_driver_sql(
                "UPDATE users SET admin_notified = 1 WHERE is_admin = 0"
            )

    # -- write helpers -------------------------------------------------------

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        *,
        is_admin: bool = False,
        role: str = "user",
        affiliation: str | None = None,
        terms_agreed: bool = False,
        registration_status: str = "email_sent",
        user_status: str = "pending",
        registration_ip: str | None = None,
        registration_country: str | None = None,
    ) -> dict[str, Any]:
        """Insert a new user.  Returns the row as a dict."""
        now = time.time()
        stmt = sa.insert(_users_table).values(
            username=username,
            email=email.lower().strip(),
            password_hash=generate_password_hash(password),
            email_verified=False,
            is_admin=is_admin,
            role=role,
            created_at=now,
            affiliation=affiliation,
            terms_agreed=terms_agreed,
            registration_status=registration_status,
            registration_ip=registration_ip,
            registration_country=registration_country,
            user_status=user_status,
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
        ``email_verified``, ``is_admin``, ``api_key_hash``,
        ``affiliation``, ``terms_agreed``, ``registration_status``,
        ``user_status``, ``approved_by``, ``approved_at``.
        Password and API key values must be pre-hashed by the caller.
        """
        _allowed = {
            "username",
            "email",
            "password_hash",
            "email_verified",
            "is_admin",
            "api_key_hash",
            "affiliation",
            "terms_agreed",
            "registration_status",
            "user_status",
            "approved_by",
            "approved_at",
            "deleted",
            "verification_resend_count",
            "verification_resend_at",
            "role",
        }
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

    # ponytail: full table scan — paginate or index if users exceed ~10k
    def list_users(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        """Return all users ordered by ``created_at`` descending.

        Soft-deleted users are excluded by default.
        """
        stmt = sa.select(_users_table).order_by(sa.desc(_users_table.c.created_at))
        if not include_deleted:
            stmt = stmt.where(_users_table.c.deleted == False)  # noqa: E712
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    def user_count(self) -> int:
        stmt = sa.select(sa.func.count()).select_from(_users_table)
        with self.engine.connect() as conn:
            return conn.execute(stmt).scalar_one()

    def get_unnotified_registrations(self) -> list[dict[str, Any]]:
        """Return non-admin users who haven't been included in a digest yet."""
        stmt = (
            sa.select(_users_table)
            .where(
                _users_table.c.admin_notified == False,  # noqa: E712
                _users_table.c.is_admin == False,  # noqa: E712
            )
            .order_by(sa.asc(_users_table.c.created_at))
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    def mark_users_notified(self, user_ids: list[int]) -> None:
        """Mark a batch of users as included in an admin digest."""
        if not user_ids:
            return
        stmt = sa.update(_users_table).where(_users_table.c.id.in_(user_ids)).values(admin_notified=True)
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def unmark_users_notified(self, user_ids: list[int]) -> None:
        """Roll back the admin_notified flag so users appear in the next digest."""
        if not user_ids:
            return
        stmt = sa.update(_users_table).where(_users_table.c.id.in_(user_ids)).values(admin_notified=False)
        with self.engine.begin() as conn:
            conn.execute(stmt)


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


def _is_account_blocked(user: dict[str, Any]) -> str | None:
    """Return an error message if *user* is not allowed to authenticate, or ``None``.

    Backward-compatible: ``user_status`` of ``None`` (pre-migration users) is
    treated as ``"active"``.
    """
    if user.get("deleted"):
        return "Account has been deleted"
    if user.get("user_status") == "banned":
        return "Account has been suspended"
    # ponytail: pending users (self-registered, not yet admin-approved)
    # cannot authenticate.  NULL = pre-migration → grandfathered as active.
    status = user.get("user_status")
    if status is not None and status != "active":
        return "Account is not yet active"
    # All active users must have a verified email address.  Admin-created
    # and admin-approved users get verify_email() called automatically in
    # the admin routes.
    if user.get("email_verified") is False:
        return "Email not verified"
    return None


def load_current_user() -> dict[str, Any] | None:
    """Resolve the authenticated user from the current request.

    Tries (in order):
    1. ``Authorization: Bearer <token>`` — web session token (time-limited).
    2. ``auth_token`` cookie — browser page navigations (same time-limited token).
    3. ``X-API-Key: <key>`` — long-lived API key (never expires).

    Returns the user dict or ``None``.
    """
    db: UserDatabase = current_app.config["user_db"]

    # 1. Bearer token (Authorization header — full privileges, CSRF-safe)
    token = _extract_bearer_token()
    if token:
        user_id = validate_token(token)
        if user_id is not None:
            user = db.get_user(user_id)
            if user is not None and _is_account_blocked(user) is None:
                g.auth_method = "bearer"
                return user
    # 2. Cookie — browser page navigations after login (read-only; CSRF-prone)
    #    Guest accounts ARE permitted to use cookie-based web access.
    token = request.cookies.get("auth_token")
    if token:
        user_id = validate_token(token)
        if user_id is not None:
            user = db.get_user(user_id)
            if user is not None and _is_account_blocked(user) is None:
                g.auth_method = "cookie"
                return user

    # 3. API key (programmatic access — restricted privileges)
    #    Guest accounts are not permitted to use API keys.
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        user = db.validate_api_key(api_key)
        if user is not None and _is_account_blocked(user) is None and user.get("role") != "guest":
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


def require_bearer_auth():
    """Return a 403 error if the current request was authenticated via cookie.

    CSRF gate: cookie-authenticated requests can be triggered cross-origin
    by top-level navigations.  State-changing endpoints must present a Bearer
    token in the ``Authorization`` header, which the browser same-origin
    policy prevents cross-origin requests from setting.
    """
    if g.get("auth_method") == "cookie":
        return jsonify({"error": "Bearer token required for this action"}), 403
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
# Email delivery — Resend (optional pip extra) with SMTP fallback
# ---------------------------------------------------------------------------


def _smtp_config() -> dict[str, Any]:
    return {
        "host": _env_str("SMTP_HOST", "localhost"),
        "port": _env_int("SMTP_PORT", 587),
        "username": _env_str("SMTP_USERNAME", ""),
        "password": _env_str("SMTP_PASSWORD", ""),
        "use_tls": _env_bool("SMTP_USE_TLS", True),
        "from_addr": _env_str("SMTP_FROM_ADDR", "hello@revodesign.local"),
        "from_name": _env_str("SMTP_FROM_NAME", "REvoDesign GREMLIN Server"),
    }


def _use_resend() -> bool:
    """Return True if Resend is installed and configured."""
    return _HAS_RESEND and bool(_resend_key)


def _resend_from() -> str:
    name = _env_str("RESEND_FROM_NAME", "REvoDesign GREMLIN Server")
    addr = _env_str("RESEND_FROM_ADDR", "onboarding@resend.dev")
    return f"{name} <{addr}>"


def _send_email(*, to: str, subject: str, text: str, html: str | None = None) -> bool:
    """Send an email.  Uses Resend if available+configured, else SMTP.

    Returns ``True`` on success, ``False`` on failure (logged).
    """
    # Resend path (optional pip extra)
    if _use_resend():
        try:
            params: _resend_module.Emails.SendParams = {  # type: ignore[union-attr]
                "from": _resend_from(),
                "to": [to],
                "subject": subject,
                "text": text,
            }
            if html:
                params["html"] = html
            _resend_module.Emails.send(params)  # type: ignore[union-attr]
            return True
        except Exception:
            logging.exception("Resend failed for %s, trying SMTP fallback", to)

    # SMTP path (stdlib, always available)
    cfg = _smtp_config()
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{cfg['from_name']} <{cfg['from_addr']}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

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
        logging.exception("Failed to send email to %s", to)
        return False


# ---------------------------------------------------------------------------
# Shared HTML email wrapper — loaded from templates/email/base.html
# ---------------------------------------------------------------------------

_EMAIL_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "email", "base.html")
with open(_EMAIL_TEMPLATE_PATH, encoding="utf-8") as _f:
    _EMAIL_TEMPLATE = _f.read()


def _email_html(body_html: str) -> str:
    """Wrap *body_html* in the shared email layout."""
    # ponytail: str.replace, not .format() — body_html may contain curly braces
    # from f-string interpolation (e.g. CSS colours like #ffffff).
    return _EMAIL_TEMPLATE.replace("{body}", body_html)


# ---------------------------------------------------------------------------
# CAPTCHA — simple math challenge, signed token (5-min expiry)
# ---------------------------------------------------------------------------


def generate_captcha() -> tuple[str, str]:
    """Return ``(question, token)`` for a math CAPTCHA challenge."""
    import secrets

    a = secrets.randbelow(10)
    b = secrets.randbelow(9) + 1  # avoid zero — makes the answer less trivial
    answer = a + b
    question = f"What is {a} + {b}?"
    token: str = _serializer.dumps({"answer": answer, "purpose": "captcha"})  # type: ignore[assignment]
    return question, token


def validate_captcha(token: str, answer: str) -> bool:
    """Validate a CAPTCHA token and answer.  Tokens expire after 5 minutes."""
    try:
        payload = _serializer.loads(token, max_age=300)
    except (SignatureExpired, BadSignature):
        return False
    if payload.get("purpose") != "captcha":
        return False
    try:
        return int(payload.get("answer", -1)) == int(answer.strip())
    except (TypeError, ValueError):
        return False


def _public_base_url() -> str:
    """Return the public-facing base URL for email links.

    Uses the current request's ``Host`` header so email links point to the
    same domain the user is accessing.  Falls back to ``SERVER_BASE_URL``
    env var, then ``http://localhost:8080`` (dev).
    """
    # ponytail: request.host_url already has scheme+host from the Host header
    try:
        return request.host_url.rstrip("/")
    except RuntimeError:
        pass  # outside request context (tests, scripts)
    return _env_str("SERVER_BASE_URL", "http://localhost:8080").rstrip("/")


def send_verification_email(user: dict[str, Any]) -> bool:
    """Send an email-verification message to *user*.

    Returns ``True`` on success, ``False`` on failure (logged).
    """
    token = _serializer.dumps({"uid": user["id"], "purpose": "verify-email"})
    base_url = _public_base_url()
    verify_url = f"{base_url}/PSSM_GREMLIN/user_verify?c={token}"

    text = (
        f"Hello {user['username']},\n"
        f"\n"
        f"Welcome to REvoDesign GREMLIN. Please confirm your email address to\n"
        f"activate your account.\n"
        f"\n"
        f"  {verify_url}\n"
        f"\n"
        f"This link expires in 2 days.\n"
        f"\n"
        f"If you did not create this account, you can ignore this message.\n"
        f"\n"
        f"— REvoDesign GREMLIN Server\n"
    )
    html_body = (
        f'<p>Hello {user["username"]},</p>'
        f"<p>Welcome to REvoDesign GREMLIN. Please confirm your email address "
        f"to activate your account.</p>"
        f'<p style="margin:24px 0;">'
        f'<a href="{verify_url}" style="display:inline-block;padding:12px 24px;'
        f"background-color:#1a1a2e;color:#ffffff;text-decoration:none;"
        f"border-radius:6px;font-weight:600;\">"
        f"Verify Email Address</a></p>"
        f"<p>Or copy this link:</p>"
        f'<p style="color:#6b7280;font-size:13px;word-break:break-all;">'
        f"{verify_url}</p>"
        f'<p style="color:#9ca3af;font-size:13px;">This link expires in 2 days.</p>'
        f"<p>If you did not create this account, you can ignore this message.</p>"
    )
    return _send_email(
        to=user["email"],
        subject="Verify your email — REvoDesign GREMLIN",
        text=text,
        html=_email_html(html_body),
    )


def validate_email_token(token: str) -> int | None:
    """Validate an email-verification token.  Returns *user_id* or ``None``."""
    try:
        payload = _serializer.loads(token, max_age=172800)  # 2-day expiry
    except (SignatureExpired, BadSignature):
        return None
    if payload.get("purpose") != "verify-email":
        return None
    return payload.get("uid")


# ---------------------------------------------------------------------------
# Password reset (same serializer, 1-hour expiry)
# ---------------------------------------------------------------------------


def send_password_reset_email(email: str, db: UserDatabase) -> bool:
    """Send a password-reset link to *email* if a user with that address exists.

    Returns ``True`` if an email was sent, ``False`` otherwise (no user, or
    delivery failure).  Does not reveal whether the email is registered.
    """
    user = db.get_user_by_email(email)
    if user is None:
        # Don't leak whether the email is registered — pretend success
        return True

    token = _serializer.dumps({"uid": user["id"], "purpose": "reset-password"})
    base_url = _public_base_url()
    reset_url = f"{base_url}/PSSM_GREMLIN/reset_password?c={token}"

    text = (
        f"Hello {user['username']},\n"
        f"\n"
        f"A password reset was requested for your account. Click the link\n"
        f"below to set a new password.\n"
        f"\n"
        f"  {reset_url}\n"
        f"\n"
        f"This link expires in 1 hour.\n"
        f"\n"
        f"If you did not request this, you can ignore this message — your\n"
        f"password will not change.\n"
        f"\n"
        f"— REvoDesign GREMLIN Server\n"
    )
    html_body = (
        f'<p>Hello {user["username"]},</p>'
        f"<p>A password reset was requested for your account. "
        f"Click the button below to set a new password.</p>"
        f'<p style="margin:24px 0;">'
        f'<a href="{reset_url}" style="display:inline-block;padding:12px 24px;'
        f"background-color:#1a1a2e;color:#ffffff;text-decoration:none;"
        f"border-radius:6px;font-weight:600;\">"
        f"Reset Password</a></p>"
        f"<p>Or copy this link:</p>"
        f'<p style="color:#6b7280;font-size:13px;word-break:break-all;">'
        f"{reset_url}</p>"
        f'<p style="color:#9ca3af;font-size:13px;">This link expires in 1 hour.</p>'
        f"<p>If you did not request this, you can ignore this message "
        f"&mdash; your password will not change.</p>"
    )
    return _send_email(
        to=email,
        subject="Reset your password — REvoDesign GREMLIN",
        text=text,
        html=_email_html(html_body),
    )


def send_approval_email(user: dict[str, Any]) -> bool:
    """Notify *user* that their registration has been approved."""
    base_url = _public_base_url()

    text = (
        f"Hello {user['username']},\n"
        f"\n"
        f"Your REvoDesign GREMLIN registration has been approved.\n"
        f"\n"
        f"  {base_url}/PSSM_GREMLIN/login\n"
        f"\n"
        f"— REvoDesign GREMLIN Server\n"
    )
    html_body = (
        f'<p>Hello {user["username"]},</p>'
        f"<p>Your REvoDesign GREMLIN registration has been approved.</p>"
        f'<p style="margin:24px 0;">'
        f'<a href="{base_url}/PSSM_GREMLIN/login" style="display:inline-block;'
        f"padding:12px 24px;background-color:#1a1a2e;color:#ffffff;"
        f"text-decoration:none;border-radius:6px;font-weight:600;\">"
        f"Log In</a></p>"
    )
    return _send_email(
        to=user["email"],
        subject="Registration approved — REvoDesign GREMLIN",
        text=text,
        html=_email_html(html_body),
    )


def send_rejection_email(user: dict[str, Any]) -> bool:
    """Notify *user* that their registration has been declined."""
    text = (
        f"Hello {user['username']},\n"
        f"\n"
        f"Your REvoDesign GREMLIN registration has been declined.\n"
        f"If you believe this is an error, please contact the\n"
        f"administrator who manages this server.\n"
        f"\n"
        f"— REvoDesign GREMLIN Server\n"
    )
    html_body = (
        f'<p>Hello {user["username"]},</p>'
        f"<p>Your REvoDesign GREMLIN registration has been declined.</p>"
        f"<p>If you believe this is an error, please contact the "
        f"administrator who manages this server.</p>"
    )
    return _send_email(
        to=user["email"],
        subject="Registration update — REvoDesign GREMLIN",
        text=text,
        html=_email_html(html_body),
    )


def _admin_notify_emails() -> list[str]:
    """Return the list of admin email addresses to notify on registration."""
    raw = _env_str("ADMIN_NOTIFY_EMAIL", "")
    if not raw:
        return []
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def send_admin_digest() -> bool:
    """Send a digest email to admins listing all unnotified registrations.

    Reads ``ADMIN_NOTIFY_EMAIL`` (comma-separated).  Returns True if a
    digest was sent.
    """
    recipients = _admin_notify_emails()
    if not recipients:
        return False
    db = UserDatabase()
    new_users = db.get_unnotified_registrations()
    if not new_users:
        return False

    # Mark first, send second — prevents duplicate digests when multiple
    # gunicorn workers or celery processes race.  Unmark on failure so the
    # users appear in the next digest.
    user_ids = [u["id"] for u in new_users]
    db.mark_users_notified(user_ids)

    base_url = _env_str("SERVER_BASE_URL", "http://localhost:8080").rstrip("/")
    rows = []
    for u in new_users:
        created = datetime.fromtimestamp(u["created_at"]).strftime("%Y-%m-%d %H:%M") if u.get("created_at") else "?"
        rows.append(f"  {u['username']:<20} {u['email']:<32} {u.get('affiliation', '-') or '-':<24} {created}")

    text = (
        f"{len(new_users)} new registration(s) pending approval:\n\n"
        f"  {'Username':<20} {'Email':<32} {'Affiliation':<24} {'Registered'}\n"
        f"  {'-' * 20:<20} {'-' * 32:<32} {'-' * 24:<24} {'-' * 16}\n"
        + "\n".join(rows)
        + f"\n\n  Review: {base_url}/PSSM_GREMLIN/user_control\n\n"
        f"— REvoDesign GREMLIN Server\n"
    )
    # Build HTML table rows
    html_rows = []
    for u in new_users:
        created = datetime.fromtimestamp(u["created_at"]).strftime("%Y-%m-%d %H:%M") if u.get("created_at") else "?"
        affil = u.get("affiliation") or "-"
        html_rows.append(
            f"<tr>"
            f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{u["username"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{u["email"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{affil}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{created}</td>'
            f"</tr>"
        )
    html_body = (
        f"<p>{len(new_users)} new registration(s) pending approval:</p>"
        f'<table style="width:100%;border-collapse:collapse;margin:16px 0;'
        f'font-size:14px;" cellpadding="0" cellspacing="0">'
        f'<thead><tr style="background-color:#f3f4f6;text-align:left;">'
        f'<th style="padding:8px 12px;">Username</th>'
        f'<th style="padding:8px 12px;">Email</th>'
        f'<th style="padding:8px 12px;">Affiliation</th>'
        f'<th style="padding:8px 12px;">Registered</th>'
        f"</tr></thead><tbody>"
        + "".join(html_rows)
        + "</tbody></table>"
        f'<p style="margin:24px 0;">'
        f'<a href="{base_url}/PSSM_GREMLIN/user_control" style="display:inline-block;'
        f"padding:12px 24px;background-color:#1a1a2e;color:#ffffff;"
        f"text-decoration:none;border-radius:6px;font-weight:600;\">"
        f"Review Registrations</a></p>"
    )
    try:
        for email in recipients:
            _send_email(
                to=email,
                subject=f"{len(new_users)} new registration(s) — REvoDesign GREMLIN",
                text=text,
                html=_email_html(html_body),
            )
    except Exception:
        db.unmark_users_notified(user_ids)
        raise
    return True


def validate_reset_token(token: str) -> int | None:
    """Validate a password-reset token.  Returns *user_id* or ``None``."""
    try:
        payload = _serializer.loads(token, max_age=3600)  # 1-hour expiry
    except (SignatureExpired, BadSignature):
        return None
    if payload.get("purpose") != "reset-password":
        return None
    return payload.get("uid")
