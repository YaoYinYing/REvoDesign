# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""HTTP route handlers for the REvoCompute server.

All ``@app.route`` decorators live here.  The module is imported by
``revocompute.__init__`` *after* ``revocompute.app`` has
created the Flask ``app``, so the decorators register against an
already-initialised application.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from celery.result import AsyncResult
from flask import (
    Response,
    abort,
    current_app,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from pydantic import ValidationError
from revocompute.app import (
    _ITERATED_STATIC_JS,
    CONFIG,
    ENABLE_REGISTER,
    TEMPLATE_IMAGE_DIR,
    _client_country,
    _client_ip,
    _current_username,
    _delete_task_artifacts,
    _deleted_status_from_task,
    _is_admin_user,
    _is_binary_file,
    _is_deleted_status,
    _request_metadata,
    _revoke_celery_task,
    _task_access_allowed,
    _task_access_denied,
    _task_artifact_access_allowed,
    _task_full_results_allowed,
    _task_id_for_upload,
    _task_mutation_allowed,
    _task_zip_download_name,
    app,
)
from revocompute.auth import (
    _DUMMY_PASSWORD_HASH,
    UserDatabase,
    _env_str,
    _is_account_blocked,
    generate_captcha,
    generate_token,
    load_current_user,
    login_required,
    optional_user,
    require_bearer_auth,
    require_web_login,
    send_approval_email,
    send_password_reset_email,
    send_rejection_email,
    send_verification_email,
    validate_captcha,
    validate_email_token,
    validate_reset_token,
)
from revocompute.input_validators import validate_input_file
from revocompute.ratelimit import rate_limit
from revocompute.resource_policy import GLOBAL_RESOURCE_KEYS, ResourceValidationError, normalize_resource_value
from revocompute.result_storyboard import ResultContractError, expected_file_tree, runner_root, storyboard_declaration
from revocompute.schemas import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    BatchUserRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TaskSubmissionRequest,
    UserResponse,
)
from revocompute.task_runtime import (
    _build_running_trace,
    _cleanup_task_workspace,
    _finalize_failed_results,
    _get_task_type,
    _local_user_identity,
    _normalize_task_id,
    _path_is_within,
    _safe_join,
    _sanitize_task_error,
    _task_zip_path,
    _virtual_upload_path,
    build_results_archive,
    cancel_compute_resources,
    format_times,
    format_walltime,
    run_compute_task,
    task_store,
)
from revocompute.task_types import get as get_task_type
from revocompute.task_types import iter_capabilities, list_categories, list_types
from revocompute.workspace_contracts import (
    WorkspaceValidationError,
    normalize_capability,
    validate_rfdiffusion_structure,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.route("/compute/projects", methods=["GET"])
@login_required
def projects_page():
    return render_template("projects.html")


@app.route("/compute/projects/<project_id>", methods=["GET"])
@optional_user
def project_page(project_id: str):
    if not _project_access(project_id, "view_project"):
        abort(404)
    return render_template("project.html", project_id=project_id)


def _authentication_required():
    return jsonify({"error": "Authentication required"}), 401


def _project_access(project_id: str, capability: str):
    store = current_app.config["collaboration"]
    user = g.get("current_user")
    authenticated = user is not None
    project = store.get_project(project_id)
    if not project or not store.can(
        project_id, int(user["id"]) if user else None, capability, authenticated=authenticated
    ):
        return None
    return project


@app.route("/compute/api/projects", methods=["GET", "POST"])
@optional_user
def projects_api():
    store = current_app.config["collaboration"]
    if request.method == "GET":
        user = g.get("current_user")
        uid = int(user["id"]) if user else None
        projects = store.list_projects(uid, authenticated=user is not None)
        capability = request.args.get("capability")
        if capability:
            projects = [project for project in projects if user and store.can(project["id"], uid, capability)]
        all_tasks = task_store.list_tasks()
        projects = [
            {
                **project,
                "membership_role": (
                    membership["role"] if user and (membership := store.get_membership(project["id"], uid)) else None
                ),
                "member_count": len(store.list_members(project["id"])),
                "task_count": sum(
                    task.get("scope_type") == "project" and str(task.get("scope_id")) == str(project["id"])
                    for task in all_tasks
                ),
            }
            for project in projects
        ]
        return jsonify({"projects": projects})
    if not g.get("current_user"):
        return _authentication_required()
    if blocked := require_bearer_auth():
        return blocked
    payload = request.get_json(silent=True) or {}
    try:
        project = store.create_project(
            int(g.current_user["id"]),
            str(payload.get("name", "")),
            description=str(payload.get("description", "")),
            visibility=str(payload.get("visibility", "private")),
        )
    except (IntegrityError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(project), 201


@app.route("/compute/api/projects/<project_id>", methods=["GET", "PATCH", "DELETE"])
@optional_user
def project_api(project_id: str):
    store = current_app.config["collaboration"]
    if request.method == "GET":
        project = _project_access(project_id, "view_project")
        if not project:
            return jsonify({"error": "Project not found"}), 404
        user = g.get("current_user")
        membership = store.get_membership(project_id, int(user["id"])) if user else None
        task_count = sum(
            task.get("scope_type") == "project" and str(task.get("scope_id")) == str(project_id)
            for task in task_store.list_tasks()
        )
        return jsonify(
            {
                **project,
                "membership_role": membership.get("role") if membership else None,
                "member_count": len(store.list_members(project_id)),
                "task_count": task_count,
                "capabilities": store.capabilities(
                    project_id, int(user["id"]) if user else None, authenticated=user is not None
                ),
            }
        )
    if not g.get("current_user"):
        return _authentication_required()
    if blocked := require_bearer_auth():
        return blocked
    capability = "delete_project" if request.method == "DELETE" else "change_project_settings"
    if not _project_access(project_id, capability):
        return jsonify({"error": "Project not found"}), 404
    if request.method == "DELETE":
        return (
            (jsonify({"status": "archived"}), 200)
            if store.archive_project(project_id)
            else (jsonify({"error": "Project not found"}), 404)
        )
    payload = request.get_json(silent=True) or {}
    try:
        store.update_project(project_id, **payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(store.get_project(project_id))


@app.route("/compute/api/projects/<project_id>/members", methods=["GET"])
@login_required
def project_members_api(project_id: str):
    store = current_app.config["collaboration"]
    if not store.get_membership(project_id, int(g.current_user["id"])):
        return jsonify({"error": "Project not found"}), 404
    users = current_app.config["user_db"]
    payload = []
    for member in store.list_members(project_id):
        user = users.get_user(member["user_id"])
        payload.append({**member, "username": user.get("username") if user else "Deleted user"})
    return jsonify({"members": payload})


@app.route("/compute/api/projects/<project_id>/members/<int:user_id>", methods=["PATCH", "DELETE"])
@login_required
def project_member_api(project_id: str, user_id: int):
    if blocked := require_bearer_auth():
        return blocked
    store = current_app.config["collaboration"]
    if not store.can_manage_members(project_id, int(g.current_user["id"])):
        return jsonify({"error": "Forbidden"}), 403
    if request.method == "DELETE":
        if not store.remove_member(project_id, user_id):
            return jsonify({"error": "Owner cannot be removed or member was not found"}), 409
        return "", 204
    payload = request.get_json(silent=True) or {}
    try:
        updated = store.set_member_role(project_id, user_id, str(payload.get("role", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return (
        (jsonify(store.get_membership(project_id, user_id)), 200)
        if updated
        else (jsonify({"error": "Member not found"}), 404)
    )


@app.route("/compute/api/projects/<project_id>/transfer-ownership", methods=["POST"])
@login_required
def project_transfer_ownership_api(project_id: str):
    if blocked := require_bearer_auth():
        return blocked
    store = current_app.config["collaboration"]
    uid = int(g.current_user["id"])
    if not store.can(project_id, uid, "transfer_ownership"):
        return jsonify({"error": "Forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    try:
        target = int(payload["user_id"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "user_id is required"}), 400
    if not store.transfer_ownership(project_id, uid, target):
        return jsonify({"error": "Ownership transfer requires an existing member"}), 409
    return jsonify({"status": "transferred"})


@app.route("/compute/api/projects/<project_id>/invitations", methods=["POST"])
@login_required
def project_invite_api(project_id: str):
    if blocked := require_bearer_auth():
        return blocked
    store = current_app.config["collaboration"]
    uid = int(g.current_user["id"])
    if not store.can(project_id, uid, "invite_members"):
        return jsonify({"error": "Forbidden"}), 403
    payload = request.get_json(silent=True) or {}
    user = None
    if payload.get("username"):
        user = current_app.config["user_db"].get_user_by_username(str(payload["username"]))
    elif payload.get("user_id") is not None:
        try:
            user = current_app.config["user_db"].get_user(int(payload["user_id"]))
        except (TypeError, ValueError):
            user = None
    if not user or user.get("deleted"):
        return jsonify({"error": "Invited user was not found"}), 404
    try:
        invitation = store.invite(project_id, int(user["id"]), uid, str(payload.get("role", "viewer")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(invitation), 201


@app.route("/compute/api/projects/<project_id>/invitations", methods=["GET"])
@login_required
def project_invitations_api(project_id: str):
    store = current_app.config["collaboration"]
    if not store.can_manage_members(project_id, int(g.current_user["id"])):
        return jsonify({"error": "Forbidden"}), 403
    users = current_app.config["user_db"]
    invitations = []
    for invitation in store.list_project_invitations(project_id):
        invited = users.get_user(invitation["invited_user_id"])
        invitations.append({**invitation, "invited_username": invited.get("username") if invited else "Deleted user"})
    return jsonify({"invitations": invitations})


@app.route("/compute/api/projects/<project_id>/invitations/<invitation_id>", methods=["DELETE"])
@login_required
def project_invitation_revoke_api(project_id: str, invitation_id: str):
    if blocked := require_bearer_auth():
        return blocked
    store = current_app.config["collaboration"]
    invitation = store.get_invitation(invitation_id)
    if (
        not invitation
        or str(invitation["project_id"]) != str(project_id)
        or not store.can_manage_members(project_id, int(g.current_user["id"]))
    ):
        return jsonify({"error": "Invitation not found"}), 404
    return (
        ("", 204)
        if store.revoke_invitation(invitation_id)
        else (jsonify({"error": "Invitation is no longer pending"}), 409)
    )


@app.route("/compute/api/invitations", methods=["GET"])
@login_required
def invitations_api():
    store = current_app.config["collaboration"]
    invitations = []
    for invitation in store.list_invitations(int(g.current_user["id"])):
        project = store.get_project(invitation["project_id"])
        invitations.append({**invitation, "project_name": project.get("name") if project else "Project"})
    return jsonify({"invitations": invitations})


@app.route("/compute/api/invitations/<invitation_id>", methods=["POST"])
@login_required
def invitation_response_api(invitation_id: str):
    if blocked := require_bearer_auth():
        return blocked
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    if action is None and isinstance(payload.get("accept"), bool):
        action = "accept" if payload["accept"] else "decline"
    if action not in {"accept", "decline"}:
        return jsonify({"error": "action must be accept or decline"}), 400
    accepted = action == "accept"
    ok = current_app.config["collaboration"].respond_invitation(invitation_id, int(g.current_user["id"]), accepted)
    return (
        (jsonify({"status": "accepted" if accepted else "declined"}), 200)
        if ok
        else (jsonify({"error": "Invalid or expired invitation"}), 404)
    )


@app.route("/compute/api/projects/<project_id>/archive", methods=["POST"])
@login_required
def project_archive_api(project_id: str):
    if blocked := require_bearer_auth():
        return blocked
    store = current_app.config["collaboration"]
    if not store.can(project_id, int(g.current_user["id"]), "delete_project"):
        return jsonify({"error": "Project not found"}), 404
    return (
        (jsonify({"status": "archived"}), 200)
        if store.archive_project(project_id)
        else (jsonify({"error": "Project not found"}), 404)
    )


@app.route("/compute/api/users/search", methods=["GET"])
@login_required
def users_search_api():
    query = request.args.get("q", "").strip().casefold()
    if len(query) < 2:
        return jsonify({"users": []})
    users = [
        {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("full_name") or user["username"],
        }
        for user in current_app.config["user_db"].list_users()
        if query in str(user.get("username") or "").casefold() or query in str(user.get("full_name") or "").casefold()
    ][:20]
    return jsonify({"users": users})


@app.route("/compute/api/projects/<project_id>/tasks", methods=["GET"])
@optional_user
def project_tasks_api(project_id: str):
    if not _project_access(project_id, "view_tasks"):
        return jsonify({"error": "Project not found"}), 404
    tasks = [
        {
            "md5sum": task["md5sum"],
            "filename": task["filename"],
            "task_type": task["task_type"],
            "status": task["status"],
            "uploaded_at": task["uploaded_at"],
            "username": task.get("username"),
        }
        for task in task_store.list_tasks()
        if task.get("scope_type") == "project" and str(task.get("scope_id")) == str(project_id)
    ]
    return jsonify({"tasks": tasks})


@app.route("/", methods=["GET"])
def index_page():
    return render_template("index.html")


@app.route("/api-docs", methods=["GET"])
def api_docs_page():
    return render_template("api_docs.html")


@app.route("/openapi.json", methods=["GET"])
def openapi_spec():
    return send_from_directory(app.static_folder, "openapi.json", mimetype="application/json")


@app.route("/runners", methods=["GET"])
def runners_page():
    catalog = _available_task_types(include_runner_metadata=True)
    return render_template("runners.html", task_types=catalog["task_types"])


@app.route("/runners/<name>", methods=["GET"])
def runner_detail_page(name: str):
    task_type = next(
        (item for item in _available_task_types(include_runner_metadata=True)["task_types"] if item["name"] == name),
        None,
    )
    if task_type is None:
        abort(404)
    return render_template("runner_detail.html", task_type=task_type)


@app.route("/compute/health", methods=["GET"])
def health():
    """Liveness probe — unauthenticated, empty 200 when the process answers."""
    return "", 200


@app.route("/compute/viewer-shell", methods=["GET"])
def viewer_shell():
    """Sandboxed shell that hosts the Mol* viewer in isolation.

    Mol*'s bundle calls ``new Function`` at load, which the main app's
    strict CSP (no ``'unsafe-eval'``) forbids. This shell page carries its
    own CSP scoped to itself — eval is permitted here and nowhere else —
    and receives all structure data from the authenticated parent page via
    postMessage, so no data, auth, or server fetch ever lives in the shell.
    """
    response: Response = make_response(render_template("viewer_shell.html"))
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "script-src 'self' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src data: blob:; "
        "font-src data:; "
        "worker-src blob:; "
        "connect-src data:"
    )
    # The whole point is embedding — the global DENY must not apply here.
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


@app.route("/compute/login", methods=["GET"])
def login_page():
    return_to = request.args.get("return_to", "")
    if (
        not return_to.startswith("/")
        or return_to.startswith("//")
        or "\\" in return_to
        or any(ord(character) < 32 for character in return_to)
    ):
        return_to = url_for("task_dashboard")
    if load_current_user() is not None:
        return redirect(return_to)
    return render_template("login.html", return_to=return_to)


@app.route("/compute/terms", methods=["GET"])
def terms_page():
    return render_template("terms.html")


@app.route("/compute/register", methods=["GET"])
def register_page():
    if load_current_user() is not None:
        return redirect(url_for("task_dashboard"))
    if not ENABLE_REGISTER:
        return render_template("error.html", code=403, message="Registration is disabled on this server"), 403
    if not _email_configured():
        return (
            render_template("error.html", code=403, message="Registration requires email service to be configured"),
            403,
        )
    return render_template("register.html")


@app.route("/compute/create_task", methods=["GET"])
@login_required
def create_task():
    response = make_response(render_template("create_task.html"))
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/compute/profile", methods=["GET"])
@login_required
def profile_page():
    return render_template("profile.html")


@app.route("/compute/user_control", methods=["GET"])
@login_required
def user_control_page():
    """Admin-only user management page."""
    if g.current_user.get("role") != "admin":
        return render_template("error.html", code=403, message="Admin access required"), 403
    return render_template("user_control.html", is_admin_user=True)


@app.route("/compute/logs", methods=["GET"])
@login_required
def log_viewer_page():
    """Admin-only active-log viewer."""
    if g.current_user.get("role") != "admin":
        return render_template("error.html", code=403, message="Admin access required"), 403
    return render_template("log_viewer.html")


@app.route("/compute/configuration", methods=["GET"])
@login_required
def configuration_page():
    """Admin-only runtime configuration page."""
    if g.current_user.get("role") != "admin":
        return render_template("error.html", code=403, message="Admin access required"), 403
    return render_template("configuration.html")


@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return send_from_directory(TEMPLATE_IMAGE_DIR, "logo.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/static/js/<path:filename>", methods=["GET"])
def static_workspace_js(filename: str):
    response = send_from_directory(os.path.join(current_app.static_folder, "js"), filename, conditional=True)
    if filename in _ITERATED_STATIC_JS:
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/compute/logo.svg", methods=["GET"])
def logo_svg():
    return send_from_directory(TEMPLATE_IMAGE_DIR, "logo.svg", mimetype="image/svg+xml")


@app.route("/PSSM_GREMLIN/")
@app.route("/PSSM_GREMLIN/dashboard")
def legacy_dashboard_redirect():
    """302 redirect to the current dashboard root."""
    return redirect(url_for("task_dashboard")), 302


# ---------------------------------------------------------------------------
# Task API routes
# ---------------------------------------------------------------------------


@app.route("/compute/api/types", methods=["GET"])
def task_types_list():
    """Return registered task types (public — needed by the create-task page)."""
    return jsonify(_available_task_types())


def _task_guidance(tt) -> dict[str, Any]:
    return {
        "summary": tt.summary,
        "use_when": tt.use_when,
        "input_summary": tt.input_summary,
        "output_summary": tt.output_summary,
        "considerations": list(tt.considerations),
    }


def _parameter_payload(parameter, *, include_help: bool = False) -> dict[str, Any]:
    payload = {
        "name": parameter.name,
        "type": parameter.type,
        "default": parameter.default,
        "required": parameter.required,
        "description": parameter.description,
        "label": parameter.label or parameter.name.replace("_", " ").title(),
        "choices": list(parameter.choices),
        "minimum": parameter.minimum,
        "maximum": parameter.maximum,
        "step": parameter.step,
        "unit": parameter.unit,
        "advanced": parameter.advanced,
    }
    if include_help:
        payload["help"] = parameter.help
    return payload


def _task_summary(tt, *, include_params: bool = False, include_runner_metadata: bool = False) -> dict[str, Any]:
    payload = {
        "name": tt.name,
        "display_name": tt.display_name,
        "category": tt.category,
        **_task_guidance(tt),
        "gpus": tt.gpus,
        "requires_network": tt.requires_network or any(stage.requires_network for stage in tt.workflow),
        "input_extensions": list(tt.input_extensions or (tt.input_extension,)),
        "input_label": tt.input_label,
        "stage_markers": tt.stage_markers,
    }
    if include_params:
        payload["params"] = [_parameter_payload(parameter) for parameter in tt.params]
    if include_runner_metadata:
        payload.update(
            runtime_family=tt.runtime.name,
            citations=[{"num": number, "doi": doi, "title": title} for number, doi, title in tt.citation_dois],
        )
    return payload


def _available_task_types(*, include_runner_metadata: bool = False) -> dict[str, Any]:
    """Serialize the ordered, enabled scientific method catalog."""
    manage_db = current_app.config.get("manage_db")
    enabled_types = []
    for tt in list_types():
        if manage_db is not None and manage_db.task_type_is_enabled(tt.name) is False:
            continue
        enabled_types.append(_task_summary(tt, include_params=True, include_runner_metadata=include_runner_metadata))
    category_order = {category.name: category.order for category in list_categories()}
    enabled_types.sort(key=lambda item: (category_order[item["category"]], item["display_name"].lower()))
    return {
        "version": 2,
        "categories": [
            {
                "name": category.name,
                "label": category.label,
                "description": category.description,
                "order": category.order,
            }
            for category in list_categories()
            if any(task["category"] == category.name for task in enabled_types)
        ],
        "task_types": enabled_types,
    }


def _input_workspace_payload(tt) -> dict:
    """Serialize the declarative, non-executable input workspace contract."""
    return {
        "version": 3,
        "steps": [
            {
                "id": step.id,
                "title": step.title,
                "description": step.description,
                "capabilities": [
                    {
                        "plugin": capability.plugin,
                        "id": capability.id,
                        "title": capability.title,
                        "description": capability.description,
                        "options": capability.options,
                    }
                    for capability in step.capabilities
                ],
            }
            for step in tt.input_workspace
        ],
    }


@app.route("/compute/api/types/<name>", methods=["GET"])
def task_type_form(name: str):
    """Return a single task type's full form definition (public).

    The client fetches this when the user selects a task type, then
    dynamically builds the upload form from the response.
    """
    try:
        tt, runner = _get_task_type(name)
    except KeyError:
        return jsonify({"error": f"Unknown task type: {name!r}"}), 404

    manage_db = current_app.config.get("manage_db")
    if manage_db is not None:
        enabled = manage_db.task_type_is_enabled(tt.name)
        if enabled is False:
            return jsonify({"error": f"Task type {name!r} is disabled"}), 404

    if manage_db is not None:
        # Fail the form early on a broken policy, but do not expose the
        # resolved resource usage to users — resource review is not part of
        # the submission flow.  The real enforcement happens at submission.
        try:
            manage_db.resolve_task_resources(
                tt.name,
                requires_gpu=tt.gpus,
                default_timeout_seconds=runner.max_runtime_seconds,
            )
        except ResourceValidationError as exc:
            return jsonify({"error": f"Task resource policy is invalid: {exc}"}), 503

    return jsonify(
        {
            **_task_summary(tt),
            "definition_version": 3,
            "runtime_family": tt.runtime.name,
            "citations": [{"num": number, "doi": doi, "title": title} for number, doi, title in tt.citation_dois],
            "workflow": [
                {
                    "name": stage.name,
                    "display_name": stage.display_name,
                    "requires_gpu": stage.requires_gpu,
                    "requires_network": stage.requires_network,
                    "stage_markers": list(stage.stage_markers),
                }
                for stage in tt.workflow
            ],
            "file_input": {
                "accept": ",".join(tt.input_extensions or (tt.input_extension,)),
                "extensions": list(tt.input_extensions or (tt.input_extension,)),
                "primary_extensions": list(tt.primary_input_extensions or (tt.input_extension,)),
                "label": tt.input_label,
                "required": tt.min_input_files > 0,
                "multiple": tt.allow_multiple_inputs,
                "max_files": tt.max_input_files,
                "max_request_bytes": current_app.config["MAX_CONTENT_LENGTH"],
            },
            "params": [_parameter_payload(parameter, include_help=True) for parameter in tt.params],
            "input_workspace": _input_workspace_payload(tt),
        }
    )


@app.route("/compute/api/types/<name>/workspace/normalize", methods=["POST"])
@login_required
def normalize_workspace(name: str):
    """Normalize one stateful capability through its server-owned adapter."""
    try:
        tt, _ = _get_task_type(name)
    except KeyError:
        return jsonify({"error": f"Unknown task type: {name!r}"}), 404
    payload = request.get_json(silent=True) or {}
    capability = next((item for item in iter_capabilities(tt) if item.id == payload.get("capability_id")), None)
    if capability is None or not capability.plugin.endswith("regions"):
        return jsonify({"error": "Unknown normalizable workspace capability"}), 400
    try:
        result = normalize_capability(tt.name, str(capability.options.get("syntax") or ""), payload.get("value"))
    except WorkspaceValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(result)


_WORKSPACE_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _safe_input_relative_path(raw_path: str) -> str | None:
    normalized = str(raw_path or "").replace("\\", "/").strip()
    if normalized.startswith("/"):
        return None
    raw_parts = normalized.split("/")
    if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
        return None
    safe_parts = [secure_filename(part) for part in raw_parts]
    if any(not part for part in safe_parts):
        return None
    return "/".join(safe_parts)


def _validate_input_uploads(task_type: str = "gremlin", artifact_reference_count: int = 0):
    """Return validated uploads with safe relative paths, or an HTTP error."""
    try:
        tt, _ = _get_task_type(task_type)
    except KeyError:
        return None, (jsonify({"error": f"Unknown task type: {task_type}"}), 400)
    if "files" not in request.files and "file" not in request.files:
        if artifact_reference_count >= tt.min_input_files:
            return [], None
        return None, (jsonify({"error": "No file part"}), 400)
    uploads = request.files.getlist("files") or request.files.getlist("file")
    uploads = [uploaded for uploaded in uploads if uploaded.filename]
    total_inputs = len(uploads) + artifact_reference_count
    if total_inputs < tt.min_input_files:
        return None, (jsonify({"error": "No selected file"}), 400)
    if not tt.allow_multiple_inputs and total_inputs != 1:
        return None, (jsonify({"error": f"{tt.display_name} accepts exactly one input file"}), 400)
    if total_inputs > tt.max_input_files:
        return None, (jsonify({"error": f"At most {tt.max_input_files} input files are allowed"}), 400)
    submitted_paths = request.form.getlist("input_paths")
    accepted = tuple(extension.lower() for extension in (tt.input_extensions or (tt.input_extension,)))
    primary_accepted = tuple(extension.lower() for extension in (tt.primary_input_extensions or (tt.input_extension,)))
    validated: list[tuple[Any, str]] = []
    seen_paths: set[str] = set()
    for index, uploaded in enumerate(uploads):
        raw_path = submitted_paths[index] if index < len(submitted_paths) else uploaded.filename
        safe_path = _safe_input_relative_path(raw_path)
        if safe_path is None or safe_path in seen_paths:
            return None, (jsonify({"error": "Invalid or duplicate input path"}), 400)
        if not safe_path.lower().endswith(accepted):
            return None, (jsonify({"error": f"Input file extensions must be one of: {', '.join(accepted)}"}), 400)
        if index == 0 and not safe_path.lower().endswith(primary_accepted):
            return None, (
                jsonify({"error": f"The primary input extension must be one of: {', '.join(primary_accepted)}"}),
                400,
            )
        seen_paths.add(safe_path)
        validated.append((uploaded, safe_path))
    return validated, None


def _save_uploaded_inputs(
    uploads: list[tuple[Any, str]],
    task_type: str,
    params: dict[str, Any],
    *,
    referenced_inputs: list[dict[str, Any]] | None = None,
    scope_identity: str,
) -> tuple[str, list[dict[str, Any]], dict[str, str]]:
    """Persist content-addressed blobs and derive an owner-scoped task ID."""
    metadata = _request_metadata()
    saved: list[dict[str, Any]] = []
    for uploaded, relative_path in uploads:
        temp_name = f".tmp_{os.urandom(8).hex()}_{os.path.basename(relative_path)}"
        temp_path = _safe_join(app.config["UPLOAD_FOLDER"], temp_name)
        uploaded.save(temp_path)
        hasher = hashlib.sha256()
        with open(temp_path, "rb") as handle:
            while chunk := handle.read(65536):
                hasher.update(chunk)
        blob_hash = hasher.hexdigest()
        blob_path = _safe_join(app.config["UPLOAD_FOLDER"], f"{blob_hash}.upload")
        if os.path.exists(blob_path):
            os.remove(temp_path)
        else:
            os.replace(temp_path, blob_path)
        saved.append(
            {
                "original_name": uploaded.filename,
                "relative_path": relative_path,
                "hash": blob_hash,
                "blob_path": blob_path,
            }
        )
    saved.extend(referenced_inputs or [])
    identity = json.dumps(
        {
            "task_type": task_type,
            "params": params,
            "inputs": [{"path": item["relative_path"], "sha256": item["hash"]} for item in saved],
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    content_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return _task_id_for_upload(content_id, scope_identity), saved, metadata


_ARTIFACT_REFERENCE_PATTERN = re.compile(r"@([a-fA-F0-9]{32})/(.+)")


def _artifact_reference_values() -> list[str]:
    references: list[str] = []
    for value in request.form.getlist("artifact_references"):
        references.extend(line.strip() for line in str(value).splitlines() if line.strip())
    return references


def _resolve_submission_scope(submission: TaskSubmissionRequest) -> dict[str, Any]:
    user = g.current_user
    if submission.scope_type == "personal":
        storage_key = user.get("storage_key")
        if not storage_key:
            raise RuntimeError("User storage identity is unavailable")
        return {"scope_type": "personal", "scope_id": str(user["id"]), "storage_key": storage_key}
    project = current_app.config["collaboration"].get_project(submission.scope_id)
    if not project or not current_app.config["collaboration"].can_submit_task(project["id"], user["id"]):
        raise PermissionError("Project is unavailable or does not accept submissions")
    return {"scope_type": "project", "scope_id": str(project["id"]), "storage_key": project["storage_key"]}


def _can_reuse_source_task(source: dict[str, Any], destination_scope: dict[str, Any]) -> bool:
    user = g.current_user
    if source.get("scope_type") == "project":
        source_project = str(source.get("scope_id") or "")
        return (
            destination_scope["scope_type"] == "project"
            and source_project == destination_scope["scope_id"]
            and bool(source_project)
            and current_app.config["collaboration"].can_use_artifact(int(source_project), int(user["id"]))
        )
    if destination_scope["scope_type"] != "personal":
        return False
    return source.get("scope_type") == "personal" and str(source["scope_id"]) == str(user["id"])


def _resolve_artifact_inputs(
    references: list[str], task_type: Any, destination_scope: dict[str, Any], uploaded_count: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = tuple(extension.lower() for extension in (task_type.input_extensions or (task_type.input_extension,)))
    primary = tuple(
        extension.lower() for extension in (task_type.primary_input_extensions or (task_type.input_extension,))
    )
    saved: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    used_paths: set[str] = set()
    for index, expression in enumerate(references):
        match = _ARTIFACT_REFERENCE_PATTERN.fullmatch(expression)
        if not match:
            raise ValueError("Invalid artifact reference")
        source_task_id, logical_path = match.groups()
        source = task_store.get_task(source_task_id.lower())
        # Authorization intentionally precedes manifest or filesystem access.
        if (
            source is None
            or source.get("status") != "finished"
            or not _can_reuse_source_task(source, destination_scope)
        ):
            raise PermissionError("Artifact reference is unavailable")
        resolved = current_app.config["storage_resolver"].resolve_artifact(source, logical_path)
        if resolved is None:
            raise ValueError("Artifact reference is unavailable")
        logical_extension = os.path.splitext(logical_path)[1].lower()
        allowed = primary if uploaded_count == 0 and index == 0 else accepted
        if logical_extension not in allowed:
            raise ValueError("Artifact type is incompatible with this task input")
        blob_path = _safe_join(app.config["UPLOAD_FOLDER"], f"{resolved['sha256']}.upload")
        if not os.path.exists(blob_path):
            temporary = _safe_join(app.config["UPLOAD_FOLDER"], f".tmp_artifact_{os.urandom(8).hex()}")
            shutil.copyfile(resolved["physical_path"], temporary)
            try:
                os.replace(temporary, blob_path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        relative_path = secure_filename(os.path.basename(logical_path))
        if not relative_path or relative_path in used_paths:
            relative_path = f"{source_task_id[:8]}-{relative_path or 'artifact'}"
        if relative_path in used_paths:
            raise ValueError("Artifact references produce duplicate input paths")
        used_paths.add(relative_path)
        saved.append(
            {
                "original_name": relative_path,
                "relative_path": relative_path,
                "hash": resolved["sha256"],
                "blob_path": blob_path,
                "artifact_reference": expression,
            }
        )
        provenance.append(
            {
                "input_name": relative_path,
                "source_task_id": source["md5sum"],
                "source_artifact_path": resolved["path"],
                "source_scope_type": source["scope_type"],
                "source_scope_id": source.get("scope_id"),
                "sha256": resolved["sha256"],
                "size": resolved["size"],
                "media_type": resolved.get("media_type"),
                "created_at": time.time(),
            }
        )
    return saved, provenance


def _existing_upload_response(existing_task: dict[str, Any] | None, md5sum: str):
    if not existing_task:
        return None
    if not _task_access_allowed(existing_task):
        return _task_access_denied(md5sum)
    if existing_task["status"] == "finished":
        return redirect(f"/compute/api/running/{md5sum}", code=302)
    if existing_task["status"] in {
        "pending",
        "queued",
        "running",
        *task_store.CLEANUP_CLAIM_STATUSES,
    }:
        return jsonify({"status": "Task already queued or running", "md5sum": md5sum}), 202
    return None


def _prepare_task_record(
    md5sum: str,
    saved_inputs: list[dict[str, Any]],
    metadata: dict[str, str],
    task_type: str = "gremlin",
    input_form: dict[str, Any] | None = None,
    task_scope: dict[str, Any] | None = None,
    artifact_provenance: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not task_scope:
        raise ValueError("Task scope is required")
    task_identity = {
        "md5sum": md5sum,
        "scope_type": task_scope["scope_type"],
        "scope_id": task_scope["scope_id"],
        "storage_key": task_scope["storage_key"],
    }
    resolver = app.config["storage_resolver"]
    workspace_dir = resolver.get_input_root(task_identity)
    if os.path.exists(workspace_dir):
        shutil.rmtree(workspace_dir)
    snapshot_root = _safe_join(workspace_dir, "inputs")
    os.makedirs(snapshot_root, exist_ok=True)
    for item in saved_inputs:
        destination = _safe_join(snapshot_root, *item["relative_path"].split("/"))
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(item["blob_path"], destination)
        os.chmod(destination, 0o440)

    result_dir = resolver.get_output_root(task_identity)
    if os.path.exists(result_dir):
        shutil.rmtree(result_dir)
    os.makedirs(result_dir, exist_ok=True)
    zip_path = resolver.get_archive_path(task_identity)
    if os.path.exists(zip_path):
        os.remove(zip_path)

    primary = saved_inputs[0] if saved_inputs else None
    return {
        "filename": primary["relative_path"] if primary else "Generated structure",
        "file_path": primary["blob_path"] if primary else "",
        "uploaded_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "walltime": None,
        "is_binary": int(_is_binary_file(primary["blob_path"])) if primary else 0,
        "source_ip": metadata["ip"],
        "user_agent": metadata["user_agent"],
        "username": metadata["username"],
        "request_headers": metadata["headers_json"],
        "local_user": _local_user_identity(),
        "celery_task_id": None,
        "run_stage": None,
        "task_type": task_type,
        "input_form": json.dumps(input_form) if input_form else None,
        **task_identity,
        "artifact_provenance": json.dumps(artifact_provenance or [], sort_keys=True),
    }


def _reject_invalid_input(
    md5sum: str, base_record: dict[str, Any], saved_inputs: list[dict[str, Any]], task_type: str = "gremlin"
):
    """Reject uploads whose content doesn't match the expected format.

    Every uploaded file — primary and auxiliary alike — passes the
    4096-byte binary sniff and is then content-validated by extension
    (FASTA/A3M/PDB/mmCIF/JSON) with generous DoS caps (see
    revocompute.input_validators), so third-party parsers never see
    pathological content from any input of a multi-file task.
    """
    error_message = None
    response_message = ""
    for item in saved_inputs:
        blob_path = item["blob_path"]
        if _is_binary_file(blob_path):
            error_message = f"Binary file uploads are not supported: {item['relative_path']}"
            response_message = "Uploaded file contains binary content"
            break
        error_message = validate_input_file(blob_path, item["relative_path"] or "")
        if error_message is not None:
            response_message = error_message
            break
    if error_message is None:
        return None

    finished_at = time.time()
    failed_task = {**base_record, "md5sum": md5sum, "status": "failed", "error": error_message}
    failed_record = {**base_record, "finished_at": finished_at}
    task_store.upsert_task(md5sum, **failed_record, status="failed", error=error_message)
    _finalize_failed_results(failed_task, error_message, finished_at=finished_at)
    _cleanup_task_workspace(failed_task)
    return jsonify({"error": response_message}), 400


@app.route("/compute/api/post", methods=["POST"])
@login_required
@rate_limit(max_requests=30, window_seconds=3600)
def upload_file():  # skipcq: PY-R1000 -- route validation branches form one transactional request boundary.
    if _blocked := require_bearer_auth():
        return _blocked

    # Deployment maintenance sentinel (restart.sh --drain): SERVER_DIR is
    # bind-mounted into the web container, so the host-side file is visible.
    if os.path.exists(os.path.join(CONFIG.server_dir, ".maintenance")):
        return jsonify({"error": "Server is in maintenance; submissions are paused"}), 503

    # Parse flat form data ("params[key]=value") into nested dict
    raw_form = request.form.to_dict(flat=True)
    artifact_references = _artifact_reference_values()
    raw_form.pop("artifact_references", None)
    form_data: dict[str, Any] = {}
    nested_params: dict[str, Any] = {}
    for key, value in raw_form.items():
        if key.startswith("params[") and key.endswith("]"):
            nested_params[key[len("params[") : -1]] = value
        else:
            form_data[key] = value
    if nested_params:
        form_data["params"] = nested_params

    workspace_payload: dict[str, Any] = {}
    raw_workspace = form_data.pop("workspace", None)
    if raw_workspace is not None:
        try:
            workspace_payload = json.loads(raw_workspace)
        except (TypeError, json.JSONDecodeError):
            return jsonify({"error": "Workspace must be valid JSON"}), 400
        if not isinstance(workspace_payload, dict) or workspace_payload.get("version") != 2:
            return jsonify({"error": "Unsupported workspace document"}), 400

    try:
        submission = TaskSubmissionRequest.model_validate(form_data)
    except ValidationError as exc:
        errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
        return jsonify({"error": "Validation failed", "details": errors}), 400

    task_type = submission.task_type
    try:
        tt, runner = _get_task_type(task_type)
    except KeyError:
        return jsonify({"error": f"Unknown task type: {task_type}"}), 400
    normalized_regions = None
    capability_values = workspace_payload.get("capabilities", {})
    if not isinstance(capability_values, dict):
        return jsonify({"error": "Workspace capabilities must be an object"}), 400
    known_capability_ids = {item.id for item in iter_capabilities(tt)}
    if set(capability_values) - known_capability_ids:
        return jsonify({"error": "Workspace contains an unknown capability"}), 400
    region_capability = next((item for item in iter_capabilities(tt) if item.plugin.endswith("regions")), None)
    if region_capability is not None and region_capability.options.get("syntax") == "rfdiffusion":
        if region_capability.id not in capability_values:
            return jsonify({"error": "Workspace is missing region state"}), 400
        try:
            normalized_regions = normalize_capability(
                tt.name,
                str(region_capability.options.get("syntax") or ""),
                capability_values[region_capability.id],
            )
        except WorkspaceValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        owned_fields = set(region_capability.options.get("fields", []))
        if owned_fields & set(submission.params):
            return jsonify({"error": "Region-owned parameters must be submitted through workspace state"}), 400
        submission.params.update(normalized_regions["params"])
    coerced_params = submission.coerce_params()
    try:
        task_scope = _resolve_submission_scope(submission)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError:
        logging.exception("Authenticated user has no immutable storage identity")
        return jsonify({"error": "Account storage is not initialized; contact an administrator."}), 503

    managedb = current_app.config.get("manage_db")
    if managedb is not None:
        enabled = managedb.task_type_is_enabled(task_type)
        if enabled is False:
            return jsonify({"error": f"Task type {task_type!r} is currently disabled"}), 400

    # Reject GPU-ineligible users and invalid scheduler configuration before
    # writing uploads or creating a task record.
    if tt.gpus and not g.current_user.get("allow_gpu_use"):
        return jsonify({"error": "GPU access required for this task type. Contact an administrator."}), 403
    resource_policy = None
    resource_policies: dict[str, Any] = {}
    if managedb is not None:
        try:
            if tt.workflow:
                resource_policies = {
                    stage.name: managedb.resolve_task_resources(
                        stage.name,
                        requires_gpu=stage.requires_gpu,
                        default_timeout_seconds=runner.max_runtime_seconds,
                    )
                    for stage in tt.workflow
                }
            else:
                resource_policy = managedb.resolve_task_resources(
                    tt.name,
                    requires_gpu=tt.gpus,
                    default_timeout_seconds=runner.max_runtime_seconds,
                )
        except ResourceValidationError as exc:
            logging.error("Resource policy rejected submission for %s: %s", task_type, exc)
            return jsonify({"error": "This task type has an invalid resource policy; contact an administrator."}), 503

    uploaded_inputs, upload_error = _validate_input_uploads(task_type, len(artifact_references))
    if upload_error is not None:
        return upload_error
    try:
        referenced_inputs, artifact_provenance = _resolve_artifact_inputs(
            artifact_references, tt, task_scope, len(uploaded_inputs)
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    uploaded_paths = {path for _, path in uploaded_inputs}
    if uploaded_paths & {item["relative_path"] for item in referenced_inputs}:
        return jsonify({"error": "Uploaded files and artifact references have duplicate input paths"}), 400
    md5sum, saved_inputs, metadata = _save_uploaded_inputs(
        uploaded_inputs,
        task_type,
        coerced_params,
        referenced_inputs=referenced_inputs,
        scope_identity=f"{task_scope['scope_type']}:{task_scope['scope_id']}",
    )
    for record in artifact_provenance:
        record["downstream_task_id"] = md5sum
    if normalized_regions is not None:
        try:
            validate_rfdiffusion_structure(
                normalized_regions,
                saved_inputs[0]["blob_path"] if saved_inputs else None,
            )
        except WorkspaceValidationError as exc:
            return jsonify({"error": str(exc)}), 400
    workspace_key = task_scope["storage_key"]
    if not _WORKSPACE_KEY_PATTERN.fullmatch(workspace_key):
        return jsonify({"error": "Username cannot be represented safely in a workspace path"}), 400

    existing_task = task_store.get_task(md5sum)
    if existing_response := _existing_upload_response(existing_task, md5sum):
        return existing_response

    # ponytail: per-user cap on active tasks — the expensive resource is the
    # Celery/Docker queue, not the HTTP layer.  Raise MAX_ACTIVE_TASKS_PER_USER
    # if users routinely hit it with legitimate batch work.
    MAX_ACTIVE_TASKS_PER_USER = 5
    if task_store.count_user_active_tasks(metadata["username"]) >= MAX_ACTIVE_TASKS_PER_USER:
        return (
            jsonify(
                {
                    "error": "Too many pending or running tasks. "
                    "Please wait for existing tasks to complete before submitting new ones."
                }
            ),
            429,
        )

    # Build entities — one list for files and params together.
    entities: list[dict[str, Any]] = []

    scoped_task = {"md5sum": md5sum, **task_scope}
    snapshot_root = _safe_join(app.config["storage_resolver"].get_input_root(scoped_task), "inputs")
    virtual_root = f"/mnt/revocompute/{workspace_key}"
    for index, item in enumerate(saved_inputs):
        entities.append(
            {
                "name": "primary_input" if index == 0 else f"input_{index + 1}",
                "type": "file",
                "value": item["original_name"],
                "verified_value": item["relative_path"],
                "relative_path": item["relative_path"],
                "mounted": f"{virtual_root}/inputs/{item['relative_path']}",
                "hash": item["hash"],
                "snapshot_path": _safe_join(snapshot_root, *item["relative_path"].split("/")),
                "snapshot_root": snapshot_root,
                "workspace_key": workspace_key,
            }
        )

    # Param entities — raw form value vs pydantic-coerced verified_value
    known_params = {p.name: p for p in tt.params}
    for key, verified in coerced_params.items():
        param = known_params[key]
        raw = submission.params.get(key, verified)
        entities.append(
            {
                "name": key,
                "type": param.type,
                "value": raw,
                "verified_value": verified,
            }
        )

    input_form = {
        "user": metadata["username"],
        "workspace_key": workspace_key,
        "virtual_root": virtual_root,
        "snapshot_root": snapshot_root,
        "submitted_at": datetime.now(tz=timezone.utc).isoformat(),
        "entities": entities,
        "resource_policy": resource_policy.public_dict() if resource_policy is not None else None,
        "resource_policies": {name: policy.public_dict() for name, policy in resource_policies.items()},
        "workspace": workspace_payload,
        "scope": {"type": task_scope["scope_type"], "id": task_scope["scope_id"]},
        "artifact_provenance": artifact_provenance,
    }

    # Runner protocol v2: the immutable snapshot carries task.json — the
    # single manifest every runner reads (params + file paths).  No
    # user-shaped data travels through environment variables anymore.
    task_manifest = {
        "task_id": md5sum,
        "task_type": task_type,
        "params": {e["name"]: e["verified_value"] for e in entities if e["type"] != "file"},
        "files": [
            {
                "name": e["name"],
                "path": e["mounted"],
                "relative_path": e["relative_path"],
                "hash": e["hash"],
            }
            for e in entities
            if e["type"] == "file"
        ],
    }
    base_record = _prepare_task_record(
        md5sum,
        saved_inputs,
        metadata,
        task_type=task_type,
        input_form=input_form,
        task_scope=task_scope,
        artifact_provenance=artifact_provenance,
    )
    # The manifest lands inside the snapshot AFTER _prepare_task_record has
    # created it (and copied the input files into it).
    manifest_path = _safe_join(snapshot_root, "task.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(task_manifest, handle, indent=2, sort_keys=True)
    if invalid_response := _reject_invalid_input(md5sum, base_record, saved_inputs, task_type):
        return invalid_response

    task_store.upsert_task(
        md5sum,
        **base_record,
        status="pending",
        error=None,
    )

    try:
        async_result = run_compute_task.apply_async(args=[md5sum], kwargs={"task_type": task_type})
    except Exception:
        logging.exception("Failed to submit compute task %s to Celery", md5sum)
        error_message = "Task queue unavailable — please try again later"
        finished_at = time.time()
        failed_task = task_store.get_task(md5sum) or dict(md5sum=md5sum, **base_record)
        _finalize_failed_results(failed_task, error_message, finished_at=finished_at)
        _cleanup_task_workspace(failed_task)
        task_store.update_task(
            md5sum,
            status="failed",
            finished_at=finished_at,
            error=error_message,
        )
        return jsonify({"error": error_message}), 503
    task_store.update_task(md5sum, celery_task_id=async_result.id)

    return redirect(f"/compute/api/running/{md5sum}", code=302)


@app.route("/compute/api/running/<md5sum>", methods=["GET"])
@login_required
def run_gremlin(md5sum):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    status = task["status"]
    if status == "finished":
        return jsonify({"status": "finished", "md5sum": md5sum}), 200
    if status == "failed":
        return (
            jsonify({"status": "failed", "md5sum": md5sum, "error": _sanitize_task_error(task, task.get("error"))}),
            404,
        )
    if status in ("running", "queued"):
        return jsonify({"status": status, "md5sum": md5sum}), 202
    if status == "pending":
        return jsonify({"status": "pending", "md5sum": md5sum}), 202
    if status == "cancelled":
        return jsonify({"status": "cancelled", "md5sum": md5sum}), 200
    if status in task_store.CLEANUP_CLAIM_STATUSES:
        return jsonify({"status": status, "md5sum": md5sum}), 202
    if status in task_store.CLEANUP_STATUSES:
        return jsonify({"status": status, "md5sum": md5sum}), 200
    if status == "deleted:finshed":
        return jsonify({"status": "deleted:finshed", "md5sum": md5sum}), 200
    if status == "deleted:cancel":
        return jsonify({"status": "deleted:cancel", "md5sum": md5sum}), 200

    return (
        jsonify({"status": "unknown", "md5sum": md5sum, "error": "Invalid task status"}),
        500,
    )


@app.route("/compute/api/results/<md5sum>", methods=["GET"])
@login_required
def get_results(md5sum):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] not in {"finished", "failed"}:
        return redirect(f"/compute/api/running/{md5sum}", code=302)

    try:
        manifest_path = current_app.config["storage_resolver"].get_manifest_path(task)
    except ValueError:
        return jsonify({"status": "error", "md5sum": md5sum, "message": "result manifest not found"}), 404
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return jsonify({"status": "error", "md5sum": md5sum, "message": "result manifest not found"}), 404

    archive_ready = os.path.isfile(_task_zip_path(task))
    payload = dict(manifest)
    full_results = _task_full_results_allowed(task)
    if not full_results:
        payload["artifacts"] = [
            artifact for artifact in payload.get("artifacts", []) if _task_artifact_access_allowed(task, artifact)
        ]
        visible_paths = {artifact["path"] for artifact in payload["artifacts"]}
        payload["views"] = [
            {
                **view,
                "sources": {
                    name: [path for path in paths if path in visible_paths]
                    for name, paths in view.get("sources", {}).items()
                },
            }
            for view in payload.get("views", [])
        ]
    payload.update(
        {
            "status": task["status"],
            "archive": {
                "ready": archive_ready and full_results,
                "request_url": f"/compute/api/results/{md5sum}/archive" if full_results else None,
                "download_url": f"/compute/api/download/{md5sum}" if archive_ready and full_results else None,
            },
        }
    )
    for artifact in payload.get("artifacts", []):
        encoded_path = quote(artifact["path"], safe="/")
        artifact["url"] = f"/compute/api/results/{md5sum}/artifacts/{encoded_path}"
    logical_files: dict[str, list[dict[str, Any]]] = {}
    for file_id, files in payload.get("result", {}).get("files", {}).items():
        logical_files[file_id] = [
            {
                "id": file_id,
                "name": os.path.basename(artifact["path"]),
                "media_type": artifact["media_type"],
                "size": artifact["size"],
                "role": artifact["role"],
                "cardinality": artifact["cardinality"],
                "viewer": artifact.get("logical_type") or artifact["preview"] or "download",
                "preview": artifact.get("logical_type") or artifact["preview"],
                "url": f"/compute/api/results/{md5sum}/files/{file_id}?index={index}",
            }
            for index, artifact in enumerate(files)
            if full_results or _task_artifact_access_allowed(task, artifact)
        ]
    payload["result"] = {"files": logical_files}
    if payload.get("storyboard"):
        payload["storyboard"][
            "entrypoint_url"
        ] = f"/compute/api/results/{md5sum}/storyboard/{payload['storyboard']['entrypoint']}"
    return jsonify(payload)


@app.route("/compute/api/results/<md5sum>/files/<file_id>", methods=["GET"])
@login_required
def get_result_logical_file(md5sum: str, file_id: str):
    """Serve a single Expected File Tree identity, never a guessed path."""
    normalized = _normalize_task_id(md5sum)
    if normalized is None or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", file_id):
        return jsonify({"error": "Result file not found"}), 404
    task = task_store.get_task(normalized)
    if task is None or not _task_access_allowed(task):
        return jsonify({"error": "Result file not found"}), 404
    try:
        with open(current_app.config["storage_resolver"].get_manifest_path(task), encoding="utf-8") as handle:
            files = json.load(handle).get("result", {}).get("files", {}).get(file_id, [])
    except (OSError, json.JSONDecodeError):
        files = []
    try:
        index = int(request.args.get("index", "0"))
    except ValueError:
        index = -1
    if index < 0 or index >= len(files):
        return jsonify({"error": "Result file not found"}), 404
    return get_result_artifact(md5sum, files[index]["path"])


@app.route("/compute/api/results/<md5sum>/storyboard/<path:asset>", methods=["GET"])
@login_required
def get_result_storyboard_asset(md5sum: str, asset: str):
    """Serve an explicitly declared, deployment-controlled runner asset."""
    normalized = _normalize_task_id(md5sum)
    task = task_store.get_task(normalized) if normalized else None
    if task is None or not _task_access_allowed(task):
        return jsonify({"error": "Storyboard not found"}), 404
    try:
        task_type, _ = get_task_type(task.get("task_type", "gremlin"))
        declaration = storyboard_declaration(
            task_type, CONFIG.server_dir, set(expected_file_tree(task_type, CONFIG.server_dir))
        )
        root = runner_root(task_type, CONFIG.server_dir) / "storyboard"
        requested = asset.replace("\\", "/").strip("/")
        if (
            not declaration
            or requested != declaration["entrypoint"]
            or not requested
            or any(part in {"", ".", ".."} for part in requested.split("/"))
        ):
            abort(404)
        target = (root / requested).resolve()
        if not target.is_file() or not target.is_relative_to(root.resolve()) or target.suffix != ".js":
            abort(404)
    except (KeyError, ResultContractError):
        abort(404)
    response = send_from_directory(root, requested, mimetype="text/javascript")
    response.headers["Cache-Control"] = "private, no-cache"
    return response


def _result_artifact(task: dict[str, Any], relative_path: str) -> tuple[str, dict[str, Any]] | None:
    """Resolve only regular files published by the task's finalized manifest."""
    resolved = current_app.config["storage_resolver"].resolve_artifact(task, relative_path)
    if resolved is None:
        return None
    path = resolved.pop("physical_path")
    return path, resolved


@app.route("/compute/api/results/<md5sum>/artifacts/<path:relative_path>", methods=["GET"])
@login_required
def get_result_artifact(md5sum: str, relative_path: str):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"error": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)
    resolved = _result_artifact(task, relative_path)
    if resolved is None:
        return jsonify({"error": "Artifact not found"}), 404
    path, artifact = resolved
    if not _task_artifact_access_allowed(task, artifact):
        return jsonify({"error": "Artifact not found"}), 404
    # Artifacts are untrusted runner output — default to attachment so they
    # are never rendered same-origin.  `?download=1` still forces a download
    # and `?download=0` explicitly opts back into inline rendering.
    as_attachment = request.args.get("download", "1") in {"1", "true", "yes"}
    if app.config["RESULT_DOWNLOAD_MODE"] == "nginx":
        internal_path = quote(os.path.relpath(path, app.config["RESULTS_FOLDER"]).replace(os.sep, "/"), safe="/")
        response = Response(status=200, mimetype=artifact.get("media_type") or "application/octet-stream")
        response.headers["X-Accel-Redirect"] = f"/_protected_results/{internal_path}"
        response.headers.set(
            "Content-Disposition",
            "attachment" if as_attachment else "inline",
            filename=os.path.basename(path),
        )
        response.headers["Cache-Control"] = "private, no-store"
        return response
    response = send_from_directory(
        os.path.dirname(path),
        os.path.basename(path),
        as_attachment=as_attachment,
        download_name=os.path.basename(path),
        mimetype=artifact.get("media_type") or None,
    )
    # Defense in depth: even an explicitly-inline artifact runs no scripts.
    # (In nginx mode the served body comes from the internal location, which
    # sets the same header in docker/nginx/default.conf.template.)
    response.headers["Content-Security-Policy"] = "sandbox"
    return response


@app.route("/compute/api/results/<md5sum>/tables/<path:relative_path>", methods=["GET"])
@login_required
def get_result_table(md5sum: str, relative_path: str):
    """Return a bounded, correctly parsed page from a manifest table artifact."""
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"error": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    if not _task_access_allowed(task):
        return _task_access_denied(md5sum)
    resolved = _result_artifact(task, relative_path)
    if resolved is None:
        return jsonify({"error": "Table artifact not found"}), 404
    path, artifact = resolved
    if not _task_artifact_access_allowed(task, artifact):
        return jsonify({"error": "Table artifact not found"}), 404
    if artifact.get("preview") != "table":
        return jsonify({"error": "Artifact is not a table"}), 400
    try:
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 100))
    except ValueError:
        return jsonify({"error": "Invalid table page"}), 400
    if offset < 0 or offset > 10000 or limit < 1 or limit > 500:
        return jsonify({"error": "Table page is outside allowed bounds"}), 400
    delimiter = "\t" if relative_path.lower().endswith(".tsv") else ","
    try:
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            columns = next(reader, [])
            max_columns = 512 if request.args.get("matrix") == "1" else 100
            if len(columns) > max_columns or any(len(cell) > 16384 for cell in columns):
                raise ValueError("Table header exceeds preview limits")
            rows = []
            for index, row in enumerate(reader):
                if index < offset:
                    continue
                if len(rows) > limit:
                    break
                if len(row) > max_columns or any(len(cell) > 16384 for cell in row):
                    raise ValueError("Table row exceeds preview limits")
                rows.append(row)
    except (OSError, UnicodeError, csv.Error, ValueError):
        logging.exception("Table preview failed for task %s artifact %s", md5sum, relative_path)
        return jsonify({"error": "Table could not be previewed"}), 400
    has_more = len(rows) > limit
    return jsonify({"columns": columns, "rows": rows[:limit], "offset": offset, "limit": limit, "has_more": has_more})


@app.route("/compute/api/results/<md5sum>/archive", methods=["POST"])
@login_required
def request_results_archive(md5sum: str):
    if _blocked := require_bearer_auth():
        return _blocked
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"error": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    if not _task_full_results_allowed(task):
        return _task_access_denied(md5sum)
    if task["status"] not in {"finished", "failed"}:
        return jsonify({"error": "Results are not ready"}), 409
    if os.path.isfile(_task_zip_path(task)):
        return jsonify({"status": "ready", "download_url": f"/compute/api/download/{md5sum}"}), 200
    async_result = build_results_archive.apply_async(args=[md5sum])
    return jsonify({"status": "building", "job_id": async_result.id, "md5sum": md5sum}), 202


@app.route("/compute/api/download/<md5sum>", methods=["GET"])
@login_required
def download_results(md5sum):
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_full_results_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] not in {"finished", "failed"}:
        return (
            jsonify(
                {
                    "status": "error",
                    "md5sum": md5sum,
                    "message": "results are not ready",
                }
            ),
            400,
        )

    zip_filename = _task_zip_path(task)
    if not os.path.exists(zip_filename):
        return (
            jsonify(
                {
                    "status": "not_requested",
                    "md5sum": md5sum,
                    "message": "Request the optional archive first",
                    "request_url": f"/compute/api/results/{md5sum}/archive",
                }
            ),
            409,
        )

    if app.config["RESULT_DOWNLOAD_MODE"] == "nginx":
        archive_name = os.path.relpath(zip_filename, app.config["RESULTS_FOLDER"]).replace(os.sep, "/")
        response = Response(status=200, mimetype="application/zip")
        response.headers["X-Accel-Redirect"] = f"/_protected_results/{archive_name}"
        response.headers.set("Content-Disposition", "attachment", filename=_task_zip_download_name(task))
        response.headers["Cache-Control"] = "private, no-store"
        return response

    return send_from_directory(
        os.path.dirname(zip_filename),
        os.path.basename(zip_filename),
        as_attachment=True,
        download_name=_task_zip_download_name(task),
    )


@app.route("/compute/api/cancel/<md5sum>", methods=["POST"])
@login_required
def cancel_task(md5sum):
    if _blocked := require_bearer_auth():
        return _blocked
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not _task_mutation_allowed(task):
        return _task_access_denied(md5sum)

    if task["status"] not in {"pending", "queued", "running"}:
        return (
            jsonify({"error": "Task cannot be cancelled as it is not pending or running"}),
            400,
        )

    now = time.time()
    started_at = task.get("started_at")
    walltime = (now - started_at) if started_at else None
    if not task_store.claim_task_cancellation(
        md5sum,
        finished_at=now,
        walltime=walltime,
        error="Task cancelled by user",
    ):
        return jsonify({"error": "Task state changed before cancellation"}), 409
    task = task_store.get_task(md5sum) or task

    # Claim cancellation in the database before asking the worker to stop
    # resources, so a workflow cannot launch its next stage in between.
    cancel_compute_resources.delay(
        slurm_job_id=str(task["slurm_job_id"]) if task.get("slurm_job_id") else None,
        container_id=str(task["container_id"]) if task.get("container_id") else None,
    )

    celery_id = task.get("celery_task_id")
    if celery_id:
        try:
            result = AsyncResult(celery_id)
            result.revoke(terminate=True)
        except Exception as exc:  # pylint: disable=broad-except
            logging.warning("Failed to revoke Celery task %s: %s", celery_id, exc)

    _delete_task_artifacts(task)
    return jsonify({"status": "cancelled", "md5sum": md5sum}), 200


# ponytail: bounded per-task read for the dashboard — a full file read per
# task turns N listed tasks into N x 16 MiB page loads. The full snapshot
# lives on the task's own results page.
_DASHBOARD_SEQUENCE_PREVIEW_BYTES = 4096


def _dashboard_task_status(task: dict[str, Any], index: int, current_user: str, is_admin: bool) -> dict[str, Any]:
    submitted_time = task.get("uploaded_at")
    finished_time = task.get("finished_at")
    task_type_name = task.get("task_type", "gremlin")
    structure_input = False
    structure_format = "pdb"
    try:
        tt_obj, _ = _get_task_type(task_type_name)
    except KeyError:
        tt_obj = None
    if tt_obj is not None:
        extensions = set(tt_obj.input_extensions or (tt_obj.input_extension,))
        filename_lower = str(task.get("filename") or "").lower()
        if extensions & {".pdb", ".cif", ".mmcif"} and filename_lower.endswith((".pdb", ".cif", ".mmcif")):
            structure_input = True
            # The parser depends on the UPLOADED file, not on the type's
            # accepted extensions — a type accepting both PDB and mmCIF
            # receives .pdb files too.
            structure_format = "mmcif" if filename_lower.endswith((".cif", ".mmcif")) else "pdb"
    sequence_truncated = False
    if structure_input:
        # Structure tasks render a py2Dmol snapshot instead of sequence text;
        # skip the per-task file read entirely.
        fasta_seq = ""
    elif task.get("is_binary"):
        fasta_seq = "Binary file rejected"
    else:
        try:
            with open(task["file_path"]) as handle:
                fasta_seq = handle.read(_DASHBOARD_SEQUENCE_PREVIEW_BYTES).strip()
                sequence_truncated = handle.read(1) != ""
        except (OSError, UnicodeDecodeError) as exc:
            reason = "file not found" if isinstance(exc, FileNotFoundError) else "file unavailable"
            fasta_seq = (
                f"Unable to read sequence: {reason} at "
                f"{_virtual_upload_path(task.get('filename', 'unknown.fasta'))}"
            )

    return {
        "id": index,
        "md5": task["md5sum"],
        "status": task["status"],
        "fasta_fn": task["filename"],
        "submitted_time": format_times(submitted_time),
        "finished_time": format_times(finished_time) if finished_time else "-",
        "walltime": format_walltime(task.get("walltime")),
        "submitted_timestamp": submitted_time or 0,
        "sequence": fasta_seq,
        "sequence_truncated": sequence_truncated,
        "structure_input": structure_input,
        "structure_format": structure_format,
        "input_url": f"/compute/api/tasks/{task['md5sum']}/input" if structure_input else None,
        "owner": task.get("username") or "-",
        "can_delete": _task_mutation_allowed(task) and task["status"] not in task_store.CLEANUP_CLAIM_STATUSES,
        "task_type": task.get("task_type", "gremlin"),
        "running_trace": _build_running_trace(task),
        "error": _sanitize_task_error(task, task.get("error")),
    }


@app.route("/compute/dashboard", methods=["GET"])
@login_required
def task_dashboard():  # skipcq: PY-R1000 -- dashboard filtering and response assembly share request state.
    current_user = _current_username() or ""
    is_admin = _is_admin_user()
    all_tasks = task_store.list_tasks()
    if is_admin:
        scoped_tasks = all_tasks
    else:
        user_id = int(g.current_user["id"])
        store = current_app.config["collaboration"]
        scoped_tasks = [
            task
            for task in all_tasks
            if (
                task.get("scope_type") == "project"
                and task.get("scope_id")
                and store.get_membership(int(task["scope_id"]), user_id)
            )
            or (
                task.get("scope_type") != "project"
                and (
                    str(task.get("scope_id") or "") == str(user_id)
                    or (not task.get("scope_id") and task.get("username") == current_user)
                )
            )
        ]
    visible_tasks = [task for task in scoped_tasks if not _is_deleted_status(task.get("status"))]
    task_statuses = [
        _dashboard_task_status(task, index, current_user, is_admin) for index, task in enumerate(visible_tasks)
    ]
    sorted_task_statuses = sorted(task_statuses, key=lambda x: x["submitted_timestamp"], reverse=True)

    return render_template(
        "dashboard.html",
        sorted_task_statuses=sorted_task_statuses,
        current_username=current_user,
        is_admin_user=is_admin,
    )


@app.route("/compute/results/<md5sum>", methods=["GET"])
@login_required
def task_results_page(md5sum):
    """Render the dedicated manifest-first result workspace for one task."""
    normalized = _normalize_task_id(md5sum)
    if normalized is None:
        abort(404)
    task = task_store.get_task(normalized)
    if task is None:
        abort(404)
    if not _task_full_results_allowed(task):
        return _task_access_denied(normalized)
    response = make_response(
        render_template(
            "task_results.html",
            task=_dashboard_task_status(task, 0, _current_username() or "", _is_admin_user()),
        )
    )
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/compute/api/tasks/<md5sum>/input", methods=["GET"])
@login_required
def task_input_file(md5sum):
    """Stream a task's uploaded input file (dashboard structure previews).

    The path comes from the server-owned task row, not from the request;
    access is restricted to the task owner (or an admin).
    """
    normalized = _normalize_task_id(md5sum)
    if normalized is None:
        abort(404)
    task = task_store.get_task(normalized)
    if task is None:
        abort(404)
    if not _task_access_allowed(task):
        return _task_access_denied(normalized)
    file_path = str(task.get("file_path") or "")
    if not file_path or not os.path.isfile(file_path):
        return jsonify({"error": "Input file not found"}), 404
    # The row is server-written, but containment is cheap insurance: serve
    # only files that live inside one of the server-owned folders.
    if not (
        _path_is_within(app.config["UPLOAD_FOLDER"], file_path)
        or _path_is_within(app.config["WORKSPACE_FOLDER"], file_path)
        or _path_is_within(app.config["RESULTS_FOLDER"], file_path)
    ):
        return jsonify({"error": "Input file not found"}), 404
    return send_from_directory(
        os.path.dirname(file_path) or ".",
        os.path.basename(file_path),
        mimetype=mimetypes.guess_type(task.get("filename") or "")[0] or "application/octet-stream",
        conditional=True,
    )


def _soft_delete_task(md5sum: str, task: dict[str, Any]) -> None:
    if task["status"] in {"pending", "queued", "running"}:
        _revoke_celery_task(task)

    _delete_task_artifacts(task)
    now = time.time()
    deleted_status = _deleted_status_from_task(task)
    started_at = task.get("started_at")
    walltime = task.get("walltime")
    if walltime is None and started_at:
        walltime = now - started_at
    finished_at = task.get("finished_at")
    if deleted_status == "deleted:cancel" or not finished_at:
        finished_at = now
    task_store.update_task(
        md5sum,
        status=deleted_status,
        finished_at=finished_at,
        walltime=walltime,
        error="Task deleted by user",
        celery_task_id=None,
    )


@app.route("/compute/api/delete/<md5sum>", methods=["DELETE"])
@login_required
def delete_task(md5sum):
    if _blocked := require_bearer_auth():
        return _blocked
    if _blocked := _reject_guest():
        return _blocked
    md5sum = _normalize_task_id(md5sum)
    if md5sum is None:
        return jsonify({"status": "bad_request", "message": "Invalid task id"}), 400
    task = task_store.get_task(md5sum)
    if not task:
        return jsonify({"status": "not_found", "md5sum": md5sum}), 404
    if not _task_mutation_allowed(task):
        return _task_access_denied(md5sum)
    if task["status"] in task_store.CLEANUP_CLAIM_STATUSES:
        return jsonify({"error": "Task cleanup is already in progress", "md5sum": md5sum}), 409

    _soft_delete_task(md5sum, task)
    return jsonify({"status": "deleted", "md5sum": md5sum}), 200


@app.route("/compute/api/delete", methods=["POST"])
@login_required
def delete_tasks_batch():  # skipcq: PY-R1000 -- per-task authorization and outcome accounting are intentionally atomic.
    if _blocked := require_bearer_auth():
        return _blocked
    if _blocked := _reject_guest():
        return _blocked
    payload = request.get_json(silent=True) or {}
    md5sums = payload.get("md5sums")
    if not isinstance(md5sums, list):
        return jsonify({"error": "md5sums must be a JSON list"}), 400

    deleted: list[str] = []
    not_found: list[str] = []
    ignored: list[str] = []
    forbidden: list[str] = []
    seen: set[str] = set()

    for raw_md5 in md5sums:
        raw_md5_text = str(raw_md5).strip()
        md5sum = _normalize_task_id(raw_md5_text)
        if md5sum is None:
            if raw_md5_text:
                ignored.append(raw_md5_text)
            continue
        if md5sum in seen:
            continue
        seen.add(md5sum)

        task = task_store.get_task(md5sum)
        if not task:
            not_found.append(md5sum)
            continue
        if not _task_mutation_allowed(task):
            forbidden.append(md5sum)
            continue
        if task["status"] in task_store.CLEANUP_CLAIM_STATUSES:
            ignored.append(md5sum)
            continue

        _soft_delete_task(md5sum, task)
        deleted.append(md5sum)

    return (
        jsonify(
            {
                "status": "ok",
                "deleted": deleted,
                "not_found": not_found,
                "ignored": ignored,
                "forbidden": forbidden,
            }
        ),
        200,
    )


# ---------------------------------------------------------------------------
# Auth API routes
# ---------------------------------------------------------------------------


def _email_configured() -> bool:
    """Return True if email sending is configured (Resend or SMTP)."""
    return bool(_env_str("RESEND_API_KEY", "") or _env_str("SMTP_HOST", ""))


def _allowed_email_domains() -> set[str]:
    """Return the set of allowed email domains from ``ALLOWED_EMAIL_DOMAINS``.

    Empty set means all domains are allowed.
    """
    raw = _env_str("ALLOWED_EMAIL_DOMAINS", "")
    if not raw.strip():
        return set()
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _get_user_db() -> UserDatabase:
    return current_app.config["user_db"]  # type: ignore[no-any-return]


def require_admin():
    """Return 403 unless the current user has the canonical admin role."""
    if _blocked := require_web_login():
        return _blocked
    if g.current_user.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    return None


_ADMIN_LOG_FILES = {
    "gunicorn-access": "gunicorn-access.log",
    "gunicorn-error": "gunicorn-error.log",
    "celery-worker": "celery-worker.log",
    "maintenance": "maintenance.log",
}
_ADMIN_LOG_ARCHIVE_PATTERN = re.compile(
    rf"(?:{'|'.join(re.escape(name) for name in _ADMIN_LOG_FILES.values())})" r"\.\d{8}T\d{12}Z\.zip"
)


def _admin_log_archive_path(archive_name: str) -> Path | None:
    """Resolve one managed rotated-log ZIP without allowing arbitrary paths."""
    if _ADMIN_LOG_ARCHIVE_PATTERN.fullmatch(archive_name) is None:
        return None
    log_dir = os.environ.get("LOG_DIR", "").strip()
    if not log_dir:
        return None
    archive_path = Path(log_dir).resolve() / archive_name
    if archive_path.is_symlink() or not archive_path.is_file():
        return None
    return archive_path


@app.route("/compute/api/auth/admin/logs/archives", methods=["GET"])
@login_required
def admin_log_archives():
    """List managed rotated-log ZIPs grouped by active log."""
    if _blocked := require_admin():
        return _blocked
    log_dir = os.environ.get("LOG_DIR", "").strip()
    if not log_dir:
        return jsonify({"error": "LOG_DIR is not configured"}), 503

    directory = Path(log_dir).resolve()
    groups = []
    for log_name, filename in _ADMIN_LOG_FILES.items():
        archives = []
        for archive in directory.glob(f"{filename}.*.zip"):
            if (
                _ADMIN_LOG_ARCHIVE_PATTERN.fullmatch(archive.name) is None
                or archive.is_symlink()
                or not archive.is_file()
            ):
                continue
            try:
                stat = archive.stat()
            except OSError:
                continue
            archives.append(
                {
                    "filename": archive.name,
                    "size": stat.st_size,
                    "modified_at": stat.st_mtime,
                }
            )
        archives.sort(key=lambda item: (item["modified_at"], item["filename"]), reverse=True)
        groups.append(
            {
                "id": log_name,
                "filename": filename,
                "archives": archives,
            }
        )
    return jsonify({"logs": groups})


@app.route(
    "/compute/api/auth/admin/logs/archives/<archive_name>",
    methods=["GET"],
)
@login_required
def admin_download_log_archive(archive_name: str):
    """Download one managed rotated-log ZIP."""
    if _blocked := require_admin():
        return _blocked
    archive_path = _admin_log_archive_path(archive_name)
    if archive_path is None:
        return jsonify({"error": "Log archive is not available"}), 404
    response = send_from_directory(
        archive_path.parent,
        archive_path.name,
        as_attachment=True,
        download_name=archive_path.name,
        mimetype="application/zip",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/compute/api/auth/admin/logs/<log_name>", methods=["GET"])
@login_required
def admin_stream_log(log_name: str):
    """Stream one fixed, unrotated server log to an administrator."""
    if _blocked := require_admin():
        return _blocked
    filename = _ADMIN_LOG_FILES.get(log_name)
    if filename is None:
        return jsonify({"error": "Unknown log"}), 404

    log_dir = os.environ.get("LOG_DIR", "").strip()
    if not log_dir:
        return jsonify({"error": "LOG_DIR is not configured"}), 503
    log_path = Path(log_dir).resolve() / filename
    if log_path.is_symlink() or not log_path.is_file():
        return jsonify({"error": "Log is not available"}), 404
    try:
        handle = log_path.open("rb")
    except OSError:
        return jsonify({"error": "Log is not available"}), 404

    def stream():
        with handle:
            while chunk := handle.read(64 * 1024):
                yield chunk

    return Response(
        stream(),
        mimetype="text/plain",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Accel-Buffering": "no",
        },
    )


def _reject_guest():
    """Return 403 if the current user is a guest account."""
    if g.current_user.get("role") == "guest":
        return jsonify({"error": "Guest accounts cannot perform this action"}), 403
    return None


def _parse_body(model_cls: type):
    """Validate request JSON against *model_cls*.  Returns the model instance
    or a ``(json_response, status_code)`` error tuple."""
    try:
        return model_cls.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return jsonify({"error": e.errors()[0]["msg"]}), 400


@app.route("/compute/api/auth/login", methods=["POST"])
@rate_limit(max_requests=5, window_seconds=60)
def auth_login():
    """Exchange username+password for a Bearer token.

    Accepts a ``username`` field that may be either a username or an email
    address — admin-created users may only know their email.
    """
    req = _parse_body(LoginRequest)
    if isinstance(req, tuple):
        return req

    db = _get_user_db()
    if "@" in req.login_id:
        user = db.get_user_by_email(req.login_id)  # already normalised by schema
    else:
        user = db.get_user_by_username(req.login_id)
    # Constant-time: always run check_password_hash so response latency does
    # not reveal whether the username exists (timing side-channel defence).
    pwd_ok = check_password_hash(
        user["password_hash"] if user is not None else _DUMMY_PASSWORD_HASH,
        req.password,
    )
    if user is None or not pwd_ok:
        return jsonify({"error": "Invalid username or password"}), 401

    if blocked := _is_account_blocked(user):
        return jsonify({"error": blocked}), 403

    token = generate_token(user["id"], user.get("token_version", 0))
    response = jsonify({"token": token, "username": user["username"]})
    response.set_cookie(
        "auth_token",
        token,
        path="/",
        httponly=True,
        samesite="Lax",
        secure=request.is_secure or current_app.config.get("AUTH_COOKIE_SECURE", False),
    )
    return response


@app.route("/compute/api/auth/forgot-password", methods=["POST"])
@rate_limit(max_requests=3, window_seconds=3600)
def auth_forgot_password():
    """Send a password-reset link to the given email address."""
    if not _email_configured():
        return jsonify({"error": "Password reset requires email service to be configured"}), 503

    req = _parse_body(ForgotPasswordRequest)
    if isinstance(req, tuple):
        return req
    email = req.email

    if not email or "@" not in email:
        # Don't leak whether the email is registered
        return jsonify({"message": "If that email is registered, a reset link has been sent."}), 200

    db = _get_user_db()
    send_password_reset_email(email, db)
    return jsonify({"message": "If that email is registered, a reset link has been sent."}), 200


@app.route("/compute/reset_password", methods=["GET"])
def auth_reset_password_page():
    """Render the password-reset page for a valid reset token."""
    token = request.args.get("c", "").strip()
    if not token:
        return render_template("error.html", code=400, message="Missing reset token."), 400
    user_id = validate_reset_token(token, _get_user_db())
    if user_id is None:
        return render_template("error.html", code=400, message="Invalid or expired reset token."), 400
    return render_template("reset-password.html", token=token), 200


@app.route("/compute/reset_password", methods=["POST"])
def auth_reset_password():
    """Set a new password using a password-reset token."""
    req = _parse_body(ResetPasswordRequest)
    if isinstance(req, tuple):
        return req

    db = _get_user_db()
    user_id = validate_reset_token(req.token, db)
    if user_id is None:
        return jsonify({"error": "Invalid or expired reset token"}), 400

    db.update_user(user_id, password_hash=generate_password_hash(req.password))
    db.increment_token_version(user_id)
    logging.info("User %d reset their password", user_id)
    return jsonify({"message": "Password updated — you can now log in."}), 200


@app.route("/compute/api/auth/logout", methods=["POST"])
@optional_user
def auth_logout():
    """Clear the auth cookie and invalidate all tokens for the current user.
    Bearer token required for the token-version bump; cookie-only requests
    only clear the cookie without invalidating tokens (CSRF-safe).
    """
    user = g.get("current_user")
    if user is not None:
        if result := require_bearer_auth():
            return result
        db = _get_user_db()
        db.increment_token_version(user["id"])
    response = jsonify({"status": "logged_out"})
    response.set_cookie(
        "auth_token",
        "",
        max_age=0,
        path="/",
        httponly=True,
        samesite="Lax",
        secure=request.is_secure or current_app.config.get("AUTH_COOKIE_SECURE", False),
    )
    return response


@app.route("/compute/api/auth/captcha", methods=["GET"])
def auth_captcha():
    """Return a math CAPTCHA challenge with a signed token (5-min expiry)."""
    question, token = generate_captcha()
    return jsonify({"question": question, "token": token}), 200


@app.route("/compute/api/auth/register", methods=["POST"])
@rate_limit(max_requests=3, window_seconds=3600)
def auth_register():
    """Register a new user account.

    Requires ``ENABLE_REGISTER=true`` AND a configured email service (Resend).
    """
    if not ENABLE_REGISTER:
        return jsonify({"error": "Registration is disabled on this server"}), 403
    if not _email_configured():
        return jsonify({"error": "Registration requires email service to be configured"}), 403

    req = _parse_body(RegisterRequest)
    if isinstance(req, tuple):
        return req

    # CAPTCHA — block bot / programmatic registration
    if not validate_captcha(req.captcha_token, req.captcha_answer):
        return jsonify({"error": "CAPTCHA validation failed. Please try again."}), 400

    # Domain allowlist
    allowed = _allowed_email_domains()
    if allowed:
        domain = req.email.partition("@")[2]
        if domain not in allowed:
            return jsonify({"error": f"Email domain @{domain} is not allowed"}), 400

    db = _get_user_db()
    if db.get_user_by_username(req.username):
        return jsonify({"error": "Username already taken"}), 409
    if db.get_user_by_email(req.email):
        return jsonify({"error": "Email address already registered"}), 409

    try:
        user = db.create_user(
            username=req.username,
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            affiliation=req.affiliation,
            position=req.position,
            pi_name=req.pi_name,
            terms_agreed=req.terms_agreed,
            registration_ip=_client_ip(),
            registration_country=_client_country(),
        )
    except IntegrityError:
        return jsonify({"error": "Username or email already registered"}), 409

    sent = send_verification_email(user)
    if not sent:
        logging.warning("Email verification failed for %r; account created but not verified", req.username)

    if sent:
        message = "Registration successful — check your email to verify your account."
    else:
        message = (
            "Account created, but the verification email could not be sent. "
            + "Contact an administrator to verify your account."
        )

    return jsonify({"message": message, "username": req.username, "email_sent": sent}), 201


@app.route("/compute/api/auth/resend-verification", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=3600)
def auth_resend_verification():
    """Resend the verification email for an unverified account.

    Per-email backoff: first resend is immediate, then 10×n minutes where
    *n* is the number of previous resends.
    """
    req = _parse_body(ForgotPasswordRequest)
    if isinstance(req, tuple):
        return req

    email = req.email
    if not email or "@" not in email:
        return (
            jsonify({"message": "If that email is registered and unverified, a new verification email has been sent."}),
            200,
        )

    db = _get_user_db()
    user = db.get_user_by_email(email)

    # Return a generic response for all non-actionable cases to prevent
    # account enumeration (unknown, deleted, banned, already verified).
    _generic = (
        jsonify({"message": "If that email is registered and unverified, a new verification email has been sent."}),
        200,
    )
    if user is None:
        return _generic
    if user.get("deleted") or user.get("user_status") == "banned":
        return _generic
    if user.get("email_verified"):
        return _generic

    # Per-email backoff: 10×n minutes since last resend
    count = user.get("verification_resend_count") or 0
    last_at = user.get("verification_resend_at")
    if last_at and count > 0:
        cooldown = 10 * 60 * count  # seconds
        elapsed = time.time() - last_at
        if elapsed < cooldown:
            remaining = int((cooldown - elapsed) / 60) + 1
            return jsonify({"error": f"Please wait {remaining} min before requesting another verification email"}), 429

    sent = send_verification_email(user)
    if not sent:
        return jsonify({"error": "Failed to send verification email. Contact an administrator."}), 500

    db.update_user(user["id"], verification_resend_count=count + 1, verification_resend_at=time.time())
    return jsonify({"message": "Verification email sent. Check your inbox."}), 200


@app.route("/compute/user_verify", methods=["GET"])
def auth_user_verify():
    """Verify email via serializer token (2-day expiry)."""
    token = request.args.get("c", "").strip()
    if not token:
        return render_template("verify-email.html", success=False, error="Missing verification token."), 400

    user_id = validate_email_token(token)
    if user_id is None:
        return (
            render_template(
                "verify-email.html",
                success=False,
                error="Invalid or expired verification token (valid for 2 days).",
            ),
            400,
        )

    db = _get_user_db()
    user = db.get_user(user_id)
    if user is None:
        return render_template("verify-email.html", success=False, error="User not found."), 404

    db.verify_email(user_id)
    db.update_user(user_id, registration_status="verified")
    # user_status stays "pending" — admin must approve
    return (
        render_template(
            "verify-email.html",
            success=True,
            email=user["email"],
            registration_pending=user.get("user_status") != "active",
        ),
        200,
    )


@app.route("/compute/api/auth/me", methods=["GET"])
@login_required
def auth_me():
    """Return the current authenticated user's profile."""
    user = g.current_user
    return (
        jsonify(
            {
                "username": user["username"],
                "email": user["email"],
                "email_verified": user["email_verified"],
                "role": user.get("role", "user"),
                "full_name": user.get("full_name"),
                "affiliation": user.get("affiliation"),
                "position": user.get("position"),
                "pi_name": user.get("pi_name"),
            }
        ),
        200,
    )


@app.route("/compute/api/auth/me", methods=["PUT"])
@login_required
def auth_update_me():
    """Change the current user's password."""
    if _blocked := require_web_login():
        return _blocked
    if _blocked := _reject_guest():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked
    user = g.current_user
    req = _parse_body(ChangePasswordRequest)
    if isinstance(req, tuple):
        return req

    if not check_password_hash(user["password_hash"], req.current_password):
        return jsonify({"error": "Current password is incorrect"}), 401

    db = _get_user_db()
    db.update_user(user["id"], password_hash=generate_password_hash(req.new_password))
    db.increment_token_version(user["id"])
    return jsonify({"message": "Password updated"}), 200


# ---------------------------------------------------------------------------
# Token refresh — cookie-authenticated endpoint that returns a fresh Bearer
# token so pages loaded via cookie navigation can perform state-changing
# operations that require Bearer auth (CSRF protection).
# ---------------------------------------------------------------------------


@app.route("/compute/api/auth/token", methods=["GET"])
@login_required
def auth_get_token():
    """Return a fresh Bearer token (cookie or Bearer auth accepted)."""
    user = g.current_user
    token = generate_token(user["id"], user.get("token_version", 0))
    return jsonify({"token": token}), 200


# ---------------------------------------------------------------------------
# API key management (long-lived, user-revokable)
# ---------------------------------------------------------------------------


@app.route("/compute/api/auth/me/api-key", methods=["GET"])
@login_required
def auth_api_key_status():
    """Return whether the current user has an active API key."""
    if _blocked := require_web_login():
        return _blocked
    db = _get_user_db()
    user = db.get_user(g.current_user["id"])
    has_key = bool(user and user.get("api_key_digest"))
    return jsonify({"has_api_key": has_key}), 200


@app.route("/compute/api/auth/me/api-key", methods=["POST"])
@login_required
def auth_generate_api_key():
    """Generate a new API key — returns the plaintext key once."""
    if _blocked := require_web_login():
        return _blocked
    if _blocked := _reject_guest():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked
    db = _get_user_db()
    plaintext = db.generate_api_key(g.current_user["id"])
    return jsonify({"api_key": plaintext, "message": "Store this key securely — it will not be shown again."}), 201


@app.route("/compute/api/auth/me/api-key", methods=["DELETE"])
@login_required
def auth_revoke_api_key():
    """Revoke the current user's API key."""
    if _blocked := require_web_login():
        return _blocked
    if _blocked := _reject_guest():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked
    db = _get_user_db()
    db.revoke_api_key(g.current_user["id"])
    return jsonify({"message": "API key revoked"}), 200


@app.route("/compute/api/auth/admin/users", methods=["GET"])
@login_required
def admin_users():
    """Admin-only user listing with safe fields only."""
    if _blocked := require_admin():
        return _blocked

    db = _get_user_db()
    users = db.list_users()
    safe = [UserResponse.model_validate(u).model_dump() for u in users]
    return jsonify({"users": safe}), 200


@app.route("/compute/api/auth/admin/users", methods=["POST"])
@login_required
def admin_create_user():
    """Admin-only user creation for pre-approved accounts."""
    if _blocked := require_admin():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked

    db = _get_user_db()
    req = _parse_body(AdminCreateUserRequest)
    if isinstance(req, tuple):
        return req

    if db.get_user_by_username(req.username):
        return jsonify({"error": "Username already taken"}), 409
    if db.get_user_by_email(req.email):
        return jsonify({"error": "Email address already registered"}), 409

    new_user = db.create_user(
        username=req.username,
        email=req.email,
        password=req.password,
        role=req.role,
        full_name=req.full_name,
        affiliation=req.affiliation,
        position=req.position,
        pi_name=req.pi_name,
        registration_status="approved",
        user_status="active",
    )
    db.verify_email(new_user["id"])  # admin-created accounts are pre-verified

    logging.info("Admin %r created user %r", g.current_user["username"], req.username)
    return jsonify({"message": "User created", "username": req.username}), 201


def _admin_email_update(db: UserDatabase, user_id: int, email: str | None):
    if email is None:
        return {}, None
    existing = db.get_user_by_email(email)
    if existing and existing["id"] != user_id:
        return None, (jsonify({"error": "Email address already in use"}), 409)
    return {"email": email}, None


def _admin_profile_update_fields(req: AdminUpdateUserRequest) -> dict[str, Any]:
    update_fields = {
        field: value
        for field in ("affiliation", "full_name", "pi_name", "user_status")
        if (value := getattr(req, field)) is not None
    }
    if "position" in req.model_fields_set:
        update_fields["position"] = req.position
    if req.password is not None:
        update_fields["password_hash"] = generate_password_hash(req.password)
    return update_fields


def _admin_registration_update_fields(
    db: UserDatabase,
    user_id: int,
    user: dict[str, Any],
    registration_status: str | None,
) -> dict[str, Any]:
    update_fields: dict[str, Any] = {}
    if registration_status is None:
        return update_fields
    update_fields["registration_status"] = registration_status
    # Admin approval implies email verification — avoid the gap where
    # an unverified self-registered account becomes active without
    # proving email ownership.
    if registration_status == "approved":
        if not user.get("email_verified"):
            db.verify_email(user_id)
        update_fields["approved_by"] = g.current_user["id"]
        update_fields["approved_at"] = time.time()
    return update_fields


def _admin_user_update_fields(
    db: UserDatabase,
    user_id: int,
    user: dict[str, Any],
    is_self: bool,
    req: AdminUpdateUserRequest,
):
    """Build validated fields for an admin user update."""
    update_fields, update_error = _admin_email_update(db, user_id, req.email)
    if update_error is not None:
        return None, update_error
    if is_self and req.user_status == "banned":
        return None, (jsonify({"error": "Administrators cannot ban their own account"}), 400)
    update_fields.update(_admin_profile_update_fields(req))
    update_fields.update(_admin_registration_update_fields(db, user_id, user, req.registration_status))
    if req.role is not None:
        if is_self and req.role != user.get("role"):
            return None, (jsonify({"error": "Administrators cannot change their own role"}), 400)
        if not is_self:
            update_fields["role"] = req.role
    if req.allow_gpu_use is not None:
        update_fields["allow_gpu_use"] = req.allow_gpu_use
    return update_fields, None


def _notify_admin_user_update(
    db: UserDatabase,
    user_id: int,
    user: dict[str, Any],
    registration_status: str | None,
) -> None:
    if registration_status == "approved":
        approved_user = db.get_user(user_id) or user
        if not send_approval_email(approved_user):
            logging.warning("Approval email failed for %r", user_id)
    elif registration_status == "rejected" and not send_rejection_email(user):
        logging.warning("Rejection email failed for %r", user_id)


@app.route("/compute/api/auth/admin/users/<int:user_id>", methods=["PUT", "DELETE"])
@login_required
def admin_manage_user(user_id):  # skipcq: PY-R1000 -- admin state transitions are kept in one audited transaction.
    """Admin-only: update or soft-delete a user."""
    if _blocked := require_admin():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked

    db = _get_user_db()
    user = db.get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    is_self = user_id == g.current_user["id"]

    if request.method == "DELETE":
        if is_self:
            return jsonify({"error": "Administrators cannot delete their own account"}), 400
        # ponytail: soft-delete — hides from user table, recoverable.
        db.update_user(user_id, deleted=True)
        logging.info("Admin %r soft-deleted user %r", g.current_user["username"], user.get("username"))
        return jsonify({"message": "User deleted"}), 200

    req = _parse_body(AdminUpdateUserRequest)
    if isinstance(req, tuple):
        return req
    update_fields, update_error = _admin_user_update_fields(db, user_id, user, is_self, req)
    if update_error is not None:
        return update_error

    if update_fields:
        db.update_user(user_id, **update_fields)
        _notify_admin_user_update(db, user_id, user, update_fields.get("registration_status"))

    return jsonify({"message": "User updated"}), 200


@app.route("/compute/api/auth/admin/users/batch", methods=["POST"])
@login_required
def admin_batch_users():
    """Admin-only batch operations on users.

    Accepts ``{"action": "enable"|"disable"|"delete", "user_ids": [...]}``.
    """
    if _blocked := require_admin():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked

    req = _parse_body(BatchUserRequest)
    if isinstance(req, tuple):
        return req

    db = _get_user_db()
    now = time.time()
    admin_id = g.current_user["id"]

    if req.action == "enable":
        updates = {
            "user_status": "active",
            "registration_status": "approved",
            "email_verified": True,
            "deleted": False,
            "approved_by": admin_id,
            "approved_at": now,
        }
    elif req.action == "disable":
        updates = {"user_status": "banned", "approved_by": admin_id, "approved_at": now}
    else:  # delete
        updates = {"deleted": True}

    count = 0
    for uid in req.user_ids:
        user = db.get_user(uid)
        if user is None:
            continue
        if uid == admin_id and req.action in {"disable", "delete"}:
            continue  # don't let an admin lock themselves out
        if user.get("role") == "admin" and req.action == "disable":
            continue  # don't disable other admins
        db.update_user(uid, **updates)
        count += 1

    return jsonify({"message": f"{req.action} action applied to {count} user(s)", "count": count}), 200


# ---------------------------------------------------------------------------
# Admin runtime configuration API
# ---------------------------------------------------------------------------


@app.route("/compute/api/auth/admin/config", methods=["GET"])
@login_required
def admin_get_config():
    """Return structured runtime configuration (admin only).

    Response::

        {
          "task_types": [{"tool": "gremlin", "enabled": true, "cpus": null,
            "memory": null, "slurm_partition": null, ...}, ...],
          "resources": {"cpus": "4", "memory": "8G", ...},
          "slurm": {
            "enabled": false,
            "allowed_queues": []
          }
        }
    """
    if _blocked := require_admin():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked
    manage_db = current_app.config.get("manage_db")
    if manage_db is None:
        return jsonify({"error": "Configuration database not available"}), 500
    task_configs = manage_db.task_type_all()
    type_map = {task_type.name: task_type for task_type in list_types()}
    stage_map = {stage.name: (task_type, stage) for task_type in type_map.values() for stage in task_type.workflow}
    for config in task_configs:
        task_type = type_map.get(config["tool"])
        workflow_stage = stage_map.get(config["tool"])
        if task_type is None and workflow_stage is None:
            continue
        stage = workflow_stage[1] if workflow_stage else None
        task_type = task_type or workflow_stage[0]
        config["display_name"] = f"{task_type.display_name} / {stage.display_name}" if stage else task_type.display_name
        config["requires_gpu"] = stage.requires_gpu if stage else task_type.gpus
        config["runtime_family"] = task_type.runtime.name
        config["is_workflow_stage"] = stage is not None
        _, runner = _get_task_type(task_type.name)
        try:
            resolved = manage_db.resolve_task_resources(
                config["tool"],
                requires_gpu=config["requires_gpu"],
                default_timeout_seconds=runner.max_runtime_seconds,
            )
            config["effective_resources"] = resolved.public_dict()
            config["resource_sources"] = resolved.sources
            config["resource_error"] = None
        except ResourceValidationError as exc:
            config["effective_resources"] = None
            config["resource_sources"] = {}
            config["resource_error"] = str(exc)
    stored_resources = manage_db.resource_all()
    return jsonify(
        {
            "task_types": task_configs,
            "resources": {key: value for key, value in stored_resources.items() if key in GLOBAL_RESOURCE_KEYS},
            "ignored_resource_keys": sorted(set(stored_resources) - GLOBAL_RESOURCE_KEYS),
            "slurm": {
                "enabled": manage_db.slurm_enabled(),
                "allowed_queues": manage_db.slurm_allowed_queues(),
            },
        }
    )


@app.route("/compute/api/auth/admin/config", methods=["PUT"])
@login_required
def admin_set_config():
    """Update runtime configuration (admin only).

    Accepts the same shape as GET::

        {
          "task_types": [{"tool": "pythia_ddg", "enabled": false,
            "cpus": 4, "memory": "16G", "slurm_partition": "gpu"}],
          "resources": {"cpus": "8", "memory": "16G", "slurm_enabled": "true"},
          "slurm": {"enabled": true, "allowed_queues": ["gpu", "cpu"]}
        }

    Each key is optional — only provided fields are updated.
    """
    if _blocked := require_admin():
        return _blocked
    if _blocked := require_bearer_auth():
        return _blocked
    manage_db = current_app.config.get("manage_db")
    if manage_db is None:
        return jsonify({"error": "Configuration database not available"}), 500

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "Expected a JSON object"}), 400

    _tt_fields = (
        "enabled",
        "cpus",
        "memory",
        "max_runtime_seconds",
        "slurm_partition",
        "slurm_gres",
        "slurm_time",
        "slurm_nodes",
        "slurm_ntasks",
        "slurm_qos",
        "slurm_account",
        "slurm_constraint",
        "slurm_exclusive",
    )

    unknown_sections = set(body) - {"task_types", "resources", "slurm"}
    if unknown_sections:
        return jsonify({"error": f"Unknown configuration sections: {sorted(unknown_sections)}"}), 400

    known_tools = {entry["tool"] for entry in manage_db.task_type_all()}
    type_map = {task_type.name: task_type for task_type in list_types()}
    profile_gpu = {name: task_type.gpus for name, task_type in type_map.items()}
    profile_gpu.update(
        {stage.name: stage.requires_gpu for task_type in type_map.values() for stage in task_type.workflow}
    )
    pending_task_updates: list[tuple[str, dict[str, Any]]] = []
    pending_resources: list[tuple[str, Any]] = []
    seen_tools: set[str] = set()

    try:
        for entry in body.get("task_types") or []:
            if not isinstance(entry, dict):
                raise ResourceValidationError("Each task_types update must be an object")
            tool = entry.get("tool")
            if tool not in known_tools:
                raise ResourceValidationError(f"Unknown task type: {tool!r}")
            if tool in seen_tools:
                raise ResourceValidationError(f"Duplicate task type update: {tool!r}")
            seen_tools.add(tool)
            unknown_fields = set(entry) - {"tool", *_tt_fields}
            if unknown_fields:
                raise ResourceValidationError(f"Unknown resource fields for {tool}: {sorted(unknown_fields)}")
            fields = {field: normalize_resource_value(field, entry[field]) for field in _tt_fields if field in entry}
            if "enabled" in fields and fields["enabled"] is None:
                raise ResourceValidationError("enabled cannot be empty")
            if not profile_gpu.get(tool, False) and fields.get("slurm_gres"):
                raise ResourceValidationError(f"CPU-only task {tool!r} cannot request GPU GRES")
            if fields:
                pending_task_updates.append((tool, fields))

        resources = body.get("resources")
        if resources is not None and not isinstance(resources, dict):
            raise ResourceValidationError("resources must be an object")
        for key, value in (resources or {}).items():
            if key not in GLOBAL_RESOURCE_KEYS:
                raise ResourceValidationError(f"Unknown global resource key: {key}")
            pending_resources.append((key, normalize_resource_value(key, value)))

        slurm = body.get("slurm")
        if slurm is not None and not isinstance(slurm, dict):
            raise ResourceValidationError("slurm must be an object")
        if isinstance(slurm, dict):
            unknown_slurm = set(slurm) - {"enabled", "allowed_queues"}
            if unknown_slurm:
                raise ResourceValidationError(f"Unknown SLURM fields: {sorted(unknown_slurm)}")
            if "enabled" in slurm:
                pending_resources.append(("slurm_enabled", normalize_resource_value("slurm_enabled", slurm["enabled"])))
            if "allowed_queues" in slurm:
                pending_resources.append(
                    (
                        "slurm_allowed_queues",
                        normalize_resource_value("slurm_allowed_queues", slurm["allowed_queues"]),
                    )
                )

        proposed_globals = {key: value for key, value in pending_resources}
        if len(proposed_globals) != len(pending_resources):
            raise ResourceValidationError("A global resource key was provided more than once")
        allowed_queues = proposed_globals.get("slurm_allowed_queues", tuple(manage_db.slurm_allowed_queues()))
        global_partition = proposed_globals.get("slurm_partition", manage_db.resource_get("slurm_partition"))
        if allowed_queues and global_partition and global_partition not in allowed_queues:
            raise ResourceValidationError(f"Global partition {global_partition!r} is not in allowed_queues")
        proposed_tasks = {tool: fields for tool, fields in pending_task_updates}
        for config in manage_db.task_type_all():
            partition = proposed_tasks.get(config["tool"], {}).get("slurm_partition", config.get("slurm_partition"))
            if allowed_queues and partition and partition not in allowed_queues:
                raise ResourceValidationError(
                    f"Partition {partition!r} for {config['tool']!r} is not in allowed_queues"
                )
    except ResourceValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    count = manage_db.apply_resource_updates(pending_task_updates, pending_resources)

    return jsonify({"message": f"{count} setting(s) updated"}), 200
