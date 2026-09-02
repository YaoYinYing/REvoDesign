/* REvoCompute - project overview, tasks, members, and settings */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;
  var pageData = JSON.parse(document.getElementById("project-page-data").textContent);
  var projectId = pageData.project_id;
  var apiRoot = "/compute/api/projects/" + encodeURIComponent(projectId);
  var state = { project: null, capabilities: [], role: null, tasks: null, members: null, invitations: null, users: [] };
  var statusNode = document.getElementById("projectStatus");

  function has(capability) { return state.capabilities.indexOf(capability) !== -1; }
  function setStatus(message, kind) { statusNode.textContent = message || ""; statusNode.className = "project-status" + (kind ? " " + kind : ""); }

  async function request(url, options, publicRead) {
    var response = publicRead ? await fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } }) : await A.authFetch(url, options);
    var payload = (response.headers.get("Content-Type") || "").includes("application/json") ? await response.json() : {};
    if (!response.ok) throw new Error(payload.error || payload.message || "Request failed (HTTP " + response.status + ")");
    return payload;
  }

  function formatDate(value) {
    if (!value) return "";
    var numeric = Number(value), date = Number.isFinite(numeric) ? new Date(numeric < 100000000000 ? numeric * 1000 : numeric) : new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
  }

  function normalizeTask(task) {
    return { id: task.md5 || task.md5sum || task.task_id || task.id, name: task.fasta_fn || task.filename || task.input_name || task.name || task.task_type || "Compute task", type: task.task_type || "task", status: task.status || "pending", date: task.submitted_time || task.uploaded_at || task.created_at };
  }

  function taskRow(task) {
    var normalized = normalizeTask(task), row = document.createElement("a");
    row.className = "project-task-row"; row.href = "/compute/results/" + encodeURIComponent(normalized.id);
    var copy = document.createElement("div"), title = document.createElement("strong"), detail = document.createElement("small");
    title.textContent = normalized.name; detail.textContent = normalized.type + (normalized.date ? " | " + formatDate(normalized.date) : ""); copy.append(title, detail);
    var identifier = document.createElement("small"); identifier.textContent = normalized.id;
    var badge = document.createElement("span"); badge.className = "task-status-badge"; badge.textContent = normalized.status;
    row.append(copy, identifier, badge); return row;
  }

  function renderTaskList(target, tasks, limit) {
    target.replaceChildren(); (limit ? tasks.slice(0, limit) : tasks).forEach(function (task) { target.appendChild(taskRow(task)); });
  }

  async function loadTasks() {
    if (state.tasks) return state.tasks;
    var payload = await request(apiRoot + "/tasks", undefined, true);
    state.tasks = Array.isArray(payload) ? payload : (payload.tasks || []);
    renderTaskList(document.getElementById("projectTaskList"), state.tasks);
    renderTaskList(document.getElementById("recentTaskList"), state.tasks, 5);
    document.getElementById("projectTasksEmpty").hidden = state.tasks.length > 0;
    document.getElementById("projectTaskCount").textContent = String(state.tasks.length);
    return state.tasks;
  }

  function memberRow(member) {
    var row = document.createElement("article"); row.className = "member-row";
    var copy = document.createElement("div"), title = document.createElement("strong"), detail = document.createElement("small");
    title.textContent = member.username || member.display_name || ("User " + member.user_id); detail.textContent = member.role; copy.append(title, detail); row.appendChild(copy);
    if (has("manage_members") && member.role !== "owner") {
      var select = document.createElement("select"); select.className = "member-role-select"; select.setAttribute("aria-label", "Role for " + title.textContent);
      ["viewer", "contributor", "maintainer"].forEach(function (role) { var option = document.createElement("option"); option.value = role; option.textContent = role.charAt(0).toUpperCase() + role.slice(1); option.selected = member.role === role; select.appendChild(option); });
      select.addEventListener("change", function () { updateMemberRole(member, select); }); row.appendChild(select);
      var actions = document.createElement("div"); actions.className = "row-actions";
      if (has("transfer_ownership")) {
        var transfer = document.createElement("button"); transfer.type = "button"; transfer.className = "row-button"; transfer.textContent = "Make owner";
        transfer.addEventListener("click", function () { transferOwnership(member, row); }); actions.appendChild(transfer);
      }
      var remove = document.createElement("button"); remove.type = "button"; remove.className = "row-button danger"; remove.textContent = "Remove";
      remove.addEventListener("click", function () { removeMember(member, row); }); actions.appendChild(remove); row.appendChild(actions);
    } else {
      var badge = document.createElement("span"); badge.className = "project-role-badge"; badge.textContent = member.role; row.appendChild(badge); row.appendChild(document.createElement("span"));
    }
    return row;
  }

  async function loadMembers(force) {
    if (state.members && !force) return state.members;
    var payload = await request(apiRoot + "/members"); state.members = Array.isArray(payload) ? payload : (payload.members || []);
    var list = document.getElementById("memberList"); list.replaceChildren(); state.members.forEach(function (member) { list.appendChild(memberRow(member)); });
    document.getElementById("projectMemberCount").textContent = String(state.members.length); return state.members;
  }

  async function updateMemberRole(member, select) {
    select.disabled = true;
    try {
      await request(apiRoot + "/members/" + encodeURIComponent(member.user_id), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role: select.value }) });
      state.members = null; await loadMembers(true); setStatus("Member role updated.", "ok");
    } catch (error) { select.value = member.role; select.disabled = false; setStatus(error.message, "error"); }
  }

  async function removeMember(member, row) {
    if (!window.confirm("Remove " + (member.username || "this member") + " from the project?")) return;
    row.querySelectorAll("button, select").forEach(function (control) { control.disabled = true; });
    try { await request(apiRoot + "/members/" + encodeURIComponent(member.user_id), { method: "DELETE" }); state.members = null; await loadMembers(true); setStatus("Member removed.", "ok"); }
    catch (error) { row.querySelectorAll("button, select").forEach(function (control) { control.disabled = false; }); setStatus(error.message, "error"); }
  }

  async function transferOwnership(member, row) {
    if (!window.confirm("Transfer project ownership to " + (member.username || "this member") + "?")) return;
    row.querySelectorAll("button, select").forEach(function (control) { control.disabled = true; });
    try {
      await request(apiRoot + "/transfer-ownership", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: member.user_id }) });
      state.members = null; await loadProject(); await loadMembers(true); setStatus("Project ownership transferred.", "ok");
    } catch (error) { row.querySelectorAll("button, select").forEach(function (control) { control.disabled = false; }); setStatus(error.message, "error"); }
  }

  function invitationRow(invitation) {
    var row = document.createElement("article"); row.className = "invitation-row";
    var copy = document.createElement("div"), title = document.createElement("strong"), detail = document.createElement("small");
    title.textContent = invitation.invited_username || invitation.username || ("User " + invitation.invited_user_id); detail.textContent = (invitation.proposed_role || invitation.role) + (invitation.expires_at ? " | expires " + formatDate(invitation.expires_at) : ""); copy.append(title, detail); row.appendChild(copy);
    if (has("invite_members") || has("manage_members")) {
      var actions = document.createElement("div"); actions.className = "row-actions"; var revoke = document.createElement("button"); revoke.type = "button"; revoke.className = "row-button danger"; revoke.textContent = "Revoke";
      revoke.addEventListener("click", function () { revokeInvitation(invitation, row); }); actions.appendChild(revoke); row.appendChild(actions);
    }
    return row;
  }

  async function loadInvitations(force) {
    if (state.invitations && !force) return state.invitations;
    var payload = await request(apiRoot + "/invitations"); state.invitations = Array.isArray(payload) ? payload : (payload.invitations || []);
    var section = document.getElementById("pendingInvitations"), list = document.getElementById("projectInvitationList"); list.replaceChildren();
    state.invitations.forEach(function (invitation) { list.appendChild(invitationRow(invitation)); }); section.hidden = state.invitations.length === 0; return state.invitations;
  }

  async function revokeInvitation(invitation, row) {
    row.querySelectorAll("button").forEach(function (button) { button.disabled = true; });
    try { await request(apiRoot + "/invitations/" + encodeURIComponent(invitation.id), { method: "DELETE" }); state.invitations = null; await loadInvitations(true); setStatus("Invitation revoked.", "ok"); }
    catch (error) { row.querySelectorAll("button").forEach(function (button) { button.disabled = false; }); setStatus(error.message, "error"); }
  }

  var searchTimer = null;
  document.getElementById("inviteUserSearch").addEventListener("input", function (event) {
    window.clearTimeout(searchTimer); var query = event.target.value.trim(); if (query.length < 2) return;
    searchTimer = window.setTimeout(async function () {
      try {
        var payload = await request(apiRoot + "/users/search?q=" + encodeURIComponent(query)); state.users = payload.users || [];
        var options = document.getElementById("inviteUserOptions"); options.replaceChildren(); state.users.forEach(function (user) { var option = document.createElement("option"); option.value = user.username; option.label = user.display_name || user.username; options.appendChild(option); });
      } catch (error) { setStatus(error.message, "error"); }
    }, 200);
  });

  document.getElementById("inviteMemberForm").addEventListener("submit", async function (event) {
    event.preventDefault(); var input = document.getElementById("inviteUserSearch"), username = input.value.trim().toLowerCase();
    var user = state.users.find(function (candidate) { return String(candidate.username).toLowerCase() === username; });
    if (!user) return setStatus("Select an existing user from the search results.", "error");
    var submit = event.target.querySelector('[type="submit"]'); submit.disabled = true;
    try {
      await request(apiRoot + "/invitations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: user.id, role: document.getElementById("inviteRole").value }) });
      input.value = ""; state.invitations = null; await loadInvitations(true); setStatus("Invitation sent.", "ok");
    } catch (error) { setStatus(error.message, "error"); }
    finally { submit.disabled = false; }
  });

  function openTab(name) {
    document.querySelectorAll(".project-tab").forEach(function (tab) {
      var selected = tab.dataset.tab === name; tab.classList.toggle("active", selected); tab.setAttribute("aria-selected", String(selected));
    });
    document.querySelectorAll(".project-tab-panel").forEach(function (panel) { panel.hidden = panel.dataset.panel !== name; });
    if (name === "tasks") loadTasks().catch(function (error) { setStatus(error.message, "error"); });
    if (name === "members") Promise.all([loadMembers(), has("manage_members") ? loadInvitations() : Promise.resolve([])]).catch(function (error) { setStatus(error.message, "error"); });
  }

  document.querySelectorAll(".project-tab").forEach(function (tab) { tab.addEventListener("click", function () { openTab(tab.dataset.tab); }); });
  document.querySelectorAll("[data-open-tab]").forEach(function (button) { button.addEventListener("click", function () { openTab(button.dataset.openTab); }); });

  document.getElementById("projectSettingsForm").addEventListener("submit", async function (event) {
    event.preventDefault(); var save = document.getElementById("saveProjectSettings"); save.disabled = true;
    try {
      var checked = document.querySelector('input[name="settingsVisibility"]:checked');
      await request(apiRoot, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: document.getElementById("settingsName").value.trim(), description: document.getElementById("settingsDescription").value.trim(), visibility: checked ? checked.value : state.project.visibility }) });
      await loadProject(); setStatus("Project settings saved.", "ok");
    } catch (error) { setStatus(error.message, "error"); }
    finally { save.disabled = false; }
  });

  document.getElementById("archiveProject").addEventListener("click", async function () {
    if (!window.confirm("Archive this project? New tasks and membership changes will stop.")) return;
    var button = document.getElementById("archiveProject"); button.disabled = true;
    try { await request(apiRoot, { method: "DELETE" }); window.location.assign("/compute/projects"); }
    catch (error) { button.disabled = false; setStatus(error.message, "error"); }
  });

  async function loadProject() {
    var payload = await request(apiRoot, undefined, true), project = payload.project || payload;
    state.project = project; state.capabilities = payload.capabilities || project.capabilities || []; state.role = payload.membership_role || project.membership_role || (payload.membership && payload.membership.role) || null;
    document.getElementById("projectTitle").textContent = project.name;
    document.getElementById("projectDescription").textContent = project.description || "No description";
    document.getElementById("projectVisibilityBadge").textContent = project.visibility;
    document.getElementById("projectRole").textContent = state.role || "Reader";
    document.getElementById("projectTaskCount").textContent = String(project.task_count || 0);
    document.getElementById("projectMemberCount").textContent = String(project.member_count || 0);
    document.getElementById("settingsName").value = project.name || ""; document.getElementById("settingsDescription").value = project.description || "";
    var visibility = document.querySelector('input[name="settingsVisibility"][value="' + project.visibility + '"]'); if (visibility) visibility.checked = true;
    var taskButton = document.getElementById("newProjectTask"); taskButton.hidden = !has("submit_tasks"); taskButton.href = "/compute/create_task?scope_type=project&scope_id=" + encodeURIComponent(projectId);
    var canSettings = has("change_project_settings"); document.getElementById("projectSettingsForm").querySelectorAll("input, textarea, button").forEach(function (control) { control.disabled = !canSettings; });
    document.getElementById("dangerZone").hidden = !has("delete_project");
    document.getElementById("inviteMemberForm").hidden = !has("invite_members");
    document.querySelector('[data-tab="members"]').hidden = !state.role;
    document.querySelector('[data-tab="settings"]').hidden = !canSettings && !has("delete_project");
    if (project.archived_at) { document.getElementById("projectScopeLabel").textContent = "Archived"; document.getElementById("projectVisibilityBadge").textContent = project.visibility + " | archived"; taskButton.hidden = true; }
    return project;
  }

  T.initToggle(document.getElementById("themeToggle"));
  loadProject().then(function () { return Promise.all([loadTasks(), state.role ? loadMembers() : Promise.resolve([])]); }).catch(function (error) { setStatus(error.message, "error"); document.getElementById("projectTitle").textContent = "Project unavailable"; });
})();
