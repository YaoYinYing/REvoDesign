/* REvoDesign GREMLIN Server — User Control page */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;

  T.initToggle(document.getElementById("themeToggle"));

  // ---- Status label maps ----

  var REG_LABELS = {
    email_sent: "Email Sent",
    verified: "Verified",
    approved: "Approved",
    rejected: "Rejected",
  };
  var USER_LABELS = {
    pending: "Pending",
    active: "Active",
    banned: "Banned",
  };
  var ROLE_LABELS = {
    admin: "Admin",
    user: "User",
    guest: "Guest",
  };

  // ---- Tab switching ----

  var tabs = document.querySelectorAll(".sub-tab");
  var panels = {
    audit: document.getElementById("tab-audit"),
    add: document.getElementById("tab-add"),
  };

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      Object.keys(panels).forEach(function (k) {
        panels[k].style.display = k === tab.dataset.tab ? "block" : "none";
      });
      if (tab.dataset.tab === "audit") loadUsers();
    });
  });

  // ---- Batch bar ----

  var batchBar = document.getElementById("batchBar");
  var batchCount = document.getElementById("batchCount");
  var selectAll = document.getElementById("selectAll");
  var currentUsername = null;

  selectAll.addEventListener("change", function () {
    var checks = document.querySelectorAll(".user-select:not(:disabled)");
    checks.forEach(function (cb) { cb.checked = selectAll.checked; });
    updateBatchBar();
  });

  function updateBatchBar() {
    var checks = document.querySelectorAll(".user-select:checked");
    var count = checks.length;
    batchBar.style.display = count > 0 ? "" : "none";
    batchCount.textContent = count + " selected";
  }

  document.getElementById("batchBar").addEventListener("click", function (e) {
    var btn = e.target.closest(".batch-action");
    if (!btn) return;
    var action = btn.dataset.action;
    var checks = document.querySelectorAll(".user-select:checked");
    var ids = [];
    checks.forEach(function (cb) { ids.push(cb.dataset.uid); });
    if (!ids.length) return;

    var labels = { enable: "Enable", disable: "Disable", delete: "Delete" };
    if (!window.confirm(labels[action] + " " + ids.length + " user(s)?")) return;
    btn.disabled = true;

    A.authFetch("/PSSM_GREMLIN/api/auth/admin/users/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: action, user_ids: ids }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (result) {
        if (result.ok) {
          selectAll.checked = false;
          loadUsers();
        } else {
          alert(result.data.error || "Batch action failed.");
          btn.disabled = false;
        }
      })
      .catch(function () { alert("Network error."); btn.disabled = false; });
  });

  // ---- Load user list (Tab A) ----

  var userTableBody = document.getElementById("userTableBody");
  var COLSPAN = 7;

  function loadCurrentUser() {
    return A.authFetch("/PSSM_GREMLIN/api/auth/me")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        currentUsername = data.username || null;
      });
  }

  function loadUsers() {
    userTableBody.innerHTML = '<tr><td colspan="' + COLSPAN + '" class="empty">Loading&hellip;</td></tr>';
    selectAll.checked = false;
    batchBar.style.display = "none";
    A.authFetch("/PSSM_GREMLIN/api/auth/admin/users")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        userTableBody.innerHTML = "";
        if (!data.users || !data.users.length) {
          userTableBody.innerHTML = '<tr><td colspan="' + COLSPAN + '" class="empty">No users found.</td></tr>';
          return;
        }
        data.users.forEach(function (u) { renderUserRow(u); });
      })
      .catch(function () {
        userTableBody.innerHTML = '<tr><td colspan="' + COLSPAN + '" class="empty error">Failed to load users.</td></tr>';
      });
  }

  function isCurrentUser(u) {
    return currentUsername && u.username === currentUsername;
  }

  function renderUserRow(u) {
    var tr = document.createElement("tr");
    var regLabel = REG_LABELS[u.registration_status] || u.registration_status || "—";
    var userLabel = USER_LABELS[u.user_status] || u.user_status || "—";
    var actionsHtml = buildActionButtons(u);
    var self = isCurrentUser(u);
    var selectAttrs = ' class="user-select" data-uid="' + u.id + '"';
    if (self) selectAttrs += ' disabled title="You cannot batch-disable or delete your own account"';

    tr.innerHTML =
      '<td class="col-select"><input type="checkbox"' + selectAttrs + '></td>' +
      '<td class="col-email">' + escapeHtml(u.email || "—") + '</td>' +
      '<td class="col-ip muted">' + escapeHtml(u.registration_ip || "—") + (u.registration_country ? ' <span class="country-tag">' + escapeHtml(u.registration_country) + '</span>' : '') + '</td>' +
      '<td class="col-affil">' + escapeHtml(u.affiliation || "—") + '</td>' +
      '<td class="col-role"><span class="status-badge ' + escapeAttr(u.role || "user") + '">' + escapeHtml(ROLE_LABELS[u.role] || u.role || "User") + '</span></td>' +
      '<td class="col-reg"><span class="status-badge ' + escapeAttr(u.registration_status) + '">' + escapeHtml(regLabel) + '</span></td>' +
      '<td class="col-user"><span class="status-badge ' + escapeAttr(u.user_status) + '">' + escapeHtml(userLabel) + '</span></td>' +
      '<td class="col-actions">' + actionsHtml + '</td>';
    // Store full user data for inline edit
    tr._userData = u;
    userTableBody.appendChild(tr);

    // ponytail: attach listener per-row so checkbox updates batch bar
    var cb = tr.querySelector(".user-select");
    if (cb) cb.addEventListener("change", updateBatchBar);
  }

  function buildActionButtons(u) {
    var buttons = "";
    var reg = u.registration_status;
    var us = u.user_status;
    var self = isCurrentUser(u);
    // Approve / Reject during registration flow
    if (reg === "email_sent" || reg === "verified") {
      buttons += '<button class="user-action-btn approve" data-id="' + u.id + '" data-action="approve">Approve</button>';
      buttons += '<button class="user-action-btn reject" data-id="' + u.id + '" data-action="reject">Reject</button>';
    }
    // Ban active users
    if (us === "active" && !self) {
      buttons += '<button class="user-action-btn ban" data-id="' + u.id + '" data-action="ban">Ban</button>';
    }
    // Re-enable banned or rejected users
    if (us === "banned" || reg === "rejected") {
      buttons += '<button class="user-action-btn enable" data-id="' + u.id + '" data-action="enable">Enable</button>';
    }
    // Always show Modify
    buttons += '<button class="user-action-btn modify" data-id="' + u.id + '" data-action="modify">Modify</button>';
    return buttons;
  }

  // ---- Action button handler (delegated) ----

  userTableBody.addEventListener("click", function (e) {
    var btn = e.target.closest(".user-action-btn");
    if (!btn) return;
    var userId = btn.dataset.id;
    var action = btn.dataset.action;

    if (action === "modify") {
      var tr = btn.closest("tr");
      showEditRow(tr, tr._userData);
      return;
    }

    var payload = {};
    if (action === "approve") {
      payload = { registration_status: "approved", user_status: "active" };
    } else if (action === "reject") {
      payload = { registration_status: "rejected" };
    } else if (action === "ban") {
      payload = { user_status: "banned" };
    } else if (action === "enable") {
      payload = { user_status: "active", registration_status: "approved" };
    }

    var labels = { approve: "Approve", reject: "Reject", ban: "Ban", enable: "Enable" };
    if (!window.confirm(labels[action] + " this user?")) return;

    btn.disabled = true;
    A.authFetch("/PSSM_GREMLIN/api/auth/admin/users/" + userId, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (result) {
        if (result.ok) { loadUsers(); }
        else { alert(result.data.error || "Action failed."); btn.disabled = false; }
      })
      .catch(function () { alert("Network error."); btn.disabled = false; });
  });

  // ---- Inline edit (Modify button) ----

  function showEditRow(tr, u) {
    var origHTML = tr.innerHTML;
    var self = isCurrentUser(u);
    tr.innerHTML =
      '<td class="col-select">—</td>' +
      '<td><input type="email" class="text-input edit-input" id="editEmail" value="' + escapeHtml(u.email || "") + '"></td>' +
      '<td class="muted">—</td>' +
      '<td><input type="text" class="text-input edit-input" id="editAffiliation" value="' + escapeHtml(u.affiliation || "") + '"></td>' +
      '<td><select class="text-input edit-input" id="editRole">' +
        '<option value="admin"' + ((u.role || "user") === "admin" ? " selected" : "") + (self ? " disabled" : "") + '>Admin</option>' +
        '<option value="user"' + ((u.role || "user") === "user" ? " selected" : "") + '>User</option>' +
        '<option value="guest"' + ((u.role || "user") === "guest" ? " selected" : "") + '>Guest</option>' +
      '</select></td>' +
      '<td><select class="text-input edit-input" id="editRegStatus">' +
        '<option value="approved"' + (u.registration_status === "approved" ? " selected" : "") + '>Approved</option>' +
        '<option value="rejected"' + (u.registration_status === "rejected" ? " selected" : "") + '>Rejected</option>' +
      '</select></td>' +
      '<td><select class="text-input edit-input" id="editUserStatus">' +
        '<option value="active"' + (u.user_status === "active" ? " selected" : "") + '>Active</option>' +
        '<option value="banned"' + (u.user_status === "banned" ? " selected" : "") + (self ? " disabled" : "") + '>Banned</option>' +
      '</select></td>' +
      '<td>' +
        '<button class="user-action-btn approve edit-save" data-id="' + u.id + '">Save</button>' +
        '<button class="user-action-btn reject edit-cancel">Cancel</button>' +
      '</td>';
    // Append password row
    var pwRow = document.createElement("tr");
    pwRow.className = "edit-row";
    pwRow.innerHTML =
      '<td></td>' +
      '<td colspan="2"><input type="password" class="text-input edit-input" id="editPassword" placeholder="New password (leave empty to keep)" minlength="8" autocomplete="new-password"></td>' +
      '<td colspan="5" class="muted" style="font-size:0.76rem">Leave blank to keep current password</td>';
    tr.parentNode.insertBefore(pwRow, tr.nextSibling);

    tr._origHTML = origHTML;
    tr._editPwRow = pwRow;

    // Save handler
    tr.querySelector(".edit-save").addEventListener("click", function () {
      var payload = {
        email: document.getElementById("editEmail").value.trim(),
        affiliation: document.getElementById("editAffiliation").value.trim(),
        role: document.getElementById("editRole").value,
        registration_status: document.getElementById("editRegStatus").value,
        user_status: document.getElementById("editUserStatus").value,
      };
      var pw = document.getElementById("editPassword").value;
      if (pw) payload.password = pw;
      if (self && payload.user_status === "banned") {
        alert("You cannot ban your own account.");
        return;
      }

      A.authFetch("/PSSM_GREMLIN/api/auth/admin/users/" + u.id, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (result) {
          if (result.ok) { loadUsers(); }
          else { alert(result.data.error || "Update failed."); }
        })
        .catch(function () { alert("Network error."); });
    });

    // Cancel handler
    tr.querySelector(".edit-cancel").addEventListener("click", function () {
      cancelEdit(tr);
    });
  }

  function cancelEdit(tr) {
    if (tr._editPwRow) { tr._editPwRow.remove(); tr._editPwRow = null; }
    if (tr._origHTML) { tr.innerHTML = tr._origHTML; tr._origHTML = null; }
    // Re-attach checkbox listener
    var cb = tr.querySelector(".user-select");
    if (cb) cb.addEventListener("change", updateBatchBar);
  }

  // ---- Add user form (Tab B) ----

  var addForm = document.getElementById("addUserForm");
  var addStatus = document.getElementById("addUserStatus");
  var TAB_AUDIT = document.querySelector('.sub-tab[data-tab="audit"]');

  addForm.addEventListener("submit", function (e) {
    e.preventDefault();
    addStatus.className = "status-msg";
    addStatus.textContent = "";

    var payload = {
      username: document.getElementById("newUsername").value.trim(),
      email: document.getElementById("newEmail").value.trim(),
      password: document.getElementById("newPassword").value,
      affiliation: document.getElementById("newAffiliation").value.trim(),
      role: document.getElementById("newRole").value,
    };

    A.authFetch("/PSSM_GREMLIN/api/auth/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (result) {
        if (result.ok) {
          addStatus.className = "status-msg ok";
          addStatus.textContent = "User created — " + result.data.username;
          addForm.reset();
          // Switch to audit tab so admin sees the new user
          if (TAB_AUDIT) TAB_AUDIT.click();
        } else {
          addStatus.className = "status-msg error";
          addStatus.textContent = result.data.error || "Failed to create user.";
        }
      })
      .catch(function () {
        addStatus.className = "status-msg error";
        addStatus.textContent = "Network error.";
      });
  });

  // ---- Logout ----

  document.getElementById("logoutBtn").addEventListener("click", function () {
    A.authFetch("/PSSM_GREMLIN/api/auth/logout", { method: "POST" })
      .then(function () { A.clearToken(); window.location.href = "/PSSM_GREMLIN/login"; })
      .catch(function () { A.clearToken(); window.location.href = "/PSSM_GREMLIN/login"; });
  });

  // ---- Helpers ----

  function escapeHtml(input) {
    if (!input) return "";
    return String(input)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(input) {
    if (!input) return "";
    return String(input).replace(/[^a-zA-Z0-9_-]/g, "");
  }

  // Initial load
  loadCurrentUser()
    .catch(function () { currentUsername = null; })
    .then(loadUsers);
})();
