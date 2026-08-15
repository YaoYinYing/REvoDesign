/* REvoCompute — schema-driven task submission orchestration */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;
  var Workspace = window.REvoComputeInputWorkspace.InputWorkspace;
  var form = document.getElementById("uploadForm");
  var fileInput = document.getElementById("fileInput");
  var statusNode = document.getElementById("uploadStatus");
  var submitButton = document.getElementById("uploadButton");
  var validationSubmit = document.getElementById("validationSubmit");
  var clearButton = document.getElementById("clearButton");
  var workspaceRoot = document.getElementById("inputWorkspace");
  var categoryRail = document.getElementById("categoryRail");
  var wizardToggle = document.getElementById("wizardToggle");
  var wizardNav = document.getElementById("wizardNav");
  var wizardPrev = document.getElementById("wizardPrev");
  var wizardNext = document.getElementById("wizardNext");
  var wizardProgress = document.getElementById("wizardProgress");
  var activeTaskCategory = document.getElementById("activeTaskCategory");
  var activeTaskName = document.getElementById("activeTaskName");
  var taskIntro = document.getElementById("taskIntro");
  var validationChecks = document.getElementById("validationChecks");
  var validationSummary = document.getElementById("validationSummary");
  var currentForm = null;
  var taskTypes = [];
  var wizardOn = true;
  var stepIndex = 0;

  var CATEGORY_ORDER = ["evolution", "structure", "fitness", "function", "inverse_folding", "design"];
  var CATEGORY_LABELS = {
    evolution: "Evolution",
    structure: "Structure",
    fitness: "Fitness",
    function: "Function",
    inverse_folding: "Inverse Folding",
    design: "Design",
  };
  var MAX_UPLOAD_BYTES = 16 * 1024 * 1024;

  function setStatus(message, kind) {
    statusNode.className = "status" + (kind ? " " + kind : "");
    statusNode.textContent = message;
  }

  function sanitizeHeader(value) {
    var cleaned = String(value || "").trim().replace(/\s+/g, "_").replace(/[^A-Za-z0-9_.-]/g, "");
    return cleaned || "sequence";
  }

  function wrapSequence(sequence, width) {
    var lines = [];
    for (var index = 0; index < sequence.length; index += width) lines.push(sequence.slice(index, index + width));
    return lines.join("\n");
  }

  function setSelectedFiles(files) {
    var transfer = new DataTransfer();
    Array.from(files).forEach(function (file) { transfer.items.add(file); });
    fileInput.files = transfer.files;
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // -- cookie helpers (wizard-mode preference) --------------------------------

  function getCookie(name) {
    var prefix = name + "=";
    var parts = document.cookie.split(";");
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].trim();
      if (part.indexOf(prefix) === 0) return part.slice(prefix.length);
    }
    return null;
  }

  function setCookie(name, value) {
    document.cookie = name + "=" + value + ";path=/;max-age=" + 365 * 86400 + ";SameSite=Lax";
  }

  // -- category rail ----------------------------------------------------------

  function labelFor(category) {
    return CATEGORY_LABELS[category] || category.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function closeRailPanels(except) {
    categoryRail.querySelectorAll(".rail-panel").forEach(function (panel) {
      if (panel !== except) panel.hidden = true;
    });
    categoryRail.querySelectorAll(".rail-node").forEach(function (node) {
      node.setAttribute("aria-expanded", node === except ? "true" : "false");
    });
  }

  function renderRail() {
    categoryRail.querySelectorAll(".rail-node, .rail-panel, .rail-bond").forEach(function (node) { node.remove(); });
    var groups = {};
    taskTypes.forEach(function (taskType) {
      (groups[taskType.category] = groups[taskType.category] || []).push(taskType);
    });
    var categories = CATEGORY_ORDER.filter(function (category) { return groups[category]; });
    categories.concat(Object.keys(groups).filter(function (category) { return CATEGORY_ORDER.indexOf(category) === -1; }));
    var first = true;
    categories.forEach(function (category) {
      if (!first) {
        var bond = document.createElement("span");
        bond.className = "rail-bond";
        bond.setAttribute("aria-hidden", "true");
        categoryRail.appendChild(bond);
      }
      first = false;
      var node = document.createElement("button");
      node.type = "button";
      node.className = "rail-node";
      node.dataset.category = category;
      node.setAttribute("aria-expanded", "false");
      node.textContent = labelFor(category);
      node.addEventListener("click", function (event) {
        event.stopPropagation();
        var panel = categoryRail.querySelector('.rail-panel[data-category="' + category + '"]');
        var opening = panel && panel.hidden;
        closeRailPanels(null);
        if (panel) panel.hidden = !opening;
        node.setAttribute("aria-expanded", opening ? "true" : "false");
      });
      categoryRail.appendChild(node);

      var panel = document.createElement("div");
      panel.className = "rail-panel";
      panel.dataset.category = category;
      panel.hidden = true;
      groups[category].forEach(function (taskType) {
        var item = document.createElement("button");
        item.type = "button";
        item.className = "rail-item";
        item.textContent = taskType.display_name;
        if (taskType.gpus) {
          var badge = document.createElement("span");
          badge.className = "rail-item-gpu";
          badge.textContent = "GPU";
          item.appendChild(badge);
        }
        item.addEventListener("click", function () {
          closeRailPanels(null);
          fetchFormDefinition(taskType.name);
        });
        panel.appendChild(item);
      });
      categoryRail.appendChild(panel);
    });
  }

  // -- wizard / single-page mode ---------------------------------------------

  function workspaceCards() {
    return Array.prototype.slice.call(workspaceRoot.querySelectorAll(".workspace-card"));
  }

  function renderWizardStep() {
    var cards = workspaceCards();
    var total = cards.length;
    cards.forEach(function (card, index) { card.hidden = index !== stepIndex; });
    wizardPrev.disabled = stepIndex === 0;
    wizardNext.textContent = stepIndex === total - 1 ? "Review" : "Next →";
    wizardProgress.replaceChildren();
    for (var i = 0; i < total; i++) {
      var dot = document.createElement("span");
      dot.className = "wizard-dot" + (i === stepIndex ? " current" : i < stepIndex ? " done" : "");
      wizardProgress.appendChild(dot);
    }
    wizardProgress.setAttribute("aria-valuemax", String(total));
    wizardProgress.setAttribute("aria-valuenow", String(stepIndex + 1));
  }

  function applyMode() {
    var cards = workspaceCards();
    var wizard = wizardOn && cards.length > 1;
    wizardNav.hidden = !wizard;
    workspaceRoot.classList.toggle("wizard-mode", wizard);
    if (wizard) {
      stepIndex = Math.min(stepIndex, cards.length - 1);
      renderWizardStep();
    } else {
      cards.forEach(function (card) { card.hidden = false; });
    }
    refreshValidation();
  }

  function setWizardMode(on) {
    wizardOn = on;
    setCookie("revocompute_wizard_mode", on ? "1" : "0");
    wizardToggle.setAttribute("aria-checked", on ? "true" : "false");
    applyMode();
  }

  // -- live validation panel --------------------------------------------------

  function validationRow(state, text) {
    var row = document.createElement("li");
    row.className = "validation-row " + state;
    var dot = document.createElement("span");
    dot.className = "validation-dot";
    dot.setAttribute("aria-hidden", "true");
    row.appendChild(dot);
    row.appendChild(document.createTextNode(text));
    return row;
  }

  function refreshValidation() {
    validationChecks.replaceChildren();
    if (!currentForm) {
      validationChecks.appendChild(validationRow("error", "Choose a method from the rail above."));
      validationSummary.textContent = "Waiting for a method";
      return;
    }
    var rows = [];
    var problems = 0;

    rows.push(validationRow("ok", "Method selected: " + currentForm.display_name));

    var files = workspace.files();
    var sequence = workspace.sequence();
    if (!files.length && !sequence) {
      rows.push(validationRow("error", "Add an input file or paste a sequence."));
      problems += 1;
    } else {
      var totalFiles = files.length + (sequence ? 1 : 0);
      rows.push(validationRow("ok", "Inputs provided: " + totalFiles));
    }

    var accepted = (currentForm.file_input.extensions || []).map(function (ext) { return ext.toLowerCase(); });
    files.forEach(function (file) {
      var extension = "." + (file.name.split(".").pop() || "").toLowerCase();
      if (accepted.indexOf(extension) === -1) {
        rows.push(validationRow("error", file.name + " has extension " + extension + " — expected " + accepted.join(", ")));
        problems += 1;
      } else {
        rows.push(validationRow("ok", file.name + " — " + extension + " accepted"));
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        rows.push(validationRow("error", file.name + " exceeds the 16 MiB upload limit"));
        problems += 1;
      }
    });

    if (files.length > currentForm.file_input.max_files) {
      rows.push(validationRow("error", "At most " + currentForm.file_input.max_files + " files are allowed"));
      problems += 1;
    }

    var paramErrors = workspace.validate();
    if (paramErrors.length) {
      paramErrors.forEach(function (error) {
        rows.push(validationRow("error", error));
        problems += 1;
      });
    } else {
      rows.push(validationRow("ok", "Parameters valid"));
    }

    rows.push(validationRow("info", "Structure geometry is checked on the server before queuing"));

    rows.forEach(function (row) { validationChecks.appendChild(row); });
    validationSummary.textContent = problems ? problems + " issue(s) to fix" : "Ready to submit";
    validationSummary.className = "validation-summary" + (problems ? " has-issues" : "");
  }

  // -- workspace mounting -----------------------------------------------------

  var workspace = new Workspace(workspaceRoot, { fileInput: fileInput, status: setStatus });

  function mountForm(definition) {
    currentForm = definition;
    fileInput.accept = definition.file_input.accept;
    fileInput.multiple = Boolean(definition.file_input.multiple);
    workspace.mount(definition, helpCache);
    stepIndex = 0;
    activeTaskCategory.textContent = labelFor(definition.category);
    activeTaskName.textContent = definition.display_name;
    taskIntro.textContent = definition.intro || "";
    setStatus("Ready to prepare " + definition.display_name + ".");
    applyMode();
  }

  var helpCache = {};

  async function fetchFormDefinition(name) {
    setStatus("Loading task workspace…", "busy");
    try {
      var response = await fetch("/compute/api/types/" + encodeURIComponent(name));
      if (!response.ok) throw new Error("Failed to load task workspace");
      var def = await response.json();
      try {
        var helpResp = await fetch("/compute/api/types/" + encodeURIComponent(name) + "/help");
        if (helpResp.ok) helpCache = await helpResp.json();
      } catch (_) { /* non-critical */ }
      mountForm(def);
    } catch (error) {
      setStatus("Could not load the selected task: " + error.message, "error");
    }
  }

  async function loadTaskTypes() {
    try {
      var response = await fetch("/compute/api/types");
      if (!response.ok) throw new Error("Failed to load task types");
      taskTypes = await response.json();
      renderRail();
      if (taskTypes.length) await fetchFormDefinition(taskTypes[0].name);
      else setStatus("No task types are currently enabled.", "error");
    } catch (error) {
      setStatus("Could not reach the server. Check your connection and reload the page.", "error");
    }
  }

  // -- drag & drop ------------------------------------------------------------

  var dropZone = form.closest(".input-zone");
  function dragOver(event) { event.preventDefault(); event.stopPropagation(); event.dataTransfer.dropEffect = "copy"; dropZone.classList.add("drop-highlight"); }
  function dragLeave(event) { event.preventDefault(); event.stopPropagation(); if (!dropZone.contains(event.relatedTarget)) dropZone.classList.remove("drop-highlight"); }
  dropZone.addEventListener("dragover", dragOver);
  dropZone.addEventListener("dragenter", dragOver);
  dropZone.addEventListener("dragleave", dragLeave);
  dropZone.addEventListener("drop", function (event) {
    event.preventDefault(); event.stopPropagation(); dropZone.classList.remove("drop-highlight");
    var files = Array.from(event.dataTransfer.files || []);
    if (!files.length || !currentForm) return;
    if (!currentForm.file_input.multiple && files.length > 1) return setStatus("This task accepts exactly one input file.", "error");
    setSelectedFiles(files); setStatus(files.length + " input file(s) ready for review.", "ok");
  });
  document.addEventListener("dragover", function (event) { event.preventDefault(); });
  document.addEventListener("drop", function (event) { event.preventDefault(); });
  document.addEventListener("click", function () { closeRailPanels(null); });

  clearButton.addEventListener("click", function () {
    fileInput.value = "";
    if (currentForm) workspace.mount(currentForm);
    setStatus("Workspace cleared.");
    applyMode();
  });

  // -- submission (shared by both submit buttons) -----------------------------

  async function submitTask() {
    if (!currentForm) return setStatus("The task definition is still loading.", "error");
    var errors = workspace.validate();
    if (errors.length) return setStatus(errors.join("\n"), "error");
    var files = workspace.files();
    var sequence = workspace.sequence();
    if (!files.length && sequence) {
      var extension = currentForm.file_input.primary_extensions[0];
      var header = sanitizeHeader(workspace.sequenceName());
      files = [new File([">" + header + "\n" + wrapSequence(sequence, 80) + "\n"], header + extension, { type: "text/plain" })];
    }
    var formData = new FormData();
    files.forEach(function (file) {
      formData.append("files", file);
      formData.append("input_paths", file.webkitRelativePath || file.name);
    });
    formData.append("task_type", currentForm.name);
    var params = workspace.paramValues();
    Object.keys(params).forEach(function (name) { formData.append("params[" + name + "]", params[name]); });

    submitButton.disabled = true; validationSubmit.disabled = true; clearButton.disabled = true;
    setStatus("Uploading the immutable snapshot and queueing the task…", "busy");
    try {
      var response = await A.authFetch("/compute/api/post", { method: "POST", body: formData });
      if (response.ok || response.status === 202) {
        setStatus("Task submitted. Redirecting to the dashboard…", "ok");
        window.location.assign("/compute/dashboard"); return;
      }
      var payload = (response.headers.get("Content-Type") || "").includes("application/json") ? await response.json() : {};
      var message = payload.error || payload.message || "Upload failed (HTTP " + response.status + ")";
      if (payload.details) message += ": " + payload.details.map(function (detail) { return detail.field + " " + detail.message; }).join("; ");
      setStatus(message, "error");
    } catch (error) {
      setStatus("Network error: " + error.message, "error");
    } finally {
      submitButton.disabled = false; validationSubmit.disabled = false; clearButton.disabled = false;
    }
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    submitTask();
  });
  validationSubmit.addEventListener("click", function () { submitTask(); });

  // -- wiring -----------------------------------------------------------------

  wizardOn = getCookie("revocompute_wizard_mode") !== "0";
  wizardToggle.setAttribute("aria-checked", wizardOn ? "true" : "false");
  wizardToggle.addEventListener("click", function () { setWizardMode(!wizardOn); });
  wizardPrev.addEventListener("click", function () { stepIndex = Math.max(0, stepIndex - 1); renderWizardStep(); });
  wizardNext.addEventListener("click", function () {
    var total = workspaceCards().length;
    if (stepIndex < total - 1) { stepIndex += 1; renderWizardStep(); }
  });

  form.addEventListener("input", refreshValidation);
  form.addEventListener("change", refreshValidation);
  setInterval(refreshValidation, 900);

  T.initToggle(document.getElementById("themeToggle"));

  // Subtle scroll reveal for workspace cards (respects reduced motion).
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    workspaceRoot.classList.add("no-reveal");
  } else {
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("revealed");
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    var revealWatch = new MutationObserver(function () {
      workspaceRoot.querySelectorAll(".workspace-card:not(.revealed)").forEach(function (card) {
        revealObserver.observe(card);
      });
    });
    revealWatch.observe(workspaceRoot, { childList: true, subtree: true });
  }

  var helpBtn = document.getElementById("workspaceHelpBtn");
  var helpPopover = document.getElementById("workspaceHelpPopover");
  helpBtn.addEventListener("click", function (event) {
    event.stopPropagation();
    helpPopover.hidden = !helpPopover.hidden;
  });

  loadTaskTypes();
})();
