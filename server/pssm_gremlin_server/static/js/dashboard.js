/* REvoDesign GREMLIN Server — Dashboard page logic */
/* SPDX-License-Identifier: GPL-3.0-only */

(function () {
  var A = window.REvoDesignAuth;
  var T = window.REvoDesignTheme;

  var allTasks = window.__DASHBOARD_TASKS__;
  var isAdmin = window.__DASHBOARD_IS_ADMIN__;
  var currentUser = window.__DASHBOARD_USER__;

  var state = {
    query: "",
    filter: "all",
    selected: new Set(),
  };

  var statusMap = {
    "pending": { label: "Pending", css: "status-pending", accent: "var(--pending)" },
    "running": { label: "Running", css: "status-running", accent: "var(--running)" },
    "packing results": { label: "Packing Results", css: "status-packing", accent: "var(--packing)" },
    "finished": { label: "Finished", css: "status-finished", accent: "var(--finished)" },
    "failed": { label: "Failed", css: "status-failed", accent: "var(--failed)" },
    "cancelled": { label: "Cancelled", css: "status-cancelled", accent: "var(--cancelled)" },
    "deleted:finshed": { label: "Deleted (Finished)", css: "status-deleted", accent: "var(--deleted)" },
    "deleted:cancel": { label: "Deleted (Cancel)", css: "status-deleted", accent: "var(--deleted)" },
  };

  var runningTraceFallback = [
    "hhblits: searching for co-evolutionary sequences [running]",
    "hhfilter: filtering co-evolutionary [pending]",
    "GREMLIN: calculating co-evolution signals [pending]",
    "PSI-Blast: searching for consensus profile [pending]",
  ].join("\n");

  function escapeHtml(input) {
    return String(input ?? "")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
  }

  function getStatusMeta(status) {
    return statusMap[status] || { label: status || "Unknown", css: "status-cancelled", accent: "var(--cancelled)" };
  }

  function getStatusTrace(task) {
    if (task.status !== "running") return "";
    return task.running_trace || runningTraceFallback;
  }

  function normalizeTraceLabel(label) {
    var raw = String(label || "").trim();
    if (!raw) return "-";
    if (/^gremlin\s*:/i.test(raw)) return raw.replace(/^gremlin\s*:/i, "GREMLIN:");
    if (/^blast\s*:/i.test(raw)) return raw.replace(/^blast\s*:/i, "PSI-Blast:");
    return raw;
  }

  function parseStatusTrace(traceText) {
    var lines = String(traceText || "").split(/\n+/).map(function (l) { return l.trim(); }).filter(Boolean);
    return lines.map(function (line) {
      var match = line.match(/^(.*?)(?:\s*\[(done|running|pending)\])?$/i);
      var label = normalizeTraceLabel(match ? match[1] : line);
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
    var counts = { total: allTasks.length, pending: 0, running: 0, packing: 0, finished: 0, failed: 0, cancelled: 0, deleted: 0 };
    allTasks.forEach(function (task) {
      if (task.status === "pending") counts.pending += 1;
      if (task.status === "running") counts.running += 1;
      if (task.status === "packing results") counts.packing += 1;
      if (task.status === "finished") counts.finished += 1;
      if (task.status === "failed") counts.failed += 1;
      if (task.status === "cancelled") counts.cancelled += 1;
      if (task.status === "deleted:finshed" || task.status === "deleted:cancel") counts.deleted += 1;
    });
    document.getElementById("totalTasks").textContent = counts.total;
    document.getElementById("inQueue").textContent = counts.pending;
    document.getElementById("inRunning").textContent = counts.running;
    document.getElementById("packingResults").textContent = counts.packing;
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

  function renderTasks() {
    var list = document.getElementById("taskList");
    var tasks = getFilteredTasks();
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
      var canDownload = task.status === "finished";
      var canCancel = task.status === "pending" || task.status === "running";
      var canDelete = Boolean(task.can_delete);
      var hasError = task.status === "failed" && task.error;
      var selected = state.selected.has(task.md5);
      var statusTrace = getStatusTrace(task);
      var traceClass = statusTrace ? "has-trace" : "";
      var traceAttr = statusTrace ? ' tabindex="0" aria-haspopup="true"' : "";
      var tracePopover = statusTrace ? renderStatusTracePopover(statusTrace) : "";

      card.innerHTML =
        '<header class="task-head">' +
          '<div class="task-head-left">' +
            (canDelete ? '<label class="task-select-wrap" title="Select task for batch delete"><input class="task-select" type="checkbox" data-action="toggle-select" data-md5="' + escapeHtml(task.md5) + '" ' + (selected ? "checked" : "") + '></label>' : "") +
            '<div>' +
              '<h2 class="task-title">' + escapeHtml(task.fasta_fn || "Unknown FASTA") + '</h2>' +
              '<p class="task-id">' + escapeHtml(task.md5) + '</p>' +
              (isAdmin ? '<span class="owner-chip">Owner: ' + escapeHtml(task.owner || "-") + '</span>' : "") +
            '</div>' +
          '</div>' +
          '<span class="status-pill ' + meta.css + ' ' + traceClass + '"' + traceAttr + '>' + escapeHtml(meta.label) + tracePopover + '</span>' +
          (hasError ? '<span class="error-indicator" title="' + escapeHtml(task.error) + '" aria-label="Error details">?</span>' : "") +
        '</header>' +
        '<div class="meta-grid">' +
          '<div class="meta-box"><p class="meta-label">Submitted</p><p class="meta-value">' + escapeHtml(task.submitted_time || "-") + '</p></div>' +
          '<div class="meta-box"><p class="meta-label">Finished</p><p class="meta-value">' + escapeHtml(task.finished_time || "-") + '</p></div>' +
          '<div class="meta-box"><p class="meta-label">Wall Time</p><p class="meta-value">' + escapeHtml(String(task.walltime ?? "-")) + '</p></div>' +
        '</div>' +
        '<details class="sequence"><summary>Sequence Snapshot</summary><pre>' + escapeHtml(task.sequence || "-") + '</pre></details>' +
        '<div class="actions">' +
          (canDownload ? '<button class="task-btn download" data-action="download" data-md5="' + escapeHtml(task.md5) + '">Download</button>' : "") +
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

  async function downloadFile(md5sum) {
    try {
      var response = await A.authFetch("/PSSM_GREMLIN/api/download/" + encodeURIComponent(md5sum));
      if (!response.ok) {
        var data = await response.json().catch(function () { return {}; });
        throw new Error(data.message || data.error || "Download failed (HTTP " + response.status + ")");
      }
      var blob = await response.blob();
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      // ponytail: let the server's Content-Disposition header name the file
      a.download = "";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 100);
    } catch (error) {
      showToast(error.message || "Download failed", "error");
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
      var response = await A.authFetch("/PSSM_GREMLIN/api/cancel/" + encodeURIComponent(md5sum), { method: "POST" });
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
      var response = await A.authFetch("/PSSM_GREMLIN/api/delete/" + encodeURIComponent(md5sum), { method: "DELETE" });
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
    A.authFetch("/PSSM_GREMLIN/api/auth/logout", { method: "POST" })
      .finally(function () {
        A.clearToken();
        window.location.href = "/PSSM_GREMLIN/login";
      });
  }

  async function deleteSelectedTasks() {
    var md5sums = Array.from(state.selected);
    if (!md5sums.length) { showToast("No tasks selected.", "error"); return; }
    if (!window.confirm("Delete " + md5sums.length + " selected task(s) and their artifacts?")) return;
    try {
      var response = await A.authFetch("/PSSM_GREMLIN/api/delete", {
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
      var md5sum = btn.dataset.md5;
      if (action === "download") downloadFile(md5sum);
      else if (action === "cancel") cancelFile(md5sum, btn);
      else if (action === "delete") deleteFile(md5sum, btn);
    });
  });
})();
