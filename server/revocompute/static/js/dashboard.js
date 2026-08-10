/* REvoCompute — Dashboard page logic */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;

  var allTasks = window.__DASHBOARD_TASKS__;
  var isAdmin = window.__DASHBOARD_IS_ADMIN__;

  var state = {
    query: "",
    filter: "all",
    selected: new Set(),
  };
  var downloads = new Map();
  var activeErrorButton = null;

  var statusMap = {
    "pending": { label: "Pending", css: "status-pending", accent: "var(--pending)" },
    "running": { label: "Running", css: "status-running", accent: "var(--running)" },
    "finished": { label: "Finished", css: "status-finished", accent: "var(--finished)" },
    "failed": { label: "Failed", css: "status-failed", accent: "var(--failed)" },
    "cancelled": { label: "Cancelled", css: "status-cancelled", accent: "var(--cancelled)" },
    "deleting:finished": { label: "Deleting (Finished)", css: "status-deleted", accent: "var(--deleted)" },
    "deleting:cancel": { label: "Deleting (Cancel)", css: "status-deleted", accent: "var(--deleted)" },
    "cleaned:finished": { label: "Cleaned (Finished)", css: "status-deleted", accent: "var(--deleted)" },
    "cleaned:cancel": { label: "Cleaned (Cancel)", css: "status-deleted", accent: "var(--deleted)" },
    "deleted:finshed": { label: "Deleted (Finished)", css: "status-deleted", accent: "var(--deleted)" },
    "deleted:cancel": { label: "Deleted (Cancel)", css: "status-deleted", accent: "var(--deleted)" },
  };

  function getStatusMeta(status) {
    return statusMap[status] || { label: status || "Unknown", css: "status-cancelled", accent: "var(--cancelled)" };
  }

  function getStatusTrace(task) {
    if (task.status !== "running") return "";
    return task.running_trace || "";
  }

  function parseStatusTrace(traceText) {
    var lines = String(traceText || "").split(/\n+/).map(function (l) { return l.trim(); }).filter(Boolean);
    return lines.map(function (line) {
      var match = line.match(/^(.*?)(?:\s*\[(done|running|pending)\])?$/i);
      var label = (match ? match[1] : line).trim() || "-";
      var marker = (match && match[2]) ? match[2].toLowerCase() : "pending";
      return { label: label, marker: (marker === "done" || marker === "running" || marker === "pending") ? marker : "pending" };
    });
  }

  function renderStatusTracePopover(traceText) {
    var stages = parseStatusTrace(traceText);
    if (!stages.length) return "";
    var stageRows = stages.map(function (stage, index) {
      var hasNext = index < stages.length - 1;
      return '<div class="status-trace-stage stage-' + stage.marker + '">' +
        '<span class="status-trace-track ' + (hasNext ? "has-next" : "") + '">' +
        '<span class="status-trace-node" aria-hidden="true"></span></span>' +
        '<span class="status-trace-text">' + escapeHtml(stage.label) + '</span></div>';
    }).join("");
    return '<span class="status-trace-popover" role="tooltip"><span class="status-trace-list">' + stageRows + '</span></span>';
  }

  function showToast(message, type) {
    type = type || "info";
    var wrap = document.getElementById("toastWrap");
    var node = document.createElement("div");
    node.className = "toast " + type;
    node.textContent = message;
    wrap.appendChild(node);
    setTimeout(function () { node.remove(); }, 3600);
  }

  function updateSummary() {
    var counts = { total: allTasks.length, pending: 0, running: 0, finished: 0, failed: 0, cancelled: 0, deleted: 0 };
    allTasks.forEach(function (task) {
      if (task.status === "pending") counts.pending += 1;
      if (task.status === "running") counts.running += 1;
      if (task.status === "finished") counts.finished += 1;
      if (task.status === "failed") counts.failed += 1;
      if (task.status === "cancelled") counts.cancelled += 1;
      if (task.status === "deleting:finished" || task.status === "deleting:cancel" ||
          task.status === "cleaned:finished" || task.status === "cleaned:cancel" ||
          task.status === "deleted:finshed" || task.status === "deleted:cancel") counts.deleted += 1;
    });
    document.getElementById("totalTasks").textContent = counts.total;
    document.getElementById("inQueue").textContent = counts.pending;
    document.getElementById("inRunning").textContent = counts.running;
    document.getElementById("finished").textContent = counts.finished;
    document.getElementById("issues").textContent = counts.failed + counts.cancelled + counts.deleted;
  }

  function updateAdminTools() {
    var tools = document.getElementById("adminTools");
    if (!tools) return;
    var hasDeletable = allTasks.some(function (task) { return Boolean(task.can_delete); });
    if (!hasDeletable) { tools.hidden = true; return; }
    tools.hidden = false;
    var btn = document.getElementById("deleteSelectedBtn");
    var count = state.selected.size;
    btn.textContent = "Delete Selected (" + count + ")";
    btn.disabled = count === 0;
  }

  function getFilteredTasks() {
    var query = state.query.trim().toLowerCase();
    return allTasks.filter(function (task) {
      if (state.filter !== "all" && task.status !== state.filter) return false;
      if (!query) return true;
      var haystack = [task.fasta_fn, task.md5, task.status, task.sequence, task.submitted_time, task.finished_time].join(" ").toLowerCase();
      return haystack.includes(query);
    });
  }

  function downloadButtonContent(phase) {
    if (phase === "started") {
      return { label: "Download started", detail: "See browser downloads" };
    }
    return { label: "Preparing download…", detail: "Checking access…" };
  }

  function downloadButtonHtml(task, downloadClass) {
    var phase = downloads.get(task.md5);
    if (!phase) {
      return '<button class="task-btn ' + downloadClass + '" data-action="download" data-md5="' +
        escapeHtml(task.md5) + '">Download</button>';
    }
    var content = downloadButtonContent(phase);
    return '<button class="task-btn ' + downloadClass + ' download-progress' +
      '" data-action="download" data-md5="' + escapeHtml(task.md5) + '" disabled aria-busy="true" aria-label="' +
      escapeHtml(content.label + " " + content.detail) + '">' +
      '<span class="download-label">' + escapeHtml(content.label) + '</span>' +
      '<span class="download-detail">' + escapeHtml(content.detail) + '</span></button>';
  }

  function updateDownloadButton(md5sum) {
    var phase = downloads.get(md5sum);
    document.querySelectorAll("button[data-action='download']").forEach(function (button) {
      if (button.dataset.md5 !== md5sum) return;
      if (!phase) {
        button.disabled = false;
        button.removeAttribute("aria-busy");
        button.removeAttribute("aria-label");
        button.classList.remove("download-progress");
        button.textContent = "Download";
        return;
      }
      var content = downloadButtonContent(phase);
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.setAttribute("aria-label", content.label + " " + content.detail);
      button.classList.add("download-progress");
      button.replaceChildren();
      var label = document.createElement("span");
      label.className = "download-label";
      label.textContent = content.label;
      var detail = document.createElement("span");
      detail.className = "download-detail";
      detail.textContent = content.detail;
      button.append(label, detail);
    });
  }

  function renderTasks() {
    var list = document.getElementById("taskList");
    var tasks = getFilteredTasks();
    closeErrorBubbles();
    updateAdminTools();
    if (!tasks.length) {
      list.innerHTML = '<div class="empty">No tasks match the current search/filter criteria.</div>';
      return;
    }
    list.innerHTML = "";
    tasks.forEach(function (task, index) {
      var meta = getStatusMeta(task.status);
      var card = document.createElement("article");
      card.className = "task-card";
      card.style.setProperty("--accent-stripe", meta.accent);
      card.style.animationDelay = Math.min(index * 35, 260) + "ms";
      var hasResults = task.status === "finished" || task.status === "failed";
      var canCancel = task.status === "pending" || task.status === "running";
      var canDelete = Boolean(task.can_delete);
      var hasError = task.status === "failed" && task.error;
      var selected = state.selected.has(task.md5);
      var statusTrace = getStatusTrace(task);
      var traceClass = statusTrace ? "has-trace" : "";
      var traceAttr = statusTrace ? ' tabindex="0" aria-haspopup="true"' : "";
      var tracePopover = statusTrace ? renderStatusTracePopover(statusTrace) : "";
      var errorHelp =
        hasError
          ? '<span class="error-help">' +
              '<button class="error-indicator" type="button" data-action="toggle-error" data-md5="' + escapeHtml(task.md5) + '" aria-label="Show runner log" aria-expanded="false" aria-controls="taskErrorPopover">?</button>' +
            '</span>'
          : "";

      card.innerHTML =
        '<header class="task-head">' +
          '<div class="task-head-left">' +
            (canDelete ? '<label class="task-select-wrap" title="Select task for batch delete"><input class="task-select" type="checkbox" data-action="toggle-select" data-md5="' + escapeHtml(task.md5) + '" ' + (selected ? "checked" : "") + '></label>' : "") +
            '<div>' +
              '<h2 class="task-title">' + escapeHtml(task.fasta_fn || "Unknown file") + '</h2>' +
              '<span class="task-type-badge">' + escapeHtml(task.task_type || "gremlin") + '</span>' +
              '<p class="task-id">' + escapeHtml(task.md5) + '</p>' +
              (isAdmin ? '<span class="owner-chip">Owner: ' + escapeHtml(task.owner || "-") + '</span>' : "") +
            '</div>' +
          '</div>' +
          '<div class="task-status-tools">' +
            '<span class="status-pill ' + meta.css + ' ' + traceClass + '"' + traceAttr + '>' + escapeHtml(meta.label) + tracePopover + '</span>' +
            errorHelp +
          '</div>' +
        '</header>' +
        '<div class="meta-grid">' +
          '<div class="meta-box"><p class="meta-label">Submitted</p><p class="meta-value">' + escapeHtml(task.submitted_time || "-") + '</p></div>' +
          '<div class="meta-box"><p class="meta-label">Finished</p><p class="meta-value">' + escapeHtml(task.finished_time || "-") + '</p></div>' +
          '<div class="meta-box"><p class="meta-label">Wall Time</p><p class="meta-value">' + escapeHtml(String(task.walltime ?? "-")) + '</p></div>' +
        '</div>' +
        '<details class="sequence"><summary>Sequence Snapshot</summary><pre>' + escapeHtml(task.sequence || "-") + '</pre></details>' +
        (hasResults ? '<section class="result-browser" data-results-for="' + escapeHtml(task.md5) + '" hidden></section>' : "") +
        '<div class="actions">' +
          (hasResults ? '<button class="task-btn download" data-action="results" data-md5="' + escapeHtml(task.md5) + '">Browse Results</button>' : "") +
          (hasResults ? downloadButtonHtml(task, task.status === "failed" ? "download-failed" : "download") : "") +
          (canCancel ? '<button class="task-btn cancel" data-action="cancel" data-md5="' + escapeHtml(task.md5) + '">Cancel</button>' : "") +
          (canDelete ? '<button class="task-btn delete" data-action="delete" data-md5="' + escapeHtml(task.md5) + '">Delete</button>' : "") +
        '</div>';
      list.appendChild(card);
    });
  }

  function setActiveFilter(nextFilter) {
    state.filter = nextFilter;
    var chips = document.querySelectorAll("#statusFilters .chip");
    chips.forEach(function (chip) { chip.classList.toggle("active", chip.dataset.filter === nextFilter); });
    renderTasks();
  }

  function closeErrorBubbles() {
    document.querySelectorAll(".error-help.open").forEach(function (node) {
      node.classList.remove("open");
      var btn = node.querySelector(".error-indicator");
      if (btn) btn.setAttribute("aria-expanded", "false");
    });
    var popover = document.getElementById("taskErrorPopover");
    if (popover) {
      popover.hidden = true;
      popover.classList.remove("open", "above");
    }
    activeErrorButton = null;
  }

  function ensureErrorPopover() {
    var popover = document.getElementById("taskErrorPopover");
    if (popover) return popover;
    popover = document.createElement("div");
    popover.id = "taskErrorPopover";
    popover.className = "error-popover error-popover-floating";
    popover.setAttribute("role", "tooltip");
    popover.hidden = true;
    popover.innerHTML =
      '<span class="error-popover-header">' +
        '<span class="error-popover-title">Runner log</span>' +
        '<button class="error-copy-btn" type="button" data-action="copy-error" aria-label="Copy runner log">Copy</button>' +
      '</span>' +
      '<span class="error-popover-message"></span>';
    document.body.appendChild(popover);
    return popover;
  }

  function positionErrorPopover(triggerButton, popover) {
    var rect = triggerButton.getBoundingClientRect();
    var top = Math.max(12, rect.bottom + 10);
    var right = Math.max(12, window.innerWidth - rect.right);
    var availableHeight = window.innerHeight - top - 12;
    if (availableHeight < 180 && rect.top > availableHeight) {
      availableHeight = rect.top - 22;
      popover.style.top = "auto";
      popover.style.bottom = Math.max(12, window.innerHeight - rect.top + 10) + "px";
      popover.classList.add("above");
    } else {
      popover.style.top = top + "px";
      popover.style.bottom = "auto";
      popover.classList.remove("above");
    }
    popover.style.right = right + "px";
    popover.style.maxHeight = Math.max(160, Math.min(420, availableHeight)) + "px";
  }

  function toggleErrorBubble(triggerButton) {
    var wrap = triggerButton.closest(".error-help");
    if (!wrap) return;
    var nextOpen = activeErrorButton !== triggerButton;
    closeErrorBubbles();
    if (nextOpen) {
      var task = allTasks.find(function (item) { return item.md5 === triggerButton.dataset.md5; });
      if (!task || !task.error) return;
      var popover = ensureErrorPopover();
      var messageNode = popover.querySelector(".error-popover-message");
      if (messageNode) {
        messageNode.textContent = task.error;
        messageNode.scrollTop = 0;
      }
      popover.scrollTop = 0;
      wrap.classList.add("open");
      triggerButton.setAttribute("aria-expanded", "true");
      popover.hidden = false;
      popover.classList.add("open");
      positionErrorPopover(triggerButton, popover);
      activeErrorButton = triggerButton;
    }
  }

  function copyTextToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      textarea.style.top = "0";
      document.body.appendChild(textarea);
      textarea.select();
      try {
        if (!document.execCommand("copy")) throw new Error("Copy command failed");
        resolve();
      } catch (error) {
        reject(error);
      } finally {
        document.body.removeChild(textarea);
      }
    });
  }

  async function copyActiveError(copyButton) {
    var popover = document.getElementById("taskErrorPopover");
    var messageNode = popover ? popover.querySelector(".error-popover-message") : null;
    var text = messageNode ? messageNode.textContent : "";
    if (!text) return;
    var originalLabel = copyButton.textContent;
    try {
      copyButton.disabled = true;
      await copyTextToClipboard(text);
      copyButton.textContent = "Copied";
      copyButton.classList.add("copied");
      setTimeout(function () {
        copyButton.textContent = originalLabel;
        copyButton.classList.remove("copied");
        copyButton.disabled = false;
      }, 1400);
    } catch (_) {
      copyButton.disabled = false;
      showToast("Could not copy runner log.", "error");
    }
  }

  async function waitForArchive(md5sum) {
    for (var attempt = 0; attempt < 120; attempt += 1) {
      var result = await A.authFetch("/compute/api/results/" + encodeURIComponent(md5sum));
      if (!result.ok) throw new Error("Could not read result manifest");
      var manifest = await result.json();
      if (manifest.archive && manifest.archive.ready) return manifest.archive.download_url;
      await new Promise(function (resolve) { setTimeout(resolve, 5000); });
    }
    throw new Error("Archive is still building. You can leave this page and try again later.");
  }

  async function downloadFile(md5sum) {
    if (!md5sum || downloads.has(md5sum)) return;
    downloads.set(md5sum, "preparing");
    updateDownloadButton(md5sum);
    try {
      var requestUrl = "/compute/api/results/" + encodeURIComponent(md5sum) + "/archive";
      var requestResponse = await A.authFetch(requestUrl, { method: "POST" });
      var requestPayload = await requestResponse.json().catch(function () { return {}; });
      if (!requestResponse.ok && requestResponse.status !== 202) throw new Error(requestPayload.error || "Archive request failed");
      var url = requestPayload.download_url || await waitForArchive(md5sum);
      downloads.set(md5sum, "started");
      updateDownloadButton(md5sum);
      var a = document.createElement("a");
      a.href = url;
      a.download = "";
      a.hidden = true;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () {
        downloads.delete(md5sum);
        updateDownloadButton(md5sum);
      }, 1800);
    } catch (error) {
      downloads.delete(md5sum);
      updateDownloadButton(md5sum);
      showToast(error.message || "Download failed", "error");
    }
  }

  function formatBytes(value) {
    var bytes = Number(value || 0);
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KiB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MiB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GiB";
  }

  function renderStructurePreview(text, artifact, previewNode) {
    var points = String(text).split(/\r?\n/).filter(function (line) {
      return line.startsWith("ATOM  ") && line.slice(12, 16).trim() === "CA";
    }).map(function (line) {
      return {
        chain: line.slice(21, 22).trim() || "_",
        x: Number(line.slice(30, 38)),
        y: Number(line.slice(38, 46)),
        z: Number(line.slice(46, 54)),
      };
    }).filter(function (point) { return Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z); });
    if (points.length < 2) {
      var fallback = document.createElement("pre");
      fallback.textContent = text + (artifact.size > 262144 ? "\n\n[Preview truncated at 256 KiB]" : "");
      previewNode.appendChild(fallback);
      return;
    }
    var canvas = document.createElement("canvas");
    canvas.className = "artifact-structure-preview";
    canvas.width = 960;
    canvas.height = 420;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", "Alpha-carbon trace preview for " + artifact.path);
    previewNode.appendChild(canvas);
    var context = canvas.getContext("2d");
    var xs = points.map(function (point) { return point.x; });
    var ys = points.map(function (point) { return point.y; });
    var minX = Math.min.apply(Math, xs); var maxX = Math.max.apply(Math, xs);
    var minY = Math.min.apply(Math, ys); var maxY = Math.max.apply(Math, ys);
    var scale = Math.min(880 / Math.max(maxX - minX, 1), 340 / Math.max(maxY - minY, 1));
    var colors = ["#0f6f8f", "#c06035", "#4d8b57", "#8b5fb3", "#b08a20", "#b3485d"];
    var chainColors = new Map();
    context.fillStyle = "#f5f8f7"; context.fillRect(0, 0, canvas.width, canvas.height);
    context.lineWidth = 3; context.lineJoin = "round"; context.lineCap = "round";
    var previous = null;
    points.forEach(function (point) {
      if (!chainColors.has(point.chain)) chainColors.set(point.chain, colors[chainColors.size % colors.length]);
      var px = 40 + (point.x - minX) * scale;
      var py = 380 - (point.y - minY) * scale;
      if (previous && previous.chain === point.chain) {
        context.strokeStyle = chainColors.get(point.chain);
        context.beginPath(); context.moveTo(previous.px, previous.py); context.lineTo(px, py); context.stroke();
      }
      previous = { chain: point.chain, px: px, py: py };
    });
    var caption = document.createElement("p");
    caption.className = "artifact-structure-caption";
    caption.textContent = points.length + " alpha carbons · chains " + Array.from(chainColors.keys()).join(", ") + " · XY projection";
    previewNode.appendChild(caption);
  }

  function parseDelimitedRows(text, delimiter, maxRows, maxColumns) {
    var rows = []; var row = []; var value = ""; var quoted = false;
    for (var index = 0; index < text.length && rows.length < maxRows; index += 1) {
      var character = text[index];
      if (quoted) {
        if (character === '"' && text[index + 1] === '"') { value += '"'; index += 1; }
        else if (character === '"') quoted = false;
        else value += character;
      } else if (character === '"') quoted = true;
      else if (character === delimiter) {
        if (row.length < maxColumns) row.push(value);
        value = "";
      } else if (character === "\n") {
        if (row.length < maxColumns) row.push(value.replace(/\r$/, ""));
        rows.push(row); row = []; value = "";
      } else value += character;
    }
    if ((value || row.length) && rows.length < maxRows) {
      if (row.length < maxColumns) row.push(value.replace(/\r$/, ""));
      rows.push(row);
    }
    return rows;
  }

  function renderTablePreview(text, artifact, previewNode) {
    var delimiter = artifact.path.toLowerCase().endsWith(".tsv") ? "\t" : ",";
    var rows = parseDelimitedRows(text, delimiter, 101, 50);
    if (!rows.length) { previewNode.textContent = "This table is empty."; return; }
    var wrapper = document.createElement("div");
    wrapper.className = "artifact-table-wrap";
    var table = document.createElement("table");
    table.className = "artifact-table-preview";
    rows.forEach(function (values, rowIndex) {
      var tableRow = document.createElement("tr");
      values.forEach(function (value) {
        var cell = document.createElement(rowIndex === 0 ? "th" : "td");
        cell.textContent = value;
        tableRow.appendChild(cell);
      });
      table.appendChild(tableRow);
    });
    wrapper.appendChild(table);
    previewNode.appendChild(wrapper);
    if (rows.length === 101 || artifact.size > 262144) {
      var note = document.createElement("p");
      note.className = "artifact-structure-caption";
      note.textContent = "Preview limited to 101 rows, 50 columns, and 256 KiB.";
      previewNode.appendChild(note);
    }
  }

  async function previewArtifact(button, artifact, previewNode) {
    previewNode.replaceChildren();
    if (!artifact.preview) {
      previewNode.textContent = "No inline preview is available for this file type.";
      return;
    }
    try {
      var response = await A.authFetch(artifact.url, { headers: { "Range": "bytes=0-262143" } });
      if (!response.ok && response.status !== 206) throw new Error("Preview unavailable");
      if (artifact.preview === "image") {
        var blob = await response.blob();
        var image = document.createElement("img");
        image.className = "artifact-image-preview";
        image.alt = artifact.path;
        image.src = URL.createObjectURL(blob);
        image.addEventListener("load", function () { URL.revokeObjectURL(image.src); }, { once: true });
        previewNode.appendChild(image);
      } else {
        var text = await response.text();
        if (artifact.preview === "structure") renderStructurePreview(text, artifact, previewNode);
        else if (artifact.preview === "table") renderTablePreview(text, artifact, previewNode);
        else {
          var pre = document.createElement("pre");
          pre.textContent = text + (artifact.size > 262144 ? "\n\n[Preview truncated at 256 KiB]" : "");
          previewNode.appendChild(pre);
        }
      }
      button.setAttribute("aria-expanded", "true");
    } catch (error) {
      previewNode.textContent = error.message || "Preview unavailable";
    }
  }

  async function openResults(md5sum) {
    var panel = document.querySelector('[data-results-for="' + CSS.escape(md5sum) + '"]');
    if (!panel) return;
    if (!panel.hidden) { panel.hidden = true; return; }
    panel.hidden = false;
    panel.textContent = "Loading finalized result tree…";
    try {
      var response = await A.authFetch("/compute/api/results/" + encodeURIComponent(md5sum));
      var manifest = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(manifest.message || "Could not load results");
      panel.replaceChildren();
      var summary = document.createElement("p");
      summary.className = "result-summary";
      summary.textContent = manifest.artifacts.length + " files · " + formatBytes(manifest.total_size);
      panel.appendChild(summary);
      var tree = document.createElement("ul");
      tree.className = "artifact-tree";
      manifest.artifacts.forEach(function (artifact) {
        var row = document.createElement("li");
        var previewButton = document.createElement("button");
        previewButton.type = "button";
        previewButton.className = "artifact-preview-button";
        previewButton.textContent = artifact.path + " · " + formatBytes(artifact.size);
        previewButton.disabled = !artifact.preview;
        previewButton.setAttribute("aria-expanded", "false");
        var download = document.createElement("a");
        download.className = "artifact-download";
        download.href = artifact.url + "?download=1";
        download.textContent = "Download";
        var preview = document.createElement("div");
        preview.className = "artifact-preview";
        previewButton.addEventListener("click", function () { previewArtifact(previewButton, artifact, preview); });
        row.append(previewButton, download, preview);
        tree.appendChild(row);
      });
      panel.appendChild(tree);
    } catch (error) {
      panel.textContent = error.message || "Could not load results";
    }
  }

  function removeTaskFromClientState(md5sum) {
    var index = allTasks.findIndex(function (task) { return task.md5 === md5sum; });
    if (index >= 0) allTasks.splice(index, 1);
    state.selected.delete(md5sum);
  }

  async function cancelFile(md5sum, triggerButton) {
    if (!md5sum) return;
    try {
      if (triggerButton) { triggerButton.disabled = true; triggerButton.textContent = "Cancelling..."; }
      var response = await A.authFetch("/compute/api/cancel/" + encodeURIComponent(md5sum), { method: "POST" });
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(payload.error || "Failed to cancel task.");
      var target = allTasks.find(function (t) { return t.md5 === md5sum; });
      if (target) {
        target.status = "cancelled";
        target.finished_time = target.finished_time === "-" ? new Date().toLocaleString() : target.finished_time;
      }
      updateSummary(); renderTasks();
      showToast("Task " + md5sum.slice(0, 8) + "... cancelled.", "info");
    } catch (error) {
      if (triggerButton) { triggerButton.disabled = false; triggerButton.textContent = "Cancel"; }
      showToast(error.message || "Cancel request failed.", "error");
    }
  }

  async function deleteFile(md5sum, triggerButton) {
    if (!md5sum) return;
    if (!window.confirm("Delete task " + md5sum.slice(0, 8) + "... and its result artifacts?")) return;
    try {
      if (triggerButton) { triggerButton.disabled = true; triggerButton.textContent = "Deleting..."; }
      var response = await A.authFetch("/compute/api/delete/" + encodeURIComponent(md5sum), { method: "DELETE" });
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(payload.message || payload.error || "Failed to delete task.");
      removeTaskFromClientState(md5sum);
      updateSummary(); renderTasks();
      showToast("Task " + md5sum.slice(0, 8) + "... deleted.", "info");
    } catch (error) {
      if (triggerButton) { triggerButton.disabled = false; triggerButton.textContent = "Delete"; }
      showToast(error.message || "Delete request failed.", "error");
    }
  }

  function triggerLogout() {
    A.authFetch("/compute/api/auth/logout", { method: "POST" })
      .finally(function () {
        A.clearToken();
        window.location.href = "/compute/login";
      });
  }

  async function deleteSelectedTasks() {
    var md5sums = Array.from(state.selected);
    if (!md5sums.length) { showToast("No tasks selected.", "error"); return; }
    if (!window.confirm("Delete " + md5sums.length + " selected task(s) and their artifacts?")) return;
    try {
      var response = await A.authFetch("/compute/api/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ md5sums: md5sums }),
      });
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(payload.message || payload.error || "Batch delete failed.");
      var deleted = Array.isArray(payload.deleted) ? payload.deleted : [];
      deleted.forEach(function (m) { removeTaskFromClientState(m); });
      updateSummary(); renderTasks();
      if (deleted.length) showToast("Deleted " + deleted.length + " task(s).", "info");
      else showToast("No tasks were deleted.", "error");
    } catch (error) {
      showToast(error.message || "Batch delete failed.", "error");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
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

    updateSummary(); renderTasks();

    document.getElementById("taskSearch").addEventListener("input", function (event) {
      state.query = event.target.value || ""; renderTasks();
    });
    document.getElementById("statusFilters").addEventListener("click", function (event) {
      var chip = event.target.closest(".chip");
      if (!chip) return;
      setActiveFilter(chip.dataset.filter || "all");
    });
    document.getElementById("refreshBtn").addEventListener("click", function () { window.location.reload(); });
    document.getElementById("logoutBtn").addEventListener("click", triggerLogout);
    document.getElementById("selectVisibleBtn").addEventListener("click", function () {
      getFilteredTasks().filter(function (t) { return Boolean(t.can_delete); }).forEach(function (t) { state.selected.add(t.md5); });
      renderTasks();
    });
    document.getElementById("clearSelectionBtn").addEventListener("click", function () { state.selected.clear(); renderTasks(); });
    document.getElementById("deleteSelectedBtn").addEventListener("click", deleteSelectedTasks);

    document.getElementById("taskList").addEventListener("change", function (event) {
      var cb = event.target.closest("input[data-action='toggle-select']");
      if (!cb || !cb.dataset.md5) return;
      if (cb.checked) state.selected.add(cb.dataset.md5);
      else state.selected.delete(cb.dataset.md5);
      updateAdminTools();
    });

    document.getElementById("taskList").addEventListener("click", function (event) {
      var btn = event.target.closest("button[data-action]");
      if (!btn) return;
      var action = btn.dataset.action;
      if (action === "toggle-error") {
        event.stopPropagation();
        toggleErrorBubble(btn);
        return;
      }
      var md5sum = btn.dataset.md5;
      if (action === "download") downloadFile(md5sum);
      else if (action === "results") openResults(md5sum);
      else if (action === "cancel") cancelFile(md5sum, btn);
      else if (action === "delete") deleteFile(md5sum, btn);
    });

    document.addEventListener("click", function (event) {
      var copyBtn = event.target.closest("button[data-action='copy-error']");
      if (copyBtn) {
        event.stopPropagation();
        copyActiveError(copyBtn);
        return;
      }
      if (!event.target.closest(".error-help") && !event.target.closest("#taskErrorPopover")) closeErrorBubbles();
    });
    window.addEventListener("resize", closeErrorBubbles);
  });
})();
