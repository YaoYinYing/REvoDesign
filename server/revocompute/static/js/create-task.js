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

  function setSelectedFiles(files) {
    var dt = new DataTransfer();
    Array.from(files).forEach(function (file) { dt.items.add(file); });
    fileInput.files = dt.files;
    fileNameDisplay.textContent = Array.from(files).map(function (file) {
      return file.webkitRelativePath || file.name;
    }).join(", ");
    refreshStructureSnapshot();
  }

  // -- form building from server schema ---------------------------------------

  function buildFormFromSchema(formDef) {
    currentFormDef = formDef;
    var fi = formDef.file_input;

    fileInput.accept = fi.accept;
    fileInput.multiple = Boolean(fi.multiple);
    fileButton.textContent = "Choose " + fi.label;
    fileUploadLabel.textContent = fi.label;
    fileHint.innerHTML = 'Upload ' + (fi.multiple ? "up to " + fi.max_files + " files; the first selected file is primary" : "one file") +
      ' matching <code>' + fi.accept + '</code>. Selected paths are copied into an immutable task snapshot.';

    editorZone.style.display = formDef.show_sequence_editor ? "" : "none";

    buildParamsForm(formDef.params);
    refreshStructureSnapshot();
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
      var label = p.label || p.name;
      html += '<div class="param-field">' +
        '<label class="param-label" for="param_' + p.name + '">' + label + (p.unit ? " (" + p.unit + ")" : "") + '</label>';
      if (p.choices && p.choices.length) {
        html += '<select class="text-input" id="param_' + p.name + '">' + p.choices.map(function (choice) {
          return '<option value="' + choice + '"' + (choice === p.default ? ' selected' : '') + '>' + choice + '</option>';
        }).join("") + '</select>';
      } else if (p.type === "bool") {
        html += '<select class="text-input" id="param_' + p.name + '">' +
          '<option value="true"' + (p.default === true ? ' selected' : '') + '>Yes</option>' +
          '<option value="false"' + (p.default === false ? ' selected' : '') + '>No</option></select>';
      } else {
        var inputType = (p.type === "int" || p.type === "float") ? "number" : "text";
        html += '<input class="text-input" type="' + inputType + '" id="param_' + p.name + '"' +
          ' value="' + (p.default != null ? p.default : "") + '"' +
          (p.minimum != null ? ' min="' + p.minimum + '"' : '') +
          (p.maximum != null ? ' max="' + p.maximum + '"' : '') +
          (p.step != null ? ' step="' + p.step + '"' : '') +
          (p.required ? ' required' : '') + '>';
      }
      html += '<p class="param-help">' + (p.description || "") + '</p></div>';
    });
    paramsZone.innerHTML = html;
  }

  function isValidInputFile(file) {
    if (!currentFormDef) return true;
    var extensions = currentFormDef.file_input.extensions || currentFormDef.file_input.accept.split(",");
    return extensions.some(function (ext) { return file.name.toLowerCase().endsWith(ext.toLowerCase()); });
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
      fileNameDisplay.textContent = Array.from(fileInput.files).map(function (file) {
        return file.webkitRelativePath || file.name;
      }).join(", ");
    } else {
      fileNameDisplay.textContent = "No file selected";
    }
    refreshStructureSnapshot();
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
    var files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;
    if (!currentFormDef.file_input.multiple && files.length > 1) {
      setStatus("This task type accepts exactly one input file.", "error");
      return;
    }
    if (files.length > currentFormDef.file_input.max_files || files.some(function (file) { return !isValidInputFile(file); })) {
      setStatus("Check the accepted extensions and maximum input count.", "error");
      return;
    }
    setSelectedFiles(files);
    setStatus(files.length + " input file(s) ready for snapshot.", "ok");
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
    refreshStructureSnapshot();
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
    var ext = (tt.file_input.extensions || [tt.file_input.accept])[0];
    var selectedFiles = (fileInput.files && fileInput.files.length > 0) ? Array.from(fileInput.files) : [];
    var normalizedSequence = normalizeSequence(sequenceInput.value);
    if (selectedFiles.some(function (file) { return !isValidInputFile(file); })) {
      setStatus("One or more selected files has an unsupported extension.", "error"); return;
    }
    var primaryExtensions = tt.file_input.primary_extensions || [ext];
    if (selectedFiles.length && !primaryExtensions.some(function (candidate) {
      return selectedFiles[0].name.toLowerCase().endsWith(candidate.toLowerCase());
    })) {
      setStatus("The first selected file must be a primary input: " + primaryExtensions.join(", "), "error"); return;
    }
    if (!selectedFiles.length && !normalizedSequence.length) {
      setStatus("Please upload a " + ext + " file or provide a sequence in the editor.", "error"); return;
    }
    if (!selectedFiles.length) {
      var header = sanitizeHeader(taskNameInput.value);
      selectedFiles = [new File([">" + header + "\n" + wrapSequence(normalizedSequence, 80) + "\n"], header + ext, { type: "text/plain" })];
    }

    var formData = new FormData();
    selectedFiles.forEach(function (file) {
      formData.append("files", file);
      formData.append("input_paths", file.webkitRelativePath || file.name);
    });
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

  // -- local structure summary (no third-party scripts or upload) ------------

  function showStructureSnapshot(file) {
    var snap = document.getElementById("structureSnapshot");
    var viewport = document.getElementById("molstarViewport");
    var checklist = document.getElementById("submissionChecklist");
    if (!snap || !viewport) return;
    snap.style.display = "";
    if (checklist) checklist.style.display = "none";

    viewport.textContent = "Reading structure…";
    file.text().then(function (text) {
      var lines = text.split(/\r?\n/);
      var atoms = 0;
      var heteroAtoms = 0;
      var chains = new Set();
      var residues = new Set();
      lines.forEach(function (line) {
        if (line.startsWith("ATOM  ") || line.startsWith("HETATM")) {
          if (line.startsWith("ATOM  ")) atoms += 1;
          else heteroAtoms += 1;
          var chain = line.slice(21, 22).trim() || "(blank)";
          chains.add(chain);
          residues.add(chain + ":" + line.slice(22, 27).trim());
        }
      });
      var summary = [
        file.name,
        "Size: " + file.size + " bytes",
        "ATOM records: " + atoms,
        "HETATM records: " + heteroAtoms,
        "Residues: " + residues.size,
        "Chains: " + (chains.size ? Array.from(chains).join(", ") : "not detected"),
      ];
      if (!atoms && !heteroAtoms) summary.push("No PDB coordinate records detected; the runner will validate this file.");
      viewport.textContent = summary.join("\n");
    }).catch(function () { viewport.textContent = "Could not read this structure locally."; });
  }

  function hideStructureSnapshot() {
    var snap = document.getElementById("structureSnapshot");
    var checklist = document.getElementById("submissionChecklist");
    if (snap) snap.style.display = "none";
    if (checklist) checklist.style.display = "";
  }

  function refreshStructureSnapshot() {
    var extensions = currentFormDef ? currentFormDef.file_input.extensions || [] : [];
    var file = fileInput.files && fileInput.files.length > 0 ? fileInput.files[0] : null;
    if (extensions.includes(".pdb") && file && file.name.toLowerCase().endsWith(".pdb")) showStructureSnapshot(file);
    else hideStructureSnapshot();
  }
})();
