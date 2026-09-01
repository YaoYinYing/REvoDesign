/* REvoCompute - project list and invitation inbox */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;
  var projects = [];
  var grid = document.getElementById("projectGrid");
  var projectSearch = document.getElementById("projectSearch");
  var createPanel = document.getElementById("createProjectPanel");
  var createForm = document.getElementById("createProjectForm");
  var createStatus = document.getElementById("createProjectStatus");

  function setStatus(node, message, kind) {
    node.textContent = message || "";
    node.className = "form-status" + (kind ? " " + kind : "");
  }

  async function request(url, options) {
    var response = await A.authFetch(url, options);
    var payload = (response.headers.get("Content-Type") || "").includes("application/json") ? await response.json() : {};
    if (!response.ok) throw new Error(payload.error || payload.message || "Request failed (HTTP " + response.status + ")");
    return payload;
  }

  function projectId(project) { return project.id || project.project_id; }

  function projectCard(project) {
    var card = document.createElement("a");
    card.className = "project-card";
    card.href = "/compute/projects/" + encodeURIComponent(projectId(project));
    var head = document.createElement("div"); head.className = "project-card-head";
    var visibility = document.createElement("span"); visibility.className = "visibility-badge"; visibility.textContent = project.visibility || "private";
    var role = document.createElement("span"); role.className = "project-role-badge"; role.textContent = project.membership_role || project.role || "Read only";
    head.append(visibility, role);
    var body = document.createElement("div");
    var title = document.createElement("h3"); title.textContent = project.name || "Untitled project";
    var description = document.createElement("p"); description.textContent = project.description || "No description";
    body.append(title, description);
    var meta = document.createElement("div"); meta.className = "project-card-meta";
    var tasks = document.createElement("span"); tasks.textContent = String(project.task_count || 0) + " tasks";
    var members = document.createElement("span"); members.textContent = String(project.member_count || 0) + " members";
    meta.append(tasks, members); card.append(head, body, meta); return card;
  }

  function renderProjects() {
    var query = projectSearch.value.trim().toLowerCase();
    var visible = projects.filter(function (project) {
      return !query || [project.name, project.description, project.visibility, project.membership_role, project.role].join(" ").toLowerCase().includes(query);
    });
    grid.replaceChildren(); visible.forEach(function (project) { grid.appendChild(projectCard(project)); });
    document.getElementById("projectsEmpty").hidden = visible.length > 0;
  }

  async function loadProjects() {
    try {
      var payload = await request("/compute/api/projects");
      projects = Array.isArray(payload) ? payload : (payload.projects || []);
      renderProjects();
    } catch (error) {
      grid.replaceChildren(); document.getElementById("projectsEmpty").hidden = false;
      document.getElementById("projectsEmpty").textContent = error.message;
    }
  }

  function invitationRow(invitation) {
    var row = document.createElement("article"); row.className = "invitation-row";
    var copy = document.createElement("div");
    var title = document.createElement("strong"); title.textContent = invitation.project_name || "Project invitation";
    var detail = document.createElement("small"); detail.textContent = (invitation.proposed_role || invitation.role || "viewer") + " role";
    copy.append(title, detail);
    var actions = document.createElement("div"); actions.className = "row-actions";
    var accept = document.createElement("button"); accept.type = "button"; accept.className = "row-button primary"; accept.textContent = "Accept";
    var decline = document.createElement("button"); decline.type = "button"; decline.className = "row-button"; decline.textContent = "Decline";
    accept.addEventListener("click", function () { respondInvitation(invitation.id, true, row); });
    decline.addEventListener("click", function () { respondInvitation(invitation.id, false, row); });
    actions.append(accept, decline); row.append(copy, actions); return row;
  }

  async function respondInvitation(invitationId, accept, row) {
    row.querySelectorAll("button").forEach(function (button) { button.disabled = true; });
    try {
      await request("/compute/api/invitations/" + encodeURIComponent(invitationId), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: accept ? "accept" : "decline" })
      });
      await Promise.all([loadProjects(), loadInvitations()]);
    } catch (error) {
      row.querySelectorAll("button").forEach(function (button) { button.disabled = false; });
      window.alert(error.message);
    }
  }

  async function loadInvitations() {
    var list = document.getElementById("invitationList"), empty = document.getElementById("invitationsEmpty");
    try {
      var payload = await request("/compute/api/invitations?status=pending");
      var invitations = Array.isArray(payload) ? payload : (payload.invitations || []);
      list.replaceChildren(); invitations.forEach(function (invitation) { list.appendChild(invitationRow(invitation)); });
      empty.hidden = invitations.length > 0;
    } catch (error) {
      list.replaceChildren(); empty.hidden = false; empty.textContent = error.message;
    }
  }

  document.getElementById("showCreateProject").addEventListener("click", function () {
    createPanel.hidden = false; document.getElementById("projectName").focus();
  });
  document.getElementById("closeCreateProject").addEventListener("click", function () { createPanel.hidden = true; setStatus(createStatus, ""); });
  projectSearch.addEventListener("input", renderProjects);
  createForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    var submit = createForm.querySelector('[type="submit"]'); submit.disabled = true; setStatus(createStatus, "Creating project...");
    try {
      var project = await request("/compute/api/projects", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
          name: document.getElementById("projectName").value.trim(),
          description: document.getElementById("projectDescription").value.trim(),
          visibility: document.getElementById("projectVisibility").value
        })
      });
      var created = project.project || project;
      window.location.assign("/compute/projects/" + encodeURIComponent(projectId(created)));
    } catch (error) { setStatus(createStatus, error.message, "error"); submit.disabled = false; }
  });

  T.initToggle(document.getElementById("themeToggle"));
  loadProjects(); loadInvitations();
})();
