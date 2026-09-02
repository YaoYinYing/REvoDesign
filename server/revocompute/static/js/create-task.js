/* REvoCompute — scientific experiment submission orchestration */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth, T = window.REvoDesignTheme;
  var Workspace = window.REvoComputeInputWorkspace.InputWorkspace;
  var form = document.getElementById("uploadForm"), fileInput = document.getElementById("fileInput");
  var statusNode = document.getElementById("uploadStatus"), submitButton = document.getElementById("uploadButton");
  var clearButton = document.getElementById("clearButton"), workspaceRoot = document.getElementById("inputWorkspace");
  var chooser = document.getElementById("methodChooser"), workbench = document.getElementById("experimentWorkbench");
  var methodGroups = document.getElementById("methodGroups"), methodSearch = document.getElementById("methodSearch");
  var catalogStatus = document.getElementById("catalogStatus"), protocolTrack = document.getElementById("protocolTrack");
  var validationChecks = document.getElementById("validationChecks"), validationSummary = document.getElementById("validationSummary");
  var scopeOptions = document.getElementById("scopeOptions"), artifactReferencesInput = document.getElementById("artifactReferences");
  var catalog = { categories: [], task_types: [] }, currentForm = null, loadController = null, loadGeneration = 0, scopeReady = false, unresolvedRequestedScope = false;

  function setStatus(message, kind) {
    statusNode.className = "status" + (kind ? " " + kind : ""); statusNode.textContent = message;
  }
  function sanitizeHeader(value) {
    var cleaned = String(value || "").trim().replace(/\s+/g, "_").replace(/[^A-Za-z0-9_.-]/g, "");
    return cleaned || "sequence";
  }
  function wrapSequence(sequence, width) {
    var lines = []; for (var index = 0; index < sequence.length; index += width) lines.push(sequence.slice(index, index + width)); return lines.join("\n");
  }
  function categoryFor(name) { return catalog.categories.find(function (category) { return category.name === name; }); }

  function artifactReferences() {
    var seen = {};
    return artifactReferencesInput.value.split(/\r?\n/).map(function (value) { return value.trim(); }).filter(function (value) {
      if (!value || seen[value]) return false; seen[value] = true; return true;
    });
  }

  function artifactReferenceErrors(references) {
    return references.filter(function (reference) {
      var match = /^@([0-9a-fA-F]{32})\/(.+)$/.exec(reference);
      if (!match || match[2].includes("\\") || match[2].startsWith("/") || match[2].includes("\u0000")) return true;
      return match[2].split("/").some(function (segment) { return !segment || segment === "." || segment === ".."; });
    }).map(function (reference) { return "Invalid artifact reference: " + reference; });
  }

  function addProjectScope(project) {
    var label = document.createElement("label"); label.className = "scope-option";
    var input = document.createElement("input"); input.type = "radio"; input.name = "taskScope"; input.value = "project"; input.dataset.scopeId = String(project.id || project.project_id);
    var copy = document.createElement("span"), title = document.createElement("strong"), detail = document.createElement("small");
    title.textContent = project.name; detail.textContent = "Project scope"; copy.append(title, detail); label.append(input, copy); scopeOptions.appendChild(label);
  }

  async function loadWritableProjects() {
    try {
      var response = await A.authFetch("/compute/api/projects?capability=submit_tasks");
      if (!response.ok) throw new Error("Failed to load project scopes");
      var payload = await response.json(), projects = Array.isArray(payload) ? payload : (payload.projects || []);
      projects.forEach(addProjectScope);
      var query = new URLSearchParams(window.location.search), requestedType = query.get("scope_type"), requestedId = query.get("scope_id");
      if (requestedType === "project" && requestedId) {
        var requested = Array.from(scopeOptions.querySelectorAll('input[value="project"]')).find(function (input) { return input.dataset.scopeId === requestedId; });
        if (requested) requested.checked = true;
        else {
          unresolvedRequestedScope = true;
          scopeOptions.querySelectorAll('input[name="taskScope"]').forEach(function (input) { input.checked = false; });
          setStatus("The requested Project is unavailable. Select another scope.", "error");
        }
      }
    } catch (error) {
      var requestedProject = new URLSearchParams(window.location.search).get("scope_type") === "project";
      unresolvedRequestedScope = requestedProject;
      setStatus(requestedProject ? "The requested Project could not be loaded. Select another scope." : "Project scopes are temporarily unavailable. Personal scope remains available.", "error");
    } finally {
      scopeReady = true; if (currentForm) refreshValidation();
    }
  }

  function selectMethod(name) {
    var exists = catalog.task_types.some(function (task) { return task.name === name; });
    if (!exists) return showChooser(name ? "That method is not available on this server." : "Choose a method to begin.");
    var url = new URL(window.location.href); url.searchParams.set("task_type", name); history.replaceState(null, "", url);
    fetchFormDefinition(name);
  }

  function showChooser(message) {
    if (loadController) loadController.abort();
    if (currentForm) workspace.destroy(); currentForm = null; workspaceRoot.replaceChildren();
    chooser.hidden = false; workbench.hidden = true;
    catalogStatus.textContent = message || "Choose a method to begin."; catalogStatus.className = "status";
    var url = new URL(window.location.href); url.searchParams.delete("task_type"); history.replaceState(null, "", url);
    methodSearch.focus();
  }

  function methodCard(task) {
    var button = document.createElement("button"); button.type = "button"; button.className = "method-card";
    button.dataset.search = [task.display_name, task.summary, task.use_when, task.input_summary, task.output_summary].join(" ").toLowerCase();
    var title = document.createElement("strong"); title.textContent = task.display_name;
    var summary = document.createElement("span"); summary.textContent = task.summary;
    var handoff = document.createElement("small"); handoff.textContent = task.input_label + " → " + task.output_summary;
    button.append(title, summary, handoff); button.addEventListener("click", function () { selectMethod(task.name); }); return button;
  }

  function renderCatalog(query) {
    query = String(query || "").trim().toLowerCase(); methodGroups.replaceChildren(); var shown = 0;
    catalog.categories.forEach(function (category) {
      var tasks = catalog.task_types.filter(function (task) {
        return task.category === category.name && (!query || [task.display_name, task.summary, task.use_when, task.input_summary, task.output_summary].join(" ").toLowerCase().includes(query));
      });
      if (!tasks.length) return;
      var section = document.createElement("section"); section.className = "method-group";
      var header = document.createElement("header"), title = document.createElement("h2"), description = document.createElement("p");
      title.textContent = category.label; description.textContent = category.description; header.append(title, description);
      var grid = document.createElement("div"); grid.className = "method-grid"; tasks.forEach(function (task) { grid.appendChild(methodCard(task)); shown += 1; });
      section.append(header, grid); methodGroups.appendChild(section);
    });
    catalogStatus.textContent = shown ? shown + " method" + (shown === 1 ? "" : "s") + " available" : "No methods match that search.";
  }

  function renderProtocol(definition) {
    protocolTrack.replaceChildren();
    definition.input_workspace.steps.forEach(function (step, index) {
      var link = document.createElement("a"); link.href = "#protocol-step-" + step.id; link.className = "protocol-link";
      link.append(Object.assign(document.createElement("span"), { textContent: String(index + 1).padStart(2, "0") }), Object.assign(document.createElement("strong"), { textContent: step.title }));
      link.addEventListener("click", function () { link.setAttribute("aria-current", "step"); }); protocolTrack.appendChild(link);
    });
  }

  function mountForm(definition) {
    currentForm = definition; fileInput.accept = definition.file_input.accept; fileInput.multiple = Boolean(definition.file_input.multiple);
    workspace.mount(definition); renderProtocol(definition);
    var category = categoryFor(definition.category);
    document.getElementById("activeTaskCategory").textContent = category ? category.label : definition.category;
    document.getElementById("activeTaskName").textContent = definition.display_name;
    document.getElementById("taskSummary").textContent = definition.summary;
    document.getElementById("taskUseWhen").textContent = definition.use_when;
    document.getElementById("taskInput").textContent = definition.input_summary;
    document.getElementById("taskOutput").textContent = definition.output_summary;
    document.getElementById("taskAccelerator").textContent = definition.gpus ? "GPU method" : "CPU method";
    document.getElementById("taskNetwork").hidden = !definition.requires_network;
    document.getElementById("taskDetails").href = "/runners/" + encodeURIComponent(definition.name);
    var considerations = document.getElementById("taskConsiderations"); considerations.replaceChildren();
    definition.considerations.forEach(function (item) { var row = document.createElement("li"); row.textContent = item; considerations.appendChild(row); });
    submitButton.textContent = "Run " + definition.display_name; chooser.hidden = true; workbench.hidden = false;
    setStatus("Preparing " + definition.display_name + "."); refreshValidation(); window.scrollTo({ top: 0, behavior: "auto" });
  }

  async function fetchFormDefinition(name) {
    if (loadController) loadController.abort(); loadController = new AbortController(); var generation = ++loadGeneration;
    chooser.hidden = true; workbench.hidden = false; workspaceRoot.replaceChildren(); setStatus("Loading experiment protocol…", "busy");
    try {
      var response = await fetch("/compute/api/types/" + encodeURIComponent(name), { signal: loadController.signal });
      if (!response.ok) throw new Error("Failed to load method"); var definition = await response.json();
      if (generation !== loadGeneration) return; mountForm(definition);
    } catch (error) {
      if (error.name === "AbortError") return;
      showChooser("Could not load the selected method. Check your connection and try again.");
    }
  }

  function validationRow(kind, text) {
    var row = document.createElement("li"); row.className = "validation-row " + kind;
    var marker = document.createElement("span"); marker.className = "validation-marker"; marker.setAttribute("aria-hidden", "true");
    row.append(marker, document.createTextNode(text)); return row;
  }

  function refreshValidation() {
    validationChecks.replaceChildren();
    if (!currentForm) { validationSummary.textContent = "Choose a method"; submitButton.disabled = true; return []; }
    var references = artifactReferences(), errors = workspace.validate(), files = workspace.files(), sequence = workspace.sequence();
    var referenceErrors = artifactReferenceErrors(references);
    artifactReferencesInput.setAttribute("aria-invalid", referenceErrors.length ? "true" : "false");
    if (!scopeReady) errors.push("Loading task scopes.");
    if (unresolvedRequestedScope) errors.push("Select a scope for this task.");
    if (references.length && !referenceErrors.length && !files.length && !sequence) {
      errors = errors.filter(function (error) { return error !== "Choose an input file or provide a sequence."; });
      workspaceRoot.querySelectorAll('[id^="file_error_"]').forEach(function (error) {
        if (error.textContent === "Choose an input file or provide a sequence.") { error.hidden = true; var control = workspaceRoot.querySelector('[aria-describedby="' + error.id + '"]'); if (control) control.removeAttribute("aria-invalid"); }
      });
    }
    errors = errors.concat(referenceErrors);
    if (errors.length) errors.forEach(function (error) { validationChecks.appendChild(validationRow("error", error)); });
    else {
      validationChecks.appendChild(validationRow("ok", "Input contract satisfied"));
      validationChecks.appendChild(validationRow("ok", "Method settings are valid"));
      validationChecks.appendChild(validationRow("info", "The server will validate the complete snapshot before queueing"));
    }
    validationSummary.textContent = errors.length ? errors.length + " issue" + (errors.length === 1 ? "" : "s") + " to fix" : "Ready to run";
    validationSummary.className = errors.length ? "has-issues" : "ready"; submitButton.disabled = errors.length > 0;
    protocolTrack.querySelectorAll(".protocol-link").forEach(function (link, index) {
      var step = currentForm.input_workspace.steps[index];
      var ids = step.capabilities.map(function (capability) { return capability.id; });
      var hasInvalid = ids.some(function (id) { return workspaceRoot.querySelector('[data-capability-id="' + id + '"] [aria-invalid="true"]'); });
      link.classList.toggle("has-issues", hasInvalid); link.classList.toggle("complete", !hasInvalid && (files.length || sequence || step.id !== "material"));
    });
    return errors;
  }

  var workspace = new Workspace(workspaceRoot, { fileInput: fileInput, status: setStatus, onChange: refreshValidation });

  async function submitTask() {
    if (!currentForm) return showChooser("Choose a method before running an experiment.");
    var capabilities = workspace.collect(), errors = refreshValidation();
    if (errors.length) { setStatus("Fix the highlighted issues before running this experiment.", "error"); var first = form.querySelector('[aria-invalid="true"]'); if (first) first.focus(); return; }
    var files = workspace.files(), sequence = workspace.sequence();
    if (!files.length && sequence) {
      var extension = currentForm.file_input.primary_extensions[0], header = sanitizeHeader(workspace.sequenceName());
      files = [new File([">" + header + "\n" + wrapSequence(sequence, 80) + "\n"], header + extension, { type: "text/plain" })];
    }
    var formData = new FormData();
    files.forEach(function (file) { formData.append("files", file); formData.append("input_paths", file.webkitRelativePath || file.name); });
    artifactReferences().forEach(function (reference) { formData.append("artifact_references", reference); });
    var selectedScope = scopeOptions.querySelector('input[name="taskScope"]:checked');
    if (!selectedScope || unresolvedRequestedScope) { setStatus("Select a scope before submitting.", "error"); return; }
    formData.append("scope_type", selectedScope.value);
    if (selectedScope && selectedScope.value === "project") formData.append("scope_id", selectedScope.dataset.scopeId);
    formData.append("task_type", currentForm.name);
    formData.append("workspace", JSON.stringify({ version: 2, capabilities: capabilities }));
    var params = workspace.paramValues(); Object.keys(params).forEach(function (name) { formData.append("params[" + name + "]", params[name]); });
    submitButton.disabled = true; clearButton.disabled = true; setStatus("Uploading the immutable snapshot and queueing the task…", "busy");
    try {
      var response = await A.authFetch("/compute/api/post", { method: "POST", body: formData });
      if (response.ok || response.status === 202) { setStatus("Experiment queued. Opening the dashboard…", "ok"); window.location.assign("/compute/dashboard"); return; }
      var payload = (response.headers.get("Content-Type") || "").includes("application/json") ? await response.json() : {};
      var message = payload.error || payload.message || "Submission failed (HTTP " + response.status + ")";
      if (payload.details) message += ": " + payload.details.map(function (detail) { return detail.field + " " + detail.message; }).join("; "); setStatus(message, "error");
    } catch (error) { setStatus("Network error: " + error.message, "error"); }
    finally { clearButton.disabled = false; refreshValidation(); }
  }

  form.addEventListener("submit", function (event) { event.preventDefault(); submitTask(); });
  clearButton.addEventListener("click", function () { if (!currentForm) return; workspace.mount(currentForm); artifactReferencesInput.value = ""; setStatus("Workspace cleared.", "ok"); refreshValidation(); var first = form.querySelector("button, input, textarea, select"); if (first) first.focus(); });
  document.getElementById("changeMethod").addEventListener("click", function () { showChooser("Choose another method."); });
  methodSearch.addEventListener("input", function () { renderCatalog(methodSearch.value); });
  artifactReferencesInput.addEventListener("input", refreshValidation);
  scopeOptions.addEventListener("change", function () { unresolvedRequestedScope = false; refreshValidation(); });

  var dropZone = document.querySelector(".experiment-form-panel");
  function dragOver(event) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; dropZone.classList.add("drop-highlight"); }
  dropZone.addEventListener("dragover", dragOver); dropZone.addEventListener("dragenter", dragOver);
  dropZone.addEventListener("dragleave", function (event) { if (!dropZone.contains(event.relatedTarget)) dropZone.classList.remove("drop-highlight"); });
  dropZone.addEventListener("drop", function (event) {
    event.preventDefault(); dropZone.classList.remove("drop-highlight"); if (!currentForm) return;
    var files = Array.from(event.dataTransfer.files || []); if (!files.length) return;
    if (!currentForm.file_input.multiple && files.length > 1) return setStatus("This method accepts exactly one input file.", "error");
    var transfer = new DataTransfer(); files.forEach(function (file) { transfer.items.add(file); }); fileInput.files = transfer.files; fileInput.dispatchEvent(new Event("change", { bubbles: true }));
  });

  async function loadCatalog() {
    try {
      var response = await fetch("/compute/api/types"); if (!response.ok) throw new Error("Failed to load methods"); catalog = await response.json(); renderCatalog("");
      var requested = new URLSearchParams(window.location.search).get("task_type");
      if (requested && catalog.task_types.some(function (task) { return task.name === requested; })) selectMethod(requested);
      else showChooser(requested ? "That method is not available on this server." : "Choose a method to begin.");
    } catch (error) { catalogStatus.textContent = "Could not reach the server. Check your connection and reload the page."; catalogStatus.className = "status error"; }
  }

  T.initToggle(document.getElementById("themeToggle")); loadWritableProjects(); loadCatalog();
})();
