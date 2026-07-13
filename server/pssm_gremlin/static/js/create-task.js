/* REvoDesign GREMLIN Server — Create Task page logic */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;

  var form = document.getElementById("uploadForm");
  var fileInput = document.getElementById("fileInput");
  var fileNameDisplay = document.getElementById("fileNameDisplay");
  var taskNameInput = document.getElementById("taskNameInput");
  var sequenceInput = document.getElementById("sequenceInput");
  var sequencePreview = document.getElementById("sequencePreview");
  var statusDiv = document.getElementById("uploadStatus");
  var clearButton = document.getElementById("clearButton");
  var uploadButton = document.getElementById("uploadButton");

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

  fileInput.addEventListener("change", function () {
    if (fileInput.files && fileInput.files.length > 0) {
      fileNameDisplay.textContent = fileInput.files[0].name;
    } else {
      fileNameDisplay.textContent = "No file selected";
    }
  });

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

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var selectedFile = (fileInput.files && fileInput.files.length > 0) ? fileInput.files[0] : null;
    var normalizedSequence = normalizeSequence(sequenceInput.value);
    var fileToUpload = selectedFile;

    if (selectedFile && !selectedFile.name.toLowerCase().endsWith(".fasta")) {
      setStatus("Only .fasta files are accepted.", "error"); return;
    }
    if (!fileToUpload && !normalizedSequence.length) {
      setStatus("Please upload a .fasta file or provide a sequence in the editor.", "error"); return;
    }
    if (!fileToUpload) {
      var header = sanitizeHeader(taskNameInput.value);
      fileToUpload = new File([">" + header + "\n" + wrapSequence(normalizedSequence, 80) + "\n"], header + ".fasta", { type: "text/plain" });
    }

    var formData = new FormData();
    formData.append("file", fileToUpload);
    uploadButton.disabled = true;
    clearButton.disabled = true;
    setStatus("Uploading and queueing task...", "busy");

    try {
      var token = A.getToken();
      var headers = {};
      if (token) headers["Authorization"] = "Bearer " + token;
      var response = await fetch("/PSSM_GREMLIN/api/post", { method: "POST", body: formData, headers: headers });

      if (response.ok || response.status === 202) {
        setStatus("Task submitted. Redirecting to dashboard...", "ok");
        window.location.assign("/PSSM_GREMLIN/dashboard");
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
