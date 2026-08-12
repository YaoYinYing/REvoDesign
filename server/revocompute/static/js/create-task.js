/* REvoCompute — schema-driven task submission orchestration */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  "use strict";
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;
  var Workspace = window.REvoComputeInputWorkspace.InputWorkspace;
  var form = document.getElementById("uploadForm");
  var fileInput = document.getElementById("fileInput");
  var taskTypeSelect = document.getElementById("taskTypeSelect");
  var statusNode = document.getElementById("uploadStatus");
  var submitButton = document.getElementById("uploadButton");
  var clearButton = document.getElementById("clearButton");
  var workspaceRoot = document.getElementById("inputWorkspace");
  var currentForm = null;

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

  var workspace = new Workspace(workspaceRoot, { fileInput: fileInput, status: setStatus });

  function fallbackForm() {
    return {
      name: "gremlin", display_name: "PSSM-GREMLIN", runtime_family: "gremlin", gpus: false,
      file_input: { accept: ".fasta", extensions: [".fasta"], primary_extensions: [".fasta"], label: "FASTA file", required: true, multiple: false, max_files: 1 },
      params: [
        { name: "iter", type: "int", default: 100, minimum: 1, maximum: 10000, step: 1, label: "Iterations", description: "GREMLIN optimization iterations", help: "Number of gradient-descent iterations for the Markov random field model. Higher values (500–1000) yield more converged coupling scores; lower values (50–100) are faster but rougher.", advanced: true },
        { name: "evalue", type: "text", default: "1E-10", label: "HHblits E-value", description: "Significance threshold (lower = more stringent)", help: "Controls which sequence matches HHblits considers significant. Lower (1E-20) = near-identical homologs only. Higher (1E-4) = remote homologs included. Default 1E-10 balances coverage and quality.", advanced: true },
        { name: "mact", type: "float", default: 0.35, minimum: 0.0, maximum: 1.0, step: 0.05, label: "Mact", description: "HHblits posterior probability threshold [0–1]", help: "How conservative column inclusion is. Near 1.0 = only high-confidence columns (shorter, more reliable MSA). Near 0.0 = include nearly every column (more noise but preserves signal).", advanced: true },
        { name: "maxfilt", type: "int", default: 100000000, minimum: 1, label: "Maxfilt", description: "HHblits maximum hits through prefilter", help: "Max raw hits passing the prefilter before the expensive alignment stage. Default (100M) effectively disables the cap. Lower to 1–10M for single-domain proteins to reduce resource use.", advanced: true },
        { name: "neffmax", type: "float", default: 20.0, minimum: 1.0, label: "Neffmax", description: "HHblits target effective sequences after diversity filtering", help: "Target number of non-redundant sequences retained. Higher (50–100) = deeper MSA, better contact prediction, but quadratic computation. Lower (5–10) = faster but may miss co-evolutionary signal.", advanced: true },
        { name: "num_iterations", type: "int", default: 3, minimum: 1, maximum: 10, step: 1, label: "PSI-BLAST iterations", description: "Search iterations for PSSM refinement", help: "Number of PSI-BLAST rounds for position-specific scoring matrix refinement. Fewer (1–2) = coarser PSSM. More (5–10) = risk of spurious hits diluting the profile. Default 3 is the NCBI-recommended value.", advanced: true }
      ],
      input_workspace: { version: 1, capabilities: [
        { plugin: "files", id: "source_files", title: "FASTA input", options: { roles: ["primary"], primary_required: true } },
        { plugin: "sequence", id: "sequence_editor", title: "Sequence", options: { allow_multiple: false, format: "fasta" } },
        { plugin: "parameters", id: "task_parameters", title: "GREMLIN settings", options: {} },
        { plugin: "review", id: "submission_review", title: "Review", options: { show_resources: true, show_paths: true } }
      ] }
    };
  }

  function mountForm(definition) {
    currentForm = definition;
    fileInput.accept = definition.file_input.accept;
    fileInput.multiple = Boolean(definition.file_input.multiple);
    workspace.mount(definition);
    setStatus("Ready to prepare " + definition.display_name + ".");
  }

  async function fetchFormDefinition(name) {
    setStatus("Loading task workspace…", "busy");
    try {
      var response = await fetch("/compute/api/types/" + encodeURIComponent(name));
      if (!response.ok) throw new Error("Failed to load task workspace");
      mountForm(await response.json());
    } catch (error) {
      if (name === "gremlin") mountForm(fallbackForm());
      else setStatus("Could not load the selected task: " + error.message, "error");
    }
  }

  async function loadTaskTypes() {
    try {
      var response = await fetch("/compute/api/types");
      if (!response.ok) throw new Error("Failed to load task types");
      var taskTypes = await response.json();
      taskTypeSelect.replaceChildren();
      taskTypes.forEach(function (taskType) {
        var option = document.createElement("option");
        option.value = taskType.name; option.textContent = taskType.display_name;
        taskTypeSelect.appendChild(option);
      });
      if (taskTypes.length) await fetchFormDefinition(taskTypes[0].name);
      else setStatus("No task types are currently enabled.", "error");
    } catch (error) {
      var option = document.createElement("option"); option.value = "gremlin"; option.textContent = "PSSM-GREMLIN";
      taskTypeSelect.replaceChildren(option); mountForm(fallbackForm());
    }
  }

  taskTypeSelect.addEventListener("change", function () { fetchFormDefinition(taskTypeSelect.value); });

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

  clearButton.addEventListener("click", function () {
    fileInput.value = "";
    if (currentForm) workspace.mount(currentForm);
    setStatus("Workspace cleared.");
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
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

    submitButton.disabled = true; clearButton.disabled = true;
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
      submitButton.disabled = false; clearButton.disabled = false;
    }
  });

  T.initToggle(document.getElementById("themeToggle"));

  var helpBtn = document.getElementById("workspaceHelpBtn");
  var helpPopover = document.getElementById("workspaceHelpPopover");
  helpBtn.addEventListener("click", function (event) {
    event.stopPropagation();
    helpPopover.hidden = !helpPopover.hidden;
  });
  document.addEventListener("click", function () { helpPopover.hidden = true; });

  loadTaskTypes();
})();
