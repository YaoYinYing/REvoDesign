/* REvoCompute — Create Task page logic */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;

  var form = document.getElementById("uploadForm");
  var fileInput = document.getElementById("fileInput");
  var fileButton = document.getElementById("fileButton");
  var fileNameDisplay = document.getElementById("fileNameDisplay");
  var taskNameInput = document.getElementById("taskNameInput");
  var sequenceInput = document.getElementById("sequenceInput");
  var sequencePreview = document.getElementById("sequencePreview");
  var statusDiv = document.getElementById("uploadStatus");
  var clearButton = document.getElementById("clearButton");
  var uploadButton = document.getElementById("uploadButton");
  var taskTypeSelect = document.getElementById("taskTypeSelect");
  var fileUploadLabel = document.getElementById("fileUploadLabel");
  var fileHint = document.getElementById("fileHint");
  var editorZone = document.getElementById("editorZone");
  var paramsZone = document.getElementById("paramsZone");

  // -- state -----------------------------------------------------------------

  var currentFormDef = null;

  // -- helpers ---------------------------------------------------------------

  function setStatus(message, kind) {
    statusDiv.className = "status" + (kind ? " " + kind : "");
    statusDiv.textContent = message;
  }

  function normalizeSequence(raw) {
    return String(raw || "").toUpperCase().replace(/[^A-Z]/g, "");
  }

  function wrapSequence(seq, width) {
    width = width || 80;
    var lines = [];
    for (var i = 0; i < seq.length; i += width) lines.push(seq.slice(i, i + width));
    return lines.join("\n");
  }

  function formatPreview(seq) {
    if (!seq.length) return "Sequence: -\nLength: 0 residues";
    var chunks = [];
    for (var i = 0; i < seq.length; i += 10) chunks.push({ index: i + 1, chunk: seq.slice(i, i + 10) });
    var groups = [];
    for (var i = 0; i < chunks.length; i += 5) groups.push(chunks.slice(i, i + 5));
    var lines = ["Sequence:"];
    groups.forEach(function (group) {
      var indexLine = group.map(function (item) { return String(item.index).padEnd(11, " "); }).join("").trimEnd();
      var chunkLine = group.map(function (item) { return item.chunk.padEnd(11, " "); }).join("").trimEnd();
      lines.push(indexLine); lines.push(chunkLine);
    });
    lines.push("Length: " + seq.length + " residues");
    return lines.join("\n");
  }

  function refreshSequencePreview() {
    var normalized = normalizeSequence(sequenceInput.value);
    sequencePreview.textContent = formatPreview(normalized);
  }

  function sanitizeHeader(name) {
    var cleaned = String(name || "").trim().replace(/\s+/g, "_").replace(/[^A-Za-z0-9_.-]/g, "");
    return cleaned || "sequence";
  }

  function setSelectedFile(file) {
    var dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    fileNameDisplay.textContent = file.name;
  }

  // -- form building from server schema ---------------------------------------

  function buildFormFromSchema(formDef) {
    currentFormDef = formDef;
    var fi = formDef.file_input;

    fileInput.accept = fi.accept;
    fileButton.textContent = "Choose " + fi.label;
    fileUploadLabel.textContent = fi.label;
    fileHint.innerHTML = 'Upload a <code>' + fi.accept + '</code> file, or drag &amp; drop one anywhere on this card. Use the optional editor below to paste a sequence instead.';

    editorZone.style.display = formDef.show_sequence_editor ? "" : "none";

    buildParamsForm(formDef.params);
    setStatus("Ready for upload.");
  }

  function buildParamsForm(params) {
    paramsZone.innerHTML = "";
    if (!params || !params.length) {
      paramsZone.style.display = "none";
      return;
    }
    paramsZone.style.display = "";
    var html = '<p class="field-label">Parameters</p>';
    params.forEach(function (p) {
      var inputType = "text";
      if (p.type === "int" || p.type === "float") inputType = "number";
      html += '<div style="margin-bottom:0.5rem;">' +
        '<label style="display:block;font-size:0.85rem;color:var(--muted);">' + p.name + '</label>' +
        '<input class="text-input" type="' + inputType + '"' +
        ' id="param_' + p.name + '" value="' + (p.default != null ? p.default : "") + '"' +
        ' placeholder="' + (p.description || "") + '" style="width:100%;">' +
        '</div>';
    });
    paramsZone.innerHTML = html;
  }

  function isValidInputFile(file) {
    if (!currentFormDef) return true;
    var ext = currentFormDef.file_input.accept;
    return file.name.toLowerCase().endsWith(ext.toLowerCase());
  }

  // -- task type selection ---------------------------------------------------

  async function loadTaskTypes() {
    try {
      var response = await fetch("/compute/api/types");
      if (!response.ok) throw new Error("Failed to load task types");
      var taskTypes = await response.json();
      taskTypeSelect.innerHTML = "";
      taskTypes.forEach(function (tt) {
        var opt = document.createElement("option");
        opt.value = tt.name;
        opt.textContent = tt.display_name;
        taskTypeSelect.appendChild(opt);
      });
      if (taskTypes.length > 0) await fetchFormDefinition(taskTypes[0].name);
    } catch (e) {
      taskTypeSelect.innerHTML = '<option value="gremlin">PSSM-GREMLIN</option>';
      buildFormFromSchema({
        name: "gremlin",
        display_name: "PSSM-GREMLIN",
        file_input: { accept: ".fasta", label: "FASTA file", required: true },
        params: [{ name: "iter", type: "int", default: 100, description: "GREMLIN optimization iterations" }],
        show_sequence_editor: true,
      });
    }
  }

  async function fetchFormDefinition(name) {
    try {
      var response = await fetch("/compute/api/types/" + encodeURIComponent(name));
      if (!response.ok) throw new Error("Failed to load form");
      var formDef = await response.json();
      buildFormFromSchema(formDef);
    } catch (e) {
      setStatus("Could not load form for task type: " + name, "error");
    }
  }

  taskTypeSelect.addEventListener("change", function () {
    fetchFormDefinition(taskTypeSelect.value);
  });

  loadTaskTypes();

  // -- file selection --------------------------------------------------------

  fileButton.addEventListener("click", function () {
    fileInput.click();
  });

  fileInput.addEventListener("change", function () {
    if (fileInput.files && fileInput.files.length > 0) {
      fileNameDisplay.textContent = fileInput.files[0].name;
    } else {
      fileNameDisplay.textContent = "No file selected";
    }
  });

  // -- drag-and-drop ---------------------------------------------------------

  var dropZone = form.closest(".input-zone");

  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "copy";
    dropZone.classList.add("drop-highlight");
  }

  function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    if (e.target === dropZone || !dropZone.contains(e.relatedTarget)) {
      dropZone.classList.remove("drop-highlight");
    }
  }

  dropZone.addEventListener("dragover", handleDragOver);
  dropZone.addEventListener("dragenter", handleDragOver);
  dropZone.addEventListener("dragleave", handleDragLeave);
  dropZone.addEventListener("drop", function (e) {
    e.preventDefault();
    e.stopPropagation();
    dropZone.classList.remove("drop-highlight");
    var file = e.dataTransfer.files[0];
    if (!file) return;
    if (!isValidInputFile(file)) {
      var ext = currentFormDef ? currentFormDef.file_input.accept : "";
      setStatus("Only " + ext + " files are accepted.", "error");
      return;
    }
    setSelectedFile(file);
    setStatus("File ready: " + file.name + " (" + file.size + " bytes)", "ok");
  });

  document.addEventListener("dragover", function (e) { e.preventDefault(); });
  document.addEventListener("drop", function (e) { e.preventDefault(); });

  // -- theme & system --------------------------------------------------------

  clearButton.addEventListener("click", function () {
    fileInput.value = "";
    fileNameDisplay.textContent = "No file selected";
    taskNameInput.value = "";
    sequenceInput.value = "";
    refreshSequencePreview();
    setStatus("Ready for upload.");
  });

  sequenceInput.addEventListener("input", refreshSequencePreview);

  T.initToggle(document.getElementById("themeToggle"));

  if (window.matchMedia) {
    var darkMedia = window.matchMedia("(prefers-color-scheme: dark)");
    var syncToSystem = function (event) {
      if (T.getStoredThemeMode() !== "auto") return;
      document.documentElement.dataset.theme = event.matches ? "dark" : "light";
    };
    if (darkMedia.addEventListener) darkMedia.addEventListener("change", syncToSystem);
    else if (darkMedia.addListener) darkMedia.addListener(syncToSystem);
  }

  refreshSequencePreview();

  // -- submit ----------------------------------------------------------------

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var tt = currentFormDef || { name: "gremlin", file_input: { accept: ".fasta" } };
    var ext = tt.file_input.accept;
    var selectedFile = (fileInput.files && fileInput.files.length > 0) ? fileInput.files[0] : null;
    var normalizedSequence = normalizeSequence(sequenceInput.value);
    var fileToUpload = selectedFile;

    if (selectedFile && !selectedFile.name.toLowerCase().endsWith(ext.toLowerCase())) {
      setStatus("Only " + ext + " files are accepted.", "error"); return;
    }
    if (!fileToUpload && !normalizedSequence.length) {
      setStatus("Please upload a " + ext + " file or provide a sequence in the editor.", "error"); return;
    }
    if (!fileToUpload) {
      var header = sanitizeHeader(taskNameInput.value);
      fileToUpload = new File([">" + header + "\n" + wrapSequence(normalizedSequence, 80) + "\n"], header + ext, { type: "text/plain" });
    }

    var formData = new FormData();
    formData.append("file", fileToUpload);
    formData.append("task_type", tt.name);

    // Collect params from dynamically-built form
    if (tt.params) {
      tt.params.forEach(function (p) {
        var el = document.getElementById("param_" + p.name);
        if (el && el.value !== "") formData.append("params[" + p.name + "]", el.value);
      });
    }

    uploadButton.disabled = true;
    clearButton.disabled = true;
    setStatus("Uploading and queueing task...", "busy");

    try {
      var token = A.getToken();
      var headers = {};
      if (token) headers["Authorization"] = "Bearer " + token;
      var response = await fetch("/compute/api/post", { method: "POST", body: formData, headers: headers });

      if (response.ok || response.status === 202) {
        setStatus("Task submitted. Redirecting to dashboard...", "ok");
        window.location.assign("/compute/dashboard");
        return;
      }

      var isJson = (response.headers.get("Content-Type") || "").includes("application/json");
      var payload = isJson ? await response.json() : null;
      var message = (payload && (payload.error || payload.message)) || ("Upload failed (HTTP " + response.status + ")");
      if (payload && payload.details) {
        message += ": " + payload.details.map(function (d) { return d.field + " " + d.message; }).join("; ");
      }
      setStatus(message, "error");
    } catch (error) {
      setStatus("Network error: " + error.message, "error");
    } finally {
      uploadButton.disabled = false;
      clearButton.disabled = false;
    }
  });
})();
