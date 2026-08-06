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

  // -- task type state ---------------------------------------------------------

  var taskTypes = [];
  var currentTaskType = null;

  function findTaskType(name) {
    for (var i = 0; i < taskTypes.length; i++) {
      if (taskTypes[i].name === name) return taskTypes[i];
    }
    return null;
  }

  function buildParamsForm(tt) {
    paramsZone.innerHTML = "";
    if (!tt.params || !tt.params.length) {
      paramsZone.style.display = "none";
      return;
    }
    paramsZone.style.display = "";
    var html = '<p class="field-label">Parameters</p>';
    tt.params.forEach(function (p) {
      html += '<div style="margin-bottom:0.5rem;">' +
        '<label style="display:block;font-size:0.85rem;color:var(--muted);">' + p.name + '</label>' +
        '<input class="text-input" type="' + (p.type === "int" || p.type === "float" ? "number" : "text") + '"' +
        ' id="param_' + p.name + '" value="' + (p.default != null ? p.default : "") + '"' +
        ' placeholder="' + (p.description || "") + '" style="width:100%;">' +
        '</div>';
    });
    paramsZone.innerHTML = html;
  }

  function onTaskTypeChange() {
    var name = taskTypeSelect.value;
    var tt = findTaskType(name);
    currentTaskType = tt;
    if (!tt) return;

    // Update file input accept and labels
    var ext = tt.input_extension || "";
    fileInput.accept = ext;
    fileButton.textContent = "Choose " + (tt.input_label || "file");
    fileUploadLabel.textContent = tt.input_label || "File Upload";
    fileHint.innerHTML = 'Upload a <code>' + ext + '</code> file, or drag &amp; drop one anywhere on this card. Use the optional editor below to paste a sequence instead.';

    // Show/hide sequence editor (ponytail: show for .fasta-like inputs, hide otherwise)
    if (ext === ".fasta") {
      editorZone.style.display = "";
    } else {
      editorZone.style.display = "none";
    }

    buildParamsForm(tt);
    setStatus("Ready for upload.");
  }

  taskTypeSelect.addEventListener("change", onTaskTypeChange);

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

  function isValidInputFile(file) {
    var ext = currentTaskType ? currentTaskType.input_extension : ".fasta";
    return file.name.toLowerCase().endsWith(ext.toLowerCase());
  }

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
      var ext = currentTaskType ? currentTaskType.input_extension : ".fasta";
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

  // -- load task types -------------------------------------------------------

  async function loadTaskTypes() {
    try {
      var response = await fetch("/compute/api/types");
      if (!response.ok) {
        taskTypeSelect.innerHTML = '<option value="gremlin">PSSM-GREMLIN</option>';
        currentTaskType = { name: "gremlin", input_extension: ".fasta", input_label: "FASTA file", params: [] };
        buildParamsForm(currentTaskType);
        return;
      }
      taskTypes = await response.json();
      taskTypeSelect.innerHTML = "";
      taskTypes.forEach(function (tt) {
        var opt = document.createElement("option");
        opt.value = tt.name;
        opt.textContent = tt.display_name;
        taskTypeSelect.appendChild(opt);
      });
      if (taskTypes.length > 0) onTaskTypeChange();
    } catch (e) {
      taskTypeSelect.innerHTML = '<option value="gremlin">PSSM-GREMLIN</option>';
      currentTaskType = { name: "gremlin", input_extension: ".fasta", input_label: "FASTA file", params: [] };
      buildParamsForm(currentTaskType);
    }
  }

  loadTaskTypes();

  // -- submit ----------------------------------------------------------------

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var tt = currentTaskType || { name: "gremlin", input_extension: ".fasta" };
    var ext = tt.input_extension || ".fasta";
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

    // Collect params
    if (tt.params) {
      tt.params.forEach(function (p) {
        var el = document.getElementById("param_" + p.name);
        if (el && el.value !== "") formData.append("param_" + p.name, el.value);
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
      setStatus(message, "error");
    } catch (error) {
      setStatus("Network error: " + error.message, "error");
    } finally {
      uploadButton.disabled = false;
      clearButton.disabled = false;
    }
  });
})();
